"""impact.py (MAE-323 AC-7): an unusable selection falls back to the full suite with a stated reason, a genuine
failure of the selected tests is never hidden by a full rerun, and a missing or unreadable map forces a full fallback."""
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

    def test_selection_without_a_map_falls_back_to_all_and_reports_the_note(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d, "map.json")
            bad.write_text("{not json")
            with mock.patch.object(impact, "MAP", bad):
                ids, why = impact.select(changes={"lib/maeng/evidence.py": {40}})
        self.assertEqual(ids, [impact.ALL])
        self.assertIn("unreadable", why[0])

    def test_off_history_map_without_coverage_falls_back_to_all(self):
        with tempfile.TemporaryDirectory() as d:
            m = Path(d, "map.json")
            m.write_text(json.dumps({"base": "0" * 40, "files": {}}))
            with mock.patch.object(impact, "MAP", m), mock.patch.object(impact, "_have_coverage", return_value=False):
                note = impact.ensure_map()
                ids, why = impact.select(changes={"lib/maeng/evidence.py": {40}})
        self.assertEqual(ids, [impact.ALL])
        self.assertIn("not an ancestor", why[0])
        self.assertIn("coverage not installed", note)

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

    def test_a_failed_build_is_not_downgraded_to_a_note(self):
        with mock.patch.object(impact, "load_map", return_value=(None, "no coverage map")), \
                mock.patch.object(impact, "_have_coverage", return_value=True), \
                mock.patch.object(impact, "build", side_effect=SystemExit("the suite failed")):
            with self.assertRaisesRegex(SystemExit, "map not rebuilt.*the suite failed"):
                impact.ensure_map()


class Main(unittest.TestCase):
    def run_main(self, argv, **patches):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.multiple(impact, **{"ensure_map": lambda: None, **patches}), \
                redirect_stdout(out), redirect_stderr(err):
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

    def test_missing_map_runs_a_reported_full_fallback_and_select_json_says_all(self):
        r = FakeRunner((0, 700))
        with tempfile.TemporaryDirectory() as d, mock.patch.object(impact, "MAP", Path(d, "map.json")):
            rc, _, err = self.run_main(["run"], run_pytest=r)
            select_rc, out, _ = self.run_main(["select", "--json"])
        self.assertEqual((rc, r.targets(0)), (0, ["tests"]))
        s = self.summary(err)
        self.assertEqual(s["mode"], "fallback")
        self.assertIn("no coverage map", s["fallback"])
        self.assertEqual((select_rc, json.loads(out)["all"]), (0, True))
        self.assertIn("no coverage map", json.loads(out)["reasons"])

    def test_failed_map_build_returns_failure_without_a_green_rerun(self):
        r = FakeRunner((0, 700))
        rc, _, err = self.run_main(["run"],
                                   ensure_map=mock.Mock(side_effect=SystemExit("the suite failed")), run_pytest=r)
        self.assertEqual((rc, r.calls), (1, []))
        s = self.summary(err)
        self.assertEqual((s["mode"], s["rc"]), ("fallback", 1))
        self.assertIn("coverage map build failed", s["fallback"])
        self.assertIn("the suite failed", s["fallback"])

    def test_select_json_reports_ids_and_a_selector_error(self):
        rc, out, _ = self.run_main(["select", "--json"], select=lambda base=None: ([T], ["why"]))
        self.assertEqual((rc, json.loads(out)["ids"], json.loads(out)["all"]), (0, [T], False))
        rc, out, _ = self.run_main(["select", "--json"], select=mock.Mock(side_effect=ValueError("boom")))
        self.assertEqual(rc, 1)
        self.assertIn("boom", json.loads(out)["error"])


class NodeIds(unittest.TestCase):
    def test_a_class_built_inside_a_function_is_addressed_by_its_module_level_name(self):
        self.assertEqual(impact._nodeid("tests.test_r1._review_cases.<locals>.R1_11_ReviewBundle.test_x"),
                         "tests/test_r1.py::R1_11_ReviewBundle::test_x")
        self.assertEqual(impact._nodeid("tests.test_cli.ClaudeBackend.test_y"), "tests/test_cli.py::ClaudeBackend::test_y")
        self.assertIsNone(impact._nodeid("maeng.evidence.x"))


