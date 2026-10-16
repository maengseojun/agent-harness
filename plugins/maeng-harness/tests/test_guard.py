import json
import os
import time

from maeng import guard
from .helpers import HarnessCase


class GuardTests(HarnessCase):
    def test_remote_parsing(self):
        for url in ("https://github.com/maengseojun/eta_v1.git", "git@github.com:maengseojun/eta_v1.git",
                    "ssh://git@github.com/endix-foundation-v1/x", "endix-foundation-v1/anything",
                    "https://github.com/Endix-Foundation-V1/Y.git"):
            self.assertTrue(guard.remote_is_eta(url), url)
        for url in ("https://github.com/maengseojun/agent-harness.git", "other/eta_v1", "", None):
            self.assertFalse(guard.remote_is_eta(url), url)

    def test_path_prefix_is_eta(self):
        (self.eta_root / "dev/web").mkdir(parents=True)
        self.assertEqual(guard.classify(self.eta_root / "dev/web"), guard.ETA)
        self.assertEqual(guard.classify(self.eta_root / "not/yet/created.txt"), guard.ETA)

    def test_personal_repo_and_plain_dir(self):
        repo = self.make_repo()
        self.assertEqual(guard.classify(repo), guard.PERSONAL)
        plain = self.tmp / "plain"
        plain.mkdir()
        self.assertEqual(guard.classify(plain), guard.PERSONAL)

    def test_origin_triggers(self):
        for i, url in enumerate(("https://github.com/maengseojun/eta_v1.git", "git@github.com:endix-foundation-v1/web.git")):
            repo = self.make_repo(f"r{i}", with_remote=False)
            self.git(repo, "remote", "add", "origin", url)
            self.assertEqual(guard.classify(repo), guard.ETA, url)

    def test_project_settings_enable_eta_rules(self):
        repo = self.make_repo("proj", with_remote=False)
        (repo / ".claude").mkdir()
        (repo / ".claude/settings.json").write_text(json.dumps({"enabledPlugins": {"eta-rules@eta": True}}))
        self.assertEqual(guard.classify(repo), guard.ETA)
        # a local override to false wins
        (repo / ".claude/settings.local.json").write_text(json.dumps({"enabledPlugins": {"eta-rules@eta": False}}))
        self.assertEqual(guard.classify(repo), guard.PERSONAL)

    def test_unknown_on_failure(self):
        repo = self.make_repo("broken", with_remote=False)
        (repo / ".git/config").write_text("[core\n  broken")
        self.assertEqual(guard.classify(repo), guard.UNKNOWN)
        bad = self.make_repo("badsettings", with_remote=False)
        (bad / ".claude").mkdir()
        (bad / ".claude/settings.json").write_text("{not json")
        self.assertEqual(guard.classify(bad), guard.UNKNOWN)

    def test_linked_worktree_origin_change_invalidates_cache(self):
        repo = self.make_repo()
        wt = self.tmp / "wt"
        self.git(repo, "worktree", "add", "-q", "-b", "wt-branch", str(wt))
        self.assertEqual(guard.classify(wt), guard.PERSONAL)
        self.assertEqual(guard.classify(wt), guard.PERSONAL)  # served from cache
        self.git(repo, "remote", "set-url", "origin", "https://github.com/endix-foundation-v1/web.git")
        os.utime(repo / ".git/config", None)
        self.assertEqual(guard.classify(wt), guard.ETA)
        self.assertEqual(guard.classify(repo), guard.ETA)

    def test_config_worktree_and_settings_changes_invalidate_cache(self):
        repo = self.make_repo()
        self.git(repo, "config", "extensions.worktreeConfig", "true")
        self.assertEqual(guard.classify(repo), guard.PERSONAL)
        time.sleep(0.01)
        self.git(repo, "config", "--worktree", "remote.origin.url", "https://github.com/maengseojun/eta_v1.git")
        self.assertEqual(guard.classify(repo), guard.ETA)
        repo2 = self.make_repo("second")
        self.assertEqual(guard.classify(repo2), guard.PERSONAL)
        (repo2 / ".claude").mkdir()
        (repo2 / ".claude/settings.local.json").write_text(json.dumps({"enabledPlugins": {"eta-rules@eta": True}}))
        self.assertEqual(guard.classify(repo2), guard.ETA)

    def test_cache_lives_outside_state_dir(self):
        repo = self.make_repo()
        guard.classify(repo)
        self.assertTrue((self.cache / "guard.json").exists())
        self.assertFalse(self.maeng_home.exists())

    def test_eta_checkout_enumeration_and_isolation_state(self):
        root = self.eta_root
        root.mkdir()
        self.git(root, "init", "-q", "-b", "main")
        (root / "f").write_text("x")
        self.git(root, "add", "-A")
        self.git(root, "commit", "-qm", "i")
        (root / "dev/contracts").mkdir(parents=True)
        wt = self.tmp / "eta-wt"
        self.git(root, "worktree", "add", "-q", "-b", "b", str(wt))
        found = {str(p.resolve()) for p in guard.eta_checkouts()}
        self.assertTrue({str(root.resolve()), str(wt.resolve()), str((root / "dev/contracts").resolve())} <= found)
        self.assertTrue(guard.isolation_missing(root))
