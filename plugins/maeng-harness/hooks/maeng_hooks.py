#!/usr/bin/env python3
"""Single hook dispatcher: reads the hook JSON on stdin, dispatches on hook_event_name."""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))

from maeng import handlers  # noqa: E402


def fail_closed(reason):
    print("maeng-harness: " + reason, file=sys.stderr)
    return 2


def main():
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        # The event name is the only thing left to learn; anything but a provably non-gate event fails closed.
        m = re.search(r'"hook_event_name"\s*:\s*"(\w+)"', raw)
        if m and m.group(1) != "PreToolUse":
            print("maeng-harness: unreadable hook input", file=sys.stderr)
            return 0
        return fail_closed("unreadable hook input; denied because the gate cannot inspect the call")
    event = payload.get("hook_event_name")
    if not isinstance(event, str) or not event:
        return fail_closed("hook input has no hook_event_name; denied because the gate cannot tell the event")
    if event == "PreToolUse" and not isinstance(payload.get("tool_input"), dict):
        return fail_closed("PreToolUse tool_input is not an object; denied because the gate cannot inspect the call")
    handler = handlers.HANDLERS.get(event)
    if not handler:
        return 0
    try:
        out = handler(payload)
    except Exception as exc:
        print(f"maeng-harness: {event} handler failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        # Gates fail closed; trackers and context fail open.
        return 2 if event == "PreToolUse" else 0
    if out:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
