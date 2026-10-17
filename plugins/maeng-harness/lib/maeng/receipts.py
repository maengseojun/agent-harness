"""Review verdicts, single-use receipts (pending/consume/reject/reconcile), Notion journal + registry."""
import json
import os
import re

from . import schema
from .common import canonical, git, home_dir, locked, now_iso, read_json, sha256, write_json

UNCONSUMED, PENDING, CONSUMED = "unconsumed", "pending", "consumed"


def nid(value):
    """Canonical Notion id: hyphens stripped, lowercase."""
    return str(value or "").replace("-", "").strip().lower()


class ReceiptError(Exception):
    pass


def receipts_dir():
    return home_dir() / "receipts"


def fixtures_allowed():
    """Test-only escape hatch: fixture receipts (and the `maeng-review store` command) need MAENG_TEST_FIXTURES=1."""
    return os.environ.get("MAENG_TEST_FIXTURES") == "1"


def usable_provenance(rec):
    """Only receipts written by `maeng-review run` authorize anything; fixture/unknown ones need the test switch."""
    prov = ((rec.get("verdict") or {}).get("reviewer") or {}).get("provenance")
    return prov == "review-run" or fixtures_allowed()


def subject_key(subject):
    kind = subject["kind"]
    if kind == "notion":
        return "notion-{}-{}".format(subject["digest"][:16], sha256(f"{subject['destination']}|{subject['op']}")[:8])
    core = {k: subject.get(k) for k in ("kind", "repo", "pr", "base", "head", "criteria_rev", "digest",
                                         "destination", "op",
                                         "files_reviewed", "files_excluded")}
    if subject.get("files_delegated"):
        core["files_delegated"] = subject["files_delegated"]
    for k in ("issue", "parent"):
        if subject.get(k):
            core[k] = subject[k]
    return "code-" + sha256(canonical(core))[:24]


def _path(key):
    return receipts_dir() / (key + ".json")


def store_verdict(verdict):
    """Validate and store a verdict; only `pass` verdicts become usable receipts."""
    errors = schema.validate(verdict, schema.load_schema())
    if errors:
        raise ReceiptError("invalid verdict: " + "; ".join(errors))
    if verdict["subject"].get("kind") == "notion" and verdict["subject"].get("destination"):
        verdict["subject"]["destination"] = nid(verdict["subject"]["destination"])
    key = subject_key(verdict["subject"])
    p = _path(key)
    with locked(p):
        existing = read_json(p)
        if existing and existing["status"] in (PENDING, CONSUMED) and existing["verdict"] != verdict:
            raise ReceiptError(f"receipt {key} is {existing['status']}; cannot replace")
        rec = existing or {"key": key, "status": UNCONSUMED, "history": []}
        rec["verdict"] = verdict
        if verdict["verdict"] == "pass":
            rec.pop("revoked", None)  # a newer pass for this exact subject supersedes an earlier revocation
        rec["history"].append({"at": now_iso(), "event": "stored:" + verdict["verdict"]})
        write_json(p, rec)
    if verdict["verdict"] != "pass":
        revoke_passes(verdict["subject"], verdict["verdict"])
    return key


def revoke_passes(subject, by):
    """A `fail`/`blocked` verdict revokes every earlier UNCONSUMED pass receipt for the same repo/base/head.
    Consumed/pending receipts are untouched (their merge already happened or is in flight). -> revoked keys."""
    if subject.get("kind") == "notion":
        return _revoke_notion(subject, by)
    if subject.get("kind") not in ("code", "parent"):
        return []
    revoked = []
    for _, rec in list(_scan("code-")):
        if rec is None or rec["verdict"]["verdict"] != "pass" or rec["status"] != UNCONSUMED or rec.get("revoked"):
            continue
        s = rec["verdict"]["subject"]
        if (s.get("repo"), s.get("base"), s.get("head")) != (subject.get("repo"), subject.get("base"),
                                                              subject.get("head")):
            continue

        def mark(r, by=by):
            if r["verdict"]["verdict"] == "pass" and r["status"] == UNCONSUMED and not r.get("revoked"):
                r["revoked"] = {"at": now_iso(), "by": by}
                r["history"].append({"at": now_iso(), "event": "revoked:" + by})
        _mutate(rec["key"], mark)
        revoked.append(rec["key"])
    return revoked


