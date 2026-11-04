# MAE-319 follow-up Plan-lite: the related eval's usage line

Linear: MAE-319. Date: 2026-11-04. This covers one follow-up PR. The default change itself is in `MAE-319-plan.md` and already landed.

Goal: the usage text of `related_eval.py run` names the threshold it really uses.
Owns: `plugins/maeng-tools/skills/decisions/scripts/related_eval.py`, `plugin.json`, the MAE-319 plan files.

- **AC-1** The usage line in `related_eval.py` reads `[--threshold 0.05]`, the value of `records.RELATED_THRESHOLD`.
- **AC-2** maeng-tools is 0.3.19, so the installed copy picks the line up, and it validates.

Verification: `grep -n 'threshold 0' plugins/maeng-tools/skills/decisions/scripts/related_eval.py`; `python3 -m pytest -q`; `claude plugin validate plugins/maeng-tools`.

Close-out:
- revisions: plan 0 / result 0
