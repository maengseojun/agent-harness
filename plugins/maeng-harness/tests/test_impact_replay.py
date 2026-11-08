"""impact_replay.py (MAE-323 AC-7): the judgement over a recorded replay. A fallback is never a narrow selection,
a selector error or a missing summary is not a completed case, and a partial recording fails."""
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("impact_replay", ROOT / "tools/testperf/impact_replay.py")
ir = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ir)


def case(i, mode="narrow", tests_run=10, rc=0, fallback=None, error=None, summary=True):
    return {"sha": f"{i:040x}", "parent": "p" * 40, "subject": f"c{i}", "code_files": ["lib/x.py"], "map": "cached",
            "select": None, "rc": rc, "selector_error": error, "duration_s": 1.0,
            "summary": {"mode": mode, "selected": None if mode == "all" else tests_run, "fallback": fallback,
                        "tests_run": tests_run, "rc": rc} if summary else None}


class Judge(unittest.TestCase):
    def test_fallbacks_and_all_runs_count_with_their_full_suite_size(self):
        cases = [case(i, tests_run=5) for i in range(15)] + [case(15, "fallback", 700, fallback="empty selection")]
        s = ir.judge(cases)
        self.assertEqual((s["completed"], s["median_tests_run"], s["median_tests_run_narrow_only"]), (16, 5, 5))
        self.assertEqual(s["fallbacks"], [{"sha": cases[15]["sha"][:12], "reason": "empty selection"}])
        cases = [case(i, "fallback", 700, fallback="x") for i in range(9)] + [case(i + 9, tests_run=5) for i in range(7)]
        self.assertEqual(ir.judge(cases)["median_tests_run"], 700)     # nine fallbacks: the median is the full suite

    def test_selector_errors_missing_summaries_and_crashes_are_not_completed(self):
        cases = [case(0, error="selector error: git"), case(1, summary=False), case(2, rc=2), case(3, rc=1), case(4)]
        s = ir.judge(cases)
        self.assertEqual(s["completed"], 2)                           # rc 1 is a real test failure: completed, listed
        self.assertEqual(s["test_failures"], [cases[3]["sha"][:12]])
        self.assertEqual(len(s["selector_errors"]), 1)

    def test_unavailable_counts_are_listed_and_excluded_from_the_median(self):
        s = ir.judge([case(0, tests_run="unavailable"), case(1, tests_run=3)])
        self.assertEqual((s["count_unavailable"], s["median_tests_run"]), ([case(0)["sha"][:12]], 3))


class Check(unittest.TestCase):
    def run_check(self, cases, partial=False, **kw):
        with tempfile.TemporaryDirectory() as d:
            m = Path(d, "m.json")
            m.write_text(json.dumps({"partial": partial, "cases": cases,
                                     "impact_sha256": ir.hashlib.sha256(ir.IMPACT.read_bytes()).hexdigest()}))
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = ir.main(["--manifest", str(m), "--require-cases", str(kw.get("require", 16)),
                              "--max-median", str(kw.get("median", 100))])
        return rc, err.getvalue()

    def test_sixteen_clean_narrow_cases_pass(self):
        self.assertEqual(self.run_check([case(i, tests_run=40) for i in range(16)])[0], 0)

    def test_fewer_cases_a_partial_recording_a_selector_error_or_a_high_median_fail(self):
        base = [case(i, tests_run=40) for i in range(16)]
        rc, err = self.run_check(base[:15])
        self.assertEqual(rc, 1)
        self.assertIn("completed cases 15 < 16", err)
        self.assertEqual(self.run_check(base, partial=True)[0], 1)
        rc, err = self.run_check(base[:15] + [case(15, error="selector error: boom")])
        self.assertIn("selector errors", err)
        rc, err = self.run_check([case(i, tests_run=101) for i in range(16)])
        self.assertIn("median executed tests 101 > 100", err)
        rc, err = self.run_check(base[:15] + [case(15, tests_run="unavailable")])
        self.assertIn("count unavailable", err)

    def test_a_changed_selector_invalidates_the_recording(self):
        with tempfile.TemporaryDirectory() as d:
            m = Path(d, "m.json")
            m.write_text(json.dumps({"partial": False, "cases": [case(i) for i in range(16)], "impact_sha256": "0" * 64}))
            err = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(err):
                rc = ir.main(["--manifest", str(m)])
        self.assertEqual(rc, 1)
        self.assertIn("impact.py changed", err.getvalue())
