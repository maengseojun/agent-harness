"""Evidence integrity (MAE-323 AC-8): runner evidence outranks declarations and agent reports; zero or all-skipped
runs never pass; a count the runner did not print is "unavailable", never 0; an impact run is never ship evidence;
a pass and a fail on the same tree are kept as flaky."""
import json
import stat
import sys
import uuid

from maeng import evidence
from .helpers import HarnessCase
from .test_g1 import ShipBase

IMPACT_RUN = "python3 plugins/maeng-harness/tests/impact.py run"
PLAN = """# Plan

Requirements -> acceptance:

- **AC-1** the suite passes in parallel.

## Verification

- AC-1: `python3 -m pytest -q -n 8`
"""


class Counting(HarnessCase):
    def test_pytest_and_unittest_counts_skip_the_skipped(self):
        self.assertEqual(evidence.test_count("collected 7 items\n\n5 passed, 2 skipped in 1.0s"), 5)
        self.assertEqual(evidence.test_count("1 failed, 3 passed, 1 xfailed, 1 error in 2s"), 6)
        self.assertEqual(evidence.test_count("Ran 4 tests in 0.1s\n\nOK (skipped=1)"), 3)
        self.assertEqual(evidence.test_count("Ran 4 tests in 0.1s\n\nOK (skipped=4)"), 0)
        self.assertIsNone(evidence.test_count("ok  \tpkg\t0.2s"))                   # go test prints no count
        self.assertIsNone(evidence.test_count("ok"))

    def test_an_all_skipped_run_counts_as_zero_tests(self):
        self.assertTrue(evidence.ran_zero_tests("collected 3 items\n\n3 skipped in 0.1s"))
        self.assertTrue(evidence.ran_zero_tests("Ran 4 tests in 0.1s\n\nOK (skipped=4)"))
        self.assertFalse(evidence.ran_zero_tests("collected 3 items\n\n2 passed, 1 skipped in 0.1s"))


class HookCounts(ShipBase):
    def respond(self, output, cmd="pytest -q", **extra):
        tuid = "tu-" + uuid.uuid4().hex[:6]
        pre = self.hook("PreToolUse", self.repo, tool_name="Bash", tool_input={"command": cmd}, tool_use_id=tuid)
        self.hook("PostToolUse", self.repo, tool_name="Bash", tool_input={"command": cmd}, tool_use_id=tuid,
                  tool_response={"stdout": output, "stderr": "", **extra})
        return pre

    def status(self):
        return json.loads(self.cli("maeng-verify", ["status"], self.repo).stdout)

    def test_an_all_skipped_run_with_exit_zero_records_no_passing_evidence(self):
        self.respond("collected 3 items\n\n3 skipped in 0.1s", returnCode=0)
        self.assertEqual(self.load_state()["evidence"], [])
        self.assertFalse(self.status()["ship_verified"])
        self.respond("Ran 4 tests in 0.1s\n\nOK (skipped=4)", "python3 -m unittest discover", returnCode=0)
        self.assertEqual(self.load_state()["evidence"], [])

    def test_executed_count_is_recorded_and_an_unprinted_count_is_unavailable(self):
        self.respond("collected 7 items\n\n5 passed, 2 skipped in 1.0s")
        self.respond("ok")
        evs = self.load_state()["evidence"]
        self.assertEqual([e["tests_run"] for e in evs], [5, "unavailable"])
        self.assertTrue(all(e["ok"] for e in evs))
        self.assertTrue(self.status()["ship_verified"])            # unknown count is not zero

    def test_compound_output_cannot_grant_evidence_to_an_all_skipped_runner(self):
        _, _, err = self.respond("1 passed in 0.1s\nRan 4 tests in 0.1s\n\nOK (skipped=4)",
                                 "pytest -q x && python3 -m unittest discover", returnCode=0)
        self.assertIn("no evidence recorded", err)
        self.assertEqual(self.load_state()["evidence"], [])
        self.assertFalse(self.status()["ship_verified"])

    def test_impact_run_output_is_never_runner_evidence(self):
        self.respond("collected 40 items\n\n40 passed in 3.0s", IMPACT_RUN)
        self.assertEqual(self.load_state()["evidence"], [])
        self.assertFalse(self.status()["ship_verified"])


