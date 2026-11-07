"""MAE-326 S4 / AC-3 (notice half), AC-6: large-task plan-receipt notices after `gh pr create` and at code-review
entry, and the PR notice that fires once per repository/PR. Notices never block anything."""
import hashlib
import json

from maeng import receipts
from .helpers import HarnessCase
from .test_cli import ReviewRunFixture

AC = "AC-1 feature works"
URL = "https://github.com/o/r/pull/%d"


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def plan_text(rows=2, grade=True, ac=AC):
    head = "| # | Do | Grade |\n|---|---|---|" if grade else "| # | Do |\n|---|---|"
    body = "".join(f"| S{i + 1} | step |" + (" quick |" if grade else "") + "\n" for i in range(rows))
    return f"# Plan\n\nRequirements -> acceptance:\n{ac}\n\nSub-tasks:\n{head}\n{body}\n## Verification\nAC-1: pytest\n"


def pass_receipt(issue, digest):
    receipts.store_verdict({
        "verdict": "pass", "findings": [],
        "subject": {"kind": "plan", "repo": None, "pr": None, "base": None, "head": None, "criteria_rev": digest,
                    "digest": None, "destination": None, "op": "review", "issue": issue, "files_reviewed": []},
        "reviewer": {"model": "m", "effort": "high", "provenance": "review-run"}})


class NoticeBase(HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.start(self.repo)

    def bind(self, issue="MAE-50", *extra, **plan):
        path = self.tmp / "plan.md"
        path.write_text(plan_text(**plan))
        self.cli("maeng-verify", ["bind", issue, "--plan", str(path), *extra], self.repo, check=True)
        return self.load_state()["binding"]


class LargeTaskBoundaries(NoticeBase):
    def test_one_row_is_small_two_rows_are_large(self):
        self.assertEqual(receipts.plan_notices(self.bind(rows=1)), [])
        lines = receipts.plan_notices(self.bind(rows=2))
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], "maeng: large task MAE-50 has no valid plan review receipt (missing); "
                                   "`maeng-review run --kind plan` records one. Notice only: review and merge are not blocked.")

    def test_children_make_a_one_row_plan_large_whether_in_the_binding_or_the_registry(self):
        binding = self.bind(rows=1)
        self.assertEqual(receipts.plan_notices(binding), [])  # no children yet
        self.assertEqual(len(receipts.plan_notices({**binding, "children": ["MAE-51"]})), 1)
        self.bind("MAE-51", "--parent", "MAE-50", rows=1)  # the registry now knows a child of MAE-50
        lines = receipts.plan_notices(self.bind(rows=1))
        self.assertEqual(len(lines), 1)
        self.assertIn("MAE-50", lines[0])

    def test_receipt_valid_stale_and_missing(self):
        binding = self.bind(rows=2)
        self.assertIn("(missing)", receipts.plan_notices(binding)[0])
        pass_receipt("MAE-50", sha(AC))
        self.assertEqual(binding["plan_updated_at"], sha(AC))
        self.assertEqual(receipts.plan_notices(binding), [])  # valid
        changed = self.bind(rows=2, ac=AC + " quickly")  # the criteria changed after the plan review
        self.assertIn("(stale)", receipts.plan_notices(changed)[0])
        self.assertEqual(receipts.plan_notices(self.bind("MAE-52", rows=2))[0].count("(missing)"), 1)  # another task

    def test_a_timestamp_binding_still_matches_the_plan_receipt_by_digest(self):
        # Review finding on PR #103: --plan-updated keeps the Linear timestamp, so the notice compares the digest.
        binding = self.bind("MAE-50", "--plan-updated", "2026-11-07T10:00:00+0900", rows=2)
        self.assertEqual(binding["plan_updated_at"], "2026-11-07T10:00:00+0900")
        self.assertEqual(binding["criteria_rev"], sha(AC))
        self.assertIn("(missing)", receipts.plan_notices(binding)[0])
        pass_receipt("MAE-50", sha(AC))
        self.assertEqual(receipts.plan_notices(binding), [])

    def test_a_table_without_a_grade_column_is_read_as_standard_with_one_line(self):
        self.assertEqual(receipts.plan_notices(self.bind(rows=1, grade=False)),
                         ["maeng: the Plan's Sub-tasks table has no Grade column; read as standard."])
        lines = receipts.plan_notices(self.bind(rows=2, grade=False))
        self.assertEqual(len(lines), 2)
        self.assertIn("large task", lines[0])
        self.assertIn("no Grade column", lines[1])

    def test_no_binding_or_no_plan_gives_no_notice(self):
        self.assertEqual(receipts.plan_notices(None), [])
        self.assertEqual(receipts.plan_notices({"issue": "MAE-50", "plan_doc": str(self.tmp / "gone.md")}), [])


