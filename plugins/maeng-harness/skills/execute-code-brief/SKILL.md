---
name: execute-code-brief
description: Execute an agreed coding brief or specification, preserving scope and connecting implementation to targeted verification. Use for implementation handoffs rather than general coding questions.
---

# Execute a coding brief

Read the supplied brief and applicable repository guidance. Inspect the relevant code, working changes, and project-defined checks. Preserve accepted decisions; reopen planning only for a contradiction, inaccessible required input, or evidence invalidating the approach.

Apply [work-records — Project/task workflow](../work-records/SKILL.md#projecttask-workflow)
before execution/resumption: read task → Spec/Plan → Architecture/Rules → dependencies.
Use its criteria, lead/handoff, change and offline rules; keep acceptance evidence
current and close the Linear issue yourself (Done) once AC are met, review passed and records are linked. Scale standalone tasks down.

Select additional skills only for a concrete need. Prefer available repository tools, APIs, and connectors for structured work; use computer interaction when the UI itself matters or other interfaces do not cover the task. Do not install tools, introduce orchestration, or delegate simply because they are available.

For web UI creation or refinement requiring design judgment, consider the available
`frontend-guidance` advisory skill. A requested dithered motion style also goes
through `frontend-guidance`, which recovers the archived `dither-motion-landing`
guidance from the MAE-127 archive (it is not an installed skill); an HTML deck
belongs to `frontend-slides`. The user's
design requirements outrank optional aesthetic advice. Skip guidance already
covered by the brief or existing implementation.

When existing guidance lacks a capability needed for the task, inspect relevant
GitHub skills/files. Either apply useful reading directly or acquire a reviewed
skill folder for reuse when the user has authorized acquisition. Check
overlap, pin the source commit, preserve existing skills and verify installation;
use skill-installer when available. Announce acquisition, and distinguish it from
permission to run bundled scripts, install runtimes or change hooks.

Implement the smallest sufficient change. For lengthy work, keep a compact project-local progress record with decisions, verification, and the next action; use an existing record if available. This is task state, not a request to update personal memories.

A brief in five fields (`TASK:`, `DELIVERABLE:`, `SCOPE:`, `VERIFY:`, `STOP WHEN:`) is run as written: change only `SCOPE:`, run the `VERIFY:` command verbatim, stop at `STOP WHEN:`. If a field is missing, ask or state the assumption. The final report starts with `Status: done | partial | blocked` and ends with `Verification:` and `Unfinished:`.

Run the narrowest project-defined checks that cover the change. Inspect the actual result and report what was verified and what remains unverified. Avoid repeated checks after success unless a new change or unresolved concern warrants them.

If the coding work feeds a document or pitch, provide an evidence handoff: implemented capabilities, limitations, test results, and usable demo/artifact references. Label proposed features separately from working features. Ensure a destination can access referenced files before treating the handoff as complete.
