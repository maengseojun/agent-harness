# Model notes for placement

Baseline: 2026-10-31. Refresh it when it is older than 30 days, or when a local list below changes. Re-check the sources at the end, note what changed, and keep the old row until the new evidence is at least as strong. Almost every score here is vendor-reported. Treat the roles as starting guesses, and correct them with the per-row outcomes recorded in Linear.

## Local ids (what the CLIs accept)

| Vendor | Check with | Ids on 2026-10-31 |
|---|---|---|
| Claude | Claude Code model list | `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`, `claude-fable-5-1` |
| Codex | `~/.codex/models_cache.json` (slug list) | `gpt-6-astra`, `gpt-6.1-sol`, `gpt-6.1-terra`, `gpt-6-luna`, `gpt-reserve` |
| Grok | `grok models` | `grok-4.7` (default), `grok-4.7-build-fast`, `grok-4.6`, `grok-4.5` |

## Strengths and default roles

| Model | Reported strengths | Reported weaknesses | Default role here |
|---|---|---|---|
| Opus 5.5 | top of Anthropic's own table (Terminal-Bench 4.0 66.4%, CursorBench 57.8%); clean, fast edge-case handling in one hands-on test; Artificial Analysis coding-agent index 62 | thinking cannot be turned off; delegates and verifies more than a task needs (org-chart.md) | coordinator (this session); ambiguous rows, interfaces, integration |
| Sonnet 5.5 | Terminal-Bench 4.0 70.6%; Anthropic positions it for well-scoped everyday work | adds unrequested tests and docs, more at high effort; own review rounds at xhigh/max; skips checks at low effort; used more tokens than Opus in one benchmark | well-specified implementation and tests at medium effort, with "no unrequested files" |
| Haiku 5.5 | cheap; Anthropic positions it as a subagent for summaries and queries | "narrowly scoped" coding only; index 37 | read-only scans, summaries, exact small edits that name the files |
| Fable 5.1 | token-efficient, good on long runs in practitioner reports | expensive; Opus 5.5 beats it on every row of Anthropic's table | parent integration review (high, first; Astra is the standby); workflow audit on the user's request (org-chart.md) |
| gpt-6-astra | OpenAI's frontier model; reported to find more actionable bugs in cross-file review | expensive (about 5x Sol); evidence mostly second-hand | architecture critique before the split, and parent integration review; never an author |
| gpt-6.1-sol | nearly Astra's pass rate at about 1/5 the price (Endor Labs: 77.7% vs 82.1%, faster, no reward hacking found); careful on well-specified changes | 10-30% more output tokens than GPT-6 Sol; xhigh scored better than max | main Codex implementer, test writer, child-task reviewer |
| gpt-6.1-terra | cheap; OpenAI positions it for writing, visual and computer-use work | OpenAI recommends Sol or Astra for complex coding; figures unreproduced | docs and writing rows, UI checked by screenshot |
| gpt-6-luna | cheap, for focused repeatable tasks | Terminal-Bench 4.0 around 13-16%; its predecessor missed edge cases | only with an exact spec; prefer Grok or Haiku for tiny rows |
| gpt-reserve | none found in any public source | unknown | not placed until a source exists |
| Grok Build (grok-4.7) | runs parallel subagents; fast on test writing in one review | slowest in one hands-on test and about 4.5x Sol's tokens; weak Rust and Go; reviews mix Grok versions | tiny leaf rows only (see SKILL.md) |

## Evidence quality (2026-10-31)

Medium: Opus 5.5, gpt-6.1-sol, Fable 5.1. Medium-low: Sonnet 5.5. Low: Haiku 5.5, Astra, Terra, Luna, Grok. No primary X, Reddit or HN threads were found; vendor pages were read through a summarizing fetch.

## Sources to re-check

1. https://www.anthropic.com/news and https://platform.claude.com/docs/en/models
2. https://learn.chatgpt.com/docs/models and the Codex changelog
3. https://artificialanalysis.ai/agents/coding-agents
4. https://www.gradually.ai/changelogs/grok-build/
5. https://flaviocopes.com/ai-coding-models/ (hands-on tests)
6. https://www.endorlabs.com/learn/gpt-6-1-sol-on-codex-astra-level-security-a-third-faster-zero-cheating
