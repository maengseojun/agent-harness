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


class SlimGate(ShipBase):
    def test_only_default_branch_pushes_and_merges_are_denied(self):
        for cmd in ("git push origin main", "git push origin feat:main", "git push origin +HEAD:refs/heads/master",
                    "git push --all origin", "git -C . push origin main", "cd . && git push origin :main"):
            self.assertDenied(cmd, "default branch")
        self.assertDenied("gh pr merge 1 --squash", "maeng-ship merge")
        self.git(self.repo, "checkout", "-q", "main")
        self.assertDenied("git push", "default branch")  # implicit destination = current branch

    def test_feature_pushes_gh_env_and_eta_paths_are_allowed(self):
        self.eta_root.mkdir()
        for cmd in ("git push origin feat", "git push -f -u origin feat", "git push && gh pr create --fill",
                    "gh pr comment 1 -b hi", "MAENG_REVIEW_BACKEND=claude maeng-review run --kind code --pr 1",
                    f"E={self.eta_root}; sed -n 1p $E/README.md", f"touch {self.eta_root}/x"):
            self.assertAllowed(cmd)

    def test_other_merge_routes_switches_and_hidden_pushes_are_denied(self):
        for cmd in ("gh pr update-branch 1", "gh api -X PUT repos/o/r/pulls/1/merge",
                    "gh api repos/o/r/merges -f base=main -f head=feat",
                    "gh api graphql -f query='mutation { mergePullRequest(input: {}) { clientMutationId } }'",
                    "MAENG_TEST_FIXTURES=1 maeng-ship merge 7", "export MAENG_GIT=/tmp/fake",
                    "env MAENG_HOME=/tmp/x maeng-ship merge 7", "git -c alias.p=push p origin main",
                    "git commit -m \"$(cat <<\\EOF\nx\nEOF\n)\" && git push origin main"):
            denied, reason = self.bash_pre(self.repo, cmd)
            self.assertTrue(denied, f"expected deny: {cmd} ({reason})")
        self.git(self.repo, "config", "alias.pm", "push origin main")
        self.assertDenied("git pm", "alias")
        self.git(self.repo, "checkout", "-qb", "fromMain")
        self.git(self.repo, "config", "branch.fromMain.merge", "refs/heads/main")
        self.assertDenied("git push", "default branch")  # implicit destination = upstream main
        self.git(self.repo, "checkout", "-q", "--detach")
        self.assertDenied("git push", "cannot tell")
        self.assertAllowed("gh api repos/o/r/pulls/1")

    def test_round2_common_routes(self):
        self.git(self.repo, "checkout", "-q", "main")
        for cmd in ("git push origin :", "git push origin +:", "git push origin @", "git push origin 'refs/heads/ma*'",
                    "git -c remote.origin.push=HEAD:refs/heads/main push origin", "git -c push.default=matching push",
                    "gh repo sync", "gh api -X POST repos/o/r/merge-upstream -f branch=main",
                    "gh api -X PUT repos/o/r/contents/f -f message=m -f content=x",
                    "gh api graphql -F query=@m.graphql", "sh -c 'git push origin main'", "eval 'gh pr merge 1'"):
            denied, reason = self.bash_pre(self.repo, cmd)
            self.assertTrue(denied, f"expected deny: {cmd} ({reason})")
        self.assertTrue(self.pre(self.repo, "Bash", {"command": 123})[0])
        self.git(self.repo, "checkout", "-q", "feat")
        sha = self.git(self.repo, "rev-parse", "HEAD").stdout.strip()
        self.assertAllowed(f"git push --force-with-lease=refs/heads/feat:{sha} origin {sha}:refs/heads/feat")
        self.assertAllowed("gh api -X PUT repos/o/r/contents/f -f branch=feat -f message=m -f content=x")

    def test_round3_effective_config_prefixes_and_policy(self):
        self.git(self.repo, "config", "push.default", "simple")
        self.git(self.repo, "config", "--add", "push.default", "matching")   # git applies the last value
        self.assertDenied("git push", "default branch")
        self.git(self.repo, "config", "--unset-all", "push.default")
        self.git(self.repo, "config", "remote.origin.mirror", "yes")
        self.assertDenied("git push origin", "default branch")
        self.git(self.repo, "config", "--unset-all", "remote.origin.mirror")
        self.git(self.repo, "config", "remote.origin.push", "HEAD:refs/heads/main")
        self.assertDenied("git -c remote.origin.push=refs/heads/feat push origin", "default branch")
        self.git(self.repo, "config", "--unset-all", "remote.origin.push")
        for cmd in ("git push origin main:", "GIT_TRACE=1 git push origin main", "env X=1 git push origin main",
                    "/usr/bin/git push origin main", "/opt/homebrew/bin/gh pr merge 1",
                    "gh api -X PUT repos/o/r/contents/f -f branch=refs/heads/main -f message=m -f content=x"):
            denied, reason = self.bash_pre(self.repo, cmd)
            self.assertTrue(denied, f"expected deny: {cmd} ({reason})")
        self.assertTrue(self.pre(self.repo, "mcp__plugin_x_github__merge_pull_request", {"pull_number": 1})[0])
        (self.repo / ".maeng").mkdir(exist_ok=True)
        (self.repo / ".maeng/verify.json").write_text("{broken")
        self.assertDenied("git push origin feat", "pushes are denied")

    def test_round4_option_operands(self):
        self.assertDenied("git -c remote.up.mirror=true push --repo=up", "default branch")
        self.assertDenied("git -c remote.origin.mirror push origin", "default branch")  # value-less -c is true
        self.assertDenied("gh api -X PUT repos/o/r/contents/f --input p.json -f branch=feat", "default branch")
        self.assertDenied("gh api --preview corsair graphql --input m.json", "cannot be checked")
        for b in ("{branch}", "@b.txt"):
            self.assertDenied(f"gh api -X PUT repos/o/r/contents/f -F branch={b} -f message=m", "cannot be checked")
        self.assertAllowed("git push --recurse-submodules on-demand origin")
        for cmd in ('b=main; git push origin "$b"', 'gh api -X PUT repos/o/r/contents/f -f "branch=$b" -f message=m',
                    'gh api graphql -f "query=mutation { $fields }"'):
            denied, reason = self.bash_pre(self.repo, cmd)
            self.assertTrue(denied, f"expected deny: {cmd} ({reason})")
        self.assertAllowed("gh api graphql -f query='query($o: String!) { repository(owner: $o, name: \"r\") { id } }'")
        self.git(self.repo, "config", "alias.ub", "!gh pr update-branch 1")
        self.assertDenied("git ub", "alias")
        self.git(self.repo, "config", "alias.rs", "!gh repo sync")
        self.assertDenied("git rs", "alias")
        self.git(self.repo, "config", "alias.ref", "!gh api -X PATCH repos/o/r/git/refs/heads/main -f sha=1")
        self.assertDenied("git ref", "maeng-ship merge")
        self.git(self.repo, "config", "alias.pr", "!gh pr")
        self.assertDenied("git pr merge 1", "maeng-ship merge")  # git appends the arguments to a ! alias
        self.assertAllowed("git pr view 1")
        self.assertDenied("gh api graphql -F 'query={branch}'", "cannot be checked")
        self.assertAllowed("gh pr create --fill")  # on feat
        (self.repo / ".maeng").mkdir(exist_ok=True)
        (self.repo / ".maeng/verify.json").write_text('{"protected_branches": ["release"]}')
        self.assertTrue(self.pre(self.repo, "mcp__github__push_files", {"branch": "release"})[0])
        self.assertFalse(self.pre(self.repo, "mcp__github__push_files", {"branch": "feat"})[0])
        (self.repo / ".maeng/verify.json").unlink()
        self.git(self.repo, "checkout", "-q", "main")
        self.assertDenied("git push --recurse-submodules on-demand origin", "default branch")
        self.assertDenied("gh pr create --base feat --fill", "default branch")
        self.assertDenied("gh pr new --base feat --fill", "default branch")
        self.assertDenied("if git push origin main; then echo pushed; fi", "default branch")
        self.assertDenied('PR=1; gh api -X PUT "repos/o/r/pulls/$PR/merge"', "maeng-ship merge")
        self.assertAllowed("gh pr create --base feat --head feat --fill")

    def test_mcp_merge_is_denied_and_other_mcp_writes_allowed(self):
        for tool, tin in (("mcp__github__merge_pull_request", {"owner": "o", "repo": "r", "pull_number": 1}),
                          ("mcp__github__push_files", {"owner": "o", "repo": "r", "branch": "main"}),
                          ("mcp__github__create_or_update_file", {"owner": "o", "repo": "r", "path": "a"}),
                          ("mcp__github__delete_file", {"owner": "o", "repo": "r", "branch": "refs/heads/main"})):
            self.assertTrue(self.pre(self.repo, tool, tin)[0], tool)
        for tool, tin in (("mcp__github__create_pull_request", {"owner": "o", "repo": "r", "head": "feat"}),
                          ("mcp__notion-maeng__notion-create-pages", {"parent": "db111111111111111111111111111111"}),
                          ("mcp__linear-eta__save_issue", {"title": "x"})):
            self.assertFalse(self.pre(self.repo, tool, tin)[0], tool)


