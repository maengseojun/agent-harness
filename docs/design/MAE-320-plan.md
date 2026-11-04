# MAE-320 Plan-lite: every decided Decisions use runs for certain

Linear: MAE-320. Date: 2026-11-04.

Goal: each use the user decided on runs because the harness makes it run, not because an agent remembers.
Deliverable: maeng-harness and maeng-tools releases with the wiring, the skill texts without the trial wording, and the weekly task updated.
Owns: `plugins/maeng-harness/bin/maeng-review`, `bin/maeng-verify`, `lib/maeng/handlers.py`, `lib/maeng/recordcheck.py`, `hooks/hooks.json`, `tests/`; skill texts of decisions, aside-research, aside-browser, work-records, obsidian-workspace, harness-run; both `plugin.json` files.

Assumptions:
- A-1 "확실하게" covers all decided uses, so records work needs a deny, not a reminder. This goes beyond the sealed recommendation (option B) on the user's word and reverses MAE-306 D-3 ("no hooks") for these checks only.
- A-2 A check is a run of the script, whatever Decisions answered. An API failure, an expired credit or `unknown` never stops work.
- A-3 One duplicate check covers creates for 30 minutes in that session, and one related check covers the session. A command form where the check may have been skipped does not count.
- A-4 Machine-made notes (`wiki/sessions`, `wiki/reviews`, `wiki/sources`, `raw`) need no duplicate check.
- A-5 The pre-flight table goes to the agent on stderr and not into the review bundle, so the reviewer is not anchored.
- A-6 The duplicate gate applies in the eta world too, as the user uses Decisions there. The bind gate applies wherever bind runs. `maeng-review` is personal only.

Decisions:
- D-1 Deny before the create instead of a reminder hook. Wrong if: agents run the check with empty candidates to pass it.
- D-2 Keep Decisions out of the reviewer's bundle. Wrong if: the pre-flight's `unmet` flags are never acted on.

- **AC-1** `maeng-review run` for code and parent runs `preflight.py ac` once before the reviewer, and a failed round runs `preflight.py triage`. Output goes to stderr, and a missing script or a failing run only warns. A code or parent review without `--plan` and `--evidence` is blocked.
- **AC-2** `maeng-review run --kind research` is blocked without `--claims <verify_claims result>`, and the result is embedded as evidence.
- **AC-3** A new Linear issue, Notion page or vault note is denied unless `records.py duplicate` ran in this session in the last 30 minutes. An update, an overwrite and a machine-made note are not denied.
- **AC-4** `maeng-verify bind` refuses until `records.py related` ran in this session.
- **AC-5** `MAENG_DECISIONS=off` turns off AC-1 to AC-4.
- **AC-6** Skill texts state the uses as standing steps with no trial date, `aside-browser` says Aside is the default for public and private pages, and the weekly task runs `records.py cleanup`.

Verification:
- `python3 -m pytest -q`
- `claude plugin validate plugins/maeng-tools`
- `claude plugin validate plugins/maeng-harness`

Close-out:
- revisions: plan 2 (A-6 corrected, AC-1 and A-3 after review round 1) / result 0
