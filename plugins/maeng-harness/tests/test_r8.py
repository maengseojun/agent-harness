"""Regression tests for the round-8 R1b findings (PR #38, MAE-216): production default of the fixture switch (1), closed
gh surface and gh aliases (2), closed git subcommand set (3), closed Notion/linear-endix tool sets and duplicate-page
(4), runner narrowing forms (6), GitHub MCP read set and cross-repository head (7), gh api REST writes (8), eta root
default and symlinks (9), Notion create-pages parent forms (10). Items 5 lives in test_r7 (lease pins)."""
import json
import os
import sys
import unittest.mock
import uuid

from maeng import evidence, gates, guard, receipts
from maeng.common import canonical, sha256
from .helpers import HarnessCase
from .test_g1 import ShipBase
from .test_g2_g3 import DB, PAGE
from .test_merge import MergeBase
from .test_r7 import R7_E_GithubMcpAllowlist, R7_L_NotionStructuralWrites

NOTION = "mcp__claude_ai_Notion__"


class R8_1_FixtureSwitchProductionDefault(MergeBase):
    """The variable is ABSENT in production: it must behave as off (`== "1"` only), never as on."""

    def absent(self):
        self.env.pop("MAENG_TEST_FIXTURES")
        os.environ.pop("MAENG_TEST_FIXTURES", None)

    def test_store_is_refused_when_the_variable_is_absent(self):
        self.absent()
        v = self.tmp / "v.json"
        v.write_text(json.dumps({"verdict": "pass", "reviewer": {"model": "m", "effort": "high"}, "findings": [],
                                 "subject": {"kind": "code", "repo": "r", "pr": 1, "base": "a", "head": "b",
                                             "criteria_rev": None, "digest": "d", "destination": "main",
                                             "op": "merge"}}))
        r = self.cli("maeng-review", ["store", str(v)], self.repo)
        self.assertEqual(r.returncode, 2)
        self.assertIn("MAENG_TEST_FIXTURES", r.stderr)
        self.assertFalse(receipts.receipts_dir().exists() and list(receipts.receipts_dir().glob("code-*.json")))

    def test_only_the_literal_one_enables_fixtures(self):
        for value in ("0", "", "true", "yes", "on"):
            with unittest.mock.patch.dict(os.environ, {"MAENG_TEST_FIXTURES": value}):
                self.assertFalse(receipts.fixtures_allowed(), value)
        with unittest.mock.patch.dict(os.environ, {"MAENG_TEST_FIXTURES": "1"}):
            self.assertTrue(receipts.fixtures_allowed())

class R8_4_NotionToolSetClosed(HarnessCase):
    PAGE_ID = PAGE.replace("-", "")
    OTHER = "cccccccc-1111-2222-3333-444455556666"

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.start(self.repo)
        self.cli("maeng-review", ["registry", "seed", PAGE], self.repo)

    sol_pass = R7_L_NotionStructuralWrites.sol_pass

    def call(self, name, tin, tuid="n1"):
        return self.pre(self.repo, NOTION + name, tin, tool_use_id=tuid)

    def test_duplicate_page_of_an_unrelated_page_is_free(self):
        self.assertFalse(self.call("notion-duplicate-page", {"page_id": self.OTHER})[0])


