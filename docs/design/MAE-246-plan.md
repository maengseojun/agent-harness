# MAE-246 Spec/Plan: verify_state must not say pass on an UNVERIFIED tree

Linear: MAE-246. Date: 2026-10-18. Single task (under the split threshold).

## Finding

The live status file `s-f6907c13.json` (the ETA-1042 session) contradicts itself:

- `state` is `blocked`, with the blocker "UNVERIFIED: ... no passing test-runner evidence for this tree".
- `verify_state` is `pass`.

The cause is `status.verify_state`: it counted any passing run on the tree as a pass, including filtered runs (test paths, `-k`) that the gate does not accept.

## Criteria

- **AC-1** `verify_state` reports:
  - `pass` only when a run passed on the tree and the Stop hook found no UNVERIFIED obligation.
  - `fail` when the Stop hook found an UNVERIFIED obligation and a run on the tree failed.
  - `not_run` when the Stop hook found an UNVERIFIED obligation and no run failed. This includes filtered passes.
  - `none` when there is no code change to verify.
- **AC-2** `StatusUnits::test_verify_state` covers a passing run on an UNVERIFIED tree (expected `not_run`). The mutant `if False:` in place of `if unverified:` must fail the test; it did on 2026-10-18.

## Done

- `python3 -m pytest -q plugins/maeng-harness/tests/test_status.py -k verify_state` reports 1 passed.
- Root `python3 -m pytest -q` passes.
- The Codex review with `--plan docs/design/MAE-246-plan.md` passes.
