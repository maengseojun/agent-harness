"""MAE-320: each decided Decisions use runs because the harness makes it run."""
import json
import os
import stat
import sys
import time

from maeng import recordcheck, state
from .helpers import HarnessCase
from .test_cli import ReviewRunFixture, load_bin

LINEAR = "mcp__linear-maeng__save_issue"
NOTION = "mcp__notion-maeng__notion-create-pages"
NOTE = "mcp__obsidian_vault__write_note"


class On:
    def checks_on(self):
        self.env.pop("MAENG_DECISIONS", None)
        os.environ.pop("MAENG_DECISIONS", None)


class DuplicateGate(On, HarnessCase):
    def setUp(self):
        super().setUp()
        self.checks_on()
        self.repo = self.make_repo()
        self.start(self.repo)

    def ran(self, command, ok=True):
        self.hook("PostToolUse" if ok else "PostToolUseFailure", self.repo, tool_name="Bash",
                  tool_input={"command": command}, tool_use_id="tu-1", tool_response={"stdout": "", "stderr": ""})

    def test_every_new_record_is_denied_until_the_check_ran(self):
        for tool, tin in ((LINEAR, {"team": "MAE", "title": "x"}), (NOTION, {"pages": []}),
                          (NOTE, {"path": "wiki/notes/NOTE-new.md", "content": "x"}),
                          ("Write", {"file_path": str(self.vault / "wiki/notes/NOTE-new.md"), "content": "x"})):
            denied, why = self.pre(self.repo, tool, tin)
            self.assertTrue(denied, tool)
            self.assertIn("records.py duplicate", why)
        self.ran("python3 /x/scripts/records.py duplicate --new t --candidates c.json")
        for tool, tin in ((LINEAR, {"team": "MAE", "title": "x"}), (NOTION, {"pages": []}),
                          (NOTE, {"path": "wiki/notes/NOTE-new.md", "content": "x"})):
            self.assertFalse(self.pre(self.repo, tool, tin)[0], tool)

    def test_updates_overwrites_and_machine_notes_pass(self):
        (self.vault / "wiki/notes").mkdir(parents=True)
        (self.vault / "wiki/notes/NOTE-old.md").write_text("x")
        for tool, tin in ((LINEAR, {"id": "MAE-1", "title": "x"}), (NOTE, {"path": "wiki/notes/NOTE-old.md"}),
                          (NOTE, {"path": "wiki/sessions/SESSION-1.md"}), (NOTE, {"path": "wiki/reviews/REV-1.md"}),
                          ("Write", {"file_path": str(self.repo / "new.md")})):
            self.assertFalse(self.pre(self.repo, tool, tin)[0], tin)

    def test_a_failed_run_or_a_mention_does_not_count(self):
        self.ran("python3 records.py duplicate --new t --candidates c.json", ok=False)
        self.ran("cat records.py")
        self.ran("echo 'python3 records.py duplicate --new t --candidates c.json'")
        self.ran("grep -n 'records.py duplicate' SKILL.md")
        self.ran("python3 records.py related --task t --candidates c.json")
        self.assertTrue(self.pre(self.repo, LINEAR, {"team": "MAE", "title": "x"})[0])

    def test_real_invocations_count(self):
        for command in ("cd /x && python3 /y/scripts/records.py duplicate --new t --candidates c.json",
                        'python3 "$D/records.py" duplicate --new t --candidates=c.json',
                        "D=/y; python3 $D/records.py duplicate --new t --candidates c.json",
                        "python3.12 records.py duplicate --new t --candidates c.json"):
            self.assertEqual(recordcheck.ran(command), ["duplicate"], command)
        self.assertEqual(recordcheck.ran("python3 records.py cleanup --candidates c.json"), [])
        self.assertEqual(recordcheck.ran("python3 records.py 'unclosed"), [])

    def test_one_call_can_run_both_checks(self):
        command = "python3 records.py related --task t --candidates c.json && python3 records.py duplicate --new t " \
                  "--candidates c.json"
        self.assertEqual(recordcheck.ran(command), ["related", "duplicate"])
        self.ran(command)
        self.assertFalse(self.pre(self.repo, LINEAR, {"team": "MAE", "title": "x"})[0])
        self.assertEqual(recordcheck.ran(command.replace(" && ", "; ")), ["duplicate"])  # only the last status is known

    def test_a_background_launch_does_not_count(self):
        self.hook("PostToolUse", self.repo, tool_name="Bash", tool_use_id="tu-1", tool_response={"stdout": ""},
                  tool_input={"command": "python3 records.py duplicate --new t --candidates c.json",
                              "run_in_background": True})
        self.assertTrue(self.pre(self.repo, LINEAR, {"team": "MAE", "title": "x"})[0])

    def test_a_step_that_may_have_been_skipped_does_not_count(self):
        for command in ("test -f cached.json || python3 records.py related --task t --candidates c.json",
                        "python3 records.py related --task t --candidates c.json || true",
                        "python3 records.py related --task t --candidates c.json &",
                        "false && python3 records.py related --task t --candidates c.json; echo ok",
                        "python3 records.py related --help",
                        "python3 records.py related --task t --candidates c.json -h",
                        "python3 records.py related --task t",
                        "python3 /missing/records.py related --task t --candidates c.json; echo done",
                        "python3 /missing/records.py related --task t --candidates c.json\necho done",
                        "python3 /missing/records.py related --task t --candidates c.json | tail -3",
                        "echo $(python3 /missing/records.py related --task t --candidates c.json)",
                        "echo `python3 /missing/records.py related --task t --candidates c.json`"):
            self.assertEqual(recordcheck.ran(command), [], command)

    def test_the_check_expires(self):
        self.ran("python3 records.py duplicate --new t --candidates c.json")
        state.update(self.sid, lambda st: st["records_checks"].update(duplicate=time.time() - recordcheck.WINDOW - 1),
                     str(self.repo))
        self.assertTrue(self.pre(self.repo, LINEAR, {"team": "MAE", "title": "x"})[0])

    def test_a_malformed_call_never_breaks_the_hook(self):
        rc, _, _ = self.hook("PostToolUse", self.repo, tool_name="Bash", tool_input="x", tool_use_id="tu-1")
        self.assertEqual(rc, 0)

    def test_off_allows_everything(self):
        self.env["MAENG_DECISIONS"] = "off"
        os.environ["MAENG_DECISIONS"] = "off"
        self.assertFalse(self.pre(self.repo, LINEAR, {"team": "MAE", "title": "x"})[0])

    def test_the_eta_world_has_the_gate_too(self):
        eta = self.make_repo("eta_v1")
        denied, _ = self.pre(eta, "mcp__linear-eta__save_issue", {"team": "E", "title": "x"})
        self.assertTrue(denied)
        self.hook("PostToolUse", eta, tool_name="Bash", tool_use_id="tu-2", tool_response={"stdout": ""},
                  tool_input={"command": "python3 records.py duplicate --new t --candidates c.json"})
        self.assertFalse(self.pre(eta, "mcp__linear-eta__save_issue", {"team": "E", "title": "x"})[0])


