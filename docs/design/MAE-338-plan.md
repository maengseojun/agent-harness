# MAE-338 Plan: 해당 작업 면제, one waiver per session for maeng-ship merges

## Goal
The user types `해당 작업 면제 <사유>` (or `작업 면제 <사유>`) once, in an interactive session. For 24 hours, `maeng-ship merge` merges that session's PRs to origin without a review receipt, `승인 #N` or merge quiz. `작업 면제 취소` ends it early.

## Deliverable
`receipts.TASK_WAIVE` and the task-waiver store, `handlers.record_task_waiver` in UserPromptSubmit, the waiver check in `bin/maeng-ship`, docs in review-and-ship and comprehension-gate, tests, and a maeng-harness version bump.

## Assumptions
- Only the UserPromptSubmit hook writes a waiver, only in the personal world, only from a non-headless prompt read through `interview.users_text`.
- The waiver is keyed by the origin repository and the session id; a merge to another remote falls back to the usual gates.
- G1 and the ship-verified head check stay; `maeng-ship` mints a single-use approval for the head, so the receipt pending/consume flow is unchanged.
- `승인 #N` keeps accepting headless relays (user decision 2026-10-18, reconfirmed 2026-11-08).

## Acceptance criteria
- AC-1: One waiver merges two PRs of the session; after `작업 면제 취소` the next PR is refused.
- AC-2: A waiver older than 24 hours no longer lets a PR merge; a waiver typed behind the desktop app's note still counts.
- AC-3: A headless prompt, a keyword without a reason, or a message that does not start with the keyword records nothing.
- AC-4: Under a waiver, a PR over 150 changed lines merges without a merge-quiz pass.
- AC-5: The full maeng-harness suite passes on the final tree.

## Steps
1. Store, find and clear the waiver in receipts.py (AC-1, AC-2).
2. Record it from UserPromptSubmit with the headless and `users_text` checks (AC-3).
3. In maeng-ship, skip `require_merge` and mint an approval when a waiver exists (AC-1, AC-4).
4. Tests, docs, version bump (AC-5).

## Verification
- AC-1: `python3 -m pytest -q plugins/maeng-harness/tests/test_merge.py -k TaskWaiver`
- AC-2: `python3 -m pytest -q plugins/maeng-harness/tests/test_merge.py -k TaskWaiver`
- AC-3: `python3 -m pytest -q plugins/maeng-harness/tests/test_merge.py -k TaskWaiver`
- AC-4: `python3 -m pytest -q plugins/maeng-harness/tests/test_interview.py -k task_waiver`
- AC-5: `python3 -m pytest -q`

## Revisions
- 2026-11-09: first version (written after the design was chosen by the user on 2026-11-08: scope session, covers all three, 24h or 취소).

## Close-out
(filled after merge)
