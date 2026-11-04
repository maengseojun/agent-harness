# MAE-319 Spec/Plan-lite: Decisions defaults to Luna alone

Linear: MAE-319. Date: 2026-11-04.

Goal: stop paying the BAZE masking charge on Decisions. The school applies masking to every gateway request, about 5 credits whatever the model, and only its admin can change that, so a Jev request costs about 5.26 credits, not 0.26.
Decisions: D-1 `gpt-6-luna` alone is the default (the user's choice, over keeping both until Sunday). Wrong if: the school lifts the policy, or Sunday's report shows Luna alone missing what the two engines caught. D-2 Jev and `both` stay selectable, because the cost comes from a policy, not from the engine. D-3 the `related` threshold returns to 0.05, Luna's value from MAE-306 A-11.
Owns: `plugins/maeng-tools/skills/decisions/`, `plugin.json`, this file.

- **AC-1** With no model set, `decide` calls `gpt-6-luna` once and never calls BAZE. `MAENG_DECISIONS_MODEL=both` still calls both engines.
- **AC-2** The `related` default threshold is 0.05.
- **AC-3** `decisions/SKILL.md` states the default and why, and maeng-tools is 0.3.18 and validates.
- **AC-4** One live default call writes only a `gpt-6-luna` ledger line, and the BAZE masking count does not move.

Verification: `python3 -m unittest discover` in `skills/decisions/scripts`; `python3 -m pytest -q`; `claude plugin validate plugins/maeng-tools`; the live check of AC-4.

Close-out:
- revisions: plan 0 / result 1 (the `related_eval.py` usage line kept 0.25; fixed after merge)
