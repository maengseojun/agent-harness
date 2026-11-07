"""MAE-326 S1: one criteria digest (SHA-256 of the acceptance section) for bind, review, ship and the lease gate.
Expected digests are hashlib over the literal section text written here, never the production helper's output."""
import hashlib
import importlib.machinery
import importlib.util
import json

from maeng import evidence, receipts, schema
from maeng.common import home_dir
from .helpers import BIN, HarnessCase
from .test_merge import MergeBase


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


SECTION = "- **AC-1** The widget renders.\n  It also resizes.\n- **AC-2** It is fast."
PLAN = ("# Plan: widget\n\nGoal: x\n\nRequirements -> acceptance:\n\n" + SECTION + "\n\n## Plan\n\nSteps: 1.\n\n"
        "## Verification\n\n- AC-1: `pytest -q`\n- AC-2: `pytest -q`\n\nRevisions:\n\n- R-1 plan order\n\n"
        "Close-out: open\n\n## Progress\n\n- started\n")
DIGEST = sha(SECTION)

ONE = "- **AC-1** x works."
ONE_PLAN = "Requirements -> acceptance:\n\n" + ONE + "\n\n## Verification\nAC-1: pytest\n"
ONE_DIGEST = sha(ONE)


class Helper(HarnessCase):
    def test_digest_is_the_hash_of_the_literal_section(self):
        self.assertEqual(evidence.criteria_rev(PLAN), DIGEST)

    def test_headed_form_and_crlf(self):
        text = "# Spec\n\n## Acceptance criteria\n\n" + SECTION + "\n\n## Plan\nAC-9 elsewhere\n"
        self.assertEqual(evidence.criteria_rev(text), DIGEST)
        self.assertEqual(evidence.criteria_rev(PLAN.replace("\n", "\r\n")), DIGEST)

    def test_b_wording_change_with_the_same_number_changes_the_digest(self):
        new = "- **AC-1** The widget renders slowly.\n  It also resizes.\n- **AC-2** It is fast."
        got = evidence.criteria_rev(PLAN.replace(SECTION, new))
        self.assertEqual(got, sha(new))
        self.assertNotEqual(got, DIGEST)

    def test_c_progress_revisions_and_close_out_do_not_change_the_digest(self):
        edited = (PLAN.replace("- started", "- started\n- AC-1 done, AC-2 done").replace("- R-1 plan order", "- R-1 plan order\n- R-2 AC-1 reworded")
                  .replace("Close-out: open", "Close-out: closed, AC-1 met"))
        self.assertEqual(evidence.criteria_rev(edited), DIGEST)

    def test_d_fenced_example_is_not_a_criterion(self):
        fenced = "```\nRequirements -> acceptance:\n  AC-9: fake\n```\n\n"
        self.assertEqual(evidence.criteria_rev(fenced + PLAN), DIGEST)
        self.assertIsNone(evidence.criteria_rev(fenced + "## Verification\nAC-9: x\n"))
        inner = "- **AC-1** shows:\n```\n## Not a heading\nAC-7: example\n```\n- **AC-2** ok."
        self.assertEqual(evidence.criteria_rev("Requirements -> acceptance:\n" + inner + "\n\n## Plan\n"), sha(inner))

    def test_e_no_usable_section_is_none_not_the_empty_digest(self):
        for text in ("", "# Plan\n\n## Verification\n- AC-1: pytest\n", "Requirements -> acceptance:\n\nnone yet\n\n## Plan\n",
                     "Requirements -> acceptance:\n- AC-1 a\n\n## Plan\n\n## Acceptance\n- AC-1 b\n"):
            self.assertIsNone(evidence.criteria_rev(text), text)
        self.assertNotEqual(evidence.criteria_rev(PLAN), sha(""))


class BindAndReview(HarnessCase):
    def test_a_bind_and_a_committed_review_give_the_same_nonnull_digest(self):
        repo = self.make_repo()
        (repo / "plan.md").write_text(PLAN)
        head = self.commit_all(repo, "plan")
        self.start(repo)
        self.assertEqual(self.cli("maeng-verify", ["bind", "MAE-1", "--plan", str(repo / "plan.md")], repo).returncode, 0)
        bound = json.loads((home_dir() / "bindings.json").read_text())["MAE-1"]["plan_updated_at"]
        mod = importlib.util.module_from_spec(spec := importlib.util.spec_from_loader(
            "maeng_review_mod", importlib.machinery.SourceFileLoader("maeng_review_mod", str(BIN / "maeng-review"))))
        spec.loader.exec_module(mod)
        reviewed = mod.committed_plan(repo, head, "plan.md")["plan_updated_at"]
        self.assertEqual((bound, reviewed), (DIGEST, DIGEST))


