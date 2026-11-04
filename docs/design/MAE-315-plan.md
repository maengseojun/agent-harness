# MAE-315 Spec/Plan-lite: the school's BAZE gateway for Jev and Argon

Linear: MAE-315. Date: 2026-11-04.

Goal: compare Jev with `gpt-6-luna` on the existing evals, and let the user call Gemini 4 Argon and other gateway models on request.
Deliverable: one PR against `feat/harness-v1`: a Jev path in the `decisions` client, and a small `baze` skill with a test.
Source: the user's request of 2026-11-04. The university gives a BAZE key with 5,000 credits a month (renews 2026-12-01).
Decisions: D-1 per-call use, not the gateway's setup prompt. That prompt exports the key in the shell profile and points all of Claude Code at the gateway, while the user wants Claude and OpenAI on their subscriptions. Wrong if: the user wants the whole agent on BAZE.
D-2 Jev answers are converted to the OpenAI shape inside `decide`, so no caller changes. Wrong if: a caller needs a Jev-only field.
D-3 `gpt-6-luna` stays the default. The Jev switch is `MAENG_DECISIONS_MODEL`, for comparison runs. Whether to change the default is the user's call on Sunday.
Assumptions: A-1 eta content is not sent to BAZE until the user says so. D-7 of MAE-306 covers OpenAI only. The client and `ask.py` enforce it: nothing goes to BAZE from the eta checkout or when the text mentions eta or Endix. A false hit only means no answer. The comparison ran on notes with no eta mention.
A-2 Solar and other gateway models need no code: `ask.py --model`.
A-3 The key lives only in the keychain item `baze-api-key`.
Owns: `plugins/maeng-tools/skills/decisions/` (client, its test, SKILL.md), `plugins/maeng-tools/skills/baze/`, `plugins/maeng-tools/.claude-plugin/plugin.json`, this file.
Exclusions: no change to Claude Code or Codex settings, no shell profile edit, no Baze CLI install. No retry in `ask.py`, since a call can spend credit.

- **AC-1** With a `jev-*` model, `decide` posts the gateway's format to the gateway with the `baze-api-key` key, in batches of 32, and returns the same answer shape; a failed batch, malformed answer, missing key or eta material gives `unknown`, never a verdict, and eta material sends nothing; the ledger records the model and Jev's price. The OpenAI path is unchanged.
- **AC-2** `ask.py` sends one chat call with the keychain key, prints the answer to stdout and tokens to stderr, masks secret formats, and exits 1 on a failure or an empty answer.
- **AC-3** A live comparison of Jev and `gpt-6-luna` on the claim and related evals is recorded here, with no eta text sent to BAZE.
- **AC-4** maeng-tools is 0.3.16 and `claude plugin validate plugins/maeng-tools` passes; no change under `plugins/maeng-harness` or `harness/`.

Routing: write in this session; review Sol high with `--kind code --pr N`.
Verification tier: code.
Verification:
- AC-1: `python3 -m unittest discover` in `skills/decisions/scripts`
- AC-2: `python3 -m unittest discover` in `skills/baze/scripts`, and one live call on Argon and on Solar
- AC-3: the results below
- AC-4: `claude plugin validate plugins/maeng-tools`, `git diff --stat origin/feat/harness-v1...HEAD -- plugins/maeng-harness harness`, `python3 -m pytest -q`

Results, 2026-11-04, Jev 1.14.0 through BAZE against `gpt-6-luna` on the OpenAI key:
- Claim eval: on the 263 claims both engines judged, a tie: 141 of 144 false claims caught (natural 5 of 6) and no true claim flagged. They miss different mutations. A second Jev run on the final client missed one more (4 in all), so a gap of one or two claims is noise. Jev left 29 claims `unknown` because 3 pages pass 64,000 characters. p50 per request: Jev 1,172 ms, Luna about 300 ms.
- Related eval, 40 cases from the 511 notes with no eta mention (Korean 30, other 10): AUC 0.974 against 0.957. Reading 30% of candidates, recall is 0.906 against 0.914; reading 40%, 0.978 against 0.942. Jev gains mostly on non-Korean notes; on Korean notes Luna is ahead at 25 to 30% and level at 35%. p50 2,525 ms against 484 ms. Cost $0.014 against $0.042.
- At the 0.05 threshold Jev selects 96.5% of candidates, so a threshold must be set for it.
- These are small sets written by the agent, so this is direction, not a verdict.

Next, not built: embeddings work (`qwen3.7-text-embedding`, 1,024 dimensions, one live call) and could narrow vault and Linear candidates before Decisions. `qwen3-rerank` returned 404 on this account and is not in its model list, so a rerank step needs the school to open it, or another way to rank. Kimi, Qwen and DeepSeek chat models are also not on this account. Exa search works through the gateway.

Revisions:
- R-1 plan scope (2026-11-04): the user left Solar to judgment (`ask.py --model`, no code) and asked to keep rerank and embeddings as context, recorded under Next.
- R-2 result (2026-11-04): first review. Structured input reaches Jev as text; score probabilities carry numeric levels and labels; an answer of another type is `unknown`.
- R-3 result (2026-11-04): Codex finding on the first head. The eta rule moved from skill text to code, because `MAENG_DECISIONS_MODEL` left set would have sent `records.py` text to BAZE.

Close-out:
- size: (filled at close)
- revisions: plan 1 / result 2
- review rounds to pass:
- unmet AC at close:
