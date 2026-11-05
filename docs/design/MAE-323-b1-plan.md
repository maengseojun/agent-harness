# MAE-323 bundle 1 Spec/Plan: settings and measurement

Linear: MAE-325 (parent MAE-323). Parent plan: `docs/design/MAE-323-plan.md` (criteria approved by the user on 2026-11-06, "승인"). Date: 2026-11-06. Status: draft. This sub-plan adds no criterion beyond the parent's; its own choices are the `A-n` below and go to the user in the CEO brief.

Parent criteria are cited by number in words ("parent 12"), never in the criterion pattern, because the binding reads every such pattern in this file as a criterion of this plan.

Goal: one table decides the model and effort of every delegated agent and every review, the full suite runs in parallel by default, the measurement behind the baseline can be re-run from the repository, and a session that changed no code is not stopped for another session's change.

Deliverable: one PR from `feat/mae-323-loop-redesign`, releases of maeng-harness and maeng-tools, and a measurement report with the numbers before the change.

Decisions: D-1, D-4 and D-9 of the parent plan.

Assumptions:
- A-1 The three personal-flow agent definitions go in `plugins/maeng-tools/agents/` as `quick.md`, `standard.md` and `design.md`. The four shared definitions are not edited. Both plugins load in eta checkouts, so no location hides the new files from eta; nothing in eta calls them. Rejected: a new `plugins/maeng-harness/agents/` directory, which isolates no better.
- A-2 Documented precedence, from research on 2026-11-06 (documentation pages read through a summarizer; the per-call and different-model parts were then observed, see "S1 results"): `CLAUDE_CODE_EFFORT_LEVEL` beats a per-call `effort` (2.1.292 and later), which beats the definition's `effort`, which beats the session's effort; the session's effort reaches a subagent only when it runs on the main model. From 2.1.317 a subagent on a different model uses that model's saved or default effort. `CLAUDE_CODE_SUBAGENT_EFFORT` (2.1.316) applies "when nothing else names one"; its exact rank is not documented. S1 observes this before S3 relies on it.
- A-3 `deep` has no definition of its own: the planner starts `standard` with a per-call `effort: high` (parent P1-3).
- A-4 The size cap is the number the new test's own count gives on the base commit, recorded in the test. The parent's 20,693 bytes came from an earlier count; a recount on 2026-11-06 with a single-line parser gave 20,065 bytes for 49 skills.
- A-5 `python3 -m pytest -q -n 8` already counts as default-mode evidence: `evidence.py` lists `-n` and a number among the benign pytest flags. Parent 4 therefore needs a config and rule-text change and one test, not a gate change. S4 proves it with the test.
- A-6 Parent P1-6 (the integration review reads the planner's model) moves to bundle 2 with the reviewer selection rules it serves (parent 11). Bundle 1 only answers open question OQ-1 in S1.
- A-7 Bundle 1 keeps today's choice of reviewer per kind and backend. It moves the values into the table and raises the two Opus standby rows (child-task PR, Notion) from medium to high (parent D-1). The environment overrides `MAENG_REVIEW_BACKEND` and `MAENG_FABLE_EFFORT` stay.
- A-8 S6 and S7 edit mapped paths. They wait for the user's design passes: `overall` and `evidence` for S6, `overall` and `gates` for S7. S1 to S5 touch no mapped path.

Owns: `plugins/maeng-harness/policy/roles.json` (new), `plugins/maeng-tools/agents/{quick,standard,design}.md` (new), `plugins/maeng-harness/skills/harness-run/**`, `plugins/maeng-harness/bin/maeng-review` (tier lookup only), `plugins/maeng-harness/lib/maeng/handlers.py` (`compute_missing` only), `plugins/maeng-harness/tests/**`, `.maeng/verify.json`, `tools/testperf/**`, the two plugin manifests, `docs/design/MAE-323-*`.

Exclusions: all of bundles 2 and 3. In particular the Stop hook as a notice, the review criteria and round cap, the plan review kind, the reviewer selection rules, the impact-test wiring, CI, the five-field brief, the personal definitions as the default, and the `omitClaudeMd` trial.

must_haves:
- T1 A subagent started from `quick`, `standard` or `design` runs with the model and effort of its row in `roles.json`.
- T2 `maeng-review` takes model and effort for every review kind from `roles.json`, and stops with an error when the file is missing or invalid.
- T3 A session that changed no code since its last stop is not flagged UNVERIFIED when the tree changed under it.
- A1 `plugins/maeng-harness/policy/roles.json` - roles and grades with model, effort, range or ceiling, standby, `sourceUrl`, `verifiedAt`.
- A2 `tools/testperf/loopstats.py` - reproduces the baseline table and prints the scorecard cells.
- K1 Sub-tasks `Grade` column -> grade row in `roles.json` -> agent definition (model, effort) or per-call effort.

Requirements -> acceptance:
- **AC-1** The three personal-flow definitions exist with `model`, `effort` and `tools`, and agree with `roles.json`. The four shared definitions are unchanged from the base. Covers T1, K1 (parent 1).
- **AC-2** For each of the three definitions and for `deep`, a transcript of a subagent run shows the effort of the table. A mismatch is listed with its cause. Covers T1 (parent 1).
- **AC-3** The Plan template's Sub-tasks table has a `Grade` column, and `roles.json` resolves quick, standard, deep and design to model, effort, ceiling and standby. Covers K1 (parent 2).
- **AC-4** `maeng-review` resolves model and effort for code, parent, docs, research and notion from `roles.json`; the row of the plan kind exists; the script holds no model or effort constant for a tier; a missing or invalid file stops the review. Every row has `sourceUrl` and `verifiedAt`. A sync test fails when `roles.json`, an agent definition or a rule-document table disagree. Covers T2, A1 (parent 12).
- **AC-5** The default ship check is `python3 -m pytest -q -n 8` in `.maeng/verify.json` and the rule documents, and a passing run of exactly that command is ship evidence. (parent 4)
- **AC-6** A session with no code change of its own since its last stop gets no UNVERIFIED when another session changed code in the same checkout. A session that changed code is still flagged. Covers T3 (parent 7, the clause on sessions that changed no code).
- **AC-7** A test fails when the total bytes of skill names and descriptions exceed the recorded base value. (parent 8, second clause)
- **AC-8** `tools/testperf/loopstats.py` reproduces each row of the parent's baseline table for the 7 days before 2026-11-05 within 5%, or prints the difference with its cause. It also prints the median time per branch, the share of PRs with three or more reviews, the count of requests whose effort exceeded the grade ceiling, a classification of the direct `codex exec` calls, and the scorecard cells G1 to G5 with "미측정" for a cell without a value. Covers A2 (parent 10, 13, 20).

## Plan

Readiness: parent criteria approved. The part map is registered (evidence, gates). Design passes: none yet; S6 and S7 wait (A-8). Inputs present: the analysis scripts of the baseline are kept at `~/Documents/maeng-harness/refs/mae323/analysis/` (a1 to a17, `lib.py`).

Environment: branch `feat/mae-323-loop-redesign`, Python 3 with pytest-xdist 3.8.0, terminal CLI 2.1.314 (the desktop app's bundled CLI version is unknown, S1 reads it).

Routing: implement with `maeng-tools:implementer` (Sonnet) and a per-call effort from the Grade column until the new definitions are released; quick rows on Haiku. Review: `maeng-review run --kind code`, Sol xhigh. Limits: none known.

Sub-tasks:

| # | Do | Grade | Writes | Interfaces | Done | Fails-if | After |
|---|---|---|---|---|---|---|---|
| S1 | Observe: the running CLI version (terminal and desktop), whether `CLAUDE_CODE_EFFORT_LEVEL`, `CLAUDE_CODE_SUBAGENT_EFFORT` or a settings effort key is set, and the effective effort of a subagent in four cases: no effort named, definition effort, per-call effort, a subagent on a different model. Answer OQ-1 and OQ-4 | planner | section "S1 results" of this file; temporary probe definitions under `.claude/agents/`, removed after | produces: the transcript field that carries effort and model, and the observed precedence | the results table has an observed value and a transcript path for every case | a case is filled from documentation instead of a transcript; the probe definitions are left in the tree | - |
| S2 | Measurement script from the kept analysis scripts: window arguments, comparison with the baseline table, the new metrics, the scorecard cells | standard | `tools/testperf/loopstats.py`, `plugins/maeng-harness/tests/test_loopstats.py` | consumes: transcripts under `~/.claude/projects`, the harness state folder, the field names from S1 | `python3 tools/testperf/loopstats.py --until 2026-11-05 --days 7` prints every baseline row with `match` or a stated difference; the unit test passes on a fixture transcript | it prints a table for a window with no transcripts instead of an error; it drops files it cannot parse without counting them; expected values in the test come from running the script; the xhigh share is one number across CLI versions (it must be split at 2.1.317) | S1 |
| S3 | `roles.json`, the three definitions, the `Grade` column, "planner" in place of "Opus session", the sync test | standard | `plugins/maeng-harness/policy/roles.json`, `plugins/maeng-tools/agents/{quick,standard,design}.md`, `skills/harness-run/SKILL.md`, `skills/harness-run/references/{spec-plan,org-chart,review-and-ship}.md`, `plugins/maeng-harness/tests/test_roles.py` | produces for S6: `roles.json` with `roles.<kind>` = `{model, effort, range, standby: [{model, effort}], sourceUrl, verifiedAt}` and `grades.<grade>` = `{agent, model, effort, ceiling, standby, sourceUrl, verifiedAt}`; kinds: `code_child`, `code_small`, `parent`, `docs`, `research`, `notion`, `plan` | `python3 -m pytest -q plugins/maeng-harness/tests/test_roles.py` passes; `git diff --stat feat/harness-v1 -- plugins/maeng-tools/agents/architect.md plugins/maeng-tools/agents/design-reviewer.md plugins/maeng-tools/agents/implementer.md plugins/maeng-tools/agents/researcher.md` prints nothing | the sync test still passes after a definition's effort is changed away from the table; a grade named in the template has no row; a row lacks `sourceUrl` or `verifiedAt` and the test passes | S1 |
| S4 | Default ship check `-n 8` | quick | `.maeng/verify.json`, `skills/harness-run/references/verification.md`, `plugins/maeng-harness/tests/test_evidence.py` | - | `python3 -m pytest -q plugins/maeng-harness/tests/test_evidence.py plugins/maeng-harness/tests/test_docs_sync.py` passes, with a new test that a passing `python3 -m pytest -q -n 8` run satisfies the default ship check | the new test also accepts a narrowed run such as `-k name` or `-n auto`; a rule document still gives the default without `-n 8` | - |
| S5 | Size test for skill names and descriptions | quick | `plugins/maeng-harness/tests/test_skill_budget.py` | - | the test passes on the base; adding 1 KB to one description makes it fail (shown once, then reverted) | it counts fewer than 40 skills and passes; it reads only one plugin | - |
| S6 | `maeng-review` reads `roles.json`; tier constants removed; error on a missing or invalid file | deep | `plugins/maeng-harness/bin/maeng-review`, `plugins/maeng-harness/tests/test_review_roles.py` | consumes `roles.json` from S3 | `python3 -m pytest -q plugins/maeng-harness/tests/test_review_roles.py` passes: for every kind and both backends the pair equals the table, and the Opus standby for a child-task PR and for Notion is high | deleting a row still yields a model (a hidden default); a broken JSON file still starts a review; a kind's pair differs from today's except the two raised rows | S3, and the user's design passes for `overall` and `evidence` |
| S7 | No UNVERIFIED for a session without a code change of its own | deep | `plugins/maeng-harness/lib/maeng/handlers.py` (`compute_missing`), `plugins/maeng-harness/tests/test_stop_hooks.py` | - | two new tests pass: another session's change gives no UNVERIFIED; the session's own change does | a session that changed code through Bash instead of Edit is silenced; the own-change test passes without the fix | the user's design passes for `overall` and `gates` |
| S8 | Versions of both plugins, the before-numbers report, the full check | planner | the two `plugin.json` files, `docs/design/MAE-323-b1-report.md` | - | the commands of the Verification section pass on the final tree | a manifest version is unchanged; the report has a row without a number or "미측정" | S2 to S7 |

Steps:
1. S1, then S2 to S5 in order (they share no file; run one after another by default). Done when AC-1, AC-3, AC-5, AC-7 and AC-8 hold and AC-2 has its observed table.
2. After the user's design passes: S6, then S7. Done when AC-4 and AC-6 hold.
3. S8, review, CEO brief, merge quiz, release. Done when every criterion is met on the final tree.

Verification tier: gate-code. While working: `python3 plugins/maeng-harness/tests/impact.py run`. At the final tree: the full suite once.

Verification:
- AC-1 to AC-7: python3 -m pytest -q -n 8
- AC-2: `S1 results table filled from observed transcripts` declared with `maeng-verify ran --ok`.
- AC-8: `loopstats baseline comparison printed for the 2026-11-05 window` declared with `maeng-verify ran --ok`.
- Before merge, because an entry point changes: the full suite with `HARNESS_TEST_PROCESS=1`, and `claude plugin validate` for both plugins.

Failure / change handling: Failure handling in harness-run. A change to a criterion, the Owns or a `D-n` needs the user. If S1 shows that a definition's effort is not honoured, stop S3 and bring the result to the user: the routing design of the parent plan then needs a decision.

Review focus: does any review kind get a different model or effort than today besides the two raised rows; can `maeng-review` run on a hidden default; does the S7 fix silence a session that did change code; do the measurement numbers come from the data or from the script under test.

Revisions:
- R-1 plan order: parent P1-6 moved to bundle 2 with the reviewer selection rules (A-6).
- R-2 plan verification: S1 observed on 2026-11-06; the measurement must split the effort share by CLI version (S2).

Close-out: filled when the bundle closes.

## Progress

- S1 done 2026-11-06 (planner). See "S1 results".
- S2 done 2026-11-06 (implementer on Sonnet at medium, commit 0b06c2c; the planner added a time of day to `--until`). The planner re-ran the three Done commands: the unit test passes (4 tests), the empty window exits 2 with the error, and the baseline window prints every row with `match` or a stated difference.

## S2 findings

1. Stop blocks in the baseline week are 99, not 164. The first count read copies of the same event in resumed-session files: 168 raw lines, 99 events by uuid and by timestamp. An independent count by the planner gave the same two numbers. The parent plan and the design notes are corrected.
2. With the window ending at 2026-11-05 11:06, the time the baseline data was extracted, the rows for full test hours, time after the first review, review pass ratio and both PR counts fall within 5%. With the window ending at 00:00 they do not. The baseline scripts ran at different times of that day, so no single end time reproduces every row.
3. Every subagent in the baseline window ran CLI 2.1.309. The 2.1.317 bucket is empty there. The "before" numbers of this bundle must come from a window after the app moved to 2.1.317.
4. Rows that still differ, with the cause the script prints: record writes (765 against 621: the baseline's set of tools was not recorded), direct `codex exec` calls (66 to 70 against 73: the baseline script was not kept).
5. Not measured by the script: mutation detection (needs a `mutate.py` run), interview and quiz passes (the state is closed to agents), requests above the grade ceiling (needs `roles.json` from S3).
6. The xhigh share counts each subagent's active time under its most common effort (91.2%). By request count it is 84.5%. The old script `a15.py` reported active hours, so the time basis is kept.

## S1 results

Observed on 2026-11-06 in the desktop app, CLI 2.1.317 (`AI_AGENT=claude-code_2-1-317_agent` in the Bash environment), session model Fable at xhigh. Each row is one probe subagent that answered one word. The values are the `effort`, `perTurnEffort` and `params.output_config.effort` fields of its transcript, which agreed in every probe. Transcripts: `~/.claude/projects/-Users-maengseojun-Documents-Project-agent-harness/d594eac0-a644-4925-a39a-6d8f0063d4d3/subagents/agent-<id>.jsonl`.

| Case | Agent type | Effort named | Model that ran | Effort that ran | Probe id |
|---|---|---|---|---|---|
| different model, nothing named | `maeng-tools:researcher` | none | claude-haiku-5-5 | medium | a68e7e07c85179d4a |
| different model, nothing named | `maeng-tools:implementer` | none | claude-sonnet-5-5 | medium | a8173a6d53c32804e |
| per-call effort | `maeng-tools:implementer` | call: low | claude-sonnet-5-5 | low | a710cb3c47e5929c0 |
| different model with a saved level | `maeng-tools:architect` | none | claude-opus-5-5 | high | a925174f796b799c9 |
| same model as the session | `general-purpose` | none | claude-fable-5-1 | xhigh | ab1d23c2f2fd3b201 |

Settings and environment at the time: `~/.claude/settings.json` has `modelSettings.claude-opus-5-5.effortLevel: high`; no `CLAUDE_CODE_EFFORT_LEVEL`, `CLAUDE_CODE_SUBAGENT_EFFORT` or `CLAUDE_CODE_SUBAGENT_MODEL` is set.

What this shows:
1. On 2.1.317 a subagent on a different model does not inherit the session's effort. Sonnet and Haiku ran at medium, Opus at its saved level.
2. A per-call `effort` is honoured.
3. A subagent on the session's model inherits the session's effort (xhigh here).
4. The transcript carries model and effort per request, so the measurement can read them without OpenTelemetry.

Consequences for this bundle:
- The baseline "92% of subagent activity at xhigh or above" was measured on the 7 days before 2026-11-05. It may include requests from CLI versions before 2.1.317. S2 reports the share per CLI version where the transcript records one, so the platform's change is not counted as this patch's effect.
- The table's values for quick, standard and design equal what the platform already does today for the typed agents. What the definitions still add: values that do not depend on platform defaults or saved settings, a `tools` limit (start context, bundle 2), and a ceiling to measure against. The remaining xhigh inheritance is the same-model case: `general-purpose` and forks.

Not observed:
- A definition's own `effort` field (needs a new definition to be loaded, so it is checked after S3 in a fresh session).
- The rank of `CLAUDE_CODE_SUBAGENT_EFFORT`.
- The terminal CLI 2.1.314.
- Whether a hook process sees `AI_AGENT` (it was read in a Bash tool call). OQ-4 stays open until a hook reads it.
- OQ-1: the session's model is in the transcript (`message.model`); whether `maeng-review` can reach the transcript path of the calling session is not checked.