class GhRoutes(ShipBase):
    def test_gh_allowed_routes(self):
        for cmd in ("gh pr comment 1 -R o/r -b hi", "gh pr edit 1 -R o/r --title t", "gh pr review 1 -R o/r --approve",
                    "gh pr ready 1 -R o/r", "gh pr close 1 -R o/r", "gh issue create -R o/r -t x -b y",
                    "gh issue comment 2 --repo o/r -b z", "gh pr checkout 3",
                    "gh pr view 1 --json state", "gh pr list", "gh api repos/o/r/pulls", "gh api user",
                    "gh api graphql -f query='query { viewer { login } }'", "gh run list", "gh release list"):
            self.assertAllowed(cmd)

    def test_pr_create_reminds_review_tier(self):
        self.verified()
        rc, out, _ = self.hook("PostToolUse", self.repo, tool_name="Bash", tool_input={"command": "gh pr create --fill"},
                               tool_use_id="x", tool_response={"stdout": "https://github.com/o/r/pull/1"})
        self.assertIn("maeng-review", out["hookSpecificOutput"]["additionalContext"])


class GitExecVectors(ShipBase):
    """C1: config and environment that make a read-only-looking git command run an arbitrary program."""

    def test_benign_global_config_and_plain_reads_still_allowed(self):
        for cmd in ("git -c color.ui=never log", "git log", "git -c user.name=x status", "git status",
                    "git -c core.quotepath=false diff", "git -c color.ui=never -c user.email=a@b log",
                    "git --config-env=user.name=NAME status"):
            self.assertAllowed(cmd)

    def test_env_exec_vars_stay_allowed_without_git_and_other_vars_with_git(self):
        for cmd in ("PAGER=cat ls", "GIT_PAGER=x echo hi", "LC_ALL=C git log", "env LANG=C git status",
                    "GIT_AUTHOR_NAME=x git log"):
            self.assertAllowed(cmd)

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
