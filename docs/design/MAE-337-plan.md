# MAE-337 Plan: an approval typed after a seal opens `reveal`

## Goal
After `maeng-interview seal`, the user's next own message opens `reveal`, including a `승인 #N` message. Today `capture` drops `승인 #N` for both an interview answer and a seal choice, so `reveal` refuses with "the user has not answered since the seal" until a second message.

## Deliverable
A one-condition change in `plugins/maeng-harness/lib/maeng/interview.py` `capture`, a regression test in `plugins/maeng-harness/tests/test_interview.py` and a maeng-harness version bump.

## Assumptions
- An approval stays out of an interview answer (`awaiting: answer`); it is not an explanation of the work.
- Any own message of the user after a seal is their choice; the seal only has to prove the recommendation was fixed before that message. The app-note and relay filters (`users_text`) stay as they are.

## Acceptance criteria
- AC-1: After a seal, `승인 #116` (plain, and behind the desktop app's note) records the choice and `reveal` returns the sealed bytes.
- AC-2: While an interview awaits an answer, `승인 #N` is still not recorded as the answer.
- AC-3: The full maeng-harness suite passes on the final tree.

## Steps
1. Apply the `receipts.APPROVE` exclusion only when `awaiting == "answer"` (AC-1, AC-2).
2. Add `test_reveal_opens_on_an_approval_typed_after_the_seal`; confirm it fails before step 1 (AC-1).
3. Bump maeng-harness.

## Verification
- AC-1: `python3 -m pytest -q plugins/maeng-harness/tests/test_interview.py -k approval`
- AC-2: the existing `test_an_approval_is_not_an_answer_and_a_second_message_extends_the_first`
- AC-3: `python3 -m pytest -q`

## Revisions
- 2026-11-09: first version.

## Close-out
(filled after merge)