class Dedupe(unittest.TestCase):
    def test_node_ids_under_a_selected_file_are_dropped(self):
        with tempfile.TemporaryDirectory() as d:
            m = Path(d, "map.json")
            m.write_text(json.dumps({"base": "HEAD", "files": {"lib/maeng/evidence.py": {
                "test_count": ["tests/test_evidence.py::Recognition::test_recognized_runners",
                               "tests/test_cli.py::ClaudeBackend::test_codex_backend_stays_selectable"]}}}))
            with mock.patch.object(impact, "MAP", m), mock.patch.object(impact, "_old_text", return_value=(
                    impact.PLUGIN / "lib/maeng/evidence.py").read_text()):
                line = next(i for i, ln in enumerate((impact.PLUGIN / "lib/maeng/evidence.py").read_text().splitlines(), 1)
                            if ln.startswith("def test_count")) + 1
                ids, _ = impact.select(changes={"lib/maeng/evidence.py": {line}, "tests/test_evidence.py": None})
        self.assertIn("tests/test_evidence.py", ids)
        self.assertNotIn("tests/test_evidence.py::Recognition::test_recognized_runners", ids)
        self.assertIn("tests/test_cli.py::ClaudeBackend::test_codex_backend_stays_selectable", ids)


class EventGraph(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        for d in ("lib/maeng", "bin", "hooks", "tests", "schemas", "config"):
            (self.root / d).mkdir(parents=True)
        (self.root / "tests/helpers.py").write_text((impact.TESTS / "helpers.py").read_text())
        (self.root / "hooks/maeng_hooks.py").write_text("from maeng import handlers, state\n")
        (self.root / "bin/maeng-test").write_text("from maeng import state\n")
        for name in ("state", "gates", "evidence", "guard", "interview", "stub", "status", "tree"):
            (self.root / f"lib/maeng/{name}.py").write_text("")
        self.handlers = self.root / "lib/maeng/handlers.py"
        self.handlers.write_text('''from . import state, gates, evidence, guard, interview, stub, status
from . import tree as treelib
DEFAULT = guard.PERSONAL
def shared(p):
    return state.load(p)
def on_session_start(p):
    shared(p)
    return interview.start(p)
def on_prompt(p):
    return interview.prompt(p)
def on_pre(p):
    shared(p)
    return gates.check(p)
def post_helper(p):
    return evidence.mark(p)
def on_post(p, failed=False):
    return post_helper(p)
def on_stop(p):
    return stub.write(p)
def on_subagent_stop(p):
    return status.read(p)
def on_session_end(p):
    return treelib.toplevel(p)
HANDLERS = {
    "SessionStart": on_session_start, "UserPromptSubmit": on_prompt,
    "PreToolUse": on_pre, "PostToolUse": on_post,
    "PostToolUseFailure": lambda p: on_post(p, failed=True),
    "Stop": on_stop, "SubagentStop": on_subagent_stop, "SessionEnd": on_session_end,
}
''')
        for attr, val in (("PLUGIN", self.root), ("TESTS", self.root / "tests")):
            patcher = mock.patch.object(impact, attr, val)
            patcher.start()
            self.addCleanup(patcher.stop)

    def make_source(self, name, body, base="HarnessCase"):
        path = self.root / f"tests/test_{name}.py"
        path.write_text(f"from .helpers import HarnessCase\nclass Case({base}):\n    def test_event(self):\n        {body}\n")
        return f"tests/test_{name}.py"

    def test_every_dispatch_event_retains_its_transitive_edge_and_omits_unrelated_handlers(self):
        expected = {"SessionStart": "interview", "UserPromptSubmit": "interview", "PreToolUse": "gates",
                    "PostToolUse": "evidence", "PostToolUseFailure": "evidence", "Stop": "stub",
                    "SubagentStop": "status", "SessionEnd": "tree"}
        for event in expected:
            self.make_source(event, f'self.hook("{event}", ".")')
        graph = impact.static_graph()
        for event, module in expected.items():
            reach = graph[f"tests/test_{event}.py"]
            self.assertIn(f"lib/maeng/{module}.py", reach, event)
            self.assertIn("lib/maeng/guard.py", reach, event)  # module-level initializer
            self.assertIn("lib/maeng/state.py", reach, event)  # dispatcher error handling
            self.assertIn("lib/maeng/handlers.py", reach, event)
            self.assertIn("hooks/maeng_hooks.py", reach, event)
            self.assertNotIn("lib/maeng/stub.py" if event != "Stop" else "lib/maeng/interview.py", reach, event)

    def test_helper_wrappers_are_resolved_from_their_code_and_cli_only_users_lose_the_dispatcher(self):
        cases = {"pre": ('self.pre(".", "Bash", {})', {"gates"}),
                 "bash": ('self.bash_pre(".", "true")', {"gates"}),
                 "start": ('self.start(".")', {"interview"}),
                 "check": ('self.run_check(".")', {"gates", "evidence"}),
                 "check_none": ('self.run_check(".", between=None)', {"gates", "evidence"}),
                 "verify": ('self.verify_tree(".")', {"gates", "evidence"}),
                 "cli": ('self.cli("maeng-test", [], ".")', set())}
        for name, (body, _) in cases.items():
            self.make_source(name, body)
        graph = impact.static_graph()
        for name, (_, modules) in cases.items():
            reached = graph[f"tests/test_{name}.py"]
            self.assertEqual({m for m in ("gates", "evidence", "interview", "stub")
                              if f"lib/maeng/{m}.py" in reached}, modules)
            self.assertEqual("hooks/maeng_hooks.py" in reached, bool(modules))
            self.assertIn("lib/maeng/state.py", reached)
        helper = self.root / "tests/helpers.py"
        helper.write_text(helper.read_text().replace("    def setUp(self):", '    def setUp(self):\n        self.hook("Stop", ".")'))
        self.assertIn("lib/maeng/stub.py", impact.static_graph()["tests/test_cli.py"])
        helper.write_text("not valid python !")
        self.assertIn("lib/maeng/stub.py", impact.static_graph()["tests/test_pre.py"])

    def test_sibling_fixture_imports_inherit_reach_transitively(self):
        fixture = self.root / "tests/test_z_fixture.py"
        fixture.write_text('from .helpers import HarnessCase\nclass Fixture(HarnessCase):\n'
                           '    def setUp(self):\n        self.start(".")\n')
        cases = [("from . import test_z_fixture as fixture", "fixture.Fixture"),
                 ("from .test_z_fixture import Fixture", "Fixture"),
                 ("from tests.test_z_fixture import Fixture", "Fixture"),
                 ("import tests.test_z_fixture", "tests.test_z_fixture.Fixture"),
                 ("from .test_import0 import Case", "Case")]
        for i, (statement, base) in enumerate(cases):
            (self.root / f"tests/test_import{i}.py").write_text(f"{statement}\nclass Case({base}):\n    pass\n")
        graph = impact.static_graph()
        for i in range(len(cases)):
            reach = graph[f"tests/test_import{i}.py"]
            self.assertEqual(reach, graph["tests/test_z_fixture.py"])
            self.assertIn("hooks/maeng_hooks.py", reach)
            self.assertIn("lib/maeng/handlers.py", reach)
            self.assertIn("lib/maeng/interview.py", reach)
            self.assertNotIn("lib/maeng/gates.py", reach)

    def test_sibling_import_cycles_propagate_reach(self):
        for name, source in {"a": "from . import test_b\n", "b": "from .test_c import Case\n",
                             "c": 'from . import test_a\nclass Case:\n    def setUp(self):\n        self.start(".")\n',
                             "unrelated": "pass\n"}.items():
            (self.root / f"tests/test_{name}.py").write_text(source)
        graph = impact.static_graph()
        for name in ("a", "b", "c"):
            self.assertIn("hooks/maeng_hooks.py", graph[f"tests/test_{name}.py"])
            self.assertIn("lib/maeng/handlers.py", graph[f"tests/test_{name}.py"])
        self.assertEqual(graph["tests/test_unrelated.py"], set())

    def test_unparseable_test_keeps_full_hook_closure_for_importers(self):
        (self.root / "tests/test_broken.py").write_text("not valid python !")
        (self.root / "tests/test_inherited.py").write_text("from .test_broken import Fixture\n")
        graph = impact.static_graph()
        for name in ("broken", "inherited"):
            reach = graph[f"tests/test_{name}.py"]
            for source in ("hooks/maeng_hooks.py", "lib/maeng/handlers.py", "lib/maeng/gates.py",
                           "lib/maeng/interview.py", "lib/maeng/stub.py"):
                self.assertIn(source, reach)

    def test_unknown_dynamic_aliases_raw_input_and_inherited_tests_keep_full_closure(self):
        known = self.make_source("known", 'self.hook("Stop", ".")')
        bodies = ['self.hook(event, ".")', 'self.hook("FutureEvent", ".")', 'self.run_hook_text(raw)',
                  'getattr(self, name)("Stop", ".")', 'runner = self.hook; runner("Stop", ".")',
                  'self.custom_driver()', 'self.hook(*args)', 'call_hook(self.env, raw)',
                  'self.hook("Stop", ".", hook_event_name="PreToolUse")', 'self.hook("Stop", ".", **fields)',
                  'self.pre(".", "Bash", {}, hook_event_name="Stop")', 'self.pre(".", "Bash", {}, **fields)',
                  'helpers.call_hook(self.env, raw)', 'helpers.HOOK', 'owner = self; owner.start(".")', 'drive(self)']
        bodies += ['self.run_check(".", between=callback)', 'self.run_check(".", "pytest", True, callback)',
                   'self.run_check(*args)', 'self.cli(name, [], ".")', 'self.cli("maeng-missing", [], ".")',
                   'helpers.call_cli(name, [], ".", self.env)', 'self.cli("maeng-" "test", [], ".")']
        unknown = [self.make_source(f"unknown{i}", body) for i, body in enumerate(bodies)]
        unknown.append(self.make_source("inherited", "pass", base="ImportedCase"))
        unknown.append(self.make_source("metaclass", "pass", base="HarnessCase, metaclass=Factory"))
        override = self.make_source("override", 'self.hook("Stop", ".")')
        target = self.root / override
        target.write_text(target.read_text() + '    def hook(self, *args):\n        self.pre(".", "Bash", {})\n')
        unknown.append(override)
        for i, prefix in enumerate(("from .support import drive", "from . import support",
                                    "from .support import decorate")):
            body = "drive()" if i == 0 else "support.drive()" if i == 1 else 'self.hook("Stop", ".")'
            path = self.make_source(f"external{i}", body)
            target = self.root / path
            text = target.read_text()
            if i == 2:
                text = text.replace("    def test_event", "    @decorate\n    def test_event")
            target.write_text(prefix + "\n" + text)
            unknown.append(path)
        unknown.append(self.make_source("receiver", "callback.run()"))
        unknown.append(self.make_source("free", "drive()"))
        path = self.make_source("shadow", "driver()")
        target = self.root / path
        target.write_text("from json import loads as driver\nfrom .support import drive as driver\n" + target.read_text())
        unknown.append(path)
        path = self.make_source("callback_value", "list(map(driver, []))")
        target = self.root / path
        target.write_text("from .support import drive as driver\n" + target.read_text())
        unknown.append(path)
        path = self.make_source("callback_arg", "list(map(driver, []))")
        target = self.root / path
        target.write_text(target.read_text().replace("def test_event(self)", "def test_event(self, driver)"))
        unknown.append(path)
        path = self.make_source("external_base", "pass")
        target = self.root / path
        target.write_text(target.read_text().replace("from .helpers import HarnessCase", "from .support import HarnessCase"))
        unknown.append(path)
        path = self.make_source("shadow_base", "pass")
        target = self.root / path
        target.write_text(target.read_text().replace("from .helpers import HarnessCase", "from .helpers import HarnessCase\nfrom .support import HarnessCase"))
        unknown.append(path)
        for i, (prefix, body) in enumerate((("import subprocess", 'subprocess.run(command)'),
                ("from runpy import run_path", 'run_path(path)'),
                ("import importlib", 'importlib.import_module(name).main()'),
                ("import os", 'os.system(command)'), ("", '__import__(name).main()'))):
            path = self.make_source(f"execution{i}", body)
            target = self.root / path
            target.write_text(prefix + "\n" + target.read_text())
            unknown.append(path)
        graph = impact.static_graph()
        self.assertNotIn("lib/maeng/gates.py", graph[known])
        for path in unknown:
            self.assertIn("lib/maeng/gates.py", graph[path], path)
            self.assertIn("lib/maeng/interview.py", graph[path], path)
        helper = self.root / "tests/helpers.py"
        original = helper.read_text()
        helper.write_text(original.replace("    def pre(", "    @decorate\n    def pre("))
        path = self.make_source("decorated_helper", 'self.pre(".", "Bash", {})')
        self.assertIn("lib/maeng/interview.py", impact.static_graph()[path])
        for definition in ("    @decorate\n    def setUp(self):", "    def setUp(self):\n        drive()",
                           "    def setUp(self):\n        from .support import driver\n        driver.run()",
                           "    def setUp(self):\n        from .support import driver\n        list(map(driver, []))"):
            helper.write_text(original.replace("    def setUp(self):", definition))
            self.assertIn("lib/maeng/interview.py", impact.static_graph()[path])

    def test_dynamic_handler_dispatch_retains_the_full_closure(self):
        path = self.make_source("stop", 'self.hook("Stop", ".")')
        self.assertNotIn("lib/maeng/gates.py", impact.static_graph()[path])
        original = self.handlers.read_text()
        for call in ('globals()[p](p)', 'callback(p)', 'getattr(p, "run")()', 'p.callback()'):
            self.handlers.write_text(original.replace("return stub.write(p)", "return " + call))
            self.assertIn("lib/maeng/gates.py", impact.static_graph()[path])
        self.handlers.write_text(original.replace("return stub.write(p)", "from . import gates\n    return gates.check(p)"))
        self.assertIn("lib/maeng/gates.py", impact.static_graph()[path])
        self.handlers.write_text(original.replace("def on_stop(p):", "@decorate\ndef on_stop(p):"))
        self.assertIn("lib/maeng/gates.py", impact.static_graph()[path])
        for bad in (original.replace('"Stop": on_stop', '"Stop": factory()'), "not valid python !",
                    original.replace("from . import state", "from . import *\nfrom . import state"),
                    original.replace("DEFAULT = guard.PERSONAL", "A, B = guard.PERSONAL"),
                    original.replace("HANDLERS = {", "HANDLERS = factory({").replace('\n}\n', '\n})\n'),
                    "import maeng.gates\nimport maeng.state\n" + original.replace("return stub.write(p)", "return maeng.gates.check(p)"),
                    "from . import gates as driver\nfrom . import state as driver\n" + original,
                    "import maeng.gates\n" + original.replace("return stub.write(p)", "return maeng.gates.check(p)")):
            self.handlers.write_text(bad)
            self.assertIn("lib/maeng/gates.py", impact.static_graph()[path])

    def test_module_changes_keep_the_event_and_process_boundary_but_drop_unrelated_events(self):
        pre = self.make_source("pre", 'self.hook("PreToolUse", ".")')
        stop = self.make_source("stop", 'self.hook("Stop", ".")')
        (self.root / impact.BOUNDARY).write_text("# inherited process scenarios\n")
        with mock.patch.object(impact, "load_map", return_value=({"files": {}}, None)), \
                mock.patch.object(impact, "boundary_twins", return_value=set()):
            selected, _ = impact.select(changes={"lib/maeng/gates.py": None})
            self.assertEqual(selected, sorted([pre, impact.BOUNDARY]))
            selected, _ = impact.select(changes={"hooks/maeng_hooks.py": None})
            self.assertEqual(selected, sorted([pre, stop, impact.BOUNDARY]))
        with mock.patch.object(impact, "PLUGIN", Path(__file__).resolve().parents[1]):
            self.assertIn("tests/test_boundary.py::SlimGateProc::test_feature_pushes_gh_env_and_eta_paths_are_allowed",
                          impact.boundary_twins({"tests/test_g1.py::SlimGate::test_feature_pushes_gh_env_and_eta_paths_are_allowed"}))
