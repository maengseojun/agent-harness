# MAE-243 Spec/Plan: ship check the gate accepts, relayed approvals, review without a session bind

Linear: MAE-243 (follow-up of MAE-242). Date: 2026-10-18.

## Criteria

- **AC-1** A plain `python3 -m pytest -q` from the repo root runs exactly `plugins/maeng-harness/tests` (root `pytest.ini`) and makes the tree ship-verified without a binding.
- **AC-2** `.maeng/verify.json` tiers and `verification.md` name that command; `-n auto`, path operands and subdirectory runs are documented as partial.
- **AC-3** `review-and-ship.md` records the user decision: a `승인 #N` relayed by dots or another agent through `claude -p` counts as the user's approval; relay only an approval the user gave.
- **AC-4** `maeng-review run --plan <repo path>` reads the `AC-n` criteria and plan text from that file at `--head` when the session has no binding, so background and dots-run sessions can get a Codex review. A session binding still wins. The receipt's `criteria_rev` stays null (the head pins the plan), so an unbound `maeng-ship merge` matches it.

## Sub-tasks

Parent task: MAE-243 = PR #49. Owns: `pytest.ini`, `.maeng/verify.json`, `plugins/maeng-harness/bin/maeng-review`, `plugins/maeng-harness/tests/test_status.py`, `plugins/maeng-harness/skills/harness-run/references/{verification,review-and-ship}.md`, `docs/design/MAE-243-plan.md`. The coordinator re-ran every success command itself; a sub-agent's report is not evidence.

| ID | Do | Writes | Success (command, expected) | Failure (incl. vacuous pass) | After | Tests |
|---|---|---|---|---|---|---|
| S1 | Root ship check | `pytest.ini`, `.maeng/verify.json` | `python3 -m pytest -q` from the root: `311 passed`; `maeng-verify status`: `ship_verified: true` | root run collects skill scripts or errors; status still reports missing evidence | - | full suite |
| S2 | Docs name the ship check, the relayed approval, `--plan` | `verification.md`, `review-and-ship.md` | `git grep -n "pytest -q -n auto plugins" -- plugins .maeng`: no output (rc 1) | the old command remains anywhere the gate or a Plan reads | S1 | - |
| S3 | `maeng-review --plan` reads AC-n at `--head` when unbound | `bin/maeng-review`, `tests/test_status.py` | `python3 -m pytest -q plugins/maeng-harness/tests/test_status.py -k CommittedPlan`: `5 passed` | mutants `if a.plan:` (binding ignored) and `if False and a.plan:` (no fallback) must each fail one test; both did (2026-10-18) | - | `CommittedPlan::*` |
| S4 | Integration and verification | - | `HARNESS_TEST_PROCESS=1 python3 -m pytest -q`: `311 passed`; `git diff --name-only 709da15..HEAD` lists only Owns paths; PR #49 open | any failure, a path outside Owns, or no PR | S1-S3 | full suite, process mode |

Expected values come from this Spec (the AC-n ids written in the test plan file), not from running the code under test.

## Verification

- AC-1: `python3 -m pytest -q` from the repo root, then `maeng-verify status` shows `ship_verified: true`.
- AC-4: `tests/test_status.py::CommittedPlan`; live: `maeng-review run --kind code --pr 49 ... --plan docs/design/MAE-243-plan.md` reaches Codex.
- AC-2, AC-3: read the doc diff.
