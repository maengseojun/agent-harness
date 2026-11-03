---
name: decisions
description: Use during the OpenAI Decisions API trial (MAE-306, until the user's decision on Sunday 2026-11-08) - verifying research claims against their pages in aside-research stage 3, a review pre-flight before every `maeng-review run` (are the Plan's AC-n met by the diff and the verification output), sorting a failed review round's findings, the claim eval, and the trial report. Personal world only. Sends public page text or a redacted diff, Plan and test output to OpenAI; never runs in an eta checkout.
---

# decisions (Decisions API trial)

Trial skill for MAE-306. The OpenAI Decisions API (`POST /v1/decisions`, `gpt-6-luna`) answers bounded questions (choice, predicate, score) with probabilities, fast and cheaply, paid from the ChatGPT Pro API credit. Plan and criteria: `docs/design/MAE-306-plan.md` in agent-harness. On Sunday 2026-11-08 the user keeps, changes or drops each use; until then use it where this file says.

## Rules

- **Data.** Only public page text and claim text, or for the pre-flight the diff, the Plan and the verification output. The client redacts known secret patterns before sending. Nothing from vault notes beyond a source note's own page extract.
- **Off and eta.** `MAENG_DECISIONS=off` sends nothing. A working directory inside the eta checkout (`MAENG_ETA_ROOT`, default `~/Documents/Project/eta_v1`) sends nothing; eta research keeps the researcher path.
- **Key.** `OPENAI_API_KEY`, else the macOS keychain item `openai-api-key`. Never print it, never ask the user to paste it into the chat.
- **Unknown is not a verdict.** An error, timeout, refusal, missing or off-list answer comes back as `unknown`. Treat it as "not checked", never as a pass.
- **Ledger.** Every call appends one line to `~/Documents/maeng-harness/decisions/ledger.jsonl` (hashes and counts, no text). The Sunday report is computed from it.
- **Advisory.** Nothing here gates or replaces the Sol review, the researcher re-check or the user's decisions.

Scripts are in this skill's `scripts/` folder; run them with `python3 <this skill>/scripts/<name>`.

## Claim verification (aside-research stage 3, `decisions` mode)

1. Write the claims you intend to cite as a JSON list `[{"id": "c1", "claim": "...", "url": "...", "note": "wiki/sources/S-....md"}]` (one atomic claim each: one number, one name, one statement).
2. `python3 verify_claims.py claims.json --seed <n> --out result.json`. One request per page; verdict per claim: `supported`, `contradicted`, `not_in_page` or `unknown`. Page text comes from the live page (GitHub and PyPI through their raw or JSON routes), else the source note's extract; never a WebFetch summary.
3. Sample re-check (the risk prevention): send every id in `route` to the `researcher` agent as in the `researcher` mode. `route` holds every verdict other than `supported` plus a seeded 20% sample of `supported` (at least 3).
4. If the researcher finds any sampled `supported` claim wrong, re-check every remaining claim of that run with the researcher.
5. Record in the source note `verified_via: decisions` (claims only Decisions checked), or `decisions+researcher` (re-checked). Note the run's numbers for Sunday on the research issue: claims, routed, sampled wrong.

## Review pre-flight (before every `maeng-review run`)

1. Save the latest verification output to a file (the test run's output).
2. `python3 preflight.py ac --plan <docs/design/MAE-n-plan.md> --base <base ref> --evidence <file>`.
3. Read the table. Fix a clear `unmet` before requesting the review; leave `unclear` for the reviewer. Never skip or delay the review because of a `met`.
4. After the review, add one line to the bound Linear issue: which `unmet` flags the review also raised or you fixed (real) and which were wrong (false). The Sunday criterion counts these.

After a failed round, `python3 preflight.py triage --findings <this round.json> --previous <earlier round.json> ...` sorts each finding into new or repeat, and this change, pre-existing or approval bypass (the review-round rule).

## Eval and report

- `python3 build_claim_eval.py --check` validates the eval set (claims verified in MAE-303 plus code-made false variants).
- `python3 eval_claims.py --out <report.json>` runs the claim eval against the plan's floors (coordinator, once per client change).
- `python3 report.py --since 2026-11-05 --until 2026-11-08 --eval-report <report.json>` prints the per-use metrics for the Sunday brief.
