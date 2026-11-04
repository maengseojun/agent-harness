"""Comprehension gate state: the part map, design and merge passes, waivers, answer capture and seals.
State lives in home_dir()/interviews/<repo slug>/ (map.json, passes.json, ledger.jsonl, open/<session>.json,
seals/); every worktree of a repository shares the slug. The model flows are in bin/maeng-interview."""
import json
import os
import re
import subprocess
import sys

from . import guard, receipts, state
from . import tree as treelib
from .common import git_out, home_dir, locked, now_iso, read_json, sha256, write_json
from .shellparse import SHELLS

WRAPPERS = ("<system-reminder>", "<task-notification>", "<cross-session-message>", "<side-sessions-event>",
            "<ci-monitor-event>")
OVERALL, LIMIT = "overall", 150  # LIMIT: changed lines at which a PR needs a merge pass (what harness-run calls one task)
WAIVE_PR = re.compile(r"\s*면제\s+#(\d+)\s+(\S.*)", re.S)
WAIVE_PART = re.compile(r"\s*면제\s+([^\s#]+)\s+(\S.*)", re.S)


class Refused(Exception):
    """A request the gate refuses; the text is for the agent."""


def warn(msg):
    print("maeng-harness: " + msg, file=sys.stderr)


# ---- state files ---------------------------------------------------------

def slug(repo):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", repo).strip("_") + "-" + sha256(repo)[:8]


def repo_key(cwd):
    """The state directory name of cwd's repository, or None without an origin remote (shortcut: such a repository
    has no gate; upgrade when a map is wanted for a repository with no remote)."""
    repo = guard.normalize_repo(git_out(cwd, "config", "--get", "remote.origin.url") or "")
    return slug(repo) if repo else None


def _file(key, name):
    return home_dir() / "interviews" / key / name


def load_map(key):
    """The part map, None without one; ValueError when the file is unreadable."""
    return read_json(_file(key, "map.json"))


def save_map(key, m):
    write_json(_file(key, "map.json"), m)  # callers that read first hold locked(_file(key, "map.json"))


def parts_of(m, rel):
    """Names of the parts whose path globs match the repo-relative path `rel`."""
    return [name for name, p in ((m or {}).get("parts") or {}).items()
            if any(treelib.glob_regex(g).match(rel) for g in p.get("paths") or [])]


def _load_passes(key):
    p = read_json(_file(key, "passes.json")) or {}
    p.setdefault("design", {})
    p.setdefault("merge", [])
    w = p.setdefault("waivers", {})
    w.setdefault("design", {})
    w.setdefault("pr", {})
    return p


def _update_passes(key, fn):
    path = _file(key, "passes.json")
    with locked(path):
        p = _load_passes(key)
        fn(p)
        write_json(path, p)


def passed(key, part, stage, digest=None):
    """design: `part` has a pass or a waiver. merge: a pass exists for the patch id `digest`, or PR `part` is waived."""
    p = _load_passes(key)
    if stage == "design":
        return part in p["design"] or part in p["waivers"]["design"]
    return str(part) in p["waivers"]["pr"] or (digest is not None and any(r.get("patch") == digest for r in p["merge"]))


def record_pass(key, stage, part=None, pr=None, patch=None, head=None):
    def put(p):
        if stage == "design":
            p["design"][part] = {"at": now_iso()}
        else:
            p["merge"].append({"pr": pr, "patch": patch, "head": head, "at": now_iso()})
    _update_passes(key, put)


def record_waiver(key, kind, ident, reason):
    """kind: `design` (ident is a part) or `pr`."""
    _update_passes(key, lambda p: p["waivers"][kind].__setitem__(str(ident), {"reason": reason, "at": now_iso()}))


def clear_design(key, part):
    """A-5: reopen a part. -> True when a pass or a waiver was there."""
    had = []
    def drop(p):
        had.extend([p["design"].pop(part, None), p["waivers"]["design"].pop(part, None)])
    _update_passes(key, drop)
    return any(had)


def ledger(key, **fields):
    """Counts and hashes only, never question, rubric, answer or reason text (A-7)."""
    path = _file(key, "ledger.jsonl")
    with locked(path), open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": now_iso(), **fields}, ensure_ascii=False, sort_keys=True) + "\n")


def _open_file(key, sid):
    return _file(key, f"open/{state.safe_id(sid)}.json")


def load_open(key, sid):
    return read_json(_open_file(key, sid))


def save_open(key, sid, rec):
    path = _open_file(key, sid)
    with locked(path):
        write_json(path, rec)


def close_open(key, sid):
    _open_file(key, sid).unlink(missing_ok=True)


# ---- who is asking -------------------------------------------------------

