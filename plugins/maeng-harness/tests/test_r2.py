"""Regression tests for Astra round-2 findings (PR #38, MAE-220): allowlist of canonical shipping forms (A-C, H, J),
fail-closed hook input (D), verify policy (E), evidence identity (F), review receipts (G), unknown-world Notion (I)."""
import json
import stat
import sys
from unittest import mock

from maeng import evidence, gates, guard, handlers, receipts
from maeng.common import canonical, sha256
from .helpers import BIN, HOOK, HarnessCase, run
from .test_cli import ReviewRunFixture
from .test_g1 import ShipBase
from .test_g2_g3 import CREATE, DB, G2Tests
from .test_merge import MergeBase

ETA_URL = "git@github.com:endix-foundation-v1/web.git"


class R2_A_CanonicalShippingForms(ShipBase):
    def test_canonical_forms_are_allowed_when_verified(self):
        self.verified()
        self.alias_origin()
        for cmd in ("git push origin feat", "git push -u origin feat", "git push --set-upstream origin feat",
                    "git push origin feat:feat", "git push origin feat:refs/heads/feat",
                    "gh pr create -R o/r --head feat --title t --body b", "gh pr create -R o/r -H feat -t t -b b -d -B main",
                    "gh pr create --repo=o/r --head=feat --title='a title' --body-file=body.md",
                    "gh pr view 1", "gh pr comment 1 -R o/r -b hi", "gh issue create -R o/r -t x -b y", "ls && echo hi",
                    "maeng-ship merge 7", "maeng-ship merge 7 --remote origin", "maeng-ship --session s1 merge 7"):
            self.assertAllowed(cmd)

    def test_mentions_inside_data_are_not_routes(self):
        self.assertAllowed("echo git push origin main")
        self.assertAllowed("git log --grep='git push' --oneline")
        self.assertAllowed("cat bin/maeng-ship")
        self.assertAllowed("git add bin/maeng-ship")


class R2_B_PlainRemoteConfig(ShipBase):
    def setUp(self):
        super().setUp()
        self.verified()
        self.assertAllowed("git push origin feat")

    def test_remote_default_branch_other_than_main_is_protected(self):
        self.git(self.repo, "push", "-q", "origin", "feat:develop")
        self.git(self.repo, "fetch", "-q", "origin")
        self.git(self.tmp / "repo-remote.git", "symbolic-ref", "HEAD", "refs/heads/develop")  # the server's default
        self.git(self.repo, "remote", "set-head", "origin", "develop")
        self.assertDenied("git push origin feat:develop", "default branch")
        self.assertAllowed("git push origin feat")

class R2_B_MergeRemoteConfig(MergeBase):
    def ship_denied(self, text):
        self.verdict()
        r = self.ship()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn(text, r.stderr)
        self.assertEqual(self.remote_main(), self.base)

    def test_maeng_ship_refuses_mirror_remote(self):
        self.git(self.repo, "config", "remote.origin.mirror", "true")
        self.ship_denied("mirror")

    def test_maeng_ship_refuses_unknown_default_branch(self):
        self.git(self.repo, "remote", "set-head", "origin", "--delete")
        self.ship_denied("set-head origin --auto")

    def test_maeng_ship_refuses_pushurl_and_push_refspec_and_followtags(self):
        self.git(self.repo, "config", "remote.origin.pushurl", "/tmp/elsewhere.git")
        self.ship_denied("pushurl")
        self.git(self.repo, "config", "--unset-all", "remote.origin.pushurl")
        self.git(self.repo, "config", "push.followTags", "true")
        self.ship_denied("followTags")

    def test_maeng_ship_still_merges_with_a_plain_remote_and_uses_the_canonical_lease_form(self):
        key = self.verdict()
        record = self.tmp / "git-argv.json"
        fake = self.fake_git("rec-git", f"import json\nopen({str(record)!r}, 'w').write(json.dumps(sys.argv[1:]))\n"
                                        f"subprocess.run(['git'] + sys.argv[1:])")
        r = self.ship(MAENG_GIT=fake)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(record.read_text()),
                         ["push", f"--force-with-lease=refs/heads/main:{self.base}", "origin", f"{self.h}:refs/heads/main"])
        self.assertEqual(self.status(key), "consumed")


