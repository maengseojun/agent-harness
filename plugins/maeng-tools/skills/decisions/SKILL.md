---
name: decisions
description: Use for the uses the user decided on for the OpenAI Decisions API - verifying research claims against their pages in aside-research stage 3, reading the pre-flight and triage that `maeng-review run` prints (are the Plan's AC-n met by the diff and the verification output), picking which Linear issues, Notion pages or Obsidian notes to read when resuming work, a duplicate check before creating a Linear issue, Notion record or vault note, cleanup candidates for the weekly vault or Linear tidy, and the evals. For personal and eta work alike. Sends public page text, a redacted diff, Plan and test output, or Linear/Notion/vault text, eta included (private spans stripped), to OpenAI.
---

# decisions (Decisions API)

The OpenAI Decisions API (`POST /v1/decisions`, `gpt-6-luna`) answers bounded questions (choice, predicate, score) with probabilities, fast and cheaply, paid from the ChatGPT Pro API credit. Plan and criteria: `docs/design/MAE-306-plan.md` in agent-harness. The user decided on the uses below (MAE-320), and the harness makes them run: see "What makes each use run".

## Rules

- **Data.** Public page text and claim text; for the pre-flight the diff, the Plan and the verification output; for records work, Linear, Notion and vault text, eta included (the user's decision, plan D-7). The client redacts known secret patterns; `records.py` strips vault `<private>` spans.
- **Off.** `MAENG_DECISIONS=off` sends nothing.
- **Engines.** By default every question goes to `gpt-6-luna` on the OpenAI key. Jev stays off by default because the school's BAZE gateway adds about 5 credits of masking to every request, whatever the model, and only the school's admin can change that (MAE-319). For a comparison, `MAENG_DECISIONS_MODEL=jev-1.14.0` runs Jev alone (keychain item `baze-api-key`) and `=both` asks both engines at once. With `both`, a choice they agree on is the answer. A choice they differ on comes back `unknown` with reason `disagree`, so the sample re-check sends it to the researcher, who settles it against the source. A probability or score is their mean. If only one engine answers, for example Jev past its 64,000-character limit or without a key, that answer stands. The `related` threshold of 0.05 is set for Luna, so pass `--threshold 0.25` with `both`.
- **Key.** `OPENAI_API_KEY`, else the macOS keychain item `openai-api-key`. Never print it, never ask the user to paste it into the chat.
- **Unknown is not a verdict.** An error, timeout, refusal, disagreement, missing or off-list answer comes back as `unknown`. Treat it as "not checked", never as a pass.
- **Ledger.** Every call to an engine appends one line to `~/Documents/maeng-harness/decisions/ledger.jsonl` (hashes and counts, no text). `report.py` is computed from it.
- **Advisory.** An answer never gates or replaces the Sol review, the researcher re-check or the user's decisions. What is certain is that the check runs, not what it says: an error, an expired credit or `unknown` never stops work.

## What makes each use run

| Use | What makes it run |
|---|---|
| Claim verification | `maeng-review run --kind research` is blocked without `--claims <verify_claims.py --out file>` |
| Review pre-flight, triage | `maeng-review run` runs them itself, is blocked without `--plan` and `--evidence`, and prints them on stderr; the reviewer does not see them |
| Related pick | `maeng-verify bind` refuses until `records.py related` ran in this session |
| Duplicate check | A new Linear issue, Notion page or vault note is denied until `records.py duplicate` ran in the last 30 minutes of this session. Updates, overwrites and machine-made notes (`wiki/sessions`, `wiki/reviews`, `wiki/sources`, `raw`) pass |
| Cleanup | The Monday `vault-weekly-maint` task runs it |

When a search found nothing, run the check with an empty candidate list.

Scripts are in this skill's `scripts/` folder; run them with `python3 <this skill>/scripts/<name>`.

## Claim verification (aside-research stage 3, `decisions` mode)

1. Write the claims you intend to cite as a JSON list `[{"id": "c1", "claim": "...", "url": "...", "note": "wiki/sources/S-....md"}]` (one atomic claim each: one number, one name, one statement).
2. `python3 verify_claims.py claims.json --seed <n> --out result.json`. One request per page; verdict per claim: `supported`, `contradicted`, `not_in_page` or `unknown`. Page text comes from the live page (GitHub and PyPI through their raw or JSON routes), else the source note's extract; never a WebFetch summary.
3. Sample re-check (the risk prevention): send every id in `route` to the `researcher` agent as in the `researcher` mode. `route` holds every verdict other than `supported` plus a seeded 20% sample of `supported` (at least 3).
4. If the researcher finds any sampled `supported` claim wrong, re-check every remaining claim of that run with the researcher.
5. Record in the source note `verified_via: decisions` (claims only Decisions checked), or `decisions+researcher` (re-checked). Note the run's numbers on the research issue: claims, routed, sampled wrong.

## Review pre-flight (`maeng-review run` runs it)

1. Pass the latest verification output with `--evidence <file>` and a `--plan`; a code or parent review is blocked without them.
2. To see the table before spending a round: `python3 preflight.py ac --plan <docs/design/MAE-n-plan.md> --base <base ref> --evidence <file>`.
3. Read the table. Fix a clear `unmet` before requesting the review; leave `unclear` for the reviewer. Never skip or delay the review because of a `met`.
4. After the review, add one line to the bound Linear issue: which `unmet` flags the review also raised or you fixed (real) and which were wrong (false).

After a failed round `maeng-review run` runs `preflight.py triage`, which sorts each finding into new or repeat, and this change, pre-existing or approval bypass (the review-round rule).

## Linear, Notion and Obsidian work (MAE-311)

All three take a candidates file: a JSON list of `{"id", "title", "text", "source", "date"}` built from the search results you already have (Linear issue search, Notion search, vault search). Put a short excerpt in `text`, not whole documents. Outputs are suggestions; you still open, create, update or close things yourself.

- **Resuming work:** after searching for related notes, issues and pages, run `python3 records.py related --task "<what you are about to do>" --candidates <file>`. Read the selected items; glance at the near misses; open anything else you need. When you later needed an item it did not select, note it on MAE-311 (a miss).
- **Before creating** a Linear issue, Notion record or vault note (the search-before-create step of work-records and obsidian-workspace): `python3 records.py duplicate --new "<title and one-line summary>" --candidates <file>`. If it names an item, open that item and decide whether to update it instead. Note on MAE-311 whether the flag was real.
- **Weekly tidy:** `python3 records.py cleanup --candidates <file>` lists items that look superseded or done. Suggest them to the user or check them yourself; never close, archive or delete because of this list alone. Note which suggestions were accepted.

## Eval and report

- `python3 build_claim_eval.py --check` validates the eval set (claims verified in MAE-303 plus code-made false variants).
- `python3 eval_claims.py --out <report.json>` runs the claim eval against the plan's floors (coordinator, once per client change).
- `python3 related_eval.py build --check` and `python3 related_eval.py run --out <report.json>`: the related-pick eval on vault wikilinks, reported for Korean and other notes separately, with recall also on the positives the task text does not name. Its files hold personal vault text, so they live outside the repository (`MAENG_DECISIONS_EVAL_DIR`, default `~/Documents/maeng-harness/decisions/eval/`; the script refuses a folder inside the checkout). agent-harness is a public repository: never commit vault, Linear or Notion text.
- `python3 report.py --since <date> --until <date> --eval-report <report.json>` prints the per-use metrics, per engine.
