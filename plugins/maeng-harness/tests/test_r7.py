"""Regression tests for the round-7 findings (PR #38, MAE-216): fail-closed parsing (A), receipt provenance (B), runner
wrappers (C), gh api graphql (D), GitHub MCP allowlist (E), unresolved variables (F), git aliases (G), destructive gh
(H), MultiEdit matcher (I), zero-test / failed responses (J), narrowing flags (K), Notion structural writes (L),
quarantine tombstone (M), non-fast-forward lease (N), eta git mutations (R)."""
import json
import os
import stat
import sys
import unittest.mock
import uuid

from maeng import evidence, gates, receipts
from maeng.common import canonical, sha256
from .helpers import HarnessCase
from .test_cli import ReviewRunFixture
from .test_g1 import ShipBase
from .test_g2_g3 import DB, PAGE
from .test_merge import MergeBase

NOTION = "mcp__claude_ai_Notion__"
ETA_SLUGS = ("maengseojun/eta_v1", "endix-foundation-v1/x")


class R7_A_UnparseableFailsClosed(ShipBase):
    def test_unparseable_commands_are_denied_with_a_hint(self):
        eta = self.eta_root
        eta.mkdir()
        deep = "echo " + "$(echo " * 7 + "x" + ")" * 7
        for cmd in (f"cat <<\\EOF > {eta}/f\nx\nEOF", f"cat <<\"E-OF\" > {eta}/f\nx\nE-OF", deep,
                    "cat <<\\EOF > f\nx\nEOF", "echo 'unterminated"):
            self.assertDenied(cmd, "cannot parse this command; use a simpler form")

    def test_ordinary_commands_still_parse(self):
        self.assertAllowed("cat <<'EOF' > notes.txt\nx\nEOF")
        self.assertAllowed("echo $(echo $(echo x))")


