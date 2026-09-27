"""Local state for native Codex agents; no model, shell, scheduler, or network calls.

CLI: python3 harness/ledger.py --db /absolute/state.sqlite COMMAND < request.json
Every request has task_id; mutations also have owner (except create). Commands:
  create: kind(doc|code), description, acceptance[str], authorization_scope[str],
          publication_required(bool), refs[str] (optional), closeout (optional)
          closeout={mode:managed,github_paths:[repo-relative paths]} or
          {mode:local-only|read-only,reason:text}; omitted keeps legacy behavior
  configure-hooks: output_owner(personal|endix|mixed), destinations[objects],
                   write_paths[absolute paths], requirements[{id,kind:evidence|child,target}]
  before-write: operation_id, destination_id, workspace, target, operation,
                payload_path, payload_sha256, authorization_ref
  after-write: operation_id, attempt, workspace, target,
               outcome(verified|absent|uncertain|conflict), evidence_path;
               readback_path required only for verified
  before-delegate: delegation_id, role(worker|reviewer), description,
                   acceptance[str], write_paths[absolute paths], refs[str]
  after-delegate: delegation_id, agent_id, outcome(finished|blocked), evidence_path
  requirement: requirement_id, evidence_path, agent_id (independent verifier)
  claim / status / context / pause / resume / complete: no additional fields
  route: skills[{name, path, sha256, source:"local"}] or immutable GitHub pins
         {name, path, sha256, repository(owner/repo), commit, source_path, url}
  artifact: path, worker_id
  check: artifact_sha256, evidence_path, check_id, agent_id, exit_code;
         failure_kind(check|auth|access, optional); source_paths maps declared
         GitHub paths to absolute local files (filled automatically by runner)
  review: artifact_sha256, evidence_path, agent_id, verdict(approved|changes),
          covered_conditions[zero-based acceptance indices]
  repair: reason_ref
  block: kind(auth|access|requirements|io), reason_ref
  clear-blocker: resolution_ref; publication_id (optional)
  feedback: category(task|skill|code|policy), reference
  enqueue: publication_id, adapter(local|remote), target, artifact_sha256
  approve: publication_id, target, artifact_sha256, approved_by, approval_ref
  publish: publication_id
  publication-error: publication_id, kind(auth|access|io|uncertain), reason_ref
  receipt: publication_id, target, artifact_sha256, readback_path, receipt_ref
  closeout: service(notion|github), receipt_ref; notion uses target, summary_path,
            readback_path; github uses repository, commit, files[{path,
            local_path,readback_path}]. The runner fills local_path from path.

One primary file per task; split larger work into bounded native-agent tasks.
Only summaries, references, hashes, and supplied skill text are retained. Do not
provide secrets or mail bodies, including in skills, summaries, or references.
Evidence files are hashed, never copied into the ledger. Evidence/approval/agent
identities are trusted coordinator attestations, not authenticated identities or
proof that native agents/tests ran. GitHub metadata is validated for a matching
immutable commit URL; byte hashes are verified locally. Remote provenance and
repository trust must be checked by the coordinator before supplying pins.

Local guarantees assume a local POSIX filesystem, cooperative ledger clients,
and durable SQLite/fsync semantics. A DB-wide flock spans transactions and file
publication. Atomic no-clobber linking protects even against competing writers
using another DB. Existing unequal content is NEVER replaced. Keep the SQLite
DB and its journal together during recovery. Status recomputes validity without
writing; the next owner mutation persists any observed invalidation.

Remote publication is intent/receipt ONLY. publish exposes reconciliation-required
and never sends anything. The caller must reconcile remotely and supply a readback
file and receipt bound to the approved target/hash. There is no remote exactly-once
claim. Permissions/approval truth, external races after readback, and OS/process
identity enforcement remain outside this ledger's boundary.
"""

import argparse
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import stat
import sys
import tempfile
from urllib.parse import quote, urlsplit
import uuid


class LedgerError(ValueError):
    """Invalid input or a rejected state transition (no input echoed)."""


def require(condition, message):
    if not condition:
        raise LedgerError(message)


def text(value, name="text", limit=2000):
    require(isinstance(value, str) and 0 < len(value) <= limit
            and value.strip() == value and not any(ord(c) < 32 for c in value),
            "invalid " + name)
    return value


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value),
            "invalid identifier")
    return value


def choice(value, values):
    require(isinstance(value, str) and value in values, "invalid choice")
    return value


def digest(value):
    require(isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value), "invalid sha256")
    return value


def strings(value, name, empty=False):
    require(isinstance(value, list) and (empty or value) and len(value) <= 64,
            "invalid " + name)
    return [text(v, name) for v in value]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def unique_object(pairs):
    result = dict(pairs)
    require(len(result) == len(pairs), "duplicate JSON fields")
    return result


def sha(data):
    return hashlib.sha256(data).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def path_name(value):
    p = Path(text(value, "path", 4096))
    try:
        resolved = p.resolve()
    except RuntimeError:
        raise LedgerError("path contains a symlink loop") from None
    require(p.is_absolute() and str(p) == str(resolved),
            "path must be absolute, canonical, and have no symlink components")
    return str(p)


def read_file(value, limit=64 * 1024 * 1024):
    path = path_name(value)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size <= limit,
                "expected a bounded regular file")
        data = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    require(len(data) <= limit and (before.st_size, before.st_mtime_ns)
            == (after.st_size, after.st_mtime_ns), "file changed while reading")
    return data


def snapshot(path):
    return {"path": path_name(path), "sha256": sha(read_file(path))}


def current(record):
    try:
        return sha(read_file(record["path"])) == record["sha256"]
    except LedgerError:
        return False


def plain_summary(data):
    """Compare simple Markdown summaries without changing content-bearing lines."""
    try:
        body = data.decode("utf-8").replace("\r\n", "\n")
    except UnicodeDecodeError:
        raise LedgerError("summary must be UTF-8") from None
    if re.search(r"(?m)^\s*(?:```|~~~|\$\$|\\\[|\\\])", body):
        return body.rstrip("\n")
    return "\n".join(line for line in body.splitlines() if line.strip())


