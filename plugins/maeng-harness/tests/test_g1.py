import os
import stat
import sys

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
        self.git(self.repo, "config", "remote.origin.url", url)
        # MAENG_GIT maps the github URL to the local bare repo for the gate's own ls-remote calls (no insteadOf
        # rewrite: a rewritten remote is denied by design)
        fake = self.tmp / "alias-git"
        fake.write_text(f"#!{sys.executable}\nimport os, sys\n"
                        f"args = [{remote!r} if a == {url!r} else a for a in sys.argv[1:]]\n"
                        f"os.execvp('git', ['git', *args])\n")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        self.env["MAENG_GIT"] = str(fake)
        os.environ["MAENG_GIT"] = str(fake)
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
        for cmd, why in (("git push origin main", "default branch"), ("git push origin feat:refs/heads/main", "default branch"),
                         ("git push origin feat:main", "default branch"), ("git push origin master", "default branch"),
                         ("git push origin HEAD:main", "HEAD is not a branch name"),
                         ("git push origin :main", "must be a local branch name or a full commit SHA"),
                         ("git push --delete origin main", "flag `--delete` is not allowed")):
            self.assertDenied(cmd, why)

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
            self.assertDenied(cmd, "canonical")
        sha = self.head(self.repo)
        self.assertDenied(f"git push origin {sha}:feat", "needs destination refs/heads/<name>")   # SHA source: full ref only

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
        self.alias_origin()
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

    def test_mcp_create_pull_request_needs_a_verified_remote_head(self):
        self.alias_origin()
        (self.repo / "app.py").write_text("print('dirty')\n")
        base = {"owner": "o", "repo": "r"}
        self.git(self.repo, "checkout", "-q", "app.py")
        denied, reason = self.pre(self.repo, "mcp__github__create_pull_request", {**base, "head": "feat", "base": "main"})
        self.assertTrue(denied)
        self.assertIn("not ship-verified", reason)

    def test_mcp_push_files_is_denied_even_on_a_verified_tree(self):
        self.verified()
        denied, reason = self.pre(self.repo, "mcp__github__push_files",
                                  {"owner": "o", "repo": "r", "branch": "feat", "files": [], "message": "m"})
        self.assertTrue(denied)
        self.assertIn("verified `git commit`", reason)


class GitExecVectors(ShipBase):
    """C1: config and environment that make a read-only-looking git command run an arbitrary program."""

    def test_global_config_exec_keys_denied_for_every_subcommand(self):
        for cmd in ("git -c core.pager='git push origin main' log",
                    "git -c core.pager=x status", "git -c CORE.Pager=x diff", "git -c core.sshCommand=x fetch origin",
                    "git -c core.fsmonitor=x status", "git -c core.editor=x commit --amend",
                    "git -c diff.external=x show", "git -c credential.helper=x ls-remote origin",
                    "git -c sequence.editor=x rebase -i HEAD~1", "git -c pager.log=x log",
                    "git -c color.ui=never -c core.hooksPath=/tmp/h log", "git -c include.path=/tmp/c log",
                    "git -c filter.f.smudge=x status", "git -c core.pager=x",
                    "git --config-env=core.pager=PAGER_CMD log", "git --config-env core.sshCommand=SSHC fetch"):
            self.assertDenied(cmd, "denied in every mode")

    def test_global_config_deny_names_the_key(self):
        self.assertDenied("git -c core.pager=x log", "core.pager")
        self.assertDenied("git --config-env=core.sshCommand=E fetch", "core.sshcommand")

    def test_benign_global_config_and_plain_reads_still_allowed(self):
        for cmd in ("git -c color.ui=never log", "git log", "git -c user.name=x status", "git status",
                    "git -c core.quotepath=false diff", "git -c color.ui=never -c user.email=a@b log",
                    "git --config-env=user.name=NAME status"):
            self.assertAllowed(cmd)

    def test_env_exec_vars_denied_when_running_git(self):
        for cmd in ("GIT_PAGER=x git log", "PAGER=x git log", "env GIT_SSH_COMMAND=x git fetch",
                    "GIT_SSH=x git ls-remote origin", "GIT_EXTERNAL_DIFF=x git diff", "GIT_EDITOR=x git commit",
                    "GIT_SEQUENCE_EDITOR=x git rebase -i HEAD~1", "GIT_ASKPASS=x git fetch",
                    "SSH_ASKPASS=x git fetch", "GIT_PROXY_COMMAND=x git fetch", "GIT_CONFIG_GLOBAL=/tmp/c git log",
                    "GIT_CONFIG_SYSTEM=/tmp/c git log", "GIT_CONFIG_PARAMETERS=\"'core.pager=x'\" git log",
                    "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.pager GIT_CONFIG_VALUE_0=x git log",
                    "GIT_CONFIG_KEY_0=core.pager git log", "GIT_TEMPLATE_DIR=/tmp/t git init",
                    "export GIT_PAGER=x; git log", "GIT_PAGER=x env git log"):
            self.assertDenied(cmd, "environment of a git command")

    def test_pager_set_to_nothing_or_cat_is_allowed_anything_else_denied(self):
        for cmd in ("GIT_PAGER=cat git log --oneline", "GIT_PAGER= git log", "PAGER=cat git log", "git -c core.pager=cat log",
                    "git -c core.pager= log", "git -c pager.log=cat log", "GIT_PAGER=cat git -c core.pager=cat diff"):
            self.assertAllowed(cmd)
        for cmd in ("GIT_PAGER='git push origin main' git log", "GIT_PAGER=less git log", "PAGER=less git log",
                    "git -c core.pager=less log", "git -c core.pager='git push origin main' log",
                    "git -c core.pager=cat -c core.pager=less log", "git --config-env=core.pager=P log",
                    "git -c pager.log=less log"):
            self.assertDenied(cmd, "denied in every mode")

    def test_env_exec_vars_stay_allowed_without_git_and_other_vars_with_git(self):
        for cmd in ("PAGER=cat ls", "GIT_PAGER=x echo hi", "LC_ALL=C git log", "env LANG=C git status",
                    "GIT_AUTHOR_NAME=x git log"):
            self.assertAllowed(cmd)

    def test_clone_and_init_template_install_hooks_and_are_denied(self):
        for cmd in ("git clone --template=/tmp/t https://github.com/o/r dest", "git clone --template /tmp/t o/r",
                    "git init --template=/tmp/t", "git init --template /tmp/t d", "git init --temp=/tmp/t",
                    "git -C . init --template=/tmp/t"):
            self.assertDenied(cmd, "denied in every mode")
        self.assertAllowed("git init newrepo")
        self.assertAllowed("git clone https://github.com/o/r elsewhere")

    def test_show_output_writes_a_file_and_is_not_read_only(self):
        from maeng import gates
        for args in (["--output=f"], ["--output", "f"], ["--out=f"], ["--outp=f", "HEAD"]):
            self.assertFalse(gates.git_readonly("show", args), args)
            self.assertFalse(gates.git_readonly("diff", args), args)
            self.assertFalse(gates.git_readonly("log", args), args)
        self.assertTrue(gates.git_readonly("show", ["--stat", "HEAD"]))

    def test_gh_issue_develop_creates_a_remote_branch_and_is_denied_unless_listing(self):
        for cmd in ("gh issue develop 1 -R o/r", "gh issue develop 1 -R o/r --base main -n b",
                    "gh issue develop 1 -R o/r --checkout", "gh issue develop 1 --repo o/r --branch-repo o/x"):
            self.assertDenied(cmd, "creates a branch on the remote")
        self.assertAllowed("gh issue develop --list 1 -R o/r")
        self.assertAllowed("gh issue develop -l 1 -R o/r")

    def test_gh_issue_transfer_stays_an_explicit_r_scoped_write(self):
        self.assertDenied("gh issue transfer 1 o/r2")                    # needs -R
        self.assertAllowed("gh issue transfer 1 o/r2 -R o/other")        # an issue write like edit/close (test_r4)


