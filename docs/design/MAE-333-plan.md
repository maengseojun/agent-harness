# MAE-333 Plan: aside-research runs the paper API search first

## Goal
When a research question depends on prior work, aside-research searches the paper APIs (OpenAlex, Semantic Scholar, arXiv, Springer Nature, KCI) before collecting, instead of relying on the "논문 확인" hook or `api-check` choosing to run.

## Scope
- Add a "Papers first" paragraph to stage 2 (Collect) of `plugins/maeng-tools/skills/aside-research/SKILL.md`.
- Bump maeng-tools so installed copies pick it up.
- Out of scope: moving `api-check` or `paper_search.py` into this repository; changes to aside-collect or the verify stage.

## Acceptance criteria
- AC-1: Stage 2 of `aside-research/SKILL.md` says when to run `paper_search.py` (questions that turn on prior work), that the top DOI or arXiv links go to `aside-collect` as seed sources so stage 3 verifies them, that `failed` or `skipped` paper sources go to Not checked, when to skip it, and to note under Limitations when `api-check` is not installed.
- AC-2: `plugins/maeng-tools/.claude-plugin/plugin.json` is bumped from 0.3.23 to 0.3.24. No other file pins the old version.
- AC-3: `python3 -m pytest -q` passes on the final tree.
