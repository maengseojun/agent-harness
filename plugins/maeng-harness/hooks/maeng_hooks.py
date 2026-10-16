#!/usr/bin/env python3
"""Single hook dispatcher: reads the hook JSON on stdin, dispatches on hook_event_name."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))

from maeng import handlers  # noqa: E402


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        print("maeng-harness: unreadable hook input", file=sys.stderr)
        return 0
    event = payload.get("hook_event_name", "")
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
