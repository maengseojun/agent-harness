import json
import os
import shutil
import subprocess
import unittest

from maeng import schema
from .helpers import BIN, HOOK, ROOT


class PluginLayout(unittest.TestCase):
    def setUp(self):
        self.hooks = json.loads((ROOT / "hooks/hooks.json").read_text())["hooks"]

    def commands(self):
        for event, groups in self.hooks.items():
            for g in groups:
                for h in g["hooks"]:
                    yield event, g, h

    def test_all_events_dispatch_to_the_single_script(self):
        self.assertEqual(set(self.hooks), {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse",
                                           "PostToolUseFailure", "Stop", "SubagentStop", "SessionEnd"})
        for event, g, h in self.commands():
            self.assertEqual(h["command"], 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/maeng_hooks.py"')
            self.assertIsInstance(h["timeout"], (int, float), event)

    def test_gate_handlers_block_on_failure_and_matchers(self):
        pre = self.hooks["PreToolUse"]
        self.assertEqual(len(pre), 1)
        self.assertEqual(pre[0]["hooks"][0]["onFailure"], "block")
        self.assertEqual(pre[0]["matcher"], "Bash|Edit|Write|MultiEdit|NotebookEdit|mcp__.*__(merge_pull_request|update_pull_request_branch|push_files|create_or_update_file|delete_file)")
        for event, g, h in self.commands():
            if event != "PreToolUse":
                self.assertNotEqual(h.get("onFailure"), "block", event)
        self.assertIn("mcp__.*", self.hooks["PostToolUse"][0]["matcher"])
        self.assertEqual(self.hooks["PostToolUseFailure"][0]["matcher"], "Bash|Edit|Write|MultiEdit|NotebookEdit|mcp__.*")
        self.assertEqual(self.hooks["PostToolUse"][1]["matcher"], "Edit|Write|MultiEdit|NotebookEdit")
        for event in ("SessionStart", "UserPromptSubmit", "Stop", "SubagentStop", "SessionEnd"):
            self.assertNotIn("matcher", self.hooks[event][0])

    def test_timeouts_follow_the_spec_table(self):
        t = {e: [h["timeout"] for g in gs for h in g["hooks"]] for e, gs in self.hooks.items()}
        self.assertEqual(t["SessionStart"], [5])
        self.assertEqual(t["UserPromptSubmit"], [10])  # `승인 #N` reads the PR head with gh
        self.assertEqual(t["PreToolUse"], [15])  # MAE-284: 5s blocked calls under load
        self.assertEqual(sorted(t["PostToolUse"]), [5, 10])      # 10s only for the formatter (Edit/Write) group
        self.assertEqual(t["Stop"], [10])
        self.assertEqual(t["SubagentStop"], [3])
        self.assertLessEqual(t["SessionEnd"][0], 2)

    def test_bin_files_are_executable_python3(self):
        for name in ("maeng-verify", "maeng-ship", "maeng-review", "maeng-eta-isolate"):
            path = BIN / name
            self.assertTrue(os.access(path, os.X_OK), name)
            self.assertEqual(path.read_text().splitlines()[0], "#!/usr/bin/env python3")
        self.assertTrue(os.access(HOOK, os.X_OK))

    def test_verdict_schema(self):
        sch = schema.load_schema()
        verdict = {"verdict": "pass", "reviewer": {"model": "gpt-6-astra", "effort": "medium"}, "findings": [],
                   "subject": {"kind": "code", "repo": "o/r", "pr": 1, "base": "a", "head": "b", "criteria_rev": None,
                               "digest": "d", "destination": "refs/heads/main", "op": "merge"}}
        self.assertEqual(schema.validate(verdict, sch), [])
        bad = json.loads(json.dumps(verdict))
        bad["verdict"] = "approve"
        del bad["subject"]["op"]
        bad["extra"] = 1
        self.assertEqual(len(schema.validate(bad, sch)), 3)

    @unittest.skipUnless(shutil.which("claude"), "claude CLI not installed")
    def test_claude_plugin_validate(self):
        p = subprocess.run(["claude", "plugin", "validate", str(ROOT)], capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
