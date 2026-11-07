"""MAE-326 S3 / AC-3: `maeng-review run --kind plan` and its criteria-bound receipt."""
import hashlib
import json

from maeng import receipts
from .test_cli import ReviewRunFixture


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


SECTION = "AC-1 feature works"
PLAN = f"# Plan\n\nRequirements -> acceptance:\n{SECTION}\n\n## Plan\n\nStep 1: change `app.py`.\n"


class PlanReview(ReviewRunFixture):
    def commit_plan(self, text):
        (self.repo / "docs").mkdir(exist_ok=True)
        (self.repo / "docs/plan.md").write_text(text)
        return self.commit_all(self.repo, "plan")

    def plan_review(self, head, *extra):
        return self.cli("maeng-review", ["run", "--kind", "plan", "--plan", "docs/plan.md", "--head", head, "--issue",
                                         "MAE-9", "--planner-model", "claude-opus-5-5", *extra],
                        self.repo, extra_env={"MAENG_CODEX": str(self.codex)})

    def stored(self):
        d = receipts.receipts_dir()
        return list(d.glob("plan-*.json")) if d.exists() else []

    def test_pass_is_a_plan_receipt_keyed_by_task_and_digest(self):
        r = self.plan_review(self.commit_plan(PLAN))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        argv = json.loads(self.log.read_text())
        self.assertEqual((argv[argv.index("-m") + 1], 'model_reasoning_effort="high"' in argv), ("gpt-6-astra", True))
        sent = self.stdin_log.read_text()
        self.assertIn("Scope check first", sent)
        self.assertIn("Step 1: change", sent)
        self.assertIn("print('feature')", sent)  # app.py is cited, so its content is in the bundle
        rec = receipts.find_plan("MAE-9", sha(SECTION))
        self.assertEqual(rec["verdict"]["subject"]["kind"], "plan")
        self.assertEqual(receipts.plan_receipt_status("MAE-9", sha(SECTION)), "valid")
        self.assertIsNone(receipts.find_plan("MAE-8", sha(SECTION)))  # another task
        self.assertIsNone(receipts.find_plan("MAE-9", None))

    def test_receipt_does_not_follow_the_tree(self):
        self.plan_review(self.commit_plan(PLAN))
        (self.repo / "app.py").write_text("print('moved')\n")
        later = self.commit_all(self.repo, "code moved")
        self.assertEqual(self.plan_review(later).returncode, 0)
        self.assertEqual(len(self.stored()), 1)  # same task and digest: the same receipt
        self.assertEqual(receipts.plan_receipt_status("MAE-9", sha(SECTION)), "valid")

    def test_changed_wording_makes_the_receipt_stale(self):
        self.plan_review(self.commit_plan(PLAN))
        new = SECTION + " quickly"
        self.commit_plan(PLAN.replace(SECTION, new))
        self.assertEqual(receipts.plan_receipt_status("MAE-9", sha(new)), "stale")
        self.assertIsNone(receipts.find_plan("MAE-9", sha(new)))
        self.assertEqual(receipts.plan_receipt_status("MAE-7", sha(new)), "missing")
        self.assertEqual(receipts.plan_receipt_status("MAE-9", None), "stale")  # null equals nothing

    def test_a_plan_without_usable_criteria_is_refused_before_any_model(self):
        for text in ("", "   \n", "# Plan\n\nno criteria here\n", "Requirements -> acceptance:\n\nnone yet\n\n## Plan\n"):
            with self.subTest(text=text):
                r = self.plan_review(self.commit_plan(text))
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                out = json.loads(r.stdout)
                self.assertEqual(out["verdict"], "blocked")
                self.assertFalse(self.log.exists())
                self.assertEqual(self.stored(), [])

    def test_the_planner_model_is_required_and_excluded(self):
        head = self.commit_plan(PLAN)
        r = self.cli("maeng-review", ["run", "--kind", "plan", "--plan", "docs/plan.md", "--head", head, "--issue",
                                      "MAE-9"], self.repo, extra_env={"MAENG_CODEX": str(self.codex)})
        self.assertEqual(r.returncode, 2)
        self.assertIn("planner", r.stderr)
        r = self.plan_review(head, "--planner-model", "gpt-6-astra")  # the planner's own model never reviews
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(self.log.exists())
        self.assertEqual(self.stored(), [])

    def test_a_code_receipt_does_not_satisfy_plan_review(self):
        self.assertEqual(self.review().returncode, 0)
        self.assertTrue(list(receipts.receipts_dir().glob("code-*.json")))
        self.assertIsNone(receipts.find_plan("MAE-221", sha(SECTION)))
        self.assertEqual(receipts.plan_receipt_status("MAE-221", sha(SECTION)), "missing")

    def test_a_draft_file_is_reviewed_too(self):
        draft = self.tmp / "draft.md"
        draft.write_text(PLAN)
        r = self.cli("maeng-review", ["run", "--kind", "plan", "--draft", str(draft), "--issue", "MAE-9",
                                      "--planner-model", "claude-opus-5-5"], self.repo,
                     extra_env={"MAENG_CODEX": str(self.codex)})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(receipts.plan_receipt_status("MAE-9", sha(SECTION)), "valid")

    def test_only_critical_or_high_fails_a_plan(self):
        head = self.commit_plan(PLAN)
        med = {"severity": "medium", "title": "wording", "body": "b", "file": None, "line": None}
        self.result.write_text(json.dumps({"verdict": "fail", "findings": [med]}))
        self.assertEqual(self.plan_review(head).returncode, 0)
        for p in self.stored():
            p.unlink()
        self.result.write_text(json.dumps({"verdict": "fail", "findings": [{**med, "severity": "high",
                                                                            "title": "AC-1 has no check"}]}))
        r = self.plan_review(head)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(self.stored(), [])
        self.assertEqual(receipts.plan_receipt_status("MAE-9", sha(SECTION)), "missing")
