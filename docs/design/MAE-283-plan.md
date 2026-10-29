# MAE-283 Spec/Plan: personal-essay skill

Linear: MAE-283. Date: 2026-10-29. Single task (one new skill folder, docs only).

## Source and decisions

- Source: the user's accepted Peopleware book report (LING414, 2026-10-29). The user's twelve prompts from the claude.ai conversation, the submitted docx, and the vault note `wiki/answers/A-LING-PEOPLEWARE-REVIEW-20261029.md`. The guideline memo attached in that conversation was not found on this machine; its rules are known only from the user's summary.
- D-1: a new skill, not an edit to `coherent-writing`. That skill keeps supplied evidence faithful; it does not elicit the user's own stance, guard ownership or run the user's revision loop. Prose coherence stays delegated to it.
- D-2: the close is the user's choice (conclusion, proposal, hypothesis or open question, regret, reflection). The Peopleware essay ended with proposals because the user wanted to speak to classmates; that is not the default (user, 2026-10-29).
- D-3: the example file keeps the inputs and revision sequence but not the student ID or the full text, which stay in the vault.

## Criteria

- **AC-1** `plugins/maeng-tools/skills/personal-essay/SKILL.md` exists with `name: personal-essay` and a "Use when" description with Korean triggers that names its redirect (`coherent-writing`).
- **AC-2** The skill's inputs cover assignment constraints verbatim, source material, the author memo, format, and the reader and close; a missing memo is asked for once, not drafted.
- **AC-3** Ownership rules: no invented experiences, results, feelings, numbers or quotes; ideas the user did not give are offered separately; forecasts are the user's expectation.
- **AC-4** The default shape and revision loop follow the accepted case, and the close type is not fixed (D-2).
- **AC-5** SKILL.md stays at or under 150 lines; `references/brief-template.md` and `references/example-peopleware.md` are linked from it, and the example has no student ID.

## Steps

1. Write SKILL.md (AC-1 to AC-5).
2. Write `references/brief-template.md` and `references/example-peopleware.md` (AC-2, AC-4, AC-5).

## Verification

- AC-1, AC-5: `claude plugin validate plugins/maeng-tools` prints `Validation passed`; the check below prints `missing [] unlinked []`, `name ok True redirect True` and `id False`.

```bash
python3 -I -c "import re,pathlib; d=pathlib.Path('plugins/maeng-tools/skills/personal-essay'); b=(d/'SKILL.md').read_text(); refs=re.findall(r'\]\((references/[^)#]+)', b); print('missing',[r for r in refs if not (d/r).is_file()],'unlinked',sorted({p.relative_to(d).as_posix() for p in (d/'references').glob('*.md')}-set(refs)),'lines',b.count(chr(10))); fm=b.split('---')[1]; print('name ok','name: personal-essay' in fm,'redirect','coherent-writing' in fm); print('id','2025131619' in (d/'references/example-peopleware.md').read_text())"
```
- AC-1 trigger: `claude -p --plugin-dir ./plugins/maeng-tools` with a book-report request and a retrospective request each invokes `maeng-tools:personal-essay` (done 2026-10-29; both asked for the memo and the reader/close).
- AC-2, AC-3, AC-4: review items, checked in the Codex review against this Plan.
- The full root `pytest -q` once at the end (docs-only change, no code touched).
