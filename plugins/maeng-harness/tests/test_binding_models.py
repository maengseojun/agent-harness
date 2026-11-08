"""S6 / AC-6: supplied execution identities survive bind/read/select, never criteria or coverage."""
import json

from maeng import evidence, receipts, state
from . import test_cli

SOL, ASTRA, OPUS, FABLE = "gpt-6.1-sol", "gpt-6-astra", "claude-opus-5-5", "claude-fable-5-1"


def test_make_binding_stores_models_without_changing_criteria(tmp_path):
    plan = tmp_path / "plan.md"
    plan.write_text("Requirements -> acceptance:\nAC-1 feature works\n\n## Plan\nChange app.py.\n")
    before = evidence.make_binding("MAE-1", str(plan))
    after = evidence.make_binding("MAE-1", str(plan), planner_model=OPUS, author_model=SOL)
    assert (after.pop("planner_model"), after.pop("author_model")) == (OPUS, SOL)
    assert (before.pop("planner_model"), before.pop("author_model")) == (None, None)
    assert after == before


class BindingModels(test_cli.ReviewRunFixture):
    fake_claude = test_cli.ClaudeBackend.fake_claude

    def bind_models(self, *extra, issue="MAE-221"):
        plan = self.load_state()["binding"]["plan_doc"]
        r = self.cli("maeng-verify", ["bind", issue, "--plan", plan, "--parent", "MAE-216", *extra], self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        return self.load_state()["binding"]

    def bound_review(self, kind="code", *extra, fake=None):
        args = ["run", "--kind", kind]
        if kind in ("code", "parent"):
            args += ["--pr", "7", "--base", self.base, "--head", self.h, "--base-ref", "main"]
        else:
            args += ["--draft", self.load_state()["binding"]["plan_doc"]]
        return self.cli("maeng-review", [*args, *extra], self.repo,
                        extra_env={"MAENG_CODEX": str(self.codex), "MAENG_CLAUDE": str(fake or self.tmp / "no-claude")})

    def reviewer(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return receipts.load(json.loads(result.stdout)["receipt"])["verdict"]["reviewer"]

    def test_flag_free_code_review_uses_bound_author_and_records_its_family(self):
        self.bind_models("--planner-model", ASTRA, "--author-model", SOL)
        fake, log, _ = self.fake_claude(model=OPUS)
        rev = self.reviewer(self.bound_review(fake=fake))
        self.assertEqual((rev["model"], rev["author"]), (OPUS, "codex"))
        self.assertEqual([(s["model"], s["match"]) for s in rev["skipped"]], [(SOL, "model")])
        self.assertTrue(log.exists())
        self.assertFalse(self.log.exists())

    def test_flag_free_parent_review_uses_both_bound_identities(self):
        self.bind_models("--planner-model", FABLE, "--author-model", SOL)
        rev = self.reviewer(self.bound_review("parent"))
        self.assertEqual((rev["model"], rev["effort"]), (ASTRA, "high"))
        self.assertIn("planner", rev["skipped"][0]["reason"])

    def test_flag_free_plan_review_excludes_the_bound_planner(self):
        self.bind_models("--planner-model", ASTRA, "--author-model", SOL)
        fake, _, _ = self.fake_claude(model=OPUS)
        rev = self.reviewer(self.bound_review("plan", fake=fake))
        self.assertEqual((rev["model"], rev["effort"]), (OPUS, "xhigh"))
        self.assertEqual([(s["model"], s["match"]) for s in rev["skipped"]], [(ASTRA, "model")])

    def test_explicit_author_model_overrides_family_and_binding(self):
        self.bind_models("--planner-model", OPUS, "--author-model", SOL)
        rev = self.reviewer(self.bound_review("code", "--author", "codex", "--author-model", OPUS))
        self.assertEqual((rev["model"], rev["author"]), (SOL, "claude"))
        self.assertEqual(self.load_state()["binding"]["author_model"], SOL)  # call-only override

    def test_legacy_author_family_overrides_the_bound_exact_author(self):
        self.bind_models("--author-model", OPUS)
        fake, _, _ = self.fake_claude(model=OPUS)
        rev = self.reviewer(self.bound_review("code", "--author", "codex", fake=fake))
        self.assertEqual((rev["model"], rev["skipped"][0]["match"]), (OPUS, "family"))

    def test_explicit_planner_and_legacy_family_override_the_binding(self):
        self.bind_models("--planner-model", FABLE, "--author-model", SOL)
        fake, _, _ = self.fake_claude(model=FABLE)
        self.assertEqual(self.reviewer(self.bound_review("parent", "--planner-model", ASTRA, fake=fake))["model"], FABLE)
        rev = self.reviewer(self.bound_review("parent", "--planner-model", "claude"))
        self.assertEqual((rev["model"], rev["skipped"][0]["match"]), (ASTRA, "family"))
        self.assertEqual(self.load_state()["binding"]["planner_model"], FABLE)

    def test_rebind_and_handoff_replace_identities_without_granting_coverage(self):
        before = self.load_state()["binding"]
        first = self.bind_models("--planner-model", OPUS, "--author-model", SOL)
        second = self.bind_models("--planner-model", ASTRA, "--author-model", FABLE)
        self.assertEqual((first["criteria_rev"], second["criteria_rev"]), (before["criteria_rev"], before["criteria_rev"]))
        self.assertEqual(self.load_state()["plan_records"][-1]["plan_updated_at"], second["plan_updated_at"])
        self.assertFalse(receipts.receipts_dir().exists())
        self.assertIsNone(receipts.find_plan("MAE-221", second["criteria_rev"]))
        rev = self.reviewer(self.bound_review())
        self.assertEqual(rev["model"], SOL)  # the handoff's author replaced Sol
        stored = next(receipts.receipts_dir().glob("code-*.json"))
        subject = json.loads(stored.read_text())["verdict"]["subject"]
        self.assertEqual(subject["criteria_rev"], before["criteria_rev"])
        self.assertEqual(subject["files_reviewed"], ["app.py"])
        self.assertEqual(subject["coverage"], [{"file": "app.py", "mode": "full"}])
        for extra in ((), ("--planner-model", OPUS), ("--author-model", SOL)):
            with self.subTest(extra=extra):
                rebound = self.bind_models(*extra, issue="MAE-222")
                self.assertEqual(rebound["planner_model"], OPUS if "--planner-model" in extra else None)
                self.assertEqual(rebound["author_model"], SOL if "--author-model" in extra else None)

    def test_an_explicit_other_task_does_not_inherit_the_current_binding(self):
        self.bind_models("--planner-model", OPUS, "--author-model", SOL)
        self.reviewer(self.bound_review("plan"))
        self.log.unlink()
        r = self.bound_review("plan", "--issue", "MAE-999")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("--author-model", r.stderr)
        self.assertFalse(self.log.exists())


    def test_invalid_bound_author_blocks_every_kind_before_bundle_or_provider(self):
        self.bind_models("--planner-model", OPUS, "--author-model", SOL)
        for kind in ("code", "parent", "plan", "docs", "research", "notion"):
            for bad in (None, "", "   ", "unknown", "unavailable", 7):
                with self.subTest(kind=kind, bad=bad):
                    state.update(self.sid, lambda st: st["binding"].update(author_model=bad), self.repo)
                    r = self.bound_review(kind)
                    self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                    self.assertIn("--author-model", r.stderr)
                    self.assertFalse(self.log.exists())

    def test_invalid_planner_blocks_plan_and_parent_but_is_unused_for_code(self):
        self.bind_models("--planner-model", OPUS, "--author-model", FABLE)
        self.reviewer(self.bound_review())
        self.log.unlink()
        for kind in ("plan", "parent"):
            for bad in (None, "", "   ", "unknown", "unavailable", 7):
                with self.subTest(kind=kind, bad=bad):
                    state.update(self.sid, lambda st: st["binding"].update(planner_model=bad), self.repo)
                    r = self.bound_review(kind)
                    self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                    self.assertIn("--planner-model", r.stderr)
                    self.assertFalse(self.log.exists())
        self.reviewer(self.bound_review())

    def test_invalid_explicit_models_do_not_fall_back_to_valid_bound_values(self):
        self.bind_models("--planner-model", OPUS, "--author-model", SOL)
        for flag in ("--author-model", "--planner-model"):
            for bad in ("", "   ", "unknown", "unavailable"):
                with self.subTest(flag=flag, bad=bad):
                    r = self.bound_review("parent", flag, bad)
                    self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                    self.assertIn(flag, r.stderr)
                    self.assertFalse(self.log.exists())
