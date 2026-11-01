# MAE-296 Spec/Plan: parent integration review is Fable first, Astra standby

Linear: MAE-296. Date: 2026-11-01. Single task (reviewer order for one tier, docs, version bump).

## Source and decisions

- D-1: parent integration is reviewed by Fable (`claude-fable-5-1`) at high first; when Fable fails (e.g. its usage is exhausted), Astra (`gpt-6-astra`) high is the standby (user, 2026-11-01: "오케이 그럼 저대로 수정하자. 그리고 fable 한도가 안 남았을 때를 대비해서 예비로 astra를 놔두는거야."; vault ADR-MAE-296-parent-review-fable). Reason: on PR #38 Fable's high findings were about the parent Spec as a whole (an unmet AC, stale evidence), Astra's about code-boundary defects that child reviews own. Signal it was wrong: parent reviews by Fable pass work whose integration defects surface later, or Fable fails often enough that Astra does most parent reviews.
- D-2: every other tier is unchanged: codex first, Opus after 3 failed codex attempts; `--author codex` still sends code reviews to Opus high (MAE-295).
- D-3: a claude reviewer failure no longer exits at once; it returns an error so parent can fall back. Every other path still stops on that error.

## Criteria

- **AC-1** `maeng-review run --kind parent` runs claude with `--model claude-fable-5-1 --effort high` first and does not run codex when Fable succeeds.
- **AC-2** When the Fable run fails, codex `gpt-6-astra` high reviews, and the receipt's `reviewer.fallback_from` names Fable (high, attempts 1).
- **AC-3** Other tiers are unchanged (codex first, Opus fallback).
- **AC-4** review-and-ship.md, harness-run SKILL.md, org-chart.md, orca-big-task SKILL.md and models.md state the new placement.
- **AC-5** The maeng-harness suite passes and never calls the real claude CLI; maeng-harness is 0.4.8.

## Steps

1. `tier_for("parent")` returns Fable at `MAENG_FABLE_EFFORT` (default now high); `run_claude` returns errors; parent falls back to `_codex_tier("parent")` (AC-1, AC-2, AC-3).
2. Tests in `tests/test_cli.py`; the test environment points `MAENG_CLAUDE` at a missing file (AC-1, AC-2, AC-5).
3. Docs and version bump (AC-4, AC-5).

## Verification

- AC-1..AC-3: `test_parent_integration_goes_to_fable_high_first`, `test_failing_fable_falls_back_to_astra_high`, `test_tier_selection` pass, and fail on the base code.
- AC-4: `grep -n "Fable" plugins/maeng-harness/skills/harness-run/references/review-and-ship.md plugins/maeng-harness/skills/orca-big-task/SKILL.md` shows the Fable-first rule.
- AC-5: `python3 -m pytest -q` at the repository root passes.
