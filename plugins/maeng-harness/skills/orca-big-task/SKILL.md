---
name: orca-big-task
description: Use when the user says "Orca - big task" (orca big task, 오르카로 큰 작업, 모델 배치) or wants a task tree spread across Claude, Codex and Grok workers in Orca. A pre-flight placement - reads the task tree, refreshes what each model is currently good at, asks only what it cannot read, proposes which model takes which row (Claude:Codex about 2:1, Opus main, Astra for architecture critique, Grok only on the smallest leaf rows) and asks once before launching. Work without a Spec/Plan goes to harness-run first; one bug raced across two models is orca-race; fewer than three independent rows stay in the session.
---

# orca-big-task

The user decides whether to launch; this skill decides who does what, and shows its reasons. Nothing starts in Orca before the user answers the last question with yes. Placement does not change harness-run: Spec/Plan, verification, `maeng-review`, the CEO brief and `maeng-ship merge` after `승인 #N` stay as they are. Orca carries the work up to one integrated branch.

## 0. Preconditions

- The task has a parent Spec/Plan with a Sub-tasks table (harness-run steps 1-6: `AC-n`, Owns, rows with Do / Writes / Interfaces / Done / Fails-if / After). If it does not, run harness-run up to the tree first; this skill places work, it does not design it.
- At least three rows that can run apart (no shared file or interface). Below that, Orca costs more than it saves: say so and keep the work in the session.
- `orca status --json` is up, and `orca skills get orchestration --full` has been read once for this run.

## 1. Read the work

For every Sub-task row, write its kind from what the row says:

| Kind | Looks like |
|---|---|
| interface | defines a type, schema, API or module boundary others consume |
| ambiguous | the Spec leaves a real choice, or the cause or approach is unknown |
| integration | joins two or more rows' outputs |
| spec-impl | well-specified logic with a Done command |
| test | writes tests against a fixed contract |
| docs | prose, comments, READMEs |
| ui | front-end checked by screenshot |
| scan | read-only search, inventory, summary |
| tiny | one file, about 30 changed lines or fewer, exact instructions, a Done command, consumes no interface it does not already see, and no judgment |

Interface rows run first and land on the parent branch before the rows that consume them branch off.

## 2. Refresh the model notes

Read [models.md](references/models.md). Compare its "Local ids" with what the CLIs list now (`~/.codex/models_cache.json`, `grok models`, the Claude model list). If the notes are older than 30 days or a list changed, research the changes (`maeng-tools:researcher`, sources at the end of models.md) before placing, and say in the proposal what changed. Propose an update to models.md through `skill-feedback`; do not edit it mid-run.

## 3. Ask only what cannot be read

AskUserQuestion, one round, at most four questions, defaults first:

1. Rows that must stay with Claude (secrets, eta-only code, anything the user does not want sent to OpenAI or xAI). Default: none beyond the Spec's forbidden paths.
2. Quota right now: is Codex usage available, and should Grok be used at all? Default: both available.
3. Concurrent worktrees. Default: 3 (most users run 2-5).
4. Review depth: the harness tiers only, or also cross-model review of every implementation row (which shifts the real token ratio toward Codex). Default: harness tiers only.

Skip a question the Spec or the conversation already answers.

## 4. Place

Fixed by the user (MAE-293 D-2):

- **Opus is the main model.** This session is the coordinator (상무): split, integration, re-running Done, the CEO brief. It is not counted as a worker.
- **Astra raises architecture-level issues, never authors.** Wave 0 is an Astra critique (`gpt-6-astra`, effort high, read-only) of the parent Spec, the interfaces and the row split: boundaries, missing rows, rows that secretly share a file or interface, risks to `AC-n`. Astra also keeps its harness tiers (design docs) and is the standby when Fable's parent integration review fails.
- **Claude:Codex is about 2:1 by worker rows**: every Sub-task row placed on a Claude or Codex model counts, scan rows included. The coordinator, Astra's wave 0 and the harness reviews are not rows and are listed separately. Count it and show it. If it is off, move swing rows (ones the table rates fine for both) until it is close; never move a row against its kind to hit the number.
- **Grok takes only `tiny` rows**, as the bottom worker. It never reviews, never owns an interface, never commits; the coordinator re-runs its Done and commits for it. Grok rows are counted separately, not in the ratio.

Default placement by kind (from models.md; change it when the refreshed notes say so):

