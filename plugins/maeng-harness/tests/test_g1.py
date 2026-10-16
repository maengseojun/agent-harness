from .helpers import HarnessCase


class ShipBase(HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.git(self.repo, "checkout", "-qb", "feat")
        self.git(self.repo, "push", "-q", "-u", "origin", "feat")
        self.start(self.repo)

    def alias_origin(self, slug="o/r"):
        """Make origin a github.com URL (what `gh pr create --repo` must name) that git maps to the local bare repo."""
        remote = self.git(self.repo, "config", "remote.origin.url").stdout.strip()
        url = f"https://github.com/{slug}.git"
        self.git(self.repo, "config", f"url.{remote}.insteadOf", url)
        self.git(self.repo, "config", "remote.origin.url", url)
        return slug

    def verified(self):
        self.run_check(self.repo, "pytest -q")

    def assertDenied(self, command, text=None):
        denied, reason = self.bash_pre(self.repo, command)
        self.assertTrue(denied, f"expected deny: {command} ({reason})")
        if text:
            self.assertIn(text, reason)

    def assertAllowed(self, command):
        denied, reason = self.bash_pre(self.repo, command)
        self.assertFalse(denied, f"expected allow: {command} ({reason})")


class PushRoutes(ShipBase):
    def test_unverified_feature_push_denied_then_allowed_when_verified(self):
        self.assertDenied("git push origin feat", "not ship-verified")
        self.verified()
        self.assertAllowed("git push origin feat")
        self.assertAllowed("git push -u origin feat")
        self.assertAllowed("git push origin feat:feat")
        self.assertAllowed("git push origin feat:refs/heads/feat")
        sha = self.head(self.repo)
        self.assertAllowed(f"git push origin {sha}:refs/heads/feat")
        self.assertDenied("git push", "canonical")          # implicit remote/refspec is not a canonical form

    def test_force_variants_denied_even_when_verified(self):
        self.verified()
        for cmd in ("git push -f origin feat", "git push --force origin feat", "git push --force-with-lease origin feat",
                    "git push --force-with-lease=feat origin feat", "git push origin +feat", "git push origin +feat:feat",
                    "git push -fu origin feat", "git push --force-if-includes origin feat",
                    "git push origin feat --force", "git -C . push --force origin feat"):
            self.assertDenied(cmd, "canonical")
        self.assertDenied("git push -f origin feat", "force")

    def test_default_branch_destinations_denied(self):
        self.verified()
        for cmd in ("git push origin main", "git push origin HEAD:main", "git push origin feat:refs/heads/main",
                    "git push origin :main", "git push --delete origin main", "git push origin master"):
            self.assertDenied(cmd)

    def test_implicit_destination_forms_are_not_canonical(self):
        """Allowlist (was: upstream/push.default resolution): only an explicit `<remote> <refspec>` is allowed."""
        self.verified()
        self.git(self.repo, "branch", "--set-upstream-to=origin/main")
        for cmd in ("git -c push.default=upstream push", "git push", "git push origin", "git push -u origin",
                    "git push origin HEAD", "git push origin HEAD:feat"):
            self.assertDenied(cmd, "canonical")
        self.git(self.repo, "config", "push.default", "upstream")
        self.assertDenied("git push", "canonical")
        self.assertAllowed("git push origin feat")                 # explicit refspec ignores push.default

    def test_implicit_current_branch_main(self):
        self.git(self.repo, "checkout", "-q", "main")
        self.verified()
        self.assertDenied("git push", "canonical")
        self.assertDenied("git push origin HEAD", "canonical")
        self.assertDenied("git push origin main", "default branch")

    def test_tags_mirror_all_and_non_branch_refs(self):
        self.verified()
        for cmd in ("git push --tags", "git push origin --tags", "git push --follow-tags origin feat",
                    "git push origin refs/tags/v1", "git push origin tag v1", "git push origin feat:refs/tags/v1",
                    "git push --mirror origin", "git push --all origin", "git push origin 'refs/heads/*:refs/heads/*'",
                    "git push origin feat:refs/notes/x"):
            self.assertDenied(cmd)

    def test_wrappers_and_compound_commands(self):
        self.verified()
        for cmd in ("bash -c 'git push origin main'", "sh -c \"git push --force\"", "eval 'git push origin main'",
                    "ls && git push origin main", "cd . ; git push origin main", "true || git push -f origin feat",
                    "echo x | git push origin main", "echo $(git push origin main)", "echo `git push origin main`",
                    "(git push origin main)", "FOO=1 git push origin main", "env X=1 git push origin main",
                    "command git push origin main", "git push origin 'main", "bash -c \"gh pr merge 1\"",
                    "bash -lc 'git push origin main'", "zsh -c 'gh release create v1'", "sudo sh -c 'git push -f'",
                    "ls\ngit push origin main", "git push origin $BRANCH"):
            self.assertDenied(cmd)

    def test_benign_commands_with_push_words_stay_allowed(self):
        self.assertAllowed("echo 'git push origin main'")
        self.assertAllowed("bash -c 'echo hello'")
        self.assertAllowed("git commit -m \"$(cat <<'EOF'\nfix: push bug and merge docs\nEOF\n)\"")
        self.assertAllowed("git status && git log --oneline | head -3")
        self.assertDenied("git push --dry-run origin main", "canonical")   # was allowed before the allowlist

    def test_verify_edit_commit_push_denied(self):
        self.verified()
        self.assertAllowed("git push origin feat")
        (self.repo / "app.py").write_text("print('changed')\n")
        self.commit_all(self.repo, "edit after verify")
        self.assertDenied("git push origin feat", "not ship-verified")

    def test_docs_only_change_keeps_evidence_but_dependency_change_invalidates(self):
        self.verified()
        (self.repo / "README.md").write_text("# new docs\n")
        (self.repo / "docs").mkdir()
        (self.repo / "docs/x.md").write_text("doc")
        self.commit_all(self.repo, "docs")
        self.assertAllowed("git push origin feat")
        (self.repo / "requirements.txt").write_text("pytest\nrequests\n")
        self.commit_all(self.repo, "deps")
        self.assertDenied("git push origin feat")

    def test_cmakelists_change_invalidates(self):
        self.verified()
        (self.repo / "CMakeLists.txt").write_text("project(x)\n")
        self.commit_all(self.repo, "cmake")
        self.assertDenied("git push origin feat")

    def test_branch_switch_or_other_source_ref_with_unverified_tree_denied(self):
        self.verified()
        self.git(self.repo, "checkout", "-qb", "other")
        (self.repo / "app.py").write_text("print('other')\n")
        self.commit_all(self.repo, "other change")
        self.assertDenied("git push origin other")            # implicit/explicit other ref
        self.assertDenied("git push origin other:feat2")
        self.assertDenied("git push")                          # current branch other, tree unverified
        self.git(self.repo, "checkout", "-q", "feat")
        self.assertDenied("git push origin other")             # other source ref while on feat
        self.assertAllowed("git push origin feat")

    def test_skip_only_tree_denies_ship_but_allows_stop(self):
        (self.repo / "app.py").write_text("print('wip')\n")
        self.commit_all(self.repo, "wip")
        self.hook("PostToolUse", self.repo, tool_name="Edit", tool_input={"file_path": str(self.repo / "app.py")},
                  tool_response={})
        r = self.cli("maeng-verify", ["skip", "no tests for this prototype"], self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertDenied("git push origin feat", "not ship-verified")
        self.alias_origin()
        self.assertDenied("gh pr create -R o/r --title t --body b", "not ship-verified")
        rc, out, _ = self.hook("Stop", self.repo, stop_hook_active=False)
        # stop-satisfied via the skip: only the (separate) record obligation remains
        self.assertIsNotNone(out)
        self.assertIn("UNRECORDED", out["reason"])
        self.assertNotIn("UNVERIFIED", out["reason"])


class GhRoutes(ShipBase):
    def test_gh_denied_routes(self):
        self.verified()
        for cmd in ("gh api -X PUT repos/o/r/contents/f.txt -f message=m -f content=Zg== -f branch=feat",
                    "gh api --method PUT repos/o/r/contents/f.txt -f branch=main",
                    "gh api repos/o/r/contents/f.txt -X DELETE -f message=m",
                    "gh api repos/o/r/contents/f.txt -f message=m -f content=Zg==",   # implicit POST
                    "gh api graphql -f query='mutation { createCommitOnBranch(input:{}) { commit { oid } } }'",
                    "gh api graphql -f query='mutation { mergePullRequest(input:{}) { clientMutationId } }'",
                    "gh api -X PUT repos/o/r/pulls/1/merge", "gh api -XPATCH repos/o/r/git/refs/heads/main -f sha=abc",
                    "gh api repos/o/r/merges -f base=main -f head=feat",
                    "gh pr merge 1", "gh pr merge --auto 1", "gh pr merge 1 --squash", "gh pr merge --admin --rebase 1",
                    "gh pr merge --merge", "gh repo sync", "gh repo sync --force", "gh repo sync o/r -b main",
                    "gh pr update-branch 1", "gh release create v1", "gh release upload v1 f", "gh release delete v1",
                    "gh repo edit --default-branch dev", "gh workflow run x.yml", "gh repo delete o/r --yes",
                    "gh api -X POST repos/o/r/issues/1/comments -f body=hi"):  # allowed before the allowlist
            self.assertDenied(cmd)

    def test_gh_allowed_routes(self):
        for cmd in ("gh pr comment 1 -R o/r -b hi", "gh pr edit 1 -R o/r --title t", "gh pr review 1 -R o/r --approve",
                    "gh pr ready 1 -R o/r", "gh pr close 1 -R o/r", "gh issue create -R o/r -t x -b y",
                    "gh issue comment 2 --repo o/r -b z", "gh pr checkout 3",
                    "gh pr view 1 --json state", "gh pr list", "gh api repos/o/r/pulls", "gh api user",
                    "gh api graphql -f query='query { viewer { login } }'", "gh run list", "gh release list"):
            self.assertAllowed(cmd)

    def test_pr_create_needs_verified_head(self):
        self.alias_origin()
        self.assertDenied("gh pr create -R o/r --title t --body b", "not ship-verified")
        self.assertDenied("gh pr create -R o/r --head feat --title t --body b")
        self.verified()
        self.assertAllowed("gh pr create -R o/r --title t --body b")
        self.assertAllowed("gh pr create -R o/r --head feat --title t --body b --draft --base main")
        self.assertDenied("gh pr create -R o/r --head nosuchbranch --title t")
        self.assertDenied("gh pr create -R o/r --fill", "canonical")         # --fill is not a canonical flag
        self.assertDenied("gh pr create -R o/r --head feat --title t --web", "canonical")

    def test_pr_create_reminds_review_tier(self):
        self.verified()
        rc, out, _ = self.hook("PostToolUse", self.repo, tool_name="Bash", tool_input={"command": "gh pr create --fill"},
                               tool_use_id="x", tool_response={"stdout": "https://github.com/o/r/pull/1"})
        self.assertIn("maeng-review", out["hookSpecificOutput"]["additionalContext"])


class McpRoutes(ShipBase):
    def test_github_mcp(self):
        base = {"owner": "o", "repo": "r"}
        remote = self.git(self.repo, "config", "remote.origin.url").stdout.strip()
        self.git(self.repo, "config", f"url.{remote}.insteadOf", "https://github.com/o/r.git")  # o/r -> local bare
        self.verified()
        for tool, tin in (("merge_pull_request", {**base, "pullNumber": 1}),
                          ("update_pull_request_branch", {**base, "pullNumber": 1}),
                          ("push_files", {**base, "branch": "main", "files": [], "message": "m"}),
                          ("create_or_update_file", {**base, "branch": "main", "path": "a", "content": "b", "message": "m"}),
                          ("push_files", {**base, "files": [], "message": "m"})):
            denied, _ = self.pre(self.repo, "mcp__github__" + tool, tin)
            self.assertTrue(denied, tool)
        for tool, tin in (("add_issue_comment", {**base, "issue_number": 1, "body": "x"}),
                          ("get_file_contents", {**base, "path": "a"}),
                          ("create_pull_request", {**base, "head": "feat", "base": "main", "title": "t"})):
            denied, reason = self.pre(self.repo, "mcp__github__" + tool, tin)
            self.assertFalse(denied, f"{tool}: {reason}")

    def test_push_files_and_create_or_update_file_are_always_denied(self):
        """R1#6: contents are never tied to the verified tree, even on a verified feature branch."""
        self.verified()
        base = {"owner": "o", "repo": "r"}
        for tool, tin in (("push_files", {**base, "branch": "feat", "files": [], "message": "m"}),
                          ("create_or_update_file", {**base, "branch": "feat", "path": "a", "content": "b",
                                                     "message": "m"})):
            denied, reason = self.pre(self.repo, "mcp__github__" + tool, tin)
            self.assertTrue(denied, tool)
            self.assertIn("verified `git commit`", reason)

    def test_mcp_pr_and_push_files_need_verification(self):
        (self.repo / "app.py").write_text("print('dirty')\n")
        base = {"owner": "o", "repo": "r"}
        self.git(self.repo, "checkout", "-q", "app.py")
        denied, _ = self.pre(self.repo, "mcp__github__create_pull_request", {**base, "head": "feat", "base": "main"})
        self.assertTrue(denied)
