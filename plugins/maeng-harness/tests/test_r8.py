"""Regression tests for the round-8 R1b findings (PR #38, MAE-216): production default of the fixture switch (1), closed
gh surface and gh aliases (2), closed git subcommand set (3), closed Notion/linear-endix tool sets and duplicate-page
(4), runner narrowing forms (6), GitHub MCP read set and cross-repository head (7), gh api REST writes (8), eta root
default and symlinks (9), Notion create-pages parent forms (10). Items 5 lives in test_r7 (lease pins)."""
import json
import os
import sys
import unittest.mock
import uuid

from maeng import evidence, gates, guard, receipts
from maeng.common import canonical, sha256
from .helpers import HarnessCase
from .test_g1 import ShipBase
from .test_g2_g3 import DB, PAGE
from .test_merge import MergeBase
from .test_r7 import R7_E_GithubMcpAllowlist, R7_L_NotionStructuralWrites

NOTION = "mcp__claude_ai_Notion__"


class R8_1_FixtureSwitchProductionDefault(MergeBase):
    """The variable is ABSENT in production: it must behave as off (`== "1"` only), never as on."""

    def absent(self):
        self.env.pop("MAENG_TEST_FIXTURES")
        os.environ.pop("MAENG_TEST_FIXTURES", None)

    def test_store_is_refused_when_the_variable_is_absent(self):
        self.absent()
        v = self.tmp / "v.json"
        v.write_text(json.dumps({"verdict": "pass", "reviewer": {"model": "m", "effort": "high"}, "findings": [],
                                 "subject": {"kind": "code", "repo": "r", "pr": 1, "base": "a", "head": "b",
                                             "criteria_rev": None, "digest": "d", "destination": "main",
                                             "op": "merge"}}))
        r = self.cli("maeng-review", ["store", str(v)], self.repo)
        self.assertEqual(r.returncode, 2)
        self.assertIn("MAENG_TEST_FIXTURES", r.stderr)
        self.assertFalse(receipts.receipts_dir().exists() and list(receipts.receipts_dir().glob("code-*.json")))

    def test_fixture_receipts_are_rejected_by_ship_the_lease_hook_and_g2_when_the_variable_is_absent(self):
        key = self.verdict()
        payload = {"parent": {"data_source_id": DB}, "pages": [{"title": "x"}]}
        receipts.store_verdict({"verdict": "pass", "reviewer": {"model": "gpt-6.1-sol", "effort": "medium",
                                                                "provenance": "fixture"}, "findings": [],
                                "subject": {"kind": "notion", "repo": None, "pr": None, "base": None, "head": None,
                                            "criteria_rev": None, "digest": sha256(canonical(payload)),
                                            "destination": DB, "op": "create"}})
        self.absent()
        r = self.ship()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fixture", r.stderr)
        self.assertEqual(self.remote_main(), self.base)
        denied, reason = self.bash_pre(
            self.repo, f"git push --force-with-lease=refs/heads/main:{self.base} origin {self.h}:refs/heads/main")
        self.assertTrue(denied)
        self.assertIn("fixture", reason)
        self.assertEqual(self.status(key), "unconsumed")
        rec, why = receipts.find_notion(sha256(canonical(payload)), DB, "create")
        self.assertIsNone(rec)
        self.assertIn("fixture", why)
        denied, reason = self.pre(self.repo, NOTION + "notion-create-pages", payload)
        self.assertTrue(denied)
        self.assertIn("fixture", reason)

    def test_only_the_literal_one_enables_fixtures(self):
        for value in ("0", "", "true", "yes", "on"):
            with unittest.mock.patch.dict(os.environ, {"MAENG_TEST_FIXTURES": value}):
                self.assertFalse(receipts.fixtures_allowed(), value)
        with unittest.mock.patch.dict(os.environ, {"MAENG_TEST_FIXTURES": "1"}):
            self.assertTrue(receipts.fixtures_allowed())

    def test_the_agent_cannot_set_the_switch_or_the_binary_overrides_from_bash(self):
        for cmd in ("export MAENG_TEST_FIXTURES=1", "MAENG_TEST_FIXTURES=1 maeng-review store v.json",
                    "MAENG_TEST_FIXTURES=1 maeng-ship merge 7", "MAENG_GIT=/tmp/g ls", "export MAENG_GH=/tmp/x",
                    "MAENG_CLAUDE=/tmp/c true", "MAENG_CODEX=/tmp/c true", "MAENG_HOME=/tmp/h ls",
                    "echo hi && export MAENG_TEST_FIXTURES=1", "env MAENG_TEST_FIXTURES=1 maeng-ship merge 7"):
            denied, reason = self.bash_pre(self.repo, cmd)
            self.assertTrue(denied, cmd)
            self.assertIn("MAENG_", reason, cmd)
        self.assertFalse(self.bash_pre(self.repo, "echo MAENG_TEST_FIXTURES")[0])


