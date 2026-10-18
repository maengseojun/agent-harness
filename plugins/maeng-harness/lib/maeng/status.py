"""Signals outside readers use (MAE-242): a per-task status file plus manifest for dots, and the `maeng/review`
commit status for GitHub. To remove the feature, delete this module and its calls in handlers.py and maeng-review."""
import os
import re
import subprocess
import time
from pathlib import Path

from .common import locked, now_iso, read_json, write_json

SCHEMA = 1
SAFE = re.compile(r"[A-Za-z0-9._-]{1,64}")
TASK_LINE = re.compile(r"^\s*task[_-]id:\s*([A-Za-z0-9._-]{1,64})\s*$", re.I | re.M)
MARKERS = (("result:", "done"), ("needs input:", "needs_input"), ("failed:", "failed"))
OWNED = ("running", "needs_input")  # states in which a task belongs to its session
DUP_WINDOW = 12 * 3600


def status_dir():
    return Path(os.environ.get("MAENG_STATUS_DIR") or Path.home() / "Documents/maeng-harness/status")


def task_id_for(session_id, prompt=""):
    """MAENG_TASK_ID, else a `task_id: X` line in the prompt, else one id per session."""
    env = os.environ.get("MAENG_TASK_ID", "")
    if SAFE.fullmatch(env):
        return env
    m = TASK_LINE.search(prompt or "")
    return m.group(1) if m else "s-" + re.sub(r"[^A-Za-z0-9]", "", str(session_id))[:8]


def outcome(text):
    """(state, summary) from the last `result:` / `needs input:` / `failed:` line of an assistant message."""
    found = ("idle", None)
    for line in (text or "").splitlines():
        low = line.strip().lower()
        for prefix, state in MARKERS:
            if low.startswith(prefix):
                found = (state, line.strip()[len(prefix):].strip())
    return found


def verify_state(evidence, tree, unverified):
    """pass: a check passed on this tree and the Stop hook found no UNVERIFIED obligation. With that obligation: fail
    when a run on the tree failed, else not_run (a filtered pass does not count). none: no code change to verify."""
    runs = [e for e in evidence if tree and e.get("tree_finish") == tree]
    if unverified:
        return "fail" if any(not e.get("ok") for e in runs) else "not_run"
    return "pass" if any(e.get("ok") for e in runs) else "none"


def read(task_id):
    try:
        return read_json(status_dir() / f"{task_id}.json", {}) or {}
    except ValueError:  # a torn or hand-edited file is ours to rewrite
        return {}


def owner_conflict(task_id, session_id):
    """The other session that owns this task right now, or None."""
    cur = read(task_id)
    other = cur.get("session_id")
    if not other or other == session_id or cur.get("state") not in OWNED:
        return None
    return other if time.time() - cur.get("updated_epoch", 0) < DUP_WINDOW else None


def write(task_id, session_id, **fields):
    """Merge fields into the task's status file and its manifest row."""
    d = status_dir()
    with locked(d / "manifest.json"):
        cur = read(task_id)
        if cur.get("session_id") != session_id:  # a new owner starts from a clean record
            cur = {}
        prev = cur.get("state")
        cur.update(fields, schema_version=SCHEMA, task_id=task_id, session_id=session_id,
                   updated_at=now_iso(), updated_epoch=int(time.time()))
        if cur.get("state") != prev:
            cur["last_progress_at"] = cur["updated_at"]
        cur["needs_user_input"] = cur.get("state") == "needs_input"
        write_json(d / f"{task_id}.json", cur)
        try:
            manifest = read_json(d / "manifest.json", {}) or {}
        except ValueError:
            manifest = {}
        manifest[task_id] = {k: cur.get(k) for k in ("session_id", "cwd", "state", "updated_at")}
        write_json(d / "manifest.json", manifest)
    return cur


def post_review_status(repo, head_sha, verdict, cwd):
    """Commit status `maeng/review` on a GitHub head. Returns an error string, or None when posted or not GitHub."""
    m = re.fullmatch(r"github\.com/([^/]+/[^/]+)", repo or "")
    if not (m and re.fullmatch(r"[0-9a-f]{40}", head_sha or "")):
        return None
    state = "success" if verdict == "pass" else "failure"
    cmd = [os.environ.get("MAENG_GH", "gh"), "api", "-X", "POST", f"repos/{m.group(1)}/statuses/{head_sha}",
           "-f", f"state={state}", "-f", "context=maeng/review", "-f", f"description=maeng-review {verdict}"]
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError) as exc:
        return str(exc)
    return None if proc.returncode == 0 else (proc.stderr.strip() or f"gh exited {proc.returncode}")
