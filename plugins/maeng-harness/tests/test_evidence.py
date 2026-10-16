import json

from maeng import evidence
from .helpers import HarnessCase
from .test_g1 import ShipBase


class Recognition(HarnessCase):
    def test_recognized_runners(self):
        yes = {"pytest -q": "pytest", "python3 -m pytest tests": "pytest", "python -m unittest discover -s t": "unittest",
               "cd sub && pytest": "pytest", "uv run pytest": "pytest", "npm test": "npm test",
               "pnpm run lint": "pnpm run lint", "yarn test": "yarn test", "npm run typecheck": "npm run typecheck",
               "npm run build": "npm run build", "forge test -vvv": "forge test", "forge build": "forge build",
               "cargo test": "cargo test", "cargo clippy -- -D warnings": "cargo clippy", "cargo build": "cargo build",
               "go test ./...": "go test", "make test": "make test", "make check": "make check",
               "ruff check .": "ruff check", "mypy src": "mypy", "tsc --noEmit": "tsc",
               "claude plugin validate plugins/x": "claude plugin validate", "playwright test": "playwright test",
               "npx playwright test": "playwright test"}
        for cmd, name in yes.items():
            rec = evidence.recognize(cmd)
            self.assertIsNotNone(rec, cmd)
            self.assertEqual(rec["checks"][0][0], name, cmd)

    def test_not_recognized(self):
        for cmd in ("ls", "git status", "pytest | tail", "pytest; echo done", "pytest || true", "pytest &", "echo pytest",
                    "ruff format .", "npm install", "make", "python script.py"):
            self.assertIsNone(evidence.recognize(cmd), cmd)