class R8_2_GhSurfaceClosed(ShipBase):
    def test_unknown_subcommands_and_mutating_known_ones_are_denied(self):
        self.verified()
        for cmd in ("gh frob 1", "gh frob", "gh extension exec x", "gh extension install o/r", "gh repo fork o/r",
                    "gh run rerun 1", "gh secret set X", "gh copilot suggest", "gh -R o/r frob 1"):
            self.assertDenied(cmd)
        self.assertDenied("gh frob 1", "not a known gh command")

    def test_gh_alias_management_is_denied_and_listing_is_allowed(self):
        for cmd in ("gh alias set m 'pr merge'", "gh alias set --shell m 'gh pr merge'", "gh alias delete m",
                    "gh alias import aliases.yml", "gh alias imp x"):
            self.assertDenied(cmd)
        self.assertAllowed("gh alias list")

    def test_a_user_defined_gh_alias_is_denied(self):
        cfg = self.home / ".config" / "gh"
        cfg.mkdir(parents=True)
        (cfg / "config.yml").write_text("version: 1\naliases:\n    m: pr merge\n    'co': pr checkout\neditor:\n")
        self.assertDenied("gh m 1", "user-defined gh alias")
        self.assertDenied("gh co 3", "user-defined gh alias")
        self.assertDenied("gh m 1 --squash")
        self.assertAllowed("gh pr view 1")


class R8_3_GitSubcommandsClosed(ShipBase):
    def test_unknown_and_external_subcommands_are_denied(self):
        self.verified()
        for cmd in ("git subtree push origin main", "git subtree push --prefix=x origin main", "git svn dcommit",
                    "git p4 submit", "git town ship", "git release v1", "git frobnicate", "git -C . frobnicate",
                    "git send-pack origin main", "git http-push origin main"):
            self.assertDenied(cmd)
        self.assertDenied("git frobnicate", "unknown git subcommand")
        self.assertDenied("git svn dcommit", "unknown git subcommand")

    def test_builtins_are_unaffected(self):
        self.verified()
        for cmd in ("git status", "git log -1", "git diff", "git add -A", "git commit --allow-empty -m x",
                    "git push origin feat", "git branch", "git stash list", "git worktree list", "git help",
                    "git diff-tree -r HEAD", "git fsck"):
            self.assertAllowed(cmd)

    def test_git_lfs_is_read_only(self):
        self.verified()
        for cmd in ("git lfs ls-files", "git lfs status", "git lfs env", "git lfs version", "git lfs fsck --pointers"):
            self.assertAllowed(cmd)
        for cmd in ("git lfs push origin feat", "git lfs push --all origin", "git lfs track '*.bin'",
                    "git lfs migrate import", "git lfs prune", "git lfs pull", "git lfs fsck", "git lfs install",
                    "git lfs"):
            self.assertDenied(cmd)


