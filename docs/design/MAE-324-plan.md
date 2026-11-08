# Spec/Plan: MAE-324 track 2 — quality, closing comprehension and improvement

Status: draft implementation plan. Date: 2026-11-09. AC-1 through AC-7 were approved by the user on 2026-11-06, with changes N-1 through N-5 approved on 2026-11-07. AC-8 through AC-10 and D-16 through D-20 are provisional overnight choices made on 2026-11-09. Sealed recommendation: 27e91a8bfa62.

Goal: improve substantial non-code deliverables through evidence-backed criteria and independent checking, offer closing comprehension, and make harness improvement repeatable.

Deliverable: one implementation PR with a quality-layer skill, five pointers, a checker route and standard validator, closing questions, a component inventory and an audit procedure. Three genre standards and the trial record remain private. Prepare maeng-harness 0.4.16 and a maeng-tools patch release; this drafting task writes only this plan and makes no commit.

Morning decisions: use this plan itself as the v3 trial (D-16); include the component inventory and audit procedure now, with the pass-definition rule only as a proposal (D-17); shorten other skill descriptions instead of raising the byte budget (D-18); use a skill-level checker route on gpt-6.1-sol high instead of a new review kind (D-19); keep genre standards in the private vault (D-20); let the trial record finish after merge instead of gating it (D-21, see Open after merge); also confirm the closing walkthrough item (AC-8) and assumptions A-1..A-5; answer the trial's pending steps and the blind comparison. Details in Decisions.

Sources: repository examples [bundle 2](MAE-323-b2-plan.md), [bundle 3](MAE-323-b3-plan.md), the harness-run Spec/Plan template, budget and role tests, and local private trial records read on 2026-11-09. Source revision: local file contents; no service revision fetched. Private content is summarized in original English; no user quotations enter this repository.

Dependency: MAE-323 bundles 2 and 3 are merged at release 0.4.15; the code-order dependency is gone. The local maeng-harness manifest is 0.4.15 and maeng-tools is 0.3.24. Installed behavior and provider availability were not probed.

Decisions:

All selected options below are provisional, covered by sealed recommendation 27e91a8bfa62. The morning list and R-1 preserve their status; a provisional decision identifier does not mean user agreement.

| Decision | Source | Selected provisionally | Alternative |
|---|---|---|---|
| D-16 Trial target | TR-6; procedure v3 | Apply v3 while writing this plan, from the start. User steps wait for morning; TR-6 stays open. Wrong if this cannot provide the required trial evidence. | Wait for the next real talk or video task. |
| D-17 Improvement scope | I-1 through I-4 | Include inventory I-1 and audit I-2, with paired measurement I-3 inside the audit. Draft I-4 as proposal-only. This expands the earlier deferral; no trial established its effect; see Evidence boundary. Wrong if the user retains that deferral. | Defer I-1 through I-3 as the approved draft did. |
| D-18 Description budget | Current budget test | Shorten existing descriptions; retain BASE_BYTES = 20651. Wrong if required trigger meaning cannot fit without loss. | Raise the byte budget with user approval. |
| D-19 Checker route | AC-3; current routes contract | Add routes.quality_check: resource gpt_pro, model gpt-6.1-sol, effort high, invoked with codex exec; standby a Claude subagent recorded as independence unknown. enforcedBy = skill; where = plugins/maeng-harness/skills/quality-layer/SKILL.md. Wrong if the actual checker is not independent or available. | Add a new maeng-review kind, with its additional receipt and gate coupling. |
| D-20 Standard location | AC-4; public repository boundary | Keep wiki/standards/STD-<genre>.md and saved sources beside them in the private vault. Repository additions are the validator and synthetic fixtures, never real standards or user words. Wrong if private source readback is unavailable. | Put standards in the repository; rejected because they can contain private user wording. |

Assumptions:

