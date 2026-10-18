"""Helpers shared by the bin/ CLIs."""
import sys

from . import guard, state


def die(msg, code=1):
    print("error: " + msg, file=sys.stderr)
    sys.exit(code)


def require_personal(cwd):
    world = guard.classify(guard.session_root(cwd))  # same root the hooks classify
    if world != guard.PERSONAL:
        die(f"this checkout classifies as {world}; maeng-harness tools run only in the personal world", 2)


def session_for(cwd, explicit=None):
    sid = explicit or state.find_session(cwd)
    if not sid:
        die("no session found: pass --session or set MAENG_SESSION_ID", 2)
    return sid


def checked_load(sid, cwd):
    try:
        return state.load(sid, cwd)
    except state.StateCorrupt as exc:
        die(exc.message())


def load_state(cwd, explicit=None):
    sid = session_for(cwd, explicit)
    return sid, checked_load(sid, cwd)
