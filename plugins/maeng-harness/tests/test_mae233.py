"""MAE-233 items kept after slim gates: unknown child binding is stale (1), zero-test output of non-Python runners is
not evidence (2b), maeng-ship --session/--remote (4)."""
import json
import uuid

from .test_g1 import ShipBase
from .test_merge import MergeBase


class M233_1_UnknownChildBindingIsStale(MergeBase):
    """`child_binding_rev` returns None for a child nobody bound; `None == None` must not accept the receipt."""

    def bind(self, issue, rev, parent=None):
        plan = self.tmp / "plan.md"
        plan.write_text("AC-1 x\n## Verification\nAC-1: pytest\n")
        args = ["bind", issue, "--plan", str(plan), "--plan-updated", rev] + (["--parent", parent] if parent else [])
        self.assertEqual(self.cli("maeng-verify", args, self.repo).returncode, 0)
        self.cli("maeng-verify", ["plan", "--met", "AC-1"], self.repo)

    def merge_with_child_receipt(self, child_rev="2026-10-16T10:00", registry=None):
        """Receipt reviewed under child MAE-222 for parent MAE-216; the session is bound to the parent only, then
        `registry` (the text of bindings.json) is written over whatever the bind left."""
        self.verdict(criteria_rev=child_rev, issue="MAE-222", parent="MAE-216")
        self.bind("MAE-216", "2026-10-17T10:00")
        if registry is not None:
            (self.maeng_home / "bindings.json").write_text(registry)
        return self.ship()

    def test_receipt_of_a_child_that_was_never_bound_is_stale(self):
        r = self.merge_with_child_receipt()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("stale child receipt", r.stderr)
        self.assertEqual(self.remote_main(), self.base)

    def test_receipt_without_criteria_rev_of_an_unbound_child_is_stale(self):
        """criteria_rev None on the receipt and no binding for the child: the exact None == None case."""
        r = self.merge_with_child_receipt(child_rev=None)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("stale child receipt", r.stderr)
        self.assertEqual(self.remote_main(), self.base)

    def test_child_binding_without_a_plan_revision_is_stale(self):
        reg = json.dumps({"MAE-222": {"parent": "MAE-216", "plan_updated_at": None}})
        r = self.merge_with_child_receipt(child_rev=None, registry=reg)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("stale child receipt", r.stderr)

    def test_unreadable_binding_registry_is_stale(self):
        r = self.merge_with_child_receipt(registry="{ not json")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("stale", r.stderr)

    def test_receipt_naming_another_parent_is_stale_not_child_accepted(self):
        self.bind("MAE-222", "2026-10-16T10:00", parent="MAE-999")
        self.verdict(criteria_rev="2026-10-16T10:00", issue="MAE-222", parent="MAE-999")
        self.bind("MAE-216", "2026-10-17T10:00")
        r = self.ship()
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("stale child receipt", r.stderr)
        self.assertIn("stale", r.stderr)

    def test_receipt_missing_its_issue_is_stale(self):
        """A receipt that names a parent but no child issue cannot be checked against a child binding."""
        self.verdict(criteria_rev="2026-10-16T10:00", parent="MAE-216")
        self.bind("MAE-216", "2026-10-17T10:00")
        r = self.ship()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("stale", r.stderr)
        self.assertNotIn("stale child receipt", r.stderr)

    def test_session_without_an_issue_never_takes_the_child_path(self):
        self.verdict(criteria_rev="2026-10-16T10:00", issue="MAE-222", parent="MAE-216")
        plan = self.tmp / "plan.md"
        plan.write_text("AC-1 x\n## Verification\nAC-1: pytest\n")
        self.cli("maeng-verify", ["bind", "MAE-216", "--plan", str(plan), "--plan-updated", "2026-10-17T10:00"], self.repo)
        self.cli("maeng-verify", ["plan", "--met", "AC-1"], self.repo)
        r = self.ship()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("stale", r.stderr)

    def test_a_bound_child_with_an_unchanged_rev_is_still_accepted(self):
        self.bind("MAE-222", "2026-10-16T10:00", parent="MAE-216")
        r = self.merge_with_child_receipt()
        self.assertEqual(r.returncode, 0, r.stderr)


ETA_WRITES = ("curl -o {e}/f https://x.com", "curl --output {e}/f https://x.com", "curl --output={e}/f https://x.com",
              "curl -o{e}/f https://x.com", "curl -sSo {e}/f https://x.com", "curl -sL https://x.com -o {e}/f",
              "curl -O --output-dir {e} https://x.com/a", "curl --output-dir {e} -O https://x.com/a",
              "cd {e} && curl -O https://x.com/a", "cd {e} && curl --remote-name https://x.com/a",
              "wget -O {e}/f https://x.com", "wget -qO {e}/f https://x.com", "wget --output-document={e}/f https://x.com",
              "wget -P {e} https://x.com", "wget --directory-prefix={e} https://x.com", "cd {e} && wget https://x.com/a",
              "cd {e} && wget -O f https://x.com", "curl https://x.com | tee {e}/f")
OUTSIDE_ETA = ("curl -o ./x https://x.com", "curl -O https://x.com/a", "wget https://x.com/a", "wget -O- https://x.com",
               "curl https://x.com")