| Kind | First choice | Swing / alternative |
|---|---|---|
| interface, ambiguous, integration | Opus (`claude-opus-5-5`, high) | none; keep with Claude |
| spec-impl | Sonnet (`claude-sonnet-5-5`, medium) | Sol (`gpt-6.1-sol`, xhigh) |
| test | Sol (xhigh) | Sonnet (medium) |
| docs | Sonnet (medium) | Terra (`gpt-6.1-terra`) |
| ui | Sonnet (medium) + `maeng-tools:design-reviewer` | Terra |
| scan | Haiku (`claude-haiku-5-5`) | none; Grok only if the row also qualifies as `tiny` |
| tiny | Grok (`grok-4.7-build-fast`) | Haiku; Luna (`gpt-6-luna`) only with an exact spec |

Not placed as workers: Fable (parent integration review and audits only), gpt-reserve (no public source).

Waves: a wave holds rows whose After rows are done and whose Writes do not overlap, up to the concurrency cap. Code-writing rows that share a file or interface never run in the same wave (harness-run Implement).

## 5. Proposal and the launch question

Show:

1. The table: row | kind | model and effort | why (one models.md reason) | wave | Done.
2. Counts: Claude N rows, Codex M rows (ratio N:M against 2:1), Grok K rows; reviews (Astra wave 0, Fable parent integration, Sol child reviews per review-and-ship.md).
3. What changed in the model notes, if anything.
4. Gates: push, merge, deploy, migrations, deleting data, money and messages to other people stay with the user (harness-run stop list).

Then ask one question:

> 이렇게 배치해서 Orca 실행할까요?

Buttons: launch, change placement. On change, re-place and ask again. When Astra's wave 0 changes the Spec, an `AC-n` or the row split, show the revised table and ask again before wave 1. No row Task exists yet at that point (section 6), so the revision costs nothing to apply.

## 6. Launch (after yes)

Follow the `orchestration` skill as coordinator. Orca can update a Task's status and result but not its spec or dependencies (`task-update`, v1.4.243), so the graph is created only once it is final:

1. Wave 0 runs alone: one `worker-start --spec "<Astra critique brief>" --agent codex --model gpt-6-astra --effort high --worktree current` on the Run, read-only, before any row Task exists.
2. Apply its findings, re-ask if the table changed (section 5), then create every row Task at once with `--deps` from the After column. Do not add Tasks mid-run; if the split must change later, abandon the Run and create a new one with the new graph.

```text
orca orchestration run-create --objective "<MAE-n>: <goal>" --json
orca orchestration task-create --spec "<row brief>" --task-title "<row>" --deps '[...]' --json
orca orchestration worker-start --task <id> --worktree new-child --agent claude --model claude-sonnet-5-5 --effort medium --json
orca orchestration worker-start --task <id> --worktree new-child --agent codex --model gpt-6.1-sol --effort xhigh --json
orca orchestration check --wait --types "worker_done,escalation,question" --timeout-ms 900000 --json
```

- Each row brief uses the org-chart.md delegation format: the head, `Why:` with the `AC-n`, Writes as the only files it may change, Interfaces, Done, Fails-if, when to stop, and the model's line from org-chart.md. Workers commit on their own worktree branch and do not push, open PRs or merge.
- Grok is not an Orca agent id. Start it in a terminal (`orca terminal create --worktree <sel> --command "grok -m grok-4.7-build-fast"`) and pass that handle as `worker-start --terminal <handle> --worktree <sel>`. Whether Grok follows the worker preamble (`worker_done`) is unverified; on the first run give it one trivial row and watch. If it does not report, run tiny rows headless instead (`grok -p "<row brief>" -m grok-4.7-build-fast --cwd <worktree>`; checked 2026-10-31: `-p` with `--cwd` runs in that folder) and check the result yourself.
- Repairs go back to the same worker with `dispatch --inject` in the org-chart.md repair format; the third cycle goes to a fresh worker.
- A stop-list action becomes a `gate-create` for the user.

## 7. Close

- For every row, re-run its Done yourself and tick the Sub-tasks table; a worker's `worker_done` is a claim.
- Merge the worker branches into the parent feature branch, then continue harness-run from Verify: checks, `maeng-review` (Fable parent integration, Astra standby), CEO brief, `승인 #N`, `maeng-ship merge`.
- Release workers, and remove worktrees once their branches are merged.
- Record in the parent Linear issue, for each row: model, effort, repair cycles, whether Done passed on the first re-run. When the same model keeps failing the same kind of row, propose a change to models.md through `skill-feedback`.
