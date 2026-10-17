"""Regression tests for the round-9 R1b findings (PR #38, MAE-216): git builtins that execute a caller-supplied command
(1), the closed gh surface pinned by equality (2), the MAENG_* prefix rule in Bash (3), the unknown-world closure of the
Notion and linear-endix write sets (4), and harness state written only by the maeng CLIs (5)."""
import os

from maeng import gates, ghcmd, guard, receipts, state
from .helpers import HarnessCase
from .test_g1 import ShipBase

NOTION = "mcp__claude_ai_Notion__"
ETA_SLUG = "maengseojun/eta_v1"


class R9_1_GitExecBuiltins(ShipBase):
    EXEC = ("git submodule foreach 'make deploy'", "git submodule --quiet foreach --recursive make",
            "git rebase -x 'make test' main", "git rebase --exec 'make test' main", "git rebase --exec='make test' main",
            "git rebase -ix make main", "git rebase --exe make main", "git rebase -xmake main",
            "git bisect run make test", "git bisect run sh -c 'make'", "git filter-branch",
            "git filter-branch --tree-filter 'rm x' HEAD", "git filter-branch --index-filter 'git rm x' HEAD",
            "git filter-branch --msg-filter cat HEAD", "git difftool -x cat HEAD", "git difftool --extcmd=cat HEAD",
            "git difftool --extcmd cat", "git difftool -yx cat", "git difftool -t vimdiff", "git difftool --tool=meld",
            "git difftool -ytmeld", "git mergetool -t vimdiff", "git mergetool --tool=meld", "git mergetool --too meld",
            "git grep --open-files-in-pager=vim foo", "git grep -Ovim foo", "git fetch --upload-pack='sh x' origin",
            "git pull --upload-pack=x origin feat", "git ls-remote --upload-pack=x origin",
            "git archive --remote=origin --exec=x HEAD", "git send-email --sendmail-cmd=x a.patch")

    def test_the_same_builtins_without_a_command_stay_allowed(self):
        self.verified()
        for cmd in ("git rebase main", "git rebase -i main", "git rebase --onto main feat", "git rebase -Xours main",
                    "git rebase --empty=drop main", "git bisect start", "git bisect good", "git bisect bad HEAD",
                    "git bisect reset", "git difftool HEAD~1", "git difftool -y HEAD~1", "git difftool --tool-help",
                    "git difftool -Stext HEAD~1", "git mergetool", "git mergetool --tool-help", "git submodule status",
                    "git submodule update --init", "git submodule update --remote", "git grep foo", "git grep -n foo",
                    "git fetch origin", "git ls-remote origin"):
            with self.subTest(cmd=cmd):
                self.assertAllowed(cmd)

class R9_6_GitExecConfig(ShipBase):
    """A config key whose value git runs as a program is a command route too: setting it is denied, reading or
    unsetting it is not, and ordinary keys stay settable."""

    def test_reads_unsets_and_ordinary_keys_are_allowed(self):
        self.verified()
        for cmd in ("git config --get core.sshCommand", "git config --get-all alias.p", "git config --list",
                    "git config get core.pager", "git config --unset core.pager", "git config unset core.editor",
                    "git config user.name x", "git config pull.rebase true", "git config core.autocrlf false",
                    "git clone -c http.version=HTTP/1.1 https://github.com/o/r"):
            with self.subTest(cmd=cmd):
                self.assertAllowed(cmd)


