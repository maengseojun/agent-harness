"""Per-session JSON state with fcntl lock and atomic replace."""
import json
import os
import re
from pathlib import Path

from .common import atomic_write, home_dir, locked, read_json, sha256


def sessions_dir():
    return home_dir() / "sessions"


def safe_id(session_id):
    sid = str(session_id or "")
    return sid if re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", sid) else "h-" + sha256(sid)[:32]


def path_for(session_id):
    return sessions_dir() / (safe_id(session_id) + ".json")


def tombstone_for(session_id):
    return sessions_dir() / (safe_id(session_id) + ".quarantined")


def is_quarantined(session_id):
    """True when this session's state was quarantined: without its state the hook cannot tell a personal session
    from an eta one, so every tool call of the session is denied until it is restarted."""
    return tombstone_for(session_id).exists()


def clear_quarantine(session_id):
    try:
        tombstone_for(session_id).unlink()
    except FileNotFoundError:
        pass


def fresh(session_id, cwd=""):
    return {"session_id": session_id, "cwd": cwd, "seq": 0, "binding": None, "evidence": [],
            "skips": [], "plan_records": [], "pending": {}, "decisions": [], "baseline_tree": None,
            "last_tree": None, "last_change_seq": 0, "last_record_seq": 0, "turn": 0,
            "stub": None, "started_at": None}


class StateCorrupt(Exception):
    """An existing session state file cannot be trusted. It is never replaced by fresh state: fresh state would
    redefine the session's world (its original cwd) and could disable cross-world gating."""

    def __init__(self, path, why=""):
        self.path, self.why = Path(path), why
        super().__init__(f"session state {path} is unreadable{': ' + why if why else ''}")

    def message(self):
        return (f"maeng: session state {self.path} is unreadable; move it aside (maeng-verify state --quarantine) "
                f"and restart")


_FIELD_TYPES = {"seq": int, "turn": int, "last_change_seq": int, "last_record_seq": int, "evidence": list,
                "skips": list, "plan_records": list, "decisions": list, "pending": dict}


def _validate(data):
    """-> reason string when the decoded state does not match the schema, else None."""
    if not isinstance(data, dict):
        return "not a JSON object"
    for key, typ in _FIELD_TYPES.items():
        if key in data and (not isinstance(data[key], typ) or isinstance(data[key], bool)):
            return f"`{key}` is not a {typ.__name__}"
    for key in ("evidence", "skips", "plan_records", "decisions"):
        if any(not isinstance(x, dict) for x in data.get(key, [])):
            return f"`{key}` has a non-object entry"
    if "cwd" in data and not isinstance(data["cwd"], str):
        return "`cwd` is not a string"
    if data.get("binding") is not None and not isinstance(data.get("binding"), dict):
        return "`binding` is not an object"
    return None


def load(session_id, cwd=""):
    p = path_for(session_id)
    try:
        data = read_json(p)
    except (ValueError, OSError) as exc:
        raise StateCorrupt(p, f"{type(exc).__name__}") from exc
    if data is None:  # no file yet: fresh state
        return fresh(session_id, cwd)
    why = _validate(data)
    if why:
        raise StateCorrupt(p, why)
    return {**fresh(session_id, cwd), **data}


def quarantine(session_id):
    """Rename a corrupt state file aside -> new path, or None when the file is absent or readable."""
    import time
    p = path_for(session_id)
    with locked(p):
        try:
            load(session_id)
            return None
        except StateCorrupt:
            pass
        dest = p.with_name(f"{p.name}.corrupt-{time.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}")
        os.replace(p, dest)
        atomic_write(tombstone_for(session_id), f"quarantined {dest.name}\n")
    return dest


def update(session_id, fn, cwd=""):
    """Run fn(state) under the lock; persist the (mutated) state; return fn's result."""
    p = path_for(session_id)
    with locked(p):
        st = load(session_id, cwd)
        result = fn(st)
        atomic_write(p, json.dumps(st, indent=1, sort_keys=True) + "\n")
    return result


def bump(st):
    st["seq"] += 1
    return st["seq"]


def find_session(cwd):
    """CLI helper: env var first, then newest session whose cwd contains/equals ours."""
    env = os.environ.get("MAENG_SESSION_ID")
    if env:
        return env
    d = sessions_dir()
    if not d.is_dir():
        return None
    cwd = str(Path(cwd).resolve())
    best, best_m = None, -1
    for f in d.glob("*.json"):
        try:
            data = read_json(f)
            scwd = str(Path(data.get("cwd", "")).resolve()) if data.get("cwd") else ""
        except (ValueError, OSError, AttributeError):
            continue
        if scwd and (cwd == scwd or cwd.startswith(scwd + os.sep) or scwd.startswith(cwd + os.sep)):
            m = f.stat().st_mtime
            if m > best_m:
                best, best_m = data.get("session_id"), m
    return best
