# MAE-306 Spec/Plan: Decisions API trial week

Linear: MAE-306 (parent), MAE-304 (claim verification), MAE-308 (review pre-flight), MAE-309 (chunk picker, stretch). MAE-307 (risk guards) canceled. Date: 2026-11-04. Source: MAE-303 research; the Linear documents "Spec/Plan: Decisions API trial week" and "Spec/Plan: Decisions API pilot (claim verification)". This file is the current version; it supersedes both where they differ (R-2).

Goal: run the OpenAI Decisions API (`POST /v1/decisions`, `gpt-6-luna`, paid from the ChatGPT Pro API credit) inside the personal harness for the rest of the week, measured against criteria fixed now, so the user can keep, change or drop each use on Sunday 2026-11-08.

Deliverable: one PR adding the skill `plugins/maeng-tools/skills/decisions/` (client, ledger, claim verification, eval, review pre-flight, report), the aside-research stage 3 change, and the maeng-tools 0.3.14 bump. Installed on Thursday after `승인 #N`. On Sunday: a report from the ledger and a CEO brief in Korean with one keep/change/drop question per use.

Decisions:
- D-1 (user, 2026-11-03) Try it this week and decide on Sunday; accept the extra token use. "이번주 정도 시험해보고 그다음에 일요일에 결정하자", "토큰 소모하는거 감수". Wrong if: none (user decision).
- D-2 (user, 2026-11-04) Research uses Decisions directly; the comparison is against the verdicts of earlier sessions (MAE-303), not a Haiku shadow run. "리서치는 decision 그냥 해도 되지 않나 ... 이전 세션들이 있으니까 그거랑 비교해볼 수 있고". Wrong if: the eval on MAE-303 claims misses the floors in A-2.
- D-3 (user, 2026-11-04) "Risk prevention" is the sample re-check (A-4), not command or content guards; no hooks. "나는 표본 재검사라서 307은 빼도 될듯". Wrong if: none (user decision).
- D-4 Everything lives in one skill directory inside maeng-tools, so deleting it removes the trial; no file under `plugins/maeng-harness` or `harness/` changes. Wrong if: a use needs a harness change.
- D-5 Stdlib-only client (urllib), no SDK. Wrong if: the API needs something urllib cannot do.
- D-6 (user, 2026-11-04) Add Linear, Notion and Obsidian work to the live trial (MAE-311): related-item pick, duplicate check before create, cleanup candidates. "나 linear, notion, obsidian을 정말 자주 쓰거든? 이거에도 붙여서 이용할 수 있지 않을까", "그럼 저것들도 넣고 실사용해보자". Wrong if: the offline related-pick eval misses its floor (AC-9) or live misses exceed the Sunday criterion.
- D-7 (user, 2026-11-04) Eta content may be sent and the skill is used in eta work too: "eta 전송되도 되는데, 나 이 작업 eta 작업에서도 쓸거야". Every eta refusal is removed; `MAENG_DECISIONS=off` stays. Supersedes the eta parts of A-7 and A-9.

Assumptions (A-n; the user approved the plan on 2026-11-03 with "승인, 진행해"):
- A-1 Key: `OPENAI_API_KEY` from the environment, else the macOS keychain item `openai-api-key` (`security find-generic-password -s openai-api-key -w`). Never logged. The user creates and stores the key; the credit is already linked (billing page shows "ChatGPT subscription linked", 2026-11-04).
- A-2 Floors for claim verification, from error costs: negative recall (known-false claims not marked `supported`) ≥ 0.95 with Wilson 95% lower bound ≥ 0.90; over-flag (true claims marked not supported) ≤ 30%; p50 time per page < 2 s. Judgment calls, fixed before the first live run.
- A-3 Eval set: positives are atomic claims the MAE-303 researcher pass verified against live pages or captures; negatives are code-made mutations of positives whose mutated value does not appear in the page text; natural negatives (MAE-303 `not_found`/`contradicted`) are kept. At least 100 positives and 100 negatives.
- A-4 Sample re-check (the risk prevention): every `contradicted` or `not_in_page` verdict goes to the researcher; a seeded random 20% of `supported` verdicts (at least 3 per run) also go; if any sampled `supported` is wrong, the rest of that run falls back to the researcher.
- A-5 Page text: live fetch with urllib, GitHub repo and blob URLs through `raw.githubusercontent.com`, HTML through a stdlib HTML-to-text; if that fails or returns under 500 characters, the S- note body (the Aside extract). Never a WebFetch summary.
- A-6 Ledger `~/Documents/maeng-harness/decisions/ledger.jsonl` (override `MAENG_DECISIONS_LEDGER`); page cache `~/Documents/maeng-harness/decisions/pages/`. Input text is stored as a hash and size only.
- A-7 Data rule: only public page text, claim text, and for pre-flight the redacted diff, Plan text and verification output. `MAENG_DECISIONS=off` sends nothing.
- A-8 Pre-flight is advisory: it prints verdicts and never edits files or gates anything; the Sol review runs as before.
- A-9 Records data rule (extends A-7 for MAE-311): Linear, Notion and vault content may be sent, eta included (D-7). Vault `<private>` spans are stripped with obsidian-workspace's `strip_private` before sending. Instructions are English; item text is sent as-is (no translation); the eval reports Korean and other items separately so the Korean question (MAE-304 Phase 2) gets data.
- A-10 Records outputs are suggestions: `related` prints the selected items and the three nearest misses; `duplicate` names a candidate for Claude to open before deciding; `cleanup` lists candidates. Nothing is created, changed or closed by the script.
- A-11 `related` selects at probability ≥ 0.05, not 0.5. The first live eval at 0.5 missed the floor (recall 121/140 = 0.864, selected share 0.25). The floor did not change. The threshold was chosen from the stored probabilities on one seeded half of the cases (21 cases, highest passing threshold) and confirmed on the other half (19 cases: recall 62/64 = 0.969, selected share 0.315). `related` now keeps everything the model is not nearly sure is irrelevant, so it reads about 35% of candidates, not 25%.