class R8_4_NotionToolSetClosed(HarnessCase):
    PAGE_ID = PAGE.replace("-", "")
    OTHER = "cccccccc-1111-2222-3333-444455556666"

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.start(self.repo)
        self.cli("maeng-review", ["registry", "seed", PAGE], self.repo)

    sol_pass = R7_L_NotionStructuralWrites.sol_pass

    def call(self, name, tin, tuid="n1"):
        return self.pre(self.repo, NOTION + name, tin, tool_use_id=tuid)

    def test_tool_sets_are_pinned_by_equality(self):
        self.assertEqual(gates.NOTION_GATED_WRITES, {
            "notion-create-pages", "notion-update-page", "notion-duplicate-page", "notion-delete-pages",
            "notion-delete-databases", "notion-move-pages", "notion-create-database", "notion-update-data-source"})
        self.assertEqual(gates.NOTION_OTHER_WRITES, {
            "notion-create-comment", "notion-update-comment", "notion-delete-comment", "notion-set-comment-reaction",
            "notion-set-discussion-resolved", "notion-create-view", "notion-update-view", "notion-create-folder",
            "notion-update-folder", "notion-create-attachment", "notion-create-file-upload", "notion-restore-pages",
            "notion-calendar-create-events", "notion-calendar-update-events", "notion-calendar-cancel-events",
            "notion-convert-page-to-skill", "notion-update-enabled-skills", "notion-upload-skill",
            "notion-spawn-session", "notion-send-message-to-session", "notion-stop-session"})
        reads = gates.NOTION_READS
        self.assertFalse(reads & (gates.NOTION_GATED_WRITES | gates.NOTION_OTHER_WRITES))
        for name in reads:
            self.assertRegex(name, r"^notion-(fetch|search|memory-search|get-|list-|query-|calendar-list-|read-|"
                                   r"download-|wait-|check-|show-)", name)
        for name in gates.NOTION_GATED_WRITES:
            self.assertTrue(gates.NOTION_WRITE.match(name), name)

    def test_unknown_notion_tools_are_denied(self):
        for name in ("notion-frobnicate", "notion-fetch-everything", "notion-get-secrets", "notion-publish-page",
                     "notion-list-x", "frob"):
            denied, reason = self.call(name, {"query": "x"})
            self.assertTrue(denied, name)
            self.assertIn("not on the allowlist", reason, name)
        for name in ("notion-fetch", "notion-search", "notion-get-users", "notion-list-recent-pages",
                     "notion-query-data-sources", "notion-create-comment"):
            self.assertFalse(self.call(name, {"query": "x"})[0], name)

    def test_unknown_linear_endix_tools_are_denied(self):
        for name in ("frobnicate", "list_whatever", "get_everything", "save_issue", "save_comment", "delete_issue"):
            self.assertTrue(self.pre(self.repo, "mcp__linear-endix__" + name, {})[0], name)
        for name in ("list_issues", "get_issue", "list_teams"):
            self.assertFalse(self.pre(self.repo, "mcp__linear-endix__" + name, {})[0], name)

    def test_duplicate_page_of_a_registered_page_is_gated_like_create(self):
        tin = {"page_id": PAGE}
        denied, reason = self.call("notion-duplicate-page", tin)
        self.assertTrue(denied)
        self.assertIn("no Sol pass receipt", reason)
        self.sol_pass(tin, self.PAGE_ID, "update")      # the wrong op is not enough
        self.assertTrue(self.call("notion-duplicate-page", tin)[0])
        self.sol_pass(tin, self.PAGE_ID, "create")
        self.assertFalse(self.call("notion-duplicate-page", tin, "d1")[0])
        self.assertEqual(receipts.read_journal()[0]["op"], "create")
        new = "dddddddd-1111-2222-3333-444455556666"
        self.hook("PostToolUse", self.repo, tool_name=NOTION + "notion-duplicate-page", tool_input=tin,
                  tool_use_id="d1", tool_response={"page_id": new})
        self.assertEqual(receipts.read_journal()[0]["status"], "sent")
        self.assertIn(new.replace("-", ""), receipts.read_journal()[0]["page_ids"])

    def test_duplicate_page_into_an_outcome_database_is_gated(self):
        tin = {"page_id": self.OTHER, "parent": {"type": "data_source_id", "data_source_id": DB}}
        self.assertTrue(self.call("notion-duplicate-page", tin)[0])
        self.sol_pass(tin, DB, "create")
        self.assertFalse(self.call("notion-duplicate-page", tin)[0])

    def test_duplicate_page_of_an_unrelated_page_is_free(self):
        self.assertFalse(self.call("notion-duplicate-page", {"page_id": self.OTHER})[0])


class R8_6_RunnerNarrowingForms(HarnessCase):
    def identity(self, cmd):
        rec = evidence.recognize(cmd)
        self.assertIsNotNone(rec, cmd)
        return rec["checks"][0][2]

    def test_cargo_selectors_are_filtered_never_default_mode(self):
        for cmd in ("cargo test my_test", "cargo test --lib", "cargo test --test integration", "cargo test --bin tool",
                    "cargo test --doc", "cargo test -p core", "cargo test --package core",
                    "cargo test --workspace -p core", "cargo test --workspace my_test", "cargo test --tests"):
            self.assertFalse(evidence.unfiltered(self.identity(cmd)), cmd)
        for cmd in ("cargo test", "cargo test --workspace", "cargo test --all --release"):
            self.assertTrue(evidence.unfiltered(self.identity(cmd)), cmd)
        for cmd in ("cargo test -- --skip slow", "cargo test x -- --exact", "cargo test --no-run",
                    "cargo test --lib -- --ignored", "cargo build foo"):
            self.assertIsNone(evidence.recognize(cmd), cmd)

    def test_package_manager_passthrough_is_not_evidence(self):
        for cmd in ("npm test -- --testPathPattern x", "pnpm test -- --grep x", "yarn test -- --list",
                    "npm run test -- x", "npm test -- --silent", "pnpm run test -- -t name", "yarn test --watch"):
            self.assertIsNone(evidence.recognize(cmd), cmd)
        self.assertTrue(evidence.unfiltered(self.identity("npm test")))

    def test_make_overrides_and_flags_are_not_evidence(self):
        for cmd in ("make test VAR=1", "make VAR=1 test", "make test CC=true", "make -C sub test", "make -f other.mk test",
                    "make -n test", "make -k test", "make -i test", "make -j4 test", "make -s test", "make --dry-run test",
                    "make test check", "make -C sub check", "make"):
            self.assertIsNone(evidence.recognize(cmd), cmd)
        for cmd in ("make test", "make check"):
            self.assertTrue(evidence.unfiltered(self.identity(cmd)), cmd)

    def test_other_runner_narrowing_forms_are_not_evidence(self):
        for cmd in ("playwright test --shard 1/2", "playwright test --grep x", "playwright test --only-changed",
                    "playwright test --last-failed", "pytest -c other.ini", "pytest -o addopts=-k", "pytest --rootdir x",
                    "pytest --override-ini addopts=x", "python3 -m unittest -k name", "python3 -m unittest -k"):
            self.assertIsNone(evidence.recognize(cmd), cmd)