def _ps(pid):
    """-> (parent pid, command line) of a process; ("", "") when ps fails."""
    try:
        out = subprocess.run(["ps", "-o", "ppid=,command=", "-p", str(pid)], capture_output=True, text=True,
                             timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return "", ""
    ppid, _, cmd = out.strip().partition(" ")
    return ppid, cmd.strip()


def headless():
    """A `claude -p` run (a dots task or a child session): MAENG_TASK_ID is set, or the claude process above this
    one has `-p` or `--print` in its argv. CLAUDE_CODE_ENTRYPOINT cannot tell (a child inherits it), A-3.
    shortcut: only shells are skipped on the way up, so a wrapper such as `node claude -p` counts as the argv;
    upgrade if headless runs are launched through one."""
    if os.environ.get("MAENG_TASK_ID"):
        return True
    pid = str(os.getppid())
    for _ in range(4):
        ppid, cmd = _ps(pid)
        argv = cmd.split()
        if argv and os.path.basename(argv[0]) in SHELLS and ppid.isdigit():  # the Bash tool's shell: its parent is claude
            pid = ppid
            continue
        return bool({"-p", "--print"} & set(argv))
    return False


# ---- capture -------------------------------------------------------------

def capture(key, sid, prompt):
    """The user's message as what the open record of this session awaits (A-4). -> a note for the agent, or None
    when nothing is awaited or the message is not an answer."""
    path = _open_file(key, sid)
    if not path.exists():  # no lock file, no directory: nothing is touched
        return None
    text = prompt.strip()
    with locked(path):
        rec = read_json(path)
        if not rec:
            return None
        wait = rec.get("awaiting")
        if text == "중단":
            path.unlink(missing_ok=True)
            return "maeng: the user closed the open interview (중단); no penalty. Do not restart it unless they ask."
        if wait == "retry" and text.startswith("이의") and text[2:].strip():
            rec["appeal"] = text[2:].strip()
            note = "maeng: the user's appeal was recorded. Run `maeng-interview appeal`."
        elif wait in ("answer", "choice") and not receipts.APPROVE.match(prompt):
            rec["answer"] = prompt if rec.get("answer") is None else rec["answer"] + "\n\n" + prompt
            note = ("maeng: the user's message was recorded as their answer. Run `maeng-interview next`." if wait == "answer"
                    else "maeng: the user's choice was recorded. Run `maeng-interview reveal <digest>`.")
        else:
            return None
        write_json(path, rec)
    return note


def _waiver(prompt, m):
    """-> (kind, ident, reason) of a `면제` message, else None. A part waiver needs a declared part."""
    hit = WAIVE_PR.fullmatch(prompt)
    if hit:
        return "pr", hit.group(1), hit.group(2).strip()
    hit = WAIVE_PART.fullmatch(prompt)
    if hit and hit.group(1) in ((m or {}).get("parts") or {}):
        return "design", hit.group(1), hit.group(2).strip()
    return None


def _waive(key, sid, rec, waiver):
    kind, ident, reason = waiver
    record_waiver(key, kind, ident, reason)
    ledger(key, stage="design" if kind == "design" else "merge", **{"part" if kind == "design" else "pr": ident},
           attempts=(rec or {}).get("attempts", 0), first_try=False, appeals=(rec or {}).get("appeals", 0),
           appeal_upheld=(rec or {}).get("appeal_upheld", 0), waived=True)
    if rec and str(rec.get("part" if kind == "design" else "pr")) == ident:
        close_open(key, sid)  # the waived interview or quiz is over
    return f"maeng: the user waived {'part ' if kind == 'design' else 'PR #'}{ident}; the gate counts it as passed."


def _naming_note(key, sid, prompt, m):
    """AC-2: the message names another part while this session's current part has no design pass."""
    cur = (m.get("current") or {}).get(sid)
    if not cur or passed(key, cur, "design"):
        return None
    for name, p in (m.get("parts") or {}).items():
        if name not in (cur, OVERALL) and any(re.search(rf"(?<!\w){re.escape(w)}(?!\w)", prompt, re.I)
                                              for w in [name, *(p.get("aliases") or [])]):
            return (f"maeng: the message names part `{name}`, but the current part `{cur}` has no design pass. "
                    f"`maeng-interview switch {name}` refuses until `{cur}` passes (or the user waives it with `면제 {cur} <reason>`).")
    return None


def on_prompt(payload):
    """UserPromptSubmit: the user's message as an answer, an appeal, a stop or a waiver. -> a note for the agent, or
    None. Touches nothing when this session has no open record, the repository has no map and the message is not a
    waiver (the eta side-effect test)."""
    prompt, sid = payload.get("prompt"), payload.get("session_id", "")
    if not isinstance(prompt, str) or prompt.lstrip().startswith(WRAPPERS):  # a wrapped message is never the user's
        return None
    key = repo_key(payload.get("cwd") or os.getcwd())
    if not key:
        return None
    rec, m = load_open(key, sid), load_map(key)
    waiver = _waiver(prompt, m)
    if not (rec or m or waiver):
        return None
    if waiver:
        if headless():  # A-11: a waiver the user typed; a `claude -p` child could write one for itself
            return "maeng: a waiver counts only when the user types it in an interactive session; not recorded."
        return _waive(key, sid, rec, waiver)
    return capture(key, sid, prompt) or (_naming_note(key, sid, prompt, m) if m else None)


# ---- seal ----------------------------------------------------------------

def seal(key, sid, data):
    """Store the recommendation (bytes) and wait for the user's choice (D-8). -> the first 12 characters of its sha256."""
    digest = sha256(data)
    cur = load_open(key, sid)
    if cur and cur.get("kind") != "seal":
        raise Refused("an interview or quiz is open in this session; finish it or have the user send 중단 first")
    path = _file(key, f"seals/{digest}.txt")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)  # not atomic: reveal checks the digest of what it reads
    save_open(key, sid, {"kind": "seal", "awaiting": "choice", "answer": None, "digest": digest, "opened_at": now_iso()})
    return digest[:12]


def reveal(key, sid, digest):
    """The sealed bytes, once the user's own message arrived after the seal (T6)."""
    rec = load_open(key, sid)
    if not rec or rec.get("kind") != "seal" or len(digest) < 12 or not rec["digest"].startswith(digest):
        raise Refused("nothing is sealed under that digest in this session")
    if rec.get("answer") is None:
        raise Refused("the user has not answered since the seal; reveal only after their own message")
    data = _file(key, f"seals/{rec['digest']}.txt").read_bytes()
    if sha256(data) != rec["digest"]:
        raise Refused("the sealed text changed on disk; do not use it")
    ledger(key, stage="seal", digest=rec["digest"][:12], revealed=True)
    close_open(key, sid)
    return data
