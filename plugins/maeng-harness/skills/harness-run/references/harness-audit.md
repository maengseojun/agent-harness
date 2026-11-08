# Harness audit

Use this procedure to evaluate the harness against fixed tasks. Passing a test proves the tested behavior, not an improvement in model performance. Keep unknown effects marked `unverified` in `policy/inventory.json`.

## Procedure

1. **Run the measurement scripts.** From the repository root, check the paths below and use the matching usage form. All eight paths were checked in this checkout; usage comes from `loopstats.py --help` or the other scripts' module docstrings. Choose fixed inputs before running, preserve raw outputs, and record the revision, model, settings, dependencies and unavailable measurements. Some commands run suites or model calls: use disposable outputs and the task's existing authorization for any external calls.

   | Script | Usage after `python3` | Measurement |
   |---|---|---|
   | `tools/testperf/loopstats.py` | `tools/testperf/loopstats.py [-h] [--until UNTIL] [--days DAYS] [--roles ROLES] [--projects PROJECTS] [--state STATE]` | Observed review-run counts and time aggregates from local transcripts and state |
   | `tools/testperf/mutate.py` | `tools/testperf/mutate.py DB --lib LIBDIR --suite NAME=PLUGINDIR [--suite ...] --file lib/maeng/gates.py [--file ...] [--sample N] [--seed S] [--impact GITPLUGINDIR] [--jobs J] [--timeout-factor F]` | Compare test suites on the same mutants |
   | `tools/testperf/review_replay.py` | `tools/testperf/review_replay.py build --out FILE`; `tools/testperf/review_replay.py check --manifest FILE`; `tools/testperf/review_replay.py replay --manifest FILE --results FILE ...` | Replay pinned reviews and report lost critical/high blockers |
   | `tools/testperf/impact_replay.py` | `tools/testperf/impact_replay.py --manifest M --record [--cases-from M \| --commits 16] [--cache DIR] [--worktree DIR]`; `tools/testperf/impact_replay.py --manifest M --require-cases 16 --max-median 610` | Selection size, fallback, execution counts and failures on pinned commits |
   | `tools/testperf/periodic_checks.py` | `tools/testperf/periodic_checks.py [--root DIR] [--output periodic-results] [--seed mae232]` | Mutation sample on disposable repositories, with logs and completeness report |
   | `tools/testperf/plugin_checks.py` | `tools/testperf/plugin_checks.py --lane gate\|periodic [--isolated] [--require-complete] [--json OUT] [--lanes FILE] [--root DIR] [--print-pip] [--timeout SEC]` | Suite inventory parity and aggregate execution status |
   | `tools/testperf/subagent_context.py` | `tools/testperf/subagent_context.py record --plugin-dir plugins/maeng-tools --out E`; `tools/testperf/subagent_context.py --evidence E --omit-trial agent-y.jsonl`; `tools/testperf/subagent_context.py --evidence E --max-input-tokens 20000 --require-observed` | Bound first-request context usage; missing usage remains unknown |
   | `tools/testperf/deny_coverage.py` | `tools/testperf/deny_coverage.py PLUGINDIR DB` | Executed deny sites under coverage, not proof of complete safety |

2. **Score G1..G5.** Set task-specific criteria before the comparison. Use `unknown` without evidence; otherwise score 0 (misses the fixed criterion), 1 (partly meets it), or 2 (meets it). Attach evidence and uncertainty to each score; retain separate dimensions rather than hiding a failure in an average.

   | Goal | What measures it |
   |---|---|
   | G1: result quality | Fixed acceptance checks and independent artifact review against real examples (quality-layer findings, not scores) |
   | G2: intent and comprehension | Request-to-result coverage and differences; the user's explanation of structure, decisions and tradeoffs after the closing walkthrough and questions. An agent's prediction is not user evidence |
   | G3: efficiency | Loopstats time and review-run counts; paired impact-replay execution counts and fallbacks; subagent-context input usage. Record actual cost separately when available, otherwise unknown. Compare only while preserving G1/G2 |
   | G4: role performance | Independent review findings and missed blockers per assigned role on the same cases; review replay blocker retention, mutation detection and deny coverage for tested gates; unknown roles stay unknown |
   | G5: improvability | Reproducibility of a failure, whether a proposed change fixes it on paired cases without regressions, and whether inventory evidence can be refreshed with plugin and periodic checks |

   An effect is measured only as a with/without pair on a fixed task, with order swapped (with then without, and without then with). Never conclude an effect from one run. Keep the task, inputs, criteria, revision and model/settings fixed except for the component under study. Record noise: repeat variation, order effects, cache state, missing usage and timing uncertainty. Repeat noisy comparisons before drawing a conclusion; report inconclusive results as such. Aggregate transcripts and passing gate tests alone cannot establish causality.

3. **Update inventory statuses only with evidence.** Include every harness skill directory and bin file, `hooks/hooks.json`, and `policy/roles.json`. Keep each model assumption concrete. `helps` and `no-effect` require paired measurements and their limits; `safety` requires named tests of the enforced behavior and does not imply a measured model benefit. All statuses except `unverified` require an evidence reference. Revert stale or inconclusive claims to `unverified`.
4. **Propose changes.** For each proposal, name the affected component, failed criterion, paired evidence, expected gain, noise, regression checks and rollback. Separate proposed changes from adopted behavior. Do not silently change the criteria to obtain a pass.
5. **The user approves.** Present the evidence and concrete changes for the user's decision before adopting the audit proposals. Record approval or rejection and retain unresolved measurements as unknown.

## Proposal (not adopted): I-4

Status: proposal only, awaiting the user's decision.

Proposed rule: a change to a definition of pass (rules, gates, completion checks) needs the user's approval first. Present the old and proposed definitions, rationale, affected tasks and evidence before making the change. This section does not adopt that rule; the user decides whether it becomes policy.
