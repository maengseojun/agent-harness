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

    def test_unverified_change_runs_then_blocks_and_pass_names_verified_head(self):
        self.start(self.repo)
        tid = "s-" + self.sid.replace("-", "")[:8]
        (self.repo / "app.py").write_text("print('x')\n")
        self.hook("PostToolUse", self.repo, tool_name="Edit", tool_input={"file_path": str(self.repo / "app.py")},
                  tool_response={})
        self.stop("result: done")
        self.assertEqual((self.task(tid)["state"], self.task(tid)["verify_state"]), ("running", "not_run"))
        self.stop("result: done", active=True)
        rec = self.task(tid)
        self.assertEqual(rec["state"], "blocked")
        self.assertIn("UNVERIFIED", rec["blocker"])
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
        self.assertEqual([status.verify_state(ev, t, u) for t, u in (("t2", True), ("t1", True), ("t3", True), ("t3", False))],
                         ["pass", "fail", "not_run", "none"])

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


class RoundCap(StatusBase):
    def seed(self, n, repo, pr="7"):
        d = self.maeng_home / "reviews"
        d.mkdir(parents=True, exist_ok=True)
        for i in range(n):
            (d / f"r{i}.json").write_text(json.dumps({"verdict": "fail", "subject": {"kind": "code", "repo": repo, "pr": pr}}))

    def review(self, *extra):
        base = self.head(self.repo)
        return self.cli("maeng-review", ["run", "--pr", "7", "--base", base, "--head", base, "--base-ref", "main", *extra],
                        self.repo)

    def test_fifth_round_is_refused_and_points_to_approval(self):
        self.start(self.repo)
        self.seed(4, str((self.tmp / "repo-remote.git").resolve()))
        r = self.review()
        self.assertEqual(r.returncode, 2)
        self.assertIn("review round cap", r.stderr)
        self.assertIn("승인 #7", r.stderr)

    def test_other_pr_and_raised_cap_are_not_refused(self):
        self.start(self.repo)
        remote = str((self.tmp / "repo-remote.git").resolve())
        self.seed(4, remote, pr="8")
        self.assertNotIn("round cap", self.review().stderr)
        self.seed(4, remote)
        self.assertNotIn("round cap", self.review("--max-rounds", "5").stderr)
