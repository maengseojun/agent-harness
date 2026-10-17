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

    def test_read_only_allowlist(self):
        for cmd in ("cat eta_checkout/x", "ls eta_checkout", "head -n1 eta_checkout/x", "grep -r a eta_checkout",
                    "find eta_checkout -name x", "diff eta_checkout/a app.py", "wc -l eta_checkout/a",
                    "git -C eta_checkout log --oneline", "git -C eta_checkout status", "cd eta_checkout && git diff",
                    "cd eta_checkout && ls", "gh pr view 1 -R maengseojun/eta_v1", "gh issue list -R maengseojun/eta_v1",
                    "gh api repos/endix-foundation-v1/x/pulls", "gh repo view maengseojun/eta_v1",
                    "gh pr diff 1 -R endix-foundation-v1/x"):
            self.allowed(cmd)

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