class R7_B_ReceiptProvenance(MergeBase):
    def no_fixtures(self):
        self.env["MAENG_TEST_FIXTURES"] = "0"
        return {"MAENG_TEST_FIXTURES": "0"}

    def test_store_requires_the_test_switch_and_marks_fixture(self):
        extra = self.no_fixtures()
        v = self.tmp / "v.json"
        v.write_text(json.dumps({"verdict": "pass", "reviewer": {"model": "m", "effort": "high"}, "findings": [],
                                 "subject": {"kind": "code", "repo": "r", "pr": 1, "base": "a", "head": "b",
                                             "criteria_rev": None, "digest": "d", "destination": "main",
                                             "op": "merge"}}))
        r = self.cli("maeng-review", ["store", str(v)], self.repo, extra_env=extra)
        self.assertEqual(r.returncode, 2)
        self.assertIn("MAENG_TEST_FIXTURES", r.stderr)
        self.assertFalse(receipts.receipts_dir().exists() and list(receipts.receipts_dir().glob("code-*.json")))
        extra = {"MAENG_TEST_FIXTURES": "1"}
        r = self.cli("maeng-review", ["store", str(v)], self.repo, extra_env=extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = receipts.load(r.stdout.strip())
        self.assertEqual(rec["verdict"]["reviewer"]["provenance"], "fixture")

    def test_fixture_receipt_is_rejected_by_ship_and_the_lease_hook_without_the_switch(self):
        key = self.verdict()
        extra = self.no_fixtures()
        r = self.ship(**extra)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fixture", r.stderr)
        self.assertEqual(self.remote_main(), self.base)
        denied, reason = self.bash_pre(
            self.repo, f"git push --force-with-lease=refs/heads/main:{self.base} origin {self.h}:refs/heads/main")
        self.assertTrue(denied)
        self.assertIn("fixture", reason)
        self.assertEqual(self.status(key), "unconsumed")
        self.env["MAENG_TEST_FIXTURES"] = "1"
        self.assertEqual(self.ship(MAENG_TEST_FIXTURES="1").returncode, 0)

    def test_receipt_without_provenance_is_not_usable_either(self):
        key = self.verdict()
        receipts._mutate(key, lambda r: r["verdict"]["reviewer"].pop("provenance"))
        with unittest.mock.patch.dict(os.environ, {"MAENG_TEST_FIXTURES": "0"}):
            recs, why = receipts.find_code(self.repo, str(self.remote.resolve()), self.base, self.h,
                                           "refs/heads/main", None)
        self.assertIsNone(recs)
        self.assertIn("fixture", why)


class R7_B_RunReceiptsAreUsable(ReviewRunFixture):
    def test_run_receipt_carries_review_run_provenance_and_passes_without_the_switch(self):
        r = self.review()
        self.assertEqual(r.returncode, 0, r.stderr)
        key = json.loads(r.stdout)["receipt"]
        self.assertEqual(receipts.load(key)["verdict"]["reviewer"]["provenance"], "review-run")
        s = receipts.load(key)["verdict"]["subject"]
        with unittest.mock.patch.dict(os.environ, {"MAENG_TEST_FIXTURES": "0"}):
            recs, why = receipts.find_code(self.repo, s["repo"], self.base, self.h, "refs/heads/main",
                                           s["criteria_rev"])
        self.assertIsNotNone(recs, why)

    def test_notion_fixture_receipt_needs_the_switch(self):
        payload = {"parent": {"data_source_id": DB}, "pages": [{"title": "x"}]}
        v = {"verdict": "pass", "reviewer": {"model": "gpt-6.1-sol", "effort": "medium", "provenance": "fixture"},
             "findings": [], "subject": {"kind": "notion", "repo": None, "pr": None, "base": None, "head": None,
                                         "criteria_rev": None, "digest": sha256(canonical(payload)),
                                         "destination": DB, "op": "create"}}
        receipts.store_verdict(v)
        digest = sha256(canonical(payload))
        with unittest.mock.patch.dict(os.environ, {"MAENG_TEST_FIXTURES": "0"}):
            rec, why = receipts.find_notion(digest, DB, "create")
        self.assertIsNone(rec)
        self.assertIn("fixture", why)
        rec, why = receipts.find_notion(digest, DB, "create")
        self.assertIsNotNone(rec, why)

    def review(self, *extra):
        return self.cli("maeng-review", ["run", "--kind", "code", "--pr", "7", "--base", self.base, "--head", self.h,
                                         "--base-ref", "main", *extra], self.repo,
                        extra_env={"MAENG_CODEX": str(self.codex)})


class R7_C_RunnerWrappers(HarnessCase):
    def test_wrappers_and_unsafe_assignments_are_not_evidence(self):
        for cmd in ("env pytest -q", "env PYTEST_ADDOPTS=--co pytest -q", "env PATH=$X pytest", "env -i pytest",
                    "PATH=/tmp/x pytest -q", "FOO=$BAR pytest -q", "FOO=`id` pytest", "CI=1 PYTHONPATH=x pytest",
                    "sudo pytest", "nohup pytest", "command pytest", "time pytest", "nice pytest", "exec pytest",
                    "builtin pytest", "uv run env pytest", "env python3 -m pytest -q", "CI=1 env pytest",
                    "LD_PRELOAD=x pytest", "PYTEST_PLUGINS=x pytest"):
            self.assertIsNone(evidence.recognize(cmd), cmd)
        self.assertIsNotNone(evidence.recognize("CI=1 pytest -q"))

    def test_maeng_verify_exec_refuses_env_wrapper(self):
        repo = self.make_repo()
        self.start(repo)
        r = self.cli("maeng-verify", ["exec", "--", "env", "PYTEST_ADDOPTS=--co", "python3", "-m", "pytest"], repo)
        self.assertEqual(r.returncode, 2)
        self.assertIn("not an allowlisted runner", r.stderr)
        self.assertEqual(self.load_state()["evidence"], [])


class R7_D_GraphqlInspectable(ShipBase):
    def test_uninspectable_graphql_is_a_write(self):
        for cmd in ("gh api graphql -F query=@m.graphql", "gh api graphql --input body.json",
                    "gh api graphql -f query=\"$(cat m.graphql)\"", "gh api graphql -f query='query { a }' -F variables=@f",
                    "gh api graphql -f query=\"$Q\"", "gh api graphql -F query='query { viewer { login } }'",
                    "gh api graphql --field query=@m.graphql", "gh api graphql -f owner=x",
                    "gh api graphql -f query=`cat m.graphql`",
                    "gh api graphql -f query='mutation { mergePullRequest(input:{}) { clientMutationId } }'"):
            self.assertDenied(cmd)

    def test_inspectable_literal_query_is_still_a_read(self):
        self.assertAllowed("gh api graphql -f query='query { viewer { login } }'")
        self.assertAllowed("gh api graphql --raw-field query='query($o:String!){ repository(owner:$o,name:\"r\"){id} }'"
                           " -F o=maengseojun")


class R7_E_GithubMcpAllowlist(ShipBase):
    BASE = {"owner": "o", "repo": "r"}
    READS = ("get_file_contents", "get_issue", "get_pull_request", "get_pull_request_files", "list_commits",
             "list_issues", "list_pull_requests", "search_code", "search_issues", "search_repositories",
             "search_users", "pull_request_read", "issue_read", "get_me")
    PLAIN = ("add_issue_comment", "create_issue", "update_issue", "create_pull_request_review")
    DENIED = ("delete_file", "create_branch", "update_pull_request", "create_repository", "fork_repository",
              "create_release", "push_files", "create_or_update_file", "merge_pull_request",
              "update_pull_request_branch", "frobnicate", "delete_branch", "set_default_branch")

    def call(self, name, **kw):
        return self.pre(self.repo, "mcp__github__" + name, {**self.BASE, "branch": "feat", "path": "a", "content": "b",
                                                            "message": "m", "title": "t", "body": "b", **kw})

    def test_the_tool_set_is_closed(self):
        self.verified()
        self.alias_origin()
        for name in self.READS + self.PLAIN:
            denied, reason = self.call(name)
            self.assertFalse(denied, f"{name}: {reason}")
        for name in self.DENIED:
            denied, reason = self.call(name)
            self.assertTrue(denied, name)
        for name in ("delete_file", "create_branch", "update_pull_request", "create_repository", "fork_repository",
                     "frobnicate"):
            self.assertIn("not on the allowlist", self.call(name)[1], name)
        self.assertEqual(gates.GITHUB_PLAIN_WRITES, set(self.PLAIN))
        self.assertEqual(gates.GITHUB_GATED_WRITES, {"push_files", "create_or_update_file", "merge_pull_request",
                                                     "update_pull_request_branch", "create_pull_request"})

    def test_allowed_writes_never_reach_eta(self):
        for name in self.PLAIN:
            denied, reason = self.pre(self.repo, "mcp__github__" + name, {"owner": "endix-foundation-v1", "repo": "x"})
            self.assertTrue(denied, name)
            self.assertIn("eta", reason)

    def test_gated_writes_keep_their_reasons(self):
        self.verified()
        self.assertIn("verified `git commit`", self.call("push_files")[1])
        self.assertIn("maeng-ship merge", self.call("merge_pull_request")[1])


class R7_F_UnresolvedVariables(HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.eta_root.mkdir()
        (self.eta_root / "file.txt").write_text("eta")
        self.start(self.repo)

    def denied(self, cmd, text=None):
        d, reason = self.bash_pre(self.repo, cmd)
        self.assertTrue(d, f"expected deny: {cmd} ({reason})")
        if text:
            self.assertIn(text, reason)

    def allowed(self, cmd):
        d, reason = self.bash_pre(self.repo, cmd)
        self.assertFalse(d, f"expected allow: {cmd} ({reason})")

    def test_unexpanded_variables_make_mutations_undecidable(self):
        e = self.eta_root
        self.denied(f"E={e}; touch $E/x", "cannot resolve")
        self.denied(f"export E={e}; touch ${{E}}/x")
        self.denied("touch $E/x")
        self.denied("cp app.py \"$NOPE/copy.py\"")
        self.denied("touch `echo x`")
        self.denied("echo hi > $E/x", "cannot resolve")
        self.denied("FOO=$BAR touch y")

    def test_cd_into_an_unresolved_variable_denies_mutations_until_a_literal_cd(self):
        self.denied("cd $E && touch x", "cannot determine")
        self.denied("cd $E && git commit -am x")
        self.denied("cd ${E} && echo hi > out.txt")
        self.allowed("cd $E && ls")                          # reads stay allowed
        self.allowed(f"cd $E; cd {self.repo} && touch x")   # a literal absolute cd resets the directory

    def test_resolvable_variables_and_plain_reads_are_unaffected(self):
        self.allowed("touch $HOME/x")
        self.allowed("echo $UNSET")
        self.allowed("cat $UNSET/file")
        self.allowed("awk '{print $NF}' app.py")
        self.allowed("git commit --allow-empty -m \"$(cat <<'EOF'\nfix $E things\nEOF\n)\"")
        self.allowed("touch ok.txt")


class R7_G_GitAliases(ShipBase):
    def test_repo_and_global_aliases_are_denied(self):
        self.verified()
        self.git(self.repo, "config", "alias.pushf", "push --force")
        self.git(self.repo, "config", "alias.sh", "!sh -c 'git push origin main'")
        self.git(self.repo, "config", "--global", "alias.pf", "push")
        for cmd in ("git pushf origin feat", "git sh", "git pf origin feat", "git -c alias.zz=push zz origin feat"):
            self.assertDenied(cmd)
        self.assertDenied("git pushf origin feat", "git aliases are not allowed")
        self.assertAllowed("git push origin feat")
        self.assertAllowed("git status")

    def test_unknown_subcommand_without_alias_fails_closed(self):
        """Round 8: an unknown subcommand is denied (it may be an external command that pushes)."""
        self.assertDenied("git frobnicate", "unknown git subcommand")


class R7_H_DestructiveGh(ShipBase):
    CMDS = ("gh pr close 1 --delete-branch", "gh pr close 1 -d", "gh issue delete 1", "gh repo delete {r} --yes",
            "gh repo archive {r}", "gh repo rename x", "gh release delete v1", "gh release delete v1 --cleanup-tag")

    def test_denied_for_personal_and_eta_repos(self):
        for slug in ("o/r",) + ETA_SLUGS:
            for tmpl in self.CMDS:
                cmd = tmpl.format(r=slug) + f" -R {slug}"
                self.assertDenied(cmd)
        self.assertAllowed("gh pr close 1 -R o/r")
        self.assertAllowed("gh issue close 2 -R o/r")


class R7_I_MultiEdit(HarnessCase):
    def test_multiedit_into_eta_is_denied(self):
        repo = self.make_repo()
        self.eta_root.mkdir()
        self.start(repo)
        self.assertTrue(self.pre(repo, "MultiEdit", {"file_path": str(self.eta_root / "f.py"), "edits": []})[0])
        self.assertFalse(self.pre(repo, "MultiEdit", {"file_path": str(repo / "app.py"), "edits": []})[0])


class R7_J_ZeroTestsAndFailedResponses(ShipBase):
    def respond(self, response, command="pytest -q"):
        tuid = "tu-" + uuid.uuid4().hex[:6]
        body = {"tool_name": "Bash", "tool_input": {"command": command}, "tool_use_id": tuid}
        self.hook("PreToolUse", self.repo, **body)
        self.hook("PostToolUse", self.repo, tool_response=response, **body)

    def test_zero_test_output_is_not_evidence(self):
        for out in ("Ran 0 tests in 0.000s\n\nNO TESTS RAN", "collected 0 items\n\n no tests ran in 0.01s",
                    "no tests ran", "?   \tpkg\t[no test files]"):
            self.respond({"stdout": out, "stderr": ""})
            self.assertEqual(self.load_state()["evidence"], [], out)
            self.assertEqual(self.load_state()["pending"], {}, out)
        self.assertTrue(self.bash_pre(self.repo, "git push origin feat")[0])

    def test_some_tests_ran_still_counts(self):
        self.respond({"stdout": "ok  \tpkg\t0.2s\n?   \tother\t[no test files]", "stderr": ""}, "go test ./...")
        self.assertEqual(len(self.load_state()["evidence"]), 1)
        self.respond({"stdout": "", "stderr": "Ran 3 tests in 0.1s\n\nOK"}, "python3 -m unittest discover")
        self.assertEqual(len(self.load_state()["evidence"]), 2)

    def test_unittest_discover_of_an_empty_directory_is_not_default_evidence(self):
        self.respond({"stdout": "", "stderr": "Ran 0 tests in 0.000s\n\nOK"}, "python3 -m unittest discover -s docs")
        self.assertEqual(self.load_state()["evidence"], [])

    def test_interrupted_or_error_responses_are_recorded_as_failures(self):
        for resp in ({"stdout": "ok", "interrupted": True}, {"stdout": "ok", "returnCode": 1},
                     {"stdout": "ok", "exit_code": "2"}, {"stdout": "ok", "is_error": True},
                     {"stdout": "ok", "exitCode": 130}):
            before = len(self.load_state()["evidence"])
            self.respond(resp)
            evs = self.load_state()["evidence"]
            self.assertEqual(len(evs), before + 1, resp)
            self.assertFalse(evs[-1]["ok"], resp)
        self.assertTrue(self.bash_pre(self.repo, "git push origin feat")[0])

    def test_successful_response_with_zero_exit_is_still_evidence(self):
        self.respond({"stdout": "ok", "interrupted": False, "returnCode": 0})
        self.assertTrue(self.load_state()["evidence"][-1]["ok"])

    def test_exec_of_a_runner_that_ran_zero_tests_records_nothing(self):
        fake = self.tmp / "bin"
        fake.mkdir()
        py = fake / "pytest"
        py.write_text(f"#!{sys.executable}\nprint('collected 0 items')\nprint('no tests ran in 0.01s')\n")
        py.chmod(py.stat().st_mode | stat.S_IEXEC)
        r = self.cli("maeng-verify", ["exec", "--", "pytest", "-q"], self.repo,
                     extra_env={"PATH": f"{fake}:{self.env['PATH']}"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ZERO tests", r.stderr)
        self.assertEqual(self.load_state()["evidence"], [])


class R7_K_NarrowingFlags(HarnessCase):
    def test_rejected_flags_are_never_evidence(self):
        for cmd in ("pytest --ignore=tests/slow", "pytest --ignore tests/slow", "pytest --ignore-glob=*_slow.py",
                    "pytest --deselect tests/a.py::t", "pytest --lf", "pytest --ff", "pytest --last-failed",
                    "pytest --failed-first", "pytest --nf", "pytest --sw", "python3 -m pytest -q --lf",
                    "go test -short ./...", "go test -short -run TestA", "cargo test -- --skip slow",
                    "cargo test --workspace -- --skip slow", "cargo test -- --exact t"):
            self.assertIsNone(evidence.recognize(cmd), cmd)

    def test_filtered_selectors_are_evidence_but_never_default_mode(self):
        for cmd in ("forge test --no-match-test X", "forge test --no-match-path 'test/slow/*'",
                    "forge test --no-match-contract C", "forge test --match-test A", "pytest -k fast",
                    "pytest -m unit", "go test -run TestA ./..."):
            rec = evidence.recognize(cmd)
            self.assertIsNotNone(rec, cmd)
            self.assertFalse(evidence.unfiltered(rec["checks"][0][2]), cmd)
        for cmd in ("forge test", "pytest -q", "go test ./...", "cargo test --workspace"):
            self.assertTrue(evidence.unfiltered(evidence.recognize(cmd)["checks"][0][2]), cmd)


class R7_L_NotionStructuralWrites(HarnessCase):
    PAGE_ID = PAGE.replace("-", "")
    OTHER = "cccccccc-1111-2222-3333-444455556666"

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.start(self.repo)
        self.cli("maeng-review", ["registry", "seed", PAGE], self.repo)

    def sol_pass(self, payload, dest, op):
        v = {"verdict": "pass", "reviewer": {"model": "gpt-6.1-sol", "effort": "medium"}, "findings": [],
             "subject": {"kind": "notion", "repo": None, "pr": None, "base": None, "head": None, "criteria_rev": None,
                         "digest": sha256(canonical(payload)), "destination": dest, "op": op}}
        f = self.tmp / f"v-{uuid.uuid4().hex[:6]}.json"
        f.write_text(json.dumps(v))
        r = self.cli("maeng-review", ["store", str(f)], self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)

    def call(self, name, tin, tuid="n1"):
        return self.pre(self.repo, NOTION + name, tin, tool_use_id=tuid)

    def test_delete_pages_of_a_registered_page_needs_a_delete_receipt(self):
        tin = {"page_ids": [PAGE], "user_confirmed": True}
        denied, reason = self.call("notion-delete-pages", tin)
        self.assertTrue(denied)
        self.assertIn("no Sol pass receipt", reason)
        self.sol_pass(tin, self.PAGE_ID, "move")           # the wrong op is not enough
        self.assertTrue(self.call("notion-delete-pages", tin)[0])
        self.sol_pass(tin, self.PAGE_ID, "delete")
        self.assertFalse(self.call("notion-delete-pages", tin)[0])

    def test_move_pages_from_or_into_a_protected_target_is_gated(self):
        moved = {"page_or_database_ids": [PAGE], "new_parent": {"type": "page_id", "page_id": self.OTHER}}
        self.assertTrue(self.call("notion-move-pages", moved)[0])
        into_db = {"page_or_database_ids": [self.OTHER], "new_parent": {"type": "data_source_id", "data_source_id": DB}}
        self.assertTrue(self.call("notion-move-pages", into_db)[0])
        self.sol_pass(into_db, DB, "move")
        self.assertFalse(self.call("notion-move-pages", into_db)[0])

    def test_database_level_writes_are_gated(self):
        self.assertTrue(self.call("notion-update-data-source", {"data_source_id": DB, "title": "x"})[0])
        self.assertTrue(self.call("notion-delete-databases", {"database_ids": [DB]})[0])
        self.assertTrue(self.call("notion-create-database", {"parent": {"type": "page_id", "page_id": PAGE},
                                                             "title": "t", "schema": "CREATE TABLE (\"Name\" TITLE)"})[0])
        tin = {"data_source_id": DB, "title": "x"}
        self.sol_pass(tin, DB, "update")
        self.assertFalse(self.call("notion-update-data-source", tin)[0])

    def test_unrelated_pages_and_databases_are_not_gated(self):
        self.assertFalse(self.call("notion-delete-pages", {"page_ids": [self.OTHER]})[0])
        self.assertFalse(self.call("notion-move-pages", {"page_or_database_ids": [self.OTHER],
                                                         "new_parent": {"type": "workspace"}})[0])
        self.assertFalse(self.call("notion-create-database", {"title": "t", "database_type": "tasks"})[0])

    def test_an_unresolved_journal_entry_blocks_structural_writes_too(self):
        tin = {"page_ids": [PAGE]}
        self.sol_pass(tin, self.PAGE_ID, "delete")
        self.assertFalse(self.call("notion-delete-pages", tin, "n1")[0])
        self.assertEqual(receipts.read_journal()[0]["status"], "pending")
        self.hook("PostToolUse", self.repo, tool_name=NOTION + "notion-delete-pages", tool_input=tin,
                  tool_use_id="n1", tool_response={})
        self.assertEqual(receipts.read_journal()[0]["status"], "sent")        # tracked like update-page


class R7_M_QuarantineTombstone(HarnessCase):
    def test_quarantined_session_is_denied_everywhere(self):
        repo = self.make_repo()
        self.eta_root.mkdir()
        self.start(repo)
        from maeng import state
        state.path_for(self.sid).write_text("{corrupt")
        denied, reason = self.bash_pre(repo, "ls")
        self.assertTrue(denied)                            # corrupt state: fail closed
        r = self.cli("maeng-verify", ["state", "--quarantine"], repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(state.is_quarantined(self.sid))
        for cwd in (self.eta_root, repo):                  # the cwd drifted into eta: still denied
            denied, reason = self.bash_pre(cwd, "touch x")
            self.assertTrue(denied, cwd)
            self.assertIn("session state was quarantined; restart the session", reason)
        self.assertTrue(self.pre(self.eta_root, "Write", {"file_path": str(self.eta_root / "f")})[0])
        self.hook("SessionStart", repo, source="startup")      # a restarted session starts clean
        self.assertFalse(state.is_quarantined(self.sid))
        self.assertFalse(self.bash_pre(repo, "ls")[0])

    def test_quarantine_of_readable_state_writes_no_tombstone(self):
        repo = self.make_repo()
        self.start(repo)
        from maeng import state
        self.cli("maeng-verify", ["state", "--quarantine"], repo)
        self.assertFalse(state.is_quarantined(self.sid))


class R7_N_NonFastForwardLease(MergeBase):
    def lease_cmd(self, base, head):
        return f"git push --force-with-lease=refs/heads/main:{base} origin {head}:refs/heads/main"

    def moved_main(self):
        other = self.other_clone()
        (other / "other.txt").write_text("moved")
        self.git(other, "add", "-A")
        self.git(other, "commit", "-qm", "main moved")
        self.git(other, "push", "-q", "origin", "main")
        self.git(self.repo, "fetch", "-q", "origin")
        return self.git(other, "rev-parse", "HEAD").stdout.strip()

    def test_receipt_with_base_not_an_ancestor_of_head_is_denied(self):
        moved = self.moved_main()
        key = self.verdict(base=moved, head=self.h)          # reviewed base = new main tip, head = old PR tip
        denied, reason = self.bash_pre(self.repo, self.lease_cmd(moved, self.h))
        self.assertTrue(denied)
        self.assertIn("BEHIND", reason)
        self.assertEqual(self.status(key), "unconsumed")
        self.set_pr(moved, self.h)
        r = self.ship()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("BEHIND", r.stderr)
        self.assertEqual(self.remote_main(), moved)

    def test_lease_form_has_the_plain_remote_pins(self):
        self.verdict()
        cmd = self.lease_cmd(self.base, self.h)
        self.assertFalse(self.bash_pre(self.repo, cmd)[0])

        def pinned(text):
            denied, reason = self.bash_pre(self.repo, cmd)
            self.assertTrue(denied, f"expected deny ({text}): {reason}")
            self.assertIn(text, reason)

        self.git(self.repo, "config", "remote.origin.pushurl", "git@github.com:endix-foundation-v1/web.git")
        pinned("pushurl")
        self.git(self.repo, "config", "--unset-all", "remote.origin.pushurl")
        self.git(self.repo, "config", "remote.origin.mirror", "true")
        pinned("mirror")
        self.git(self.repo, "config", "remote.origin.mirror", "false")
        self.git(self.repo, "config", "push.followTags", "true")
        pinned("followTags")
        self.git(self.repo, "config", "--unset-all", "push.followTags")
        self.git(self.repo, "config", "push.recurseSubmodules", "on-demand")
        pinned("recurseSubmodules")
        self.git(self.repo, "config", "--unset-all", "push.recurseSubmodules")
        url = self.git(self.repo, "config", "remote.origin.url").stdout.strip()
        fork = self.tmp / "fork.git"
        self.git(self.tmp, "clone", "-q", "--bare", str(self.remote), str(fork))
        self.git(self.repo, "config", f"url.{fork}.pushInsteadOf", url)
        pinned("insteadOf")
        self.git(self.repo, "config", "--unset-all", f"url.{fork}.pushInsteadOf")
        self.git(self.repo, "remote", "set-head", "origin", "--delete")
        pinned("set-head")


class R7_R_EtaGitMutations(HarnessCase):
    CMDS = ("pull", "fetch", "merge feat", "rebase main", "reset --hard", "clean -fd", "checkout -- file.txt",
            "am p.patch", "apply p.patch", "cherry-pick abc", "submodule update", "stash", "restore file.txt",
            "switch -c x")

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.eta_root.mkdir()
        (self.eta_root / "file.txt").write_text("eta")
        self.start(self.repo)

    def test_mutations_with_dash_c_into_eta_are_denied(self):
        for sub in self.CMDS:
            d, reason = self.bash_pre(self.repo, f"git -C {self.eta_root} {sub}")
            self.assertTrue(d, sub)
            self.assertIn("eta", reason, sub)

    def test_mutations_after_cd_and_from_a_drifted_cwd_are_denied(self):
        for sub in self.CMDS:
            self.assertTrue(self.bash_pre(self.repo, f"cd {self.eta_root} && git {sub}")[0], sub)
            self.assertTrue(self.bash_pre(self.eta_root, f"git {sub}")[0], sub)

    def test_local_path_remote_that_is_an_eta_checkout_is_denied(self):
        self.git(self.repo, "checkout", "-qb", "feat")
        self.git(self.repo, "remote", "add", "etalocal", str(self.eta_root))
        self.run_check(self.repo, "pytest -q")
        for cmd in ("git push etalocal feat", "maeng-ship merge 7 --remote etalocal"):
            denied, reason = self.bash_pre(self.repo, cmd)
            self.assertTrue(denied, cmd)
            self.assertIn("eta", reason, cmd)