class ReadonlyPins(ShipBase):
    """C1 low: the read-only allowlists change only on purpose. Update the literal or digest when adding to them."""

    @staticmethod
    def digest(obj):
        import hashlib

        def norm(o):
            if isinstance(o, dict):
                return sorted((k, norm(v)) for k, v in o.items())
            if isinstance(o, (set, frozenset)):
                return sorted(o)
            return o
        return hashlib.sha256(repr(norm(obj)).encode()).hexdigest()

    def test_readonly_git_subcommands_pinned(self):
        from maeng import gates
        self.assertEqual(gates.READONLY_GIT, {"status", "log", "diff", "show", "rev-parse", "ls-files", "ls-tree",
                                              "cat-file", "blame", "describe", "grep", "shortlog", "rev-list",
                                              "name-rev", "merge-base", "ls-remote", "check-ignore"})

    def test_readonly_programs_pinned(self):
        from maeng import readonly
        self.assertEqual(readonly.PROGS, {"[", "basename", "cat", "cd", "cut", "date", "df", "diff", "dirname", "du",
                                          "echo", "env", "false", "find", "grep", "head", "jq", "ls", "md5", "popd",
                                          "printf", "pushd", "pwd", "readlink", "realpath", "rg", "sha256sum",
                                          "shasum", "sort", "stat", "tail", "test", "tr", "tree", "true", "uniq",
                                          "wc", "which"})
        self.assertEqual(readonly.FREE, {"test", "[", "cd", "pushd", "popd"})

    def test_readonly_option_sets_pinned(self):
        from maeng import readonly
        pins = {
            "SPECS": "76bc9e80e77f62d3051fa9c0c6381bbd96a28a4ea3a6242cf204db2a62868a0f",
            "GIT_SHORT": "722b60fd1d8ad2bc15b3569cdd1dbc325f28450bdfbf91cb08c85d7a006c6484",
            "GIT_LONG": "a1de8d4222af4fb229e8dd96e0ca795ee1cec751fa7881822a4c91fb58448dde",
            "GIT_LONG_VALUE": "3cc1db592c764e9efb08bd80a381ba279ab89e748ae34b9659c20377c933dfa4",
            "GH_READ_FLAGS": "e30a6dce1e18703394a2a130a8d8e627303ba5e22bda89ab558231fef11e3a30",
            "FIND_FLAG": "993f56542f72f377785fcfe6a14c98c57ac01b7d4587c208178fad28ad28e311",
            "FIND_PRIMARY_BOOL": "f60c0c528b43ba46fd6e441a852c520a4549e77008dd4e2437cc6523f1de16ab",
            "FIND_PRIMARY_VALUE": "ea495fa822264b55a44f715e36b43dcf32a465cee01c75739ca92cea9a4f9963",
        }
        for name, want in pins.items():
            self.assertEqual(self.digest(getattr(readonly, name)), want, f"readonly.{name} changed")