def _revoke_notion(subject, by):
    """A fail/blocked outcome for a Notion payload revokes every unconsumed pass for the same digest + destination
    + op, so an earlier pass of the identical payload can no longer authorize the write."""
    digest = subject.get("digest")
    revoked = []
    if not digest:
        return revoked
    for _, rec in list(_scan("notion-" + digest[:16])):
        if rec is None or rec["verdict"]["verdict"] != "pass" or rec["status"] != UNCONSUMED or rec.get("revoked"):
            continue
        s = rec["verdict"]["subject"]
        if (s.get("digest"), nid(s.get("destination")), s.get("op")) != (digest, nid(subject.get("destination")),
                                                                          subject.get("op")):
            continue

        def mark(r, by=by):
            if r["verdict"]["verdict"] == "pass" and r["status"] == UNCONSUMED and not r.get("revoked"):
                r["revoked"] = {"at": now_iso(), "by": by}
                r["history"].append({"at": now_iso(), "event": "revoked:" + by})
        _mutate(rec["key"], mark)
        revoked.append(rec["key"])
    return revoked


def load(key):
    return read_json(_path(key))


def _mutate(key, fn):
    p = _path(key)
    with locked(p):
        rec = read_json(p)
        if rec is None:
            raise ReceiptError("no such receipt " + key)
        fn(rec)
        write_json(p, rec)
        return rec


def _scan(prefix):
    """Yield (path, record|None) where record is None when unreadable."""
    d = receipts_dir()
    for p in sorted(d.glob(prefix + "*.json")) if d.is_dir() else []:
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
            yield p, rec if isinstance(rec, dict) and "verdict" in rec else None
        except (ValueError, OSError):
            yield p, None


def changed_files(cwd, base, head):
    rc, out, _ = git(cwd, "diff", "--name-only", "--no-renames", f"{base}...{head}")
    return sorted(set(out.splitlines())) if rc == 0 else None


def diff_digest(cwd, base, head, files):
    rc, out, _ = git(cwd, "diff", "--no-renames", f"{base}...{head}", "--", *files)
    return sha256(out.strip()) if rc == 0 else None


def child_binding_rev(issue):
    """The current criteria rev `maeng-verify bind` last recorded for `issue` (None when unknown)."""
    try:
        return ((read_json(home_dir() / "bindings.json", {}) or {}).get(issue) or {}).get("plan_updated_at")
    except ValueError:
        return None


def find_code(cwd, repo, base, head, ref, criteria_rev, files=None, issue=None):
    """Pass receipts that together cover every file changed between base and head for this exact
    repo/base/head/criteria. A file is covered when it is in `files_reviewed` of a pass receipt, or in
    `files_excluded` of a pass receipt of kind `parent` (the parent reviewer accepted the exclusion).
    A receipt reviewed under a child issue (subject.parent == `issue`) also counts when its criteria_rev still
    equals that child's own current binding rev.
    -> (list of records | None, problem). Every returned record must be consumed together."""
    unreadable = stale = child_stale = failed = revoked = fixture = False
    seen_status = None
    cands = []
    for _, rec in _scan("code-"):
        if rec is None:
            unreadable = True
            continue
        s = rec["verdict"]["subject"]
        if s.get("kind") not in ("code", "parent"):
            continue
        if (s.get("base"), s.get("head")) != (base, head) or s.get("destination") not in (ref, ref.replace("refs/heads/", "")):
            continue
        if not repo or s.get("repo") != repo:
            continue
        if rec["verdict"]["verdict"] != "pass":
            failed = True
            continue
        if not usable_provenance(rec):
            fixture = True
            continue
        if rec.get("revoked"):
            revoked = True
            continue
        if (s.get("criteria_rev") or None) != (criteria_rev or None):
            if issue and s.get("parent") == issue and s.get("issue"):
                if (s.get("criteria_rev") or None) != (child_binding_rev(s["issue"]) or None):
                    child_stale = True
                    continue
            else:
                stale = True
                continue
        if rec["status"] != UNCONSUMED:
            seen_status = rec["status"]
            continue
        cands.append(rec)
    if failed:
        return None, "review verdict is not pass"
    if not cands:
        if revoked:
            return None, "review was revoked by a later fail/blocked verdict for this head"
        if child_stale:
            return None, "stale child receipt: the child issue's criteria changed since the review"
        if stale:
            return None, "review is stale: criteria updatedAt changed since review"
        if fixture:
            return None, "the receipt is a fixture, not a `maeng-review run` result"
        if seen_status:
            return None, f"receipt is {seen_status}; run `maeng-review reconcile`"
        return None, "receipt unreadable" if unreadable else "no pass receipt for this repo/base/head"
    if unreadable:
        return None, "receipt unreadable"
    if files is None:
        files = changed_files(cwd, base, head)
    if files is None:
        return None, "cannot list the files changed between base and head"
    uncovered, used = set(files), []
    for rec in cands:
        s = rec["verdict"]["subject"]
        reviewed = set(s.get("files_reviewed") or [])
        got = (uncovered & reviewed)
        if s.get("kind") == "parent":  # exempt exclusions only; delegated files need their own pass receipt
            got |= uncovered & (set(s.get("files_excluded") or []) - set(s.get("files_delegated") or []))
        if reviewed and diff_digest(cwd, base, head, sorted(reviewed)) != s.get("digest"):
            continue  # the recorded diff digest does not match what is being shipped
        if got or (not files and not used):
            used.append(rec)
            uncovered -= got
    if uncovered or not used:
        shown = ", ".join(sorted(uncovered)[:8])
        return None, ("review coverage incomplete: no pass receipt covers " + (shown or "this change") +
                      " (each changed file must be in some receipt's files_reviewed, or in a parent receipt's files_excluded; "
                      "files_delegated are NOT covered by the parent and need their own pass receipt)")
    return used, ""


def find_notion(digest, destination, op):
    matches, unreadable = [], False
    for p, rec in _scan("notion-" + digest[:16]):
        if rec is None:
            unreadable = True
        elif rec["verdict"]["subject"].get("digest") == digest:
            matches.append(rec)
    if unreadable:
        return None, "receipt unreadable"
    if not matches:
        return None, "no Sol pass receipt for this payload digest (digest mismatch or never reviewed)"
    for rec in matches:
        s = rec["verdict"]["subject"]
        if (nid(s["destination"]), s["op"]) == (nid(destination), op):
            if rec["verdict"]["verdict"] != "pass":
                return None, "review verdict is not pass"
            if not usable_provenance(rec):
                return None, "the receipt is a fixture, not a `maeng-review run` result"
            if rec.get("revoked"):
                return None, "review was revoked by a later fail/blocked verdict for this payload"
            if rec["status"] != UNCONSUMED:
                return None, f"receipt is {rec['status']}"
            return rec, ""
    return None, "receipt destination/op mismatch"


def begin(key, intent):
    def f(rec):
        # re-checked under the receipt lock: a concurrent re-review may have revoked the receipt after lookup
        if rec.get("revoked"):
            raise ReceiptError("receipt was revoked")
        if (rec.get("verdict") or {}).get("verdict") != "pass":
            raise ReceiptError("receipt verdict is not pass")
        if rec["status"] != UNCONSUMED:
            raise ReceiptError(f"receipt is {rec['status']}")
        rec["status"], rec["intent"] = PENDING, intent
        rec["history"].append({"at": now_iso(), "event": "pending"})
    return _mutate(key, f)


