"""impact_replay.py (MAE-323 AC-7): the judgement over a recorded replay. A fallback is never a narrow selection,
a selector error or a missing summary is not a completed case, and a partial recording fails."""
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

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

    def test_unavailable_counts_keep_the_denominator_and_make_the_median_unknown(self):
        s = ir.judge([case(0, tests_run="unavailable"), case(1, tests_run=3)])
        self.assertEqual((s["completed"], s["count_unavailable"], s["median_tests_run"]),
                         (2, [case(0)["sha"][:12]], None))
        s = ir.judge([case(0, mode="all", tests_run="unavailable"), case(1, tests_run=3)])
        self.assertEqual((s["median_tests_run"], s["median_tests_run_narrow_only"]), (None, 3))


class Recording(unittest.TestCase):
    def test_parent_map_failure_is_disclosed_and_a_failed_child_selection_is_final(self):
        with tempfile.TemporaryDirectory() as d:
            wt, cache = Path(d, "checkout"), Path(d, "cache")
            plugin = wt / ir.PLUGIN_REL
            plugin.mkdir(parents=True)
            cache.mkdir()
            for rc in (1, 0):  # even exit zero without a map is not a usable parent build
                proc = ir.subprocess.CompletedProcess([], rc, "1 failed, 9 passed in 0.1s" if rc else "no test count",
                                                      "impact build: the suite failed")
                sel = ir.subprocess.CompletedProcess([], 1, json.dumps({"all": True, "ids": [], "reasons": [],
                                                                       "error": "child map build failed"}), "")
                with mock.patch.object(ir, "git"), \
                        mock.patch.object(ir, "run_impact", side_effect=[(proc, 1.0), (sel, 1.0)]) as run:
                    result = ir.record_case(case(0), wt, cache)
                self.assertEqual([c.args[1] for c in run.call_args_list], ["build", "select"])
                self.assertEqual(result["rc"], 1)
                self.assertIsNone(result["summary"])
                self.assertEqual(result["selector_error"], "child map build failed")
                self.assertEqual(ir.judge([result])["completed"], 0)
                self.assertEqual(len(ir.judge([result])["parent_map_failures"]), 1)
                self.assertEqual(result["parent_map_test_failures"], 1 if rc else None)

            sel = ir.subprocess.CompletedProcess([], 0, json.dumps({"all": False, "ids": ["tests/test_x.py"],
                                                                   "reasons": [], "error": None}), "")
            summary = case(0)["summary"]
            passed = ir.subprocess.CompletedProcess([], 0, "", ir.SUMMARY + json.dumps(summary))
            responses = iter([proc, sel, passed])
            def reply(plugin, command, *args):
                if command == "select":
                    (plugin / ".impact/map.json").write_text(json.dumps({"base": case(0)["sha"]}))
                return next(responses), 1.0
            with mock.patch.object(ir, "git"), mock.patch.object(ir, "run_impact", side_effect=reply):
                result = ir.record_case(case(0), wt, cache)
            s = ir.judge([result])
            self.assertEqual((s["completed"], s["selector_errors"], s["test_failures"]), (1, [], []))
            self.assertEqual(s["parent_map_failures"][0]["map_base"], case(0)["sha"])

    def test_cases_from_replays_only_pinned_pairs_and_keys_cache_by_selector(self):
        with tempfile.TemporaryDirectory() as d:
            source, output = Path(d, "source.json"), Path(d, "out.json")
            pairs = [{"sha": "a" * 40, "parent": "b" * 40}, {"sha": "c" * 40, "parent": "d" * 40}]
            source.write_text(json.dumps({"cases": [{**p, "summary": "ignore old results"} for p in pairs]}))
            with mock.patch.object(ir, "worktree", return_value=Path(d, "checkout")), \
                    mock.patch.object(ir, "record_case", side_effect=lambda c, wt, cache: {**case(0), **c}) as run, \
                    mock.patch.object(ir, "code_commits", side_effect=AssertionError("moving window")), \
                    mock.patch.object(ir.shutil, "rmtree"):
                rc = ir.main(["--manifest", str(output), "--record", "--cases-from", str(source),
                              "--cache", str(Path(d, "cache")), "--require-cases", "2"])
            self.assertEqual(rc, 0)
            self.assertEqual([c.args[0] for c in run.call_args_list], pairs)
            self.assertEqual(run.call_args.args[2], Path(d, "cache", ir.hashlib.sha256(ir.IMPACT.read_bytes()).hexdigest()).resolve())
            self.assertEqual(json.loads(output.read_text())["cases_from"], str(source))
            with mock.patch.object(ir, "worktree", return_value=Path(d, "checkout")), \
                    mock.patch.object(ir, "record_case", side_effect=OSError("interrupted recording")), \
                    mock.patch.object(ir.shutil, "rmtree") as cleanup:
                with self.assertRaisesRegex(OSError, "interrupted recording"):
                    ir.main(["--manifest", str(output), "--record", "--cases-from", str(source),
                             "--cache", str(Path(d, "cache"))])
                cleanup.assert_called_once_with(Path(d, "checkout"))

    def test_invalid_or_duplicate_pairs_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d, "source.json")
            for pairs in ([], [{"sha": "HEAD", "parent": "b" * 40}],
                          [{"sha": "a" * 40}], [{"sha": "a" * 40, "parent": "b" * 40}] * 2):
                source.write_text(json.dumps({"cases": pairs}))
                with self.assertRaises(ValueError):
                    ir.load_cases(source)

    def test_disposable_checkout_does_not_register_a_worktree_in_the_source(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(ir, "git") as git:
            path = Path(d, "checkout").resolve()
            self.assertEqual(ir.worktree(path), path)
            self.assertEqual(git.call_args.args, ("clone", "--shared", "--no-checkout", "-q", str(ir.ROOT), str(path)))
            path.mkdir()
            with self.assertRaises(ValueError):
                ir.worktree(path)


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

    def test_default_ceiling_remains_610(self):
        with tempfile.TemporaryDirectory() as d:
            m = Path(d, "m.json")
            m.write_text(json.dumps({"cases": [case(i, tests_run=610) for i in range(16)],
                                     "impact_sha256": ir.hashlib.sha256(ir.IMPACT.read_bytes()).hexdigest()}))
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(ir.main(["--manifest", str(m)]), 0)

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

    def test_test_failures_zero_boolean_counts_and_incomplete_extra_cases_fail(self):
        base = [case(i) for i in range(16)]
        for bad in (case(15, rc=1), case(15, tests_run=0), case(15, tests_run=True), case(15, summary=False)):
            self.assertEqual(self.run_check(base[:15] + [bad])[0], 1)
        self.assertEqual(self.run_check(base + [case(16, summary=False)])[0], 1)
        self.assertEqual(self.run_check([], require=0)[0], 1)
        legacy = case(15)
        legacy["map"] = "unbuilt: the suite failed"
        self.assertEqual(len(ir.judge([legacy])["parent_map_failures"]), 1)

    def test_changed_pinned_membership_fails(self):
        with tempfile.TemporaryDirectory() as d:
            source, output = Path(d, "source.json"), Path(d, "out.json")
            source.write_text(json.dumps({"cases": [{"sha": "a" * 40, "parent": "b" * 40}]}))
            output.write_text(json.dumps({"cases_from": str(source), "cases": [case(0)],
                                         "impact_sha256": ir.hashlib.sha256(ir.IMPACT.read_bytes()).hexdigest()}))
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(ir.main(["--manifest", str(output), "--require-cases", "1"]), 1)
