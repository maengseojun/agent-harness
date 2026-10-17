"""Regression tests for Astra round-5 findings (PR #38, MAENG-220): MCP PR destination (1), non-executing runner
values (2), G3 read-only option allowlist (3), declarations vs runner requirements + `maeng-verify exec` (4), corrupt
session state (5), Notion registry/journal schema (6)."""
import unittest
import json
import sys

from maeng import evidence, receipts, state
from maeng import tree as treelib
from .helpers import HarnessCase
from .test_g1 import ShipBase
from .test_g2_g3 import DB, PAGE, UPDATE
from .test_r3 import EtaDirMixin


class R5_1_McpPullRequestDestination(ShipBase):
    MCP = "mcp__github__create_pull_request"

    def tin(self, **kw):
        return {"owner": "o", "repo": "r", "head": "feat", "base": "main", "title": "t", **kw}

class R5_2_NonExecutingRunnerValues(HarnessCase):
    def test_go_count_must_be_positive(self):
        for cmd in ("go test ./... -count=0", "go test -count 0 ./...", "go test -count=00 ./...", "go test -count=-1 ./..."):
            self.assertIsNone(evidence.recognize(cmd), cmd)
        for cmd in ("go test ./... -count=1", "go test -count=10 ./..."):
            self.assertIsNotNone(evidence.recognize(cmd), cmd)

    def test_go_run_must_select_something(self):
        for cmd in ("go test -run '^$' ./...", "go test -run '' ./...", "go test -run= ./...", "go test -run '^' ./...",
                    "go test -run 'a^b' ./...", "go test -run '()' ./..."):
            self.assertIsNone(evidence.recognize(cmd), cmd)
        for cmd in ("go test -run TestA ./...", "go test -run '^TestA|TestB' ./...", "go test -run TestA/sub ./..."):
            self.assertIsNotNone(evidence.recognize(cmd), cmd)

    def test_empty_pytest_selectors_are_not_evidence(self):
        for cmd in ("pytest -k ''", "pytest -m ''", "pytest -k=", "python3 -m pytest -k '  '"):
            self.assertIsNone(evidence.recognize(cmd), cmd)
        self.assertIsNotNone(evidence.recognize("pytest -k 'not slow' -m unit"))