Owns: `plugins/maeng-tools/skills/decisions/**`, `plugins/maeng-tools/skills/aside-research/SKILL.md`, `plugins/maeng-tools/.claude-plugin/plugin.json`, this file. The records pilot imports `strip_private` from `plugins/maeng-tools/skills/obsidian-workspace/scripts/private_filter.py` without changing it.

Exclusions: hooks and guards (MAE-307 canceled); the Korean translation arm (MAE-304 Phase 2); image QA; subagent routing; the chunk picker unless everything else is merged first (MAE-309).

must_haves:
- truths:
  - T1: An HTTP error, timeout, refusal or missing answer never becomes `supported`, `met` or any real verdict; it becomes `unknown`.
  - T2: With `MAENG_DECISIONS=off`, no request is sent.
  - T3: The eval runner never opens the label file while building requests.
  - T4: In `decisions` mode no claim is marked verified without passing the A-4 rules.
  - T5: No planted secret appears in a pre-flight request body.
- artifacts:
  - A1: `skills/decisions/scripts/decisions_client.py` - request, parse, `unknown` mapping, key lookup, off check, redaction, ledger, cost estimate.
  - A2: `skills/decisions/scripts/verify_claims.py` - page fetch and text, one request per page with a `choice` question per claim, A-4 routing.
  - A3: `skills/decisions/eval/claims-v1.jsonl`, `labels-v1.jsonl`, `scripts/build_claim_eval.py`, `scripts/eval_claims.py` - eval set and runner with the A-2 report.
  - A4: `skills/decisions/scripts/preflight.py` - per-AC check and finding triage.
  - A5: `skills/decisions/scripts/report.py` - per-use metrics for a date range.
  - A6: `skills/decisions/SKILL.md`; aside-research SKILL.md stage 3 modes.
- key_links:
  - K1: aside-research stage 3 → `verify_claims.py` → client → ledger; routed claims → researcher agent.
  - K2: before `maeng-review run` → `preflight.py` → bound Plan + `git diff` + verification output.

