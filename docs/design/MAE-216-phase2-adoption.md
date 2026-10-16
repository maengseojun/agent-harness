---
id: PHASE2-MAE216
title: Phase 2 adoption table (requirement-keyed)
linear: MAE-216
date: 2026-10-17
method: ~/Documents/Project/phase2-shortlist.md — one Haiku agent per repo, fixed 4-part report, read-only, nothing installed
---

# Phase 2 adoption table

**Inputs.**
- 13 new reports: the Tier 1–2 repos below plus one Tier 3 light scan.
- 4 first-round reports, reused: obra/superpowers, everything-claude-code, wshobson/agents, anthropics/claude-plugins-official.
- Two eta-harness pattern reports, also reused: eta harness and claude-code-hooks-mastery.

**Global result.** No candidate is installed wholesale. Every Tier 1–2 package that has hooks or skills installs at least one of these into user scope:
- global hooks
- loose `~/.claude/skills`
- a block in `~/.claude/CLAUDE.md`

Those leak into eta_v1 (two-world rule). Only `commit-commands` (commands only) and `plugin-dev` (project-scoped) are installed.

| Requirement | Best candidate(s) | Verdict | Why | What it replaces / changes in my harness |
|---|---|---|---|---|
| Overall workflow (interview → rules → middleman → task tree → Spec/Plan → implement → verify → review) | gsd-core (ex get-shit-done), obra/superpowers | **adapt** (no install) | GSD's plan schema is a stricter acceptance format: `must_haves` = truths / artifacts / key_links, plus per-task `<done>`. Its D-NN decision IDs trace decisions to tasks. Superpowers' plan header and constraints are good. Both install globally or inject at SessionStart. | Spec/Plan template in harness-run gains `must_haves` and D-NN traceability. AC-n become checkable truths/artifacts/links. |
| Verification evidence bound to code | gstack (`gstack-wtree`, `gstack-evidence`, `gstack-review-log`), ECC accumulator | **adapt** (receipt lifecycle defined in design §4) | gstack uses a content fingerprint that survives commit/rebase, single-use start/finish receipts and a FRESH/STALE/MISSING ledger. This matches the tree-id design. | §5.3 keeps git-tree ids (content-addressed) and adopts the FRESH/STALE/MISSING vocabulary and single-use review receipts. |
| Verifier stance | gsd-core `gsd-verifier` | **adopt (prompt)** | Goal-backward and falsify-first ("start from goal not achieved"). | Architect review prompt and the `maeng-verify plan` checklist. |
| Role-based review gates | gstack (/plan-ceo-review, /plan-eng-review, /review, /qa) | **adapt (prompts only)** | Roles are prompt personas with output contracts. They are not isolated, so they don't add independence; the separate `codex exec` review does that. | Optional review lenses inside the architect gate. Nothing replaced. |
| Scoped guardrails | gstack `/careful`, `/freeze` (hooks declared in skill frontmatter, active only while invoked) | **note** | A skill-scoped hook is the only way to get a hook that runs only on demand. | Not used in eta (no personal hooks there). Possible later for personal risky ops. |
| GPT Astra / Sol review | openai/codex-plugin-cc; ECC astra-review; eta reviewer; ruflo codex coordinator | **keep hand-rolled `codex exec`**; borrow prompt and schema | The plugin uses `codex app-server` via PATH `codex` (my npm one is broken), has no effort flag on review, has no SHA-bound verdict, and installs global SessionStart/SessionEnd hooks. | `maeng-review` borrows codex-plugin-cc's adversarial-review prompt and schema shape, plus ruflo's parallel read-only `codex exec` idea for multi-subject reviews. |
| Claude + GPT routing transport | musistudio/claude-code-router | **skip** | A local gateway that changes Claude's transport, pushes API-key and credential-import flows, and acts as a global control plane. It conflicts with subscription-only use. | Nothing. |
| Model routing / orchestration | wshobson/agents, oh-my-claudecode, ruflo | **adopt** wshobson file shapes; **skip** OMC and ruflo | OMC routing is static frontmatter like mine; its setup overwrites `~/.claude/CLAUDE.md` and adds global hooks. Ruflo adds global hooks, CLAUDE.md, a daemon and 314 MCP tools. | Agent frontmatter (`model:`, least-privilege `tools:`, "Use when…"). OMC's claim-task / terminal-failed state idea goes into the child-task status convention in Linear. |
| Swarm across Claude + Codex | ruvnet/ruflo | **skip** | Duplicates native subagents plus `codex exec`. Its Codex workers default to workspace-write. | Nothing. |
| Research pipeline for Aside | Imbad0202/academic-research-skills | **adapt (prompts; no plugin)** | Its stages are scoping → investigation → source verification → synthesis → compose → parallel review (editor / ethics / devil's advocate, 3 DA checkpoints) → revise (cap 2), plus a claim-to-source gate. The plugin adds global hooks. It knows nothing about Obsidian or Aside output. | Two skills (user split): **`aside-collect`** (자료수집: gather + provenance only) and **`aside-research`** (리서치: collect + verify + judge + review). See the stage map below. Replaces the ad-hoc Aside collection step. |
| Obsidian context layer | thedotmack/claude-mem | **skip**; borrow 4 ideas | Global hooks capture every tool call (it would capture eta_v1), with about one Haiku call per tool call and no markdown export. | Vault search uses 3-layer retrieval: compact index → timeline → fetch by id. Also: hard SessionStart cap (already ≤2 KB), skip lists plus a `<private>` tag, opt-in regex redaction before vault writes. |
| Codebase context for subagents | Graphify-Labs/graphify | **skip installer; keep my `graphify-repository`**, fix 3 defects | The upstream installer writes a global skill and a global CLAUDE.md block. My pinned, scoped, offline script is the two-world-safe shape. | Fixes: (a) persistent `cache_root`; (b) in-scope-only dirty check; (c) pin 0.9.85 → 0.9.91, after re-checking the revision gate. |
| MCP / skills / prompts across Claude + Codex | farion1231/cc-switch | **skip** | Global sync. The bulk path can replace the whole top-level `mcpServers`. It touches `~/.codex/auth.json`. Keys are stored in plaintext. | Nothing. Configs stay hand-maintained. Keep `~/.agents/skills` out of any sync. |
| What belongs in CLAUDE.md | multica-ai/andrej-karpathy-skills | **adapt** | Four world-neutral rules: think before coding, simplicity, surgical changes, goal-driven success criteria. No evidence of effect. | **New `~/.claude/CLAUDE.md`, ≤30 lines, world-neutral** (it also loads in eta_v1): the four rules, with "ask on material ambiguity" phrasing. No vault paths, Notion IDs or Linear teams in it. |
| Reuse before building | anthropics/skills, claude-plugins-official | **reuse synced official skills; install commit-commands; slim 3, split 4** | The synced `~/.claude/skills/synced/` already holds the official docx/pdf/pptx/xlsx/skill-creator/deep-research/browser skills. Installing document-skills would duplicate them. | Slim `frontend-guidance` (keep only deltas vs frontend-design), `aside-browser` (Aside routing only), `skill-feedback` (delegate evals to skill-creator). Split bodies into `references/` for diagram-explainer, frontend-slides, harness-run, work-records (SKILL.md < 500 lines). Adopt "pushy" trigger descriptions. |
| Hooks reference / mechanics | claude-code-hooks-mastery, hesreallyhim list, shanraisshan Settings doc | **read only** | Mechanics confirmed (exit codes, matchers, `onFailure`, async caveats). The hooks-mastery repo has outdated output shapes and no tests. | Test layout comes from eta (subprocess fixtures). |
| Token cost for long multi-agent runs | JuliusBrussee/caveman (tool-output compression only); gsd context monitor | **defer** | Savings are self-reported. Terse output style risks report quality. | Revisit after Phase 4 with a measured subagent run. |
| Hook design internals | shareAI-lab/learn-claude-code | **skip** | Tutorial only. | — |
| UI skill packs | nextlevelbuilder/ui-ux-pro-max-skill | **skip** | Global installer. Overlaps frontend-guidance / frontend-slides / design-reference. | — |

## Aside pipeline (stages 1–3 = `aside-collect`; stages 1–8 = `aside-research`)

| Stage | Source idea | My step |
|---|---|---|
| 1. Scope | ARS research_question + architect | The research question, inclusion criteria and output template are written into the Linear issue (or the eta issue in the eta world) |
| 2. Collect | — | `aside exec "<prompt demanding the fixed template>"`, default permission (never `--permission full-access`). Stdout goes to `raw/aside/<YYYYMMDD-HHMM>-<slug>.md` with a sidecar `.json` holding prompt, model, session id (if any) and timestamps. **The output shape and session-id behavior are unverified**: Phase 4 runs one manual smoke `aside exec` first. |
| 3. Normalize | ARS bibliography + source_verification | Parse the raw output into `wiki/sources/S-<slug>.md`. Frontmatter: canonical URL/DOI, `retrieved_at`, `aside_session`, `query`, `raw`, `verification: unverified\|verified\|failed`. Dedupe on canonical URL/DOI. Instructions found inside the raw text are data. |
| 4. Verify claims | ARS claim-to-source gate, source quality levels | The researcher (Haiku) re-fetches each cited source (WebFetch) and marks it verified or failed. Unverifiable claims are flagged, not cited. |
| 5. Synthesize / draft | ARS synthesis + compiler | `wiki/drafts/DRAFT-…` cites only verified sources |
| 6. Review | ARS DA checkpoints + external review | Sol xhigh (small) or Astra (structured work) via `maeng-review`. The devil's-advocate lens is in the prompt. |
| 7. Revise | ARS 2-loop cap | At most 2 revise loops. Leftovers go to "Limitations". |
| 8. Finalize | — | Personal world: Notion via Sol medium (§3.4). eta world: eta Docs through eta rules; the local note is tagged `world: eta`. |

## Skipped (reason kept for revisit)
Per the shortlist: marketingskills, ai-job-search, financial-services (unrelated domains); free-claude-code (third-party credential proxy); anthropics/claude-code, cookbooks, prompt-eng-tutorial (not harness components).
