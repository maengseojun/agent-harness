---
name: task-brief
description: Clarify a substantial assignment and prepare a handoff brief for Codex or ChatGPT Work when the user asks to plan, scope, specify, or prepare a task for execution.
---

# Task brief

Turn an initial request into enough shared understanding to execute without consequential guessing. Match the request's language. Respect an existing brief and accepted decisions; do not restart an interview.

Inspect relevant available material before asking questions. Resolve factual questions from sources and ask only about consequential preferences, missing inputs, or contradictions. Keep small tasks small. Planning does not require exhaustive detail or an approval ritual.

Default routing: coding and technical verification to Codex; research, documents, spreadsheets, and pitch preparation to Work. Respect the user's chosen surface. Mixed tasks share one brief: verify product capabilities before using them as pitch claims. Never transfer or create a task without the user's request, or claim a handoff occurred merely because a brief exists.

Use [work-records — Project/task workflow](../work-records/SKILL.md#projecttask-workflow)
for interview/research-informed Architecture/Rules, assigned Tasks and separate
Spec/Plan and blockers identified after task creation/assignment: prerequisite
work, research or decisions needed for accurate execution, without requiring a
hard stop. Shared blockers link all dependent tasks; independent blocker work
has its own Spec/Plan. Use the same contract for revision/approval
references and requirement-to-task/Acceptance mapping. Interview only unresolved
criteria; standalone short/mid tasks need no project Architecture overhead.

Produce a concise brief covering only applicable items:

- Goal, audience, and the decision or action the output should support.
- Deliverables, destination format, language, tone, and constraints.
- Accepted decisions, source references, and reusable inputs.
- Unknowns: distinguish questions blocking execution from facts to investigate during execution.
- Approach and relevant available capabilities, with concrete acceptance checks.
- Execution destination and immediate next action.

A brief meant for an agent to execute has five fields, filled from the items above: `TASK:` (with the reason), `DELIVERABLE:`, `SCOPE:` (files it may change, or the exact files to read), `VERIFY:` (the command verbatim and its expected result) and `STOP WHEN:`. Skip a field only when it does not apply.

Preserve source URLs or file references rather than embedding whole retrieved documents. State the access requirements for the destination: a local path alone is not a transferable attachment. Include the brief in the answer unless a saved file is requested or necessary for the handoff.

When the user requests execution and the necessary tools are available, use the brief to continue within their authorized scope. Do not force a separate Chat phase or task merely because this skill was selected.
