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


class R1_5_ControlStructures(ShipBase):
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

    def test_identity_normalizes_whitespace_and_verbosity_only(self):
        ident = lambda c: evidence.recognize(c)["checks"][0][2]
        self.assertEqual(ident("pytest   -q "), "pytest")
        self.assertEqual(ident("python3 -m pytest -vv tests/unit"), "pytest tests/unit")
        self.assertEqual(ident("uv run pytest  -k  foo"), "pytest -k foo")
        self.assertEqual(evidence.recognize("cd packages && cd api && pytest")["cd"], "packages/api")
        self.assertIsNone(evidence.recognize("mypy @args.txt"))
        self.assertIsNone(evidence.recognize("(pytest) &"))
        self.assertIsNotNone(evidence.recognize("pytest 2>&1"))
        self.assertEqual(evidence.parse_requirement("cd packages && cd api && pytest")[0][1], "packages/api")

    def test_glob_requirement_accepts_matching_identity(self):
        self.policy(["pytest tests/*"])
        self.run_check(self.repo, "pytest tests/unit")
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

    def test_plain_reads_and_git_read_allowlist_still_allowed(self):
        e = self.eta_root
        for cmd in (f"find {e} -name file.txt", f"sort {e}/file.txt", f"cat {e}/file.txt", f"git -C {e} status",
                    f"git -C {e} log --oneline", f"git -C {e} diff", f"git -C {e} show HEAD", f"git -C {e} rev-parse HEAD",
                    f"git -C {e} ls-files", f"git -C {e} branch --list", f"git -C {e} remote -v",
                    f"git -C {e} config --get remote.origin.url", f"cd {e} && git status"):
            self.allowed(cmd)


class R1_11_ReviewPromptAndEvidence(HarnessCase):
    def test_prompt_states_the_threat_model(self):
        import importlib.machinery
        import importlib.util
        from .helpers import BIN
        loader = importlib.machinery.SourceFileLoader("maeng_review_mod", str(BIN / "maeng-review"))
        spec = importlib.util.spec_from_loader("maeng_review_mod", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        for needle in ("cooperative", "seatbelt", "disguised", "Out of scope and NOT findings", "in-scope path"):
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
