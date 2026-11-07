"""impact.py (MAE-323 AC-7): an unusable selection falls back to the full suite with a stated reason, a genuine
failure of the selected tests is never hidden by a full rerun, and a missing or unreadable map is a note."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from . import impact

T = "tests/test_evidence.py::Recognition::test_recognized_runners"


class FakeRunner:
    """Records the pytest argv of every call; answers (rc, count) from the queue."""

    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, args):
        self.calls.append(args)
        return self.answers.pop(0)

    def targets(self, i):
        args = self.calls[i]
        return args[args.index("no:cacheprovider") + 1:]


class RunSelected(unittest.TestCase):
    def test_all_by_rule_runs_the_suite_once_and_is_not_a_fallback(self):
        r = FakeRunner((0, 700))
        rc, s = impact.run_selected([impact.ALL], [], r)
        self.assertEqual((rc, len(r.calls), r.targets(0)[-1]), (0, 1, "tests"))
        self.assertEqual((s["mode"], s["selected"], s["fallback"], s["tests_run"]), ("all", None, None, 700))

    def test_empty_selection_runs_the_full_suite_and_says_so(self):
        r = FakeRunner((0, 700))
        rc, s = impact.run_selected([], [], r)
        self.assertEqual((rc, r.targets(0)), (0, ["tests"]))
        self.assertEqual((s["mode"], s["selected"], s["fallback"]), ("fallback", 0, "empty selection"))

    def test_missing_selected_file_is_named_and_the_full_suite_runs_instead(self):
        r = FakeRunner((0, 700))
        rc, s = impact.run_selected([T, "tests/test_gone.py::X::test_y"], [], r)
        self.assertEqual(len(r.calls), 1)                      # no narrow run with the missing file dropped
        self.assertEqual(r.targets(0), ["tests"])
        self.assertEqual(s["mode"], "fallback")
        self.assertIn("tests/test_gone.py", s["fallback"])

    def test_nothing_collected_or_a_bad_node_id_falls_back_to_the_full_suite(self):
        for bad_rc in (impact.NO_TESTS_COLLECTED, impact.USAGE_ERROR):
            r = FakeRunner((bad_rc, None), (0, 700))
            rc, s = impact.run_selected([T], [], r)
            self.assertEqual((rc, len(r.calls)), (0, 2), bad_rc)
            self.assertEqual((r.targets(0), r.targets(1)), ([T], ["tests"]))
            self.assertEqual((s["mode"], s["selected"], s["rc"]), ("fallback", 1, 0))
            self.assertIn(f"exit {bad_rc}", s["fallback"])

    def test_a_failing_selected_test_is_final_and_never_rerun_in_full(self):
        r = FakeRunner((1, 12))
        rc, s = impact.run_selected([T], [], r)
        self.assertEqual((rc, len(r.calls), r.targets(0)), (1, 1, [T]))
        self.assertEqual((s["mode"], s["fallback"], s["tests_run"], s["rc"]), ("narrow", None, 12, 1))

    def test_full_suite_failure_after_fallback_keeps_its_exit_code(self):
        r = FakeRunner((impact.NO_TESTS_COLLECTED, None), (1, 699))
        rc, s = impact.run_selected([T], [], r)
        self.assertEqual((rc, s["rc"], s["mode"]), (1, 1, "fallback"))

    def test_a_count_the_runner_did_not_print_is_unavailable_not_zero(self):
        r = FakeRunner((0, None))
        _, s = impact.run_selected([T], [], r)
        self.assertEqual(s["tests_run"], "unavailable")

    def test_pytest_args_keep_extra_arguments_and_parallelize_the_full_suite(self):
        args = impact.pytest_args(["tests"], ["-x"])
        self.assertEqual(args[-2:], ["-x", "tests"])
        self.assertIn("no:cacheprovider", args)
        if impact._have_xdist():
            self.assertIn("auto", args)


class MapNotes(unittest.TestCase):
    def test_missing_and_unreadable_maps_are_notes_not_crashes(self):
        with tempfile.TemporaryDirectory() as d:
            missing = Path(d, "map.json")
            with mock.patch.object(impact, "MAP", missing):
                self.assertEqual(impact.load_map(), (None, "no coverage map"))
            missing.write_text("{not json")
            with mock.patch.object(impact, "MAP", missing):
                cov, note = impact.load_map()
            self.assertIsNone(cov)
            self.assertIn("unreadable", note)
            missing.write_text(json.dumps({"files": {}}))        # no base: unusable
            with mock.patch.object(impact, "MAP", missing):
                self.assertIsNone(impact.load_map()[0])

    def test_selection_without_a_map_uses_the_static_graph_and_reports_the_note(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d, "map.json")
            bad.write_text("{not json")
            with mock.patch.object(impact, "MAP", bad):
                ids, why = impact.select(changes={"lib/maeng/evidence.py": {40}})
        self.assertTrue(ids)
        self.assertIn("unreadable", why[0])
        self.assertTrue(ids == [impact.ALL] or all(i.startswith("tests/test_") for i in ids))

    def test_ensure_map_without_coverage_is_a_note_and_builds_nothing(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(impact, "MAP", Path(d, "map.json")), \
                mock.patch.object(impact, "_have_coverage", return_value=False), \
                mock.patch.object(impact, "build", side_effect=AssertionError("must not build")):
            note = impact.ensure_map()
        self.assertIn("coverage not installed", note)

    def test_ensure_map_rebuilds_when_the_base_left_the_history(self):
        with tempfile.TemporaryDirectory() as d:
            m = Path(d, "map.json")
            m.write_text(json.dumps({"base": "0" * 40, "files": {}}))
            with mock.patch.object(impact, "MAP", m), mock.patch.object(impact, "_have_coverage", return_value=True), \
                    mock.patch.object(impact, "build") as build:
                note = impact.ensure_map()
        self.assertEqual(build.call_count, 1)
        self.assertIn("not an ancestor", note)
        self.assertIn("rebuilt", note)


class Main(unittest.TestCase):
    def run_main(self, argv, **patches):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.multiple(impact, ensure_map=lambda: None, **patches), redirect_stdout(out), redirect_stderr(err):
            rc = impact.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def summary(self, err):
        line = [ln for ln in err.splitlines() if ln.startswith("impact-summary: ")][-1]
        return json.loads(line[len("impact-summary: "):])

    def test_selector_error_falls_back_to_the_full_suite_with_the_error_as_reason(self):
        r = FakeRunner((0, 700))
        rc, _, err = self.run_main(["run"], select=mock.Mock(side_effect=SystemExit("git diff failed")), run_pytest=r)
        self.assertEqual((rc, r.targets(0)), (0, ["tests"]))
        s = self.summary(err)
        self.assertEqual(s["mode"], "fallback")
        self.assertIn("selector error: git diff failed", s["fallback"])

    def test_run_prints_one_summary_line_for_a_narrow_run(self):
        r = FakeRunner((0, 3))
        rc, _, err = self.run_main(["run"], select=lambda base=None: ([T], ["x: 1 tests"]), run_pytest=r)
        self.assertEqual((rc, r.targets(0)), (0, [T]))
        self.assertEqual(self.summary(err), {"mode": "narrow", "selected": 1, "fallback": None, "tests_run": 3, "rc": 0})

    def test_select_json_reports_ids_and_a_selector_error(self):
        rc, out, _ = self.run_main(["select", "--json"], select=lambda base=None: ([T], ["why"]))
        self.assertEqual((rc, json.loads(out)["ids"], json.loads(out)["all"]), (0, [T], False))
        rc, out, _ = self.run_main(["select", "--json"], select=mock.Mock(side_effect=ValueError("boom")))
        self.assertEqual(rc, 1)
        self.assertIn("boom", json.loads(out)["error"])
