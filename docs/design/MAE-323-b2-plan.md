<!-- DRAFT written by Codex Sol high on 2026-11-07 from the parent plan, the bundle 1 plan, candidates C-1..C-58 and the verified code-reading source note; the planner found it matches the parent's bundle 2 allocation (P6, P2-2~5, P3, P5-2~4, P4b, P9). Not approved. Pending user choices: one PR or two (2a structure core S1-S4+S6, 2b test structure S5, S7, S8), D-10, D-11; recommendations sealed 6496fb3d2f9b, 449310dbaf9f, 5176adee2579. -->

# MAE-323 bundle 2 Spec/Plan: structure

Linear: MAE-326 (parent MAE-323). Parent plan: `docs/design/MAE-323-plan.md` (criteria approved by the user on 2026-11-06, "승인"). Predecessor: `docs/design/MAE-323-b1-plan.md`. Date: 2026-11-07. Status: current (criteria approved 2026-11-07). This document proposes implementation choices as `A-n`; the two additional gate candidates remain unresolved user decisions. Drafting is read-only: no repository file is written.

Parent criteria are cited by number in words ("parent 16"), never in the criterion pattern, because binding must not mistake a parent reference for a criterion of this plan.

Goal: Stop reports missing work without blocking, working checks select affected tests, and independent review converges within two reviewed heads plus one confirmation run while preserving verification and merge gates.