- A-1 Use one skill, no hook and no gate, preserving the approved form. A reference repository reported zero invocations in 180 opportunities for an unprompted skill; that is a warning, not a measurement of this harness. AC-2 pointers and TR-6's separate read/followed record address invocation risk. If it is not invoked, move the procedure into harness-run steps through an explicit revision.
- A-2 Apply the quality layer when the user will show or submit the result and the work appears longer than 30 minutes. Exclude code tasks and a user's request to omit criteria. The closing offer in AC-8 has its own broader scope.
- A-3 Prefer a checker from a different provider than the author. Record planned and actual model on every check; a same-harness standby has independence unknown. Unavailable, timed-out or same-author checks are not checked, never pass.
- A-4 The quality judgment never blocks work, review, merge or submission (Q-5). Structural implementation acceptance and existing safety gates retain their separate meaning.
- A-5 Time is reported by measured segment, never used as a pass line; this preserves MAE-324's earlier D-1. Missing measurements remain unavailable, not zero.

Owns: this task writes only docs/design/MAE-324-plan.md. Future implementation owns exactly the paths in the Sub-tasks table, including its private planner outputs. No hook, merge CLI, review kind, measurement script or shared agent definition is assigned a change.

Exclusions:

- Q-4 (recording a quality score per task) is replaced by finding lists and user assessments; no score trend or numeric pass threshold.
- Q-3 (forcing demand-evidence and prior-art questions) is excluded; demand evidence and precedent comparison belong in a product-genre standard when one exists.
- U-3 (putting quality conditions into the closing questions) remains untested and is not added here.
- I-4 (the user must approve any change to what counts as a pass; only a proposal paragraph ships) adoption is excluded. I-5 (weekly change watch and model onboarding) already belongs to MAE-327.
- No hook reminder, gate, blocking quality judgment, new maeng-review kind, automatic invocation or time pass line.
- No standards beyond business pitch talks, research talks and one-minute promotional videos. No quality-layer procedure for code tasks.
- No new measurement framework, audit scheduler, provider benchmark or unrelated tool fixes.

Any item above can be requested back.

Evidence boundary:

The three trials on 2026-11-06 covered a course pitch talk, a research-community talk and a one-minute promotional video. All three met their fixed include condition, each relying on one interpretation of an answer or defect agreement. They were one user's same-day trials without a control group; they support a bounded quality-layer trial, not a general effectiveness claim.

The user found the largest defect every time. Independent checkers found real defects the authors missed, especially when opening sources themselves. Authors expanded criteria beyond their sources: 5 of 7, 6 of 7, and 10 of 25 sentences respectively. Same-format real examples mattered; their independent causal effect was not isolated.

Scores moved by up to six points across checking depths, so scores are not compared. Closing Q&A was offered three times and never used as Q&A; once it became an explanation from first principles. Extra time was about 1.8 times and 2.2 times work time in trials 1 and 2, and the user still judged it worthwhile. Trial 3 had no measured work-time denominator; later rework was not fully included.

The trials did not support I-1 through I-4, Q-4 score tracking or U-3. AC-8 preserves a requested default without claiming demonstrated learning; AC-9 and AC-10 are provisional procedure additions, not proven improvements. Procedure v3 and N-1 through N-5 still require the new trial. The user's relayed instruction for this overnight run was to carry track 2 through in one pass, which is why the untrialed AC-8..AC-10 ship; they are provisional, live in separate commits (S6, S7), and dropping them leaves AC-1..AC-7 intact.

must_haves:

- T1 Evidence-led, nonblocking quality checking follows v3 with explicit failure states: AC-1, AC-3, AC-5.
- T2 Five existing skills link once to the procedure without duplicating it: AC-2.
- T3 Three private standards have attributable conditions and verifiable saved quotations: AC-4.
- T4 A complete new trial records user judgment, paired comparison, checker controls and invocation: TR-6; its decision conditions are fixed in advance: AC-7.
- T5 Finished work includes a default structure/design walkthrough and questions, with user-only skipping: AC-8.
- T6 Component assumptions and evidence are inventoried; an approved, paired audit can be repeated: AC-9, AC-10.
- A1 Quality-layer skill and checker prompt (AC-1, AC-3).
- A2 Validator, private standards and synthetic fixtures (AC-4).
- A3 Closing item, component inventory and audit procedure (AC-8 through AC-10).
- K1 Skill -> checker prompt and policy route (AC-1, AC-3).
- K2 Validator -> private standards and synthetic fixtures (AC-4); harness-run -> closing item and audit -> inventory (AC-8 through AC-10).

