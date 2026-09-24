"""Codex entry gate. Local state only; no network, credentials or prompt storage.

UserPromptSubmit supplies the route decision contract. PreToolUse requires one
explicit entry selection before local tools. The model decides ownership; this
script enforces delivery of the selected entry, not semantic correctness or ACLs.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile
import time


ROUTES = ("personal", "endix", "mixed")
BASE = Path.home() / ".local/share/agent-harness/entry-state"
SKILL = Path.home() / ".codex/skills/harness-run/SKILL.md"
ENDIX = """Endix project entry (read-only bootstrap, not a Lighthouse stamp):
Read the current target project's AGENTS.md and actual entry configuration, then
the relevant live entry/flow sources. Locators: https://linear.app/endix-labs/issue/END-462
(overview), END-464 (Docs decisions), END-471 (flows). Exports and screenshots are
reference snapshots, not authority or proof that Lighthouse/managers are deployed.
Reuse the existing umbrella/issue/flow. Follow the actual project's entry once;
do not start another personal task tree or recurse back into the personal harness.
If no deployed entry is available, inspect the current interim F0 procedure and
prepare a bounded handoff; do not fabricate a stamp or act as a team manager.
Endix Linear, Notion, GitHub, hooks and team rules remain READ-ONLY for this
personal harness. A concrete authorized team operation must go through the team
entry and its applicable owner gates; this route grants no write permission.
Do not send Slack messages or impersonate a human approval.
Endix team workflow setup is in progress by Hyunsu. Its end-to-end execution test
is deferred until the user says it is ready; do not build or repair that workflow
as part of personal harness maintenance.
"""


def key_for(event):
    ids = [event.get("session_id"), event.get("turn_id")]
    if not all(isinstance(value, str) and value for value in ids):
        return None
    return hashlib.sha256(json.dumps(ids).encode()).hexdigest()


def state_path(key):
    if not re.fullmatch(r"[a-f0-9]{64}", key):
        raise ValueError("Invalid entry key")
    return BASE / (key + ".json")


def save(key, state):
    BASE.mkdir(mode=0o700, parents=True, exist_ok=True)
    if BASE.is_symlink():
        raise ValueError("Entry state directory must not be a symlink")
    fd, temporary = tempfile.mkstemp(dir=BASE, prefix=".entry-")
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(state, stream, sort_keys=True)
        os.replace(temporary, state_path(key))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read(key):
    path = state_path(key)
    if path.is_symlink():
        raise ValueError("Entry receipt must not be a symlink")
    if not path.exists():
        return None
    state = json.loads(path.read_text())
    if not isinstance(state, dict) or not isinstance(state.get("created_at"), (int, float)):
        raise ValueError("Invalid entry receipt")
    expected = {"created_at", "route"}
    if state.get("route") in ROUTES:
        expected |= {"entered_at", "entry_sha256"}
        if (not isinstance(state.get("entered_at"), (int, float)) or
                not isinstance(state.get("entry_sha256"), str) or
                not re.fullmatch(r"[a-f0-9]{64}", state["entry_sha256"])):
            raise ValueError("Invalid entered receipt")
    elif state.get("route") is not None:
        raise ValueError("Invalid entry route in receipt")
    if set(state) != expected:
        raise ValueError("Invalid entry receipt fields")
    return state


def command(key, route):
    return shlex.join([sys.executable, str(Path(__file__).resolve()), "enter", key, route])


def instruction(key):
    return (
        "PERSONAL HARNESS ENTRY GATE: Before local tools, determine the requested "
        "output owner from this prompt AND settled conversation context. Choose "
        "personal for personal/non-Endix work; endix for actual Endix team work; "
        "mixed for separate personal and team outputs. A passing Endix mention, "
        "current directory, or a private Endix analysis does not make it team work. "
        "Do not classify by keywords alone. If material ownership is unclear, "
        "ask a concise clarification. Ordinary answers needing no tools can be "
        "answered directly without a ledger. For tool work, first run exactly one "
        "of the following commands by exec_command (no shell additions):\n" +
        "\n".join(command(key, route) for route in ROUTES) +
        "\nRead the returned entry and follow its relevant workflow/specialist "
        "skills. The entry receipt is not authorization, verified source access, "
        "or evidence of completed work. Do not disable this hook to skip entry."
    )


def entry(route):
    if route not in ROUTES:
        raise ValueError("Unknown entry route")
    if route == "endix":
        return ENDIX
    personal = SKILL.read_text()
    if route == "personal":
        return "Selected PERSONAL entry.\n" + personal
    return ("Selected MIXED entry. Separate outputs and permissions by owner. "
            "Keep only links to team records in a personal overview; do not copy "
            "or synchronize team state.\n" + ENDIX + "\nPersonal portion:\n" + personal)


def output(event, **fields):
    return {"hookSpecificOutput": {"hookEventName": event, **fields}}


def handle(event):
    name, key = event.get("hook_event_name"), key_for(event)
    if name not in ("UserPromptSubmit", "PreToolUse"):
        return {}
    if not key:
        return {"systemMessage": "Harness entry gate could not identify this turn; routing is not enforced."}
    BASE.mkdir(mode=0o700, parents=True, exist_ok=True)
    if BASE.is_symlink():
        raise ValueError("Entry state directory must not be a symlink")
    # Serialize selection and duplicate prompt events for this turn only.
    fd = os.open(BASE / (key + ".lock"), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return handle_locked(event, name, key)


def handle_locked(event, name, key):
    if name == "UserPromptSubmit":
        # An already delivered event must not relock a turn during a retry.
        if read(key) is None:
            save(key, {"created_at": time.time(), "route": None})
        return output(name, additionalContext=instruction(key))
    state = read(key)
    # ponytail: only turns observed by UserPromptSubmit are gated; existing turns
    # and subagent-only lifecycles need no invented parent/child ownership state.
    if state is None:
        return {}
    tool = event.get("tool_name", "")
    if tool in ("request_user_input", "request_user_input_async", "mcp__codex_app__end_realtime_voice_call"):
        return {}
    arguments = event.get("tool_input") or {}
    submitted = arguments.get("command", arguments.get("cmd")) if isinstance(arguments, dict) else None
    if tool in ("Bash", "exec_command"):
        for route in ROUTES:
            if submitted == command(key, route):
                if state["route"] is not None:
                    if state["route"] == route:
                        return {}
                    return output(name, permissionDecision="deny", permissionDecisionReason=
                                  "This turn already entered another route. Keep separate outputs within the selected ownership; clarify a changed scope with the user.")
                context = entry(route)
                state.update(route=route, entered_at=time.time(),
                             entry_sha256=hashlib.sha256(context.encode()).hexdigest())
                save(key, state)
                # Delivery happens in the hook even if the subsequent shell tool
                # fails. The enter command itself only reads and prints context.
                return output(name, additionalContext=context)
    if state["route"] in ROUTES:
        return {}
    return output(name, permissionDecision="deny", permissionDecisionReason=instruction(key))


def main():
    try:
        if len(sys.argv) == 4 and sys.argv[1] == "enter":
            state = read(sys.argv[2])
            if state is None or state.get("route") not in (None, sys.argv[3]):
                raise ValueError("No matching entry event; use the current turn's entry command")
            print(entry(sys.argv[3]))
        elif len(sys.argv) == 1:
            event = json.load(sys.stdin)
            if not isinstance(event, dict):
                raise ValueError("Expected a hook event object")
            print(json.dumps(handle(event)))
        else:
            raise ValueError("Usage: entry_hook.py [enter KEY personal|endix|mixed]")
    except (OSError, ValueError, TypeError) as error:
        # Exit 2 is a documented hook block, not an unsupported output shape.
        print(f"Harness entry failed: {error}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
