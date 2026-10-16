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


def fresh(session_id, cwd=""):
    return {"session_id": session_id, "cwd": cwd, "seq": 0, "binding": None, "evidence": [],
            "skips": [], "plan_records": [], "pending": {}, "decisions": [], "baseline_tree": None,
            "last_tree": None, "last_change_seq": 0, "last_record_seq": 0, "turn": 0,
            "stub": None, "started_at": None}


def load(session_id, cwd=""):
    try:
        data = read_json(path_for(session_id))
    except ValueError:
        data = None
    if not isinstance(data, dict):
        return fresh(session_id, cwd)
    return {**fresh(session_id, cwd), **data}


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
