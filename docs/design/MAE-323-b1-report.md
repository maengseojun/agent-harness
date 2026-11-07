# MAE-323 bundle 1 report: the numbers before the change

Linear: MAE-325 (parent MAE-323). Plan: `docs/design/MAE-323-b1-plan.md`. Date: 2026-11-07.

Every row has a number or `미측정` with the reason. The numbers come from `python3 tools/testperf/loopstats.py --until 2026-11-05 --days 7 --roles plugins/maeng-harness/policy/roles.json` (window 2026-10-29 to 2026-11-05 00:00 local, 1,020 transcript files, 0 unparsable), run on the final tree of this bundle. They are the "before" of the parent's scorecard; the "after" is measured on a window after the release of 0.4.13 / 0.3.21, when every subagent runs on CLI 2.1.317 or later (S2 finding 3).

## Baseline rows

| Row | Now | Baseline | Match within 5% | Cause of a difference |
|---|---|---|---|---|
| subagent active time at xhigh or above, % | 91.2 | 92 | yes | all 196 subagents of the window ran CLI 2.1.309; the 2.1.317 bucket is empty |
| full test runs (300+ passed) | 100 | 107 | no (-6.5%) | baseline window ended at the measurement time on 2026-11-05, this one at 00:00. Runs are keyed by tool-use id (review finding on PR #102); the first count keyed them by second and lost one |
| full test hours | 6.3 | 6.8 | no (-7.6%) | same |
| full test runs per branch | 3.8 | 4 | yes | |
| impact-test runs | 0 | 0 | yes | |
| time share after the first review, % | 63.7 | 68 | no (-6.3%) | same window cause; 21 branches |
| review pass ratio, % | 35 | 34 | yes | |
| PRs with 4 or more review runs | 11 | 12 | no (-8.3%) | file mtime window |
| PRs with a review run | 25 | 26 | yes | |
| Stop blocks | 99 | 99 (the parent's original 164 counted copies in resumed-session files; corrected 2026-11-06) | yes | counted once per uuid; 168 raw lines |
| record writes by the main thread | 765 | 621 | no (+23.2%) | the baseline's set of tools was not recorded; without `save_issue` and `update_frontmatter` the count is 621 |
| record writes per human turn | 1.4 | 1.3 | yes | |
| maeng-verify skip calls | 65 | 67 | yes | |
| implementer delegations | 13 | 13 | yes | |
| main-thread Edit/Write calls | 793 | 792 | yes | |
| delegation calls naming an effort | 1 | 1 | yes | |
| delegation calls | 163 | 156 | yes | |
| direct codex exec calls (no maeng-review) | 66 | 73 | no (-9.6%) | the baseline script was not kept |
| start context median of implementer, k tokens | 75.9 | 75 | yes | |
| start context median of general-purpose, k tokens | 77.7 | 80 | yes | |
| skills | 49 | 49 | yes | |
| skill name+description bytes | 20,651 | 20,693 | yes | one parser now (`lib/maeng/skillbytes.py`) |
| skills over 260 bytes | 38 | 38 | yes | |
| mutation detection | 미측정 | 9 of 20 sampled | - | needs a run of `tools/testperf/mutate.py` |

Reproduced within 5%: 17 of 23 rows. The 6 others print their cause.

## New metrics

| Metric | Value |
|---|---|
| median wall time per branch | 31 min (21 branches) |
| PRs with 3 or more review runs | 15 of 25 (60%) |
| requests above the grade ceiling | 0 of 0 checked: no request of the window used a typed agent with a grade row, so this is "no data", not zero |
| direct codex exec calls by purpose | image 4, other 8, probe 12, read-only analysis 9, review 9, write-capable work 24 |
| xhigh+ share by request count (not time) | 84.5% |

## Scorecard (G1-G5), before

| Cell | Value |
|---|---|
| G1 result quality | 미측정 (MAE-324 defines the measure) |
| G2 comprehension gates | interview and quiz passes 미측정 (state closed to agents); review runs 120, passes 42 |
| G3 efficiency | full test hours 6.3; time share after the first review 63.7%; median wall time per branch 31 min |
| G4 role performance | xhigh+ subagent time 91.2%; requests above ceiling: no data; implementer delegations 13; delegation calls naming an effort 1 of 163 |
| G5 improvability | the script runs in 4-14 s; baseline rows reproduced 17 of 23 |

## Effort observation (S1, 2026-11-06, CLI 2.1.317)

A subagent on a different model does not inherit the session's effort (Sonnet and Haiku ran at medium, Opus at its saved level); a per-call `effort` is honoured; a subagent on the session's model inherits the session's effort. Full table in the plan, "S1 results". AC-2 was then observed on 2026-11-07 through headless sessions that load the plugin from the working tree (`claude -p --plugin-dir plugins/maeng-tools`, CLI 2.1.314), not the released plugin: quick ran Haiku medium, standard Sonnet medium, deep (standard with a per-call effort) Sonnet high, design Opus high, with the session at medium effort for the design probe so the definition's own `effort` is what shows. All four match the table (plan, "AC-2 observation").

## What this bundle changed

1. `policy/roles.json`: one table for review kinds, grades, resources and routes (S3, S9).
2. Three personal agent definitions `quick`, `standard`, `design` with model, effort and tools (S3).
3. `maeng-review` resolves model and effort from the table and fails closed on a bad table; the Opus standby for a child-task PR and for Notion is high (S6).
4. Stop reports UNVERIFIED only for this session's own code change (S7).
5. The default ship check is `python3 -m pytest -q -n 8` (S4); a test keeps the skill name+description bytes at or under the base (S5).
6. `tools/testperf/loopstats.py` reproduces the baseline table and prints the scorecard cells (S2).
7. `aside-collect` passes `--model` and `--effort` from the two research routes; delegations name the exact range (S9).

## Not verified

- AC-2 was observed with `--plugin-dir` on CLI 2.1.314, not in the desktop app's 2.1.317 on the released plugin.
- Mutation detection was not re-run.
- The "after" window does not exist yet; nothing here claims an improvement.
