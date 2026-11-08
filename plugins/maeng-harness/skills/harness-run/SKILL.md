---
name: harness-run
description: Use when work is big enough to need a plan and a task tree - "build/implement/design X", multi-file or multi-step coding, a feature with several parts, research-then-build, anything that deserves interview, Spec/Plan, verification and independent review (구현, 설계, 기능 만들어줘, 계획 세워서 진행, 큰 작업, 작업 분해, 태스크 트리). Drives the personal workflow from interview through merge and outcome records. Skip for ordinary answers and trivial edits.
---

# harness-run (Claude edition)

The user's workflow for substantial work in the personal world. The plugin hooks enforce the code gates (verification, review receipts, merge route) and nudge recording; this skill is how you work inside them. In eta checkouts eta's own rules come first; the ranks, DRI and message formats of [org-chart.md](references/org-chart.md) still apply to local work on top of them.

Records are autonomous, code is strict: write Linear and Obsidian without asking; publish to Notion only after a Sol review; push, open PRs and merge only with verification evidence bound to the exact code.

## Where things live

| Thing | Home |
|---|---|
| Work map: issues, sub-issues, Spec/Plan documents, decisions, progress, review findings | Linear (workspace `maeng`, team MAE), written by you, never by the user |
| LLM context: notes, ADRs, drafts, reviews, session logs | Obsidian vault via the `obsidian-workspace` skill |
| Final outcomes and policies | Notion, only through the `work-records` Sol flow; the user gets the link |
| Code | git feature branch, PR, `maeng-ship merge` |

## The workflow

Quality layer: for a non-code result the user will show or submit, follow [quality-layer](../quality-layer/SKILL.md) (criteria from real examples, independent check, closing walkthrough).

Scale it down for small work: a small task can skip the interview and tree but keeps Spec/Plan-lite (a goal, a Deliverable line, Assumptions or "none", 1-3 `AC-n`, a Verification line, the Revisions log and the Close-out), verification, review and recording.

