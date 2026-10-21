# Spec/Plan: verify before review, external checks do not block (maeng-harness 0.4.2)

Source: review-rounds analysis 2026-10-21 (vault `wiki/answers/A-REVIEW-ROUNDS-20261021`). Since the 4-round cap, about 40% of code-review findings were "cannot verify from the bundle" rather than defects, and blocked runs used up rounds. The user chose fixes A and B on 2026-10-21.

- AC-1 (A): `maeng-review run` for code/parent refuses locally (verdict blocked, exit 2, no reviewer call, no stored review run) when the reviewed head is not ship-verified, and the message says which check is missing.
- AC-2 (B): the reviewer prompt makes `needs-external-check` a low finding that never by itself fails or blocks the verdict, and limits `blocked` to a bundle that lacks something required to judge an AC.
- AC-3: review-and-ship.md documents both rules for the coordinator.
- AC-4: maeng-harness version is 0.4.2.

## Verification

- AC-1: test_cli `test_unverified_head_is_blocked_before_reviewer_and_not_counted`.
- AC-2: test_r2 `test_prompt_states_the_slim_gate_design` (needle list).
- All: `python3 -m pytest -q`.