class Gates(MergeBase):
    """Ship and the lease-push gate compare the receipt's criteria revision with the binding's."""

    def bind_plan(self, text):
        plan = self.tmp / "plan.md"
        plan.write_text(text)
        self.assertEqual(self.cli("maeng-verify", ["bind", "MAE-9", "--plan", str(plan)], self.repo).returncode, 0)
        self.cli("maeng-verify", ["plan", "--met", "AC-1"], self.repo)

    def lease(self):
        return f"git push --force-with-lease=refs/heads/main:{self.base} origin {self.h}:refs/heads/main"

    def test_matching_digest_ships(self):
        self.bind_plan(ONE_PLAN)
        self.verdict(criteria_rev=ONE_DIGEST)
        r = self.ship()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_timestamp_override_keeps_the_digest_for_ship_and_the_lease_gate(self):
        # Plan-review finding on PR 2a: `--plan-updated` keeps the source timestamp, but authorization uses the digest.
        plan = self.tmp / "plan.md"
        plan.write_text(ONE_PLAN)
        r = self.cli("maeng-verify", ["bind", "MAE-9", "--plan", str(plan), "--plan-updated", "2026-11-07T10:00:00+0900"], self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        binding = self.load_state()["binding"]
        self.assertEqual((binding["plan_updated_at"], binding["criteria_rev"]), ("2026-11-07T10:00:00+0900", ONE_DIGEST))
        self.cli("maeng-verify", ["plan", "--met", "AC-1"], self.repo)
        self.verdict(criteria_rev=ONE_DIGEST)  # what a review of the committed text records
        r = self.ship()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_ship_rejects_a_receipt_from_other_criteria(self):
        self.bind_plan(ONE_PLAN)
        self.verdict(criteria_rev=sha("- **AC-1** x works differently."))
        r = self.ship()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("stale", r.stderr)
        self.assertEqual(self.remote_main(), self.base)

    def test_lease_gate_rejects_a_receipt_from_other_criteria_and_accepts_the_match(self):
        self.bind_plan(ONE_PLAN)
        self.verdict(criteria_rev=sha("- **AC-1** x works differently."))
        denied, reason = self.bash_pre(self.repo, self.lease())
        self.assertTrue(denied)
        self.assertIn("stale", reason)
        self.verdict(criteria_rev=ONE_DIGEST)
        denied, reason = self.bash_pre(self.repo, self.lease())
        self.assertFalse(denied, reason)

    def test_null_receipt_and_null_binding_do_not_match(self):
        self.bind_plan("Requirements -> acceptance:\n\nnone\n\n## Verification\nAC-1: pytest\n")  # no AC -> no digest
        self.assertIsNone(json.loads((home_dir() / "bindings.json").read_text())["MAE-9"]["plan_updated_at"])
        self.verdict(criteria_rev=None)
        r = self.ship()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("stale", r.stderr)
        denied, reason = self.bash_pre(self.repo, self.lease())
        self.assertTrue(denied)
        self.assertIn("stale", reason)
        self.assertEqual(self.remote_main(), self.base)

    def test_null_receipt_does_not_match_a_real_binding(self):
        self.bind_plan(ONE_PLAN)
        self.verdict(criteria_rev=None)
        self.assertIn("stale", self.ship().stderr)


class ReceiptFields(HarnessCase):
    def verdict(self, **subject):
        s = {"kind": "code", "repo": "o/r", "pr": 1, "base": "a", "head": "b", "criteria_rev": DIGEST, "digest": "d",
             "destination": "refs/heads/main", "op": "merge", "files_reviewed": ["x.py"]}
        s.update(subject)
        return {"verdict": "pass", "subject": s, "reviewer": {"model": "m", "effort": "high", "provenance": "review-run"},
                "findings": []}

    def test_coverage_fields_validate_and_a_legacy_receipt_still_loads(self):
        full = self.verdict(coverage=[{"file": "x.py", "mode": "delta"}], previous_head="p", review_mode="round2")
        self.assertEqual(schema.validate(full, schema.load_schema()), [])
        self.assertEqual(schema.validate(self.verdict(), schema.load_schema()), [])
        self.assertTrue(schema.validate(self.verdict(coverage=[{"file": "x.py", "mode": "some"}]), schema.load_schema()))
        self.assertNotEqual(receipts.subject_key(full["subject"]), receipts.subject_key(self.verdict()["subject"]))

    def test_plan_receipt_is_keyed_by_task_and_digest_and_null_never_matches(self):
        v = self.verdict(kind="plan", issue="MAE-9", repo=None, pr=None, base=None, head=None, digest=None,
                         destination=None, op="review", files_reviewed=[])
        receipts.store_verdict(v)
        self.assertIsNotNone(receipts.find_plan("MAE-9", DIGEST))
        self.assertIsNone(receipts.find_plan("MAE-9", sha("changed")))
        self.assertIsNone(receipts.find_plan("MAE-8", DIGEST))
        self.assertIsNone(receipts.find_plan("MAE-9", None))
        self.assertIsNone(receipts.find_plan(None, None))