class ExecCounts(ShipBase):
    def fake_pytest(self, text):
        fake = self.tmp / "bin"
        fake.mkdir(exist_ok=True)
        py = fake / "pytest"
        py.write_text(f"#!{sys.executable}\nprint({text!r})\n")
        py.chmod(py.stat().st_mode | stat.S_IEXEC)
        return {"PATH": f"{fake}:{self.env['PATH']}"}

    def test_exec_all_skipped_records_nothing_and_a_count_is_kept(self):
        r = self.cli("maeng-verify", ["exec", "--", "pytest", "-q"], self.repo,
                     extra_env=self.fake_pytest("collected 3 items\n3 skipped in 0.1s"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ZERO tests", r.stderr)
        self.assertEqual(self.load_state()["evidence"], [])
        self.cli("maeng-verify", ["exec", "--", "pytest", "-q"], self.repo,
                 extra_env=self.fake_pytest("collected 3 items\n2 passed, 1 skipped in 0.1s"), check=True)
        self.assertEqual(self.load_state()["evidence"][-1]["tests_run"], 2)

    def test_exec_refuses_an_impact_run(self):
        r = self.cli("maeng-verify", ["exec", "--", *IMPACT_RUN.split()], self.repo)
        self.assertEqual(r.returncode, 2)
        self.assertIn("not an allowlisted runner", r.stderr)
        self.assertEqual(self.load_state()["evidence"], [])


class Declarations(ShipBase):
    def setUp(self):
        super().setUp()
        (self.repo / "plan.md").write_text(PLAN)
        self.cli("maeng-verify", ["bind", "MAE-1", "--plan", "plan.md"], self.repo, check=True)
        self.cli("maeng-verify", ["plan", "--met", "AC-1"], self.repo, check=True)

    def status(self):
        return json.loads(self.cli("maeng-verify", ["status"], self.repo).stdout)

    def test_a_declaration_never_satisfies_a_runner_requirement(self):
        r = self.cli("maeng-verify", ["ran", "--ok", "python3 -m pytest -q -n 8"], self.repo, check=True)
        self.assertIn("declaration never satisfies a runner requirement", r.stderr)
        st = self.status()
        self.assertFalse(st["ship_verified"])
        self.assertTrue(any("required check not passed" in m for m in st["missing"]), st["missing"])
        self.run_check(self.repo, "python3 -m pytest -q -n 8")   # the runner itself does
        self.assertTrue(self.status()["ship_verified"])

    def test_impact_output_never_satisfies_the_full_suite_requirement(self):
        self.run_check(self.repo, IMPACT_RUN)
        self.run_check(self.repo, "python3 -m pytest -q tests/test_x.py")   # a path-filtered run is not the suite either
        st = self.status()
        self.assertFalse(st["ship_verified"])
        self.assertTrue(any("python3 -m pytest -q -n 8" in m for m in st["missing"]), st["missing"])


class Flaky(ShipBase):
    def status(self):
        return json.loads(self.cli("maeng-verify", ["status"], self.repo).stdout)

    def test_fail_then_pass_on_one_tree_keeps_both_runs_marked_flaky(self):
        self.run_check(self.repo, "pytest -q", ok=False)
        self.run_check(self.repo, "pytest -q", ok=True)
        evs = self.load_state()["evidence"]
        self.assertEqual([(e["ok"], e.get("flaky")) for e in evs], [(False, True), (True, True)])
        st = self.status()
        self.assertTrue(st["ship_verified"])                       # the later pass resolves the failure
        self.assertEqual(st["flaky"], ["pytest"])

    def test_pass_then_fail_is_flaky_and_still_unresolved(self):
        self.run_check(self.repo, "pytest -q", ok=True)
        self.run_check(self.repo, "pytest -q", ok=False)
        self.assertTrue(all(e.get("flaky") for e in self.load_state()["evidence"]))
        st = self.status()
        self.assertFalse(st["ship_verified"])
        self.assertTrue(any("unresolved failure" in m for m in st["missing"]))
        self.assertEqual(st["flaky"], ["pytest"])

    def test_two_passes_or_different_checks_are_not_flaky(self):
        self.run_check(self.repo, "pytest -q", ok=True)
        self.run_check(self.repo, "pytest -q", ok=True)
        self.run_check(self.repo, "npm test", ok=False)
        self.assertFalse(any(e.get("flaky") for e in self.load_state()["evidence"]))
        self.assertEqual(self.status()["flaky"], [])
