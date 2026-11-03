# MAE-301 Spec/Plan: Plan template fields from the revision study

Linear: MAE-301. Date: 2026-11-03. Single task, Spec/Plan-lite (rules docs and a version bump). This Plan uses the fields it adds.

## Spec

Goal: the Spec/Plan template asks up front for what past plans missed most, and records what a later comparison of planned and unplanned work needs.

Deliverable: one PR against `feat/harness-v1` that changes three harness docs and bumps maeng-harness to 0.4.9, plus a CEO brief in Korean on Slack and Linear.

Source (user, 2026-11-03): "초안 만들기", then "PR까지 진행" on the draft `plan-template-draft.md`. The draft rests on a study of 31 planned tasks with 284 distinct revision requests: intent 50, format 54 (32 of them reply language), scope 49, constraint 43, overbuild 22, criteria plus verification 19.

Decisions:
- D-1: add `Deliverable`, `Assumptions` (A-n), `Routing`, a `Revisions` log and `Close-out`; widen `Exclusions`. Wrong if: over the next five planned tasks, intent and format revisions per task do not fall below the study's rate, or the user says the Plan takes too long to read.
- D-2: keep `must_haves`, `AC-n` and `Verification` unchanged; the gates and reviewers read them. Wrong if: none (scope).
- D-3: reply language and approval reduction stay standing rules, not fields. Wrong if: either comes back in `Revisions` across three tasks.

Assumptions:
- A-1: eta's own templates are out of scope (stated in the draft the user approved).
- A-2: the version bump goes in this PR, as in MAE-295 and MAE-296 (not in the draft).
- A-3: the `Revisions` categories are the ten from the study (intent, scope, format, constraint, overbuild, criteria, verification, reuse, order, quality).
- A-4: the harness-run line "note the assumption and keep going" gains "as an `A-n`" so mid-task assumptions reach the CEO brief (not in the draft).

Owns: `plugins/maeng-harness/skills/harness-run/references/spec-plan.md`, `plugins/maeng-harness/skills/harness-run/SKILL.md`, `plugins/maeng-harness/skills/work-records/references/project-task-workflow.md`, `plugins/maeng-harness/.claude-plugin/plugin.json`, this file.

Exclusions: eta templates; any gate or hook that reads the new fields; a tool that counts revisions from transcripts (the study's scripts stay outside the repo). Simplified away: no separate "smallest version" field, folded into `Exclusions`.

## Criteria

- **AC-1** `spec-plan.md`: the Spec template has `Deliverable:` and `Assumptions:` (A-n) and the widened `Exclusions`; the Plan template has `Routing:`, a `Revisions:` log naming the ten categories and a `Close-out:` block with size, revisions plan/result, review rounds to pass and unmet AC; Readiness asks whether every A-n is confirmed; the Rules say how an A-n differs from a D-n and how mid-task assumptions are handled.
- **AC-2** `SKILL.md`: Plan-lite includes Deliverable, Assumptions and the Revisions log; the outcome step copies Close-out into the records; the mid-task assumption line names A-n. `project-task-workflow.md` lists the new Spec/Plan fields and logs user corrections under Plan changes.
- **AC-3** The `must_haves`, `AC-n` and `Verification` parts of the template are unchanged (D-2).
- **AC-4** maeng-harness is 0.4.9, `claude plugin validate plugins/maeng-harness` passes and the root suite passes.

## Plan

Readiness: draft approved; every A-n listed above for the CEO brief.
Environment: worktree `.claude/worktrees/plan-template-fields`, branch `feat/mae-301-plan-template` from `origin/feat/harness-v1` at 391c633.
Routing: write in this Opus session (template design, about 60 lines, so no implementer hand-off); review Astra medium per the rules-docs tier; limits: none known.

Steps:
1. Edit `spec-plan.md` (AC-1, AC-3).
2. Edit `SKILL.md` and `project-task-workflow.md` (AC-2).
3. Bump the version (AC-4).

Verification tier: code (plugin.json is not a non-code path).
Verification:
- AC-1, AC-2, AC-3: the check below prints `ok`.

```bash
python3 -I -c "
import pathlib,subprocess
r=pathlib.Path('plugins/maeng-harness/skills'); sp=(r/'harness-run/references/spec-plan.md').read_text()
sk=(r/'harness-run/SKILL.md').read_text(); wf=(r/'work-records/references/project-task-workflow.md').read_text()
need=['Deliverable:','Assumptions: A-1','Routing:','Revisions:','Close-out:','every A-n confirmed','review rounds to pass','unmet AC at close']
need+=[c for c in 'intent scope format constraint overbuild criteria verification reuse order quality'.split()]
gone=subprocess.run(['git','diff','origin/feat/harness-v1','--','plugins/maeng-harness/skills/harness-run/references/spec-plan.md'],capture_output=True,text=True).stdout
kept=not any(l.startswith('-') and k in l for l in gone.splitlines() for k in ('must_haves','AC-1:','AC-2:','Verification:','truths','artifacts','key_links'))
lite='Deliverable' in sk.split('Spec/Plan-lite')[1][:300] and 'Assumptions' in sk.split('Spec/Plan-lite')[1][:300]
print('ok' if all(n in sp for n in need) and kept and lite and 'Close-out' in sk and 'A-n' in sk and 'Revisions' in wf and 'Assumptions' in wf else 'FAIL')"
```
- AC-4: `claude plugin validate plugins/maeng-harness` prints `Validation passed`; `python3 -m pytest -q` passes once at the final tree.

Failure / change handling: a review finding inside Owns is fixed here; one that asks for a gate or a tool goes to a follow-up issue.
Review focus: does each new field earn its place against the study numbers, and does any new rule conflict with harness-run autonomy ("do not ask mid-task")?

Revisions:
- none yet

Close-out:
- size: (filled at close)
- revisions: plan 0 / result 0
- review rounds to pass:
- unmet AC at close:
