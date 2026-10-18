import json
import stat
import sys

from maeng import receipts
from .helpers import HarnessCase


class MergeBase(HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.remote = self.tmp / "repo-remote.git"
        self.base = self.head(self.repo)
        self.git(self.repo, "checkout", "-qb", "feat")
        (self.repo / "app.py").write_text("print('c1')\n")
        self.c1 = self.commit_all(self.repo, "c1")
        (self.repo / "lib.py").write_text("x = 1\n")
        self.h = self.commit_all(self.repo, "c2")
        self.git(self.repo, "push", "-q", "origin", "feat")
        self.start(self.repo)
        self.run_check(self.repo, "pytest -q")
        self.pr_json = self.tmp / "pr.json"
        self.set_pr(self.base, self.h)
        self.fake_gh = self.tmp / "fake-gh"
        self.fake_gh.write_text(f"#!{sys.executable}\nimport os\nprint(open(os.environ['FAKE_GH_JSON']).read())\n")
        self.fake_gh.chmod(self.fake_gh.stat().st_mode | stat.S_IEXEC)

    def set_pr(self, base, head, state="OPEN"):
        self.pr_json.write_text(json.dumps({"number": 7, "state": state, "baseRefName": "main", "baseRefOid": base,
                                            "headRefName": "feat", "headRefOid": head,
                                            "url": f"{self.remote}/pull/7"}))

    def changed(self, base, head):
        return sorted(self.git(self.repo, "diff", "--name-only", "--no-renames", f"{base}...{head}").stdout.split())

    def digest(self, base, head, files):
        import hashlib
        out = self.git(self.repo, "diff", "--no-renames", f"{base}...{head}", "--", *files).stdout
        return hashlib.sha256(out.strip().encode()).hexdigest()

    def verdict(self, base=None, head=None, criteria_rev=None, verdict="pass", kind="code", files=None,
                excluded=None, repo="__remote__", pr=7, digest=None, issue=None, parent=None):
        base, head = base or self.base, head or self.h
        files = self.changed(base, head) if files is None else files
        repo = str(self.remote.resolve()) if repo == "__remote__" else repo
        v = {"verdict": verdict, "reviewer": {"model": "gpt-6-astra", "effort": "medium"}, "findings": [],
             "subject": {"kind": kind, "repo": repo, "pr": pr, "base": base, "head": head,
                         "criteria_rev": criteria_rev, "digest": digest or self.digest(base, head, files),
                         "destination": "refs/heads/main", "op": "merge", "files_reviewed": files,
                         "files_excluded": excluded or [], "exclusion_reason": "x" if excluded else None}}
        if issue:
            v["subject"]["issue"] = issue
        if parent:
            v["subject"]["parent"] = parent
        f = self.tmp / "verdict.json"
        f.write_text(json.dumps(v))
        r = self.cli("maeng-review", ["store", str(f)], self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def ship(self, **env):
        return self.cli("maeng-ship", ["merge", "7"], self.repo,
                        extra_env={"MAENG_GH": str(self.fake_gh), "FAKE_GH_JSON": str(self.pr_json), **env})

    def remote_main(self):
        return self.git(self.remote, "rev-parse", "refs/heads/main").stdout.strip()

    def status(self, key):
        return receipts.load(key)["status"]

    def other_clone(self):
        other = self.tmp / "other"
        if not other.exists():
            self.git(self.tmp, "clone", "-q", str(self.remote), str(other))
        return other

    def fake_git(self, name, body):
        path = self.tmp / name
        path.write_text(f"#!{sys.executable}\nimport subprocess, sys\n"
                        f"if sys.argv[1] != 'push':\n    sys.exit(subprocess.run(['git'] + sys.argv[1:]).returncode)\n{body}\n")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
        return str(path)

    LOST_RESPONSE = ("subprocess.run(['git'] + sys.argv[1:])\n"
                     "print('fatal: connection reset by peer', file=sys.stderr)\nsys.exit(1)")


class MaengShipMerge(MergeBase):
    def test_success_consumes_receipt_and_merge_tree_equals_verified_tree(self):
        key = self.verdict()
        r = self.ship()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.remote_main(), self.h)
        rec = receipts.load(key)
        self.assertEqual(rec["status"], "consumed")
        self.assertEqual(rec["result"]["merge_sha"], self.h)
        verified_tree = self.load_state()["evidence"][0]["tree_finish"]
        self.assertEqual(self.git(self.remote, "rev-parse", "refs/heads/main^{tree}").stdout.strip(), verified_tree)
        # single use: a consumed receipt cannot merge again
        self.assertNotEqual(self.ship().returncode, 0)

    def test_without_receipt_nothing_is_pushed(self):
        r = self.ship()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no pass receipt", r.stderr)
        self.assertEqual(self.remote_main(), self.base)

    def test_fail_verdict_is_not_a_receipt(self):
        self.verdict(verdict="fail")
        self.assertNotEqual(self.ship().returncode, 0)
        self.assertEqual(self.remote_main(), self.base)

    def test_behind_pr_is_denied_before_push(self):
        key = self.verdict()
        other = self.other_clone()
        (other / "other.txt").write_text("moved")
        self.git(other, "add", "-A"); self.git(other, "commit", "-qm", "main moved")
        self.git(other, "push", "-q", "origin", "main")
        moved = self.git(other, "rev-parse", "HEAD").stdout.strip()
        self.set_pr(moved, self.h)                     # GitHub reports the new base: head is BEHIND
        r = self.ship()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("BEHIND", r.stderr)
        self.assertEqual(self.remote_main(), moved)
        self.assertEqual(self.status(key), "unconsumed")

    def test_divergent_base_advance_rejected_by_lease_receipt_not_consumed(self):
        key = self.verdict()
        other = self.other_clone()
        (other / "other.txt").write_text("moved")
        self.git(other, "add", "-A"); self.git(other, "commit", "-qm", "diverge")
        self.git(other, "push", "-q", "origin", "main")
        moved = self.git(other, "rev-parse", "HEAD").stdout.strip()
        r = self.ship()                                # GitHub metadata is stale: still reports the reviewed base
        self.assertEqual(r.returncode, 1)
        self.assertIn("base moved", r.stderr)
        self.assertEqual(self.remote_main(), moved)
        self.assertEqual(self.status(key), "unconsumed")

    def test_base_moved_to_ancestor_of_head_rejected_by_lease(self):
        key = self.verdict()
        self.git(self.repo, "push", "-q", "origin", f"{self.c1}:refs/heads/main")   # main -> c1, an ancestor of head
        self.assertEqual(self.remote_main(), self.c1)
        r = self.ship()
        self.assertEqual(r.returncode, 1)
        self.assertIn("base moved", r.stderr)
        self.assertEqual(self.remote_main(), self.c1)  # a plain push would have fast-forwarded; the lease did not
        self.assertEqual(self.status(key), "unconsumed")

    def test_unverified_head_tree_blocks_merge(self):
        (self.repo / "app.py").write_text("print('unverified')\n")
        new_head = self.commit_all(self.repo, "unverified")
        self.git(self.repo, "push", "-q", "origin", "feat")
        self.set_pr(self.base, new_head)
        self.verdict(head=new_head)
        r = self.ship()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not ship-verified", r.stderr)
        self.assertEqual(self.remote_main(), self.base)

    def test_stale_head_base_and_criteria_receipts_are_rejected(self):
        self.verdict(head=self.c1)                      # reviewed an older head
        self.assertIn("no pass receipt", self.ship().stderr)
        self.verdict(base=self.c1)                      # reviewed a different base
        self.assertIn("no pass receipt", self.ship().stderr)
        plan = self.tmp / "plan.md"
        plan.write_text("AC-1 x\n## Verification\nAC-1: pytest\n")
        self.cli("maeng-verify", ["bind", "MAE-3", "--plan", str(plan), "--plan-updated", "2026-10-17T10:00"], self.repo)
        self.cli("maeng-verify", ["plan", "--met", "AC-1"], self.repo)
        self.verdict(criteria_rev="2026-10-16T10:00")   # review predates the current criteria
        r = self.ship()
        self.assertIn("stale", r.stderr)
        self.assertEqual(self.remote_main(), self.base)
        self.verdict(criteria_rev="2026-10-17T10:00")
        self.assertEqual(self.ship().returncode, 0)

    def bind(self, issue, rev, parent=None):
        plan = self.tmp / "plan.md"
        plan.write_text("AC-1 x\n## Verification\nAC-1: pytest\n")
        args = ["bind", issue, "--plan", str(plan), "--plan-updated", rev] + (["--parent", parent] if parent else [])
        self.assertEqual(self.cli("maeng-verify", args, self.repo).returncode, 0)
        self.cli("maeng-verify", ["plan", "--met", "AC-1"], self.repo)

    def test_child_receipt_covers_parent_merge(self):
        self.bind("MAE-222", "2026-10-16T10:00", parent="MAE-216")
        self.verdict(criteria_rev="2026-10-16T10:00", issue="MAE-222", parent="MAE-216")
        self.bind("MAE-216", "2026-10-17T10:00")
        r = self.ship()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.remote_main(), self.h)

    def test_non_child_receipt_with_other_criteria_is_stale(self):
        self.bind("MAE-300", "2026-10-16T10:00", parent="MAE-999")
        self.verdict(criteria_rev="2026-10-16T10:00", issue="MAE-300", parent="MAE-999")
        self.bind("MAE-216", "2026-10-17T10:00")
        r = self.ship()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("stale", r.stderr)
        self.assertNotIn("stale child receipt", r.stderr)
        self.assertEqual(self.remote_main(), self.base)

    def test_receipt_without_issue_fields_is_stale(self):
        self.verdict(criteria_rev="2026-10-16T10:00")
        self.bind("MAE-216", "2026-10-17T10:00")
        r = self.ship()
        self.assertIn("stale", r.stderr)
        self.assertNotIn("stale child receipt", r.stderr)
        self.assertEqual(self.remote_main(), self.base)

    def test_child_receipt_with_changed_child_criteria_is_denied(self):
        self.bind("MAE-222", "2026-10-16T10:00", parent="MAE-216")
        self.verdict(criteria_rev="2026-10-16T10:00", issue="MAE-222", parent="MAE-216")
        self.bind("MAE-222", "2026-10-16T12:00", parent="MAE-216")   # child plan changed after the review
        self.bind("MAE-216", "2026-10-17T10:00")
        r = self.ship()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("stale child receipt", r.stderr)
        self.assertEqual(self.remote_main(), self.base)

    def test_lost_response_then_reconcile_remote_at_head(self):
        key = self.verdict()
        r = self.ship(MAENG_GIT=self.fake_git("lost-git", self.LOST_RESPONSE))
        self.assertEqual(r.returncode, 3)
        self.assertEqual(self.remote_main(), self.h)    # the server accepted it
        self.assertEqual(self.status(key), "pending")
        self.assertNotEqual(self.ship().returncode, 0)  # pending receipts cannot be reused
        out = self.cli("maeng-review", ["reconcile", "--repo", str(self.repo)], self.repo)
        self.assertIn("consumed", out.stdout)
        self.assertEqual(self.status(key), "consumed")

    def test_lost_response_then_reconcile_remote_advanced_beyond_head(self):
        key = self.verdict()
        self.ship(MAENG_GIT=self.fake_git("lost-git", self.LOST_RESPONSE))
        other = self.other_clone()
        self.git(other, "pull", "-q", "origin", "main")
        (other / "later.txt").write_text("later")
        self.git(other, "add", "-A"); self.git(other, "commit", "-qm", "after merge")
        self.git(other, "push", "-q", "origin", "main")
        advanced = self.git(other, "rev-parse", "HEAD").stdout.strip()
        self.assertNotEqual(advanced, self.h)
        out = self.cli("maeng-review", ["reconcile", "--repo", str(self.repo)], self.repo)
        self.assertIn("consumed", out.stdout)
        rec = receipts.load(key)
        self.assertEqual(rec["status"], "consumed")
        self.assertEqual(rec["result"]["merge_sha"], advanced)

    def test_client_failure_before_server_then_reconcile_allows_retry(self):
        key = self.verdict()
        self.ship(MAENG_GIT=self.fake_git("dead-git", "print('fatal: could not resolve host', file=sys.stderr)\nsys.exit(1)"))
        self.assertEqual(self.status(key), "pending")
        out = self.cli("maeng-review", ["reconcile", "--repo", str(self.repo)], self.repo)
        self.assertIn("retry", out.stdout)
        self.assertEqual(self.status(key), "unconsumed")
        self.assertEqual(self.ship().returncode, 0)

    def test_reconcile_unknown_state_stays_pending(self):
        key = self.verdict()
        self.ship(MAENG_GIT=self.fake_git("dead-git", "sys.exit(1)"))
        other = self.other_clone()
        (other / "div.txt").write_text("d")
        self.git(other, "add", "-A"); self.git(other, "commit", "-qm", "diverged")
        self.git(other, "push", "-q", "origin", "main")
        self.cli("maeng-review", ["reconcile", "--repo", str(self.repo)], self.repo)
        self.assertEqual(self.status(key), "pending")


