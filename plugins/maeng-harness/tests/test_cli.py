import importlib.machinery
import importlib.util
import json
from pathlib import Path
import tempfile
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

    def test_feature_names_come_from_codex_features_list(self):
        rv = load_bin("maeng-review")
        fake = self.tmp / "codex-features" if hasattr(self, "tmp") else Path(tempfile.mkdtemp()) / "codex-features"
        fake.write_text(f"#!{sys.executable}\nprint('apps stable true\\nbrowser_use stable true\\nplugins stable false\\nshell_tool stable true\\nimage_generation stable true')\n")
        fake.chmod(0o755)
        self.assertEqual(rv.features_to_disable(str(fake)), ["apps", "browser_use", "image_generation"])
        self.assertEqual(rv.features_to_disable("/nonexistent/codex"), [])

    def test_isolated_flags_and_default_binary(self):
        rv = load_bin("maeng-review")
        rv.features_to_disable = lambda codex: ["apps", "browser_use", "hooks"]  # real names come from `features list`
        cmd = rv.codex_command("gpt-6-astra", "medium", "/s.json", "/o.json")
        self.assertIn(cmd[0], rv.CODEX_CANDIDATES)  # ChatGPT.app-bundled CLI (npm codex is broken here)
        self.assertEqual(cmd[1:4], ["exec", "--ignore-user-config", "--ignore-rules"])
        disabled = [cmd[i + 1] for i, a in enumerate(cmd) if a == "--disable"]
        self.assertEqual(disabled, ["apps", "browser_use", "hooks"])
        self.assertEqual(cmd[cmd.index("--sandbox") + 1], "read-only")
        self.assertIn('approval_policy="never"', cmd)
        self.assertIn("--ephemeral", cmd)
        self.assertEqual(cmd[cmd.index("--output-schema") + 1], "/s.json")
        self.assertIn('model_reasoning_effort="medium"', cmd)
        self.assertFalse(any("dangerously" in a for a in cmd))
        os.environ["MAENG_CODEX"] = "/x/fake"
        self.assertEqual(rv.codex_command("m", "high", "s", "o")[0], "/x/fake")


class ReviewRunFixture(HarnessCase):
    """Shared repo + fake codex fixture. Holds no test methods so subclasses do not re-run each other's tests."""

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
            f"if sys.argv[1:3] == ['features', 'list']:\n"
            f"    print('apps stable true\\nbrowser_use stable true\\nshell_tool stable true\\nplugins stable false')\n"
            f"    sys.exit(0)\n"
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



class ReviewRun(ReviewRunFixture):
    def test_pass_verdict_is_stored_as_receipt_with_exact_flags(self):
        r = self.review()
        self.assertEqual(r.returncode, 0, r.stderr)
        argv = json.loads(self.log.read_text())
        self.assertEqual(argv[argv.index("-m") + 1], "gpt-6-astra")
        self.assertIn('model_reasoning_effort="medium"', argv)
        for flag in ("--ignore-user-config", "--ignore-rules", "--ephemeral"):
            self.assertIn(flag, argv)
        disabled = [argv[i + 1] for i, a in enumerate(argv) if a == "--disable"]
        self.assertEqual(disabled, ["apps", "browser_use"])  # only enabled features that exist; never "browser"
        bundle = self.stdin_log.read_text()
        for needle in (self.base, self.h, "AC-1 feature works", "pytest"):  # AC text, not just its id
            self.assertIn(needle, bundle)
        key = json.loads(r.stdout)["receipt"]
        rec = receipts.load(key)
        self.assertEqual(rec["status"], "unconsumed")
        s = rec["verdict"]["subject"]
        self.assertEqual((s["base"], s["head"], s["destination"], s["op"]), (self.base, self.h, "refs/heads/main", "merge"))
        self.assertEqual(rec["verdict"]["reviewer"],
                         {"model": "gpt-6-astra", "effort": "medium", "provenance": "review-run"})
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

    def test_bundle_carries_evidence_binding_to_head(self):
        r = self.review()
        self.assertEqual(r.returncode, 0, r.stderr)
        sent = self.stdin_log.read_text()
        bundle = json.loads(sent[sent.index("\n{") + 1:])
        self.assertTrue(bundle["evidence_binding"], "evidence binding missing")
        for b in bundle["evidence_binding"]:
            self.assertIn("evidence_tree", b)
            self.assertIsInstance(b["relevant_differences"], list)
        self.assertTrue(bundle["ship_verified"], bundle.get("ship_verified_reasons"))
        # A verified head must have at least one evidence tree with no relevant difference.
        self.assertTrue(any(b["relevant_differences"] == [] for b in bundle["evidence_binding"]))

    def test_prompt_over_limit_is_blocked_before_codex(self):
        big = self.tmp / "big-evidence.txt"
        big.write_text("x" * 50_000)
        r = self.review("--evidence", str(big), "--max-bytes", "40000")
        self.assertEqual(r.returncode, 2)
        self.assertIn("characters", json.loads(r.stdout)["findings"][0]["body"])
        self.assertFalse(self.log.exists())

    def test_default_limit_is_below_codex_input_cap(self):
        rv = load_bin("maeng-review")
        import argparse, inspect
        self.assertIn("default=1_000_000", inspect.getsource(rv))

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


