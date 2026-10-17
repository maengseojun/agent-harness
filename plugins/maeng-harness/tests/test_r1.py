"""Regression tests for Astra review R1 (PR #38): one test class per finding."""
import json
import threading
import uuid

from maeng import evidence, gates, handlers, receipts
from maeng.common import canonical, sha256
from .helpers import HarnessCase
from .test_g1 import ShipBase
from .test_g2_g3 import CREATE, DB, FETCH, PAGE, G2Tests
from .test_merge import MergeBase

LEASE = "git push --force-with-lease=refs/heads/main:{base} origin {head}:refs/heads/main"


class R1_1_ReservationFailsClosed(MergeBase):
    def payload(self):
        cmd = LEASE.format(base=self.base, head=self.h)
        return {"hook_event_name": "PreToolUse", "session_id": self.sid, "cwd": str(self.repo), "tool_name": "Bash",
                "tool_input": {"command": cmd}, "tool_use_id": "x" + uuid.uuid4().hex[:4]}

    def test_reservation_error_denies_and_nothing_stays_pending(self):
        key = self.verdict()
        from unittest import mock
        with mock.patch.object(receipts, "begin_many", side_effect=OSError("disk full")):
            out = handlers.on_pre(self.payload())
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("unjournaled", out["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertEqual(self.status(key), "unconsumed")

    def test_second_concurrent_call_is_denied(self):
        key = self.verdict()
        from unittest import mock
        intent = {"remote": "origin", "ref": "refs/heads/main", "base_sha": self.base, "head_sha": self.h}
        dec = gates.Decision(True, "", [("receipt_pending", key, intent)])
        with mock.patch.object(gates, "evaluate", return_value=dec):   # both calls passed evaluation
            first = handlers.on_pre(self.payload())
            second = handlers.on_pre(self.payload())
        self.assertIsNone(first)
        self.assertEqual(second["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_begin_many_is_exclusive_across_threads(self):
        key = self.verdict()
        results = []

        def go():
            try:
                receipts.begin_many([(key, {"n": 1})])
                results.append("ok")
            except receipts.ReceiptError:
                results.append("denied")
        ts = [threading.Thread(target=go) for _ in range(6)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(sorted(results), ["denied"] * 5 + ["ok"])

    def test_journal_failure_denies_and_releases_receipt(self):
        from unittest import mock
        payload = {"parent": {"data_source_id": DB}, "pages": [{"properties": {"title": "Outcome"}}]}
        repo = self.make_repo("notion")
        self.start(repo)
        v = {"verdict": "pass", "reviewer": {"model": "gpt-6.1-sol", "effort": "medium"}, "findings": [],
             "subject": {"kind": "notion", "repo": None, "pr": None, "base": None, "head": None, "criteria_rev": None,
                         "digest": sha256(canonical(payload)), "destination": DB, "op": "create"}}
        key = receipts.store_verdict(v)
        with mock.patch.object(receipts, "journal_pending", side_effect=OSError("disk full")):
            out = handlers.on_pre({"hook_event_name": "PreToolUse", "session_id": self.sid, "cwd": str(repo),
                                   "tool_name": CREATE, "tool_input": payload, "tool_use_id": "n1"})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(receipts.load(key)["status"], "unconsumed")


class R1_2_ReviewCoverage(MergeBase):
    def test_partial_receipt_does_not_authorize_whole_pr(self):
        k1 = self.verdict(files=["app.py"])
        r = self.ship()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("coverage incomplete", r.stderr)
        self.assertIn("lib.py", r.stderr)
        self.assertEqual(self.remote_main(), self.base)
        self.assertEqual(self.status(k1), "unconsumed")

    def test_partial_receipt_denied_through_the_hook_too(self):
        self.verdict(files=["app.py"])
        denied, reason = self.bash_pre(self.repo, LEASE.format(base=self.base, head=self.h))
        self.assertTrue(denied)
        self.assertIn("coverage incomplete", reason)

    def test_union_of_receipts_covers_and_all_are_consumed(self):
        k1 = self.verdict(files=["app.py"])
        k2 = self.verdict(files=["lib.py"])
        self.assertNotEqual(k1, k2)
        r = self.ship()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.status(k1), self.status(k2)), ("consumed", "consumed"))
        self.assertEqual(self.remote_main(), self.h)

    def test_code_receipt_exclusion_does_not_cover_but_parent_exclusion_does(self):
        self.verdict(files=["app.py"], excluded=["lib.py"])                       # kind=code: exclusion not accepted
        self.assertIn("coverage incomplete", self.ship().stderr)
        k = self.verdict(files=["app.py"], excluded=["lib.py"], kind="parent")    # parent reviewer accepted it
        r = self.ship()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.status(k), "consumed")

    def test_receipt_whose_diff_digest_does_not_match_is_not_used(self):
        self.verdict(digest="0" * 64)
        self.assertIn("coverage incomplete", self.ship().stderr)
        self.assertEqual(self.remote_main(), self.base)


class R1_3_RepositoryBinding(MergeBase):
    def test_receipt_for_another_repository_does_not_authorize(self):
        self.verdict(repo="github.com/someone/fork")
        r = self.ship()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no pass receipt for this repo", r.stderr)
        self.assertEqual(self.remote_main(), self.base)
        denied, reason = self.bash_pre(self.repo, LEASE.format(base=self.base, head=self.h))
        self.assertTrue(denied)

    def test_gh_repository_must_equal_push_remote(self):
        self.verdict()
        data = json.loads(self.pr_json.read_text())
        data["url"] = "https://github.com/other/repo/pull/7"
        self.pr_json.write_text(json.dumps(data))
        r = self.ship()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("does not match the repository gh reports", r.stderr)
        self.assertEqual(self.remote_main(), self.base)

    def test_eta_remote_is_refused_by_ship_and_hook(self):
        self.verdict()
        self.git(self.repo, "remote", "add", "etar", "git@github.com:endix-foundation-v1/web.git")
        r = self.cli("maeng-ship", ["merge", "7", "--remote", "etar"], self.repo,
                     extra_env={"MAENG_GH": str(self.fake_gh), "FAKE_GH_JSON": str(self.pr_json)})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("eta", r.stderr)
        cmd = LEASE.format(base=self.base, head=self.h).replace(" origin ", " etar ")
        denied, reason = self.bash_pre(self.repo, cmd)
        self.assertTrue(denied)
        self.assertIn("eta", reason)
        self.assertEqual(self.remote_main(), self.base)

    def test_normalize_repo_equates_url_forms(self):
        from maeng import guard
        forms = ["git@github.com:O/R.git", "https://github.com/o/r", "ssh://git@github.com/o/r.git", "o/r"]
        self.assertEqual({guard.normalize_repo(f) for f in forms}, {"github.com/o/r"})


class R1_4_ConfiguredPushRefspec(ShipBase):
    """Round 2 replaced refspec resolution with: explicit refspec only, and no remote.<r>.push at all."""

    def test_c_override_of_remote_push_to_default_branch_denied(self):
        self.verified()
        self.assertDenied("git -c remote.origin.push=HEAD:refs/heads/main push origin", "canonical")
        self.assertDenied("git -c remote.origin.push=HEAD:refs/heads/main push", "canonical")

    def test_config_file_remote_push_denied(self):
        self.verified()
        self.git(self.repo, "config", "remote.origin.push", "HEAD:refs/heads/main")
        self.assertDenied("git push origin", "canonical")
        self.assertDenied("git push", "canonical")
        self.assertDenied("git push origin feat", "remote.origin.push")      # was allowed: now any remote.push denies

    def test_undeterminable_refspec_is_denied(self):
        self.verified()
        self.git(self.repo, "config", "remote.origin.push", "+refs/heads/*:refs/heads/*")
        self.assertDenied("git push origin", "canonical")
        self.assertDenied("git push origin feat", "remote.origin.push")
        self.git(self.repo, "config", "--unset", "remote.origin.push")
        self.git(self.repo, "config", "remote.origin.push", "refs/heads/*:refs/heads/*")
        self.assertDenied("git push origin", "canonical")
        self.assertDenied("GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=remote.origin.push git push origin", "canonical")

    def test_benign_configured_refspec_no_longer_allows_implicit_pushes(self):
        self.verified()
        self.git(self.repo, "config", "remote.origin.push", "HEAD:refs/heads/feat")
        self.assertDenied("git push origin", "canonical")
        self.assertDenied("git -c remote.origin.push= push origin", "canonical")


class R1_5_ControlStructures(ShipBase):
    def test_structures_with_shipping_routes_are_denied(self):
        self.verified()
        for cmd in ("if true; then git push origin main; fi", "while true; do git push origin feat; done",
                    "for i in 1; do gh pr merge 1; done", "case x in x) git push origin feat;; esac",
                    "f() { git push origin main; }; f", "{ git push origin main; }", "( git push origin main )",
                    "true && if true; then gh api -X POST repos/o/r/merges; fi", "if x; then git -C /tmp push; fi"):
            self.assertDenied(cmd, "canonical")

    def test_structures_without_routes_and_plain_pushes_unchanged(self):
        self.verified()
        self.assertAllowed("if true; then echo hi; fi")
        self.assertAllowed("git push origin feat")
        self.assertDenied("git push origin main")


class R1_7_EvidenceIdentity(ShipBase):
    def policy(self, required):
        (self.repo / ".maeng").mkdir(exist_ok=True)
        (self.repo / ".maeng/verify.json").write_text(json.dumps({"required": required}))
        self.commit_all(self.repo, "policy")

    def test_invocations_that_run_no_checks_are_not_evidence(self):
        for cmd in ("pytest --version", "pytest -V", "pytest --help", "pytest -h", "pytest --collect-only",
                    "pytest --co", "cargo test --dry-run", "python3 -m pytest --version"):
            self.assertIsNone(evidence.recognize(cmd), cmd)
            self.run_check(self.repo, cmd)
        self.assertEqual(self.load_state()["evidence"], [])
        self.assertTrue(self.bash_pre(self.repo, "git push origin feat")[0])

    def test_identity_normalizes_whitespace_and_verbosity_only(self):
        ident = lambda c: evidence.recognize(c)["checks"][0][2]
        self.assertEqual(ident("pytest   -q "), "pytest")
        self.assertEqual(ident("python3 -m pytest -vv tests/unit"), "pytest tests/unit")
        self.assertEqual(ident("uv run pytest  -k  foo"), "pytest -k foo")

    def test_unit_subset_does_not_satisfy_full_suite_requirement(self):
        self.policy(["pytest"])
        self.run_check(self.repo, "pytest tests/unit")
        denied, reason = self.bash_pre(self.repo, "git push origin feat")
        self.assertTrue(denied)
        self.assertIn("required check not passed", reason)
        self.run_check(self.repo, "pytest")                              # bare pytest = the full suite
        self.assertFalse(self.bash_pre(self.repo, "git push origin feat")[0])

    def test_glob_requirement_accepts_matching_identity(self):
        self.policy(["pytest tests/*"])
        self.run_check(self.repo, "pytest tests/unit")
        self.assertFalse(self.bash_pre(self.repo, "git push origin feat")[0])

    def test_subset_pass_does_not_clear_full_failure(self):
        self.policy(["pytest tests/unit"])
        self.run_check(self.repo, "pytest", ok=False)
        self.run_check(self.repo, "pytest tests/unit")
        denied, reason = self.bash_pre(self.repo, "git push origin feat")
        self.assertTrue(denied)
        self.assertIn("unresolved failure: pytest", reason)
        self.run_check(self.repo, "pytest")                              # the same identity passes later
        self.assertFalse(self.bash_pre(self.repo, "git push origin feat")[0])


class R1_8_G3(HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.eta_root.mkdir()
        (self.eta_root / "file.txt").write_text("eta")
        self.start(self.repo)

    def denied(self, cmd):
        d, reason = self.bash_pre(self.repo, cmd)
        self.assertTrue(d, f"expected deny: {cmd} ({reason})")

    def allowed(self, cmd):
        d, reason = self.bash_pre(self.repo, cmd)
        self.assertFalse(d, f"expected allow: {cmd} ({reason})")

    def test_relative_redirects_resolve_against_effective_directory(self):
        e = self.eta_root
        for cmd in (f"cd {e} && printf x > file.txt", f"cd {e} && echo x >> new.txt", f"cd {e} && echo x 2> err.txt",
                    f"cd {e} && echo x &> all.txt", f"cd {e}; echo x | tee out.txt", f"echo x | tee {e}/out.txt",
                    f"cd {e} && cat file.txt > ../eta_v1/y"):
            self.denied(cmd)
        self.allowed("echo x > out.txt")
        self.allowed(f"cd {e} && ls 2>&1")
        self.allowed(f"ls {e} > /dev/null")

    def test_read_only_programs_with_mutation_options_are_mutating(self):
        e = self.eta_root
        for cmd in (f"find {e} -type f -delete", f"find {e} -exec rm {{}} ;", f"find {e} -execdir touch x ;",
                    f"find {e} -fprint {e}/o", f"sort -o {e}/file.txt in.txt", f"sort --output={e}/file.txt in.txt",
                    f"sed -i s/a/b/ {e}/file.txt", f"cd {e} && sed -i s/a/b/ file.txt", f"echo a | xargs rm {e}/file.txt",
                    f"cd {e} && xargs touch", f"cp a {e}/a", f"mv a {e}/a", f"rm {e}/file.txt", f"touch {e}/t",
                    f"mkdir {e}/d", f"ln -s a {e}/l", f"chmod 600 {e}/file.txt", f"chown me {e}/file.txt",
                    f"truncate -s 0 {e}/file.txt", f"dd if=/dev/zero of={e}/file.txt", f"awk -i inplace 1 {e}/file.txt",
                    f"git -C {e} diff --output={e}/o", f"git -C {e} branch newbranch", f"git -C {e} config user.name x",
                    f"git -C {e} remote add x y", f"git -C {e} stash"):
            self.denied(cmd)

    def test_plain_reads_and_git_read_allowlist_still_allowed(self):
        e = self.eta_root
        for cmd in (f"find {e} -name file.txt", f"sort {e}/file.txt", f"cat {e}/file.txt", f"git -C {e} status",
                    f"git -C {e} log --oneline", f"git -C {e} diff", f"git -C {e} show HEAD", f"git -C {e} rev-parse HEAD",
                    f"git -C {e} ls-files", f"git -C {e} branch --list", f"git -C {e} remote -v",
                    f"git -C {e} config --get remote.origin.url", f"cd {e} && git status"):
            self.allowed(cmd)


class R1_9_AmbiguousNotionFailure(HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.start(self.repo)
        self.payload = {"parent": {"data_source_id": DB}, "pages": [{"properties": {"title": "Outcome"}}]}
    sol_pass = G2Tests.sol_pass
    call = G2Tests.call
    post = G2Tests.post

    def test_ambiguous_failures_keep_receipt_and_journal_pending(self):
        for n, err in enumerate(("timeout", "connection reset by peer", "Notion MCP error: something odd")):
            key = self.sol_pass(self.payload, DB, "create")
            self.assertFalse(self.call(CREATE, self.payload, f"a{n}")[0])
            self.post(CREATE, self.payload, f"a{n}", error=err)
            self.assertEqual(receipts.load(key)["status"], "pending", err)
            self.assertEqual(receipts.read_journal()[-1]["status"], "pending", err)
            self.assertTrue(self.call(CREATE, self.payload, f"b{n}")[0])        # blocked until reconcile
            self.cli("maeng-review", ["reconcile", "--notion", receipts.read_journal()[-1]["id"], "--absent"], self.repo)
            self.assertEqual(receipts.load(key)["status"], "unconsumed")

    def test_confirmed_rejections_release_the_receipt(self):
        for n, err in enumerate(("validation_error: bad property", "object_not_found", "unauthorized",
                                 "restricted_resource", "invalid_request_url")):
            key = self.sol_pass(self.payload, DB, "create")
            self.assertFalse(self.call(CREATE, self.payload, f"c{n}")[0])
            self.post(CREATE, self.payload, f"c{n}", error=err)
            self.assertEqual(receipts.load(key)["status"], "unconsumed", err)


class R1_10_ReconcilePendingWithPageId(HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.start(self.repo)
        self.payload = {"parent": {"data_source_id": DB}, "pages": [{"properties": {"title": "Outcome"}}]}
    sol_pass = G2Tests.sol_pass
    call = G2Tests.call
    post = G2Tests.post

    def test_pending_entry_resolves_as_success_with_confirmed_page_id(self):
        key = self.sol_pass(self.payload, DB, "create")
        self.call(CREATE, self.payload, "t1")
        self.post(CREATE, self.payload, "t1", error="timeout")             # landed, but the post hook never saw it
        entry = receipts.read_journal()[0]
        self.assertEqual(entry["status"], "pending")
        out = self.cli("maeng-review", ["reconcile", "--notion", entry["id"], "--page-id", PAGE], self.repo)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("reconciled", out.stdout)
        self.assertEqual(receipts.load(key)["status"], "consumed")
        self.assertIn(PAGE.replace("-", ""), receipts.registry_ids())
        self.assertEqual(receipts.unresolved_entries(), [])

    def test_a_plain_fetch_does_not_resolve_a_pending_entry(self):
        key = self.sol_pass(self.payload, DB, "create")
        self.call(CREATE, self.payload, "t1")
        self.post(CREATE, self.payload, "t1", error="timeout")
        self.post(FETCH, {"id": PAGE}, "t2", response={"title": "Outcome"})
        self.assertEqual(receipts.load(key)["status"], "pending")


class R1_11_ReviewPromptAndEvidence(HarnessCase):
    def test_prompt_states_the_threat_model(self):
        import importlib.machinery
        import importlib.util
        from .helpers import BIN
        loader = importlib.machinery.SourceFileLoader("maeng_review_mod", str(BIN / "maeng-review"))
        spec = importlib.util.spec_from_loader("maeng_review_mod", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        for needle in ("cooperative", "not a security boundary", "disguised", "known", "fail closed"):
            self.assertIn(needle, mod.PROMPT)


def _review_cases():
    from .test_cli import ReviewRunFixture

    class R1_11_ReviewBundle(ReviewRunFixture):
        def bundle(self):
            sent = self.stdin_log.read_text()
            return json.loads(sent[sent.index("\n{") + 1:])

        def test_evidence_files_are_embedded_and_counted(self):
            ev = self.tmp / "transcript.txt"
            ev.write_text("model routing: gpt-6-astra\n")
            r = self.review("--evidence", str(ev))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(self.bundle()["evidence_files"], {str(ev): "model routing: gpt-6-astra\n"})
            ev.write_text("x" * 5000)
            self.log.unlink()
            r = self.review("--evidence", str(ev), "--max-bytes", "3000")
            self.assertEqual(r.returncode, 2)
            self.assertFalse(self.log.exists())

        def test_receipt_records_reviewed_scope_and_digest(self):
            r = self.review()
            s = receipts.load(json.loads(r.stdout)["receipt"])["verdict"]["subject"]
            self.assertEqual(s["files_reviewed"], ["app.py"])
            self.assertEqual(s["files_excluded"], [])
            self.assertEqual(s["digest"], receipts.diff_digest(self.repo, self.base, self.h, ["app.py"]))
            self.assertEqual(s["repo"], __import__("maeng.guard", fromlist=["x"]).normalize_repo(
                str(self.tmp / "repo-remote.git")))

        def test_exclusions_are_recorded_with_reason(self):
            r = self.review("--exclude", "app.py", "--exclusion-reason", "verbatim copy")
            s = receipts.load(json.loads(r.stdout)["receipt"])["verdict"]["subject"]
            self.assertEqual((s["files_reviewed"], s["files_excluded"], s["exclusion_reason"]),
                             ([], ["app.py"], "verbatim copy"))
    return R1_11_ReviewBundle


R1_11_ReviewBundle = _review_cases()
