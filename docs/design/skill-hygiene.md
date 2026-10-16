---
id: SKILL-HYGIENE-MAE222
linear: [MAE-222]
date: 2026-10-17
---

# Skill hygiene (MAE-216 C5, steps 2-7)

Scope: `plugins/maeng-tools/skills/` and `plugins/maeng-harness/skills/` only. Nothing was committed. Deleted files remain in git history (`git show HEAD:<path>`). Line counts are `wc -l` of `SKILL.md`, before (HEAD) / after.

## New skills

| Skill | Lines | What |
|---|---|---|
| `aside-collect` (maeng-tools) | 73 | 자료수집. Fixed ITEM template, `aside exec` with default Guard permission and closed stdin, raw + sidecar under `raw/aside/`, last-run-only parse, source notes `S-<slug>` deduped by canonical URL/DOI, index note, one `session resume` retry. Scripts: `scripts/parse_aside.py`, `scripts/test_parse_aside.py` (8 tests). Pipeline from design 5.9 and `aside-smoke-2026-10-17.md`. |
| `aside-research` (maeng-tools) | 40 | 리서치. Scope, collect (via aside-collect), researcher verification, cited judgment with confidence, `DRAFT-` note, `maeng-review` with a devil's-advocate lens, at most 2 revise loops, finalize (Notion Sol medium personal; eta Docs in eta world). |

Trigger wording is pushy in both descriptions; each names the other as the redirect target.

## Changed skills

| Skill | Before / after | Changed | Removed and why |
|---|---|---|---|
| `harness-run` (maeng-harness) | 375 / 55 | Rewritten for Claude Code per design 5.7: interview, mandatory rules, Middleman, task tree, Spec+Plan (`must_haves`, `AC-n`, Verification, `D-n`), `maeng-verify bind`, `maeng-tools:implementer`, verification (5.3), self-record (5.4), review tiers (4), `maeng-ship merge`, outcome records. Detail moved to `references/{workflow,spec-plan,verification,review-and-ship}.md`; the visual-artifact routing section of the old README is kept as `references/visual-artifacts.md`. | See "harness-run removals" below. |
| `work-records` (maeng-harness) | 373 / 61 | Closeout changed from "user approves the exact draft" to the Sol flow (design 3.4): payload `publish/<id>.json`, `maeng-review` Sol medium, fix and re-review, pending journal, publish exact payload, readback, backlinks, link only to the user. Linear and Obsidian need no approval. The Project/task workflow moved to `references/project-task-workflow.md`, Middleman to `references/middleman.md`, Notion locators and schema to `references/notion-records.md`. The `## Project/task workflow` and `## Middleman code questions` headings stay so links from task-brief and execute-code-brief resolve. | Codex mechanics: `work_records.py` propose/presented/decide/saved/linked/reviewed/finalized, `CODEX_THREAD_ID`, entry receipt, tool-gate and provider-adapter text, Stop-reminder text, standing-maintenance grants and approval-reference plumbing (all replaced by the Sol flow). Endix: the END-629 link and OPS-F2-62 citation. Middleman stays as the user's personal Linear convention with its personal locator. |
| `harness-run/references/work-records/SKILL.md` | 373 / removed | Replaced by `references/work-records-pointer.md` that points at the top-level skill. | An identical nested copy would diverge. |
| `obsidian-workspace` (maeng-tools) | 90 / 94 | New `references/claude-edition.md`: world rule (`world: eta`, under `hubs/projects/P-ETA.md`, never promoted to personal Notion or linked from personal Linear), folders `wiki/decisions|drafts|reviews|sessions` with unique id formats, keys `linear|world|notion|commit|session`, 3-layer retrieval, `<private>` and opt-in regex redaction. New `scripts/private_filter.py` + `test_private_filter.py` (3 tests). SKILL.md gets a pointer section and a boundary sentence that records are written without asking. | Nothing. Existing scripts untouched. |
| `frontend-guidance` (maeng-tools) | 45 / 19 | Kept only the deltas over the official `frontend-design`: user inputs win, preserve product facts, surface-dependent emphasis, Korean UI via `hangul-wrap`, verify the rendered result, HTML decks go to `frontend-slides`, dither-motion archive pointer, UI-audit route. Description made a "Use when..." trigger. | Cut: the generic "advisory, not mandatory" preamble; the long skill-acquisition procedure (upstream fetch, pinning, skill-installer, overlap and installation rules) which is Codex-era plumbing; generic hierarchy/type/spacing/color/motion advice that `frontend-design` already carries. `references/` unchanged. |
| `aside-browser` (maeng-tools) | 15 / 24 | Version 4. Routes only to Aside (logged-in sessions, memory, history, `mcp__aside__*`); explicit hand-offs to aside-collect/aside-research, and generic browsing to the built-in browser, Claude-in-Chrome and `playwright`; Guard-permission safety note. The `aside guide` entry-point wording is kept. | Cut: the broad "Read when you need a browser" trigger. (Lines grew because routing and safety text were added; the scope shrank.) |
| `skill-feedback` (maeng-harness) | 20 / 18 | Kept correction capture (fix first, classify, edit the canonical source, check, ship via the normal route). Evals, benchmarks and description tuning delegated to `skill-creator`. | Cut: the "personal skill publication" standing authorization (direct default-branch publication, byte comparison against a remote, symlink-alias verifier) because it contradicts the gated ship route in design 4/5.2. |
| `diagram-explainer` (maeng-tools) | 406 / 278 | Moved to `references/`: `visual-type-guide.md` (45-type table), `anti-patterns.md`, `pre-output-checklist.md`; each leaves a pointer. Description starts with "Use when...". | Nothing deleted; relative links in moved text were rewritten. |
| `frontend-slides` (maeng-tools) | 382 / 225 | Moved to new `references/`: `style-discovery.md` (Phase 2), `share-and-export.md` (Phase 6); pointers left. Description rewritten as a "Use when..." trigger. | Nothing deleted. |
| `graphify-repository` (maeng-tools) | 17 / 17 | Script fixes below; SKILL.md and `references/local-evidence.md` document them. | See below. |

