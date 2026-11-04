# MAE-317 Spec/Plan-lite: both Decisions engines at once

Linear: MAE-317. Date: 2026-11-04.

Goal: run the same questions on `gpt-6-luna` and `jev-1.14.0` and use the combined result (user: "정반합처럼").
Decisions: D-1 agreement is the answer; a disputed choice is `unknown` with reason `disagree`, so the existing re-check sends it to the researcher. A probability or score is the mean. One engine alone stands. D-2 `both` is the default during the trial, as the user asked; one engine stays selectable by `MAENG_DECISIONS_MODEL`. D-3 the `related` threshold is 0.25 for the mean, chosen on 18 cases, confirmed on 22 (recall 74/78, share 0.302).
Owns: `plugins/maeng-tools/skills/decisions/`, `plugin.json`, this file.

- **AC-1** With `both`, `decide` calls both engines at once, merges as D-1, each engine logs its own ledger line, callers do not change, and a missing BAZE key falls back to Luna.
- **AC-2** A disagreement on a false claim does not fail the eval's judged floor; an outage still does. The report shows engines apart.
- **AC-3** Live evals pass, and maeng-tools is 0.3.17 and validates.

Verification: `python3 -m unittest discover` in `skills/decisions/scripts`; `python3 -m pytest -q`; `claude plugin validate plugins/maeng-tools`; the results below.

Results, 2026-11-04. Claims: 154 of 156 false claims caught, no true claim flagged, 5 sent to the judge, p50 1,155 ms. Related, same 40 full-vault cases: both 151/159 at share 0.392, Luna alone 150/159 at 0.383; Korean 60/61 against 58/61, other 91/98 against 92/98. A request takes as long as Jev: p50 2.9 s against 0.44 s. The gain on these small sets is slight, so the Sunday report judges it per engine.
Known limit: when Jev gives no answer, Luna's probability meets a threshold set for the mean, so `related` selects less.

Close-out:
- revisions: plan 0 / result 0
