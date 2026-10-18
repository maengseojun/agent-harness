# MAE-244 Spec/Plan: parent task and sub-tasks, adjusted by evidence (maeng-harness 0.3.1)

Linear: MAE-244. Date: 2026-10-18.

## Purpose

The "ETA-1042 build" session relayed a user rule: one parent task per PR, 3-7 sub-tasks each with one success command, and the coordinator re-runs every check. The user then asked for it to be adjusted against our purpose rather than adopted blindly. That purpose is the CEO model: agents work on their own, the user judges once before approval, and the harness stays practical and easy to maintain.

## Criteria

- **AC-1** harness-run states when to split. One PR is one parent task. Split only where a reviewer could reject one part and accept its neighbour. A change of about 150 lines or less stays a single task with one Done check. There is no fixed sub-task count.
- **AC-2** Each sub-task row records Do, Writes, Interfaces, Done and Fails-if. Done is a command with its expected output for code, or a review item for judgment work. Fails-if includes a vacuous pass (a mutation the tests do not catch), required for logic only.
- **AC-3** Read-only work may fan out. Code-writing work runs one task after another by default, and in parallel only when the tasks share no file and no interface.
- **AC-4** The coordinator re-runs every Done; a sub-agent's report is not evidence. Rows run their targeted tests. The full suite, the Codex review and the CEO brief happen once at the parent, which is judged against the Spec AC.
- **AC-5** A failing row gets the existing three repair cycles, each with a concrete change. After that it is split smaller, or dropped and named in the CEO brief. Rulings are decided and recorded instead of waiting, except on the stop list.
- **AC-6** The Plan's Sub-tasks table, in Linear or in `docs/design/MAE-n-plan.md`, is the ledger. Linear issues stay for parent and child work items; sub-tasks never become Linear issues.
- **AC-7** Release 0.3.1. It also ships `maeng-review --plan` from MAE-243.

## Evidence behind the adjustments (collected with aside, 2026-10-18)

- **Split only above a size, scale effort to complexity.**
  - Anthropic, "How we built our multi-agent research system": "Simple fact-finding requires just 1 agent... complex research might use more than 10 subagents"; "multi-agent systems use about 15× more tokens than chats". (https://www.anthropic.com/engineering/multi-agent-research-system)
  - GSD: "plans with 2-3 tasks each, sized for a single context window". (https://github.com/gsd-build/get-shit-done/blob/main/docs/FEATURES.md)
- **Split where a reviewer could reject one part.** superpowers writing-plans: "split only where a reviewer could meaningfully reject one task while approving its neighbor". (https://github.com/obra/superpowers/blob/main/skills/writing-plans/SKILL.md)
- **Parallel writers are the risk.**
  - Cognition: "Actions carry implicit decisions, and conflicting decisions carry bad results". (https://cognition.ai/blog/dont-build-multi-agents)
  - superpowers: "Never dispatch multiple implementation subagents in parallel (conflicts)".
  - Anthropic: "most coding tasks involve fewer truly parallelizable tasks than research".
  - GSD: "Parallel agents MUST be truly independent (no shared mutable state)".
- **Interfaces between tasks.** superpowers: "Consumes: ... exact signatures / Produces: ...".
- **Re-check reported work.** GSD: "Failed agents MUST be detected (spot-check actual output vs reported failure)"; "check against phase goals, not just task completion".
- **Repair, then split or drop.** GSD node repair: "RETRY, DECOMPOSE, or PRUNE"; superpowers: "Rulings, not stalls".

Not adopted: the fixed 3-7 count, per-task Codex reviews (they would exhaust the 4-round cap), and GSD's two-attempt repair budget (the existing three cycles stay, to avoid churn).

## Plan and verification

This is a single task: about 40 lines of docs plus a version bump, under the split threshold.

- **Done**:
  - `python3 -m pytest -q` from the repo root passes.
  - Codex review (`maeng-review run --kind code --pr N --plan docs/design/MAE-244-plan.md`) passes. It checks AC-1 to AC-6 as review items.
- **Fails-if**: the skill contradicts itself, for example on where Plans live or on whether disjoint write sets may run in parallel; or a step still allows parallel writers that share an interface.
