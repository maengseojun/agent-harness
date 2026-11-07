"""plugin_checks.py on a temporary root with fake lanes.json and fake suite scripts."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "tools" / "testperf" / "plugin_checks.py"
spec = importlib.util.spec_from_file_location("plugin_checks", SCRIPT)
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)

D = "plugins/p/tests"


def suite(id, script, covers=(D,), required=True, deps=(), pip=(), reason=None):
    s = {"id": id, "cwd": ".", "command": [sys.executable, script], "covers": list(covers), "required": required,
         "deps": list(deps), "pip": list(pip)}
    if reason:
        s["reason"] = reason
    return s


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / D).mkdir(parents=True)
        (self.root / D / "test_a.py").write_text("")

    def script(self, name, out="", rc=0):
        (self.root / name).write_text("import sys\nprint(%r)\nsys.exit(%d)\n" % (out, rc))
        return name

    def run_checks(self, gate, periodic=(), *args, env=None):
        lanes = self.root / "lanes.json"
        lanes.write_text(json.dumps({"version": 1, "lanes": {"gate": gate, "periodic": list(periodic)}}))
        out = self.root / "out.json"
        e = dict(os.environ, **(env or {}))
        e.pop("GITHUB_STEP_SUMMARY", None)
        p = subprocess.run([sys.executable, str(SCRIPT), "--lane", "gate", "--root", str(self.root), "--lanes",
                            str(lanes), "--json", str(out), *args], capture_output=True, text=True, env=e)
        return p, json.loads(out.read_text()) if out.exists() else None


class Parity(Base):
    def test_directory_without_lane_fails(self):
        (self.root / "plugins/q/tests").mkdir(parents=True)
        (self.root / "plugins/q/tests/test_b.py").write_text("")
        ok = self.script("ok.py", "1 passed in 0.1s")
        p, data = self.run_checks([suite("a", ok)])
        self.assertEqual(p.returncode, 1)
        self.assertFalse(data["aggregate_ok"])
        self.assertEqual(data["parity"]["missing_lane"], ["plugins/q/tests"])
        self.assertEqual(data["suites"][0]["status"], "ok")

    def test_excluded_directories_are_not_discovered(self):
        for d in ("plugins/p/archive", "plugins/p/node_modules/x", "plugins/p/.claude"):
            (self.root / d).mkdir(parents=True)
            (self.root / d / "test_z.py").write_text("")
        self.assertEqual(pc.discover(self.root), {D})

    def test_covers_entry_that_does_not_exist_fails(self):
        ok = self.script("ok.py", "1 passed in 0.1s")
        p, data = self.run_checks([suite("a", ok, covers=[D, "plugins/gone/tests"])])
        self.assertEqual(p.returncode, 1)
        self.assertEqual(data["parity"]["nonexistent"], ["plugins/gone/tests"])

    def test_periodic_covers_count_toward_parity(self):
        ok = self.script("ok.py", "1 passed in 0.1s")
        p, data = self.run_checks([suite("a", ok, covers=[])], [suite("m", ok, covers=[D], required=False)])
        self.assertTrue(data["parity"]["ok"])

    def test_real_inventory_matches_real_repository(self):
        lanes = json.loads((REPO / "plugins/maeng-harness/tests/lanes.json").read_text())["lanes"]
        par = pc.parity(REPO, lanes)
        self.assertTrue(par["ok"], par)
        self.assertIn("plugins/maeng-harness/tests", {c for s in lanes["gate"] for c in s["covers"]})
        self.assertEqual([s["id"] for s in lanes["periodic"]], ["mutation-sample"])
        self.assertFalse(lanes["periodic"][0]["required"])


class Results(Base):
    def test_ok_suite_passes(self):
        p, data = self.run_checks([suite("a", self.script("ok.py", "3 passed in 0.1s"))])
        self.assertEqual(p.returncode, 0)
        self.assertTrue(data["aggregate_ok"])
        self.assertEqual((data["suites"][0]["status"], data["suites"][0]["tests_run"]), ("ok", 3))

    def test_failed_required_suite_fails_aggregate(self):
        p, data = self.run_checks([suite("a", self.script("bad.py", "1 failed, 2 passed in 0.1s", rc=1))])
        self.assertEqual(p.returncode, 1)
        self.assertFalse(data["aggregate_ok"])
        self.assertEqual(data["suites"][0]["status"], "failed")
        self.assertEqual(data["suites"][0]["rc"], 1)
        self.assertIn("1 failed", data["suites"][0]["output_tail"])

    def test_zero_tests_with_rc_zero_is_empty(self):
        for name, out in (("pytest", "collected 0 items\n\nno tests ran in 0.01s"),
                          ("unittest", "Ran 0 tests in 0.000s\n\nNO TESTS RAN")):
            with self.subTest(name):
                p, data = self.run_checks([suite("a", self.script(name + ".py", out))])
                self.assertEqual(p.returncode, 1)
                self.assertEqual(data["suites"][0]["status"], "empty")
                self.assertFalse(data["aggregate_ok"])

    def test_missing_command_is_missing_and_fails(self):
        s = suite("a", "x.py")
        s["command"] = ["/nonexistent/binary"]
        p, data = self.run_checks([s])
        self.assertEqual(data["suites"][0]["status"], "missing")
        self.assertEqual(p.returncode, 1)

    def test_timeout(self):
        (self.root / "slow.py").write_text("import time\ntime.sleep(30)\n")
        p, data = self.run_checks([suite("a", "slow.py")], (), "--timeout", "1")
        self.assertEqual(data["suites"][0]["status"], "timeout")
        self.assertEqual(p.returncode, 1)


class Deps(Base):
    MISSING = "no_such_module_for_plugin_checks"

    def test_required_suite_with_missing_dep_is_unavailable(self):
        ok = self.script("ok.py", "1 passed in 0.1s")
        p, data = self.run_checks([suite("a", ok, deps=[self.MISSING])])
        self.assertEqual(data["suites"][0]["status"], "unavailable")
        self.assertEqual(p.returncode, 1)

    def test_optional_suite_with_missing_dep_is_skipped_and_passes(self):
        ok = self.script("ok.py", "1 passed in 0.1s")
        p, data = self.run_checks([suite("a", ok, required=False, deps=[self.MISSING], reason="needs a thing")])
        self.assertEqual(data["suites"][0]["status"], "skipped")
        self.assertIn("needs a thing", data["suites"][0]["output_tail"])
        self.assertEqual(p.returncode, 0)
        self.assertTrue(data["aggregate_ok"])

    def test_require_complete_turns_a_skip_into_failure(self):
        ok = self.script("ok.py", "1 passed in 0.1s")
        p, data = self.run_checks([suite("a", ok, required=False, deps=[self.MISSING], reason="r")], (),
                                  "--require-complete")
        self.assertEqual(p.returncode, 1)
        self.assertFalse(data["aggregate_ok"])
        self.assertTrue(data["require_complete"])

    def test_print_pip_is_the_sorted_union_of_the_lane(self):
        ok = self.script("ok.py")
        lanes = self.root / "lanes.json"
        lanes.write_text(json.dumps({"version": 1, "lanes": {
            "gate": [suite("a", ok, pip=["zeta", "alpha"]), suite("b", ok, pip=["alpha", "mid"])],
            "periodic": [suite("m", ok, pip=["mutmut"])]}}))
        p = subprocess.run([sys.executable, str(SCRIPT), "--lane", "gate", "--lanes", str(lanes), "--root",
                            str(self.root), "--print-pip"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout.split(), ["alpha", "mid", "zeta"])


class Isolation(Base):
    DUMP = "import json, os\nprint(json.dumps(dict(os.environ)))\n"

    def dump(self, *args):
        (self.root / "env.py").write_text(self.DUMP)
        parent = {"OPENAI_API_KEY": "sk-parent", "ANTHROPIC_API_KEY": "sk-parent", "MAENG_HOME": "/parent/maeng"}
        p, data = self.run_checks([suite("a", "env.py")], (), *args, env=parent)
        line = [ln for ln in data["suites"][0]["output_tail"].splitlines() if ln.startswith("{")][0]
        return json.loads(line), data

    def test_isolated_child_sees_only_the_minimal_environment(self):
        env, data = self.dump("--isolated")
        self.assertTrue(data["isolated"])
        for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "MAENG_HOME"):
            self.assertNotIn(k, env)
        self.assertTrue(env["PATH"])
        tmp = env["HOME"]
        self.assertNotEqual(tmp, str(Path.home()))
        self.assertTrue(env["TMPDIR"].startswith(tmp) and env["XDG_CONFIG_HOME"].startswith(tmp))
        self.assertTrue(env["GIT_CONFIG_GLOBAL"].startswith(tmp))
        self.assertEqual(env["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(env["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertEqual(env["LC_ALL"], "C.UTF-8")
        self.assertTrue(env["GIT_AUTHOR_EMAIL"] and env["GIT_COMMITTER_NAME"])
        self.assertFalse(Path(tmp).exists(), "the temporary home is removed after the suite")

    def test_without_isolated_the_parent_environment_passes_through(self):
        env, _ = self.dump()
        self.assertEqual(env["OPENAI_API_KEY"], "sk-parent")


class Parsing(unittest.TestCase):
    def test_pytest_summaries(self):
        self.assertEqual(pc.tests_run("....\n===== 5 passed, 1 skipped, 2 warnings in 1.2s ====="), 5)
        self.assertEqual(pc.tests_run("3 failed, 4 passed, 1 error, 2 xfailed, 1 xpassed in 0.5s"), 11)
        self.assertEqual(pc.tests_run("12 passed in 0.06s"), 12)
        self.assertEqual(pc.tests_run("no tests ran in 0.01s"), 0)

    def test_unittest_summaries(self):
        self.assertEqual(pc.tests_run("Ran 28 tests in 0.069s\n\nOK"), 28)
        self.assertEqual(pc.tests_run("Ran 10 tests in 0.1s\n\nOK (skipped=3)"), 7)
        self.assertEqual(pc.tests_run("Ran 10 tests in 0.1s\n\nFAILED (failures=1, skipped=2)"), 8)
        self.assertEqual(pc.tests_run("Ran 1 test in 0.1s\n\nOK"), 1)

    def test_unparseable_is_none(self):
        self.assertIsNone(pc.tests_run("something else entirely"))


class Summary(Base):
    def test_step_summary_is_appended_when_set(self):
        f = self.root / "summary.md"
        p, _ = self.run_checks([suite("a", self.script("ok.py", "2 passed in 0.1s"))], (),
                               env={"GITHUB_STEP_SUMMARY": str(f)})
        # run_checks drops the variable; run once more directly
        lanes = self.root / "lanes.json"
        subprocess.run([sys.executable, str(SCRIPT), "--lane", "gate", "--root", str(self.root), "--lanes",
                        str(lanes)], capture_output=True, env=dict(os.environ, GITHUB_STEP_SUMMARY=str(f)))
        self.assertIn("| a | ok |", f.read_text())


if __name__ == "__main__":
    unittest.main()