# Required fields beyond task_id/owner; strict schemas keep accidental payloads out.
FIELDS = {
    "create": ("kind description acceptance authorization_scope publication_required", "refs closeout"),
    "status": ("", ""), "claim": ("", ""), "context": ("", ""),
    "pause": ("", ""), "resume": ("", ""), "complete": ("", ""),
    "route": ("skills", ""), "artifact": ("path worker_id", ""),
    "check": ("artifact_sha256 evidence_path check_id agent_id exit_code", "failure_kind source_paths"),
    "review": ("artifact_sha256 evidence_path agent_id verdict covered_conditions", ""),
    "repair": ("reason_ref", ""), "block": ("kind reason_ref", ""),
    "clear-blocker": ("resolution_ref", "publication_id"),
    "feedback": ("category reference", ""),
    "enqueue": ("publication_id adapter target artifact_sha256", ""),
    "approve": ("publication_id target artifact_sha256 approved_by approval_ref", ""),
    "publish": ("publication_id", ""),
    "publication-error": ("publication_id kind reason_ref", ""),
    "receipt": ("publication_id target artifact_sha256 readback_path receipt_ref", ""),
    "closeout": ("service receipt_ref", "target summary_path readback_path repository commit files"),
    "configure-hooks": ("output_owner destinations write_paths requirements", ""),
    "before-write": ("operation_id destination_id workspace target operation payload_path payload_sha256 authorization_ref", ""),
    "after-write": ("operation_id attempt workspace target outcome evidence_path", "readback_path"),
    "before-delegate": ("delegation_id role description acceptance write_paths refs", ""),
    "after-delegate": ("delegation_id agent_id outcome evidence_path", ""),
    "requirement": ("requirement_id evidence_path agent_id", ""),
}

NEXT_ACTION = {
    "created": "claim", "routing": "route", "working": "artifact", "verifying": "check",
    "review-ready": "review", "repair-required": "repair", "blocked": "resolve-blocker",
    "awaiting-approval": "approve-publication", "publishing": "publish-or-reconcile",
    "awaiting-requirements": "resolve-requirements", "awaiting-closeout": "closeout", "ready-to-complete": "complete", "done": "none", "paused": "resume",
}


def validate(action, data):
    require(isinstance(action, str) and action in FIELDS and isinstance(data, dict), "unknown command or invalid object")
    required, optional = (set(s.split()) for s in FIELDS[action])
    required.add("task_id")
    if action not in {"create", "status"}:
        required.add("owner")
    require(required <= data.keys() <= required | optional, "missing or unexpected fields")
    identifier(data["task_id"])
    if "owner" in data:
        identifier(data["owner"])