class EvidenceTests(ShipBase):
    def state_evidence(self):
        return self.load_state()["evidence"]

    def test_edit_during_check_gives_no_evidence(self):
        self.run_check(self.repo, "pytest -q",
                       between=lambda: (self.repo / "app.py").write_text("print('mid-check edit')\n"))
        self.assertEqual(self.state_evidence(), [])
        self.assertTrue(self.bash_pre(self.repo, "git push origin feat")[0])

    def test_background_and_piped_runs_give_no_evidence(self):
        self.hook("PreToolUse", self.repo, tool_name="Bash", tool_input={"command": "pytest", "run_in_background": True},
                  tool_use_id="bg")
        self.hook("PostToolUse", self.repo, tool_name="Bash", tool_input={"command": "pytest", "run_in_background": True},
                  tool_use_id="bg", tool_response={})
        self.run_check(self.repo, "pytest | tail -3")
        self.assertEqual(self.state_evidence(), [])

    def test_formatter_change_invalidates_evidence(self):
        (self.repo / "fmt.py").write_text("import sys,pathlib\np=pathlib.Path(sys.argv[1]);p.write_text(p.read_text().upper())\n")
        (self.repo / ".maeng").mkdir()
        (self.repo / ".maeng/verify.json").write_text(json.dumps({"formatter": ["python3", "fmt.py", "{file}"]}))
        self.commit_all(self.repo, "formatter policy")
        self.verified()
        self.assertFalse(self.bash_pre(self.repo, "git push origin feat")[0])
        # the Edit tool "writes" the file; the synchronous formatter then rewrites it
        self.hook("PostToolUse", self.repo, tool_name="Edit", tool_input={"file_path": str(self.repo / "app.py")}, tool_response={})
        self.assertEqual((self.repo / "app.py").read_text(), "PRINT('HI')\n")
        self.commit_all(self.repo, "formatted")
        self.assertTrue(self.bash_pre(self.repo, "git push origin feat")[0])

    def test_failed_pytest_plus_passing_ruff_is_not_ship_verified(self):
        self.run_check(self.repo, "pytest -q", ok=False)
        self.run_check(self.repo, "ruff check .", ok=True)
        denied, reason = self.bash_pre(self.repo, "git push origin feat")
        self.assertTrue(denied)
        self.assertIn("unresolved failure: pytest", reason)
        self.run_check(self.repo, "pytest -q", ok=True)     # same check passes later at the same tree
        self.assertFalse(self.bash_pre(self.repo, "git push origin feat")[0])

    def test_later_failure_after_pass_is_unresolved(self):
        self.verified()
        self.run_check(self.repo, "pytest -q", ok=False)
        self.assertTrue(self.bash_pre(self.repo, "git push origin feat")[0])

    def test_required_checks_precedence(self):
        (self.repo / ".maeng").mkdir()
        (self.repo / ".maeng/verify.json").write_text(json.dumps({"required": ["pytest", "ruff check"]}))
        self.commit_all(self.repo, "policy")
        self.verified()
        denied, reason = self.bash_pre(self.repo, "git push origin feat")
        self.assertTrue(denied)
        self.assertIn("ruff check", reason)
        self.run_check(self.repo, "ruff check .")
        self.assertFalse(self.bash_pre(self.repo, "git push origin feat")[0])
        # a bound plan's Verification section takes precedence over the policy
        plan = self.repo.parent / "plan.md"
        plan.write_text("# Plan\nAC-1 works\n## Verification\nAC-1: mypy\n")
        self.cli("maeng-verify", ["bind", "MAE-1", "--plan", str(plan)], self.repo)
        denied, reason = self.bash_pre(self.repo, "git push origin feat")
        self.assertTrue(denied)
        self.assertIn("mypy", reason)

    def test_declared_ran_and_skip(self):
        r = self.cli("maeng-verify", ["ran", "--ok", "screenshot checked"], self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        ev = self.state_evidence()
        self.assertEqual((ev[0]["check"], ev[0]["ok"], ev[0]["kind"]), ("screenshot checked", True, "declared"))
        # declared checks do not satisfy the default "recognized test runner" rule
        self.assertTrue(self.bash_pre(self.repo, "git push origin feat")[0])

    def test_dirty_submodule_gives_no_evidence(self):
        sub = self.make_repo("subrepo", with_remote=False)
        self.git(self.repo, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(sub), "vendor/sub")
        self.commit_all(self.repo, "add submodule")
        self.verified()                                    # clean submodule: evidence is recorded
        self.assertEqual(len(self.state_evidence()), 1)
        (self.repo / "vendor/sub/app.py").write_text("print('dirty')\n")
        self.run_check(self.repo, "pytest -q")
        self.assertEqual(len(self.state_evidence()), 1)    # no new evidence while dirty
        r = self.cli("maeng-verify", ["skip", "x"], self.repo)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("dirty submodule", r.stderr)


class PlanCoverage(ShipBase):
    def setUp(self):
        super().setUp()
        self.plan = self.tmp / "plan.md"
        self.plan.write_text("# Plan\n- AC-1 does a\n- AC-2 does b\n## Verification\nAC-1: pytest\nAC-2: pytest\n")
        r = self.cli("maeng-verify", ["bind", "MAE-9", "--plan", str(self.plan)], self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.verified()

    def push_denied(self):
        return self.bash_pre(self.repo, "git push origin feat")

    def test_no_plan_record_blocks_ship(self):
        denied, reason = self.push_denied()
        self.assertTrue(denied)
        self.assertIn("no plan record", reason)

    def test_missing_ac_blocks_ship_even_with_empty_unmet(self):
        self.cli("maeng-verify", ["plan", "--met", "AC-1"], self.repo)
        denied, reason = self.push_denied()
        self.assertTrue(denied)
        self.assertIn("AC-2", reason)

    def test_unmet_ac_blocks_then_complete_coverage_passes(self):
        self.cli("maeng-verify", ["plan", "--met", "AC-1", "--unmet", "AC-2"], self.repo)
        self.assertTrue(self.push_denied()[0])
        self.cli("maeng-verify", ["plan", "--met", "AC-1,AC-2"], self.repo)
        self.assertFalse(self.push_denied()[0])

    def test_stale_criteria_blocks_ship(self):
        self.cli("maeng-verify", ["plan", "--met", "AC-1,AC-2"], self.repo)
        self.assertFalse(self.push_denied()[0])
        self.plan.write_text(self.plan.read_text().replace("## Verification", "- AC-3 new criterion\n## Verification"))
        denied, reason = self.push_denied()
        self.assertTrue(denied)
        self.assertIn("plan changed since bind", reason)
        self.cli("maeng-verify", ["bind", "MAE-9", "--plan", str(self.plan)], self.repo)
        self.assertTrue(self.push_denied()[0])             # re-bound: AC-3 is not met yet
        self.cli("maeng-verify", ["plan", "--met", "AC-1,AC-2,AC-3"], self.repo)
        denied, reason = self.push_denied()
        self.assertFalse(denied, reason)

    def test_plan_record_stale_after_code_change(self):
        self.cli("maeng-verify", ["plan", "--met", "AC-1,AC-2"], self.repo)
        (self.repo / "app.py").write_text("print('later')\n")
        self.commit_all(self.repo, "later")
        self.run_check(self.repo, "pytest -q")
        denied, reason = self.push_denied()
        self.assertTrue(denied)
        self.assertIn("no plan record", reason)
