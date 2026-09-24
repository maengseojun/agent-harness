"""Run with python3 -B harness/test_entry_hook.py; no external services."""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import entry_hook as hook


def check():
    with tempfile.TemporaryDirectory() as temporary:
        hook.BASE = Path(temporary) / "state"
        hook.SKILL = Path(temporary) / "SKILL.md"
        hook.SKILL.write_text("Personal specialist selection and verified closeout.")
        event = {"session_id": "parent", "turn_id": "turn-1", "hook_event_name": "UserPromptSubmit",
                 "prompt": "Endix-related private analysis; don't copy this secret prompt"}
        key = hook.key_for(event)
        assert "keywords alone" in hook.handle(event)["hookSpecificOutput"]["additionalContext"]
        assert "secret prompt" not in hook.state_path(key).read_text()
        pre = {**event, "hook_event_name": "PreToolUse", "tool_name": "Bash",
               "tool_input": {"command": "touch should-not-run"}}
        assert hook.handle(pre)["hookSpecificOutput"]["permissionDecision"] == "deny"
        # No shell suffix or different-turn receipt can unlock a pending turn.
        pre["tool_input"]["command"] = hook.command(key, "personal") + "; touch injected"
        assert hook.handle(pre)["hookSpecificOutput"]["permissionDecision"] == "deny"
        pre["tool_input"]["command"] = hook.command(key, "personal")
        assert "Selected PERSONAL" in hook.handle(pre)["hookSpecificOutput"]["additionalContext"]
        assert hook.read(key)["route"] == "personal"
        hook.handle(event)
        assert hook.handle({**pre, "tool_name": "mcp__notion__fetch"}) == {}
        for route in ("endix", "mixed"):
            other = {**event, "turn_id": route}
            hook.handle(other)
            other_key = hook.key_for(other)
            pending = {**pre, "turn_id": route}
            assert hook.handle(pending)["hookSpecificOutput"]["permissionDecision"] == "deny"
            pending["tool_input"] = {"command": hook.command(other_key, route)}
            body = hook.handle(pending)["hookSpecificOutput"]["additionalContext"]
            assert "READ-ONLY" in body and "END-471" in body
            assert hook.read(other_key)["route"] == route
        assert hook.handle({**pre, "turn_id": "unobserved-subagent"}) == {}
        assert "not enforced" in hook.handle({"hook_event_name": "PreToolUse"})["systemMessage"]
        try:
            hook.state_path("../escape")
            assert False, "Traversal accepted"
        except ValueError:
            pass
        for value in (None, [], 3, "text", {}, {"created_at": 1, "route": "bogus"},
                      {"created_at": 1, "route": "personal"}):
            hook.state_path(key).write_text(json.dumps(value))
            try:
                hook.handle(pre)
                assert False, "Malformed receipt accepted"
            except ValueError:
                pass
        hook.state_path(key).write_text('{')
        try:
            hook.handle(pre)
            assert False, "Truncated receipt accepted"
        except ValueError:
            pass
        simultaneous = {**event, "turn_id": "concurrent-choice"}
        hook.handle(simultaneous)
        shared = hook.key_for(simultaneous)
        def choose(route):
            return hook.handle({**pre, "turn_id": "concurrent-choice",
                                "tool_input": {"command": hook.command(shared, route)}})
        with ThreadPoolExecutor(max_workers=2) as pool:
            decisions = list(pool.map(choose, ("personal", "endix")))
        results = [d["hookSpecificOutput"] for d in decisions]
        assert sum("additionalContext" in d for d in results) == 1
        assert sum(d.get("permissionDecision") == "deny" for d in results) == 1
        selected = hook.read(shared)["route"]
        assert choose(selected) == {}
        # An unreadable personal skill leaves the turn locked.
        broken = {**event, "turn_id": "missing-skill"}
        hook.handle(broken)
        broken_key = hook.key_for(broken)
        hook.SKILL.unlink()
        try:
            hook.handle({**pre, "turn_id": "missing-skill", "tool_input": {"command": hook.command(broken_key, "personal")}})
            assert False, "Missing skill accepted"
        except OSError:
            assert hook.read(broken_key)["route"] is None
    print(json.dumps({"result": "pass", "cases": ["pending denial", "exact bootstrap", "shell suffix rejection", "semantic ownership contract", "prompt privacy", "retry idempotence", "turn isolation", "personal/endix/mixed", "Endix read-only context", "legacy lifecycle boundary", "invalid key", "malformed receipt rejection", "concurrent route selection", "missing skill stays locked"]}))


if __name__ == "__main__":
    check()
