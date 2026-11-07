"""MAE-242: task status file for dots, review round cap, `maeng/review` commit status."""
import json
import os
import stat
import sys
from unittest import mock

from maeng import status
from .helpers import HarnessCase


class StatusBase(HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.sdir = self.home / "Documents/maeng-harness/status"

    def task(self, tid):
        return json.loads((self.sdir / f"{tid}.json").read_text())

    def stop(self, message="", active=False):
        return self.hook("Stop", self.repo, stop_hook_active=active, last_assistant_message=message)


class StatusFile(StatusBase):
    def test_first_prompt_acks_intake_with_session_and_manifest(self):
        self.hook("SessionStart", self.repo, source="startup")
        self.hook("UserPromptSubmit", self.repo, prompt="task_id: dots-17\nfix the filter")
        rec = self.task("dots-17")
        self.assertEqual((rec["state"], rec["session_id"], rec["cwd"]), ("running", self.sid, str(self.repo)))
        self.assertFalse(rec["needs_user_input"])
        manifest = json.loads((self.sdir / "manifest.json").read_text())
        self.assertEqual(manifest["dots-17"]["session_id"], self.sid)

    def test_env_task_id_wins_and_default_is_per_session(self):
        self.env["MAENG_TASK_ID"] = "from-env"
        self.start(self.repo)
        self.assertEqual(self.task("from-env")["state"], "running")
        with mock.patch.dict(os.environ, {"MAENG_TASK_ID": "from-env"}):
            self.assertEqual(status.task_id_for("ab", "task_id: line"), "from-env")
        self.assertEqual(status.task_id_for("ab-cd-ef-gh-ij", "no marker"), "s-abcdefgh")

    def test_stop_marker_lines_set_state(self):
        self.start(self.repo)
        tid = "s-" + self.sid.replace("-", "")[:8]
        self.stop("Did it.\nresult: filter keeps its page")
        rec = self.task(tid)
        self.assertEqual((rec["state"], rec["result_summary"]), ("done", "filter keeps its page"))
        self.stop("needs input: pick A or B")
        rec = self.task(tid)
        self.assertEqual((rec["state"], rec["next_action"], rec["needs_user_input"]), ("needs_input", "pick A or B", True))
        self.stop("just chatting")
        self.assertEqual(self.task(tid)["state"], "idle")
        self.hook("SessionEnd", self.repo)
        self.assertEqual(self.task(tid)["state"], "ended")

    def test_unverified_change_finishes_not_running_and_pass_names_verified_head(self):
        self.start(self.repo)
        tid = "s-" + self.sid.replace("-", "")[:8]
        (self.repo / "app.py").write_text("print('x')\n")
        self.hook("PostToolUse", self.repo, tool_name="Edit", tool_input={"file_path": str(self.repo / "app.py")},
                  tool_response={})
        self.assertEqual(self.task(tid)["state"], "running")
        for active in (False, True):  # a finished turn is never left running or forced blocked by the gap
            self.stop("result: done", active=active)
            rec = self.task(tid)
            self.assertEqual((rec["state"], rec["verify_state"], rec["blocker"]), ("done", "not_run", None))
        self.stop("no marker line here")
        self.assertEqual((self.task(tid)["state"], self.task(tid)["verify_state"]), ("idle", "not_run"))
        self.hook("SessionEnd", self.repo)
        self.assertEqual((self.task(tid)["state"], self.task(tid)["verify_state"]), ("ended", "not_run"))
        head = self.commit_all(self.repo)
        self.run_check(self.repo, "pytest -q")
        self.hook("PostToolUse", self.repo, tool_name="mcp__claude_ai_Linear__save_comment",
                  tool_input={"issueId": "MAE-1", "body": "p"}, tool_response={"id": "c"}, tool_use_id="r")
        self.stop("result: done")
        rec = self.task(tid)
        self.assertEqual((rec["state"], rec["verify_state"], rec["verified_head_sha"]), ("done", "pass", head))

    def test_second_session_on_a_running_task_is_warned(self):
        self.hook("SessionStart", self.repo, source="startup")
        self.hook("UserPromptSubmit", self.repo, prompt="task_id: t1")
        first = self.sid
        self.sid = "sess-other"
        self.hook("SessionStart", self.repo, source="startup")
        _, out, _ = self.hook("UserPromptSubmit", self.repo, prompt="task_id: t1")
        self.assertIn(f"already running in session {first}", out["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(self.task("t1")["session_id"], "sess-other")


class StatusUnits(StatusBase):
    def test_outcome_takes_last_marker(self):
        self.assertEqual(status.outcome("result: a\nfailed: b"), ("failed", "b"))
        self.assertEqual(status.outcome(None), ("idle", None))

    def test_verify_state(self):
        ev = [{"tree_finish": "t1", "ok": False}, {"tree_finish": "t2", "ok": True}]
        cases = (("t2", False), ("t2", True), ("t1", True), ("t3", True), ("t3", False))
        # (t2, True): a passing run the gate does not count (e.g. filtered) on an UNVERIFIED tree is not a pass (MAE-246)
        self.assertEqual([status.verify_state(ev, t, u) for t, u in cases], ["pass", "not_run", "fail", "not_run", "none"])

    def test_corrupt_status_file_is_rewritten(self):
        self.sdir.mkdir(parents=True)
        (self.sdir / "t.json").write_text("{torn")
        self.assertEqual(status.write("t", "s1", state="running")["state"], "running")

    def fake_gh(self, rc=0):
        log = self.tmp / "gh.log"
        gh = self.tmp / "fake-gh"
        gh.write_text(f"#!{sys.executable}\nimport sys\nopen({str(log)!r}, 'a').write(' '.join(sys.argv[1:]) + '\\n')\n"
                      f"sys.exit({rc})\n")
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        os.environ["MAENG_GH"] = str(gh)  # restored by HarnessCase's env patcher
        return log

    def test_review_status_posts_only_for_github_full_sha(self):
        log = self.fake_gh()
        sha = "a" * 40
        self.assertIsNone(status.post_review_status("github.com/o/r", sha, "pass", self.repo))
        self.assertIsNone(status.post_review_status("/local/remote", sha, "pass", self.repo))
        self.assertIsNone(status.post_review_status("github.com/o/r", "abc", "fail", self.repo))
        calls = log.read_text().splitlines()
        self.assertEqual(len(calls), 1)
        self.assertIn(f"repos/o/r/statuses/{sha}", calls[0])
        self.assertIn("state=success", calls[0])
        self.assertIn("context=maeng/review", calls[0])

    def test_review_status_failure_is_reported_not_raised(self):
        self.fake_gh(rc=1)
        self.assertTrue(status.post_review_status("github.com/o/r", "b" * 40, "fail", self.repo))


class CommittedPlan(StatusBase):
    """MAE-243: without a session binding, `--plan` reads the criteria from the plan file at the reviewed head."""

    def missing(self, *extra):
        base = self.head(self.repo)
        (self.repo / "docs").mkdir()
        (self.repo / "docs/plan.md").write_text("- **AC-2** two\n- **AC-1** one, see AC-1\n")
        (self.repo / "notes.md").write_text("no criteria here\n")
        head = self.commit_all(self.repo)
        r = self.cli("maeng-review", ["run", "--pr", "9", "--base", base, "--head", head, "--base-ref", "main", *extra],
                     self.repo)
        return json.loads(r.stdout)["findings"][0]["body"]

    def test_plan_at_head_supplies_criteria(self):
        self.start(self.repo)
        self.assertNotIn("criteria", self.missing("--plan", "docs/plan.md"))

    def test_without_plan_or_without_ids_criteria_are_missing(self):
        self.start(self.repo)
        self.assertIn("AC-n criteria", self.missing())

    def test_existing_binding_wins_even_without_criteria(self):
        self.start(self.repo)
        self.cli("maeng-verify", ["bind", "MAE-9"], self.repo, check=True)
        self.assertIn("AC-n criteria", self.missing("--plan", "docs/plan.md"))

    def test_plan_without_ids_is_missing(self):
        self.start(self.repo)
        self.assertIn("AC-n criteria", self.missing("--plan", "notes.md"))

    def test_ids_are_unique_and_ordered(self):
        import importlib.machinery
        import importlib.util
        from .helpers import BIN
        loader = importlib.machinery.SourceFileLoader("maeng_review_mod", str(BIN / "maeng-review"))
        spec = importlib.util.spec_from_loader("maeng_review_mod", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        (self.repo / "p.md").write_text("AC-10 AC-2 AC-1 AC-2\n")
        head = self.commit_all(self.repo)
        self.assertEqual(mod.committed_plan(self.repo, head, "p.md")["criteria"], ["AC-1", "AC-2", "AC-10"])


class RoundCap(StatusBase):
    def seed(self, n, repo, pr="7"):
        d = self.maeng_home / "reviews"
        d.mkdir(parents=True, exist_ok=True)
        for i in range(n):
            (d / f"r{i}.json").write_text(json.dumps({"verdict": "fail", "subject": {"kind": "code", "repo": repo, "pr": pr,
                                                                                  "head": f"head{i}"}}))

    def review(self, *extra):
        base = self.head(self.repo)
        return self.cli("maeng-review", ["run", "--pr", "7", "--base", base, "--head", base, "--base-ref", "main", *extra],
                        self.repo)

    def test_incomplete_bundle_at_the_cap_is_blocked_locally_not_capped(self):
        self.start(self.repo)
        self.seed(2, str((self.tmp / "repo-remote.git").resolve()))
        r = self.review()  # unverified head: the local block wins, so the user sees what is missing
        self.assertEqual(r.returncode, 2)
        self.assertEqual(json.loads(r.stdout)["verdict"], "blocked")
        self.assertNotIn("round cap", r.stderr)

    def test_third_head_on_a_verified_head_is_refused_and_points_to_approval(self):
        (self.repo / "docs").mkdir()
        (self.repo / "docs/plan.md").write_text("- **AC-1** one\n")
        head = self.commit_all(self.repo)
        self.start(self.repo)
        self.run_check(self.repo, "pytest -q")
        self.seed(2, str((self.tmp / "repo-remote.git").resolve()))
        r = self.cli("maeng-review", ["run", "--pr", "7", "--base", head, "--head", head, "--base-ref", "main",
                                      "--plan", "docs/plan.md"], self.repo)
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("review round cap", r.stderr)
        self.assertIn("승인 #7", r.stderr)

    def test_other_pr_and_raised_cap_are_not_refused(self):
        self.start(self.repo)
        remote = str((self.tmp / "repo-remote.git").resolve())
        self.seed(2, remote, pr="8")
        self.assertNotIn("round cap", self.review().stderr)
        self.seed(2, remote)
        self.assertNotIn("round cap", self.review("--max-rounds", "3").stderr)