Procedure contract (AC-1):

The skill uses headings in the form ### P-n <name>, in this order, each with a Fails: line stating the resulting status, retained obligation and next owner/action. The following is an English implementation contract, not copied private prose. Tests bind the markers and failure structure, not these sentences.

| Step | Required behavior |
|---|---|
| P-1 Target | Confirm topic, purpose, audience, destination, length and time; resolve a missing destination, disclose access needs and why the layer applies. Measure what can be measured instead of asking the user. |
| P-2 Inputs | Read supplied material fully before costly questions. Inventory all task-relevant reference files at a pinned revision, excluding unrelated application code. For delegated reads give exact paths and verify complete reads. Record scope, omissions, reuse/adapt/reject choices, requirements, decisions versus recommendations and qualifications. |
| P-3 Examples | The author directly inspects 2–3 same-format examples, including full text or video frames. Collectors return originals or frame paths, not summaries. Extract structure and voice; retry failed collection once, then continue with missing examples prominent in the record and closing explanation. |
| P-4 Criteria | Start from the genre standard; propose 3–7 conditions with sentence-level source quotation, user attribution or author's judgment. Record genre/date; cover format distinction and audience persuasion. Keep format limits in an unscored checklist. Show each condition with an example; default to all without waiting, subject to user changes. |
| P-5 Attribution | The script checks literal quotations; another model checks whether they support the condition. Record supported, contradicted or uncertain. Replace, relabel or remove contradicted conditions; relabel uncertainty as author's judgment before P-7. Keep a disposition table; do not score examples. |
| P-6 Author | Use examples' structure and voice, not the criteria as an outline or internal reporting prose. Keep a source-linked fact table for numbers, names and dates; distinguish verified from user-supplied facts, and measurements from estimates. |
| P-7 Check | One fresh checker receives artifact, criteria, sources and examples, without author conversation or rationale. Read as the audience first; name the weakest part separately from defects. Open evidence, recompute numbers, compare facts literally, inspect renders and examples. Return pass/fail/uncertain/not-applicable per condition; overall fail precedes uncertain precedes pass, ignoring not-applicable. Audience failure prevents pass. No applicable conditions cannot establish pass. |
| P-8 Revise | Record accepted, rejected-with-evidence or uncertain for each finding. Fix high findings once; retain medium/low. Ask separately before changing user direction. A fresh execution rereads the full result for flow, compares changed conditions side by side and records version order. Report remaining high findings; later edits are not checked. |
| P-9 Feedback | Restate user feedback for confirmation and add it as a provisional task condition, preserving exact user wording only privately. Recheck the earlier version against the added condition. |
| P-10 Close | Explain structure and design before offering 3–5 questions; only the user skips, without blocking. Cover problem/example/solution, choices, discarded options, deviations, first/final comparison, omissions and checks the harness cannot perform. Read back files before claiming creation; label manual guidance as guidance. |
| P-11 Record | Save user assessments, segment timestamps, findings/dispositions and planned/actual checker identities privately. Promote conditions only after explicit genre-wide direction or recurrence on a second same-genre task. Keep at most seven dated current/stale conditions; treat stored standards as revisable hints. Preserve the meaning of short answers with their preceding options privately. |

Checker output contract: up to three highest-impact evidence-backed findings first, then the finding list. Each separates observed behavior, expected behavior, quoted evidence, smallest correction and speculation. High changes audience comprehension or condition success; medium is a local error despite condition success; low concerns expression. Unquoted claims go in an appendix. Zero findings is valid; stylistic preference or only trivial findings does not establish useful defect detection. List opened and unopened evidence. No numeric scores; observable counts are allowed. Requiring an addition also identifies what can be removed.

