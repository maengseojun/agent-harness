"""Regression tests for Astra round-2 findings (PR #38, MAE-220): allowlist of canonical shipping forms (A-C, H, J),
fail-closed hook input (D), verify policy (E), evidence identity (F), review receipts (G), unknown-world Notion (I)."""
import json
import stat
import sys
from unittest import mock

from maeng import evidence, gates, guard, handlers, receipts
from maeng.common import canonical, sha256
from .helpers import BIN, HOOK, HarnessCase, run
from .test_cli import ReviewRun
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

    def test_compound_commit_then_push_is_denied(self):
        """Round-2: `git commit -am wip && git push` verified the OLD commit but pushed the new one."""
        self.verified()
        self.assertDenied("git commit -am wip && git push origin feat", "canonical")
        self.assertDenied("git add -A; git commit -m x; git push origin feat", "canonical")
        self.assertDenied("git commit -m x\ngit push origin feat", "canonical")

    def test_git_config_overrides_are_denied(self):
        self.verified()
        self.assertDenied(f"git -c remote.origin.pushurl={ETA_URL} push origin feat", "canonical")
        self.assertDenied("git -c remote.origin.mirror=true push origin", "canonical")
        self.assertDenied("git -c push.followTags=true push origin feat", "canonical")
        self.assertDenied("git -c alias.p=push p origin feat", "canonical")
        self.assertDenied("git --config-env=remote.origin.pushurl=X push origin feat", "canonical")

    def test_wrappers_around_push_are_denied(self):
        self.verified()
        for cmd in ("command -- git push origin main", "env -u FOO git push origin main", "command git push origin feat",
                    "env git push origin feat", "nohup git push origin feat", "time git push origin feat",
                    "sudo git push origin feat", "exec git push origin feat", "xargs git push origin feat",
                    "FOO=1 git push origin feat", "GIT_SSH_COMMAND=x git push origin feat",
                    "bash -c 'git push origin feat'", "sh -c \"git push origin feat\"", "eval git push origin feat",
                    "find . -exec git push origin feat \\;"):
            self.assertDenied(cmd, "canonical")

    def test_shell_syntax_around_a_canonical_command_is_denied(self):
        self.verified()
        for cmd in ("git push origin feat &", "git push origin feat;", "git push origin feat | cat",
                    "git push origin feat > out.txt", "git push origin feat 2>&1", "(git push origin feat)",
                    "{ git push origin feat; }", "git push origin $(echo feat)", "git push origin `echo feat`",
                    "git push origin $BRANCH", "git push origin {feat,x}", "git push origin feat || true",
                    "echo $(git push origin feat)", "if true; then git push origin feat; fi"):
            self.assertDenied(cmd, "canonical")

    def test_non_canonical_push_flags_and_refspecs_are_denied(self):
        self.verified()
        sha = self.head(self.repo)
        for cmd in ("git push --dry-run origin feat", "git push --no-verify origin feat", "git push --tags origin feat",
                    "git push -o ci.skip origin feat", "git push origin feat other", "git push origin",
                    "git push", "git push -u", f"git push origin {sha}:feat", "git push origin feat:refs/tags/v1",
                    "git push origin +feat", "git push origin :feat", "git push origin 'refs/heads/*:refs/heads/*'",
                    "git push git@github.com:o/r.git feat", "git push /tmp/x feat", "git push ../x feat",
                    "git push origin ../feat", "git push origin -- feat", "git push origin HEAD"):
            self.assertDenied(cmd, "canonical")

    def test_gh_non_canonical_forms_are_denied(self):
        self.verified()
        for cmd in ("gh pr create --fill", "gh pr create --head feat --title t --web", "gh pr create --head feat -a me",
                    "gh pr create --head feat --title t extra", "gh -R o/r pr create --head feat --title t",
                    "GH_REPO=o/r gh pr create --head feat --title t", "gh pr create --head feat --title \"$(date)\"",
                    "gh pr create --head feat --title t && echo done", "gh pr merge 1", "gh release create v1",
                    "gh api -X POST repos/o/r/issues/1/comments -f body=hi", "gh repo sync",
                    "gh repo edit --default-branch dev"):
            self.assertDenied(cmd, "canonical")

    def test_maeng_ship_only_in_its_canonical_form(self):
        for cmd in ("maeng-ship merge 7 && echo done", "FOO=1 maeng-ship merge 7", "env maeng-ship merge 7",
                    "maeng-ship merge", "maeng-ship merge x", "maeng-ship merge 7 --force", "maeng-ship merge 7 8",
                    "maeng-ship merge 7 --remote /tmp/x", "bash -c 'maeng-ship merge 7'"):
            self.assertDenied(cmd, "canonical")

    def test_direct_github_api_writes_are_denied_but_reads_are_not(self):
        for cmd in ("curl -X POST https://api.github.com/repos/o/r/merges -d '{}'",
                    "curl -XPUT https://api.github.com/repos/o/r/contents/f -d x", "curl --request DELETE https://api.github.com/x",
                    "curl -d @f https://api.github.com/repos/o/r/git/refs", "wget --method=PUT https://api.github.com/x"):
            self.assertDenied(cmd, "canonical")
        self.assertAllowed("curl -s https://api.github.com/repos/o/r")
        self.assertAllowed("curl -X POST https://example.com/hook -d x")

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

    def test_pushurl_must_be_unset_or_equal_to_url(self):
        url = self.git(self.repo, "config", "remote.origin.url").stdout.strip()
        self.git(self.repo, "config", "remote.origin.pushurl", ETA_URL)
        self.assertDenied("git push origin feat", "pushurl")
        self.git(self.repo, "config", "remote.origin.pushurl", url)
        self.assertAllowed("git push origin feat")
        self.git(self.repo, "config", "--add", "remote.origin.pushurl", url + "2")
        self.assertDenied("git push origin feat", "pushurl")

    def test_insteadof_rewrite_to_eta_is_classified_by_the_effective_url(self):
        url = self.git(self.repo, "config", "remote.origin.url").stdout.strip()
        self.git(self.repo, "config", f"url.{ETA_URL}.insteadOf", url)
        self.assertDenied("git push origin feat", "eta")

    def test_multiple_urls_mirror_push_refspec_and_followtags_are_denied(self):
        self.git(self.repo, "config", "--add", "remote.origin.url", "/tmp/another.git")
        self.assertDenied("git push origin feat", "exactly one url")
        self.git(self.repo, "config", "--unset-all", "remote.origin.url", "another.git")
        self.assertAllowed("git push origin feat")
        self.git(self.repo, "config", "remote.origin.mirror", "true")
        self.assertDenied("git push origin feat", "mirror")
        self.git(self.repo, "config", "remote.origin.mirror", "false")
        self.assertAllowed("git push origin feat")
        self.git(self.repo, "config", "remote.origin.push", "HEAD:refs/heads/feat")
        self.assertDenied("git push origin feat", "remote.origin.push")
        self.git(self.repo, "config", "--unset-all", "remote.origin.push")
        self.git(self.repo, "config", "push.followTags", "true")
        self.assertDenied("git push origin feat", "followTags")

    def test_unknown_remote_default_branch_is_denied_with_fix_hint(self):
        self.git(self.repo, "remote", "set-head", "origin", "--delete")
        denied, reason = self.bash_pre(self.repo, "git push origin feat")
        self.assertTrue(denied)
        self.assertIn("git remote set-head origin --auto", reason)
        self.git(self.repo, "remote", "set-head", "origin", "main")
        self.assertAllowed("git push origin feat")

    def test_remote_default_branch_other_than_main_is_protected(self):
        self.git(self.repo, "push", "-q", "origin", "feat:develop")
        self.git(self.repo, "fetch", "-q", "origin")
        self.git(self.tmp / "repo-remote.git", "symbolic-ref", "HEAD", "refs/heads/develop")  # the server's default
        self.git(self.repo, "remote", "set-head", "origin", "develop")
        self.assertDenied("git push origin feat:develop", "default branch")
        self.assertAllowed("git push origin feat")

    def test_remote_must_be_a_configured_name(self):
        self.assertDenied("git push nosuch feat", "exactly one url")


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

    def test_git_dir_and_work_tree_space_and_equals_forms_resolve_the_target(self):
        e = self.e
        for cmd in (f"git --git-dir {e}/.git --work-tree {e} commit --allow-empty -m x",
                    f"git --git-dir={e}/.git --work-tree={e} commit --allow-empty -m x",
                    f"git --work-tree {e} add -A", f"git --git-dir {e}/.git add -A", f"git -C {e} commit -m x",
                    f"cd {e} && git commit -m x"):
            self.denied(cmd, "eta")

    def test_git_dir_selectors_to_an_unresolvable_target_are_denied(self):
        self.denied("git --git-dir /nonexistent-zzz/x/.git --work-tree /nonexistent-zzz/x commit -m x")

    def test_read_only_git_on_eta_and_own_git_dir_stay_allowed(self):
        e = self.e
        self.allowed(f"git --git-dir {e}/.git status")
        self.allowed(f"git -C {e} log --oneline")
        self.allowed("git --git-dir .git status")
        self.allowed("git --git-dir=.git commit --allow-empty -m x")

    def test_git_dir_environment_assignments_are_denied_for_any_git_command(self):
        e = self.e
        for cmd in (f"GIT_DIR={e}/.git git status", f"GIT_WORK_TREE={e} git commit -m x", f"env GIT_DIR={e}/.git git log",
                    f"export GIT_DIR={e}/.git; git status", "GIT_DIR=.git git status"):
            self.denied(cmd, "GIT_DIR")
        self.allowed("GIT_PAGER=cat git log --oneline")

    def test_gh_url_arguments_and_repo_flag_are_resolved(self):
        eta = "https://github.com/endix-foundation-v1/x"
        for cmd in (f"gh issue comment {eta}/issues/1 -b hi", f"gh pr comment {eta}/pull/2 -b hi",
                    f"gh pr edit {eta}/pull/2 --title t", f"gh issue close {eta}/issues/1",
                    "gh pr comment 1 -R endix-foundation-v1/x -b hi", "gh issue create --repo endix-foundation-v1/x -t t -b b",
                    "gh issue comment https://github.com/maengseojun/eta_v1/issues/3 -b hi"):
            self.denied(cmd)
        self.allowed(f"gh issue view {eta}/issues/1")                       # read-only on eta stays allowed
        self.allowed("gh issue comment https://github.com/o/r/issues/1 -R o/r -b hi")
        self.allowed("gh pr comment 1 -R o/r -b hi")