class R9_2_GhSurfacePinned(ShipBase):
    MUTATING = ("gh repo create o/new --private", "gh gist create f.txt", "gh variable set X --body y",
                "gh label create bug", "gh label delete bug", "gh project item-add 1 --owner o --url u",
                "gh ssh-key add k.pub", "gh gpg-key add k.asc", "gh codespace create", "gh ruleset create",
                "gh ruleset delete 1", "gh auth login", "gh auth setup-git")

    def test_the_gh_surface_is_pinned_by_equality(self):
        self.assertEqual(ghcmd.GH_OPEN_GROUPS, {"issue", "search", "status", "browse", "completion", "help", "version"})
        self.assertEqual(ghcmd.GH_WRITES, {("pr", "comment"), ("pr", "edit"), ("pr", "review"), ("pr", "ready"),
                                           ("pr", "close")})
        self.assertEqual(ghcmd.GH_GATED, {("pr", "create")})
        self.assertEqual(ghcmd.LOCAL_WRITES, {("pr", "checkout"), ("repo", "clone"), ("repo", "set-default"),
                                              ("release", "download"), ("run", "download"), ("gist", "clone")})
        self.assertEqual(ghcmd.GH_READS, {
            ("alias", "list"), ("auth", "status"), ("auth", "token"), ("cache", "list"), ("config", "get"),
            ("config", "list"), ("extension", "browse"), ("extension", "list"), ("extension", "search"),
            ("gist", "list"), ("gist", "view"), ("gpg-key", "list"), ("label", "list"), ("pr", "checks"),
            ("pr", "diff"), ("pr", "list"), ("pr", "status"), ("pr", "view"), ("release", "list"),
            ("release", "view"), ("repo", "list"), ("repo", "view"), ("ruleset", "check"), ("ruleset", "list"),
            ("ruleset", "view"), ("run", "list"), ("run", "view"), ("run", "watch"), ("secret", "list"),
            ("ssh-key", "list"), ("variable", "get"), ("variable", "list"), ("workflow", "list"),
            ("workflow", "view")})
        self.assertEqual(ghcmd.DENIED_ACTIONS, {
            "issue": {"delete"}, "repo": {"delete", "archive", "unarchive", "rename", "edit"},
            "release": {"delete", "delete-asset", "create", "edit", "upload"}})
        self.assertEqual(ghcmd.STRICT_READ, {
            "pr": {"view", "list", "diff", "checks", "status"}, "issue": {"view", "list", "status"},
            "repo": {"view"}, "run": {"view", "list"}, "release": {"view", "list"}, "workflow": {"view", "list"}})
        for group, action in ghcmd.GH_READS:
            self.assertEqual(ghcmd.classify_gh(["gh", group, action])[0], "read", (group, action))
        for group, action in ghcmd.GH_WRITES:
            self.assertEqual(ghcmd.classify_gh(["gh", group, action, "1"])[0], "write", (group, action))

    def test_classification_of_the_mutating_commands_is_deny(self):
        for cmd in self.MUTATING:
            with self.subTest(cmd=cmd):
                self.assertEqual(ghcmd.classify_gh(cmd.split())[0], "deny")


class R9_3_MaengPrefixRule(ShipBase):
    def test_reading_a_maeng_variable_stays_allowed(self):
        for cmd in ("echo $MAENG_HOME", "printenv MAENG_SESSION_ID", "echo MAENG_TEST_FIXTURES", "env | grep MAENG_",
                    "export PATH=/usr/bin:$PATH"):
            with self.subTest(cmd=cmd):
                self.assertAllowed(cmd)


class R9_4_UnknownWorldClosure(HarnessCase):
    LINEAR_WRITES = ("save_issue", "save_comment", "save_document", "save_project", "save_milestone",
                     "save_status_update", "create_attachment", "create_issue_label", "update_diff",
                     "delete_comment", "delete_attachment", "delete_status_update")

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.start(self.repo)
        (self.repo / ".claude").mkdir(exist_ok=True)
        (self.repo / ".claude/settings.json").write_text("{ not json")
        self.assertEqual(guard.classify(self.repo), guard.UNKNOWN)

class R9_5_HarnessStateWrites(ShipBase):
    def targets(self):
        return {"receipt": receipts.receipts_dir() / "x.json", "registry": receipts._notion("registry.json"),
                "journal": receipts._notion("journal.json"), "session": state.path_for(self.sid),
                "cache": self.cache / "guard.json"}

    def test_file_tools_cannot_write_harness_state(self):
        for what, path in self.targets().items():
            for tool, tin in (("Write", {"file_path": str(path), "content": "{}"}),
                              ("Edit", {"file_path": str(path), "old_string": "a", "new_string": "b"}),
                              ("MultiEdit", {"file_path": str(path), "edits": []}),
                              ("NotebookEdit", {"notebook_path": str(path), "new_source": "x"})):
                with self.subTest(what=what, tool=tool):
                    denied, reason = self.pre(self.repo, tool, tin)
                    self.assertTrue(denied)
                    self.assertIn("harness state", reason)
        self.assertFalse(self.pre(self.repo, "Write", {"file_path": str(self.repo / "ok.txt"), "content": "x"})[0])

    def test_a_symlink_into_harness_state_is_denied(self):
        receipts.receipts_dir().mkdir(parents=True, exist_ok=True)
        os.symlink(receipts.receipts_dir(), self.repo / "rlink")
        denied, reason = self.pre(self.repo, "Write", {"file_path": "rlink/x.json", "content": "{}"})
        self.assertTrue(denied)
        self.assertIn("harness state", reason)