Deliverable: two PRs (D-12, user's choice 2026-11-07 "PR 둘로"): PR 2a, structure core, rows S1, S2, S3, S4 and S6 with separate commits per row; PR 2b, test structure, rows S5, S7 and S8, merged after 2a. Each PR carries the acceptance checks of its rows; 2b carries the final report (impact-selection results, review-preservation results, context observations, remaining measurement gaps) and the releases of the changed plugins. Updated harness-run rules land in 2a.

Decisions: D-2, D-3, D-5, D-6, D-7 and D-8 of the parent plan. The resource-route enforcement also follows bundle 1 R-3 and the user's instruction of 2026-11-07.

The following decisions were pending at the first draft; all three are now chosen (see the rows). The recommendations were sealed before each choice.

| Decision | Source | 가 | 나 |
|---|---|---|---|
| D-10 Evidence-store protection | C-29, **보고**; original reopened: `oh-my-hermes src/plugin_bundle/omh/evidence_store_guard.py:1-84`. **Chosen (2026-11-07): 가, the existing boundary; sealed recommendation 449310dbaf9f was the same** | **Existing store boundary:** retain the current protection of `MAENG_HOME` and `MAENG_CACHE_DIR`; add no protected location | **Extended artifact boundary:** also protect explicitly named evidence locations outside those roots against Write/Edit; specify those locations and exceptions before implementation. Shell writes remain outside this guard |
| D-12 PR structure of bundle 2 | parent "묶음(PR 3개)"; bundle 1 took two review rounds plus the user's approval at 94 files | ~~One PR~~ | **Chosen (2026-11-07): two PRs.** 2a structure core (S1, S2, S3, S4, S6) merged first, then 2b test structure (S5, S7, S8); each PR carries the acceptance checks of its rows, 2b carries the final report and the releases, and the parent's AC numbering stays. Sealed recommendation 6496fb3d2f9b was also two PRs |
| D-11 Human approval at the plan boundary | C-30, **보고**; original reopened: `oh-my-hermes src/plugin_bundle/omh/plan_stage_gate.py:14-20`. **Chosen (2026-11-07): 가, notification-only; sealed recommendation 5176adee2579 was the same** | **Plan-review notice:** keep parent P9's notification-only behavior | **Host approval request:** investigate a host-native approval request before implementation without an accepted plan. This changes the parent's notification-only boundary and requires an explicit parent revision and a supported-host probe |

The current `gates.check_edit` already protects harness state and cache directories. D-10 concerns an extension of that boundary. The upstream account behind D-11 describes Hermes behavior; it does not establish that Claude Code supports the same approval mechanism.

Assumptions:

- A-1 Bundle 1's role table, personal definitions and tier lookup are prerequisites. Its S6 and S7 are not treated as complete from their presence in the plan. Before implementation, inspect their actual changes and results; preserve the session-own-change fix when changing Stop.
- A-2 One helper in `evidence.py` computes `criteria_rev`: SHA-256 of the complete acceptance section, including criterion bodies and their continuation lines, with line endings normalized. Verification, Revisions, Progress and Close-out are outside that section. An absent or ambiguous section yields an unknown revision, never a digest of an empty string. Parsing supports this repository's labeled section and the template's headed form, ignores headings inside fences, and does not collect arbitrary mentions of criterion IDs elsewhere.
- A-3 Keep `files_reviewed` as the receipt's coverage list. Add explicit full/delta coverage metadata, previous reviewed head and review mode. A legacy receipt without that metadata cannot justify narrowing. Bind, review, ship and the lease-push gate use the same criteria digest; an old timestamp is not silently converted into one.
- A-4 Count distinct code-review heads with completed pass/fail results per repository and PR. Same-head reruns and scope splits share one round; blocked results use none. A base or criteria change forces full scope but does not reset the two-head budget. Confirmation is a separately recorded, once-per-PR dispatch after two rounds; an incomplete local preflight does not consume it. An unavailable or malformed confirmation never grants pass. Confirmation is possible only on the same base and criteria digest as the round-two head (AC-5); a change there ends the PR's review budget.
- A-5 Reviewer identity comes from recorded execution identity, supplemented by explicit model-ID inputs when needed. Add `--author-model` and `--planner-model`; retain family flags only where they resolve unambiguously. For plan and parent reviews, missing planner identity must not silently waive planner exclusion. Resource selection for review follows the selected role candidate: GPT Pro for Codex candidates and Claude Code for Claude candidates.
- A-6 Extend the personal SubagentStop selector to the exact `maeng-tools:quick`, `maeng-tools:standard` and `maeng-tools:design` types. Preserve the existing implementer behavior, the required `Verification:` and `Unfinished:` sections, the one-retry escape and eta isolation. `Status: done | partial | blocked` is the new definitions' report convention; it does not become an additional Stop-block condition.
- A-7 Stop stores a pending notice and delivers it through the next `UserPromptSubmit` `additionalContext`. First test whether Stop's existing `context_out` shape itself reaches the model. A user-only `systemMessage` is insufficient evidence of delivery. Missing work remains recorded after a notice.
- A-8 A finished turn uses the existing outcome states. Missing verification alone does not leave it `running` or force `blocked`; `verify_state` still reports the verification gap. With no outcome marker, use `idle`, followed by `ended` at SessionEnd. This changes no dots status schema.
- A-9 Route enforcement is personal-world work. Existing eta behavior, the four shared agent definitions, Decisions question semantics and research fallback decisions remain unchanged. The claim and duplicate wrappers pass the resolved table model explicitly, so an ambient Decisions model setting cannot silently replace it.
- A-10 The standard-agent context check measures the first actual request in a fresh session that loads the candidate tree with `--plugin-dir` before merge, and again on the released plugin after release, including cached input where the transcript distinguishes it. Missing usage is unknown, not zero. The read-only `omitClaudeMd` trial uses `design`; unsupported behavior is reported rather than inferred from frontmatter.
- A-11 CI uses an explicit test-suite inventory checked against discovered plugin tests. Each suite runs in its own process and working directory. CI remains informational to shipping; a failed or unexpectedly skipped suite still makes its aggregate result fail.
- A-12 Parent 5 is a post-release observation. The bundle report records the observation window and separates impact fallback, base movement and post-round-two high-finding fixes. It does not claim a median of two from fixture tests or before sufficient branch data exists.

Owns: the exact files in the Sub-tasks table. Runtime changes are limited to the named hook, verification, receipt, review and route paths. The two Decisions wrappers and the new routing helper are the bounded extension needed for the user's route-enforcement instruction.

Exclusions: bundle 3, MAE-324's quality layer, automatic task/model routing, new PR-creation gates, mandatory plan-review receipts, required CI checks in `maeng-ship`, repair-limit changes, automatic issue creation for review notes, and either unresolved gate extension above.

**묶음 밖 — candidate extensions:**

- C-3: general completion deny-list.
- C-5, C-6, C-7: a separate pre-existing-failure witness protocol, uncovered-file report and gate-weakening detector. The parent's existing-defect severity rule still applies.
- C-8, remaining portion: base-versus-head criteria audit and PR disclosure. This bundle takes the criteria-identity requirement, not that additional audit.
- C-9, C-10, C-11: additional end checklist, statistical flaky-clearance rule and broad real-HOME snapshot mechanism. The parent's flaky recording and key-free test requirements remain in scope.
- C-12 through C-19: additional finding taxonomies, report headers, clean/unjudged lists, backend-specific parsing and sideways searches. Parent V-1 through V-6 remain fully in scope.
- C-20: the upstream third-round permission rule; retain the user's already-decided D-8 confirmation instead.
- C-21 through C-26: additional grade rationale, incompatible no-fallback policy, extra brief requirements, worker/git projection, model-comparison experiment and bundle-1 budget refinements.
- C-27, C-28: broader warning and goal-loop machinery.
- C-29, C-30: pending D-10 and D-11; neither extension is assigned to an implementation row.
- C-31 through C-34: approval-relay records, a new repeated-repair rule, an additional decision-completeness blocker and the complete upstream reviewer checklist. Plan review retains exactly the parent's three blocking categories.
- C-36 through C-42: broader test-value policy, measurement-panel changes, unexpected-stop detection, orchestration verification machinery, lifecycle recovery, a general differential harness and deletion approvals.
- C-43 through C-49: skill generation, section-carving, new byte budgets, trigger tests, maintenance policy and skill-use measurement.
- C-50: reading policy from the base branch. This is a separate trust-boundary change.
- C-52 through C-58: automatic follow-up tasks, an additional convergence mechanism, a spawn-time router, a general route-observation ledger, Decisions outcome refactoring, a new detector's 50-PR calibration and skill-trigger cases.

These are deferred extensions, not removals of overlapping requirements already approved in the parent.

must_haves:

- T1 Stop never blocks for UNVERIFIED or UNRECORDED. Review entry and merge still require final-tree ship verification.
- T2 Working checks select affected tests and recover safely from unusable selections; they cannot produce ship evidence.
- T3 Code review uses parent V-1 through V-6, two reviewed heads and one bounded confirmation.
- T4 Plan review has its own kind, role selection and criteria-bound receipt. Missing plan review produces notices only.
- T5 Existing claim-check, review and duplicate-check paths consume their routes at execution.
- T6 Personal definitions use the five-field brief and checked report sections.
- A1 Updated review schema and receipts distinguish criteria identity, review coverage and confirmation.
- A2 Replay tools and reports expose incomplete inputs and lost blockers.
- A3 An informational CI aggregate covers every discovered plugin test suite; mutation sampling runs periodically.
- K1 Acceptance text -> one criteria digest -> binding, review receipt, ship and lease-push gate.
- K2 `roles.json` -> route/role resolver -> actual invocation arguments.
- K3 Prior review -> validated scope -> round-two or confirmation input -> exact-head receipt.

Requirements -> acceptance:

- **AC-1** Binding a file Plan and reviewing the same committed acceptance text produce the same non-null digest. Editing criterion wording while preserving its number changes the digest; editing Progress alone does not. Ship and the lease-push gate reject a mismatched criteria revision. Owner: S1. Check: the Verification command. Fails if an empty acceptance section receives a usable revision, null equals null for narrowing, or the tests merely compare two calls to the same digest helper. Covers K1 (parent 16).
- **AC-2** Claim check, review and duplicate check resolve their route before invocation. Default claim and duplicate requests explicitly use Luna through the listed OpenAI resource. Reviews follow role candidate order, exclude the actual author, additionally exclude the planner for plan/parent, and advance only on exclusions or availability failure. Exhaustion returns blocked. Owner: S2. Check: the Verification command. Fails if any route is absent yet the invocation starts, a hidden constant supplies a model, or mocks pass without asserting the launched arguments and exclusion cases. Covers T5, K2 (parent 11; bundle 1 R-3).
- **AC-3** `--kind plan` selects Astra high when eligible and stores a pass receipt tied to task identity and a non-null criteria digest, independent of code-tree movement. Its only blocking categories are an uncheckable criterion, an unexecutable step and conflict with cited code. Missing receipt on a large task causes one-line notices after PR creation and at code-review entry; it blocks neither review nor merge. Boundaries include one/two Sub-task rows and absent/present children. Owner: S3 for review, S4 for notices. Check: the Verification command. Fails if an empty plan passes, a code receipt satisfies plan review, changed criterion wording leaves the receipt current, or notice tests never exercise a large task. Covers T4 (parent 9, 11).
- **AC-4** Blocking findings mean an unmet criterion, operational breakage, or data/secret loss. Medium and low alone do not cause fail. Existing defects and findings without a reachable call/input are low unless they establish an unmet criterion. Code findings require file and positive line, or an explicit missing-file/function exception naming the affected criterion. Low findings are capped at five plus an omitted count; no findings is valid. Owner: S3. Check: the Verification command. Fails if pass is accepted with an unresolved blocker, an unmet criterion is downgraded as pre-existing, a missing location lacks its exception, or an empty/refused response counts as a clean review. Covers T3 (parent 16).
- **AC-5** Round two receives previous findings. Narrowing requires the same base, the same non-null criteria digest, ancestry of the previous head and actual prior file coverage. Previously excluded, delegated or unreviewed files receive full review; unavailable metadata restores full scope. The default cap is two distinct reviewed heads. One confirmation receives only remaining critical/high findings and their fixing diff, raises no new findings, and can issue a pass receipt usable by ship for that head. Confirmation requires the same base and the same non-null criteria digest as the round-two head; otherwise `maeng-review` refuses it as `blocked` without consuming it, the PR has no review budget left, and the planner goes to the user's `승인 #N` (parent A-7) or opens a new PR. Owner: S3. Check: the Verification command. Fails if same-head/split/blocked runs spend rounds, metadata gaps narrow scope, a second confirmation dispatches, a confirmation passes after the base or the criteria changed since round two, or a confirmation test checks only printed pass without testing receipt eligibility. Covers T3, K3 (parent 16).
- **AC-6** Stop returns no block for missing verification or records, including errors and timeout paths. A session with no own code change receives no verification notice. Missing work survives notice delivery; the next prompt receives model context. Finished runs do not remain `running`. Record omission creates no new refusal and its PR notice occurs once per repository/PR. Owner: S4. Check: the Verification command. Fails if tests only set `stop_hook_active=true`, inspect only `systemMessage`, clear the obligation after notice, or omit the own-Bash-change and other-session cases. Covers T1 (parent 7, 15).
- **AC-7** Working checks use `impact.py run` with the normal Python environment. Missing coverage/map, bad node IDs, empty selection and selector rc 5 trigger a reported full fallback. Genuine test failure remains failure. A pinned replay of 16 recent code commits has no selection errors and selects a median of at most 100 tests. Owner: S5. Check: the Verification command. Fails if fewer than 16 cases execute, fallback is counted as successful narrow selection, missing targets are silently dropped, or an empty selection exits green without running the fallback. Covers T2 (parent 3).
- **AC-8** Runner evidence outranks declarations and agent reports. Zero executed tests cannot pass; unknown count is labeled unavailable. A declaration cannot satisfy a runner requirement, and impact output cannot satisfy the full-suite requirement. Same-tree success/failure is retained as flaky evidence. Owner: S5. Check: the Verification command. Fails if rc 0 with zero/all-skipped tests records passing evidence, an unknown count becomes zero, or a test accepts a declaration without exercising the runner boundary. Covers T1, T2 (parent 6).
- **AC-9** Harness-run contains stage entry/exit criteria with code/document enforcement, evidence limits, negative-path requirements, failure reproduction before bug fixes, and informational base-code tests. The plan-review instructions preserve discarded alternatives and a criterion -> task -> verification table. Personal delegation uses TASK, DELIVERABLE, SCOPE, VERIFY and STOP WHEN. Owner: S6. Check: the Verification command. Fails if a required stage/field is absent or the check fixes English sentences rather than the structural fields and executable examples. Covers T6 (parent 6).
- **AC-10** Each new personal definition uses the report convention, and SubagentStop checks its Verification/Unfinished sections in the personal world. The old implementer behavior and eta behavior remain covered. Owner: S6. Check: the Verification command. Fails if only `implementer` is tested, every new type is allowed without both sections, or the hook claims to verify the truth of a report. Covers T6.
- **AC-11** Before merge, a fresh headless session that loads the candidate tree (`claude -p --plugin-dir plugins/maeng-tools`, the way bundle 1 observed AC-2) shows a standard-agent request with observed starting input of at most 20,000 tokens. After release, the same observation on the released plugin goes into the bundle report as verification, not as the acceptance gate. The report separately records the read-only `omitClaudeMd` trial and its supported/unsupported outcome. Owner: S6. Check: the Verification command. Fails if the transcript is missing, belongs to another definition/version, omits cached input, or a zero/default estimate substitutes for observation. Covers T6 (parent 8).
- **AC-12** CI runs every plugin test suite identified by the checked inventory without personal keys or writes to the real user home, and emits one informational aggregate. Required suite failure, cancellation, empty execution or unexpected skip prevents aggregate success. Mutation sampling belongs to the periodic lane. Owner: S7. Check: the Verification command. Fails if only the root pytest testpath runs, an unlisted suite is ignored, or `continue-on-error` turns a failed suite into a green aggregate. Covers A3 (parent 19).
- **AC-13** Historical review bundles are reconstructed from pinned inputs and run with the new prompt. Every expected patch-introduced critical/high finding remains blocking: lost blockers = 0. The manifest preserves original outputs and independently enrolled expectations. Owner: S8. Check: the Verification command. Fails if the corpus or blocker denominator is empty, missing bundles are omitted, outputs are altered after enrollment, or expected findings are generated from the new reviewer result. Covers A2 (parent 16).

## Plan

Readiness: parent criteria approved. D-12 (two PRs), D-10 (existing boundary) and D-11 (notification-only) chosen by the user on 2026-11-07. The sub-plan's criteria AC-1 to AC-13 and assumptions A-1 to A-12 were approved by the user on 2026-11-07 ("승인"). PR 2a starts with S1. Reconcile bundle 1 S6/S7 before coding. Mapped changes wait for the user's applicable `overall`, `evidence` and `gates` design passes. D-10/D-11 are unassigned extensions; selecting an extension first requires a concrete scope amendment. Historical replay availability remains parent OQ-2 and must be resolved before changing the review prompt.

Environment: repository `agent-harness`, branch reported as `feat/mae-323-loop-redesign`. The repository pins pytest 7.4.4, pytest-xdist 3.8.0 and coverage 7.16.2; installed versions were not tested. Root `pytest.ini` collects only `plugins/maeng-harness/tests`, so a root pytest run alone does not cover the other plugin suites.

Read inventory: both hook files; `handlers.py`, `gates.py`, `evidence.py`, `receipts.py`, `schema.py`, `recordcheck.py` and `status.py`; the three requested CLIs; `roles.json`; the three personal definitions; the relevant harness-run documents; Decisions client and claim/record wrappers; test configuration and the existing CI workflow. Existing test files assigned writes below were read in full.

Files listed under `plugins/maeng-harness/tests/`:

```text
__init__.py
conftest.py
helpers.py
impact.py
test_boundary.py
test_cli.py
test_decisions_wiring.py
test_docs_sync.py
test_evidence.py
test_g1.py
test_g2_g3.py
test_guard.py
test_interview.py
test_loopstats.py
test_mae233.py
test_merge.py
test_plugin.py
test_quiz.py
test_r1.py
test_r2.py
test_r3.py
test_r4.py
test_r5.py
test_r7.py
test_r8.py
test_r9.py
test_roles.py
test_skill_budget.py
test_status.py
test_stop_hooks.py
test_tree_index.py
```

Routing: implement using the Grade rows from released bundle 1; `deep` uses `standard` with explicit high effort. The planner integrates and judges acceptance. Review follows the resolved role, including author/planner exclusions. Failure does not raise effort or select another model. Limits: no live provider availability checked.

Sub-tasks:

All paths below are repository-relative. New files are marked `(new)`. Source-row titles refer only to the supplied source document's **"그대로 쓸 수 있는 것"** table; the cited original ranges used below were reopened.

| # | Do | Grade | Writes | Interfaces | Done | Fails-if | After |
|---|---|---|---|---|---|---|---|
| S1 | Implement acceptance-section parsing and one criteria digest across binding, committed Plans, receipt lookup and merge authorization. Define plan-receipt and review-coverage fields without treating legacy unknowns as matches. Source: C-8 (**보고**, acceptance identity only); "Fence-aware section boundaries", `gstack test/helpers/skill-fixture.ts:154-173` | deep | `plugins/maeng-harness/lib/maeng/evidence.py`; `plugins/maeng-harness/lib/maeng/receipts.py`; `plugins/maeng-harness/lib/maeng/gates.py`; `plugins/maeng-harness/bin/maeng-verify`; `plugins/maeng-harness/bin/maeng-review`; `plugins/maeng-harness/bin/maeng-ship`; `plugins/maeng-harness/schemas/verdict.schema.json`; `plugins/maeng-harness/tests/test_criteria_rev.py` (new) | produces: `criteria_rev`, acceptance extraction, separate plan-receipt identity, full/delta coverage contract; consumes: local or committed Plan bytes | `python3 -m pytest -q plugins/maeng-harness/tests/test_criteria_rev.py` passes fixed text-pair fixtures and review/ship/lease integration cases for AC-1 | wording-only criterion changes match; Progress invalidates the digest; fenced examples become criteria; empty/null revision authorizes reuse; expected hashes come from the production helper | verified bundle 1 result; applicable design passes |
| S2 | Enforce the three existing routes and the parent's reviewer candidate rules. Resolve actual author/planner identities; pass the claim/duplicate model explicitly. Preserve existing opt-out and eta behavior. Source: "Policy precedence with provenance", `oh-my-hermes src/routing/recommend.py:5867-5875`; bundle 1 R-3 | deep | `plugins/maeng-harness/lib/maeng/routing.py` (new); `plugins/maeng-harness/policy/roles.json`; `plugins/maeng-harness/bin/maeng-review`; `plugins/maeng-tools/skills/decisions/scripts/verify_claims.py`; `plugins/maeng-tools/skills/decisions/scripts/records.py`; `plugins/maeng-harness/tests/test_roles.py`; `plugins/maeng-harness/tests/test_cli.py`; `plugins/maeng-harness/tests/test_route_enforcement.py` (new) | consumes: bundle 1 roles/resources/routes; produces: selected candidate, supplying policy row, explicit invocation arguments and fallback reason; supports source checkout and versioned plugin installation | `python3 -m pytest -q plugins/maeng-harness/tests/test_route_enforcement.py plugins/maeng-harness/tests/test_roles.py` passes AC-2, including Fable planner -> Astra parent review and Sol author -> Opus code review | missing/invalid policy launches a provider; an availability error and review fail are treated alike; family identity silently proves exact-model exclusion; installed-layout discovery falls back to constants | S1 |
| S3 | Add plan review, V-1 through V-6, previous findings, guarded round-two scope, distinct-head counting and one confirmation dispatch. Validate verdict/finding consistency before issuing receipts. Source: C-51 (**direct**), `gstack docs/ship-policy.md:1580-1612`; "Later-pass ancestry", `gstack bin/gstack-review-scope:159-168`; "Derive status from findings", `gstack lib/review-evidence.ts:251-264`. Retain the parent's severity and confirmation rules where upstream differs | deep | `plugins/maeng-harness/bin/maeng-review`; `plugins/maeng-harness/lib/maeng/receipts.py`; `plugins/maeng-harness/schemas/verdict.schema.json`; `plugins/maeng-harness/tests/test_cli.py`; `plugins/maeng-harness/tests/test_status.py`; `plugins/maeng-harness/tests/test_decisions_wiring.py`; `plugins/maeng-harness/tests/test_review_policy.py` (new); `plugins/maeng-harness/tests/test_review_rounds.py` (new); `plugins/maeng-harness/tests/test_plan_review.py` (new) | consumes: S1 identity/coverage and S2 selection; produces: plan pass receipt, explicit reviewed coverage, unresolved findings and confirmation receipt; serializes confirmation reservation per repository/PR | `python3 -m pytest -q plugins/maeng-harness/tests/test_review_policy.py plugins/maeng-harness/tests/test_review_rounds.py plugins/maeng-harness/tests/test_plan_review.py` passes AC-3 through AC-5 | a medium-only result fails; unknown coverage narrows; blocked consumes a round; new findings enter confirmation; confirmation passes without closing every enrolled blocker; malformed output triggers model fallback | S2; nonempty historical corpus enrolled in S8 |
| S4 | Turn Stop into notices, deliver pending notices in model context, fix terminal status, and add PR/review-entry plan-review notices. Deduplicate record notices per repository/PR. Keep verification and merge refusals intact. Source: "Stable record identity", `oh-my-hermes src/system/append_only_store.py:263-271`; parent P4b/P9 | deep | `plugins/maeng-harness/lib/maeng/handlers.py`; `plugins/maeng-harness/lib/maeng/receipts.py`; `plugins/maeng-harness/bin/maeng-review`; `plugins/maeng-harness/tests/test_stop_hooks.py`; `plugins/maeng-harness/tests/test_status.py`; `plugins/maeng-harness/tests/test_plan_notices.py` (new) | consumes: session-own-change tracking and S3 plan receipts; produces: pending context notice, PR notice identity and existing terminal status fields; uses existing dispatcher fail-open behavior | `python3 -m pytest -q plugins/maeng-harness/tests/test_stop_hooks.py plugins/maeng-harness/tests/test_status.py plugins/maeng-harness/tests/test_plan_notices.py` passes AC-3/AC-6; record the real model-context delivery probe in the report | only the second Stop is nonblocking; a notice erases missing work; a failed PR-create call produces a notice; another session's change warns this session; notices become PR/review/merge gates | S3 |
| S5 | Make impact selection usable by default, build/refresh its coverage map, recover from unusable selection, and preserve the full-run evidence boundary. Add count/flaky metadata and the 16-commit replay. Source: C-1 (**direct**), `gstack ship/sections/tests.md.tmpl:57-68`; C-2 (**direct**); C-4 (**보고**, original reopened at `oh-my-hermes src/skills/catalog_definitions.py:207-219`); C-35 (**direct**); "Exact selected-case coverage", `gstack scripts/test-paid-shards.ts:494-501` | deep | `plugins/maeng-harness/tests/impact.py`; `plugins/maeng-harness/lib/maeng/evidence.py`; `plugins/maeng-harness/bin/maeng-verify`; `plugins/maeng-harness/tests/test_evidence.py`; `plugins/maeng-harness/tests/test_impact.py` (new); `plugins/maeng-harness/tests/test_evidence_integrity.py` (new); `tools/testperf/impact_replay.py` (new); `docs/design/MAE-323-b2-impact-cases.json` (new) | consumes: existing coverage dependency and static graph; produces: selected-case census, fallback reason, count availability and flaky metadata; impact wrapper remains ineligible for ship evidence | `python3 -m pytest -q plugins/maeng-harness/tests/test_impact.py plugins/maeng-harness/tests/test_evidence_integrity.py plugins/maeng-harness/tests/test_evidence.py` passes AC-7/AC-8; replay uses 16 pinned recent code commits | missing coverage crashes instead of falling back; missing node IDs disappear; empty selection passes; rc 1 is hidden by a green full rerun; impact fallback grants ship evidence; zero-test CLI exits successfully as verification | S1; after S4 because both touch verification integration |
| S6 | Update stage criteria, enforcement columns, evidence rules, five-field briefs and personal-definition defaults. Extend the report selector and measure standard starting context; trial `omitClaudeMd` only for read-only design. Source: "Checklist declarations start unobserved", `oh-my-hermes src/maintenance/release.py:2418-2430`; parent P3/P5/P6 | standard | `plugins/maeng-harness/skills/harness-run/SKILL.md`; `plugins/maeng-harness/skills/harness-run/references/spec-plan.md`; `plugins/maeng-harness/skills/harness-run/references/org-chart.md`; `plugins/maeng-harness/skills/harness-run/references/verification.md`; `plugins/maeng-harness/skills/harness-run/references/review-and-ship.md`; `plugins/maeng-harness/skills/task-brief/SKILL.md`; `plugins/maeng-harness/skills/execute-code-brief/SKILL.md`; `plugins/maeng-tools/agents/quick.md`; `plugins/maeng-tools/agents/standard.md`; `plugins/maeng-tools/agents/design.md`; `plugins/maeng-harness/lib/maeng/handlers.py`; `plugins/maeng-harness/tests/test_stop_hooks.py`; `plugins/maeng-harness/tests/test_docs_sync.py`; `plugins/maeng-harness/tests/test_workflow_contracts.py` (new); `tools/testperf/subagent_context.py` (new); `docs/design/MAE-323-b2-context.json` (new) | consumes: final S3/S4/S5 behavior; produces: executable examples, stage table, exact report types and transcript-backed context result | `python3 -m pytest -q plugins/maeng-harness/tests/test_workflow_contracts.py plugins/maeng-harness/tests/test_stop_hooks.py plugins/maeng-harness/tests/test_docs_sync.py` passes AC-9/AC-10; AC-11 has an observed transcript and checked context record | old four-round/Stop-block instructions remain; shared definitions change; a report is treated as runner evidence; an unknown context count passes; prose-only tests duplicate English sentences | S4, S5; bundle 1 released (0.3.21, 2026-11-07) |
| S7 | Add checked gate/periodic suite inventory, isolated plugin-suite execution and an informational CI aggregate. Keep sampled mutation outside the PR lane. Source: "One paid-test classifier", `gstack test/helpers/paid-test-set.ts:13-33`, used for one shared lane inventory | standard | `.github/workflows/harness.yml`; `plugins/maeng-harness/tests/lanes.json` (new); `tools/testperf/plugin_checks.py` (new); `plugins/maeng-harness/tests/test_plugin_checks.py` (new) | consumes: discovered plugin test suites and S5 result/count contract; produces: per-suite results plus one aggregate; no CI result is consumed by ship | `python3 -m pytest -q plugins/maeng-harness/tests/test_plugin_checks.py` passes inventory, failure/skip and isolation fixtures; a real CI run covers the enrolled suites for AC-12 | a plugin has tests but no lane; only `plugins/maeng-harness/tests` executes; credentials leak into a child; failed/cancelled/empty required execution yields aggregate success | S5; key-free/HOME-isolation preflight before the real workflow run |
| S8 | Enroll historical review inputs before S3's prompt edit, run preservation replay, test new regressions on pre-change behavior for information, complete integration checks and report/release preparation. Source: "Replay output integrity", `gstack lib/review-ledger.ts:525-551`; parent P3-6/P6-6 | planner | `tools/testperf/review_replay.py` (new); `plugins/maeng-harness/tests/test_review_replay.py` (new); `docs/design/MAE-323-b2-review-cases.json` (new); `docs/design/MAE-323-b2-report.md` (new); `plugins/maeng-harness/.claude-plugin/plugin.json`; `plugins/maeng-tools/.claude-plugin/plugin.json` | produces for S3: frozen corpus, original-output hashes and independently enrolled blockers; consumes final rows for replay, report and release; records post-release measurement owner/window | `python3 tools/testperf/review_replay.py --manifest docs/design/MAE-323-b2-review-cases.json --require-complete --max-lost-blockers 0` passes AC-13; final Verification checks pass | no reconstructable blocker case exists; missing cases are skipped; original output changes; expectations follow the new result; regression collection errors are called useful red; release/report is claimed before it exists | corpus enrollment before S3; final work after S1 through S7 |

Traceability:

| Criterion | Responsible row | Verification |
|---|---|---|
| AC-1 | S1 | Full suite, including criteria identity and merge-boundary fixtures |
| AC-2 | S2 | Full suite, including actual invocation-argument fixtures |
| AC-3 | S3, S4 | Full suite, including plan receipt and notice boundaries |
| AC-4, AC-5 | S3 | Full suite, including findings, coverage and confirmation fixtures |
| AC-6 | S4 | Full suite, including Stop, context delivery and terminal status |
| AC-7 | S5 | Pinned 16-commit impact replay |
| AC-8 | S5 | Full suite, including evidence-integrity fixtures |
| AC-9, AC-10 | S6 | Full suite; semantic rules also inspected in independent review |
| AC-11 | S6 | Transcript-backed context checker |
| AC-12 | S7 | Isolated plugin-suite runner; attach the real CI result |
| AC-13 | S8 | Historical review replay |

Steps:

1. Reconcile bundle 1 and the applicable design passes. Enroll S8's historical corpus and blocker expectations before S3 changes the review prompt: the corpus file `docs/design/MAE-323-b2-review-cases.json` lands in PR 2a; the replay run stays in 2b (S8). If the corpus cannot be reconstructed, preserve the gap and resolve OQ-2 before S3; other independent preparation may continue.
2. PR 2a: S1, then S2 and S3. Done when AC-1 through AC-5 hold on fixed fixtures. Validate receipt consumption through ship and the lease gate, not only review stdout.
3. PR 2a: S4, then S6. Done when AC-3, AC-6, AC-9, AC-10 and AC-11 hold, including the pre-merge `--plugin-dir` context observation. Then the full checks, review, CEO brief and merge quiz of 2a; merge 2a.
4. PR 2b (branched from the merged 2a): S5, then S7. Done when AC-7, AC-8 and AC-12 hold, including the real CI result. These rows do not infer execution from configuration.
5. PR 2b: finish S8, run the final checks, review, CEO brief and merge quiz; merge 2b. Prepare releases after merge under the parent's release procedure. Report the post-release measurement as pending until its observation window exists.

Verification tier: gate-code. While working: `python3 plugins/maeng-harness/tests/impact.py run`. Before every code-review round, run `python3 -m pytest -q -n 8` on the completed head. Impact runs never replace it.

Verification:

Each line names one check command. A successful command with no relevant cases or missing required evidence fails the corresponding criterion. Expected bounds and behavior come from the Spec above, not from running the implementation to obtain expected values.

- AC-1: `python3 -m pytest -q -n 8` — expect the criteria-identity and authorization cases to execute and pass.
- AC-2: `python3 -m pytest -q -n 8` — expect all three route paths and the exclusion/availability matrix to execute and pass.
- AC-3: `python3 -m pytest -q -n 8` — expect plan-review receipt and large-task notice boundaries to execute and pass.
- AC-4: `python3 -m pytest -q -n 8` — expect blocking, nonblocking, location-exception and empty-response cases to execute and pass.
- AC-5: `python3 -m pytest -q -n 8` — expect head counting, scope fallback, one-confirmation and ship-eligibility cases to execute and pass.
- AC-6: `python3 -m pytest -q -n 8` — expect Stop, prompt-context delivery, PR deduplication and terminal-status cases to execute and pass.
- AC-7: `python3 tools/testperf/impact_replay.py --manifest docs/design/MAE-323-b2-impact-cases.json --require-cases 16 --max-median 100` — expect 16 completed cases, zero selector errors and median selected tests at most 100; report fallback separately.
- AC-8: `python3 -m pytest -q -n 8` — expect runner/declaration, zero/unknown count, impact and flaky-evidence cases to execute and pass.
- AC-9: `python3 -m pytest -q -n 8` — expect nonempty stage/brief contracts and valid executable examples; independent review judges their meaning.
- AC-10: `python3 -m pytest -q -n 8` — expect each new personal type, legacy implementer, missing-section and eta case to execute and pass.
- AC-11: `python3 tools/testperf/subagent_context.py --evidence docs/design/MAE-323-b2-context.json --max-input-tokens 20000 --require-observed` — expect a valid fresh-session standard observation at or below 20,000; disclose the separate omission trial result.
- AC-12: `python3 tools/testperf/plugin_checks.py --lane gate --isolated --require-complete` — expect inventory parity and every required suite to execute successfully; attach the matching real CI aggregate and per-suite results.
- AC-13: `python3 tools/testperf/review_replay.py --manifest docs/design/MAE-323-b2-review-cases.json --require-complete --max-lost-blockers 0` — expect nonempty complete cases and blocker denominator, unchanged enrolled inputs and zero lost blockers.

Replay, CI and context commands need actual outputs and source artifacts attached to review. A `maeng-verify ran --ok` declaration alone does not establish those results.

Before merge, because hook behavior and CLI entry points change:

- Run `HARNESS_TEST_PROCESS=1 python3 -m pytest -q -n 8` on the final tree.
- Run `claude plugin validate plugins/maeng-harness`.
- Run `claude plugin validate plugins/maeng-tools`.
- Confirm the four shared agent definitions have no changes.

Full-run sequence follows parent P2-3: full -> round one -> impact while fixing -> full on the revised head -> round two. If round one passes, one full run suffices. If remaining high findings need confirmation, fix them, run full on that head, then confirm. Base movement requires fresh verification. Record these extra-run reasons separately for parent 5.

Failure / change handling: use harness-run's existing repair limit. A criterion, Owns or decision change needs the user; ordinary ordering changes within this scope go in Revisions. Missing role policy blocks the affected invocation, not unrelated preparation. Stop failures stay open; review and merge verification failures stay closed. If preservation replay loses a patch-introduced blocker, do not release the new review policy until corrected. If standard context remains above the approved limit, report the measured cause before expanding the tool or context-removal scope. D-10/D-11 require an explicit choice before either extension is implemented.

Review focus: can missing evidence become pass through an empty selection, declaration, legacy receipt or confirmation; does every entry path use the same acceptance digest; does later review narrow only where prior coverage is established; can a failed reviewer trigger an unauthorized model change; can notification delivery leave a finished task running or erase its obligation; does CI cover the plugin suites outside root pytest collection.

Revisions:

- R-1 plan scope: kept the parent's complete bundle 2 allocation within eight rows; additional candidate machinery is listed in "묶음 밖".
- R-2 plan interface: retained the coverage list and proposed explicit full/delta metadata so receipt consumers can preserve their existing file-coverage contract.
- R-3 plan order: historical corpus enrollment precedes the review-prompt change; final replay follows implementation.
- R-4 plan decisions: C-29/C-30 remain D-10/D-11 with named options and no recommendation. Existing state-directory protection was distinguished from the proposed extension.
- R-5 plan verification: every criterion has one check command and an explicit vacuous-pass failure. Full verification remains required before each review round.
- R-12 plan approval (2026-11-07): the user approved AC-1 to AC-13 and A-1 to A-12 ("승인").
- R-11 plan decisions (2026-11-07): the user chose 가 for D-11 ("가 알림만"); the parent's P9 stands.
- R-10 plan decisions (2026-11-07): the user chose 가 for D-10 ("가 지금 경계 유지"): no new protected location in bundle 2.
- R-9 plan decisions (2026-11-07): the user chose two PRs for D-12 ("PR 둘로"); Deliverable and the steps now name 2a and 2b.
- R-8 plan decisions (docs review round 2, Astra medium, 2026-11-07: pass, low 1): the PR structure is D-12 with two named options and a readiness rule; no recommendation shown before the user chooses.
- R-7 plan verification (docs review round 1, Astra medium, 2026-11-07: high 2): confirmation requires the round-two base and criteria digest, else `blocked` and the user's `승인 #N`; AC-11 is observed before merge with `--plugin-dir` on the candidate tree and verified again after release.
- R-6 plan boundary: extending SubagentStop to the new definitions is explicit; it resolves bundle 1's known selector gap without changing shared definitions or eta behavior.

Close-out: filled when the bundle closes.

## Progress

- Step 1 done 2026-11-07 (standard at medium, commit a23f430): the pass-receipt store holds no high findings, so `review_replay.py build` reads the review store (`<home>/reviews/*.json`) too; 209 code/parent verdicts scanned, 49 cases with 127 expected-blocking findings enrolled, all 49 reconstructable (shas present). `plan_path` is null everywhere (review subjects carry no plan field); the old `criteria_rev` values are mtime-based, so S8 recomputes the digest from the head's plan text. The planner re-ran `check` and the 2 tests.
- S2 done 2026-11-07 (standard at high, partial report completed by the planner): `lib/maeng/routing.py` (stdlib only, loaded by path from the maeng-tools Decisions scripts) resolves roles and routes to candidates in primary-then-standby order with the parent's rules 1-5 (author family or exact id skipped; planner skipped for `plan` and `parent`; advance only on exclusion or availability failure; exhaustion = `blocked`, exit 2; a dated id such as `claude-opus-5-5-20261101` matches its model). `maeng-review` gains `--author-model` and `--planner-model` (`--author codex` stays as a family); a `parent` review without a planner identity is refused, because nothing in the binding records the planner (S6 updates the rule text; a binding field is a bundle 3 candidate). Receipts' `reviewer` records `resource`, `row`, `route` and `skipped` (schema extended). Every roles row and standby carries `resource`; `test_roles.py` checks the resource lists the model. `verify_claims.py` and `records.py` resolve `claim_check` and `records_duplicate` from the table and pass `model=` explicitly (an ambient `MAENG_DECISIONS_MODEL` no longer replaces the route's model; `MAENG_DECISIONS=off` and eta unchanged); the table is found from a source checkout or a versioned install. Two `test_r2.py` parent calls gained `--planner-model`. Mutations caught: planner exclusion removed → 4 tests fail; explicit claim model dropped → 2 fail. The planner re-ran: route tests 20 pass, full suite 630 pass, both plugins validate. Not driven end to end: the `plan` kind through the CLI (S3), the author exclusion on docs/research/notion (resolver tests only).
- S1 done 2026-11-07 (standard at high): `evidence.criteria_rev(text)` (acceptance section between the `Requirements -> acceptance:` label or an `## Acceptance` heading and the next heading, fences ignored, None when absent, ambiguous or without an AC id); bind stores it in the binding's `plan_updated_at` field (name kept; `--plan-updated` still overrides, which the Linear-timestamp flow uses); `committed_plan()` in `maeng-review` computes the same digest; `find_code` treats a null revision as matching nothing; receipts gain `coverage` (list of file+mode), `previous_head`, `review_mode` and a `plan` subject kind with `find_plan(issue, criteria_rev)`. Three test files moved off "null equals null". The planner re-ran `test_criteria_rev.py` (14 pass) and the full suite (609 pass). Known shortcut: the label form ends at the next heading or a blank line plus unindented prose.

- Draft preparation only. No implementation, tests, probes, provider calls, CI runs, releases or external writes were performed.
- Read the parent plan, bundle 1 plan, template, all 58 candidates and the full supplied code-reading source. Only its "그대로 쓸 수 있는 것" rows are used as code-reading sources here.
- Listed the harness test files and plugin test-suite locations. Existing files assigned changes were read; new proposed files do not yet exist.
- Observed boundaries: the dispatcher already fails open for Stop handler errors; Stop itself currently returns block. SubagentStop selects names ending in `implementer`. `criteria_rev` currently uses a file timestamp for bound Plans and is absent for committed `--plan` input. Impact currently returns success on an empty selection and drops nonexistent selected targets. Root pytest excludes maeng-tools skill suites.
- Unfinished prerequisites: reconcile bundle 1 S6/S7; obtain applicable design passes; enroll a reconstructable historical review corpus; observe model-context notice delivery and fresh standard-agent context; run the isolated plugin suites and real CI.
- Post-release observation remains with MAE-323: report full-suite frequency and separately count impact fallback, base movement and confirmation fixes. No operational improvement is claimed from this draft.

Not read / not verified: no required input was inaccessible; repository-root `AGENTS.md` was absent, so the supplied instructions were used. Installed versions, bundle 1 completion evidence, historical review reconstruction, host timeout/context behavior, live model identities, starting context, tests, CI and release behavior were not verified.