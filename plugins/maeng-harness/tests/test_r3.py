"""Regression tests for Astra round-3 findings (PR #38, MAE-220): gh effective repository (1), stale default branch (2),
recursive push (3), Notion revocation (4), launcher evidence (5), malformed operation fields (6), bare filesystem
operands (7), gh local writes (8), reconcile repository check (9)."""
import json
import stat
import subprocess
import sys

from maeng import evidence, receipts
from maeng.common import canonical, sha256
from .helpers import HarnessCase
from .test_g1 import ShipBase
from .test_g2_g3 import CREATE, DB, G2Tests
from .test_merge import MergeBase

ETA_URL = "git@github.com:endix-foundation-v1/web.git"


def fake_git(tmp, name, symref_stdout=None, fail=False):
    """A MAENG_GIT stand-in: answers `ls-remote --symref`, delegates everything else to the real git."""
    path = tmp / name
    if fail:
        body = "if 'ls-remote' in sys.argv:\n    print('fatal: unable to access', file=sys.stderr); sys.exit(128)\n"
    else:
        body = f"if '--symref' in sys.argv:\n    sys.stdout.write({symref_stdout!r}); sys.exit(0)\n"
    path.write_text(f"#!{sys.executable}\nimport subprocess, sys\n{body}"
                    f"sys.exit(subprocess.run(['git'] + sys.argv[1:]).returncode)\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


class R3_2_StaleDefaultBranch(ShipBase):
    def test_agreeing_remote_allows(self):
        self.verified()
        self.env["MAENG_GIT"] = fake_git(self.tmp, "ok-git", "ref: refs/heads/main\tHEAD\n" + "a" * 40 + "\tHEAD\n")
        self.assertFalse(self.bash_pre(self.repo, "git push origin feat")[0])


class R3_3_RecursivePush(ShipBase):
    def test_check_value_is_not_recursive(self):
        self.verified()
        self.git(self.repo, "config", "push.recurseSubmodules", "check")
        self.assertFalse(self.bash_pre(self.repo, "git push origin feat")[0])


class R3_4_NotionRevocation(G2Tests):
    def test_revocation_is_scoped_to_digest_destination_and_op(self):
        key = self.sol_pass(self.payload, DB, "create")
        subject = {"kind": "notion", "digest": sha256(canonical(self.payload)), "destination": "other", "op": "create"}
        self.assertEqual(receipts.revoke_passes(subject, "fail"), [])
        self.assertEqual(receipts.load(key).get("revoked"), None)

class R3_5_LauncherEvidence(HarnessCase):
    def rec(self, cmd):
        return evidence.recognize(cmd)

    def test_python_interpreter_options_before_m_are_not_evidence(self):
        for cmd in ("python3 --version -m pytest", "python -V -m pytest", "python3 -h -m pytest",
                    "python3 -c 'print(1)' -m pytest", "python3 -X dev -m pytest", "python3 tests/run.py -m pytest",
                    "python3.12 --help -m pytest", "python3 pytest -m unit", "python3 -W error -m pytest"):
            self.assertIsNone(self.rec(cmd), cmd)

    def test_python_plain_options_then_m_are_evidence(self):
        for cmd in ("python3 -m pytest", "python -B -m pytest -q", "python3.11 -u -I -E -s -m pytest tests",
                    "python3 -B -m unittest discover"):
            self.assertIsNotNone(self.rec(cmd), cmd)

    def test_launcher_level_help_and_version_are_not_evidence(self):
        for cmd in ("npx --help playwright test", "npx --version playwright test", "npx -h playwright test",
                    "npm exec --help playwright test", "pnpm dlx --version playwright test",
                    "yarn dlx -h playwright test", "npx playwright test --help"):
            self.assertIsNone(self.rec(cmd), cmd)
        self.assertIsNotNone(self.rec("npx -y playwright test"))
        self.assertIsNotNone(self.rec("npx --package pw playwright test"))


class R3_6_MalformedOperationFields(HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.start(self.repo)

    def test_missing_or_non_string_tool_name_is_denied(self):
        for fields in ({"tool_input": {"command": "git push origin main"}},
                       {"tool_name": 5, "tool_input": {"command": "ls"}},
                       {"tool_name": "", "tool_input": {}}):
            rc, out, err = self.hook("PreToolUse", self.repo, **fields)
            self.assertTrue(rc == 2 or out["hookSpecificOutput"]["permissionDecision"] == "deny", fields)

class EtaDirMixin:
    def make_eta_dir(self, parent, name="eta_checkout"):
        d = parent / name
        d.mkdir()
        self.git(d, "init", "-q", "-b", "main")
        self.git(d, "remote", "add", "origin", ETA_URL)
        return d


class R3_7_BareFilesystemOperands(EtaDirMixin, HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.start(self.repo)
        self.eta_dir = self.make_eta_dir(self.repo)

    def test_bare_names_in_personal_space_are_allowed(self):
        for cmd in ("cp app.py copy.py", "touch notes.txt", "mkdir build", "mv app.py renamed.py"):
            self.assertFalse(self.bash_pre(self.repo, cmd)[0], cmd)

class R3_8_GhLocalWrites(EtaDirMixin, HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.start(self.repo)
        self.eta_dir = self.make_eta_dir(self.repo)

    def test_remote_reads_stay_reads_in_eta(self):
        for cmd in ("gh pr view 1", "gh pr list", "gh run view 5", "gh release view v1", "gh repo view o/r",
                    "gh issue view 1"):
            self.assertFalse(self.bash_pre(self.repo, f"cd eta_checkout && {cmd}")[0], cmd)


class R3_9_ReconcileRepository(MergeBase):
    def test_reconcile_from_another_repository_leaves_the_receipt_pending(self):
        key = self.verdict()
        r = self.ship(MAENG_GIT=self.fake_git("lost-git", self.LOST_RESPONSE))
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertEqual(self.status(key), "pending")
        fork_remote = self.tmp / "fork.git"
        self.git(self.tmp, "clone", "-q", "--bare", str(self.remote), str(fork_remote))
        fork = self.tmp / "fork"
        self.git(self.tmp, "clone", "-q", str(fork_remote), str(fork))
        out = self.cli("maeng-review", ["reconcile", "--repo", str(fork)], fork)
        self.assertIn("checkout of", out.stdout)
        self.assertIn("pending", out.stdout)
        self.assertEqual(self.status(key), "pending")
        out = self.cli("maeng-review", ["reconcile", "--repo", str(self.repo)], self.repo)
        self.assertIn("consumed", out.stdout)
        self.assertEqual(self.status(key), "consumed")