class R5_3_ReadOnlyOptionAllowlist(EtaDirMixin, HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.eta_root.mkdir()
        self.start(self.repo)
        self.eta_dir = self.make_eta_dir(self.repo)
        (self.eta_dir / "log").write_text("x\n")

    def denied(self, cmd):
        d, reason = self.bash_pre(self.eta_dir, cmd)
        self.assertTrue(d, f"expected deny in eta dir: {cmd} ({reason})")

    def allowed(self, cmd):
        d, reason = self.bash_pre(self.eta_dir, cmd)
        self.assertFalse(d, f"expected allow in eta dir: {cmd} ({reason})")

    def test_plain_reads_are_allowed(self):
        for cmd in ("cat log", "cat -n log", "head -5 log", "head -n 3 log", "tail -n 2 log", "tail -f log", "wc -l log",
                    "stat log", "ls -la", "ls -1 --color=never", "grep -rn pat .", "grep -n -e pat -C 2 log",
                    "rg -n --hidden pat", "rg -t py pat", "diff -u log log", "find . -name '*.py' -type f",
                    "find . -maxdepth 2 -print", "git log --oneline -n 5", "git status --short", "git diff --stat HEAD",
                    "git show HEAD", "git log --format=%H -3", "git rev-parse --show-toplevel", "gh pr view 1 --json title",
                    "gh pr list --state open -L 5", "sort -u log", "pwd", "echo hi", "jq -r . log", "date -u"):
            self.allowed(cmd)


class R5_4_ExecAndDeclarations(HarnessCase):
    REQ = "python3 -m pytest -q"

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo(files={"test_ok.py": "def test_ok():\n    assert True\n", "app.py": "x = 1\n",
                                                 ".gitignore": "__pycache__/\n.pytest_cache/\n"})
        self.start(self.repo)

    def bind(self, *checks):
        args = ["bind", "MAE-1"]
        for c in checks:
            args += ["--check", c]
        self.assertEqual(self.cli("maeng-verify", args, self.repo).returncode, 0)

    def status(self):
        return json.loads(self.cli("maeng-verify", ["status"], self.repo).stdout)

    def test_declaration_cannot_satisfy_a_runner_requirement(self):
        self.bind("pytest")
        r = self.cli("maeng-verify", ["ran", "--ok", "pytest"], self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("exec", r.stderr)
        st = self.status()
        self.assertFalse(st["ship_verified"], st)
        self.assertTrue(any("pytest" in m for m in st["missing"]))

    def test_declaration_still_satisfies_free_text_requirements(self):
        self.bind("manual smoke test in staging")
        self.cli("maeng-verify", ["ran", "--ok", "manual smoke test in staging"], self.repo)
        self.assertTrue(self.status()["ship_verified"])

    def test_exec_records_runner_evidence_and_satisfies(self):
        self.bind(self.REQ)
        r = self.cli("maeng-verify", ["exec", "--", "python3", "-m", "pytest", "-q"], self.repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("passed", r.stdout)
        ev = self.load_state()["evidence"][-1]
        self.assertEqual((ev["source"], ev["ok"], ev["kind"]), ("runner", True, "test"))
        self.assertEqual(ev["exit_code"], 0)
        self.assertEqual(len(ev["output_sha256"]), 64)
        self.assertIn("duration_s", ev)
        self.assertTrue(self.status()["ship_verified"])

    def test_exec_identity_includes_relative_cwd(self):
        sub = self.repo / "pkg"
        sub.mkdir()
        (sub / "test_p.py").write_text("def test_p():\n    assert True\n")
        self.commit_all(self.repo)
        r = self.cli("maeng-verify", ["exec", "--", "python3", "-m", "pytest", "-q"], sub)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        ev = self.load_state()["evidence"][-1]
        self.assertEqual((ev["dir"], ev["identity"]), ("pkg", "pytest@pkg"))

    def test_failing_run_records_failure_and_exit_code(self):
        (self.repo / "test_bad.py").write_text("def test_bad():\n    assert False\n")
        self.commit_all(self.repo)
        r = self.cli("maeng-verify", ["exec", "--", "python3", "-m", "pytest", "-q", "test_bad.py"], self.repo)
        self.assertEqual(r.returncode, 1)
        ev = self.load_state()["evidence"][-1]
        self.assertFalse(ev["ok"])
        self.assertEqual(ev["exit_code"], 1)
        self.assertFalse(self.status()["ship_verified"])

    def test_non_allowlisted_command_is_refused(self):
        marker = self.tmp / "ran"
        for cmd in (["touch", str(marker)], ["python3", "-c", f"open({str(marker)!r}, 'w')"],
                    ["python3", "-m", "pytest", "--collect-only"], ["sh", "-c", "pytest"], ["pytest", "&&", "touch", "x"],
                    ["FOO=1", "pytest"]):
            r = self.cli("maeng-verify", ["exec", "--", *cmd], self.repo)
            self.assertEqual(r.returncode, 2, (cmd, r.stderr))
            self.assertIn("not an allowlisted runner", r.stderr)
        self.assertFalse(marker.exists())
        self.assertEqual(self.load_state()["evidence"], [])

    def test_tree_change_during_exec_records_no_evidence(self):
        (self.repo / "test_mut.py").write_text(
            "def test_mut():\n    open('app.py', 'a').write('y = 2\\n')\n")
        self.commit_all(self.repo)
        r = self.cli("maeng-verify", ["exec", "--", "python3", "-m", "pytest", "-q", "test_mut.py"], self.repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.load_state()["evidence"], [])
        self.assertEqual(self.load_state()["pending"], {})


class R5_5_CorruptSessionState(EtaDirMixin, HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.eta_root.mkdir()
        self.start(self.repo)
        self.eta_dir = self.make_eta_dir(self.repo)
        self.path = state.path_for(self.sid)

    def test_other_events_have_no_side_effects(self):
        self.path.write_text("{broken")
        for event, extra in (("UserPromptSubmit", {"prompt": "x"}), ("SessionStart", {"source": "startup"}),
                             ("PostToolUse", {"tool_name": "Bash", "tool_input": {"command": "ls"},
                                              "tool_use_id": "t", "tool_response": {}}),
                             ("Stop", {})):
            rc, out, err = self.hook(event, self.repo, **extra)
            self.assertEqual(rc, 0, event)
            self.assertIsNone(out, event)
            self.assertIn("unreadable", err, event)
        self.assertEqual(self.path.read_text(), "{broken")

    def test_quarantine_moves_the_file_aside(self):
        self.path.write_text("{broken")
        r = self.cli("maeng-verify", ["state"], self.repo)
        self.assertEqual(r.returncode, 1)
        self.assertIn("unreadable", r.stderr)
        r = self.cli("maeng-verify", ["state", "--quarantine"], self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.path.exists())
        moved = list(self.path.parent.glob(self.path.name + ".corrupt-*"))
        self.assertEqual(len(moved), 1)
        self.assertEqual(moved[0].read_text(), "{broken")
        self.start(self.repo)                                           # restart: fresh state
        self.assertTrue(self.path.exists())

    def test_quarantine_leaves_a_readable_state_alone(self):
        before = self.path.read_text()
        r = self.cli("maeng-verify", ["state", "--quarantine"], self.repo)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.path.read_text(), before)

    def test_cli_commands_refuse_corrupt_state(self):
        self.path.write_text("{broken")
        r = self.cli("maeng-verify", ["status"], self.repo)
        self.assertEqual(r.returncode, 1)
        self.assertIn("unreadable", r.stderr)
        self.assertEqual(self.path.read_text(), "{broken")


class R5_6_NotionRegistrySchema(HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.start(self.repo)
        self.reg = receipts._notion("registry.json")
        self.jr = receipts._notion("journal.json")
        self.page = PAGE.replace("-", "")
        self.update = {"page_id": PAGE, "command": "update_properties"}

    def call(self, tin=None):
        return self.pre(self.repo, UPDATE, tin or self.update)

    def write(self, path, obj):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(obj if isinstance(obj, str) else json.dumps(obj))

    def test_seed_repairs_an_invalid_registry(self):
        self.write(self.reg, {"page_ids": self.page})
        r = self.cli("maeng-review", ["registry", "seed", PAGE], self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(receipts.registry_ids(), {self.page})
        self.assertEqual(len(list(self.reg.parent.glob("registry.json.invalid-*"))), 1)
        r = self.cli("maeng-review", ["registry", "seed", "nothex"], self.repo)
        self.assertEqual(r.returncode, 2)


class R5_DefaultModeNeedsUnfilteredSuite(unittest.TestCase):
    """A filtered run (selector that may match nothing) never satisfies the default 'passing tests' rule."""

    def test_filtered_identities_are_not_unfiltered(self):
        from maeng import evidence as ev
        for ident in ("pytest -k foo", "pytest tests/unit", "pytest@sub", "go test -run X ./...", "go test ./pkg",
                      "unittest discover -s a -p test_x.py", "unittest mod.Test", "forge test --match-test x",
                      "playwright test e2e", "playwright test --project chromium"):
            self.assertFalse(ev.unfiltered(ident), ident)

    def test_whole_suite_identities_are_unfiltered(self):
        from maeng import evidence as ev
        for ident in ("pytest", "pytest -x", "go test ./...", "go test -race -count=1 ./...", "make test", "npm test",
                      "unittest discover -s plugins/x/tests -t plugins/x", "forge test -vvv", "playwright test"):
            self.assertTrue(ev.unfiltered(ident), ident)
