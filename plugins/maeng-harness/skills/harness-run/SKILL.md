---
name: harness-run
description: Use when work is big enough to need a plan and a task tree - "build/implement/design X", multi-file or multi-step coding, a feature with several parts, research-then-build, anything that deserves interview, Spec/Plan, verification and independent review (구현, 설계, 기능 만들어줘, 계획 세워서 진행, 큰 작업, 작업 분해, 태스크 트리). Drives the personal workflow from interview through merge and outcome records. Skip for ordinary answers and trivial edits.
---

# harness-run (Claude edition)

The user's workflow for substantial work in the personal world. The plugin hooks enforce the code gates (verification, review receipts, merge route) and nudge recording; this skill is how you work inside them. In the eta world this plugin is off and eta's own rules apply.

Records are autonomous, code is strict: write Linear and Obsidian without asking; publish to Notion only after a Sol review; push, open PRs and merge only with verification evidence bound to the exact code.

## Where things live

| Thing | Home |
|---|---|
| Work map: issues, sub-issues, Spec/Plan documents, decisions, progress, review findings | Linear (workspace `maeng`, team MAE), written by you, never by the user |
| LLM context: notes, ADRs, drafts, reviews, session logs | Obsidian vault via the `obsidian-workspace` skill |
| Final outcomes and policies | Notion, only through the `work-records` Sol flow; the user gets the link |
| Code | git feature branch, PR, `maeng-ship merge` |

## The workflow

Scale it down for small work: a small task can skip the interview and tree but keeps Spec/Plan-lite (a goal, 1-3 `AC-n`, a Verification line), verification, review and recording.

1. **Interview** only for what changes architecture or workflow and cannot be read from the repo or issue. Settled decisions are not reopened. Detail: [workflow.md](references/workflow.md). When the work starts from a new product or AI-system idea, run the `maeng-tools:ai-loop-design` checklist here and carry its design note into the parent Spec.
2. **Mandatory rules.** Write down the constraints that bind every task (repo rules, environment, forbidden changes) in the parent Spec.
3. **Middleman first.** A code-level question the existing pages and code do not answer becomes a Middleman issue, answered before the tree is split. See [middleman](../work-records/references/middleman.md).
4. **Task tree.** Parent issue, then child issues as fine-grained as is useful, each with one owner (Owns) and explicit dependencies (`blocks`/`blockedBy`).
5. **Spec + Plan per task** as Linear documents, finer criteria at depth. The Spec carries `must_haves` (truths, artifacts, key_links), the numbered `AC-n` criteria and the `D-n` decision ids; the Plan carries the steps (each citing the `AC-n` it advances) and a `Verification` section that names the check for every `AC-n`. A falsify-first reviewer reads `must_haves` from the Spec. Template: [spec-plan.md](references/spec-plan.md).
6. **Bind.** `maeng-verify bind MAE-n --plan <doc>` for the task you are about to work on. Gates read this binding; suggestions in `last-bindings.json` never count.
7. **Implement.** Delegate one approved task to `maeng-tools:implementer` (Sonnet) with the Spec/Plan text, Owns boundary and the Verification section; it must end with `Verification:` and `Unfinished:`. Keep design, integration and acceptance with you. Disjoint write sets may run in parallel; overlapping ones are sequenced.
8. **Verify** per [verification.md](references/verification.md): run the checks the Plan names after the last edit, declare any non-test check with `maeng-verify ran`, and record the plan result with `maeng-verify plan --met ... --unmet ...`. A tree is *ship-verified* only with every required check ok at an unchanged tree and every `AC-n` met. A skip never ships; it only satisfies Stop.
9. **Self-record** (verification.md): after the last substantive change, write the progress, decision or result to the bound Linear issue or an Obsidian note whose `linear` key includes it. Do it yourself; never ask the user.
10. **Review tier** (`maeng-review`; details in [review-and-ship.md](references/review-and-ship.md)): Codex always comes first. Tiers: child-task PR, Sol xhigh; parent integration, Astra high; design/rules docs, Astra medium; small work without a tree, Sol high; Notion outcome payload, Sol medium; research draft (`--kind research`), Sol xhigh. Only after 3 failed codex attempts (e.g. usage exhausted) does it fall back to Claude: parent integration, Fable medium; everything else, Opus (docs, research and small work high; child-task PRs and Notion medium). Architect review of a task is falsify-first: start from "goal not achieved" and look for the proof.
11. **Merge** only with `maeng-ship merge <PR>` and a matching `pass` receipt. If the base moved: update, re-verify, re-review. `maeng-review` refuses a fifth review run on the same PR; then, or whenever the user's approval is needed, send the CEO brief (below) and wait for `승인 #N`.
12. **Outcome records.** Obsidian ADR/session note, then the Notion record through `work-records` (Sol medium), then give the user the link only. Then close the Linear issue yourself (Done) once every `AC-n` is met, the review passed and the records are linked; the user never manages Linear.