class R8_7_GithubMcp(ShipBase):
    BASE = R7_E_GithubMcpAllowlist.BASE
    call = R7_E_GithubMcpAllowlist.call

    def test_the_read_set_is_pinned_by_equality(self):
        self.assertEqual(gates.GITHUB_READS, {
            "get_file_contents", "get_issue", "get_issue_comments", "get_pull_request", "get_pull_request_files",
            "get_pull_request_comments", "get_pull_request_reviews", "get_pull_request_status", "get_me",
            "list_commits", "list_issues", "list_pull_requests", "list_branches", "list_tags", "list_releases",
            "search_code", "search_issues", "search_repositories", "search_users", "issue_read", "pull_request_read"})
        self.assertFalse(gates.GITHUB_READS & (gates.GITHUB_PLAIN_WRITES | gates.GITHUB_GATED_WRITES))
        for name in ("get_secret", "list_secrets", "search_and_delete", "get_x", "read_everything"):
            self.assertIn("not on the allowlist", self.call(name)[1], name)

    def test_create_pull_request_with_a_cross_repository_head_is_denied(self):
        self.verified()
        self.alias_origin()
        self.assertFalse(self.call("create_pull_request", head="feat", base="main")[0])
        for head in ("someone:feat", "o:feat", "fork-owner:feat"):
            denied, reason = self.call("create_pull_request", head=head, base="main")
            self.assertTrue(denied, head)
            self.assertIn("cross-repository", reason, head)


class R8_8_GhApiRestWrites(ShipBase):
    def test_rest_write_forms_in_personal_repositories_are_denied(self):
        self.verified()
        for cmd in ("gh api repos/o/r/merges --input body.json", "gh api repos/o/r/merges -X POST --input body.json",
                    "gh api repos/o/r/merges -F base=main -F head=feat", "gh api repos/o/r/merges --field base=main",
                    "gh api repos/o/r/merges -F base=main", "gh api repos/o/r/git/refs -F ref=refs/heads/x -F sha=abc",
                    "gh api repos/o/r/git/refs --field sha=abc", "gh api repos/o/r/contents/f.txt --input body.json",
                    "gh api repos/o/r/pulls/1/merge --input body.json", "gh api repos/o/r/dispatches -F event_type=x",
                    "gh api repos/o/r/pulls -F title=t -F head=feat -F base=main"):
            self.assertDenied(cmd)
        self.assertAllowed("gh api repos/o/r/pulls")
        self.assertAllowed("gh api repos/o/r/merges")        # a plain GET


