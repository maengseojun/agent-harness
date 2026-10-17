# Workflow details

Contents: [Interview](#interview) · [Mandatory rules](#mandatory-rules) · [Task tree](#task-tree) · [Status convention](#status-convention) · [Resuming](#resuming) · [Small work](#small-work)

## Interview

Purpose: settle the architecture or workflow, not collect requirements the repo already answers.

- Read first: the issue, linked documents, the repo, the relevant vault hub and latest session note. Ask only about consequential preferences, missing inputs and contradictions.
- One question at a time when asking; offer a recommended default.
- Output: the decisions, each with a `D-n` id, a reason and the alternatives rejected. Write them in the parent Spec (Linear document) and, when they outlive the task, an ADR note `wiki/decisions/ADR-<MAE-id>-<slug>.md`.

## Mandatory rules

A short list in the parent Spec that every child inherits: repo conventions, environment, forbidden changes, required checks, data/credentials handling. A child Plan may add rules but not relax them. Write them before splitting so children cannot drift.

## Task tree

- Parent issue = the goal and success criteria. Child issues = independently buildable and verifiable units, as fine-grained as is useful.
- Each child names: Owns (files/modules it may change), dependencies, its Spec and Plan documents, and the parent `D-n` it implements.
- Two children must not own the same file. If they must, sequence them or merge them.
- Middleman questions are issues of Kind Middleman, linked with `blocks`/`blockedBy` to consumers. Read the actual answer before the dependent step; Done alone is not proof.

## Status convention

Use existing Linear statuses and add one comment per transition:
- `claimed`: who/which chat is working it, branch name.
- `blocked`: the blocker and what unblocks it.
- `terminal-failed`: the attempt failed for a reason that needs a new approach; record what was tried.
- Done: you close it yourself once Acceptance is met, required review passed, and evidence, limits and links are recorded. The user never manages Linear.

## Resuming

Order: bound issue state, then Spec/Plan (`updatedAt` must match what the binding recorded), then Architecture/rules, then dependency results, then the latest session note in the vault. If a Spec/Plan changed since the binding, rebind and re-verify.

## Small work

No tree needed: one issue, a three-line Plan (goal, `AC-n`, Verification), the implementer or you directly, verify, Sol high review before any PR, record. Trivial edits (typos, config tweaks) need no issue.