## Autonomy and the CEO

The user is the CEO: they set purpose and direction, the agents work on their own, and the user judges once, before final approval. Decide by reversibility:

| Act without asking | Stop for the CEO |
|---|---|
| Reading, research, code on a feature branch, tests, PRs, Linear and Obsidian records, Slack reports to `#maestro-claude` | Merge to the default branch, deploys, deleting data, real money, messages to other people or teams, anything the Spec marks as a stop |

Do not ask mid-task what a sensible default or the Spec already answers; note the assumption and keep going.

**CEO brief.** Before every approval request, post one brief to Slack `#maestro-claude` and the bound Linear issue:
1. **Intent**: the purpose in one line, and the `AC-n` it serves.
2. **Candidates**: the options considered and why the chosen one won.
3. **Result**: what changed (PR, files), what it does now.
4. **Evidence**: checks run with results, review verdict, backend and rounds, open findings with severity.
5. **Risk and rollback**: what could break, and how to undo it.
6. **The decision**: one question, e.g. `승인 #N`, or a choice between named options.

**dots and Slack.** dots (Slack bot `seojunmaeng-maestro`) injects work by running the local `claude` CLI through its Mac Work task, passing `MAENG_TASK_ID` or a `task_id: X` line. Slack `@Claude` mentions do not reach local sessions: read and post Slack yourself (`slack-maeng`). The hooks keep `~/Documents/maeng-harness/status/<task_id>.json` and `manifest.json` current for dots; end a run's last reply with one marker line (`result:`, `needs input:` or `failed:`), because the Stop hook reads it into the status file.

## Choosing helpers

- Specialist skills: pick the smallest set that materially helps the deliverable (a deck needs presentation guidance, a diagram needs `diagram-explainer`), read them before applying, and say which you used. User requirements and repo constraints outrank advisory skills. Visual deliverables: [visual-artifacts.md](references/visual-artifacts.md).
- Agents: `maeng-tools:architect` (Opus, read-only design and internal review), `maeng-tools:implementer` (Sonnet), `maeng-tools:researcher` (Haiku, read-only research). The session itself stays on Opus. Do not set `CLAUDE_CODE_SUBAGENT_MODEL`.
- Collection and research: `aside-collect` gathers, `aside-research` judges.
- Planning or coding handoffs for another agent: the `task-brief` and `execute-code-brief` skills.

## Failure handling

- Verification fails: fix within scope and re-run; at most three repair cycles on the same failure, then record the blocker in Linear and stop that branch of work. Never mark an unmet `AC-n` as met.
- A page is silent or two sources disagree: stop that step and ask, as a Middleman question if it is a code question.
- Review `fail` or `blocked`: fix, then request a new review of the new head. A receipt is single use and bound to the exact base/head/criteria.
- Uncertain write (timeout, lost response): read back before retrying; never retry blindly or create a duplicate.
- Hooks are guardrails against mistakes, not a security boundary; do not look for ways around a denial. Use the sanctioned route (for merges, `maeng-ship merge`).

## Feedback

One-off corrections stay in the task; reusable preferences go to the specialist skill through `skill-feedback`; deterministic defects go into code with a regression test.