class R8_9_EtaClassification(HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.eta_root.mkdir()
        (self.eta_root / "file.txt").write_text("eta")
        self.start(self.repo)

    def test_production_default_root_when_the_variable_is_absent(self):
        self.env.pop("MAENG_ETA_ROOT")
        os.environ.pop("MAENG_ETA_ROOT")
        default = self.home / "Documents" / "Project" / "eta_v1"
        (default / "dev").mkdir(parents=True)
        self.assertEqual(guard.eta_root(), default)
        self.assertEqual(guard.classify(default / "dev"), guard.ETA)
        self.assertEqual(guard.classify(default / "not/yet.txt"), guard.ETA)
        self.assertEqual(guard.classify(self.repo), guard.PERSONAL)
        denied, reason = self.pre(self.repo, "Write", {"file_path": str(default / "dev/x.txt"), "content": "x"})
        self.assertTrue(denied)
        self.assertIn("eta", reason)
        self.assertTrue(self.bash_pre(self.repo, f"touch {default}/dev/x")[0])
        self.assertTrue(self.bash_pre(self.repo, f"echo hi > {default}/dev/x")[0])
        self.assertFalse(self.bash_pre(self.repo, f"cat {default}/dev/../dev")[0])

    def link(self):
        (self.repo / "etalink").symlink_to(self.eta_root, target_is_directory=True)
        (self.repo / "linkfile").symlink_to(self.eta_root / "file.txt")
        (self.repo / "newlink").symlink_to(self.eta_root / "new.txt")            # dangling: the target is created

    def test_symlinks_into_eta_are_classified_by_their_real_path(self):
        self.link()
        for name in ("etalink/file.txt", "linkfile", "newlink", "etalink/sub/new.txt", "etalink"):
            self.assertEqual(guard.classify(self.repo / name), guard.ETA, name)
        self.assertEqual(guard.classify(self.repo / "app.py"), guard.PERSONAL)

    def test_edit_and_write_through_a_symlink_are_denied(self):
        self.link()
        for tool in ("Edit", "Write", "MultiEdit"):
            for name in ("etalink/file.txt", "linkfile", "newlink", "etalink/sub/new.txt"):
                denied, reason = self.pre(self.repo, tool, {"file_path": str(self.repo / name), "content": "x"})
                self.assertTrue(denied, f"{tool} {name}")
                self.assertIn("eta", reason)
        self.assertFalse(self.pre(self.repo, "Write", {"file_path": str(self.repo / "ok.txt"), "content": "x"})[0])

    def test_bash_operands_through_a_symlink_are_denied(self):
        self.link()
        for cmd in ("touch etalink/x", "echo hi > newlink", "echo hi > etalink/f", "cp app.py etalink/c.py",
                    "cd etalink && touch y", "rm linkfile", "mv app.py newlink", f"touch {self.repo}/etalink/z",
                    "sed -i s/a/b/ linkfile", "git -C etalink commit --allow-empty -m x"):
            denied, reason = self.bash_pre(self.repo, cmd)
            self.assertTrue(denied, cmd)
            self.assertIn("eta", reason, cmd)
        for cmd in ("cat etalink/file.txt", "ls etalink", "cat linkfile", "touch ok.txt"):
            self.assertFalse(self.bash_pre(self.repo, cmd)[0], cmd)


class R8_10_NotionCreatePagesParents(HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.start(self.repo)

    def test_every_parent_form_naming_an_outcome_database_is_gated(self):
        pages = [{"properties": {"title": "Outcome"}}]
        for parent in ({"data_source_id": DB}, {"database_id": DB}, {"type": "data_source_id", "data_source_id": DB},
                       {"type": "database_id", "database_id": DB},
                       {"type": "page_id", "page_id": "cccccccccccccccccccccccccccccccc", "database_id": DB}):
            denied, reason = self.pre(self.repo, NOTION + "notion-create-pages", {"parent": parent, "pages": pages})
            self.assertTrue(denied, parent)
            self.assertIn("no Sol pass receipt", reason, parent)

    def test_other_parents_are_not_gated(self):
        pages = [{"properties": {"title": "x"}}]
        other = "cccccccccccccccccccccccccccccccc"
        for parent in ({"page_id": other}, {"type": "page_id", "page_id": other}, {"database_id": other},
                       {"type": "database_id", "database_id": other}, {"type": "workspace"}):
            self.assertFalse(self.pre(self.repo, NOTION + "notion-create-pages",
                                      {"parent": parent, "pages": pages})[0], parent)

    def test_a_receipt_for_the_exact_payload_passes_for_database_id(self):
        payload = {"parent": {"type": "database_id", "database_id": DB}, "pages": [{"properties": {"title": "x"}}]}
        v = {"verdict": "pass", "reviewer": {"model": "gpt-6.1-sol", "effort": "medium"}, "findings": [],
             "subject": {"kind": "notion", "repo": None, "pr": None, "base": None, "head": None, "criteria_rev": None,
                         "digest": sha256(canonical(payload)), "destination": DB, "op": "create"}}
        f = self.tmp / f"v-{uuid.uuid4().hex[:6]}.json"
        f.write_text(json.dumps(v))
        self.assertEqual(self.cli("maeng-review", ["store", str(f)], self.repo).returncode, 0)
        self.assertFalse(self.pre(self.repo, NOTION + "notion-create-pages", payload)[0])