class UserApproval(MergeBase):
    def approve(self, prompt="승인 #7"):
        self.env.update(MAENG_GH=str(self.fake_gh), FAKE_GH_JSON=str(self.pr_json))
        return self.hook("UserPromptSubmit", self.repo, prompt=prompt)[1]

    def test_user_approval_replaces_the_review_receipt_once_for_that_head(self):
        self.assertIn("승인 #7", self.ship().stderr)
        self.assertIsNone(self.approve("이거 승인 #7 하지마"))     # only a message that starts with it counts
        self.assertIn("approved PR #7", json.dumps(self.approve(), ensure_ascii=False))
        r = self.ship()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.remote_main(), self.h)
        self.assertNotEqual(self.ship().returncode, 0)            # consumed: single use

    def test_pending_approval_is_listed_for_reconcile(self):
        self.approve()
        key = receipts.approval_key(str(self.remote.resolve()), "7", self.h)
        receipts.begin(key, {"remote": "origin", "ref": "refs/heads/main", "base_sha": self.base, "head_sha": self.h})
        self.assertIn(key, [r["key"] for r in receipts.pending_code()])

    def test_approval_is_bound_to_the_head_it_saw(self):
        self.approve("approve PR #7")
        (self.repo / "late.py").write_text("y = 2\n")
        h2 = self.commit_all(self.repo, "late")
        self.git(self.repo, "push", "-q", "origin", "feat")
        self.run_check(self.repo, "pytest -q")
        self.set_pr(self.base, h2)
        self.assertNotEqual(self.ship().returncode, 0)
        self.assertEqual(self.remote_main(), self.base)