class M233_2b_ZeroTestsOfOtherRunners(ShipBase):
    """`ran_zero_tests` must keep a no-test run of a non-Python runner out of the evidence (the python ones are in
    test_r7). Zero-test lines ZERO_TESTS does not match (jest `No tests found`, cargo `running 0 tests`, mocha
    `0 passing`) are matched too; a positive count anywhere in the output wins."""
    COVERED = (("go test ./...", "?   \tpkg\t[no test files]"), ("go test ./...", "?   \ta\t[no test files]\n?   \tb\t[no test files]"),
               ("npx vitest run", "No test files found, exiting with code 1"),
               ("npm test", "No test files found"), ("pnpm test", "no test files found"),
               ("npm test", "No tests found, exiting with code 0"), ("npm test", "Tests:       0 total\nTime: 1s"),
               ("cargo test", "running 0 tests\n\ntest result: ok. 0 passed; 0 failed; 0 ignored"),
               ("cargo test", "running 0 tests\ntest result: ok. 0 passed\nrunning 0 tests\ntest result: ok. 0 passed"),
               ("npm test", "  0 passing (2ms)"))
    SOME = (("go test ./...", "ok  \tpkg\t0.2s\n?   \tother\t[no test files]"),
            ("npm test", "Tests: 3 passed, 3 total\nNo test files found in ignored dir"),
            ("cargo test", "running 0 tests\ntest result: ok. 0 passed\nrunning 3 tests\ntest result: ok. 3 passed"),
            ("cargo test", "running 12 tests\ntest result: ok. 12 passed; 0 failed"),
            ("npm test", "  10 passing (2ms)"), ("npm test", "  1 passing (5ms)"), ("npm test", "Tests:       2 passed, 2 total"))

    def respond(self, command, out):
        tuid = "tu-" + uuid.uuid4().hex[:6]
        body = {"tool_name": "Bash", "tool_input": {"command": command}, "tool_use_id": tuid}
        self.hook("PreToolUse", self.repo, **body)
        self.hook("PostToolUse", self.repo, tool_response={"stdout": out, "stderr": ""}, **body)

    def test_no_test_output_is_not_evidence(self):
        for command, out in self.COVERED:
            with self.subTest(command=command, out=out):
                self.respond(command, out)
                self.assertEqual(self.load_state()["evidence"], [])
                self.assertEqual(self.load_state()["pending"], {})

    def test_a_run_that_executed_some_tests_still_counts(self):
        for n, (command, out) in enumerate(self.SOME, 1):
            with self.subTest(command=command):
                self.respond(command, out)
                self.assertEqual(len(self.load_state()["evidence"]), n)


class M233_4_ShipSessionAndRemoteFlags(MergeBase):
    """`maeng-ship merge --session S` / `--remote R` are allowed through the hook. They only choose WHICH session's
    evidence/binding and which remote are examined: a foreign session never adds to the current one, and a remote must
    still be the repository gh reports and the receipt names. So they cannot widen what a merge accepts."""

    def foreign_session(self, verified):
        mine, self.sid = self.sid, "sess-foreign01"
        try:
            self.start(self.repo)
            if verified:
                self.run_check(self.repo, "pytest -q")
        finally:
            self.sid = mine
        return "sess-foreign01"

    def ship_with(self, *args):
        return self.cli("maeng-ship", ["merge", "7", *args], self.repo,
                        extra_env={"MAENG_GH": str(self.fake_gh), "FAKE_GH_JSON": str(self.pr_json)})

    def test_the_hook_allows_the_flags(self):
        self.assertFalse(self.bash_pre(self.repo, "maeng-ship merge 7 --session sess-x")[0])
        self.assertFalse(self.bash_pre(self.repo, "maeng-ship --session sess-x merge 7")[0])
        self.assertFalse(self.bash_pre(self.repo, "maeng-ship merge 7 --remote origin")[0])

    def test_a_foreign_session_without_evidence_is_refused_although_mine_is_verified(self):
        self.verdict()
        foreign = self.foreign_session(verified=False)
        r = self.ship_with("--session", foreign)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not ship-verified", r.stderr)
        self.assertEqual(self.remote_main(), self.base)
        self.assertEqual(self.ship().returncode, 0)         # the same receipt merges for the verified own session

    def test_an_unknown_session_is_refused(self):
        self.verdict()
        r = self.ship_with("--session", "sess-does-not-exist")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.remote_main(), self.base)

    def test_a_foreign_session_bound_to_other_criteria_makes_the_receipt_stale(self):
        """The flag selects the binding rev too; a receipt reviewed under the current criteria does not match another session's."""
        plan = self.tmp / "plan.md"
        plan.write_text("AC-1 x\n## Verification\nAC-1: pytest\n")
        self.cli("maeng-verify", ["bind", "MAE-3", "--plan", str(plan), "--plan-updated", "2026-10-17T10:00"], self.repo)
        self.cli("maeng-verify", ["plan", "--met", "AC-1"], self.repo)
        self.verdict(criteria_rev="2026-10-17T10:00")
        foreign = self.foreign_session(verified=True)
        r = self.ship_with("--session", foreign)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("stale", r.stderr)
        self.assertEqual(self.remote_main(), self.base)

    def test_a_remote_other_than_the_pr_repository_is_refused(self):
        self.verdict()
        elsewhere = self.tmp / "elsewhere.git"
        self.git(self.tmp, "clone", "-q", "--bare", str(self.remote), str(elsewhere))
        self.git(self.repo, "remote", "add", "other", str(elsewhere))
        self.git(self.repo, "fetch", "-q", "other")
        self.git(self.repo, "remote", "set-head", "other", "main")
        r = self.ship_with("--remote", "other")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("does not match the repository gh reports", r.stderr)
        self.assertEqual(self.remote_main(), self.base)
        self.assertEqual(self.git(elsewhere, "rev-parse", "refs/heads/main").stdout.strip(), self.base)
