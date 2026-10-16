import importlib.machinery
import importlib.util
import json
import os
import stat
import sys

from maeng import guard, receipts
from maeng.common import canonical, sha256
from .helpers import BIN, HarnessCase


def load_bin(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_"), str(BIN / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


class ReviewConfig(HarnessCase):
    def test_tier_selection(self):
        rv = load_bin("maeng-review")
        child = {"parent": "MAE-216", "criteria": ["AC-1"]}
        self.assertEqual(rv.tier_for("code", child), ("gpt-6-astra", "medium"))
        self.assertEqual(rv.tier_for("code", {"criteria": ["AC-1"]}), ("gpt-6.1-sol", "xhigh"))
        self.assertEqual(rv.tier_for("code", None), ("gpt-6.1-sol", "xhigh"))
        self.assertEqual(rv.tier_for("parent", child), ("gpt-6-astra", "xhigh"))
        self.assertEqual(rv.tier_for("docs", None), ("gpt-6-astra", "high"))
        self.assertEqual(rv.tier_for("notion", None), ("gpt-6.1-sol", "medium"))

    def test_isolated_flags_and_default_binary(self):
        rv = load_bin("maeng-review")
        cmd = rv.codex_command("gpt-6-astra", "medium", "/s.json", "/o.json")
        self.assertEqual(cmd[0], "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex")
        self.assertEqual(cmd[1:4], ["exec", "--ignore-user-config", "--ignore-rules"])
        disabled = [cmd[i + 1] for i, a in enumerate(cmd) if a == "--disable"]
        self.assertEqual(disabled, ["apps", "browser", "computer_use", "hooks", "plugins", "memories", "multi_agent", "image"])
        self.assertEqual(cmd[cmd.index("--sandbox") + 1], "read-only")
        self.assertIn('approval_policy="never"', cmd)
        self.assertIn("--ephemeral", cmd)
        self.assertEqual(cmd[cmd.index("--output-schema") + 1], "/s.json")
        self.assertIn('model_reasoning_effort="medium"', cmd)
        self.assertFalse(any("dangerously" in a for a in cmd))
        os.environ["MAENG_CODEX"] = "/x/fake"
        self.assertEqual(rv.codex_command("m", "high", "s", "o")[0], "/x/fake")


class ReviewRun(HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.base = self.head(self.repo)
        self.git(self.repo, "checkout", "-qb", "feat")
        (self.repo / "app.py").write_text("print('feature')\n")
        self.h = self.commit_all(self.repo, "feature")
        self.start(self.repo)
        self.run_check(self.repo, "pytest -q")
        self.log = self.tmp / "codex.log"
        self.stdin_log = self.tmp / "codex.stdin"
        self.result = self.tmp / "codex-result.json"
        self.result.write_text(json.dumps({"verdict": "pass", "findings": []}))
        self.codex = self.tmp / "fake-codex"
        self.codex.write_text(
            f"#!{sys.executable}\nimport json, sys\n"
            f"open({str(self.log)!r}, 'w').write(json.dumps(sys.argv[1:]))\n"
            f"open({str(self.stdin_log)!r}, 'w').write(sys.stdin.read())\n"
            f"out = sys.argv[sys.argv.index('-o') + 1]\n"
            f"open(out, 'w').write(open({str(self.result)!r}).read())\n")
        self.codex.chmod(self.codex.stat().st_mode | stat.S_IEXEC)
        plan = self.tmp / "plan.md"
        plan.write_text("AC-1 feature works\n## Verification\nAC-1: pytest\n")
        self.cli("maeng-verify", ["bind", "MAE-221", "--plan", str(plan), "--parent", "MAE-216"], self.repo)
        self.cli("maeng-verify", ["plan", "--met", "AC-1"], self.repo)

    def review(self, *extra):
        return self.cli("maeng-review", ["run", "--kind", "code", "--pr", "7", "--base", self.base, "--head", self.h,
                                         "--base-ref", "main", *extra], self.repo, extra_env={"MAENG_CODEX": str(self.codex)})

    def test_pass_verdict_is_stored_as_receipt_with_exact_flags(self):
        r = self.review()
        self.assertEqual(r.returncode, 0, r.stderr)
        argv = json.loads(self.log.read_text())
        self.assertEqual(argv[argv.index("-m") + 1], "gpt-6-astra")
        self.assertIn('model_reasoning_effort="medium"', argv)
        for flag in ("--ignore-user-config", "--ignore-rules", "--ephemeral"):
            self.assertIn(flag, argv)
        bundle = self.stdin_log.read_text()
        for needle in (self.base, self.h, "AC-1", "feature", "pytest"):
            self.assertIn(needle, bundle)
        key = json.loads(r.stdout)["receipt"]
        rec = receipts.load(key)
        self.assertEqual(rec["status"], "unconsumed")
        s = rec["verdict"]["subject"]
        self.assertEqual((s["base"], s["head"], s["destination"], s["op"]), (self.base, self.h, "refs/heads/main", "merge"))
        self.assertEqual(rec["verdict"]["reviewer"], {"model": "gpt-6-astra", "effort": "medium"})
        self.assertTrue(s["criteria_rev"])

    def test_fail_verdict_stores_no_receipt(self):
        self.result.write_text(json.dumps({"verdict": "fail", "findings": [
            {"severity": "high", "title": "bug", "body": "b", "file": "app.py", "line": 1}]}))
        r = self.review()
        self.assertEqual(r.returncode, 1)
        self.assertIsNone(json.loads(r.stdout)["receipt"])
        self.assertEqual(list(receipts.receipts_dir().glob("*.json")) if receipts.receipts_dir().exists() else [], [])

    def test_schema_violation_from_reviewer_is_an_error(self):
        self.result.write_text(json.dumps({"verdict": "maybe", "findings": []}))
        r = self.review()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("schema", r.stderr)

    def test_oversized_bundle_is_blocked_without_calling_reviewer(self):
        r = self.review("--max-bytes", "10")
        self.assertEqual(r.returncode, 2)
        out = json.loads(r.stdout)
        self.assertEqual(out["verdict"], "blocked")
        self.assertIn("--max-bytes", out["findings"][0]["body"])
        self.assertFalse(self.log.exists())

    def test_path_scope_limits_bundle_and_lists_exclusions(self):
        r = self.review("--exclude", "app.py", "--exclusion-reason", "verbatim copy")
        self.assertEqual(r.returncode, 0, r.stderr)
        sent = self.stdin_log.read_text()
        bundle = json.loads(sent[sent.index("\n{") + 1:])  # stdin = prompt text, then the bundle JSON
        self.assertEqual(bundle["scope"]["excluded_files"], ["app.py"])
        self.assertEqual(bundle["scope"]["exclusion_reason"], "verbatim copy")
        self.assertNotIn("app.py", bundle["changed_files"])
        self.assertNotIn("app.py", bundle["diff"])

    def test_incomplete_bundle_is_blocked_without_calling_reviewer(self):
        r = self.cli("maeng-review", ["run", "--kind", "code", "--pr", "7", "--base", self.base, "--head", self.h],
                     self.repo, extra_env={"MAENG_CODEX": str(self.codex)})
        self.assertEqual(r.returncode, 2)
        self.assertEqual(json.loads(r.stdout)["verdict"], "blocked")
        self.assertFalse(self.log.exists())

    def test_notion_review_digest_binds_the_payload(self):
        payload = {"parent": {"data_source_id": "db111111111111111111111111111111"}, "pages": [{"title": "x"}]}
        pf = self.tmp / "payload.json"
        pf.write_text(json.dumps(payload))
        r = self.cli("maeng-review", ["run", "--kind", "notion", "--payload", str(pf), "--destination",
                                      "db111111111111111111111111111111", "--op", "create"], self.repo,
                     extra_env={"MAENG_CODEX": str(self.codex)})
        self.assertEqual(r.returncode, 0, r.stderr)
        argv = json.loads(self.log.read_text())
        self.assertEqual(argv[argv.index("-m") + 1], "gpt-6.1-sol")
        self.assertIn('model_reasoning_effort="medium"', argv)
        rec, problem = receipts.find_notion(sha256(canonical(payload)), "db111111111111111111111111111111", "create")
        self.assertIsNotNone(rec, problem)


class VerifyCli(HarnessCase):
    def test_bind_status_and_suggestions(self):
        repo = self.make_repo()
        self.start(repo)
        r = self.cli("maeng-verify", ["bind", "MAE-5", "--criteria", "AC-1,AC-2", "--check", "pytest",
                                      "--plan-updated", "2026-10-17"], repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        b = self.load_state()["binding"]
        self.assertEqual((b["issue"], b["criteria"], b["checks"]), ("MAE-5", ["AC-1", "AC-2"], ["pytest"]))
        sugg = json.loads((self.maeng_home / "last-bindings.json").read_text())
        self.assertEqual(sugg[os.path.realpath(repo)]["issue"], "MAE-5")
        st = json.loads(self.cli("maeng-verify", ["status"], repo).stdout)
        self.assertFalse(st["ship_verified"])
        self.run_check(repo, "pytest -q")
        st = json.loads(self.cli("maeng-verify", ["status"], repo).stdout)
        self.assertFalse(st["ship_verified"])             # criteria AC-1/AC-2 have no plan record yet
        self.assertIn("no plan record", " ".join(st["missing"]))
        self.cli("maeng-verify", ["ran", "--fail", "manual check"], repo)
        ev = self.load_state()["evidence"]
        self.assertFalse(ev[-1]["ok"])

    def test_requires_session_and_personal_world(self):
        repo = self.make_repo()
        env = {k: v for k, v in self.env.items()}
        import subprocess
        p = subprocess.run([sys.executable, str(BIN / "maeng-verify"), "skip", "x"], cwd=repo, env=env,
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)
        self.assertIn("no session", p.stderr)
        self.eta_root.mkdir()
        p = self.cli("maeng-verify", ["skip", "x"], self.eta_root)
        self.assertEqual(p.returncode, 2)
        self.assertIn("eta", p.stderr)

    def test_session_found_by_cwd_without_env(self):
        repo = self.make_repo()
        self.start(repo)
        import subprocess
        p = subprocess.run([sys.executable, str(BIN / "maeng-verify"), "decision", "x"], cwd=repo, env=self.env,
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)


class EtaIsolate(HarnessCase):
    def setUp(self):
        super().setUp()
        root = self.eta_root
        root.mkdir()
        self.git(root, "init", "-q", "-b", "main")
        (root / ".gitignore").write_text(".claude/settings.local.json\n")
        (root / "f").write_text("x")
        self.git(root, "add", "-A")
        self.git(root, "commit", "-qm", "i")
        self.wt = self.tmp / "eta-wt"
        self.git(root, "worktree", "add", "-q", "-b", "b", str(self.wt))
        (root / ".claude").mkdir()
        (root / ".claude/settings.local.json").write_text(json.dumps({"permissions": {"allow": ["Bash(ls)"]}}))

    def isolate(self, *args):
        return self.cli("maeng-eta-isolate", list(args), self.tmp)

    def test_dry_run_is_default_and_writes_nothing(self):
        before = (self.eta_root / ".claude/settings.local.json").read_text()
        r = self.isolate()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("would write", r.stdout)
        self.assertIn("dry run", r.stdout)
        self.assertEqual((self.eta_root / ".claude/settings.local.json").read_text(), before)
        r = self.isolate("--dry-run")
        self.assertIn("would write", r.stdout)

    def test_apply_merges_keys_and_is_idempotent(self):
        sub = self.eta_root / "dev/contracts"
        sub.mkdir(parents=True)
        self.git(sub, "init", "-q")
        (sub / ".gitignore").write_text(".claude/settings.local.json\n")
        r = self.isolate("--apply")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads((self.eta_root / ".claude/settings.local.json").read_text())
        self.assertEqual(data["permissions"], {"allow": ["Bash(ls)"]})          # existing keys preserved
        self.assertEqual(data["enabledPlugins"], {"maeng-harness@maeng": False, "linear@synced": False,
                                                  "commit-commands@claude-plugins-official": False})
        for checkout in (self.eta_root, self.wt, sub):
            self.assertFalse(guard.isolation_missing(checkout), checkout)
        self.assertIn("already isolated", self.isolate("--apply").stdout)

    def test_refuses_tracked_or_unignored_settings_and_bad_json(self):
        (self.eta_root / ".gitignore").write_text("")
        self.git(self.eta_root, "add", "-A")
        self.git(self.eta_root, "commit", "-qm", "unignore")
        r = self.isolate("--apply")
        self.assertIn("not git-ignored", r.stdout)
        self.assertNotIn("enabledPlugins", (self.eta_root / ".claude/settings.local.json").read_text())
        (self.eta_root / ".gitignore").write_text(".claude/settings.local.json\n")
        self.git(self.eta_root, "add", "-f", "-A")
        (self.eta_root / ".claude/settings.local.json").write_text("{broken")
        self.git(self.eta_root, "add", "-f", ".claude/settings.local.json")
        self.git(self.eta_root, "commit", "-qm", "track it")
        r = self.isolate("--apply")
        self.assertIn("refusing to touch", r.stdout)
        self.git(self.eta_root, "rm", "-q", "--cached", ".claude/settings.local.json")
        r = self.isolate("--apply")
        self.assertIn("cannot merge", r.stdout)
        self.assertEqual((self.eta_root / ".claude/settings.local.json").read_text(), "{broken")