class R2_C_G3Targets(HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.eta_root.mkdir()
        (self.eta_root / "file.txt").write_text("eta")
        self.start(self.repo)
        self.e = self.eta_root

    def denied(self, cmd, text=None):
        d, reason = self.bash_pre(self.repo, cmd)
        self.assertTrue(d, f"expected deny: {cmd} ({reason})")
        if text:
            self.assertIn(text, reason)

    def allowed(self, cmd):
        d, reason = self.bash_pre(self.repo, cmd)
        self.assertFalse(d, f"expected allow: {cmd} ({reason})")

    def test_read_only_git_on_eta_and_own_git_dir_stay_allowed(self):
        e = self.e
        self.allowed(f"git --git-dir {e}/.git status")
        self.allowed(f"git -C {e} log --oneline")
        self.allowed("git --git-dir .git status")
        self.allowed("git --git-dir=.git commit --allow-empty -m x")

class R2_C_UnknownClassification(HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        (self.repo / ".claude").mkdir()
        (self.repo / ".claude/settings.json").write_text("{ not json")      # checkout can no longer be classified
        self.assertEqual(guard.classify(self.repo), guard.UNKNOWN)

    def test_read_only_commands_still_run(self):
        for cmd in ("ls", "cat app.py", "git status", "git log --oneline", "pwd", "grep hi app.py"):
            denied, reason = self.bash_pre(self.repo, cmd)
            self.assertFalse(denied, f"{cmd}: {reason}")

class R2_D_HookInputFailsClosed(HarnessCase):
    def feed(self, text):
        proc = run([sys.executable, str(HOOK)], env=self.env, input_text=text, check=False)
        return proc.returncode, proc.stderr

    def test_unreadable_pretooluse_input_exits_2(self):
        for text in ("", "not json", "{", "[]", "null", "42", '"PreToolUse"', "{}",
                     '{"hook_event_name": "PreToolUse", "tool_name": "Bash"',          # truncated
                     '{"hook_event_name": "PreToolUse", "tool_name": "Bash"}',          # no tool_input
                     '{"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": "git push"}',
                     '{"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": []}',
                     '{"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": null}',
                     '{"tool_name": "Bash", "tool_input": {"command": "git push origin main"}}',   # no event name
                     '{"hook_event_name": 7, "tool_input": {}}'):
            rc, err = self.feed(text)
            self.assertEqual(rc, 2, f"{text!r}: {err}")
            self.assertTrue(err.strip(), text)

    def test_other_events_with_unreadable_input_do_not_block(self):
        for text in ('{"hook_event_name": "Stop", garbage', '{"hook_event_name":"SessionStart" ,,'):
            self.assertEqual(self.feed(text)[0], 0, text)
        self.assertEqual(self.feed('{"hook_event_name": "Notification", "message": "x"}')[0], 0)

    def test_well_formed_pretooluse_still_works(self):
        repo = self.make_repo()
        self.assertFalse(self.bash_pre(repo, "ls")[0])

    def test_handler_denies_a_non_object_tool_input(self):
        out = handlers.on_pre({"hook_event_name": "PreToolUse", "session_id": "s", "cwd": str(self.tmp),
                               "tool_name": "Bash", "tool_input": "git push origin main"})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")


class R2_E_VerifyPolicy(ShipBase):
    def write_policy(self, text):
        (self.repo / ".maeng").mkdir(exist_ok=True)
        (self.repo / ".maeng/verify.json").write_text(text)
        self.commit_all(self.repo, "policy")

    def test_missing_policy_uses_defaults(self):
        self.verified()
        self.assertAllowed("git push origin feat")
        self.assertIsNone(__import__("maeng.tree", fromlist=["x"]).load_policy(self.repo)["invalid"])

class R2_F_EvidenceIdentity(ShipBase):
    def policy(self, required):
        (self.repo / ".maeng").mkdir(exist_ok=True)
        (self.repo / ".maeng/verify.json").write_text(json.dumps({"required": required}))
        (self.repo / "tests/unit").mkdir(parents=True, exist_ok=True)
        (self.repo / "tests/unit/test_a.py").write_text("def test_a(): pass\n")
        self.commit_all(self.repo, "policy")

    def test_launcher_options_are_stripped_but_runner_args_are_kept(self):
        self.assertIsNone(evidence.recognize("npx playwright test --help"))
        self.assertIsNone(evidence.recognize("npx -y playwright test --help"))
        self.assertIsNone(evidence.recognize("npx --yes -p @playwright/test playwright test -h"))
        self.assertIsNone(evidence.recognize("pnpm dlx playwright test --list-tests"))
        self.assertIsNone(evidence.recognize("yarn dlx playwright test --help"))
        self.assertIsNone(evidence.recognize("npx -c 'playwright test'"))
        self.assertEqual(evidence.recognize("npx -y playwright test tests/e2e")["checks"][0][2],
                         "playwright test tests/e2e")
        self.assertEqual(evidence.recognize("pnpm dlx playwright test")["checks"][0][2], "playwright test")

class R2_G_ReviewRevocationAndDelegation(ReviewRunFixture):
    def setUp(self):
        super().setUp()
        (self.repo / "lib.py").write_text("x = 1\n")
        self.h = self.commit_all(self.repo, "lib")
        self.run_check(self.repo, "pytest -q")  # reviews need a ship-verified head
        self.cli("maeng-verify", ["plan", "--met", "AC-1"], self.repo)

    def subject(self, key):
        return receipts.load(key)["verdict"]["subject"]

    def find(self, key):
        s = self.subject(key)
        return receipts.find_code(self.repo, s["repo"], self.base, self.h, "refs/heads/main", s["criteria_rev"])

    def set_verdict(self, verdict):
        self.result.write_text(json.dumps({"verdict": verdict, "findings": [] if verdict == "pass" else [
            {"severity": "high", "title": "bug", "body": "b", "file": "app.py", "line": 1}]}))

    def test_failed_re_review_revokes_the_earlier_unconsumed_pass(self):
        for verdict in ("fail", "blocked"):
            self.set_verdict("pass")
            key = json.loads(self.review().stdout)["receipt"]
            self.assertEqual(self.find(key)[1], "", verdict)
            self.set_verdict(verdict)
            self.assertEqual(self.review("--path", "lib.py").returncode, 1)     # a different file scope: other key
            rec = receipts.load(key)
            self.assertEqual(rec["revoked"]["by"], verdict)
            self.assertIn("revoked:" + verdict, [h["event"] for h in rec["history"]])
            recs, problem = self.find(key)
            self.assertIsNone(recs)
            self.assertIn("revoked", problem)

    def test_a_newer_pass_after_a_failure_is_usable_again(self):
        key = json.loads(self.review().stdout)["receipt"]
        self.set_verdict("fail")
        self.assertEqual(self.review().returncode, 1)
        self.assertIsNone(self.find(key)[0])
        self.set_verdict("pass")
        self.assertEqual(json.loads(self.review().stdout)["receipt"], key)
        self.assertNotIn("revoked", receipts.load(key))
        self.assertEqual(self.find(key)[1], "")

    def test_revocation_leaves_other_heads_and_consumed_receipts_alone(self):
        key = json.loads(self.review().stdout)["receipt"]
        receipts.begin(key, {"x": 1})
        receipts.consume(key, {"merge_sha": self.h})
        self.set_verdict("fail")
        self.review("--path", "lib.py")
        rec = receipts.load(key)
        self.assertEqual(rec["status"], "consumed")
        self.assertNotIn("revoked", rec)

    def test_store_of_a_fail_verdict_revokes_too(self):
        key = json.loads(self.review().stdout)["receipt"]
        v = receipts.load(key)["verdict"]
        other = {**v, "verdict": "fail", "subject": {**v["subject"], "files_reviewed": ["lib.py"],
                                                      "digest": receipts.diff_digest(self.repo, self.base, self.h, ["lib.py"])},
                 "findings": [{"severity": "high", "title": "t", "body": "b", "file": None, "line": None}]}
        receipts.store_verdict(other)
        self.assertIn("revoked", receipts.load(key))

    def test_delegated_files_are_recorded_and_not_covered_by_the_receipt(self):
        r = self.review("--delegate", "lib.py", "--exclude", "README.md")
        self.assertEqual(r.returncode, 0, r.stderr)
        key = json.loads(r.stdout)["receipt"]
        s = self.subject(key)
        self.assertEqual((s["files_reviewed"], s["files_delegated"], s["files_excluded"]),
                         (["app.py"], ["lib.py"], []))
        bundle = json.loads(self.stdin_log.read_text().split("BUNDLE:\n", 1)[1])
        self.assertEqual(bundle["scope"]["delegated_files"], ["lib.py"])
        recs, problem = self.find(key)
        self.assertIsNone(recs)
        self.assertIn("coverage incomplete", problem)
        self.assertIn("lib.py", problem)
        self.assertIn("files_delegated", problem)

    def test_delegated_scope_needs_another_pass_receipt(self):
        key1 = json.loads(self.review("--delegate", "lib.py").stdout)["receipt"]
        key2 = json.loads(self.review("--path", "lib.py").stdout)["receipt"]
        self.assertNotEqual(key1, key2)
        recs, problem = self.find(key1)
        self.assertEqual(problem, "")
        self.assertEqual(sorted(r["key"] for r in recs), sorted([key1, key2]))

    def test_plain_exclude_stays_exempt_under_a_parent_pass(self):
        r = self.review("--kind", "parent", "--exclude", "lib.py", "--exclusion-reason", "verbatim")
        key = json.loads(r.stdout)["receipt"]
        s = self.subject(key)
        self.assertEqual((s["files_reviewed"], s["files_excluded"], s.get("files_delegated")), (["app.py"], ["lib.py"], []))
        self.assertEqual(self.find(key)[1], "")

    def test_delegating_a_parent_exclusion_removes_the_exemption(self):
        r = self.review("--kind", "parent", "--delegate", "lib.py")
        key = json.loads(r.stdout)["receipt"]
        self.assertIsNone(self.find(key)[0])


class R2_G_DelegatedSubjectInShipFlow(MergeBase):
    def store_subject(self, files, delegated=()):
        v = {"verdict": "pass", "reviewer": {"model": "gpt-6-astra", "effort": "xhigh"}, "findings": [],
             "subject": {"kind": "parent", "repo": str(self.remote.resolve()), "pr": 7, "base": self.base,
                         "head": self.h, "criteria_rev": None, "digest": self.digest(self.base, self.h, files),
                         "destination": "refs/heads/main", "op": "merge", "files_reviewed": files,
                         "files_excluded": list(delegated), "files_delegated": list(delegated),
                         "exclusion_reason": None}}
        f = self.tmp / "v.json"
        f.write_text(json.dumps(v))
        r = self.cli("maeng-review", ["store", str(f)], self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def test_ship_is_denied_until_the_delegated_file_has_its_own_receipt(self):
        k1 = self.store_subject(["app.py"], delegated=["lib.py"])      # even if it also lists it as excluded
        r = self.ship()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("coverage incomplete", r.stderr)
        self.assertIn("lib.py", r.stderr)
        self.assertEqual(self.remote_main(), self.base)
        k2 = self.verdict(files=["lib.py"])
        r = self.ship()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.status(k1), self.status(k2)), ("consumed", "consumed"))


class R2_I_UnknownWorldNotion(HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.start(self.repo)
        self.payload = {"parent": {"data_source_id": DB}, "pages": [{"properties": {"title": "Outcome"}}]}
    sol_pass = G2Tests.sol_pass
    call = G2Tests.call
    post = G2Tests.post

    def break_classification(self):
        (self.repo / ".claude").mkdir(exist_ok=True)
        (self.repo / ".claude/settings.json").write_text("{ not json")
        self.assertEqual(guard.classify(self.repo), guard.UNKNOWN)

    def test_an_allowed_g2_write_is_never_left_unreserved_in_a_non_personal_world(self):
        key = self.sol_pass(self.payload, DB, "create")
        self.break_classification()
        intent = {"entry": "e1"}
        entry = {"id": "e1", "tool_use_id": "w1", "digest": "d", "op": "create", "destination": DB, "key": key}
        dec = gates.Decision(True, "", [("journal_pending", entry), ("receipt_pending", key, intent)])
        with mock.patch.object(gates, "evaluate", return_value=dec):
            out = handlers.on_pre({"hook_event_name": "PreToolUse", "session_id": self.sid, "cwd": str(self.repo),
                                   "tool_name": CREATE, "tool_input": self.payload, "tool_use_id": "w1"})
        self.assertIsNone(out)
        self.assertEqual(receipts.load(key)["status"], "pending")
        self.assertEqual(receipts.read_journal()[0]["status"], "pending")


class R2_J_ReviewerPrompt(HarnessCase):
    def test_prompt_states_the_slim_gate_design(self):
        import importlib.machinery
        import importlib.util
        loader = importlib.machinery.SourceFileLoader("maeng_review_mod2", str(BIN / "maeng-review"))
        spec = importlib.util.spec_from_loader("maeng_review_mod2", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        for needle in ("SLIM by design", "audit the gate only when", "state changed earlier in the same command", "AFTER THE FACT", "MAENG_TEST_FIXTURES", "maeng-ship merge <N>", "files_delegated",
                       "tool_reference", "needs-external-check", "--tool-ref", "tool_reference is null",
                       "never\nby itself a reason for fail or blocked", "not blocked."):
            self.assertIn(needle, mod.PROMPT)
