"""Regression tests for Astra round-4 findings (PR #38, MAE-220): G3 token taint (1), runner invocation allowlist for
evidence (2), remote URL rewrites (3), Notion id normalization/config validation (4), revocation race (5)."""
import json
import os
import unittest.mock

from maeng import evidence, gates, receipts
from .helpers import HarnessCase
from .test_g1 import ShipBase
from .test_g2_g3 import CREATE, DB
from .test_merge import MergeBase
from .test_r3 import ETA_URL, EtaDirMixin


class R4_1_TokenTaint(EtaDirMixin, HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.eta_root.mkdir()
        (self.eta_root / "file.txt").write_text("eta")
        self.start(self.repo)
        self.eta_dir = self.make_eta_dir(self.repo)

    def denied(self, cmd, cwd=None):
        d, reason = self.bash_pre(cwd or self.repo, cmd)
        self.assertTrue(d, f"expected deny: {cmd} ({reason})")
        return reason

    def allowed(self, cmd, cwd=None):
        d, reason = self.bash_pre(cwd or self.repo, cmd)
        self.assertFalse(d, f"expected allow: {cmd} ({reason})")

    def test_clone_and_worktree_destinations(self):
        e = self.eta_root
        self.denied(f"git clone https://github.com/o/r {e}/new")
        self.denied(f"git worktree add {e}/new")
        self.denied("git worktree add eta_checkout/wt")
        self.allowed("git clone https://github.com/o/r elsewhere")

    def test_gh_slug_destinations_and_set_default(self):
        self.denied("gh issue transfer 1 maengseojun/eta_v1 -R maengseojun/other")
        self.denied("cd eta_checkout && gh repo set-default maengseojun/eta_v1")
        self.denied("gh repo set-default maengseojun/eta_v1")
        self.allowed("gh repo set-default o/r")
        self.allowed("gh issue transfer 1 o/r2 -R o/other")

    def test_bare_operand_option_values_and_env_values(self):
        self.denied("cp app.py eta_checkout")
        self.denied("python3 build.py --out=eta_checkout/o")
        self.denied("dd if=app.py of=eta_checkout/x")
        self.denied("FOO=eta_checkout/x touch y")
        self.denied("make install DESTDIR=eta_checkout")
        self.denied("tar -xf a.tar -Ceta_checkout")
        self.denied("echo hi > eta_checkout/x")

    def test_read_only_allowlist(self):
        for cmd in ("cat eta_checkout/x", "ls eta_checkout", "head -n1 eta_checkout/x", "grep -r a eta_checkout",
                    "find eta_checkout -name x", "diff eta_checkout/a app.py", "wc -l eta_checkout/a",
                    "git -C eta_checkout log --oneline", "git -C eta_checkout status", "cd eta_checkout && git diff",
                    "cd eta_checkout && ls", "gh pr view 1 -R maengseojun/eta_v1", "gh issue list -R maengseojun/eta_v1",
                    "gh api repos/endix-foundation-v1/x/pulls", "gh repo view maengseojun/eta_v1",
                    "gh pr diff 1 -R endix-foundation-v1/x"):
            self.allowed(cmd)

    def test_read_only_programs_with_mutation_options_are_denied(self):
        for cmd in ("find eta_checkout -delete", "find eta_checkout -exec rm {} +", "find eta_checkout -fprint x",
                    "git -C eta_checkout commit -am x", "git -C eta_checkout branch -D x",
                    "gh api -X POST repos/endix-foundation-v1/x/issues -f title=t",
                    "gh api repos/endix-foundation-v1/x/issues -f title=t",
                    "gh api repos/endix-foundation-v1/x/issues --input body.json",
                    "sort -o eta_checkout/out app.py"):
            self.denied(cmd)

    def test_eta_effective_directory_is_read_only(self):
        self.denied("touch x", cwd=self.eta_dir)
        self.denied("git commit -am x", cwd=self.eta_dir)
        self.allowed("ls", cwd=self.eta_dir)
        self.allowed("git log", cwd=self.eta_dir)

    def test_personal_only_commands_are_unaffected(self):
        for cmd in ("touch notes.txt", "mkdir build", "cp app.py copy.py", 'git commit --allow-empty -m "fix a/b thing"',
                    "git add -A", "python3 -c 'print(1)'", "gh pr view 1", "gh issue comment 1 -R maengseojun/other -b hi",
                    "cat app.py | wc -l", "echo hi > out.txt", "git checkout -b topic"):
            self.allowed(cmd)


class R4_2_RunnerAllowlist(HarnessCase):
    def test_no_run_modes_are_not_evidence(self):
        for cmd in ("make -n test", "make --dry-run test", "make -q test", "make -t test", "make test -n",
                    "go test -list .", "go test -n ./...", "playwright test --list", "npx playwright test --list",
                    "pytest --collect-only", "pytest --co", "pytest --version", "cargo test --no-run",
                    "forge test --list", "ruff check --fix .", "ruff check --help", "mypy --version",
                    "tsc --version", "npm test -- --list", "npm run test --silent", "yarn test --help",
                    "python3 -m pytest --unknown-flag", "pytest -k", "pytest -p other", "pytest -p no:cacheprovider -x --bogus",
                    "unittest discover", "python3 -m unittest --bogus", "npx --help playwright test",
                    "PYTEST_ADDOPTS=--co pytest", "pytest $EXTRA", "claude plugin validate", "make test lint",
                    "go test -json -x ./...", "cargo test --features foo", "forge test --gas-report"):
            self.assertIsNone(evidence.recognize(cmd), cmd)

    def test_allowed_forms_are_evidence(self):
        for cmd in ("pytest tests -q -x -k 'not slow' -m unit --maxfail=2 -p no:cacheprovider --tb=short -n 4",
                    "python3 -m pytest -v tests/test_x.py::T::test_a", "python3 -m unittest discover -s tests -t . -p 'test*.py' -q",
                    "python3 -m unittest tests.test_a -v", "npm test", "pnpm run lint", "yarn build", "npm run typecheck",
                    "forge test -vvv --match-test testA --match-contract C --match-path test/A.t.sol --no-match-test X",
                    "forge build", "cargo test --workspace --all-features --release -q -p core", "cargo clippy --all",
                    "go test ./... -run TestA -count=1 -race -v -json", "make test", "make check", "ruff check src tests",
                    "mypy src", "tsc --noEmit -p tsconfig.json", "tsc", "claude plugin validate plugins/maeng-harness",
                    "playwright test e2e/a.spec.ts --project chromium", "npx playwright test", "npx -y playwright test",
                    "pnpm dlx playwright test", "npm exec playwright test", "uv run pytest -q"):
            self.assertIsNotNone(evidence.recognize(cmd), cmd)


class R4_3_RemoteRewrites(ShipBase):
    def fork(self):
        fork = self.tmp / "fork.git"
        self.git(self.tmp, "clone", "-q", "--bare", str(self.tmp / "repo-remote.git"), str(fork))
        return fork

    def test_push_insteadof_fork_redirect_denies_pr_create(self):
        self.alias_origin()
        self.verified()
        self.assertAllowed("gh pr create --repo o/r --head feat --title t --body b")
        self.git(self.repo, "config", f"url.{self.fork()}.pushInsteadOf", "https://github.com/o/r.git")
        self.assertDenied("gh pr create --repo o/r --head feat --title t --body b", "insteadOf")
        self.assertDenied("git push origin feat", "insteadOf")

    def test_fetch_insteadof_rewrite_is_denied(self):
        self.alias_origin()
        self.verified()
        self.git(self.repo, "config", f"url.{self.fork()}.insteadOf", "https://github.com/o/r.git")
        self.assertDenied("gh pr create --repo o/r --head feat --title t --body b", "insteadOf")


class R4_3_ReconcileRewrites(MergeBase):
    def test_reconcile_refuses_when_push_url_is_rewritten(self):
        key = self.verdict()
        r = self.ship(MAENG_GIT=self.fake_git("lost-git", self.LOST_RESPONSE))
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertEqual(self.status(key), "pending")
        fork = self.tmp / "fork.git"
        self.git(self.tmp, "clone", "-q", "--bare", str(self.remote), str(fork))
        self.git(self.repo, "config", f"url.{fork}.pushInsteadOf", str(self.remote))
        out = self.cli("maeng-review", ["reconcile", "--repo", str(self.repo)], self.repo)
        self.assertIn("pending", out.stdout)
        self.assertEqual(self.status(key), "pending")


class R4_4_NotionConfig(HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.start(self.repo)
        self.payload = {"parent": {"data_source_id": DB}, "pages": [{"properties": {"title": "x"}}]}

    def call(self, parent_id):
        return self.pre(self.repo, CREATE, {**self.payload, "parent": {"data_source_id": parent_id}})

    def use_config(self, value):
        self.env.pop("MAENG_NOTION_DBS", None)
        os.environ.pop("MAENG_NOTION_DBS", None)
        self.maeng_home.mkdir(parents=True, exist_ok=True)
        (self.maeng_home / "config.json").write_text(json.dumps({"notion_databases": value}))

    def test_uppercase_and_hyphenated_ids_are_gated(self):
        for pid in (DB, DB.upper(), "DB111111-1111-1111-1111-111111111111"):
            denied, reason = self.call(pid)
            self.assertTrue(denied, pid)
            self.assertIn("no Sol pass receipt", reason)

    def test_uppercase_configured_ids_are_normalized(self):
        self.use_config(["DB111111-1111-1111-1111-111111111111"])
        denied, reason = self.call(DB)
        self.assertTrue(denied)
        self.assertIn("no Sol pass receipt", reason)

    def test_string_instead_of_list_denies_writes(self):
        self.use_config(DB)
        denied, reason = self.call(DB)
        self.assertTrue(denied)
        self.assertIn("invalid Notion gate configuration", reason)
        denied, reason = self.call("cccccccccccccccccccccccccccccccc")
        self.assertTrue(denied)

    def test_bad_entries_and_empty_list_deny(self):
        for bad in ([], ["not-hex"], [DB, 5], ["abc"]):
            self.use_config(bad)
            denied, reason = self.call(DB)
            self.assertTrue(denied, bad)
            self.assertIn("invalid Notion gate configuration", reason)

    def test_invalid_env_denies(self):
        self.env["MAENG_NOTION_DBS"] = "zzz"
        denied, reason = self.call(DB)
        self.assertTrue(denied)
        self.assertIn("invalid Notion gate configuration", reason)

    def test_missing_shipped_default_denies(self):
        os.environ.pop("MAENG_NOTION_DBS", None)
        with unittest.mock.patch.object(gates, "read_json", return_value=None):
            d = gates.check_mcp_notion(CREATE, self.payload, gates.Ctx(self.repo, {}))
        self.assertFalse(d.allow)
        self.assertIn("invalid Notion gate configuration", d.reason)
        with unittest.mock.patch.object(gates, "read_json", side_effect=OSError("boom")):
            d = gates.check_mcp_notion(CREATE, self.payload, gates.Ctx(self.repo, {}))
        self.assertFalse(d.allow)

    def test_registry_and_journal_ids_are_normalized(self):
        receipts.registry_add(["AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"])
        self.assertIn("aaaaaaaabbbbccccddddeeeeeeeeeeee", receipts.registry_ids())
        scope = gates.notion_scope("mcp__claude_ai_Notion__notion-update-page",
                                   {"page_id": "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"})
        self.assertEqual(scope, ("update", "aaaaaaaabbbbccccddddeeeeeeeeeeee"))


class R4_5_RevocationRace(MergeBase):
    def revoke(self, key):
        receipts._mutate(key, lambda r: r.update(revoked={"at": "now", "by": "fail"}))

    def test_begin_refuses_a_receipt_revoked_after_lookup(self):
        key = self.verdict()
        rec = receipts.load(key)
        self.revoke(key)                      # a concurrent re-review revokes between lookup and reservation
        with self.assertRaises(receipts.ReceiptError):
            receipts.begin(rec["key"], {"remote": "origin"})
        self.assertEqual(self.status(key), "unconsumed")

    def test_begin_many_is_all_or_nothing_on_revocation(self):
        k1 = self.verdict()
        k2 = self.verdict(kind="code", files=["lib.py"], excluded=None)
        self.assertNotEqual(k1, k2)
        self.revoke(max(k1, k2))
        with self.assertRaises(receipts.ReceiptError):
            receipts.begin_many([(k1, {}), (k2, {})])
        self.assertEqual(self.status(k1), "unconsumed")
        self.assertEqual(self.status(k2), "unconsumed")

    def test_begin_refuses_non_pass_verdict(self):
        key = self.verdict()
        receipts._mutate(key, lambda r: r["verdict"].update(verdict="fail"))
        with self.assertRaises(receipts.ReceiptError):
            receipts.begin(key, {})
