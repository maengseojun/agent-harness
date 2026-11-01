# MAE-295 Spec/Plan: no same-model code review (`--author codex`)

Linear: MAE-295. Date: 2026-11-01. Single task (one CLI flag, schema field, docs, version bump).

## Source and decisions

- MAE-294 research: child-task PRs are reviewed by Sol xhigh (`review-and-ship.md`) while Sol can implement them (`org-chart.md`), so a model could review its own code. LLM judges favor their own outputs (arXiv 2404.13076).
- D-1: when Sol or another Codex model wrote the change, the code review goes to Opus high and codex is not tried (user, 2026-11-01: "그럼 sol이 맡은 구현은 opus high가 검토하면 되지"; vault ADR-MAE-294-sol-author-opus-review). Signal it was wrong: Opus high misses defects on Sol-written PRs that later surface, more often than Sol reviews of Claude-written PRs.
- D-2: the caller states the author with `--author claude|codex`; `maeng-review` does not guess it. Without the flag the behavior is unchanged. Signal: Sol-written PRs reviewed without the flag.
- Out of scope: the parent tier (Astra) when all children are Sol-written.

## Criteria

- **AC-1** `maeng-review run --kind code --author codex` never runs codex and runs claude with `--model claude-opus-5-5 --effort high`.
- **AC-2** The receipt's `reviewer` records `author: codex` and passes the verdict schema.
- **AC-3** Without the flag, or with `--author claude`, codex still comes first.
- **AC-4** `review-and-ship.md` states the rule, the command and the tier row; harness-run `SKILL.md` step 10 mentions it.
- **AC-5** The maeng-harness test suite passes; maeng-harness is 0.4.7.

## Steps

1. Add `--author` to `maeng-review run`; route `--kind code --author codex` to Opus high; record `reviewer.author`; allow it in `verdict.schema.json` (AC-1, AC-2, AC-3).
2. Tests in `tests/test_cli.py` `ClaudeBackend` (AC-1, AC-2, AC-3).
3. Docs and version bump (AC-4, AC-5).

## Verification

- AC-1..AC-3: `test_codex_written_code_goes_to_opus_high_without_codex` and `test_claude_written_code_keeps_codex_first` pass, and fail on the base code.
- AC-4: `grep -n "author codex" plugins/maeng-harness/skills/harness-run/references/review-and-ship.md plugins/maeng-harness/skills/harness-run/SKILL.md` shows the rule in both files.
- AC-5: `python3 -m pytest -q` in `plugins/maeng-harness` passes.