Timing contract: work comprises P-2, P-6 and editing in P-8/P-9; overhead comprises P-3/P-4/P-5/P-7, rechecking in P-8 and P-10. Record start/end for each measured segment; label other or unavailable segments explicitly. P-5, P-7 and P-8 are the three separate checker executions.

## Acceptance

- AC-1: plugins/maeng-harness/skills/quality-layer/SKILL.md carries P-1 through P-11 of v3 as ordered ### P-n <name> headings, each with Fails:. test_quality_layer.py checks markers, order and failure lines, fails on zero markers, and does not freeze prose (N-1). Total skill name/description bytes remain within BASE_BYTES 20651 (D-18). Structure is not evidence of effect.
- AC-2: harness-run and maeng-tools aside-research, coherent-writing, presentation-design-interview and motion-studio each contain one pointer line to quality-layer without copying its body. Tests fail on a removed pointer, a P-n heading or a copied checker instruction block in any pointing skill (N-1).
- AC-3: routes.quality_check exists in policy/roles.json with D-19's resource, model, effort, standby, enforcement and location. test_roles.py checks that the quality-layer skill names the same model and effort; absence or mismatch fails.
- AC-4: quality-layer/scripts/check_std.py validates at most seven conditions, each dated, current or stale, with exactly one tag: source plus quotation, user plus the user's words, or author's judgment. Every source quotation occurs verbatim in its named saved source (N-2). Empty files and zero quotations fail. It exits zero on all three trial-derived private standards, nonzero on missing-tag, absent-source-quote, eight-condition and empty fixtures.
- AC-5: No hook blocks on quality judgment. A test asserts hooks code and hooks.json contain no reference to quality-layer or check_std; this is a new coupling check, not removal of existing safety gates.
- AC-7: The private record fixes include/drop/revise conditions before TR-6's trial; time is reported, never a pass line. Include requires a better final result, at least one checker defect the user agrees with and worthwhile extra time. Drop requires neither a better final result nor worthwhile extra time; otherwise revise. Recording the conditions meets this criterion; the outcome informs judgment, not implementation pass.
- AC-8: For all finished work, harness-run's CEO brief list gains an item offering a structure/design walkthrough first, then 3–5 structure/design questions by default (U-1, U-2). Only the user skips; skipping blocks nothing. The forced merge quiz is unchanged. A structure test checks the item is in that list. Provisional.
- AC-9: policy/inventory.json lists every maeng-harness skill, every bin and the hooks entry, including quality-layer. Each entry has status helps, no-effect, unverified or safety, one line describing its model assumption, and evidence for any status other than unverified. Tests check path existence, complete skill/bin coverage, valid statuses and required fields. Provisional I-1.
- AC-10: harness-run/references/harness-audit.md defines one procedure: run named tools/testperf scripts, assess G1 through G5, propose changes, then obtain user approval. Component effect requires a with/without pair and is never concluded from one run (I-3). I-4's pass-definition approval rule is explicitly proposal-only, not adopted. Tests check named script paths exist and the proposal marker is present. Provisional I-2.

## Open after merge

D-21 (provisional, 2026-11-09, not sealed because one seal was already open): the trial record moves out of Acceptance. It was the sixth criterion of the approved set; it is a private vault record that only the user's morning answers can complete, and the review gate refuses a head with an unmet criterion. Bundle 3 closed the same way with a user-judgment row deferred past its PR (its D-14). The code does not depend on it. Wrong if the user wants the merge to wait for the trial answers.

- TR-6: A private trial record applies v3 plus N-1 through N-5 from the start and names its source revision first. It contains segment times, first/final user answers, checker defects explicitly agreed by the user, user-first defects, separate skill-read and skill-followed evidence (N-5), and a blind comparison with one part authored without the layer (N-3). Controls catch a planted defect, fail empty/off-topic results and leave a clean passage unflagged (N-4). Expected unmet at PR time until the user answers (D-16).
  Locator: `grep -c "시험 4" "$HOME/Documents/Obsidian Vault/wiki/drafts/DRAFT-MAE-324-quality-layer-plan.md"`
  Locator only: a positive count is insufficient. Inspect complete trial evidence, controls, blinded comparison, read/followed records and direct user answers; pending means unmet.