class Ledger:
    def __init__(self, db):
        self.path = path_name(str(db))

    @contextmanager
    def locked(self):
        # ponytail: DB-wide lock; use per-task locks only if local throughput matters.
        fd = os.open(self.path + ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        with os.fdopen(fd, "rb") as lock:
            require(stat.S_ISREG(os.fstat(lock.fileno()).st_mode), "lock must be a regular file")
            fcntl.flock(lock, fcntl.LOCK_EX)
            fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
            try:
                require(stat.S_ISREG(os.fstat(fd).st_mode), "database must be a regular file")
            finally:
                os.close(fd)
            with closing(sqlite3.connect(self.path, timeout=30)) as db:
                self.db = db
                db.execute("PRAGMA synchronous=FULL")
                db.execute("CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, request TEXT NOT NULL, state TEXT NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS outbox (task_id TEXT, id TEXT, request TEXT NOT NULL, state TEXT NOT NULL, PRIMARY KEY(task_id,id), UNIQUE(task_id,request))")
                db.commit()
                db.execute("BEGIN IMMEDIATE")
                try:
                    yield
                finally:
                    # All expected rejections are committed by dispatch; unexpected errors roll back.
                    db.rollback()
            del self.db

    def save(self):
        self.task["updated_at"] = now()
        stage = self.stage()
        self.task["stage"] = stage
        self.task["next_action"] = NEXT_ACTION[stage]
        if not self.task["stages"] or self.task["stages"][-1]["stage"] != stage:
            self.task["stages"].append({"stage": stage, "at": now(), "run_id": self.task["run_id"]})
        self.db.execute("UPDATE tasks SET state=? WHERE id=?", (canonical(self.task), self.task["task_id"]))
        for p in self.pubs:
            self.db.execute("UPDATE outbox SET state=? WHERE task_id=? AND id=?",
                            (canonical(p), self.task["task_id"], p["publication_id"]))

    def stage(self):
        t = self.task
        pubs = [p for p in self.pubs if p["status"] != "superseded"]
        if t["paused"]:
            return "paused"
        if t["blocker"] or any(p["status"] in {"blocked", "conflict"} for p in pubs):
            return "blocked"
        if t["owner"] is None:
            return "created"
        if not t["skills"]:
            return "routing"
        if t["repair_open"] or not t["artifact"]:
            return "working"
        if t["work_status"] == "repair-required":
            return "repair-required"
        if not t["check"]:
            return "verifying"
        if not t["review"]:
            return "review-ready"
        if (t["request"]["publication_required"] and not pubs
                or any(p["status"] == "awaiting-approval" for p in pubs)):
            return "awaiting-approval"
        if any(p["status"] != "verified" for p in pubs):
            return "publishing"
        if self.closeout_missing():
            return "awaiting-closeout"
        if self.requirements_missing():
            return "blocked" if t["blocker"] else "awaiting-requirements"
        return "done" if t["completion_requested"] else "ready-to-complete"

    def closeout_missing(self):
        policy = self.task["request"].get("closeout")
        if not policy or policy["mode"] != "managed":
            return False
        recorded = self.task.get("closeouts", {})
        return ("notion" not in recorded
                or (self.task["request"]["kind"] == "code" and not policy["github_paths"])
                or bool(policy["github_paths"] and "github" not in recorded))

    def source_paths(self):
        policy = self.task["request"].get("closeout", {})
        return policy.get("github_paths", []) if policy.get("mode") == "managed" else []

    def sources_current(self, record):
        sources = record.get("sources", {})
        return (set(sources) == set(self.source_paths())
                and all(self.work_current(item) for item in sources.values()))

    def work_current(self, record):
        try:
            return current(record)
        except OSError as exc:
            self.task["blocker"] = {"kind": "access" if isinstance(exc, PermissionError) else "io",
                                    "reference": "work-or-evidence-file-unavailable"}
            return False

    def refresh(self):
        t = self.task
        if any(record and not self.sources_current(record) for record in (t["check"], t["review"])):
            t["check"] = t["review"] = None
            t["closeouts"] = {}
            t["work_status"] = "repair-required"
            t["completion_requested"] = False
        if t["artifact"] and not self.work_current(t["artifact"]):
            t["check"] = t["review"] = None
            t["work_status"] = "repair-required"
            t["completion_requested"] = False
        if t["check"] and not self.work_current(t["check"]["evidence"]):
            t["check"] = t["review"] = None
            t["work_status"] = "repair-required"
            t["completion_requested"] = False
        if t["review"] and (not self.work_current(t["review"]["evidence"])
                            or t["review"]["agent_id"] in t["owners"] + t["workers"]):
            t["review"] = None
            t["work_status"] = "repair-required"
            t["completion_requested"] = False
        for service, record in list(t.get("closeouts", {}).items()):
            snapshots = ([record["summary"], record["readback"]] if service == "notion"
                         else [snapshot for file in record["files"]
                               for snapshot in (file["source"], file["readback"])])
            if (not t["artifact"] or record["artifact_sha256"] != t["artifact"]["sha256"]
                    or not all(self.work_current(item) for item in snapshots)):
                del t["closeouts"][service]
                t["completion_requested"] = False
        for p in self.pubs:
            if p["status"] == "verified":
                evidence = ({"path": p["target"], "sha256": p["artifact_sha256"]}
                            if p["adapter"] == "local" else p["receipt"]["readback"])
                try:
                    matches = current(evidence)
                except PermissionError:
                    p["status"] = "blocked"
                    p["blocker"] = {"kind": "access", "reference": "publication-readback-unavailable"}
                    continue
                except OSError:
                    matches = False
                if not matches:
                    p["status"] = "conflict" if p["adapter"] == "local" else "reconciliation-required"
                    p["blocker"] = {"kind": "conflict", "reference": "readback-no-longer-matches"}

    def result(self, include_context=False):
        result = json.loads(canonical(self.task))
        result["stage"] = self.stage()
        result["publications"] = self.pubs
        if include_context:
            result["context"] = {"request": self.task["request"], "refs": self.task["request"]["refs"],
                                 "skills": self.task["skills"]}
        result["skills"] = [{k: v for k, v in pin.items() if k != "text"} for pin in result["skills"]]
        # A status read is non-mutating but reports the current effective next action.
        result["next_action"] = NEXT_ACTION[result["stage"]]
        if hasattr(self, "hook_result"):
            result["hook"] = self.hook_result
        return result

    def dispatch(self, action, data):
        validate(action, data)
        with self.locked():
            if action == "create":
                return self.create(data)
            row = self.db.execute("SELECT state FROM tasks WHERE id=?", (data["task_id"],)).fetchone()
            require(row is not None, "task not found")
            self.task = json.loads(row[0])
            self.pubs = [json.loads(r[0]) for r in self.db.execute(
                "SELECT state FROM outbox WHERE task_id=? ORDER BY id", (data["task_id"],))]
            if action != "status":
                owner = self.task["owner"]
                require((action == "claim" and owner in {None, data["owner"]})
                        or (action == "resume" and self.task["paused"])
                        or owner == data["owner"], "owner conflict; explicit pause/resume required")
                require(not self.task["paused"] or action in {"pause", "resume", "context"}, "task paused")
            self.hook_result = None
            self.refresh()
            if action == "status":
                return self.result()
            try:
                if action not in {"claim", "pause", "resume", "context", "block", "clear-blocker", "feedback"}:
                    require(self.task["blocker"] is None, "task blocked")
                getattr(self, action.replace("-", "_"))(data)
            except OSError as exc:
                self.task["blocker"] = {"kind": "access" if isinstance(exc, PermissionError) else "io",
                                        "reference": "local-file-unavailable"}
                self.save()
                self.db.commit()
                raise LedgerError("local file access failed; task blocked") from None
            except LedgerError:
                self.save()
                self.db.commit()
                raise
            self.save()
            self.db.commit()
            return self.result(include_context=action in {"route", "context"})

    def create(self, d):
        choice(d["kind"], {"doc", "code"})
        require(type(d["publication_required"]) is bool, "publication_required must be boolean")
        request = {"kind": d["kind"], "description": text(d["description"], "description"),
                   "acceptance": strings(d["acceptance"], "acceptance"),
                   "authorization_scope": strings(d["authorization_scope"], "authorization_scope"),
                   "publication_required": d["publication_required"],
                   "refs": strings(d.get("refs", []), "refs", empty=True)}
        if "closeout" in d:
            policy = d["closeout"]
            require(isinstance(policy, dict) and "mode" in policy, "invalid closeout policy")
            mode = choice(policy["mode"], {"managed", "local-only", "read-only"})
            if mode == "managed":
                require(set(policy) == {"mode", "github_paths"}, "invalid managed closeout policy")
                paths = strings(policy["github_paths"], "github_paths", empty=True)
                require(d["kind"] != "code" or paths,
                        "managed code requires github_paths or an explicit local-only/read-only exception")
                for value in paths:
                    path = PurePosixPath(value)
                    require(not path.is_absolute() and ".." not in path.parts and str(path) == value
                            and value != ".", "invalid github path")
                require(len(set(paths)) == len(paths), "duplicate github paths")
                request["closeout"] = {"mode": mode, "github_paths": paths}
            else:
                require(set(policy) == {"mode", "reason"}, "invalid closeout exception")
                request["closeout"] = {"mode": mode, "reason": text(policy["reason"], "reason")}
        row = self.db.execute("SELECT request,state FROM tasks WHERE id=?", (d["task_id"],)).fetchone()
        self.pubs = []
        if row:
            require(row[0] == canonical(request), "task id already has a different request")
            self.task = json.loads(row[1])
            self.pubs = [json.loads(r[0]) for r in self.db.execute(
                "SELECT state FROM outbox WHERE task_id=? ORDER BY id", (d["task_id"],))]
            self.refresh()
            return self.result()
        self.task = {"task_id": d["task_id"], "request": request, "run_id": str(uuid.uuid4()),
                     "owner": None, "owners": [], "paused": False, "work_status": "not-started",
                     "stage": "created", "stages": [], "next_action": "claim", "blocker": None,
                     "retry_count": 0, "repair_open": False, "created_at": now(), "updated_at": now(),
                     "skills": [], "artifact": None, "artifact_history": [], "workers": [],
                     "check": None, "review": None, "feedback": [], "closeouts": {},
                     "completion_requested": False}
        self.db.execute("INSERT INTO tasks VALUES (?,?,?)", (d["task_id"], canonical(request), canonical(self.task)))
        self.save()
        self.db.commit()
        return self.result()

    def claim(self, d):
        require(not self.task["paused"], "use resume for a paused task")
        self.task["owner"] = d["owner"]
        if d["owner"] not in self.task["owners"]:
            self.task["owners"].append(d["owner"])

    def pause(self, d):
        self.task["paused"] = True

    def resume(self, d):
        require(self.task["paused"], "resume requires an explicit pause")
        self.task["paused"] = False
        self.task["run_id"] = str(uuid.uuid4())
        self.claim(d)
        self.refresh()

    def context(self, d):
        require(self.task["skills"], "route real skill files first")

    def route(self, d):
        require(isinstance(d["skills"], list) and 0 < len(d["skills"]) <= 16, "invalid skill list")
        pins = []
        for p in d["skills"]:
            local_fields = {"name", "path", "sha256", "source"}
            github_fields = {"name", "path", "sha256", "repository", "commit", "source_path", "url"}
            require(isinstance(p, dict) and (set(p) == local_fields or set(p) == github_fields),
                    "invalid skill pin fields")
            text(p["name"], "skill name", 128)
            digest(p["sha256"])
            path_name(p["path"])
            if set(p) == local_fields:
                require(p["source"] == "local", "invalid local skill source")
                require(Path(p["path"]).name == "SKILL.md", "local skill must be a SKILL.md file")
                pins.append(dict(p))
                continue
            require(isinstance(p["repository"], str) and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", p["repository"]),
                    "invalid GitHub repository")
            require(isinstance(p["commit"], str) and re.fullmatch(r"[a-f0-9]{40}", p["commit"]), "immutable 40-digit Git commit required")
            rel = PurePosixPath(text(p["source_path"], "source_path"))
            require(not rel.is_absolute() and ".." not in rel.parts and str(rel) == p["source_path"]
                    and rel.name == "SKILL.md", "invalid skill repository path")
            require(p["url"] == "https://github.com/" + p["repository"] + "/blob/" + p["commit"] + "/" + quote(str(rel), safe="/"),
                    "GitHub URL must match repository, immutable commit and path")
            pins.append(dict(p))
        require(len({p.get("url", p["path"]) for p in pins}) == len(pins)
                and len({p["name"] for p in pins}) == len(pins), "duplicate skills")
        if self.task["skills"]:
            require(pins == [{k: v for k, v in p.items() if k != "text"} for p in self.task["skills"]],
                    "skill versions are frozen for this task")
            return
        for p in pins:
            content = read_file(p["path"], 256 * 1024)
            require(sha(content) == p["sha256"], "skill sha256 mismatch")
            try:
                p["text"] = content.decode("utf-8")
            except UnicodeDecodeError:
                raise LedgerError("skill must be UTF-8") from None
            require(p["text"].strip(), "empty skill")
        self.task["skills"] = pins
        self.task["work_status"] = "working"

    def artifact(self, d):
        require(self.task["skills"], "route real skill files first")
        worker = identifier(d["worker_id"])
        artifact = {**snapshot(d["path"]), "worker_id": worker}
        old = self.task["artifact"]
        if old == artifact and not self.task["repair_open"]:
            return
        require(old is None or self.task["repair_open"], "changed artifact requires a bounded repair")
        self.task["artifact"] = artifact
        self.task["artifact_history"].append({**artifact, "at": now(), "run_id": self.task["run_id"]})
        for record in self.task.get("runtime_hooks", {}).get("writes", {}).values():
            if record["outcome"] in {"verified", "absent"} and record["binding"]["artifact_sha256"] != artifact["sha256"]:
                record["resolution_outcome"] = record["outcome"]
                record["outcome"] = "superseded"
        if worker not in self.task["workers"]:
            self.task["workers"].append(worker)
        self.task["check"] = self.task["review"] = None
        self.task["repair_open"] = False
        self.task["work_status"] = "artifact-recorded"
        self.task["completion_requested"] = False
        for p in self.pubs:
            if p["artifact_sha256"] != artifact["sha256"]:
                p["status"] = "superseded"
                p["updated_at"] = now()

    def exact_artifact(self, value):
        digest(value)
        require(self.task["artifact"] is not None and self.task["artifact"]["sha256"] == value
                and self.work_current(self.task["artifact"]) and not self.task["repair_open"], "artifact hash is not current")

    def check(self, d):
        self.exact_artifact(d["artifact_sha256"])
        require(self.task["work_status"] != "repair-required", "repair required before another check")
        require(type(d["exit_code"]) is int and 0 <= d["exit_code"] <= 255, "invalid exit_code")
        kind = d.get("failure_kind", "check")
        choice(kind, {"check", "auth", "access"})
        if kind in {"auth", "access"}:
            self.task["blocker"] = {"kind": kind, "reference": text(d["check_id"])}
        require(not (d["exit_code"] == 0 and kind != "check"),
                "auth/access errors cannot be successes")
        record = {"artifact_sha256": d["artifact_sha256"], "evidence": snapshot(d["evidence_path"]),
                  "check_id": text(d["check_id"]), "agent_id": identifier(d["agent_id"]),
                  "exit_code": d["exit_code"], "failure_kind": kind}
        paths = d.get("source_paths", {})
        require(isinstance(paths, dict) and set(paths) == set(self.source_paths()),
                "check source_paths must match declared GitHub paths")
        if paths:
            record["sources"] = {path: snapshot(local) for path, local in paths.items()}
        if self.task["check"] == record:
            return
        self.task["check"] = record
        self.task["review"] = None
        self.task["completion_requested"] = False
        self.task["work_status"] = "checked" if d["exit_code"] == 0 else "repair-required"
        if kind in {"auth", "access"}:
            self.task["blocker"] = {"kind": kind, "reference": record["check_id"]}

    def review(self, d):
        self.exact_artifact(d["artifact_sha256"])
        require(self.task["check"] and self.task["check"]["exit_code"] == 0
                and self.task["work_status"] != "repair-required", "valid mechanical check required")
        require(self.sources_current(self.task["check"]), "checked source files changed; repair required")
        agent = identifier(d["agent_id"])
        require(agent not in self.task["owners"] + self.task["workers"], "reviewer must be independent of coordinator and workers")
        choice(d["verdict"], {"approved", "changes"})
        covered = d["covered_conditions"]
        require(isinstance(covered, list) and all(type(i) is int for i in covered)
                and len(set(covered)) == len(covered)
                and all(0 <= i < len(self.task["request"]["acceptance"]) for i in covered), "invalid covered_conditions")
        require(d["verdict"] != "approved" or sorted(covered) == list(range(len(self.task["request"]["acceptance"]))),
                "review must cover every acceptance condition")
        record = {"artifact_sha256": d["artifact_sha256"], "agent_id": agent, "verdict": d["verdict"],
                  "covered_conditions": covered, "evidence": snapshot(d["evidence_path"])}
        if self.source_paths():
            record["sources"] = self.task["check"]["sources"]
        if self.task["review"] == record:
            return
        self.task["review"] = record
        self.task["completion_requested"] = False
        self.task["work_status"] = "verified" if d["verdict"] == "approved" else "repair-required"

    def repair(self, d):
        text(d["reason_ref"])
        require(self.task["artifact"] is not None, "no artifact to repair")
        if self.task["retry_count"] >= 3:
            self.task["blocker"] = {"kind": "retry-limit", "reference": d["reason_ref"]}
            raise LedgerError("repair limit reached (3)")
        self.task["retry_count"] += 1
        self.task["repair_open"] = True
        self.task["check"] = self.task["review"] = None
        self.task["closeouts"] = {}
        self.task["completion_requested"] = False
        self.task["work_status"] = "working"

    def block(self, d):
        choice(d["kind"], {"auth", "access", "requirements", "io"})
        self.task["blocker"] = {"kind": d["kind"], "reference": text(d["reason_ref"])}

    def clear_blocker(self, d):
        text(d["resolution_ref"])
        record = self.publication(d) if "publication_id" in d else self.task
        require(not record["blocker"] or record["blocker"]["kind"] != "retry-limit", "retry limit cannot be cleared")
        record["blocker"] = None
        record["resolution_ref"] = d["resolution_ref"]
        if "publication_id" in d and record["status"] == "blocked":
            record["status"] = "pending" if record["adapter"] == "local" else "reconciliation-required"
        if "publication_id" in d:
            record["updated_at"] = now()

    def feedback(self, d):
        choice(d["category"], {"task", "skill", "code", "policy"})
        entry = {"category": d["category"], "reference": text(d["reference"])}
        if entry not in self.task["feedback"]:
            self.task["feedback"].append(entry)

    def verified_work(self):
        require(self.task["work_status"] == "verified" and self.task["artifact"]
                and self.task["check"] and self.task["check"]["exit_code"] == 0
                and self.task["review"] and self.task["review"]["verdict"] == "approved", "checked and independently reviewed work required")
        require(self.task["review"]["agent_id"] not in self.task["owners"] + self.task["workers"],
                "reviewer must remain independent")
        self.exact_artifact(self.task["artifact"]["sha256"])
        require(self.sources_current(self.task["review"])
                and self.task["review"].get("sources", {}) == self.task["check"].get("sources", {}),
                "checked and reviewed source files changed; repair required")

    def complete(self, d):
        self.verified_work()
        require(all(p["artifact_sha256"] == self.task["artifact"]["sha256"]
                    for p in self.pubs if p["status"] != "superseded"),
                "publication is bound to an older artifact")
        require(not self.closeout_missing(), "required closeout evidence is absent or stale")
        require(not self.requirements_missing(), "required outputs, children, writes or delegations are incomplete")
        self.task["completion_requested"] = True

    def closeout(self, d):
        self.verified_work()
        policy = self.task["request"].get("closeout")
        require(policy and policy["mode"] == "managed", "managed closeout was not declared")
        service = choice(d["service"], {"notion", "github"})
        reference = text(d["receipt_ref"], "receipt_ref")
        artifact_sha256 = self.task["artifact"]["sha256"]
        if service == "notion":
            require(set(d) == {"task_id", "owner", "service", "target", "summary_path",
                               "readback_path", "receipt_ref"}, "invalid Notion closeout fields")
            target = text(d["target"], "Notion target", 4096)
            url = urlsplit(target)
            require(url.scheme == "https" and (url.hostname in {"notion.so", "www.notion.so"}
                    or bool(url.hostname and url.hostname.endswith(".notion.site"))
                    or (url.hostname == "app.notion.com" and
                        re.fullmatch(r"/p/[a-f0-9]{32}/?", url.path)))
                    and url.path.strip("/") and not url.username and not url.password
                    and not url.query and not url.fragment, "invalid Notion page URL")
            require(d["summary_path"] != d["readback_path"], "Notion readback must be separate")
            summary, readback = snapshot(d["summary_path"]), snapshot(d["readback_path"])
            body = plain_summary(read_file(summary["path"]))
            require(body and body == plain_summary(read_file(readback["path"])),
                    "Notion summary body readback mismatch")
            record = {"artifact_sha256": artifact_sha256, "target": target,
                      "summary": summary, "readback": readback,
                      "body_sha256": sha(body.encode("utf-8")), "receipt_ref": reference, "at": now()}
        else:
            require(set(d) == {"task_id", "owner", "service", "repository", "commit",
                               "files", "receipt_ref"}, "invalid GitHub closeout fields")
            require(policy["github_paths"], "GitHub closeout paths were not declared")
            repository = text(d["repository"], "repository", 256)
            require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository),
                    "invalid GitHub repository")
            commit = d["commit"]
            require(isinstance(commit, str) and re.fullmatch(r"[a-f0-9]{40}", commit),
                    "immutable 40-digit Git commit required")
            files = d["files"]
            require(isinstance(files, list) and len(files) == len(policy["github_paths"])
                    and all(isinstance(item, dict) and set(item) == {"path", "local_path", "readback_path"}
                            for item in files)
                    and sorted(item["path"] for item in files) == sorted(policy["github_paths"]),
                    "GitHub files must match declared paths")
            bound = []
            for item in files:
                require(item["local_path"] != item["readback_path"], "GitHub readback must be separate")
                source, readback = snapshot(item["local_path"]), snapshot(item["readback_path"])
                require(source == self.task["review"]["sources"][item["path"]],
                        "GitHub source differs from reviewed bytes; repair required")
                require(source["sha256"] == readback["sha256"], "GitHub file readback mismatch")
                bound.append({"path": item["path"], "source": source, "readback": readback,
                              "url": "https://github.com/" + repository + "/blob/" + commit + "/"
                                     + quote(item["path"], safe="/")})
            record = {"artifact_sha256": artifact_sha256, "repository": repository,
                      "commit": commit, "files": bound, "receipt_ref": reference, "at": now()}
        self.task["closeouts"][service] = record
        self.task["completion_requested"] = False

    def configure_hooks(self, d):
        """Freeze cooperative runtime contracts; supplied references are not permission."""
        require(self.task["artifact"] is None, "configure hooks before recording work")
        choice(d["output_owner"], {"personal", "endix", "mixed"})
        strings(d["write_paths"], "write_paths", empty=True)
        for path in d["write_paths"]:
            path_name(path)
        require(isinstance(d["destinations"], list) and len(d["destinations"]) <= 64,
                "invalid destinations")
        for dest in d["destinations"]:
            require(isinstance(dest, dict) and set(dest) ==
                    {"id", "service", "workspace", "target", "output_owner", "operations", "authorization_ref"},
                    "invalid destination")
            identifier(dest["id"])
            choice(dest["output_owner"], {"personal", "endix"})
            require(d["output_owner"] in {"mixed", dest["output_owner"]}, "destination ownership mismatch")
            for field in ("service", "workspace", "target", "authorization_ref"):
                text(dest[field], field, 4096)
            strings(dest["operations"], "operations")
        require(len({x["id"] for x in d["destinations"]}) == len(d["destinations"]), "duplicate destination")
        require(isinstance(d["requirements"], list) and len(d["requirements"]) <= 64,
                "invalid requirements")
        for item in d["requirements"]:
            require(isinstance(item, dict) and set(item) == {"id", "kind", "target"}, "invalid requirement")
            identifier(item["id"])
            choice(item["kind"], {"evidence", "child"})
            text(item["target"], "requirement target", 4096)
            if item["kind"] == "child":
                identifier(item["target"])
                require(item["target"] != self.task["task_id"], "task cannot depend on itself")
        require(len({x["id"] for x in d["requirements"]}) == len(d["requirements"]), "duplicate requirement")
        policy = {k: d[k] for k in ("output_owner", "destinations", "write_paths", "requirements")}
        old = self.task.get("runtime_hooks")
        if old:
            require(old["policy"] == policy, "runtime hook policy is frozen")
            return
        self.task["runtime_hooks"] = {"policy": policy, "writes": {}, "delegations": {}, "evidence": {}}

    def hooks(self):
        require(self.task.get("runtime_hooks"), "configure runtime hooks first")
        return self.task["runtime_hooks"]

    def before_write(self, d):
        self.verified_work()
        hooks = self.hooks()
        identifier(d["operation_id"])
        dest = next((x for x in hooks["policy"]["destinations"] if x["id"] == d["destination_id"]), None)
        require(dest is not None, "destination is not authorized by the frozen policy")
        require(all(d[k] == dest[k] for k in ("workspace", "target", "authorization_ref"))
                and d["operation"] in dest["operations"], "write destination, operation or authorization mismatch")
        payload = snapshot(d["payload_path"])
        require(payload["sha256"] == digest(d["payload_sha256"]), "write payload changed")
        binding = {k: d[k] for k in ("destination_id", "workspace", "target", "operation", "authorization_ref")}
        binding.update(payload=payload, artifact_sha256=self.task["artifact"]["sha256"])
        existing = hooks["writes"].get(d["operation_id"])
        # A second ID must not silently duplicate an existing logical write.
        require(not any(key != d["operation_id"]
                        and all(x["binding"][field] == binding[field] for field in
                                ("destination_id", "workspace", "target", "operation", "authorization_ref", "artifact_sha256"))
                        and x["binding"]["payload"]["sha256"] == payload["sha256"]
                        for key, x in hooks["writes"].items()), "reuse the existing operation id")
        if existing:
            require(existing["binding"] == binding, "operation id is bound to different content")
            if existing["outcome"] == "verified":
                require(self.work_current(existing["readback"]) and self.work_current(existing["evidence"]), "verified readback is stale")
                self.hook_result = {"should_write": False, "reason": "already verified"}
                return
            require(existing["outcome"] == "absent" and self.work_current(existing["evidence"]),
                    "reconcile the previous attempt before retrying")
        attempt = existing["attempt"] + 1 if existing else 1
        hooks["writes"][d["operation_id"]] = {"binding": binding, "attempt": attempt,
                                              "outcome": "pending", "at": now()}
        self.task["completion_requested"] = False
        self.hook_result = {"should_write": True, "attempt": attempt, "operation_id": d["operation_id"]}

    def after_write(self, d):
        record = self.hooks()["writes"].get(d["operation_id"])
        require(record is not None, "no prepared write")
        require(type(d["attempt"]) is int and d["attempt"] == record["attempt"], "stale write attempt")
        require(all(d[k] == record["binding"][k] for k in ("workspace", "target")), "readback destination mismatch")
        outcome = choice(d["outcome"], {"verified", "absent", "uncertain", "conflict"})
        evidence = snapshot(d["evidence_path"])
        if outcome == "verified":
            # A delayed receipt may reconcile an old reviewed version after repair.
            require(self.work_current(record["binding"]["payload"]), "write version is stale")
            require("readback_path" in d and d["readback_path"] != record["binding"]["payload"]["path"],
                    "write readback must be separate")
            readback = snapshot(d["readback_path"])
            require(readback["sha256"] == record["binding"]["payload"]["sha256"], "write readback mismatch")
        else:
            require("readback_path" not in d, "nonverified write cannot carry a readback")
            readback = None
        require(record["outcome"] not in {"verified", "superseded"} or
                (outcome == "verified" and record["readback"] == readback and record["evidence"] == evidence),
                "verified write receipt cannot be replaced")
        stored_outcome = ("superseded" if outcome in {"verified", "absent"} and self.task["artifact"]
                          and record["binding"]["artifact_sha256"] != self.task["artifact"]["sha256"] else outcome)
        record.update(outcome=stored_outcome, resolution_outcome=outcome,
                      evidence=evidence, readback=readback, at=now())
        self.task["completion_requested"] = False
        self.hook_result = {"verified": outcome == "verified", "retry_allowed": outcome == "absent"}

    def before_delegate(self, d):
        hooks = self.hooks()
        require(self.task["skills"], "route skills before delegation")
        identifier(d["delegation_id"])
        role = choice(d["role"], {"worker", "reviewer"})
        text(d["description"], "description")
        strings(d["acceptance"], "acceptance")
        strings(d["refs"], "refs", empty=True)
        strings(d["write_paths"], "write_paths", empty=True)
        allowed = [Path(p) for p in hooks["policy"]["write_paths"]]
        for path in d["write_paths"]:
            path_name(path)
            require(any(Path(path).is_relative_to(p) for p in allowed), "delegation exceeds allowed write paths")
        if role == "reviewer":
            require(not d["write_paths"], "reviewer is read-only; coordinator saves its evidence")
            require(self.task["check"] and self.task["check"]["exit_code"] == 0
                    and self.task["work_status"] != "repair-required", "reviewer needs current check and artifact")
        contract = {k: d[k] for k in ("role", "description", "acceptance", "write_paths", "refs")}
        contract.update(task_id=self.task["task_id"], output_owner=hooks["policy"]["output_owner"],
                        authorization_scope=self.task["request"]["authorization_scope"],
                        skills=self.task["skills"], artifact=self.task["artifact"], check=self.task["check"])
        old = hooks["delegations"].get(d["delegation_id"])
        if old:
            require(old["contract"] == contract and old["outcome"] == "pending", "delegation id is already used")
        else:
            for record in hooks["delegations"].values():
                if record["outcome"] == "pending":
                    require(not any(Path(a).is_relative_to(Path(b)) or Path(b).is_relative_to(Path(a))
                                    for a in d["write_paths"] for b in record["contract"]["write_paths"]),
                            "active delegation write paths overlap")
            hooks["delegations"][d["delegation_id"]] = {"contract": contract, "outcome": "pending"}
        self.task["completion_requested"] = False
        self.hook_result = {"contract": contract}

    def after_delegate(self, d):
        record = self.hooks()["delegations"].get(d["delegation_id"])
        require(record is not None, "no prepared delegation")
        agent = identifier(d["agent_id"])
        require(agent not in self.task["owners"], "delegate must be a different agent")
        if record["contract"]["role"] == "reviewer":
            require(agent not in self.task["workers"], "review delegate authored task work")
        outcome = choice(d["outcome"], {"finished", "blocked"})
        result = {"agent_id": agent, "outcome": outcome, "evidence": snapshot(d["evidence_path"])}
        if record["outcome"] == "finished":
            require(all(record[k] == v for k, v in result.items()), "delegation result is already recorded")
        record.update(result)
        if record["contract"]["role"] == "worker" and agent not in self.task["workers"]:
            self.task["workers"].append(agent)
        self.refresh()
        self.task["completion_requested"] = False

    def requirement(self, d):
        hooks = self.hooks()
        item = next((x for x in hooks["policy"]["requirements"] if x["id"] == d["requirement_id"]), None)
        require(item and item["kind"] == "evidence", "unknown evidence requirement")
        agent = identifier(d["agent_id"])
        require(agent not in self.task["owners"] + self.task["workers"], "requirement verifier must be independent")
        self.verified_work()
        hooks["evidence"][item["id"]] = {"target": item["target"], "agent_id": agent,
                                         "artifact_sha256": self.task["artifact"]["sha256"],
                                         "sources": self.task["review"].get("sources", {}),
                                         "evidence": snapshot(d["evidence_path"])}
        self.task["completion_requested"] = False

    def requirements_missing(self):
        hooks = self.task.get("runtime_hooks")
        if not hooks:
            return False  # Existing tasks retain their original completion contract.
        seen = getattr(self, "dependency_stack", set()) | {self.task["task_id"]}
        if len(seen) > 16:
            return True
        for record in hooks["writes"].values():
            if record["outcome"] == "superseded":
                continue
            if (record["outcome"] != "verified" or not self.work_current(record["evidence"])
                    or not self.work_current(record["readback"]) or not self.work_current(record["binding"]["payload"])
                    or not self.task["artifact"]
                    or record["binding"]["artifact_sha256"] != self.task["artifact"]["sha256"]):
                return True
        if any(r["outcome"] != "finished" or not self.work_current(r["evidence"])
               for r in hooks["delegations"].values()):
            return True
        for item in hooks["policy"]["requirements"]:
            if item["kind"] == "evidence":
                record = hooks["evidence"].get(item["id"])
                if (not record or not self.work_current(record["evidence"])
                        or not self.task["artifact"]
                        or record["artifact_sha256"] != self.task["artifact"]["sha256"]
                        or not self.sources_current(record)
                        or record["agent_id"] in self.task["owners"] + self.task["workers"]):
                    return True
            else:
                if item["target"] in seen:
                    return True
                row = self.db.execute("SELECT state FROM tasks WHERE id=?", (item["target"],)).fetchone()
                if not row:
                    return True
                child = Ledger(self.path)
                child.db, child.task, child.dependency_stack = self.db, json.loads(row[0]), seen
                child.pubs = [json.loads(r[0]) for r in self.db.execute(
                    "SELECT state FROM outbox WHERE task_id=? ORDER BY id", (item["target"],))]
                child.refresh()
                if child.stage() != "done":
                    return True
        return False

    def publication(self, d):
        identifier(d["publication_id"])
        p = next((p for p in self.pubs if p["publication_id"] == d["publication_id"]), None)
        require(p is not None, "publication not found")
        require(p["status"] != "superseded", "publication was superseded by an artifact revision")
        return p

    def enqueue(self, d):
        self.verified_work()
        self.exact_artifact(d["artifact_sha256"])
        identifier(d["publication_id"])
        choice(d["adapter"], {"local", "remote"})
        target = text(d["target"], "target", 4096)
        if d["adapter"] == "local":
            path_name(target)
            require(target not in {self.path, self.path + ".lock", self.task["artifact"]["path"]}
                    and not target.startswith(self.path + "-"), "target is protected")
        else:
            try:
                url = urlsplit(target)
            except ValueError:
                raise LedgerError("invalid remote target URL") from None
            require(url.scheme == "https" and url.hostname and not url.username and not url.password
                    and not url.query and not url.fragment, "remote target must be a credential-free HTTPS resource URL")
        request = {k: d[k] for k in ("adapter", "target", "artifact_sha256")}
        encoded = canonical(request)
        existing = next((p for p in self.pubs if p["publication_id"] == d["publication_id"]), None)
        if existing is not None:
            require(all(existing[k] == v for k, v in request.items()), "publication id already has a different request")
        else:
            existing = next((p for p in self.pubs if all(p[k] == v for k, v in request.items())), None)
        if existing is not None:
            if existing["status"] == "superseded":
                existing["status"] = "pending" if existing["approval"] else "awaiting-approval"
                existing["receipt"] = existing["blocker"] = None
                existing["updated_at"] = now()
                self.task["completion_requested"] = False
            return
        p = {**request, "publication_id": d["publication_id"], "status": "awaiting-approval",
             "approval": None, "attempts": 0, "blocker": None, "receipt": None, "created_at": now(), "updated_at": now()}
        self.db.execute("INSERT INTO outbox VALUES (?,?,?,?)", (d["task_id"], d["publication_id"], encoded, canonical(p)))
        self.pubs.append(p)
        self.task["completion_requested"] = False

    def binding(self, p, d):
        require(d["target"] == p["target"] and digest(d["artifact_sha256"]) == p["artifact_sha256"], "approval/receipt target or hash mismatch")
        self.exact_artifact(p["artifact_sha256"])

    def approve(self, d):
        p = self.publication(d)
        self.binding(p, d)
        approval = {"target": p["target"], "artifact_sha256": p["artifact_sha256"],
                    "approved_by": identifier(d["approved_by"]), "reference": text(d["approval_ref"])}
        if p["approval"]:
            require(p["approval"] == approval, "approval already recorded; cannot replace")
            return
        p["approval"] = approval
        p["status"] = "pending"
        p["updated_at"] = now()

    def approved(self, p):
        self.verified_work()
        require(p["approval"] is not None, "publication approval required")
        self.binding(p, p["approval"])
        require(not p["blocker"] or p["blocker"]["kind"] not in {"auth", "access"}, "publication access blocker requires explicit resolution")

    def publish(self, d):
        p = self.publication(d)
        self.approved(p)
        if p["status"] == "verified":
            return
        if p["adapter"] == "remote":
            p["status"] = "reconciliation-required"
            p["updated_at"] = now()
            return
        p["status"] = "pending"
        p["attempts"] += 1
        p["updated_at"] = now()
        self.save()
        self.db.commit()  # Durable intent BEFORE any output side effect; flock remains held.
        try:
            data = read_file(self.task["artifact"]["path"])
            require(sha(data) == p["artifact_sha256"], "artifact changed before publication")
            target = Path(path_name(p["target"]))
            if not target.exists():
                fd, temporary = tempfile.mkstemp(prefix=".ledger-", dir=target.parent)
                try:
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(data)
                        stream.flush()
                        os.fsync(stream.fileno())
                    try:
                        os.link(temporary, target)  # Atomic create, NEVER os.replace.
                    except FileExistsError:
                        pass
                finally:
                    os.unlink(temporary)
                directory = os.open(target.parent, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            self.test_crash(target)
            require(sha(read_file(str(target))) == p["artifact_sha256"], "publication target content conflict")
            p["status"] = "verified"
            p["blocker"] = None
            p["receipt"] = {"target": str(target), "sha256": p["artifact_sha256"], "readback_at": now()}
        except (OSError, LedgerError) as exc:
            p["status"] = "conflict" if isinstance(exc, LedgerError) else "blocked"
            p["blocker"] = {"kind": "conflict" if isinstance(exc, LedgerError) else
                            "access" if isinstance(exc, PermissionError) else "io", "reference": "local-publication-needs-reconciliation"}
        finally:
            self.db.execute("BEGIN IMMEDIATE")
        p["updated_at"] = now()

    def test_crash(self, target):
        """Test-only real process death, guarded to a dedicated temporary root."""
        root = os.environ.get("HARNESS_LEDGER_TEST_CRASH_ROOT")
        if os.environ.get("HARNESS_LEDGER_TEST_CRASH_AFTER_SAVE") == "1" and root:
            root = Path(root).resolve()
            if (root.parent == Path(tempfile.gettempdir()).resolve() and root.name.startswith("harness-ledger-test-")
                    and Path(self.path).is_relative_to(root) and target.is_relative_to(root)):
                os._exit(91)

    def publication_error(self, d):
        p = self.publication(d)
        choice(d["kind"], {"auth", "access", "io", "uncertain"})
        p["blocker"] = {"kind": d["kind"], "reference": text(d["reason_ref"])}
        p["status"] = "reconciliation-required" if d["kind"] == "uncertain" else "blocked"
        p["updated_at"] = now()

    def receipt(self, d):
        p = self.publication(d)
        self.approved(p)
        require(p["adapter"] == "remote", "local publication uses its own readback")
        self.binding(p, d)
        readback = snapshot(d["readback_path"])
        require(readback["sha256"] == p["artifact_sha256"], "remote readback hash mismatch")
        p["receipt"] = {"target": p["target"], "sha256": p["artifact_sha256"], "readback": readback,
                        "reference": text(d["receipt_ref"]), "readback_at": now()}
        p["status"] = "verified"
        p["blocker"] = None
        p["updated_at"] = now()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", required=True, help="absolute SQLite path; parent directory must exist")
    parser.add_argument("command", choices=FIELDS)
    args = parser.parse_args()
    try:
        raw = sys.stdin.read(128 * 1024 + 1)
        require(len(raw) <= 128 * 1024, "request too large")
        result = Ledger(args.db).dispatch(args.command, json.loads(raw, object_pairs_hook=unique_object))
        print(canonical(result))
        return 1 if result["stage"] == "blocked" else 0
    except LedgerError as exc:
        print(canonical({"error": str(exc)}), file=sys.stderr)
        return 2
    except (json.JSONDecodeError, OSError, sqlite3.Error):
        print(canonical({"error": "request rejected; check input and task status"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