All SKILL.md files in both plugins are under 500 lines (largest: `diagram-explainer` 278). No moved reference file exceeds 300 lines, so no TOC was needed; `obsidian-workspace/references/claude-edition.md` has one anyway.

## harness-run removals

Deleted (Codex-only or Endix-specific; all recoverable from git history):

| File | Lines | Why |
|---|---|---|
| `scripts/ledger.py` | 1363 | Codex SQLite/JSON task ledger; design 5.7 says the ledger and prepare-tool are not ported. Linear, session state and hooks replace it. |
| `scripts/tool_hook.py` | 1244 | Codex tool-gate bridge (`prepare-tool`, `CODEX_THREAD_ID`, `exec_command`, `mcp__codex_apps__`). Replaced by plugin hooks G1-G3. |
| `scripts/work_records.py` | 972 | Codex work-record state machine (propose/decide/saved/linked). Replaced by the Sol flow. |
| `scripts/run.py` | 208 | CLI front end of the ledger. |
| `manifest.json` | 14 | Hash manifest of the Codex release. |
| `agents/openai.yaml` | 4 | Codex agent metadata. |
| `references/README.md` | 994 | Codex install, model routing for Luna/gpt-6, four runtime hooks, ledger CLI, publication permissions, Endix ownership checks. Two parts survive: the visual-artifact routing section (now `references/visual-artifacts.md`); the consolidated Task brief and Execute-code-brief sections duplicate the standalone `task-brief` and `execute-code-brief` skills. |
| `references/NOTION-WORKSPACE.md` | 223 | Old Codex approval policy contradicts the Sol flow. Its locators and Runs/Knowledge schema live on in `work-records/references/notion-records.md`; the Codex Task field is noted as historical. |
| `references/work-records/SKILL.md` | 373 | Duplicate of work-records. |

Grep check: `exec_command|CODEX_THREAD_ID|mcp__codex_apps|END-629` finds nothing under `skills/harness-run` or `skills/work-records`.

## graphify-repository fixes (design 5.9)

- Persistent `cache_root`: default `~/.cache/maeng/graphify/<sha256(repo)[:16]>`, override `--cache-root`; passed to the worker instead of the per-index `--out` directory. Recorded in the snapshot.
- In-scope dirty check: `git status` is limited to the included paths minus excludes, and ignores the `--out` and cache directories. Snapshots record `status_scope: in-scope`; older snapshots rebuild once.
- Pin unchanged at 0.9.85 (`PIN_VERSION`, `PIN_REVISION`); the worker now reads the version from its argv. A TODO in the script and a "Version bump (not done)" section in `references/local-evidence.md` say that moving to 0.9.91 needs the revision gate re-checked first. Nothing was downloaded.
- `run_worker` was split out so tests mock it. `scripts/test_index_repository.py`: 11 offline tests, graphify not installed.

## Not done here

- `task-brief` and `execute-code-brief` still say Codex/ChatGPT Work; they were out of this task's list.
- `linear`, `notion-authoring`, `error-fix-manual-1`, other craft skills: untouched.
- `obsidian-workspace/references/local-vault.md` still describes the Codex-era MCP route and install paths.
- Pre-existing: `obsidian-workspace/scripts/test_convert_source.py` errors without the `docx` module (1 error in 65 tests, same as before).