Acceptance:
- **AC-1** Client: parses `choice`, `predicate`, `score` answers; maps HTTP errors, timeouts, refusals and missing answers to `unknown`; sends nothing when off; writes one ledger line per call; redacts planted secrets. covers T1, T2, T5, A1
- **AC-2** Claim verification: one request per page; `supported`/`contradicted`/`not_in_page`/`unknown` per claim; A-4 routing list (seeded, reproducible). covers T1, T4, A2
- **AC-3** Eval: the builder writes at least 100 positives and 100 negatives, byte-identical on a rerun, dropping mutations whose value appears in the page; the runner builds requests without the label file and reports negative recall, over-flag, Wilson intervals, p50 latency, tokens and cost. covers T3, A3
- **AC-4** Pre-flight: one request with a `choice` (`met`/`unmet`/`unclear`) per `AC-n` of the given Plan; diff and verification output always in the input; finding triage (`new`/`repeat`, `this_change`/`pre_existing`/`bypass`); no file writes. covers T5, A4
- **AC-5** Report: per-use counts, outcomes, latency p50/p95, tokens and cost for a date range from the ledger; fixture numbers equal hand-computed values in the test. covers A5
- **AC-6** Skill text: `decisions` SKILL.md says when to run each script and the data rule; aside-research stage 3 has `decisions` (trial default, A-4) and `researcher` modes. covers A6, K1, K2
- **AC-7** No change under `plugins/maeng-harness` or `harness/`; maeng-tools is 0.3.14 and validates.
- **AC-8** Records: `records.py related|duplicate|cleanup` builds one request per call with English instructions; strips `<private>` spans; `unknown` answers are never selected, never named as duplicates and never listed as cleanup candidates; no file writes. covers A-9, A-10
- **AC-9** Related-pick offline eval: a builder makes cases from vault wikilinks (a note's linked notes are relevant, seeded random unlinked notes are not; private content excluded), deterministic on rerun; the runner reports recall of relevant items, share of candidates selected, and both per language (Korean / other), plus recall on positives the task text does not name. Floor for the live trial: recall ≥ 0.9 with selected share ≤ 0.5 overall; the unnamed recall is reported for the Sunday judgment. The case files hold vault text and live outside the public repository (`~/Documents/maeng-harness/decisions/eval/`).

Sub-tasks:

| # | Do | Writes | Interfaces | Done | Fails-if | After |
|---|---|---|---|---|---|---|
| S1 | Client, redaction, ledger | `scripts/decisions_client.py`, `scripts/test_decisions_client.py` | `decide(input, questions, pilot) -> list[answer]`; answer keys `name`, `status` (`ok`/`unknown`), `choice`/`probability`/`score`, `probabilities`, `confidence`; `redact(text)` | `python3 -m unittest test_decisions_client` in `scripts/` OK | an error path returns a real verdict; the off tests pass without asserting that no request was sent; a planted secret survives | - |
| S2 | Report | `scripts/report.py`, `scripts/test_report.py`, fixture ledger | reads the A-6 ledger | test numbers equal hand-computed values written in the test | expected values produced by running `report.py` | S1 |
| S3 | Claim verification, eval builder and runner, eval data | `scripts/verify_claims.py`, `scripts/build_claim_eval.py`, `scripts/eval_claims.py`, tests, `eval/*.jsonl` | consumes S1 | tests OK; `build_claim_eval.py --check` prints ≥100/≥100 and is byte-identical on rerun | a mutation identical to the original; a mutated value present on the page; the runner reads labels | S1 |
| S4 | Pre-flight | `scripts/preflight.py`, `scripts/test_preflight.py` | consumes S1 | tests OK with a fake client: every request carries diff and verification output; no file writes | a request without evidence; a planted secret in a request | S1 |
| S5 | Skill texts and bump | `SKILL.md` (decisions), aside-research `SKILL.md`, `plugin.json` | - | `claude plugin validate plugins/maeng-tools` passes; review item for AC-6 | `decisions` mode can mark verified without A-4 | S1-S4 |

Routing: implement `maeng-tools:implementer` (Sonnet), S1 first, then S3 and S4 in parallel (separate files, both only consume S1), S2 and S5 after; eval data positives written by the coordinator from the MAE-303 verification results; review Sol xhigh (`--kind code --pr N`), at most 4 rounds; live eval by the coordinator once the key exists. Limits: Pro API credit ($67 balance on 2026-11-04).

Verification tier: code (skill scripts; maeng-harness suite untouched).

Verification:
- AC-1: `cd plugins/maeng-tools/skills/decisions/scripts && python3 -m unittest test_decisions_client` expect OK
- AC-2: `cd plugins/maeng-tools/skills/decisions/scripts && python3 -m unittest test_verify_claims` expect OK
- AC-3: `cd plugins/maeng-tools/skills/decisions/scripts && python3 -m unittest test_build_claim_eval test_eval_claims && python3 build_claim_eval.py --check` expect OK and counts ≥100/≥100; live eval report recorded with `maeng-verify ran`
- AC-4: `cd plugins/maeng-tools/skills/decisions/scripts && python3 -m unittest test_preflight` expect OK
- AC-5: `cd plugins/maeng-tools/skills/decisions/scripts && python3 -m unittest test_report` expect OK
- AC-6: declared check: review confirms the two skill texts
- AC-7: `git diff --stat origin/feat/harness-v1...HEAD -- plugins/maeng-harness harness` expect no output; `claude plugin validate plugins/maeng-tools` expect `Validation passed`
- AC-8: `cd plugins/maeng-tools/skills/decisions/scripts && python3 -m unittest test_records` expect OK
- AC-9: `cd plugins/maeng-tools/skills/decisions/scripts && python3 -m unittest test_related_eval && python3 related_eval.py build --check` expect OK and identical (files under `~/Documents/maeng-harness/decisions/eval/`, never in the repo); live run recorded with `maeng-verify ran`

Failure / change handling: three repair cycles per failing check, then cut and name it in the CEO brief. A floor miss in the live eval is a result: report it, keep `researcher` as the default mode, ship the rest.

Review focus: any path to a real verdict from an error; requests with `off`; labels leaking into requests; secrets in pre-flight requests; `decisions` mode skipping A-4.

Sunday criteria (fixed 2026-11-03, P2 removed):
- Claim verification: A-2 floors on the eval set, and in live runs the sample re-check found at most one wrong `supported` per run.
- Review pre-flight: at least one flag was a real defect (listed by the Sol review on the same head or fixed before review) and false flags ≤ 50% of flags; with no PR this week, extend.
- Chunk picker (if built): root-error chunk selected in ≥ 9 of 10 real logs, Claude-read tokens down ≥ 70%.
- Records (MAE-311, added 2026-11-04): related-pick offline floor (AC-9) met overall and reported per language; live `related` misses (an item Claude later needed that was not selected) ≤ 1 in 10 uses; `duplicate` flags that were real ≥ 50% of flags; `cleanup` suggestions the user or Claude accepted ≥ 50%.
- Cost and token overhead reported, no criterion.

Revisions:
- R-1 plan scope (2026-11-03): MAE-304 folded into the trial week; client shared.
- R-2 plan scope (2026-11-04): guards dropped (D-3), Haiku shadow replaced by comparison with earlier sessions (D-2), one skill instead of a new plugin (D-4), everything through the Thursday plan done now.
- R-3 plan scope (2026-11-04): records pilot added (D-6, A-9, A-10, AC-8, AC-9, MAE-311).
- R-4 result (2026-11-04): first live evals. Claim eval passed all floors. Related eval missed recall at threshold 0.5; default moved to 0.05 (A-11), full rerun recall 133/140 = 0.950, unnamed 58/64 = 0.906, selected share 0.350.
- R-5 result (2026-11-04): first review. Pre-flight refuses to run without evidence; the client treats off-list choices and out-of-range values as `unknown`. The review's eta finding is closed by R-6.
- R-6 plan scope (2026-11-04): eta gates removed (D-7). The related eval now covers every wiki and hubs note. Final runs at threshold 0.05: claim eval passed all floors (recall 0.981, over-flag 0, p50 392 ms); related eval recall 144/149 = 0.966, unnamed 99/104 = 0.952, selected share 0.370, Korean 54/54, other 90/95.
- R-7 result (2026-11-04): second review. Redaction covers a secret on the following lines (YAML block, or one opaque value alone); the note fallback strips `<private>` spans; the mutation check includes the emitted date spelling; malformed answer names and huge numbers stay `unknown`.
- R-8 result (2026-11-04): third review. Redaction covers quoted next-line values; eval requests carry neutral names in a seeded order and a claim never shares a request with its own mutation; the date check covers dotted spellings for every seed format; `related`, `duplicate` and `cleanup` log under their own pilot names. The blinded claim eval gave the same result as before: recall 0.9808, over-flag 0, the same three misses.
- R-9 result (2026-11-04): internal review before the last round. Redaction covers more assignment forms, command flags, the rest of an unquoted line and more token formats; a PEM header alone no longer erases what follows; claim verification keeps named values because page text is public and masking made true and false claims identical; malformed `confidence` and `probabilities` are dropped; a lone surrogate cannot fail a call; a claim eval with an unknown negative cannot pass; pre-flight `triage` needs evidence and an empty diff sends nothing; stage 3 maps `decisions` verdicts to the citation labels.
- R-10 result (2026-11-04): fourth and last review round (fail, cap reached). Redaction covers wrapped and multi-part values; an interrupted eval keeps its completed calls in the main ledger. These two fixes have no independent review.
- R-11 result (2026-11-04): internal Fable review, at the user's request. No blocker. A bracketed value ends at its closing line, a zero-indent context line ends a block, a PEM block must hold only body characters, `_PASS`, passphrase and webhook names plus Slack webhooks and JWTs are redacted, a cut ledger line is skipped and counted. No independent `maeng-review` of this either.

Close-out:
- size: (filled at close)
- revisions: plan 4 / result 7
- review rounds to pass:
- unmet AC at close:
