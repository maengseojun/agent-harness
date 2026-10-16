"""Review verdicts, single-use receipts (pending/consume/reject/reconcile), Notion journal + registry."""
import json

from . import schema
from .common import canonical, git, home_dir, locked, now_iso, read_json, sha256, write_json

UNCONSUMED, PENDING, CONSUMED = "unconsumed", "pending", "consumed"


class ReceiptError(Exception):
    pass


def receipts_dir():
    return home_dir() / "receipts"


def subject_key(subject):
    kind = subject["kind"]
    if kind == "notion":
        return "notion-{}-{}".format(subject["digest"][:16], sha256(f"{subject['destination']}|{subject['op']}")[:8])
    core = {k: subject.get(k) for k in ("kind", "repo", "pr", "base", "head", "criteria_rev", "digest",
                                         "destination", "op")}
    return "code-" + sha256(canonical(core))[:24]


def _path(key):
    return receipts_dir() / (key + ".json")


def store_verdict(verdict):
    """Validate and store a verdict; only `pass` verdicts become usable receipts."""
    errors = schema.validate(verdict, schema.load_schema())
    if errors:
        raise ReceiptError("invalid verdict: " + "; ".join(errors))
    key = subject_key(verdict["subject"])
    p = _path(key)
    with locked(p):
        existing = read_json(p)
        if existing and existing["status"] in (PENDING, CONSUMED) and existing["verdict"] != verdict:
            raise ReceiptError(f"receipt {key} is {existing['status']}; cannot replace")
        rec = existing or {"key": key, "status": UNCONSUMED, "history": []}
        rec["verdict"] = verdict
        rec["history"].append({"at": now_iso(), "event": "stored:" + verdict["verdict"]})
        write_json(p, rec)
    return key


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


def find_code(base, head, ref, criteria_rev):
    """Receipt for exactly this base/head/ref. -> (record | None, problem)."""
    unreadable = False
    stale = None
    for _, rec in _scan("code-"):
        if rec is None:
            unreadable = True
            continue
        s = rec["verdict"]["subject"]
        if (s.get("base"), s.get("head")) != (base, head) or s.get("destination") not in (ref, ref.replace("refs/heads/", "")):
            continue
        if rec["verdict"]["verdict"] != "pass":
            return None, "review verdict is not pass"
        if (s.get("criteria_rev") or None) != (criteria_rev or None):
            stale = "review is stale: criteria updatedAt changed since review"
            continue
        return rec, ""
    if stale:
        return None, stale
    return None, "receipt unreadable" if unreadable else "no pass receipt for this base/head"


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
        if (s["destination"], s["op"]) == (destination, op):
            if rec["verdict"]["verdict"] != "pass":
                return None, "review verdict is not pass"
            if rec["status"] != UNCONSUMED:
                return None, f"receipt is {rec['status']}"
            return rec, ""
    return None, "receipt destination/op mismatch"


def begin(key, intent):
    def f(rec):
        if rec["status"] != UNCONSUMED:
            raise ReceiptError(f"receipt is {rec['status']}")
        rec["status"], rec["intent"] = PENDING, intent
        rec["history"].append({"at": now_iso(), "event": "pending"})
    return _mutate(key, f)


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
    rc, out, err = git(cwd, "ls-remote", it["remote"], it["ref"])
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
        git(cwd, "fetch", "--quiet", it["remote"], it["ref"])
        if git(cwd, "cat-file", "-e", remote_sha + "^{commit}")[0] == 0 and \
                git(cwd, "merge-base", "--is-ancestor", it["head_sha"], remote_sha)[0] == 0:
            consume(key, {"merge_sha": remote_sha, "via": "reconcile:head-ancestor-of-remote"})
            return "consumed", remote_sha
    return "pending", "cannot establish whether head was integrated"


# ---- Notion journal and registry ----------------------------------------

def _notion(name):
    return home_dir() / "notion" / name


def read_journal():
    return read_json(_notion("journal.json"), []) or []


def journal_update(fn):
    p = _notion("journal.json")
    with locked(p):
        entries = read_json(p, []) or []
        result = fn(entries)
        write_json(p, entries)
        return result


def unresolved_entries():
    return [e for e in read_journal() if e["status"] in ("pending", "sent")]


def journal_pending(entry):
    entry = {**entry, "status": "pending", "page_ids": [], "at": now_iso()}
    journal_update(lambda es: es.append(entry))
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
            if e["status"] == "sent" and (page_id in e["page_ids"] or entry_id == e["id"]):
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
    return set((read_json(_notion("registry.json"), {}) or {}).get("page_ids", []))


def registry_add(ids):
    p = _notion("registry.json")
    with locked(p):
        cur = read_json(p, {}) or {}
        cur["page_ids"] = sorted(set(cur.get("page_ids", [])) | set(ids))
        write_json(p, cur)
