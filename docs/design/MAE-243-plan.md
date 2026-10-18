# MAE-243 Spec/Plan: ship check the gate accepts, relayed approvals, review without a session bind

Linear: MAE-243 (follow-up of MAE-242). Date: 2026-10-18.

## Criteria

- **AC-1** A plain `python3 -m pytest -q` from the repo root runs exactly `plugins/maeng-harness/tests` (root `pytest.ini`) and makes the tree ship-verified without a binding.
- **AC-2** `.maeng/verify.json` tiers and `verification.md` name that command; `-n auto`, path operands and subdirectory runs are documented as partial.
- **AC-3** `review-and-ship.md` records the user decision: a `승인 #N` relayed by dots or another agent through `claude -p` counts as the user's approval; relay only an approval the user gave.
- **AC-4** `maeng-review run --plan <repo path>` reads the `AC-n` criteria and plan text from that file at `--head` when the session has no binding, so background and dots-run sessions can get a Codex review. A session binding still wins. The receipt's `criteria_rev` stays null (the head pins the plan), so an unbound `maeng-ship merge` matches it.

## Verification

- AC-1: `python3 -m pytest -q` from the repo root, then `maeng-verify status` shows `ship_verified: true`.
- AC-4: `tests/test_status.py::CommittedPlan`; live: `maeng-review run --kind code --pr 49 ... --plan docs/design/MAE-243-plan.md` reaches Codex.
- AC-2, AC-3: read the doc diff.