class BindGate(On, HarnessCase):
    def setUp(self):
        super().setUp()
        self.checks_on()
        self.repo = self.make_repo()
        self.start(self.repo)

    def test_bind_refuses_until_the_related_check_ran(self):
        proc = self.cli("maeng-verify", ["bind", "MAE-1"], self.repo)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("records.py", proc.stderr + proc.stdout)
        self.hook("PostToolUse", self.repo, tool_name="Bash", tool_use_id="tu-1", tool_response={"stdout": ""},
                  tool_input={"command": "python3 records.py related --task t --candidates c.json"})
        self.assertEqual(self.cli("maeng-verify", ["bind", "MAE-1"], self.repo).returncode, 0)

    def test_off_binds(self):
        self.assertEqual(self.cli("maeng-verify", ["bind", "MAE-1"], self.repo,
                                  extra_env={"MAENG_DECISIONS": "off"}).returncode, 0)


class ReviewWiring(On, ReviewRunFixture):
    def setUp(self):
        super().setUp()
        self.checks_on()
        self.calls = self.tmp / "preflight.log"
        self.fake = self.tmp / "preflight.py"
        self.fake.write_text(f"import json, sys\nopen({str(self.calls)!r}, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
                             f"print('TABLE'); sys.exit(0)\n")
        self.fake.chmod(self.fake.stat().st_mode | stat.S_IEXEC)
        self.ev = self.tmp / "ev.txt"
        self.ev.write_text("1 passed\n")

    def run_review(self, script=None):
        env = {"MAENG_CODEX": str(self.codex), "MAENG_PREFLIGHT": str(script or self.fake)}
        return self.cli("maeng-review", ["run", "--kind", "code", "--pr", "7", "--base", self.base, "--head", self.h,
                                         "--base-ref", "main", "--evidence", str(self.ev)], self.repo, extra_env=env)

    def logged(self):
        return [json.loads(x) for x in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def test_a_passing_review_runs_the_preflight_once(self):
        proc = self.run_review()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual([c[0] for c in self.logged()], ["ac"])
        self.assertIn("TABLE", proc.stderr)
        self.assertNotIn("TABLE", proc.stdout)
        self.assertNotIn("TABLE", self.stdin_log.read_text())  # the reviewer stays unanchored

    def test_a_failed_round_runs_the_triage_with_earlier_rounds(self):
        self.result.write_text(json.dumps({"verdict": "fail", "findings": [
            {"severity": "high", "title": "t", "body": "b", "file": None, "line": None}]}))
        self.assertEqual(self.run_review().returncode, 1)
        self.result.write_text(json.dumps({"verdict": "fail", "findings": [
            {"severity": "high", "title": "t2", "body": "b", "file": None, "line": None}]}))
        self.run_review()
        calls = self.logged()
        self.assertEqual([c[0] for c in calls], ["ac", "triage", "ac", "triage"])
        self.assertNotIn("--previous", calls[1])
        self.assertIn("--previous", calls[3])

    def test_a_broken_preflight_never_stops_the_review(self):
        bad = self.tmp / "bad.py"
        bad.write_text("raise SystemExit(3)\n")
        proc = self.run_review(bad)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("failed with exit code 3", proc.stderr)
        self.assertEqual(self.run_review(self.tmp / "gone.py").returncode, 0)

    def test_a_review_without_evidence_is_blocked_before_the_reviewer(self):
        proc = self.cli("maeng-review", ["run", "--kind", "code", "--pr", "7", "--base", self.base, "--head", self.h,
                                         "--base-ref", "main"], self.repo,
                        extra_env={"MAENG_CODEX": str(self.codex), "MAENG_PREFLIGHT": str(self.fake)})
        self.assertEqual(proc.returncode, 2)
        self.assertIn("pre-flight inputs", proc.stdout)
        self.assertEqual(self.logged(), [])
        self.assertFalse(self.stdin_log.exists())

    def test_off_skips_it(self):
        self.env["MAENG_DECISIONS"] = "off"
        self.run_review()
        self.assertEqual(self.logged(), [])

    def test_a_research_review_needs_the_claim_check(self):
        draft = self.tmp / "d.md"
        draft.write_text("draft\n")
        env = {"MAENG_CODEX": str(self.codex)}
        args = ["run", "--kind", "research", "--draft", str(draft)]
        proc = self.cli("maeng-review", args, self.repo, extra_env=env)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("claim check", proc.stdout)
        claims = self.tmp / "claims.json"
        for bad in ('{"results": []}', "", "not json", "[]", '{"results": true}', '{"results": "error"}',
                    '{"results": [1]}', '{"results": [{"id": "c1"}]}'):
            claims.write_text(bad)
            proc = self.cli("maeng-review", [*args, "--claims", str(claims)], self.repo, extra_env=env)
            self.assertEqual(proc.returncode, 2, bad)
        proc = self.cli("maeng-review", [*args, "--claims", str(self.tmp / "gone.json")], self.repo, extra_env=env)
        self.assertEqual(proc.returncode, 2)
        claims.write_text('{"results": [{"id": "c1", "verdict": "supported"}]}')
        proc = self.cli("maeng-review", [*args, "--claims", str(claims)], self.repo, extra_env=env)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("supported", self.stdin_log.read_text())


class Locate(HarnessCase):
    def test_the_highest_cached_version_wins(self):
        mod = load_bin("maeng-review")
        cache = self.tmp / "cache/maeng"
        harness = cache / "maeng-harness/0.4.11/bin"
        harness.mkdir(parents=True)
        for v in ("0.3.9", "0.3.19"):
            s = cache / "maeng-tools" / v / "skills/decisions/scripts"
            s.mkdir(parents=True)
            (s / "preflight.py").write_text("")
        real = mod.__file__
        mod.__file__ = str(harness / "maeng-review")
        self.addCleanup(setattr, mod, "__file__", real)
        self.assertIn("/0.3.19/", str(mod.preflight_script()))
