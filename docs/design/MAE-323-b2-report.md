# MAE-323 bundle 2 final report

Linear: MAE-326 (parent MAE-323). Written 2026-11-08 from the recorded runs; drafted by Codex Sol from the planner's measured facts and corrected by the planner.

Bundle 2 (Linear MAE-326) rebuilt the code loop. Recorded results support the changes below, but AC-7 and AC-13 are unmet. Final-tree checks passed; the real CI aggregate and the release observations are pending. The CEO must decide whether to amend those criteria before approving release.

## What bundle 2 changed

PR 2a (#103) merged 2026-11-07 into `feat/harness-v1`, head `1f04c88`, carrying S1-S4 and S6. It added one `criteria_rev` acceptance digest across bind, review, ship and lease gate; `policy/roles.json` route/reviewer resolution excluding author/planner; `--kind plan` with V-1..V-6, two distinct reviewed heads per PR and one confirmation run; notification-only Stop; rule documents and three personal agents. Commit `a23f430` enrolled 49 historical cases and 127 expected blockers before the prompt changed.

PR 2b, `feat/mae-326-tests` from `1f04c88`, carries S5, S7, S8 and this report.

## Impact selection (AC-7)

S5's `plugins/maeng-harness/tests/impact.py run` builds coverage when `coverage` is installed, otherwise reports static-graph use. Default Python has requirements-dev pin 7.16.2. Empty selections, missing files, selector errors and pytest exits 5 or 4 trigger full-suite fallback, reported on stderr. Exit 1 remains failure. Every run prints `impact-summary:` with mode narrow/all/fallback, selected count, reason, executed tests and exit code.

Replay fixed two defects: the parent plan's “rc 5” from uncollectable `_review_cases.<locals>.R1_11_ReviewBundle` node ids, and duplicated file/node selections. One commit's 273 selected ids executed 995 tests.

`tools/testperf/impact_replay.py`, using `docs/design/MAE-323-b2-impact-cases.json`, replayed the 16 newest plugin-changing commits, including 5 from 2b, on commit worktrees with cached parent coverage. Results: 16 completed; 0 selector errors, 0 fallbacks, 0 failures; 5 all by rule, 11 narrow.

Executed counts: 805, 14, 799, 9, 791, 771, 236, 717, 24, 266, 232, 37, 699, 658, 630, 590. Median: 610; narrow-only: 236. The “median at most 100” bound is unmet. Observed reachability includes nearly every test through dispatcher imports and about 200 tests each through `apply_rounds` and `run_review`. This explains the broad selection. The bound came from expectation, not measurement. Earlier recordings had 7 exit-5 fallbacks and medians 601 and 611.5.

## Evidence integrity (AC-8)

Runner evidence records `tests_run` from pytest tallies or unittest `Ran N` minus skips; absent counts are “unavailable”, never a guessed 0. All-skipped runs count zero and record no evidence. `maeng-verify ran` declarations cannot satisfy runner requirements. Impact runs supply no ship evidence. Same-tree pass/fail records remain marked `flaky` in status; ship requires the later pass. `maeng-verify exec` no longer double-counts small output.

Cases: `test_evidence_integrity.py` (13), `test_impact.py` (17), `test_impact_replay.py` (6). Final tree: `python3 -m pytest -q -n 8` 805 passed; `HARNESS_TEST_PROCESS=1 python3 -m pytest -q -n 8` 802 passed, 3 skipped; `claude plugin validate` passed for both plugins; the four shared agent definitions are unchanged.

## Plugin suites and CI (AC-12)

S7's `lanes.json` enrolls 12 required suites: maeng-harness, harness and ten maeng-tools suites. Sampled mutation is manual and never launched.

`tools/testperf/plugin_checks.py --lane gate --isolated --require-complete` checks inventory parity and dependencies, uses temporary HOME, removes API keys and keeps PYTHONUSERBASE read-only. It reports ok/failed/empty/unavailable/skipped/timeout/missing and an aggregate; exit 1 unless aggregate ok. CI `plugin-suites` in `.github/workflows/harness.yml` uses fetch-depth 0 for historical-commit access, without continue-on-error.

Run 1: 11 ok; obsidian-workspace unavailable until python-docx/python-pptx installation. Run 2: maeng-harness collection error fixed that minute; obsidian-workspace's load-sensitive 1-second timeout failed, then passed alone with 83 tests. This test is outside scope. Final-tree isolated run: 12 of 12 suites ok, parity ok, aggregate ok (`docs/design/MAE-323-b2-plugin-checks-local.json`). The real CI aggregate is attached to the PR.

## Review preservation replay (AC-13)

S8's `tools/testperf/review_replay.py replay` validates enrollment against `a23f430` and rebuilds original scopes. PR 38 whole diffs were 19 MB; scoped diffs under 1 MB. Head-resolved plans covered 25 cases: by issue 5, single changed plan 9, largest changed plan 11. Another 24 cases, PRs 40-46, had Linear-only plans and criteria null.

New prompt: 46 of 49 run; 3 oversized PR 38 originals were blocked. Among 108 judged blockers: 18 critical/high, 18 medium/low, 72 absent; 32 new blockers. Verdicts: blocked 19, all plan-less; fail 17; pass 10.

Baseline `--prompt-from a23f430` validated schema/verdict consistency only: 41 ok. `docs/design/MAE-323-b2-review-replay-compare.json` compares 41 cases/97 expectations: baseline kept 9, new kept 11, both lost 83, new gained 5, new lost 3. Two losses matched only by line proximity under different titles. The third, `maeng-review store <file>` accepting local JSON as a pass receipt, became medium under V-2 as pre-existing. Five Claude baselines failed location rules; reruns were waived to save usage.

Matching uses same file within 20 lines or title Jaccard >= 0.5. Lost blockers = 0 is unmet. Comparison bounds prompt loss at 3 of 97. Reconstruction limits qualify interpretation: expectations date 2026-10-17 to 10-19, before MAE-237 and slim gates; Linear plans and runner evidence cannot be rebuilt.

## Context observation (AC-11, carried from 2a)

Observed before merge: 9,821 tokens, transcript-bound by nonce/definition hash. The read-only design-definition `omitClaudeMd` trial was supported and recorded. Released-plugin observation is pending.

## Remaining measurement gaps and post-release observation

Releases of maeng-harness/maeng-tools follow 2b merge under the parent procedure. Parent 5 observations remain pending: full-suite frequency, impact fallback, base movement and confirmation fixes.

## Decisions for the CEO

- AC-7: accept 610 and amend, or retain the bound and open a dispatcher-graph narrowing follow-up.
- AC-13: accept comparison evidence of 3 of 97 prompt losses and 83 shared losses under reconstruction limits and amend, or retain unmet status and withhold review-policy release.
- C-59: consider a later PR row supplying modified existing tests to reviewers without blocking.