## Plan

Readiness: the approved quality-layer criteria remain current; overnight additions remain provisional pending morning confirmation. Existing review and merge requirements still apply. No implementation or private-record update occurs in this drafting task.

Environment: run commands from the repository root. Root pytest collects maeng-harness only; the gate-lane inventory also runs harness and maeng-tools suites in their own working directories. New files and test selections below are planned, not observed passing commands.

Routing: implement under each Grade using the existing policy; use D-19 for quality checking separately from implementation review. Reconcile actual author/provider before dispatch, record planned/actual identities, and report unavailable routes. No provider call is needed to draft this file.

Discarded alternatives:

- Hook reminder: adds hook coupling while invocation is still unmeasured; pointers and N-5 test that assumption first.
- Numeric 0–100 score and 90 pass line: the trials exposed unstable scoring; use evidenced findings and user judgment.
- Repository standards: reject private user wording and real trial material in a public tree.
- New maeng-review kind: adds receipt/gate semantics to a nonblocking judgment; use the skill route.
- Higher byte budget: first shorten descriptions without losing trigger meaning; a higher ceiling needs approval.
- Waiting for another trial and deferring I-1 through I-3 remain reversible alternatives in D-16/D-17, not established inferior choices.

Sub-tasks:

All paths are repository-relative unless marked private. Q means plugins/maeng-harness/skills/quality-layer; H means plugins/maeng-harness; M means plugins/maeng-tools; T means H/tests/test_quality_layer.py (S1, S4, S5); TL means H/tests/test_quality_layer_links.py (S2, S6, S7). These abbreviations expand literally, not to directory-wide write permission. New paths are proposals. Budget trims (D-18) may touch the frontmatter description of any existing skill, keeping its trigger words; pointer and CEO-brief edits follow them in the same files.