class ExactLeaseThroughHook(MergeBase):
    def lease_cmd(self, base=None, head=None):
        return f"git push --force-with-lease=refs/heads/main:{base or self.base} origin {head or self.h}:refs/heads/main"

    def test_exact_form_needs_matching_receipt(self):
        denied, reason = self.bash_pre(self.repo, self.lease_cmd())
        self.assertTrue(denied)
        self.assertIn("no pass receipt", reason)
        key = self.verdict()
        denied, reason = self.bash_pre(self.repo, self.lease_cmd())
        self.assertFalse(denied, reason)
        self.assertEqual(self.status(key), "pending")            # persisted before dispatch

    def test_stale_head_or_base_in_exact_form(self):
        self.verdict()
        self.assertTrue(self.bash_pre(self.repo, self.lease_cmd(head=self.c1))[0])
        self.assertTrue(self.bash_pre(self.repo, self.lease_cmd(base=self.c1))[0])

    def test_unreadable_receipt_denies(self):
        key = self.verdict()
        (receipts.receipts_dir() / f"{key}.json").write_text("{corrupt")
        denied, reason = self.bash_pre(self.repo, self.lease_cmd())
        self.assertTrue(denied)
        self.assertIn("unreadable", reason)

    def test_unverified_head_denies_exact_form(self):
        (self.repo / "app.py").write_text("print('unverified')\n")
        new_head = self.commit_all(self.repo, "unverified")
        self.verdict(head=new_head)
        denied, reason = self.bash_pre(self.repo, self.lease_cmd(head=new_head))
        self.assertTrue(denied)
        self.assertIn("not ship-verified", reason)

    def test_post_hooks_consume_reject_or_leave_pending(self):
        key = self.verdict()
        cmd = self.lease_cmd()
        body = {"tool_name": "Bash", "tool_input": {"command": cmd}}
        self.hook("PreToolUse", self.repo, tool_use_id="m1", **body)
        self.assertEqual(self.status(key), "pending")
        self.hook("PostToolUseFailure", self.repo, tool_use_id="m1", error="! [rejected] main (stale info)", **body)
        self.assertEqual(self.status(key), "unconsumed")           # confirmed rejection: retry allowed
        self.hook("PreToolUse", self.repo, tool_use_id="m2", **body)
        self.hook("PostToolUseFailure", self.repo, tool_use_id="m2", error="fatal: connection reset by peer", **body)
        self.assertEqual(self.status(key), "pending")              # unclear: waits for reconcile
        self.assertTrue(self.bash_pre(self.repo, cmd)[0])
        self.cli("maeng-review", ["reconcile", "--repo", str(self.repo)], self.repo)
        self.assertEqual(self.status(key), "unconsumed")
        self.hook("PreToolUse", self.repo, tool_use_id="m3", **body)
        self.hook("PostToolUse", self.repo, tool_use_id="m3", tool_response={"stdout": ""}, **body)
        self.assertEqual(self.status(key), "consumed")