def begin_many(items):
    """Reserve several receipts atomically: all become pending, or none do. items = [(key, intent)]."""
    done = []
    try:
        for key, intent in sorted(items, key=lambda x: x[0]):
            begin(key, intent)
            done.append(key)
    except Exception:
        for key in done:
            try:
                reject(key, "reservation-rolled-back")
            except Exception:
                pass
        raise


def consume(key, result):
    def f(rec):
        rec["status"], rec["result"] = CONSUMED, result
        rec["history"].append({"at": now_iso(), "event": "consumed"})
    return _mutate(key, f)


def reject(key, note):
    """Confirmed rejection (or proven no mutation): eligible for retry."""
    def f(rec):
        rec["status"] = UNCONSUMED
        rec["history"].append({"at": now_iso(), "event": "rejected:" + note})
    return _mutate(key, f)


def pending_code():
    return [rec for _, rec in _scan("code-") if rec and rec["status"] == PENDING]


def reconcile_code(key, cwd):
    """Decide a pending merge receipt from the remote's actual state. -> (outcome, detail)."""
    rec = load(key)
    if not rec or rec["status"] != PENDING:
        return "not-pending", ""
    it = rec["intent"]
    from . import guard  # local import: guard is a leaf module, keep receipts importable on its own
    rc, url, _ = git(cwd, "remote", "get-url", "--push", it["remote"])
    here = guard.normalize_repo(url.strip()) if rc == 0 and url.strip() else None
    if not it.get("repo") or here != it["repo"]:
        return "pending", (f"run reconcile in a checkout of {it.get('repo') or 'the receipt repository'} "
                           f"(remote `{it['remote']}` here is {here or 'unresolvable'}); receipt left pending")
    from . import remotecfg  # same leaf-module reasoning as guard
    eff, err = remotecfg.plain_remote(cwd, it["remote"], for_push=False)
    if err or guard.normalize_repo(eff) != it["repo"]:
        return "pending", (f"remote `{it['remote']}` is not a plain remote ({err or 'url differs'}); "
                           f"receipt left pending")
    rc, out, err = git(cwd, "ls-remote", eff, it["ref"])
    if rc != 0:
        return "pending", "cannot reach remote: " + err.strip()
    remote_sha = out.split()[0] if out.split() else ""
    if remote_sha == it["head_sha"]:
        consume(key, {"merge_sha": remote_sha, "via": "reconcile:at-head"})
        return "consumed", remote_sha
    if remote_sha == it["base_sha"]:
        reject(key, "reconcile:remote-still-at-base")
        return "retry", "remote unchanged; no mutation happened"
    if remote_sha:
        git(cwd, "fetch", "--quiet", eff, it["ref"])
        if git(cwd, "cat-file", "-e", remote_sha + "^{commit}")[0] == 0 and \
                git(cwd, "merge-base", "--is-ancestor", it["head_sha"], remote_sha)[0] == 0:
            consume(key, {"merge_sha": remote_sha, "via": "reconcile:head-ancestor-of-remote"})
            return "consumed", remote_sha
    return "pending", "cannot establish whether head was integrated"


# ---- Notion journal and registry ----------------------------------------

def _notion(name):
    return home_dir() / "notion" / name


class RegistryError(Exception):
    """The Notion registry or journal is unreadable or malformed. Callers must treat every G2-scoped update as gated
    (and deny) rather than guess which pages are protected."""


def _hex32(value):
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{32}", nid(value)))


def _load_notion(name, default):
    try:
        return read_json(_notion(name), default)
    except (ValueError, OSError) as exc:
        raise RegistryError(f"{name} is unreadable ({type(exc).__name__})") from exc