class R2_C_UnknownClassification(HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        (self.repo / ".claude").mkdir()
        (self.repo / ".claude/settings.json").write_text("{ not json")      # checkout can no longer be classified
        self.assertEqual(guard.classify(self.repo), guard.UNKNOWN)

    def test_every_non_read_only_bash_command_is_denied(self):
        for cmd in ("touch marker.txt", "echo hi > marker.txt", "cp README.md copy.md", "mkdir d", "python3 -c 1",
                    "pytest", "git commit --allow-empty -m x", "git add -A", "sed -i s/a/b/ app.py", "rm app.py"):
            denied, reason = self.bash_pre(self.repo, cmd)
            self.assertTrue(denied, cmd)
            self.assertIn("cannot classify", reason)

    def test_read_only_commands_still_run(self):
        for cmd in ("ls", "cat app.py", "git status", "git log --oneline", "pwd", "grep hi app.py"):
            denied, reason = self.bash_pre(self.repo, cmd)
            self.assertFalse(denied, f"{cmd}: {reason}")

    def test_mcp_writes_are_denied(self):
        base = {"owner": "o", "repo": "r"}
        for tool, tin in (("mcp__github__add_issue_comment", {**base, "issue_number": 1, "body": "x"}),
                          ("mcp__github__create_pull_request", {**base, "head": "feat", "base": "main", "title": "t"}),
                          ("mcp__claude_ai_Notion__notion-update-page", {"page_id": "a" * 32})):
            denied, reason = self.pre(self.repo, tool, tin)
            self.assertTrue(denied, tool)
        self.assertFalse(self.pre(self.repo, "mcp__github__get_issue", {**base, "issue_number": 1})[0])

    def test_effective_directory_unknown_after_cd_is_denied_while_session_is_personal(self):
        ok = self.make_repo("ok")
        bad = self.make_repo("bad")
        (bad / ".claude").mkdir()
        (bad / ".claude/settings.json").write_text("{ not json")
        self.start(ok)
        d, reason = self.bash_pre(ok, f"cd {bad} && touch marker.txt")
        self.assertTrue(d)
        self.assertIn("cannot classify", reason)
        self.assertFalse(self.bash_pre(ok, "touch marker.txt")[0])


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

    def test_invalid_policy_denies_shipping(self):
        for bad in ("{ broken", "[]", "null", '"required"', '{"required": "pytest"}', '{"required": [1]}',
                    '{"non_code_globs": {"a": 1}}', '{"protected_branches": "main"}', '{"formatter": "ruff"}', ""):
            self.write_policy(bad)
            self.verified()
            denied, reason = self.bash_pre(self.repo, "git push origin feat")
            self.assertTrue(denied, bad)
            self.assertIn("invalid verification policy", reason, bad)

    def test_unreadable_policy_denies_shipping(self):
        self.write_policy("{}")
        self.verified()
        self.assertAllowed("git push origin feat")
        path = self.repo / ".maeng/verify.json"
        path.chmod(0)
        self.addCleanup(path.chmod, stat.S_IRUSR | stat.S_IWUSR)
        denied, reason = self.bash_pre(self.repo, "git push origin feat")
        self.assertTrue(denied)
        self.assertIn("invalid verification policy", reason)

    def test_fixed_policy_ships_again(self):
        self.write_policy("{ broken")
        self.verified()
        self.assertTrue(self.bash_pre(self.repo, "git push origin feat")[0])
        self.write_policy('{"required": ["pytest"]}')
        self.verified()
        self.assertAllowed("git push origin feat")


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

    def test_npx_help_is_not_evidence(self):
        self.run_check(self.repo, "npx playwright test --help")
        self.assertEqual(self.load_state()["evidence"], [])
        self.assertTrue(self.bash_pre(self.repo, "git push origin feat")[0])

    def test_working_directory_is_part_of_the_identity(self):
        self.policy(["pytest"])
        self.run_check(self.repo, "cd tests/unit && pytest")
        ev = self.load_state()["evidence"][-1]
        self.assertEqual((ev["identity"], ev["dir"]), ("pytest@tests/unit", "tests/unit"))
        denied, reason = self.bash_pre(self.repo, "git push origin feat")
        self.assertTrue(denied)
        self.assertIn("required check not passed on this tree: pytest", reason)
        self.run_check(self.repo, "pytest")
        self.assertEqual(self.load_state()["evidence"][-1]["identity"], "pytest")
        self.assertAllowed("git push origin feat")

    def test_session_started_in_a_subdirectory_records_that_directory(self):
        self.policy(["pytest"])
        self.run_check(self.repo / "tests/unit", "pytest")
        self.assertEqual(self.load_state()["evidence"][-1]["identity"], "pytest@tests/unit")
        self.assertTrue(self.bash_pre(self.repo, "git push origin feat")[0])

    def test_requirement_in_a_subdirectory_needs_that_directory(self):
        self.policy(["cd tests/unit && pytest"])
        self.run_check(self.repo, "pytest")
        self.assertTrue(self.bash_pre(self.repo, "git push origin feat")[0])
        self.run_check(self.repo, "cd tests/unit && pytest")
        self.assertAllowed("git push origin feat")

    def test_compound_requirement_needs_every_constituent(self):
        for required in ("pytest && ruff check .", "pytest; ruff check ."):
            self.policy([required])
            self.run_check(self.repo, "pytest")
            denied, reason = self.bash_pre(self.repo, "git push origin feat")
            self.assertTrue(denied, required)
            self.assertIn("required check not passed", reason)
            self.run_check(self.repo, "ruff check .")
            self.assertAllowed("git push origin feat")

    def test_compound_requirement_is_met_by_one_compound_run_and_not_by_a_different_ruff(self):
        self.policy(["pytest && ruff check ."])
        self.run_check(self.repo, "ruff check src")
        self.run_check(self.repo, "pytest")
        self.assertTrue(self.bash_pre(self.repo, "git push origin feat")[0])
        self.run_check(self.repo, "pytest && ruff check .")
        self.assertAllowed("git push origin feat")


class R2_G_ReviewRevocationAndDelegation(ReviewRun):
    def setUp(self):
        super().setUp()
        (self.repo / "lib.py").write_text("x = 1\n")
        self.h = self.commit_all(self.repo, "lib")

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


class R2_H_PullRequestRemoteHead(ShipBase):
    def setUp(self):
        super().setUp()
        self.alias_origin()

    def push_unverified_commit(self):
        (self.repo / "app.py").write_text("print('unverified')\n")
        self.commit_all(self.repo, "unverified")
        self.git(self.repo, "push", "-q", "origin", "feat")

    def test_gh_pr_create_denied_when_the_remote_head_is_not_the_verified_commit(self):
        self.verified()
        self.assertAllowed("gh pr create -R o/r --head feat --title t --body b")
        self.push_unverified_commit()                      # remote head advanced to an unverified tree
        self.assertDenied("gh pr create -R o/r --head feat --title t --body b", "not ship-verified")
        self.assertDenied("gh pr create -R o/r --title t --body b", "not ship-verified")

    def test_remote_head_advanced_by_someone_else_is_denied(self):
        self.verified()
        other = self.tmp / "other"
        self.git(self.tmp, "clone", "-q", str(self.tmp / "repo-remote.git"), str(other))
        self.git(other, "checkout", "-q", "feat")
        (other / "evil.py").write_text("x = 1\n")
        self.git(other, "add", "-A")
        self.git(other, "commit", "-qm", "theirs")
        self.git(other, "push", "-q", "origin", "feat")
        self.assertDenied("gh pr create -R o/r --head feat --title t --body b", "not ship-verified")

    def test_unpushed_local_branch_is_denied(self):
        self.verified()
        self.git(self.repo, "checkout", "-qb", "local-only")
        self.assertDenied("gh pr create -R o/r --head local-only --title t --body b", "cannot establish the remote head")

    def test_ls_remote_failure_is_denied(self):
        self.verified()
        fake = self.tmp / "dead-git"
        fake.write_text(f"#!{sys.executable}\nimport sys\nprint('fatal: unable to access', file=sys.stderr)\nsys.exit(128)\n")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        self.env["MAENG_GIT"] = str(fake)
        self.assertDenied("gh pr create -R o/r --head feat --title t --body b", "cannot establish the remote head")

    def test_repo_flag_must_name_origin_repository(self):
        self.verified()
        denied, reason = self.bash_pre(self.repo, "gh pr create -R x/y --head feat --title t --body b")
        self.assertTrue(denied)
        self.assertIn("must name origin's repository", reason)
        self.assertAllowed("gh pr create --repo o/r --head feat --title t --body b")

    def test_cross_repository_head_is_denied(self):
        self.verified()
        self.assertDenied("gh pr create -R o/r --head someone:feat --title t --body b", "cross-repository")

    def test_mcp_create_pull_request_checks_the_remote_head_too(self):
        self.verified()
        tin = {"owner": "o", "repo": "r", "head": "feat", "base": "main", "title": "t"}
        self.assertFalse(self.pre(self.repo, "mcp__github__create_pull_request", tin)[0])
        self.push_unverified_commit()
        denied, reason = self.pre(self.repo, "mcp__github__create_pull_request", tin)
        self.assertTrue(denied)
        self.assertIn("not ship-verified", reason)
        denied, _ = self.pre(self.repo, "mcp__github__create_pull_request", {**tin, "repo": "other"})
        self.assertTrue(denied)                            # unreachable repository: cannot establish the head


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

    def test_notion_write_with_a_matching_receipt_is_denied_when_unknown(self):
        key = self.sol_pass(self.payload, DB, "create")
        self.break_classification()
        denied, reason = self.call(CREATE, self.payload, "u1")
        self.assertTrue(denied)
        self.assertIn("cannot classify", reason)
        self.assertEqual(receipts.load(key)["status"], "unconsumed")
        self.assertEqual(receipts.read_journal(), [])
        (self.repo / ".claude/settings.json").unlink()
        self.assertFalse(self.call(CREATE, self.payload, "u2")[0])       # classifiable again: normal G2 path

    def test_every_notion_write_tool_is_denied_when_unknown(self):
        self.break_classification()
        for name in ("notion-create-pages", "notion-update-page", "notion-update-data-source", "notion-move-pages",
                     "notion-create-database", "notion-delete-pages"):
            self.assertTrue(self.pre(self.repo, "mcp__claude_ai_Notion__" + name, {"page_id": "a" * 32})[0], name)
        self.assertFalse(self.pre(self.repo, "mcp__claude_ai_Notion__notion-search", {"query": "x"})[0])

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
    def test_prompt_states_the_allowlist_design(self):
        import importlib.machinery
        import importlib.util
        loader = importlib.machinery.SourceFileLoader("maeng_review_mod2", str(BIN / "maeng-review"))
        spec = importlib.util.spec_from_loader("maeng_review_mod2", loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        for needle in ("ALLOWLIST of canonical forms", "denied by design", "allowlist is closed", "canonical form",
                       "git push [-u] <remote>", "gh pr create", "maeng-ship merge <N>", "files_delegated"):
            self.assertIn(needle, mod.PROMPT)