1. **Interview** only for what changes architecture or workflow and cannot be read from the repo or issue. Settled decisions are not reopened. Detail: [workflow.md](references/workflow.md). When the work starts from a new product or AI-system idea, run the `maeng-tools:ai-loop-design` checklist here and carry its design note into the parent Spec. When the big picture is settled, propose a part map and run the user's design interviews ([comprehension-gate](../comprehension-gate/SKILL.md)); code in a mapped part waits for them. Architecture and workflow recommendations are sealed before the user chooses.
2. **Mandatory rules.** Write down the constraints that bind every task (repo rules, environment, forbidden changes) in the parent Spec.
3. **Middleman first.** A code-level question the existing pages and code do not answer becomes a Middleman issue, answered before the tree is split. See [middleman](../work-records/references/middleman.md).
4. **Task tree.** Parent issue, then child issues as fine-grained as is useful, each with one owner (Owns), one `DRI:` line ([org-chart.md](references/org-chart.md) DRI) and explicit dependencies (`blocks`/`blockedBy`). Child issues track the work; by default their commits go into one PR, the *parent task*, and a child gets its own PR only when it must merge before another change can build ([org-chart.md](references/org-chart.md)). Inside a PR, split into rows of the Plan's Sub-tasks table ([Sub-tasks](#sub-tasks)), never into Linear issues.
5. **Spec + Plan per task** as Linear documents or the repo file `docs/design/MAE-n-plan.md` (the file is what `maeng-review --plan` reads; link it from the issue), finer criteria at depth. The Spec carries `must_haves` (truths, artifacts, key_links), the numbered `AC-n` criteria and the `D-n` decision ids; the Plan carries the steps (each citing the `AC-n` it advances) and a `Verification` section that names the check for every `AC-n`. A falsify-first reviewer reads `must_haves` from the Spec. Template: [spec-plan.md](references/spec-plan.md).
6. **Bind.** Search Linear, Notion and the vault for the task and run the `decisions` skill's related check (bind refuses without it), then `maeng-verify bind MAE-n --plan <doc>` for the task you are about to work on. Gates read this binding; suggestions in `last-bindings.json` never count.
7. **Implement.** Delegate one approved task to the personal-flow definition of its Sub-tasks Grade (`maeng-tools:quick`, `standard` or `design`; `implementer` when there is no table), never `general-purpose`. The brief has five fields, TASK, DELIVERABLE, SCOPE, VERIFY (the command verbatim) and STOP WHEN ([org-chart.md](references/org-chart.md)), with the Spec/Plan text and Owns boundary; the report starts with `Status: done | partial | blocked` and ends with `Verification:` and `Unfinished:`. Keep design, integration and acceptance with you. Code-writing work runs one task after another by default, and in parallel only when the tasks share no file and no interface; read-only work (research, scans, reviews) may fan out.
8. **Verify** per [verification.md](references/verification.md): run the checks the Plan names after the last edit, declare any non-test check with `maeng-verify ran`, and record the plan result with `maeng-verify plan --met ... --unmet ...`. A tree is *ship-verified* only with every required check ok at an unchanged tree and every `AC-n` met. A skip never ships; it only clears the Stop notice.
9. **Self-record** (verification.md): after the last substantive change, write the progress, decision or result to the bound Linear issue or an Obsidian note whose `linear` key includes it. Do it yourself; never ask the user.
10. **Review tier** (`maeng-review`; details in [review-and-ship.md](references/review-and-ship.md)): Codex comes first, except for parent integration. Tiers: child-task PR, Sol xhigh; parent integration, Fable high first with Astra high as its standby when Fable fails; design/rules doc drafts, Astra medium (a PR you will merge takes `--kind code` even when it is docs only); plan review of a large task (`--kind plan`), Astra high; small work without a tree, Sol high; Notion outcome payload, Sol medium; research draft (`--kind research`), Sol xhigh. Parent and plan reviews need `--planner-model <id>`; that model is skipped as reviewer. Code that Sol/Codex wrote is never reviewed by Sol: pass `--author codex` and Opus high reviews it instead. Only after 3 failed codex attempts (e.g. usage exhausted) does it fall back to Claude Opus (docs, research and small work high; child-task PRs and Notion high). Architect review of a task is falsify-first: start from "goal not achieved" and look for the proof.
11. **Merge** only with `maeng-ship merge <PR>` and a matching `pass` receipt. If the base moved: update, re-verify, re-review. A PR over 150 changed lines, or one touching a mapped part, also needs the user's merge quiz (comprehension-gate), started last once the review passed; `승인 #N` replaces only the review. `maeng-review` counts reviewed heads: two rounds, then one `--confirm` run when a critical/high finding remains ([review-and-ship.md](references/review-and-ship.md)). After that, or whenever the user's approval is needed, send the CEO brief (below) and wait for `승인 #N`.
12. **Outcome records.** Judge each `D-n` held, broke or open against its signal ([org-chart.md](references/org-chart.md) DRI) and write the judgments, with the Plan's `Close-out`, into the Linear closing comment and the Obsidian ADR/session note; each broke one gets one learning line through [Feedback](#feedback). Then the Notion record through `work-records` (Sol medium), then give the user the link only. Then close the Linear issue yourself (Done) once every `AC-n` is met, the review passed and the records are linked; the user never manages Linear.

## Stage entry and exit

Each stage has an entry and an exit criterion. `code` means a script or hook refuses the move (named by path under `plugins/maeng-harness`); `doc` means only this page asks for it.