def _checked_journal(data):
    if not isinstance(data, list):
        raise RegistryError("journal.json is not a list")
    for e in data:
        if not (isinstance(e, dict) and isinstance(e.get("id"), str) and isinstance(e.get("status"), str)
                and isinstance(e.get("page_ids"), list) and all(_hex32(i) for i in e["page_ids"])):
            raise RegistryError("journal.json has an invalid entry")
    return data


def read_journal():
    return _checked_journal(_load_notion("journal.json", []))


def _checked_registry(data):
    if not isinstance(data, dict):
        raise RegistryError("registry.json is not an object")
    if not data:
        return []
    ids = data.get("page_ids")
    if not isinstance(ids, list) or not all(_hex32(i) for i in ids):
        raise RegistryError("registry.json page_ids is not a list of 32-hex Notion ids")
    return ids


def journal_update(fn):
    p = _notion("journal.json")
    with locked(p):
        entries = _checked_journal(_load_notion("journal.json", []))
        result = fn(entries)
        write_json(p, entries)
        return result


def unresolved_entries():
    return [e for e in read_journal() if e["status"] in ("pending", "sent")]


def journal_pending(entry):
    entry = {**entry, "status": "pending", "page_ids": [], "at": now_iso()}

    def f(es):
        if any(e["status"] in ("pending", "sent") for e in es):
            raise ReceiptError("an earlier Notion write is unresolved")
        es.append(entry)
    journal_update(f)
    return entry


def _find_entry(es, tool_use_id):
    for e in reversed(es):
        if e.get("tool_use_id") == tool_use_id and e["status"] in ("pending", "sent"):
            return e
    return None


def journal_sent(tool_use_id, page_ids):
    def f(es):
        e = _find_entry(es, tool_use_id)
        if e:
            e["status"], e["page_ids"] = "sent", list(page_ids)
        return e
    return journal_update(f)


def journal_rejected(tool_use_id):
    def f(es):
        e = _find_entry(es, tool_use_id)
        if e:
            e["status"] = "rejected"
        return e
    e = journal_update(f)
    if e:
        reject(e["key"], "notion-error-response")
    return e


def journal_readback(page_id, entry_id=None):
    """A successful readback of `page_id` resolves the matching entry, consumes the receipt, fills the registry."""
    def f(es):
        for e in es:
            sent = e["status"] == "sent" and (page_id in e["page_ids"] or entry_id == e["id"])
            confirmed_pending = e["status"] == "pending" and entry_id == e["id"]  # agent read the page back
            if sent or confirmed_pending:
                e["status"] = "read_back"
                if page_id not in e["page_ids"]:
                    e["page_ids"].append(page_id)
                return e
        return None
    e = journal_update(f)
    if e:
        consume(e["key"], {"page_ids": e["page_ids"], "via": "readback"})
        registry_add(e["page_ids"])
    return e


def journal_absent(entry_id):
    """Reconcile: the page does not exist, so nothing was published; receipt may retry."""
    def f(es):
        for e in es:
            if e["id"] == entry_id and e["status"] in ("pending", "sent"):
                e["status"] = "absent"
                return e
    e = journal_update(f)
    if e:
        reject(e["key"], "reconcile:absent")
    return e


def registry_ids():
    """-> set of registered page ids; raises RegistryError when the registry is malformed."""
    return {nid(i) for i in _checked_registry(_load_notion("registry.json", {}))}


def registry_add(ids, repair=False):
    """Add page ids. With repair=True (explicit `maeng-review registry seed`) a malformed registry is moved aside
    and replaced by one holding `ids`."""
    p = _notion("registry.json")
    with locked(p):
        try:
            cur = _load_notion("registry.json", {})
            known = _checked_registry(cur)
        except RegistryError:
            if not repair:
                raise
            if p.exists():
                import os
                import time
                os.replace(p, p.with_name(f"{p.name}.invalid-{time.strftime('%Y%m%dT%H%M%S')}"))
            cur, known = {}, []
        cur["page_ids"] = sorted({nid(i) for i in known} | {nid(i) for i in ids})
        write_json(p, cur)