class PrNotice(NoticeBase):
    def create(self, n=1, failed=False, **resp):
        tin = {"command": "gh pr create --fill"}
        if failed:
            return self.hook("PostToolUseFailure", self.repo, tool_name="Bash", tool_input=tin, tool_use_id="c",
                             error="Command failed with exit code 1")[1]
        return self.hook("PostToolUse", self.repo, tool_name="Bash", tool_input=tin, tool_use_id="c",
                         tool_response=resp or {"stdout": URL % n})[1]

    def context(self, out):
        return out["hookSpecificOutput"]["additionalContext"]

    def test_notice_names_open_work_and_plan_receipt_state(self):
        self.bind(rows=2)
        (self.repo / "app.py").write_text("print('changed')\n")
        self.hook("PostToolUse", self.repo, tool_name="Edit", tool_input={"file_path": str(self.repo / "app.py")},
                  tool_response={})
        text = self.context(self.create())
        self.assertIn("PR created. Next: run `maeng-review`", text)
        self.assertIn("UNVERIFIED: code changed", text)
        self.assertIn("UNRECORDED:", text)
        self.assertIn("large task MAE-50 has no valid plan review receipt (missing)", text)

    def test_notice_fires_once_per_pr_and_again_for_another_pr(self):
        self.bind(rows=1)
        self.assertIn("PR created", self.context(self.create(1)))
        self.assertIn("o/r#1", self.load_state()["pr_notices"])
        self.assertIsNone(self.create(1))  # the same PR again
        self.assertEqual(self.load_state()["pr_notices"], ["o/r#1"])
        self.assertIn("PR created", self.context(self.create(2)))

    def test_failed_create_gives_no_notice_and_does_not_use_up_the_once(self):
        self.bind(rows=1)
        self.assertIsNone(self.create(failed=True))
        self.assertIsNone(self.create(stdout="", exit_code=1))
        self.assertNotIn("pr_notices", self.load_state())
        self.assertIn("PR created", self.context(self.create(1)))


class ReviewEntryNotice(ReviewRunFixture):
    def rebind(self, **plan):
        path = self.tmp / "plan2.md"
        path.write_text(plan_text(**plan))
        self.cli("maeng-verify", ["bind", "MAE-221", "--plan", str(path), "--parent", "MAE-216"], self.repo, check=True)

    def test_large_task_prints_one_line_and_the_review_still_runs(self):
        self.rebind(rows=2)
        r = self.review()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual([l for l in r.stderr.splitlines() if "plan review receipt" in l],
                         ["maeng: large task MAE-221 has no valid plan review receipt (missing); "
                          "`maeng-review run --kind plan` records one. Notice only: review and merge are not blocked."])
        self.assertTrue(self.log.exists())  # the reviewer was dispatched
        self.assertEqual(json.loads(r.stdout)["verdict"], "pass")

    def test_small_task_valid_receipt_and_other_kinds_print_nothing(self):
        self.rebind(rows=1)
        self.assertNotIn("plan review receipt", self.review().stderr)
        self.rebind(rows=2)
        pass_receipt("MAE-221", sha("AC-1 feature works"))
        self.assertNotIn("plan review receipt", self.review().stderr)

    def test_parent_kind_prints_it_too(self):
        self.rebind(rows=2)
        r = self.cli("maeng-review", ["run", "--author-model", "unlisted-author", "--kind", "parent", "--planner-model", "claude-opus-5-5", "--pr", "7"],
                     self.repo, extra_env={"MAENG_CODEX": str(self.codex)})
        self.assertIn("large task MAE-221 has no valid plan review receipt", r.stderr)