| Stage | Entry | Exit | Enforced by |
|---|---|---|---|
| interview | a question about architecture or workflow that the repo and issue cannot answer | every `D-n` settled; no open question that changes what ships | `doc` |
| spec/plan | interview exit, or a small task | Spec with numbered `AC-n`; Plan with a Verification line for every `AC-n` and a Sub-tasks row per part; a large task also gets a plan review (`--kind plan`), and a missing receipt only produces a notice | `doc` |
| bind | Spec/Plan document exists; the `decisions` related check ran | `maeng-verify bind` stored the binding with a non-null `criteria_rev` | `code` `bin/maeng-verify` |
| implement | binding exists; one approved Sub-tasks row | the planner re-ran the row's Done | `doc` |
| verify | last edit made | every Plan check has runner evidence at the unchanged tree; every `AC-n` marked met | `code` `bin/maeng-verify`, `lib/maeng/evidence.py` |
| review | head is ship-verified (full suite, never an impact run) | `pass` receipt for the exact base, head and `criteria_rev` within two counted heads plus one `--confirm` | `code` `bin/maeng-review`, `lib/maeng/receipts.py` |
| merge | `pass` receipt or `승인 #N`, ship-verified head, base is an ancestor | `maeng-ship merge <PR>` pushed | `code` `bin/maeng-ship`, `lib/maeng/gates.py` |
| records | the last substantive change | progress, each `D-n` judgment and the Close-out written; Linear closed | `doc` (Stop notifies, never blocks) |

## Sub-tasks

One PR is one parent task. Split the task into Sub-task rows (never into separate PRs; PR splits follow org-chart.md) only where a reviewer could reject one part and accept its neighbour. A change of about 150 lines or less stays one task with one Done check; there is no fixed count. Why (MAE-244): fixed criteria and re-run checks catch "done" claims, but parallel writers make conflicting implicit decisions and small splits cost more than they save.

The Plan's `Sub-tasks` table is the ledger and survives compaction. Tick a row only after you have re-run its Done yourself; a sub-agent's report is a claim, not evidence. This is the one re-run: the full suite and the review still run once, at the parent.

| Column | Content |
|---|---|
| Do | one deliverable |
| Writes | files, inside the PR's Owns |
| Interfaces | exact names it consumes from or produces for other rows, when any |
| Done | code: one command and its expected output; judgment (docs, design): a review item checked in the parent review |
| Fails-if | what makes it not done; for logic (branches, calculations, security) include a vacuous pass, a mutation the tests do not catch, and the negative paths (null, empty, negative, exception) ([verification.md](references/verification.md)) |
| After | rows it waits for |
| Grade | `quick`, `standard`, `deep` or `design`: the row of `policy/roles.json` that sets the agent, model and effort; a task without a table drops one grade; the planner raises a grade only with a reason in Revisions |

- Expected values come from the Spec or an independent source, never from running the code under test.
- Rows run their targeted tests. The full suite, the Codex review and the CEO brief happen once, at the parent, judged against the Spec `AC-n` and not only the ticks.
- A failing row gets the repair cycles in Failure handling, each with a concrete change; then split it, or drop it and say so in the CEO brief. Decide and record rulings instead of waiting, except on the stop list and the questions Failure handling says to ask.

## Autonomy and the CEO

The user is the CEO: they set purpose and direction, the agents work on their own, and the user judges before final approval and shows in the comprehension gate (design interviews, merge quiz; the `comprehension-gate` skill) that they can explain and defend what was built. Decide by reversibility:

| Act without asking | Stop for the CEO |
|---|---|
| Reading, research, code on a feature branch, tests, PRs, Linear and Obsidian records, Slack reports to `#maestro-claude` | Merge to the default branch, deploys, deleting data, real money, messages to other people or teams, anything the Spec marks as a stop, a step the comprehension gate blocks (the user's interview, quiz or waiver: never answer, grade or waive for them) |

Do not ask mid-task what a sensible default or the Spec already answers; note the assumption as an `A-n` in the Spec and keep going. The CEO brief lists every `A-n` added since the Plan approval.

**CEO brief.** Before every approval request, post one brief to Slack `#maestro-claude` and the bound Linear issue:
1. **Intent**: the purpose in one line, and the `AC-n` it serves.
2. **Candidates**: the options considered and why the chosen one won.
3. **Result**: what changed (PR, files), what it does now.
4. **Evidence**: checks run with results, review verdict, backend and rounds, open findings with severity, wildcards used and dissent rulings (org-chart.md).
5. **Risk and rollback**: what could break, and how to undo it.
6. **The decision**: one whether-question (org-chart.md DRI layers), e.g. `승인 #N`, or a choice between named options; how-choices are already in Candidates and Result. A proposed direction (org-chart.md Wildcard) follows as its own yes/no.
7. **Understanding**: offer this closing walkthrough by default for every finished task, including tasks without an approval request. First walk through the structure and design: what was decided and why, discarded alternatives, where the result differs from the request, and what to check before shipping. Then ask 3-5 questions on structure and design; only the user may skip it, and skipping blocks nothing. The forced merge quiz for PRs over 150 changed lines or touching a mapped part remains unchanged; follow [comprehension-gate](../comprehension-gate/SKILL.md).

**dots and Slack.** dots (Slack bot `seojunmaeng-maestro`) injects work by running the local `claude` CLI through its Mac Work task, passing `MAENG_TASK_ID` or a `task_id: X` line. Slack `@Claude` mentions do not reach local sessions: read and post Slack yourself (`slack-maeng`). The hooks keep `~/Documents/maeng-harness/status/<task_id>.json` and `manifest.json` current for dots; end a run's last reply with one marker line (`result:`, `needs input:` or `failed:`), because the Stop hook reads it into the status file.

## Choosing helpers

- Specialist skills: pick the smallest set that materially helps the deliverable (a deck needs presentation guidance, a diagram needs `diagram-explainer`), read them before applying, and say which you used. User requirements and repo constraints outrank advisory skills. Visual deliverables: [visual-artifacts.md](references/visual-artifacts.md).
- Agents: the personal-flow definitions `maeng-tools:quick` (Haiku), `standard` (Sonnet) and `design` (Opus, read-only) are the default for delegated work; `general-purpose` is not. Others: `maeng-tools:architect` (Opus, read-only design and internal review), `maeng-tools:implementer` (Sonnet), `maeng-tools:researcher` (Haiku, read-only research), `maeng-tools:design-reviewer` (Sonnet, read-only review of a rendered UI). The planner is the session's model, Opus or Fable. Do not set `CLAUDE_CODE_SUBAGENT_MODEL`.
- Ranks: who does what, who may decide what (one PR by default), the delegation/report format and where each rank reads first are in [org-chart.md](references/org-chart.md).
- Collection and research: `aside-collect` gathers, `aside-research` judges.
- Planning or coding handoffs for another agent: the `task-brief` and `execute-code-brief` skills.

## Failure handling

- Verification fails: fix within scope and re-run; at most three repair cycles on the same failure, then record the blocker in Linear and split that work smaller, or drop it and name the drop in the CEO brief. Never mark an unmet `AC-n` as met.
- A page is silent or two sources disagree: when the answer changes what ships (a Spec meaning, an interface others use, anything on the stop list), stop that step and ask, as a Middleman question if it is a code question; otherwise decide, record the ruling in Linear and the CEO brief, and continue.
- Review `fail` or `blocked`: fix, then request a new review of the new head. A receipt is single use and bound to the exact base/head/criteria.
- Any fix you hand down, for a failing check or a review finding, uses the repair format (org-chart.md: `Keep:`, `Change:`, `Scope:`); the third repair cycle on the same failure goes to a fresh agent.
- Uncertain write (timeout, lost response): read back before retrying; never retry blindly or create a duplicate.
- Hooks are guardrails against mistakes, not a security boundary; do not look for ways around a denial. Use the sanctioned route (for merges, `maeng-ship merge`).

## Feedback

Use [harness-audit.md](references/harness-audit.md) to measure effects and propose evidence-backed harness changes; I-4 remains a proposal awaiting the user's decision.

One-off corrections stay in the task; reusable preferences go to the specialist skill through `skill-feedback`; deterministic defects go into code with a regression test; a CEO-approved decision that broke updates its ADR. The learning line of a broke `D-n` takes the same routes.