class ClaudeBackend(ReviewRunFixture):
    """D-9: the default reviewer is an isolated headless `claude -p` (different model from the authors)."""

    def fake_claude(self, verdict="pass", model="claude-fable-5-1", is_error=False, structured=True):
        log, stdin_log = self.tmp / "claude-argv.json", self.tmp / "claude-stdin.txt"
        fake = self.tmp / "fake-claude"
        fake.write_text(
            f"#!{sys.executable}\nimport json, sys\n"
            f"open({str(log)!r}, 'w').write(json.dumps(sys.argv[1:]))\n"
            f"open({str(stdin_log)!r}, 'w').write(sys.stdin.read())\n"
            f"models = {([model] if isinstance(model, str) else list(model))!r}\n"
            f"out = {{'is_error': {is_error!r}, 'modelUsage': {{m: {{}} for m in models}}}}\n"
            f"if {structured!r}:\n    out['structured_output'] = {{'verdict': {verdict!r}, 'findings': []}}\n"
            f"print(json.dumps(out))\n")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        return fake, log, stdin_log

    def run_claude_review(self, fake):
        return self.cli("maeng-review", ["run", "--kind", "code", "--pr", "7", "--base", self.base, "--head", self.h,
                                         "--base-ref", "main"], self.repo,
                        extra_env={"MAENG_REVIEW_BACKEND": "claude", "MAENG_CLAUDE": str(fake)})

    def test_claude_backend_is_isolated_and_records_the_real_model(self):
        fake, log, stdin_log = self.fake_claude()
        r = self.run_claude_review(fake)
        self.assertEqual(r.returncode, 0, r.stderr)
        argv = json.loads(log.read_text())
        self.assertEqual(argv[:1], ["-p"])
        for pair in (["--setting-sources", ""], ["--tools", ""]):
            i = argv.index(pair[0])
            self.assertEqual(argv[i:i + 2], pair)
        self.assertIn("--strict-mcp-config", argv)
        self.assertEqual(argv[argv.index("--model") + 1], "claude-fable-5-1")
        self.assertEqual(argv[argv.index("--effort") + 1], "medium")  # child-task tier
        self.assertIn("--json-schema", argv)
        self.assertIn("AC-1 feature works", stdin_log.read_text())
        receipt_files = list(receipts.receipts_dir().glob("*.json"))
        self.assertTrue(receipt_files)
        rec = json.loads(receipt_files[0].read_text())
        self.assertEqual(rec["verdict"]["reviewer"]["model"], "claude-fable-5-1")  # never labelled Astra

    def test_claude_reviewer_on_wrong_model_is_rejected(self):
        fake, _, _ = self.fake_claude(model="claude-haiku-4-5")
        r = self.run_claude_review(fake)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not the requested", r.stderr)

    def test_default_backend_is_claude_when_the_variable_is_unset(self):
        """D-9: with MAENG_REVIEW_BACKEND absent, maeng-review runs the Claude backend, not codex."""
        fake, log, _ = self.fake_claude()
        self.env.pop("MAENG_REVIEW_BACKEND")
        r = self.cli("maeng-review", ["run", "--kind", "code", "--pr", "7", "--base", self.base, "--head", self.h,
                                      "--base-ref", "main"], self.repo,
                     extra_env={"MAENG_CLAUDE": str(fake), "MAENG_CODEX": str(self.codex)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(log.exists())
        self.assertFalse(self.log.exists(), "codex must not run by default")
        rec = receipts.load(json.loads(r.stdout)["receipt"])
        self.assertEqual(rec["verdict"]["reviewer"]["model"], "claude-fable-5-1")
        self.assertEqual(rec["verdict"]["reviewer"]["provenance"], "review-run")

    def test_codex_backend_stays_selectable(self):
        fake, log, _ = self.fake_claude()
        r = self.cli("maeng-review", ["run", "--kind", "code", "--pr", "7", "--base", self.base, "--head", self.h,
                                      "--base-ref", "main"], self.repo,
                     extra_env={"MAENG_REVIEW_BACKEND": "codex", "MAENG_CLAUDE": str(fake),
                                "MAENG_CODEX": str(self.codex)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(self.log.exists())
        self.assertFalse(log.exists())

    def test_claude_reviewer_with_an_extra_model_in_usage_is_rejected(self):
        fake, _, _ = self.fake_claude(model=["claude-fable-5-1", "claude-haiku-4-5"])
        r = self.run_claude_review(fake)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not the requested", r.stderr)
        self.assertEqual(list(receipts.receipts_dir().glob("*.json")) if receipts.receipts_dir().exists() else [], [])

    def test_claude_reviewer_without_structured_output_is_rejected(self):
        fake, _, _ = self.fake_claude(structured=False)
        r = self.run_claude_review(fake)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no structured output", r.stderr)

    def test_claude_error_is_reported_not_stored(self):
        fake, _, _ = self.fake_claude(is_error=True)
        r = self.run_claude_review(fake)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(list(receipts.receipts_dir().glob("*.json")) if receipts.receipts_dir().exists() else [], [])


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
        self.calls = self.tmp / "claude-calls.jsonl"
        self.fake = self.tmp / "fake-claude"
        self.fake.write_text("#!/bin/sh\nprintf '{\"argv\": [' >> \"%s\"\nsep=; for a in \"$@\"; do printf '%%s\"%%s\"' \"$sep\" \"$a\" >> \"%s\"; sep=,; done\nprintf '], \"cwd\": \"%%s\"}\\n' \"$(pwd -P)\" >> \"%s\"\n" % (self.calls, self.calls, self.calls))
        self.fake.chmod(0o755)

    def isolate(self, *args, env=None):
        return self.cli("maeng-eta-isolate", list(args), self.tmp, extra_env={"MAENG_CLAUDE": str(self.fake), **(env or {})})

    def report(self, r):
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return {t["path"]: t for t in json.loads(r.stdout)["targets"]}

    def make_team_repo(self, parent, name, origin=None, ignore=True):
        repo = parent / name
        repo.mkdir(parents=True)
        self.git(repo, "init", "-q", "-b", "main")
        if ignore:
            (repo / ".gitignore").write_text(".claude/settings.local.json\n")
        if origin:
            self.git(repo, "remote", "add", "origin", origin)
        return repo

    def test_dry_run_is_default_and_writes_nothing(self):
        before = (self.eta_root / ".claude/settings.local.json").read_text()
        r = self.isolate()
        t = self.report(r)
        self.assertEqual(json.loads(r.stdout)["mode"], "dry-run")
        self.assertEqual(t[str(self.eta_root)]["settings"], "would write")
        self.assertEqual(t[str(self.eta_root)]["installs_needed"], ["eta-rules@eta", "eta-craft@eta"])
        self.assertEqual((self.eta_root / ".claude/settings.local.json").read_text(), before)
        self.assertFalse(self.calls.exists())
        self.assertEqual(json.loads(self.isolate("--dry-run").stdout)["mode"], "dry-run")

    def test_apply_merges_keys_installs_and_is_idempotent(self):
        sub = self.make_team_repo(self.eta_root / "dev", "contracts", "git@github.com:endix-foundation-v1/contracts.git")
        skipped = self.make_team_repo(self.eta_root / "_to_delete", "old")
        nm = self.make_team_repo(self.eta_root / "dev/web/node_modules", "pkg")
        t = self.report(self.isolate("--apply"))
        self.assertIn(str(sub), t)
        self.assertNotIn(str(skipped), t)
        self.assertNotIn(str(nm), t)
        data = json.loads((self.eta_root / ".claude/settings.local.json").read_text())
        self.assertEqual(data["permissions"], {"allow": ["Bash(ls)"]})          # existing keys preserved
        self.assertEqual(data["enabledPlugins"], {"maeng-harness@maeng": False, "linear@synced": False,
                                                  "commit-commands@claude-plugins-official": False,
                                                  "eta-rules@eta": True, "eta-craft@eta": True})
        for checkout in (self.eta_root, self.wt, sub):
            self.assertFalse(guard.isolation_missing(checkout), checkout)
        calls = [json.loads(l) for l in self.calls.read_text().splitlines()]
        self.assertIn({"argv": ["plugin", "install", "eta-rules@eta", "--scope", "local"], "cwd": str(sub)}, calls)
        self.assertIn({"argv": ["plugin", "install", "eta-craft@eta", "--scope", "local"], "cwd": str(self.eta_root)}, calls)
        self.assertEqual(len(calls), 2 * 3)
        n = len(calls)
        # idempotent for settings; installs repeat only where the registry has no entry (fake registers nothing)
        t = self.report(self.isolate("--apply"))
        self.assertEqual({v["settings"] for v in t.values()}, {"ok"})
        self.assertGreaterEqual(len(self.calls.read_text().splitlines()), n)

    def test_install_skipped_when_registered_for_path(self):
        reg = self.home / ".claude/plugins"
        reg.mkdir(parents=True)
        entries = lambda path: [{"scope": "local", "projectPath": path}]
        (reg / "installed_plugins.json").write_text(json.dumps({"version": 2, "plugins": {
            "eta-rules@eta": entries(str(self.eta_root)), "eta-craft@eta": [{"scope": "user"}]}}))
        t = self.report(self.isolate("--apply"))
        self.assertEqual(t[str(self.eta_root)]["installs_needed"], ["eta-craft@eta"])
        calls = [json.loads(l) for l in self.calls.read_text().splitlines()]
        self.assertFalse([c for c in calls if c["cwd"] == str(self.eta_root) and "eta-rules@eta" in c["argv"]])

    def test_non_git_eta_folder_is_a_target(self):
        import shutil
        shutil.rmtree(self.eta_root)
        self.eta_root.mkdir()
        t = self.report(self.isolate("--apply"))
        self.assertEqual(t[str(self.eta_root)]["kind"], "folder")
        self.assertEqual(t[str(self.eta_root)]["settings"], "written")
        data = json.loads((self.eta_root / ".claude/settings.local.json").read_text())
        self.assertIs(data["enabledPlugins"]["eta-rules@eta"], True)

    def test_scan_finds_team_checkouts_by_origin_org(self):
        elsewhere = self.tmp / "elsewhere"
        labs = self.make_team_repo(elsewhere / "a", "web", "https://github.com/endix-labs-v1/web.git")
        found = self.make_team_repo(elsewhere, "contracts", "git@github.com:endix-foundation-v1/contracts.git")
        other = self.make_team_repo(elsewhere, "mine", "https://github.com/maengseojun/agent-harness.git")
        deep = self.make_team_repo(elsewhere / "a/b/c/d/e", "toodeep", "https://github.com/endix-labs-v1/x.git")
        t = self.report(self.isolate("--apply", "--scan", str(elsewhere)))
        self.assertIn(str(labs), t)
        self.assertIn(str(found), t)
        self.assertNotIn(str(other), t)
        self.assertNotIn(str(deep), t)
        self.assertFalse(guard.isolation_missing(labs))
        t = self.report(self.isolate("--dry-run"))      # without --scan they are not discovered
        self.assertNotIn(str(labs), t)

    def test_refuses_tracked_or_unignored_settings_and_bad_json(self):
        (self.eta_root / ".gitignore").write_text("")
        self.git(self.eta_root, "add", "-A")
        self.git(self.eta_root, "commit", "-qm", "unignore")
        r = self.isolate("--apply")
        self.assertIn("not git-ignored", r.stdout)
        self.assertEqual(r.returncode, 1)
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