class R8_6_RunnerNarrowingForms(HarnessCase):
    def identity(self, cmd):
        rec = evidence.recognize(cmd)
        self.assertIsNotNone(rec, cmd)
        return rec["checks"][0][2]

    def test_cargo_selectors_are_filtered_never_default_mode(self):
        for cmd in ("cargo test my_test", "cargo test --lib", "cargo test --test integration", "cargo test --bin tool",
                    "cargo test --doc", "cargo test -p core", "cargo test --package core",
                    "cargo test --workspace -p core", "cargo test --workspace my_test", "cargo test --tests"):
            self.assertFalse(evidence.unfiltered(self.identity(cmd)), cmd)
        for cmd in ("cargo test", "cargo test --workspace", "cargo test --all --release"):
            self.assertTrue(evidence.unfiltered(self.identity(cmd)), cmd)
        for cmd in ("cargo test -- --skip slow", "cargo test x -- --exact", "cargo test --no-run",
                    "cargo test --lib -- --ignored", "cargo build foo"):
            self.assertIsNone(evidence.recognize(cmd), cmd)

    def test_package_manager_passthrough_is_not_evidence(self):
        for cmd in ("npm test -- --testPathPattern x", "pnpm test -- --grep x", "yarn test -- --list",
                    "npm run test -- x", "npm test -- --silent", "pnpm run test -- -t name", "yarn test --watch"):
            self.assertIsNone(evidence.recognize(cmd), cmd)
        self.assertTrue(evidence.unfiltered(self.identity("npm test")))

    def test_make_overrides_and_flags_are_not_evidence(self):
        for cmd in ("make test VAR=1", "make VAR=1 test", "make test CC=true", "make -C sub test", "make -f other.mk test",
                    "make -n test", "make -k test", "make -i test", "make -j4 test", "make -s test", "make --dry-run test",
                    "make test check", "make -C sub check", "make"):
            self.assertIsNone(evidence.recognize(cmd), cmd)
        for cmd in ("make test", "make check"):
            self.assertTrue(evidence.unfiltered(self.identity(cmd)), cmd)

    def test_other_runner_narrowing_forms_are_not_evidence(self):
        for cmd in ("playwright test --shard 1/2", "playwright test --grep x", "playwright test --only-changed",
                    "playwright test --last-failed", "pytest -c other.ini", "pytest -o addopts=-k", "pytest --rootdir x",
                    "pytest --override-ini addopts=x", "python3 -m unittest -k name", "python3 -m unittest -k"):
            self.assertIsNone(evidence.recognize(cmd), cmd)


class R8_9_EtaClassification(HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.eta_root.mkdir()
        (self.eta_root / "file.txt").write_text("eta")
        self.start(self.repo)

    def link(self):
        (self.repo / "etalink").symlink_to(self.eta_root, target_is_directory=True)
        (self.repo / "linkfile").symlink_to(self.eta_root / "file.txt")
        (self.repo / "newlink").symlink_to(self.eta_root / "new.txt")            # dangling: the target is created

    def test_symlinks_into_eta_are_classified_by_their_real_path(self):
        self.link()
        for name in ("etalink/file.txt", "linkfile", "newlink", "etalink/sub/new.txt", "etalink"):
            self.assertEqual(guard.classify(self.repo / name), guard.ETA, name)
        self.assertEqual(guard.classify(self.repo / "app.py"), guard.PERSONAL)

class R8_10_NotionCreatePagesParents(HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.start(self.repo)

    def test_other_parents_are_not_gated(self):
        pages = [{"properties": {"title": "x"}}]
        other = "cccccccccccccccccccccccccccccccc"
        for parent in ({"page_id": other}, {"type": "page_id", "page_id": other}, {"database_id": other},
                       {"type": "database_id", "database_id": other}, {"type": "workspace"}):
            self.assertFalse(self.pre(self.repo, NOTION + "notion-create-pages",
                                      {"parent": parent, "pages": pages})[0], parent)

class R8_DeclaredProseChecks(unittest.TestCase):
    """A Plan check with no runner in it is prose: shell punctuation in it must not split it into parts that no single
    declaration can satisfy; a runner constituent still needs runner evidence."""

    def test_prose_with_parentheses_and_separators_is_one_literal(self):
        for t in ("skill line counts (declared; evidence wc -l of every SKILL.md)", "a && b", "cd x && make lint"):
            self.assertEqual(evidence.parse_requirement(t), [(evidence.norm_identity(t).lower(), "", False)])

    def test_declaration_of_the_exact_text_satisfies_it(self):
        t = "vault policy readback (declared, evidence docs/design/vault-policy-readback.md)"
        good = [{"identity": evidence.norm_identity(t), "check": t, "source": "declared"}]
        self.assertTrue(evidence.requirement_met(good, t))
        self.assertFalse(evidence.requirement_met(good, t + " extra"))

    def test_runner_constituent_still_requires_runner_evidence(self):
        reqs = evidence.parse_requirement("python3 -m pytest -q && docs reviewed")
        self.assertIn(True, [r for _, _, r in reqs])
        self.assertEqual(len(reqs), 2)