| Row | Do | Grade | Writes | Interfaces | Done command | Fails-if | After |
|---|---|---|---|---|---|---|---|
| S1 | Write v3 and checker prompt; trim existing descriptions without changing BASE_BYTES. | standard | Q/SKILL.md; Q/references/checker-prompt.md; T; H/skills/harness-run/SKILL.md; description trims in existing plugins/*/skills/*/SKILL.md frontmatter | P markers; Fails lines; checker input/output contract | python3 -m pytest plugins/maeng-harness/tests/test_quality_layer.py plugins/maeng-harness/tests/test_skill_budget.py -q | zero/missing/out-of-order markers, missing failure line, lost procedure meaning or raised budget passes | approved baseline; D-18 |
| S2 | Add one pointer to each of the five skills; test deletion and duplication. | quick | H/skills/harness-run/SKILL.md; M/skills/{aside-research,coherent-writing,presentation-design-interview,motion-studio}/SKILL.md; TL | single-line links; no procedure/checker copy | python3 -m pytest plugins/maeng-harness/tests/test_quality_layer_links.py -q -k pointer | fewer than five skills checked, zero pointers, removed link or copied block passes | S1 |
| S3 | Add quality_check route and model/effort sync checks with missing/mismatch cases. | standard | H/policy/roles.json; H/tests/test_roles.py; Q/SKILL.md (route text) | D-19 route and actual invocation instructions | python3 -m pytest plugins/maeng-harness/tests/test_roles.py -q | absent route or skill model/effort drift passes; declared route is called proof of execution | S1; D-19 |
| S4 | Implement validator, document condition fields, add synthetic fixtures/tests and build three private standards. | standard | Q/scripts/check_std.py; Q/SKILL.md (standard format); H/tests/fixtures/quality_layer/* (synthetic standard/source fixtures only); T; private wiki/standards/STD-{business-pitch-talk,research-talk,promo-video-1min}.md and saved sources beside them | literal source attribution; max seven; date/status/tag schema | python3 -m pytest plugins/maeng-harness/tests/test_quality_layer.py -q -k std | zero fixture cases, no quotes, missing tag/source, invented quote, eight conditions or empty input passes | S3; D-20; real-standard command in AC-4 also required |
| S5 | Assert absence of quality-layer/check_std references in hook code/config. | quick | T | H/hooks and H/lib/maeng hook handlers, read-only | python3 -m pytest plugins/maeng-harness/tests/test_quality_layer.py -q -k hook | no hook files inspected or injected coupling passes; runtime hooks are edited | S4 |
| S6 | Add closing walkthrough/questions item to the CEO brief list. | quick | H/skills/harness-run/SKILL.md; TL | default offer; user-only skip; existing quiz untouched | python3 -m pytest plugins/maeng-harness/tests/test_quality_layer_links.py -q -k closing | missing list/item passes, offer becomes opt-in, skipping blocks, or forced quiz changes | S5; runs overnight as provisional; morning confirmation needed before merge |
| S7 | Inventory components and model assumptions; write one paired audit procedure and proposal marker; test coverage/paths. | standard | H/policy/inventory.json; H/skills/harness-run/references/harness-audit.md; TL | I-1/I-2/I-3; proposal-only I-4; existing measurement CLIs | python3 -m pytest plugins/maeng-harness/tests/test_quality_layer_links.py -q -k 'inventory or audit' | empty inventory, missing skill/bin, nonexistent path, invalid status, unsupported evidence claim or absent proposal marker passes | S6; runs overnight as provisional; morning confirmation of D-17 and AC-9/AC-10 needed before merge |
| P1 | Complete the started private trial and inspect fixed decision conditions. | planner | private wiki/drafts/DRAFT-MAE-324-quality-layer-plan.md | TR-6/AC-7; user answers and blind comparison | grep -c "시험 4" "$HOME/Documents/Obsidian Vault/wiki/drafts/DRAFT-MAE-324-quality-layer-plan.md" | marker alone closes TR-6; pending answers become inferred agreement; missing paired/control evidence passes | started with this plan; user steps in morning |
| P2 | Integrate checks/review and prepare both patch versions. | planner | docs/design/MAE-324-plan.md (Revisions/Close-out); H/.claude-plugin/plugin.json; M/.claude-plugin/plugin.json | maeng-harness 0.4.16; maeng-tools patch from 0.3.24 | python3 tools/testperf/plugin_checks.py --lane gate --isolated --require-complete | zero/failed required suites, provisional approval or prepared version is called release; TR-6 gap is hidden | S1 through S7; morning decisions; existing merge/release authorization |

Tests are split so rows can run in parallel with disjoint files: S1/S4/S5 own test_quality_layer.py, S2/S6/S7 own test_quality_layer_links.py, S3 owns test_roles.py. S3/S4 also sequence changes to Q/SKILL.md. P1's user-dependent work can remain open while implementation finishes; it cannot be marked met merely because a PR is ready.

Audit contract (AC-10): name existing tools/testperf/loopstats.py, impact_replay.py, review_replay.py and periodic_checks.py, with their real arguments, prerequisites and retained outputs. Run mutation only through its disposable-copy runner. Unavailable data stays unavailable; an audit document is not a completed audit.

Assess G1 artifact quality against evidenced conditions; G2 intent and user comprehension; G3 time and model-call cost; G4 defects caught, missed defects and false positives; G5 repeatability, component evidence and response to change. Use findings for G1, not unstable historical scores. Propose changes with evidence; the user approves before adoption. Hold task, input, model and judging conditions fixed within with/without pairs, disclose repeats and uncertainty, and draw no effect conclusion from a single pair. Structural tests cannot establish these effects.

Trial controls (TR-6): an isolated author produces the comparison part without skill or criteria; verify its read record, blind the labels and obtain the user's choice. One comparison is noisy. Keep planted controls separate from the genuine artifact, and record checker openings, planned/actual identities and all four control outcomes. Ask about qualified answers and defect agreement explicitly; do not infer them.

Trial judgment (AC-7): freeze include/drop/revise before observing results. Keep first-version answers separate from final-version judgment. Report measured time, including gaps; the second same-genre task's overhead goal is no more than work time, not a pass threshold. One trial cannot establish the later reuse value of retained user feedback.

Traceability:

| Requirement | Criterion | Responsible row | Verification |
|---|---|---|---|
| Q-1, B-1 through B-6 revised to v3; N-1; D-18 | AC-1 | S1 | Procedure structure and budget tests; semantic review |
| Invocation links; N-1 duplication boundary; A-1 | AC-2 | S2 | Five pointer deletion/copy cases |
| Q-2 independent route; A-3; D-19 | AC-3 | S3 | Role/skill model and effort sync |
| Private standards; attribution; N-2; D-20 | AC-4 | S4 | Synthetic negative/positive cases plus all three real standards |
| Q-5; A-4 | AC-5 | S5 | Hook code/config absence and injected-reference case |
| v3 trial; N-3/N-4/N-5; D-16; A-5 | TR-6 | P1 | Marker locator plus full record and direct user evidence |
| Earlier D-1 decision conditions | AC-7 | P1 | Condition locator plus pretrial timing/content inspection |
| U-1/U-2, closing comprehension | AC-8 | S6 | CEO brief list structure and skip/quiz inspection |
| I-1 inventory; D-17 | AC-9 | S7 | Complete component/path/status/assumption/evidence checks |
| I-2/I-3; proposal-only I-4; D-17 | AC-10 | S7 | Script path checks, proposal marker and procedure review |

Order:

1. Preserve the started P1 record and fixed judgment conditions; keep user-dependent steps pending. Confirm overnight choices in the morning before treating the expanded scope as current.
2. Execute S1 through S5 sequentially, advancing AC-1 through AC-5 with the targeted commands and real-standard readback.
3. Execute S6/S7 overnight as provisional rows (the user can drop them in the morning; the commits are separate); complete P1 with the user for TR-6/AC-7. Record reversals rather than silently replacing the earlier deferral.
4. Integrate P2, run final-tree checks once and independent review under existing limits. Report TR-6 open if still unanswered; this is not completion of all ten criteria. Merge/publish only under existing authorization, then fill Close-out.

Verification tier: docs-only for this drafting task; code for the later implementation. Working checks are the row commands. The following checks are planned; none is claimed run here. Zero relevant tests, all-skipped execution or absent evidence never satisfies a criterion.

## Verification

- AC-1: `python3 -m pytest plugins/maeng-harness/tests/test_quality_layer.py plugins/maeng-harness/tests/test_skill_budget.py -q`
  Expect ordered nonempty markers, one Fails line per step and total bytes within unchanged 20651; inspect semantic v3 coverage separately.
- AC-2: `python3 -m pytest plugins/maeng-harness/tests/test_quality_layer_links.py -q -k pointer`
  Expect all five links, deletion failures and detection of copied P headings/checker blocks.
- AC-3: `python3 -m pytest plugins/maeng-harness/tests/test_roles.py -q`
  Expect route presence and exact skill model/effort agreement, including missing/mismatch failures; this does not verify provider availability.
- AC-4: `python3 plugins/maeng-harness/skills/quality-layer/scripts/check_std.py "$HOME/Documents/Obsidian Vault/wiki/standards/STD-business-pitch-talk.md" "$HOME/Documents/Obsidian Vault/wiki/standards/STD-research-talk.md" "$HOME/Documents/Obsidian Vault/wiki/standards/STD-promo-video-1min.md"`
  Expect all three to exit zero with saved-source matches; S4's fixture command must also reject all named invalid cases, zero quotes and malformed fields.
- AC-5: `python3 -m pytest plugins/maeng-harness/tests/test_quality_layer.py -q -k hook`
  Expect actual hook code/config inspected and injected references rejected; no quality coupling or new blocker.
- AC-7: `grep -c "판단 조건" "$HOME/Documents/Obsidian Vault/wiki/drafts/DRAFT-MAE-324-quality-layer-plan.md"`
  Locator only: inspect the fixed include/drop/revise rules and pretrial record; no match or a bare count cannot establish them. Time remains descriptive.
- AC-8: `python3 -m pytest plugins/maeng-harness/tests/test_quality_layer_links.py -q -k closing`
  Expect the walkthrough-first, default-question item inside the CEO brief list; inspect user-only skipping and unchanged forced quiz.
- AC-9: `python3 -m pytest plugins/maeng-harness/tests/test_quality_layer_links.py -q -k inventory`
  Expect every skill/bin and hooks entry, including quality-layer, with existing paths, valid statuses, assumptions and evidence fields.
- AC-10: `python3 -m pytest plugins/maeng-harness/tests/test_quality_layer_links.py -q -k audit`
  Expect all named script paths to exist and I-4 marked proposal-only; inspect paired measurement, G1 through G5 and user approval order.

Final tree: once, from the repository root, run python3 tools/testperf/plugin_checks.py --lane gate --isolated --require-complete. This is the .github/workflows/harness.yml gate-lane runner using plugins/maeng-harness/tests/lanes.json; its maeng-harness entry runs python3 -m pytest -q -n 8 -p no:cacheprovider, and the other enrolled suites run separately. Repeat only for a changed tree, failure or unresolved risk. Do not run the periodic lane as this change's routine check.

Failure / change handling: use the existing bounded repair procedure. Missing sources or examples remain disclosed; failed checker execution remains not checked. Neither a clean structure test nor a grep count resolves missing semantic or user evidence. Preserve open criteria. Order changes within Owns go in Revisions; criterion, ownership or provisional-scope changes return to the user. Do not upgrade inventory status from a single run.

Review focus: can vacuous structure pass; can copied procedure text escape pointer checks; can unsupported wording be treated as a sourced condition; can a failed or same-author checker become pass; can a marker count close the trial; can provisional scope become approval; can inventory labels or a single pair be mistaken for measured effect; can private wording enter fixtures or public artifacts.

## Revisions

- R-1 plan scope, 2026-11-09: under the relayed one-pass instruction, provisionally selected D-16 this-plan trial, D-17 inventory/audit expansion with I-4 proposal-only, D-18 description trims, D-19 skill-enforced checker route and D-20 private standards. Seal 27e91a8bfa62. AC-8 through AC-10 are provisional additions. Morning confirmation list: those five decisions, those three criteria and A-1 through A-5; no user agreement is inferred. ADR: private vault wiki/decisions/ADR-MAE-324-track2-overnight.md.
- R-2 trial record, 2026-11-09: the private record has started v3 plus N-1 through N-5 for this plan, using the 2026-11-07 revision. User confirmation, feedback, final assessment and blind choice wait for morning. This file does not complete or update that record; TR-6 remains open.
- R-3 plan review, 2026-11-09: `maeng-review --kind plan` (gpt-6-astra high) passed with one medium finding (S6/S7 prerequisites contradicted overnight execution); fixed: they run overnight as provisional and need the morning confirmation before merge. Budget trims widened to any existing description (actual trims: diagram-explainer, easy-understanding, manuscript-writing-review, motion-studio). Tests split into two files so rows could run in parallel.
- R-5 criteria, 2026-11-09: D-21 (provisional) moves the trial record (approved sixth criterion, now TR-6) to "Open after merge", because the parent review gate refuses a head with an unmet criterion and only the user can complete it; the AC numbering of the rest is kept.
- R-4 plan quality, 2026-11-09: quality-layer P-7 check (claude-sonnet-5-5 subagent, author gpt-6.1-sol) gave cannot-judge on C2 with one high and two medium findings; applied once (P-8): one-pass instruction cited for AC-8..AC-10, plain morning decision list, ADR pointer, glossed exclusions, typed must_haves.
- Approved baseline retained: N-1 structural tests/order/failure lines and pointer nonduplication; N-2 literal saved-source quotation checks; N-3 blind with/without comparison; N-4 planted/empty/off-topic/clean checker controls; N-5 separate skill-read and skill-followed evidence.

Close-out: fill only when the work closes.

- Size: pending lines changed / files changed.
- Revisions: plan pending / result pending.
- Review rounds to pass: pending.
- Unmet criteria at close: pending; TR-6 currently open, AC-8 through AC-10 awaiting confirmation.
- Releases and observed effect: pending; prepared manifests, tests and procedure documents alone establish neither.
