import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "tools" / "testperf" / "subagent_context.py"
PLUGIN = json.loads((REPO / "plugins/maeng-tools/.claude-plugin/plugin.json").read_text())["version"]

DEF = hashlib.sha256((REPO / "plugins/maeng-tools/agents/standard.md").read_bytes()).hexdigest()
NONCE = "0123456789abcdef"

LINES = [
    {"type": "user", "version": "2.1.314", "message": {"content": f"probe {NONCE}: reply ok"}},
    {"type": "assistant", "version": "2.1.314", "message": {"model": "claude-sonnet-5-5", "usage": {
        "input_tokens": 2, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 30}}},
]


class SubagentContext(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def run_check(self, lines=LINES, agent="maeng-tools:standard", total=132, std=None, plugin=None):
        tr = self.tmp / "agent-x.jsonl"
        tr.write_text("\n".join(json.dumps(l) for l in lines) + "\n")
        (self.tmp / "agent-x.meta.json").write_text(json.dumps({"agentType": agent}))
        rec = {"transcript": str(tr), "agent_type": "maeng-tools:standard", "model": "claude-sonnet-5-5",
               "cli_version": "2.1.314", "input_tokens": 2, "cache_creation_input_tokens": 100,
               "cache_read_input_tokens": 30, "total_input_tokens": total, "status": "observed",
               "nonce": NONCE, "definition_sha256": DEF, "plugin_dir": "plugins/maeng-tools"}
        rec.update(std or {})
        ev = {"standard": rec, "plugin": {"version": plugin or PLUGIN}, "cli_version": "2.1.314",
              "omit_claude_md_trial": {"result": "supported"}}
        f = self.tmp / "ev.json"
        f.write_text(json.dumps(ev))
        return subprocess.run([sys.executable, str(SCRIPT), "--evidence", str(f), "--max-input-tokens", "20000",
                               "--require-observed"], capture_output=True, text=True)

    def test_consistent_passes(self):
        r = self.run_check()
        self.assertEqual((r.returncode, r.stderr), (0, ""))

    def test_missing_transcript_fails(self):
        r = self.run_check(std={"transcript": str(self.tmp / "gone.jsonl")})
        self.assertEqual(r.returncode, 1)
        self.assertIn("transcript missing", r.stderr)

    def test_other_agent_type_fails(self):
        r = self.run_check(agent="maeng-tools:design")
        self.assertEqual(r.returncode, 1)
        self.assertIn("agent_type", r.stderr)

    def test_cli_version_differs_fails(self):
        lines = copy.deepcopy(LINES)
        for l in lines:
            l["version"] = "9.9.9"
        r = self.run_check(lines=lines)
        self.assertEqual(r.returncode, 1)
        self.assertIn("cli_version", r.stderr)

    def test_plugin_version_differs_fails(self):
        r = self.run_check(plugin="0.0.1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("differs from this checkout", r.stderr)

    def test_unknown_usage_fails(self):
        lines = copy.deepcopy(LINES)
        del lines[1]["message"]["usage"]["cache_read_input_tokens"]
        r = self.run_check(lines=lines, std={"cache_read_input_tokens": 0})
        self.assertEqual(r.returncode, 1)
        self.assertIn("unknown", r.stderr)

    def test_zero_total_fails(self):
        lines = copy.deepcopy(LINES)
        lines[1]["message"]["usage"] = {"input_tokens": 0, "cache_creation_input_tokens": 0,
                                        "cache_read_input_tokens": 0}
        r = self.run_check(lines=lines, total=0)
        self.assertEqual(r.returncode, 1)
        self.assertIn("positive", r.stderr)

    def test_json_total_disagrees_fails(self):
        r = self.run_check(total=99)
        self.assertEqual(r.returncode, 1)
        self.assertIn("total_input_tokens", r.stderr)

    def test_missing_nonce_fails(self):
        r = self.run_check(std={"nonce": None})
        self.assertEqual(r.returncode, 1)
        self.assertIn("nonce missing", r.stderr)

    def test_nonce_mismatch_fails(self):
        r = self.run_check(std={"nonce": "ffffffffffffffff"})
        self.assertEqual(r.returncode, 1)
        self.assertIn("nonce not in", r.stderr)

    def test_definition_hash_mismatch_fails(self):
        r = self.run_check(std={"definition_sha256": "0" * 64})
        self.assertEqual(r.returncode, 1)
        self.assertIn("definition_sha256 differs", r.stderr)

    def test_over_the_limit_fails_and_the_limit_itself_passes(self):
        big = copy.deepcopy(LINES)
        big[1]["message"]["usage"] = {"input_tokens": 2, "cache_creation_input_tokens": 19999, "cache_read_input_tokens": 0}
        r = self.run_check(lines=big, total=20001, std={"cache_creation_input_tokens": 19999, "cache_read_input_tokens": 0})
        self.assertEqual(r.returncode, 1)
        big[1]["message"]["usage"]["cache_creation_input_tokens"] = 19998
        r = self.run_check(lines=big, total=20000, std={"cache_creation_input_tokens": 19998, "cache_read_input_tokens": 0})
        self.assertEqual((r.returncode, r.stderr), (0, ""))


if __name__ == "__main__":
    unittest.main()


    def test_another_plugin_dir_fails_even_with_a_matching_hash(self):
        # Round-2 finding on PR #103: the hash must belong to the plugin the launch loaded, and that must be this candidate.
        r = self.run_check(std={"plugin_dir": str(self.tmp / "other-maeng-tools")})
        self.assertEqual(r.returncode, 1)
        self.assertIn("is not this checkout's plugins/maeng-tools", r.stderr)
        r = self.run_check(std={"plugin_dir": None})
        self.assertEqual(r.returncode, 1)
        self.assertIn("plugin_dir missing", r.stderr)
