---
name: orca-race
description: Use when the user says "Orca - race" (orca race, 경주, 레이스) or hands over a bug whose cause is unclear and wants Claude and Codex to attack it separately - after at least one failed attempt, an intermittent failure, or two plausible hypotheses. A pre-flight interview - fixes the evidence, purpose, guardrails, scope, done and stop criteria and report format with the user, then asks once before launching two Orca worktrees. Known fixes and small edits stay in the session; a bug that cannot be reproduced or observed goes back to evidence gathering first; a production outage gets rolled back before any race; spreading a task tree across models is orca-big-task.
---

# orca-race

Two models, one bug, separate worktrees, the same brief. The value is where they disagree; that is the hard part the user decides. A race costs about twice the tokens, so it needs a reason.

Nothing launches before the user answers the last question with yes. The interview exists because an agent "will always produce a fix"; the brief decides whether that fix means anything.

## 0. Is a race worth it?

Say no and stop (with the reason) when any of these holds:

- The cause is already known, or the fix is a few lines: fix it here.
- The bug was never reproduced and there is no log, trace or failing run to point at: gather evidence first. A brief without evidence makes two guesses.
- Production is down: roll back first, race the cause afterwards.
- The two racers would need the same live resource (one database, one device, one paid API quota) and cannot be isolated.

## 1. Read before asking

Collect what the repo, issue, logs and this conversation already say: the symptom, error text, failing command, recent commits (`git log`), last known good version, attempts already made. Run `orca status --json` to confirm the runtime is up. Ask only for what is still missing.

## 2. Interview

Use AskUserQuestion, at most four questions per round and at most two rounds. Offer the default from [brief-template.md](references/brief-template.md) as the first option, so a yes keeps it.

| Part | Fix with the user | Default when the user has no preference |
|---|---|---|
| Evidence | repro command with literal inputs, expected vs actual, environment (commit, OS, flags), repro rate, logs, what was tried | none; the race waits for at least one repro or one concrete log |
| Purpose | what counts as solved: (a) root cause explained, no code change; (b) root cause plus minimal fix; (c) workaround acceptable | (b) |
| Guardrails | the must-not list | the template's list |
| Scope | paths the racers may edit; paths they must not touch | edit only the area the evidence points to; never secrets, migrations, infra, lockfiles |
| Done | the check that proves it, per purpose: (a) a command or probe that shows the mechanism, repro unchanged; (b)/(c) the repro turns green and the named suite stays green | (b)/(c): repro test + the area's suite + lint/typecheck |
| Stop | budget per racer and the give-up rule | 60 minutes or the turn cap the user names; stop and report when the bug does not reproduce or no hypothesis explains all of the evidence; after two failed fix attempts, report instead of trying a third |
| Racers | which two models | Opus (`claude-opus-5-5`, xhigh) vs Sol (`gpt-6.1-sol`, xhigh), the two best-evidenced coders in [orca-big-task's model notes](../orca-big-task/references/models.md); re-check there first. Different vendors, never the same model twice |
| Judging | what decides the winner, in order | root cause backed by evidence > guardrails kept > Done check passes on re-run > smaller diff |

## 3. Freeze the repro

When the purpose includes a fix, write the failing repro test (or script) before the race, show it to the user, and commit it on a race base branch. Both racers start from that commit. This stops either racer from weakening the check, and it gives the user one fixed bar. If a repro test cannot be written, the Done row must name another check the coordinator can run itself.

## 4. The brief and the launch question

Fill [brief-template.md](references/brief-template.md) and show the whole brief to the user, then ask one question:

> 이 브리프로 <model A> vs <model B> 경주를 시작할까요?

Buttons: start, change something. On change, edit the brief and ask again; do not launch on a partial answer.

## 5. Launch (after yes)

Follow the installed `orchestration` skill (`orca skills get orchestration --full` once per run) as coordinator:

```text
orca orchestration run-create --objective "race: <bug in one line>" --json
orca orchestration worker-start --spec "<brief>" --worktree new-child --base-branch <race-base> --agent claude --model <id> --effort <level> --display-name race-claude --json
orca orchestration worker-start --spec "<brief>" --worktree new-child --base-branch <race-base> --agent codex --model <id> --effort <level> --display-name race-codex --json
orca orchestration check --wait --types "worker_done,escalation,question" --timeout-ms 900000 --json
```

- Each racer sees only the brief, never the other racer's work.
- Answer racer questions from the brief. Anything that would change the brief (scope, purpose, a guardrail) goes to the user, and the same answer goes to both racers.
- Racers do not push, open PRs or merge. A request for a stop-list action becomes a gate (`gate-create`) for the user.

## 6. Compare

When both settle (or one hits its stop rule), check each racer yourself; a racer's report is a claim:

1. `git diff --name-only <race-base>...<racer-branch>`: flag any file outside Scope, and any change to the frozen repro or other tests.
2. Re-run the Done check in each worktree and record the output.
3. Read the claimed root cause against the evidence: does it explain every symptom, including the repro rate?

Show one table: racer | root cause (file:line) | evidence for it | Done re-run | guardrail flags | files and lines changed | confidence | not verified. Then list where the two disagree; that list is the point of the race. Recommend a winner by the Judging order, and ask the user to pick: A, B, or neither (the race found the cause but no acceptable fix).

## 7. After the pick

- The winner continues as ordinary work under harness-run: Spec/Plan-lite, verification, `maeng-review`, CEO brief, `maeng-ship merge` after `승인 #N`. The race does not replace any gate.
- The loser's worktree: release the worker, and remove the worktree only after the user confirms nothing in it is wanted.
- Record in the bound Linear issue: the brief, both results, the disagreement list, the pick and why. Over time this shows which model wins which kind of bug.
