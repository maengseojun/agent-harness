---
id: DESIGN-MAE216
title: Two-harness Claude Code environment (personal plugins + eta isolation)
linear: MAE-216
status: approved 2026-10-17 (rev 6.2: Aside split into collect/research; rev 6 Astra pass; after Astra reviews 1–4, Phase 2 rerun and user decisions 2026-10-17)
author: Claude (Opus 5.5), architect
date: 2026-10-17
---

# Two-harness Claude Code environment

## 0. Goal, principle, threat model, terms

**Goal.** Two worlds that never mix.
- **eta world.** `~/Documents/Project/eta_v1`, its worktrees and nested repos, and any checkout the guard classifies as eta.
  - eta's harness (eta-rules + eta-craft) is in charge.
  - **No personal hooks and no personal Linear/Notion record flows.**
  - Allowed personal parts:
    - `maeng-tools`: hookless craft skills, the generic model-routed agents, and `obsidian-workspace`.
    - Local eta logs in the personal vault, tagged `world: eta` (user decision; see §3.3).
- **Personal world** (everything else): the personal harness only, with no eta skills or hooks.

**Principle (user).** Records are autonomous and code is strict.
- **Records.** The agent writes Linear and Obsidian without gates. It publishes to Notion after a Sol review, and the user receives only the link.
- **Code.** Ordinary feature-branch pushes are allowed when the session is verified. Force pushes, pushes to the default branch, tag pushes and every merge are gated. Opening or merging a PR requires verification evidence bound to the exact code being shipped.

**Threat model (user decision).** The agent is cooperative.
- Hooks are **guardrails against mistakes and convenience shortcuts, not a security boundary.** A deliberately disguised route, such as a script with an innocuous name that pushes, is out of scope.
- No server-side enforcement exists: `agent-harness` is private on a free plan, and branch protection/rulesets return 403. GitHub Pro was declined.
- Every guardrail must still deny the *known* routes, and fail closed when a gate cannot decide.

**Terms.**
- **Session state.** Per-session state, keyed by `session_id`.
- **Tree id.** The git tree of the full working tree: `git add -A` into a temporary index, then `git write-tree`. It respects `.gitignore` and includes untracked files.
- **Verification-relevant paths.** Every path *except* the repo policy's `non_code_globs` (`.maeng/verify.json`; default: `**/*.md`, `docs/**`, `**/*.{png,jpg,jpeg,gif,svg,webp}`). Dependency and build inputs (`requirements*.txt`, `constraints*.txt`, `CMakeLists.txt`, lockfiles, configs) are always relevant.
- **Submodules.** A tree id is not taken (and no evidence is recorded) while any submodule is dirty. The evidence record stores each submodule's commit.

Inputs are in the MAE-216 comments: Phase 0–2 results, Astra reviews 1–2 (`docs/design/reviews/`) and user decisions. The verified facts are in §8.

---

## 1. Packaging and scoping

### 1.1 Marketplace and plugins

This repo becomes the marketplace `maeng` (`.claude-plugin/marketplace.json`). It holds two plugins:

| Plugin | Contents | Hooks | Enabled |
|---|---|---|---|
| `maeng-tools` | Craft skills, **agents** (architect, implementer, researcher), **obsidian-workspace** (world-aware) | none | user scope; **ON everywhere incl. eta world** |
| `maeng-harness` | Hooks, personal workflow/record skills, review/verify/isolate CLIs, the 7 craft skills eta-craft also ships | all | user scope; **OFF in the eta world** |

**maeng-tools skills:** aside-browser, ask-claude, blockchain-upstream-review, coherent-writing, design-reference, diagram-explainer, explainer, frontend-guidance, frontend-slides, gh-address-comments, gh-fix-ci, graphify-repository, hangul-wrap, interactive-explainer, manuscript-writing-review, obsidian-workspace, playwright, prepare-work-deliverable, presentation-design-interview, screenshot, tutorial-video, vercel-deploy.

**maeng-harness skills:** harness-run (Claude edition, §5.7), work-records (Sol flow), linear, notion-authoring, skill-feedback, task-brief, execute-code-brief, error-fix-manual-1. Plus the craft skills eta-craft also ships: chart-style, proof-guided-optimization, foundry-testing, solidity-habits, writing-a-vault, writing-an-auction, html-prototype-interview.

**obsidian-workspace world rule.** When the guard classifies the session as eta:
- notes get `world: eta`;
- they are filed under `hubs/projects/P-ETA.md` → `wiki/sessions/`;
- they are never promoted to personal Notion and never linked from personal Linear.

Reading the whole vault is allowed in both worlds.

**Retired** (moved to `_to_delete`): subscription-harness (superseded by §4); endix-workflow (moved in Phase 0).

### 1.2 Staging, release, loose-skill retirement

1. **Staging** (before review and merge). In scratch repos, load the candidate with `claude --plugin-dir <worktree>/plugins/maeng-tools --plugin-dir <worktree>/plugins/maeng-harness`. In eta_v1 (S5), pass **only** maeng-tools; inline plugins can't be disabled by settings. Nothing is installed at this stage.
2. **Release** (after an Astra pass and a merge through `maeng-ship merge`).
   - A release clone at `~/.local/share/maeng/agent-harness` is registered as directory marketplace `maeng`.
   - Both plugins install at user scope.
   - Updates: `git pull --ff-only` → `claude plugin marketplace update maeng` → `claude plugin update …`.
   - A fresh session must show the expected versions, and the installed files must hash-match the release clone.
3. **Retirement.** In this order:
   1. A fresh session shows every planned skill and agent under its namespace.
   2. Quarantine, using an **explicit inventory**: the 29 personal entries listed in `docs/design/retirement-inventory.txt`, generated and reviewed before the move. Moved to `_to_delete/`. **`synced/` (Anthropic-managed official skills) and `_to_delete/` are never moved.**
   - The inventory also covers user-level **agents**: `~/.claude/agents/codebase-explorer.md`. It loads in every project, eta included (staging S5), and `maeng-tools:researcher` replaces it.
   3. A *second* fresh session shows no un-namespaced duplicates and no missing skills, **and still lists the official synced skills** (docx, pdf, pptx, xlsx, skill-creator, deep-research, browser skills).
   4. If that check fails, move the entries back (rollback) and record why.

### 1.3 Isolation from the eta world

1. **eta world = every checkout of an eta repo (D-8).** A Claude session started inside a nested team repo uses that repo as its project root, so settings placed in the `eta_v1` folder never apply there. Isolation is therefore per checkout, not per folder.
   - **Org list:** one constant, `guard.ETA_ORGS = {endix-foundation-v1, endix-labs-v1}` (plus the slug `maengseojun/eta_v1` and the `eta_v1` path prefix). The guard (`spec_is_eta`, `remote_is_eta`, origin classification) and the CLI all read it.
   - **Discovery** (`maeng-eta-isolate`, shared with the SessionStart check): the `eta_v1` folder itself (a plain folder, no git needed); every git repo and linked worktree found by walking it (skipping `_to_delete`, `node_modules`, `.git` internals and submodules, and following `git worktree list` of each repo); and, with `--scan <dir>` (depth <= 4), team checkouts elsewhere, classified by origin org.
   - **Per target** it merges into `.claude/settings.local.json`, keeping existing keys: `maeng-harness@maeng`, `linear@synced` and `commit-commands@claude-plugins-official` set to `false`; `eta-rules@eta` and `eta-craft@eta` set to `true`.
   - **Plugin install:** in `--apply` mode it runs `claude plugin install eta-rules@eta|eta-craft@eta --scope local` with the target as cwd, unless `installed_plugins.json` already has a local/project entry for that path. `MAENG_CLAUDE` overrides the binary (tests use a fake).
   - **Safety:** for a git target it requires `git check-ignore` to pass and refuses tracked files; the non-git `eta_v1` folder needs no check. Default is a dry run that prints the plan as JSON; `--apply` executes and reports per target.
   - It runs at release, and again whenever SessionStart finds an eta checkout whose local settings lack the eta enables or the maeng-harness disable (one warning line, written to nothing).
   - Verified 2026-10-17: a local `false` removed `linear@synced`.
2. **Guard.**
   - `guard.classify(path)` returns `eta` when:
     - the path is under eta_v1;
     - the git `origin` is `maengseojun/eta_v1` or belongs to an org in `ETA_ORGS` (`endix-foundation-v1`, `endix-labs-v1`);
     - or the project settings enable `eta-rules@eta`.
   - The result is cached, keyed by the mtimes of the config files actually used: `git rev-parse --git-common-dir`/`config`, `--git-dir`/`config.worktree` when present, and `.claude/settings*.json`. This works for linked worktrees.
   - **If classification cannot be resolved, the state is `unknown`.**
     - Personal record and context side effects are suppressed, as in eta: no session stub, no SessionStart context.
     - **Every mutating operation covered by G1/G3 is denied** until classification succeeds. The reason tells the agent to fix the repo config or open the session in a resolvable directory.
   - With an eta session, **every handler exits 0 immediately with no side effects.**
   - **One exception:** SessionStart emits a single warning line telling the agent to run `maeng-eta-isolate` and restart. It writes nothing.
3. **G3 cross-world gate** (personal sessions acting on eta). Deny targets that classify as eta:
   - **Local targets:** Edit/Write/NotebookEdit `file_path`; Bash `cd` / `git -C` / path arguments.
   - **Remote targets** (resolved repo identity, including positional destinations such as `git push <url|remote> …` and `gh … <owner/repo>` arguments):
     - `gh … -R <repo>`, or the current repo for `gh pr|issue|release` writes;
     - `gh api repos/<owner>/<repo>/…` write methods;
     - `git push` to a remote whose URL classifies as eta;
     - `mcp__github__*` writes with `owner`/`repo` arguments;
     - eta Linear (`mcp__linear-endix__*`) writes.
   - Read-only access to eta material stays allowed.

Tests assert loaded plugins, skills and agents (stream-json `init`) **separately** from hook side effects.

### 1.4 Reconciling skill sources
Seven skills have diverging copies. For each, the newer substantive copy wins, judged by diff + mtime and recorded per skill. The loser is archived under `archive/2026-10-17-mae216/`. The Codex side is untouched.

### 1.5 Existing plugins
- **Install:**
  - `commit-commands@claude-plugins-official`: user scope, OFF in eta.
  - `plugin-dev@claude-plugins-official`: project scope in this repo.
- **Not installed globally:** superpowers, everything-claude-code, security-guidance, ralph-loop and the wshobson plugins. Their patterns are borrowed (Phase 2 table).

---

## 2. Model routing (agents in maeng-tools, usable in both worlds)

The main session uses `model: opus`. Exact frontmatter:

```yaml
# plugins/maeng-tools/agents/architect.md
name: architect
description: Use when a design, plan, integration decision or internal review gate is needed before implementation or external review.
model: opus
tools: Read, Grep, Glob
---
# plugins/maeng-tools/agents/implementer.md
name: implementer
description: Use when one approved task (with its Spec/Plan) must be implemented and verified. End with "Verification:" and "Unfinished:" sections.
model: sonnet
# tools omitted on purpose: inherits the session's tools
---
# plugins/maeng-tools/agents/researcher.md
name: researcher
description: Use when read-only research or codebase exploration is needed.
model: haiku
tools: Read, Grep, Glob, WebFetch, WebSearch
```

- The agent bodies are world-neutral. In eta, eta-rules skills set the work rules; in the personal world, harness-run does.
- `CLAUDE_CODE_SUBAGENT_MODEL` is never set.
- **Model check** (`tests/live/check_models.py`):
  - find the parent transcript's `Agent` tool calls by `subagent_type` (`maeng-tools:architect|implementer|researcher`), and require ≥ 1 call per type;
  - correlate each call with its `subagents/*.jsonl`;
  - assert the resolved model ID's family (opus / sonnet / haiku).
- **Negative test:** asking architect or researcher to write a file must show no write tool available.

---

## 3. Information architecture

### 3.1 Linear (workspace `maeng`, team MAE): live work map
The agent creates, starts, updates and closes issues; the user never touches Linear.

| What | Where |
|---|---|
| Work | parent issue → child issues, following the user's task tree (§5.7) |
| Middleman questions | existing `Kind → Middleman` convention, linked with blocks/blockedBy |
| Spec / Plan | Linear documents per task. Plans number their acceptance criteria `AC-n`; deeper tasks have finer criteria. |
| Decisions, blockers, progress, review findings | comments |
| Links | attachments: PR, commit, Obsidian paths, Notion record |

**Binding.** The session's binding (`issue`, `plan_doc` + `updatedAt`, `repo`, `world`) lives in session state. It is set by `maeng-verify bind MAE-n --plan <doc>`. `last-bindings.json` holds suggestions only and never drives a gate.

### 3.2 Obsidian: LLM context layer
Vault: `~/Documents/Obsidian Vault`. The existing structure stays.

Additions:

| Path | Holds | Unique id |
|---|---|---|
| `wiki/decisions/` | ADRs | `ADR-<MAE-id>-<slug>` |
| `wiki/drafts/` | Notion-bound drafts | `DRAFT-<MAE-id>-<slug>` |
| `wiki/reviews/` | Review verdicts | `REV-<MAE-id>-<YYYYMMDD-HHMM>-<digest7>` |
| `wiki/sessions/` | Session logs | `SESSION-<MAE-id or none>-<YYYYMMDD-HHMM>-<session_id[:8]>` |

New frontmatter keys: `linear`, `world`, `notion`, `commit`, `session`.

- **Read order:** hub → latest session for the bound issue → linked decisions.
- **Writes:** new files get unique ids; replacing an existing note checks its hash first; shared `log.md` is written only by the agent through MCP.
- **Vault rules.** `AGENTS.md` and `rules/체계구조.md` are updated in Phase 4 under this approval:
  - Notion publishing follows the Sol flow;
  - session stubs and agent self-recording are allowed;
  - eta-world notes are allowed, as §3.3 describes.

### 3.3 eta-world notes (user decision: full logs allowed)
eta work logs and knowledge may be written to the personal vault under P-ETA with `world: eta`, by the agent through obsidian-workspace.

**Recorded conflict.** eta rule OPS-A1-12 (read live 2026-10-17) says "Nothing about eta is kept in a private page or outside the teamspace." The user co-owns that rule ("Henry or 서준") and chose full local logs. The authoritative eta record stays in eta Docs and eta Linear.

eta notes are never promoted to personal Notion and never linked from personal Linear.

### 3.4 Notion: SSOT for final outcomes (personal world)
**Databases:** Runs & Evaluations (outcomes) and Knowledge & Skills (policies).

**Flow:**
1. Turn the Obsidian draft into the exact tool payload `publish/<id>.json`.
2. **Sol review (`gpt-6.1-sol`, medium)** of that payload.
3. On `fail`, fix and re-review.
4. Record a pending entry in a local journal.
5. Publish exactly that payload.
6. Read back; this also reconciles any uncertain result.
7. Write backlinks.
8. Send the user **the link only**.

The Notion `harness-run` page text that requires user approval is revised in Phase 5.

### 3.5 Cold storage: archive and backup (user, 2026-10-17)
The vault is the **hot** tier (what the LLM reads). Google Drive and OneDrive (both on the Korea University accounts) are the **cold** tier: kept, never loaded into context.

| Use | Where | How |
|---|---|---|
| **Archive** of distilled-away material: originals after their key points were extracted, bulky `raw/aside/` dumps, superseded notes, old transcripts | **OneDrive** `maeng-archive/<world>/<YYYY>/…` (local sync folder `~/Library/CloudStorage/OneDrive-고려대학교`) | `maeng-archive move <path>`: copy, then verify sha256, then replace the vault file with a **stub note**. The stub carries the summary, `archive: {store, path, sha256, size, archived_at}`, and keeps its links and frontmatter. |
| **Backup** snapshots of the vault and harness state | **Google Drive** `maeng-backup/` (via Google Drive for desktop once installed), and also OneDrive | `maeng-archive backup`: timestamped zip plus a manifest of hashes, keeping the last N. Restore is a dry run by default. |
| **Search / read** of cloud files | Google Drive | the claude.ai Google Drive connector (verified live, 2026-10-17) |

- eta material is allowed (user decision). It goes under the `eta/` subfolder with `world: eta`.
- Accounts are university-administered. The cold tier never holds the *only* copy of anything essential: archive originals keep their Obsidian stub, and backups go to both clouds.
- Lives in `maeng-tools` (no hooks), so it works in both worlds.
- Nothing is deleted. A vault file is replaced by its stub only after a hash-verified copy exists.

---

## 4. External review (author ≠ reviewer), tiered to the user's workflow

`codex exec` uses the ChatGPT-bundled CLI v0.163; the npm one is broken. Both models were verified live.

| Subject | Codex reviewer | Effort | Claude fallback | Selection rule |
|---|---|---|---|---|
| **Child-task PR** of a structured implementation | Sol `gpt-6.1-sol` | **xhigh** (user, 2026-10-17) | Opus medium | The bound issue has a parent, and the task has a Plan with `AC-n` |
| **Parent integration / boundary review** (child tasks meeting) | Astra `gpt-6-astra` | **high** | **Fable medium** | Bound to a parent issue whose children are merged; reviews the combined diff against the parent Spec/Plan and child contracts |
| Architecture / rules / design docs | Astra | medium | Opus high | Document review |
| **Small implementation** (no task tree) | Sol | **high** | Opus high | No parent/child structure |
| Notion outcome payload | Sol | medium | Opus medium | §3.4 |
| Research draft (`aside-research`, `--kind research`) | Sol | **xhigh** | Opus high | Devil's-advocate lens |

**Codex first, Claude fallback** (user, 2026-10-17; D-9). Codex is always tried first. Only after 3 consecutive failed codex runs (e.g. usage exhausted) does `maeng-review` switch to an isolated headless `claude -p` reviewer (no settings sources, no MCP, no tools) at the fallback tier above, recording `reviewer.fallback_from`. Fable runs only for parent integration, at medium; its effort changes (`MAENG_FABLE_EFFORT`) only on the user's request. `MAENG_REVIEW_BACKEND=claude` skips codex and is set only on the user's request.

**Reviewer configuration** (`maeng-review`; probed 2026-10-17): `--ignore-user-config --ignore-rules`, feature disables (apps, browser, computer_use, hooks, plugins, memories, multi_agent, image), `--sandbox read-only`, `-c approval_policy="never"`, `--ephemeral`, `--output-schema`.

What that gives:
- The reviewer is read-only, not tool-free. It can read files and use model-side web search, but cannot write.
- Anything that needs approval is auto-rejected. Review 1's attempts to reach Aside and Linear were rejected this way.
- Its skill catalog stays visible. The prompt forbids using skills.

**Bundles** (`blocked` if anything required is missing):

| Subject | Bundle |
|---|---|
| Code | repo, PR, base/head SHAs, diff, full changed files, Spec/Plan `AC-n` + `updatedAt`, verification evidence (tree ids, commands, results) |
| Parent | + child Spec/Plans and their merged PRs |
| Docs | doc + digest + the requirements it answers |
| Notion | payload + digest + draft + sources |

**Verdict.** `{verdict, subject{kind, repo, pr, base, head, criteria_rev, digest, destination, op}, reviewer{model, effort}, findings[]}`. It is stored per subject. The agent routes it to a Linear comment and `wiki/reviews/`.

**Receipt lifecycle** (single-use):
- A `pass` receipt is **consumed** only when PostToolUse confirms that the gated action succeeded: the merge push was accepted, or the Notion create/update was read back.
- A failed or rejected action leaves the receipt unconsumed, so the same subject can retry.
- A changed subject (head, base, criteria, digest) needs a new review.
- Consumed receipts are kept and point to the resulting merge SHA or page id.
- **`pending` is persisted before dispatch.** Retry eligibility comes back only after a **confirmed rejection** (e.g. git's "stale info" / non-fast-forward error, or a Notion error response) **or** after reconciliation proves no mutation happened. To prove that, `maeng-review reconcile` checks the remote ref == reviewed base, or that no page exists.
- If the client failed but the remote may have changed (accepted push, lost response), the receipt stays `pending` and cannot be reused until reconcile. Reconcile marks it consumed when the head has been integrated: either the remote ref == head, **or the head is an ancestor of a remote ref that has since advanced** (`git merge-base --is-ancestor`). If neither can be established, the receipt stays `pending`.

---

## 5. Hooks (`plugins/maeng-harness/hooks/`, personal world only)

### 5.1 General
- **Dispatcher:** stdlib Python, every handler **synchronous** with an explicit timeout. The guard runs first.
- **State:** per session, with lock and atomic replace.
- **Gates (G1–G3):** registered with `onFailure: "block"`. They fail closed: a missing or unreadable receipt means deny.
- **Trackers and context:** fail open with a stderr warning.
- **Minimum Claude Code version:** 2.1.301.
- **Known host limit (staging GF4).**
  - `onFailure: "block"` blocks when the gate script exits non-zero, is missing, or times out (verified live: GF1–GF3).
  - It does **not** block when a script exits 0 with malformed JSON. Claude Code then treats the call as allowed.
  - The dispatcher therefore never prints non-JSON on stdout, and it exits 2 on any internal PreToolUse error (unit-tested).
  - A malformed-output failure from outside the dispatcher is out of scope under the cooperative threat model.

### 5.2 Gates
**G1 code-ship.** `gh` writes use an **allowlist**:
- **Allowed without a gate:** `gh pr comment|edit|review|ready|close`, `gh issue *`, `gh pr checkout` (local), read-only subcommands.
- **Allowed with a gate:** `gh pr create`.
- **Denied:** every other mutating `gh` subcommand.

Commands are split into segments (`;`, `&&`, `||`, `|`). A command is **denied when it mentions push, merge or pr-create but can't be parsed, or when it goes through a known wrapper** (`sh -c`, `bash -c`, `eval`). Disguised scripts are out of scope (§0).

| Route | Rule |
|---|---|
| `git push` | Resolve the remote, source commit(s) and destination refs (explicit refspec, `push.default`, upstream). **Deny:** any force form (`-f`, `--force`, `--force-with-lease`, `+refspec`), destination = default branch, tags, `--mirror`, deleting the default branch. **Allow a feature-branch push only if every pushed commit's tree is *ship-verified* (§5.3).** |
| `gh pr create` (and `mcp__github__create_pull_request`) | The head commit's tree must be ship-verified |
| **Merging (the only route): `maeng-ship merge <PR>`** | It performs a **lease-guarded fast-forward push of the reviewed head to the base branch**: `git push --force-with-lease=refs/heads/<base>:<reviewed_base_sha> <remote> <head_sha>:refs/heads/<base>`. The lease makes the **exact reviewed base SHA** an atomic server-side precondition. Any base movement is rejected, including movement to an ancestor of the head. The pre-push ancestry check (base is an ancestor of head) guarantees the update is a fast-forward. **This exact form, issued by `maeng-ship` with a matching receipt, is the only lease or force form G1 allows.** GitHub then marks the PR merged. Before pushing, the command requires: (1) base is an ancestor of head, so the integration tree **is** the head tree; (2) the head tree is **ship-verified**; (3) an Astra/Sol `pass` receipt (tier per §4) for exactly that base and head, with a current criteria `updatedAt`. On rejection it reports "base moved: update, re-verify, re-review". G1 allows a push to the default branch **only** as this exact command form, with the receipt present. |
| (Denied — use `maeng-ship merge`) `gh pr merge` (all modes incl. `--auto`), `gh pr update-branch`, `gh repo sync`, `gh release create/upload/delete`, `gh repo edit --default-branch`, `gh api` merge, ref-write endpoints, **contents API writes (`PUT`/`DELETE repos/*/contents/*`)**, GraphQL mutations (`createCommitOnBranch`, `mergePullRequest`), `mcp__github__merge_pull_request` | Deny; merge only through `maeng-ship merge` |
| `mcp__github__push_files` / `create_or_update_file` | Same rules as `git push` against the target branch |

**D-6, allowlist (PR #38 review round 2).** Shipping and cross-world routes are gated by an **allowlist of canonical forms**, not by parsing arbitrary shell. Any Bash command that mentions a shipping route must be exactly one plain command in one of these forms; anything else is denied by design:
- `git push <remote> <branch|src:refs/heads/x>`
- the restricted `gh pr create` flags
- `maeng-ship merge <N>`
- the read-only gh allowlist

The remote must have a plain config, and its default branch must be known. PR creation verifies the remote head SHA via `git ls-remote`. G3 resolves `--git-dir`/`--work-tree`/`-C` and gh URL arguments, and denies `GIT_DIR` assignments. When the effective directory is **unknown**, every mutation is denied. Reviewers check that the allowlist is closed.

**G2 Sol publish.**
- **Scope:** Notion create-pages into the two databases, plus update-page/update-data on page ids in the registry.
- **Registry:** filled after each readback, and re-seeded from a database query when the agent binds a task.
- **Rule:** requires a Sol `pass` whose digest equals sha256(canonical JSON of the tool input), with the same destination and op.
- **Journal:** an unresolved pending entry (create sent, readback missing) blocks every further G2 write for that subject until `maeng-review reconcile` records the readback (or its absence). The registry is re-seeded at bind time **and** before every publish.
- **Documented limit:** a page moved into the databases from elsewhere is unknown to the registry until the next re-seed.

**G3 cross-world.** See §1.3.

**Never gated:** Linear and Obsidian writes.

### 5.3 Verification and Stop

**Evidence record:** `{cmd, ok, tree_start, tree_finish, finished_at}`.
- `tree_start` is taken at PreToolUse and `tree_finish` at PostToolUse / PostToolUseFailure.
- **The evidence is valid only if `tree_start == tree_finish`**, so the code didn't change during the check. Background commands produce no evidence.
- **Recognized runners:** pytest, `python -m unittest`, `npm|pnpm|yarn test|run lint|run build|run typecheck`, `forge test|build`, `cargo test|clippy|build`, `go test`, `make test|check`, `ruff check`, `mypy`, `tsc`, `claude plugin validate`, `playwright test`.
- **`maeng-verify` commands:**
  - `ran --ok|--fail "<what>"` declares a check the agent ran (screenshot, dry-run…), recorded with the tree at call time.
  - `skip "<reason>"` records a skip.
  - `plan --met AC-1,… --unmet AC-k "<notes>"` records the result against a bound plan.

**Required checks**, in order of precedence:
1. the bound Plan's `Verification` section (each `AC-n` / `must_have` names its check);
2. otherwise the repo policy `.maeng/verify.json` → `required: [patterns]`;
3. otherwise at least one recognized test runner.

**Ship-verified tree T:**
- **every** required check has valid `ok` evidence at a tree `T'` that differs from T only in non-relevant paths;
- **no failed evidence at T' is unresolved** (a failure stays until the same check passes at a later relevant tree);
- when a plan is bound, the latest plan record at T' marks **every current AC / must_have met** (complete coverage, not just an empty unmet list) and matches the plan's current `updatedAt`.
- **A skip never makes a tree ship-verified.**

**Stop-satisfied** = the current tree is ship-verified **or** has an explicit skip.

**Stop** aggregates two checks: verification (Stop-satisfied for code changes made since the last check) and records (§5.4).
- If anything is missing and `stop_hook_active` is false: **block once** with the full list.
- If `stop_hook_active` is true: allow the stop, add a `systemMessage` the user sees ("UNVERIFIED / UNRECORDED: …"), and **keep the state**.

Shipping stays blocked by G1 until a tree is ship-verified.

### 5.4 Self-recording
- **Obligation:** after the last substantive change of the turn (a code tree change, a commit, or `maeng-verify decision`), there must be a **later** successful record write **for the bound issue**. That means a Linear write whose issue/document belongs to the bound issue, or an Obsidian write whose frontmatter `linear` includes it.
- **Without a binding:** any Linear or Obsidian write after the change counts.
- **The agent records the work itself and never asks the user.** Question-only turns pass.

### 5.5 Other handlers

| Event | Behavior | Timeout |
|---|---|---|
| SessionStart | From disk only: binding suggestions, hub and latest session note, policy summary, versions, eta checkouts missing isolation. Output ≤ 2 KB. | 5s |
| UserPromptSubmit | Marks the turn start | 3s |
| PreToolUse Bash (runner) | Records `tree_start` | 5s |
| PostToolUse / PostToolUseFailure | Evidence and record tracking. After `gh pr create`, a review reminder with its tier. | 5s |
| PostToolUse Edit/Write/NotebookEdit | Synchronous single-file format, only if the repo has a formatter config. The tree id catches the change. | 10s |
| Stop | §5.3/§5.4. Also **writes or refreshes the session stub** `wiki/sessions/SESSION-…` (atomic write + readback), so the durable record exists before SessionEnd. | 10s |
| SessionEnd | Best-effort finalize of the stub (end time). Nothing depends on it finishing. | 1.5s |
| SubagentStop | If `maeng-tools:implementer` ends without `Verification:` / `Unfinished:`, block once (personal world only) | 3s |

**No Linear update from hooks.** Hooks have no MCP, and a stored Linear token would be a credential. §5.4 keeps Linear current.

### 5.6 Codex hook mapping (11 → Claude)

| Codex | Claude |
|---|---|
| #1/#3 entry gate | Retired (user) |
| #2 | SessionStart policy + turn mark |
| #4 eta-phase1 | Not ported (eta world) |
| #5 | G1 + G3 (records ungated) |
| #6 | G2 |
| #7/#8 | Trackers |
| #9 | §5.3 |
| #10 | §5.4 |
| #11 | SubagentStop hand-off check |

### 5.7 harness-run, Claude edition: the user's workflow
1. **Interview** to settle the architecture or the workflow.
2. **Mandatory rules** written down.
3. **Middleman** decisions and research finished before splitting.
4. **Task tree:** parent → children, as fine-grained as possible.
5. **A Spec + Plan per task**, with finer criteria at depth. The Plan schema comes from gsd-core:
   - `must_haves`: truths / artifacts / key_links;
   - per-step `done` criteria, numbered `AC-n`;
   - a `Verification` section that names the check for each criterion;
   - **decision IDs `D-n`** that link each task to the decision it implements.
6. **`maeng-verify bind`** for each task.
7. The **implementer** (Sonnet) builds each child, then verifies (§5.3) and records (§5.4). The architect reviews falsify-first, like the gsd-core verifier: it starts from "goal not achieved".
8. **Review tier** (§4): child PR → Sol xhigh; parent integration → Astra high; small work → Sol high; Claude fallback (Opus; Fable medium for parent integration) only after 3 failed codex runs.
9. **Merge** with a matching receipt.
10. **Outcome:** Obsidian ADR/session, then a Notion record via Sol medium, then the link to the user.

The Codex ledger and prepare-tool are not ported.

### 5.8 Tests

**Unit** (subprocess with fixtures, temp HOME and repos):
- Guard triggers and cache invalidation.
- G1 negatives:
  - force variants;
  - implicit destinations;
  - tags and `--mirror`;
  - wrappers and compound commands;
  - `gh api` merges and MCP merge;
  - stale base, stale head, stale criteria;
  - verify → edit → commit → push (deny);
  - a branch switch, or another source ref with an unverified tree (deny);
  - a skip-only tree (deny ship, allow stop).
- G2: digest/destination mismatch, missing receipt, unreadable receipt.
- G3: local and remote eta targets.
- Evidence:
  - an edit during a check (tree_start ≠ tree_finish) gives no evidence;
  - formatter changes invalidate evidence;
  - unmet or **missing** `AC-n` blocks ship;
  - **failed pytest + passing ruff at the same tree → not ship-verified**;
  - a `requirements.txt` or `CMakeLists.txt` change invalidates evidence;
  - a dirty submodule → no evidence.
- G1 extra:
  - deny `gh api -X PUT repos/o/r/contents/f` (on a feature and on the default branch), GraphQL `createCommitOnBranch`, `gh pr merge` in any mode, `gh repo sync [--force]`, `gh pr update-branch`, `gh release create`;
  - `maeng-ship merge` on a BEHIND PR → deny;
  - **deterministic base-movement tests** on a local bare remote: (a) a divergent base advance, and (b) the base moved to an *ancestor of the head*. Both are rejected by the lease, and the receipt is not consumed.
  - Accepted push followed by a client failure → receipt `pending` → reconcile marks it consumed, both when the remote stays at head and when it has advanced beyond head.
- G3 extra: `git push https://github.com/maengseojun/eta_v1.git …` and `gh pr create -R endix-foundation-v1/x` from a personal session → deny.
- Unknown classification: no stub or context written, and every G1/G3 mutation denied.
- Retirement: `synced/` is still present and listed after quarantine.
- Receipts: consumed only on success; retry after rejection; pending → reconcile.
- G2 extra: a create that succeeds but whose readback fails → the next update is denied until reconcile.
- Guard: a change to a linked worktree's origin invalidates the cache; unresolvable classification → no-op.
- Stop: the second continuation keeps the state.
- §5.4: an unrelated write doesn't count; a "starting work" comment followed by more changes still requires a record.
- Gate handler failure modes through Claude Code: missing script, crash, malformed output, timeout.

**Live** (`claude -p --output-format stream-json --verbose --include-hook-events`):

| | Setup | Expected |
|---|---|---|
| S1 | scratch repo, both plugins inline; bind, edit, stop | Block → continuation → `systemMessage`; stub written |
| S2 | run pytest, record on the bound issue | No block; ship-verified |
| S3 | `git push --force`; `gh pr merge`; `maeng-ship merge` without a receipt; push of an unverified commit | Deny |
| S8 | Scratch repo with a local bare remote: verified + reviewed PR → `maeng-ship merge` | Push accepted; receipt consumed; merge tree == verified tree |
| S9 | Real `dev/contracts` (endix-foundation-v1) after `maeng-eta-isolate --apply`, both maeng plugins inline, read-only prompt | `init` shows eta-rules / eta-craft, no linear; maeng-harness hooks have no side effects (guard eta by org); checkout unchanged |
| S4 | the agents | Transcripts show opus / sonnet / haiku |
| S5 | eta_v1 with **only maeng-tools inline**, after isolation | `init`: eta-rules, eta-craft, maeng-tools; no maeng-harness; zero personal hook events; state dir unchanged |
| S6 | eta worktree with maeng-harness inline (misconfigured) | Guard: no side effects; one SessionStart warning |
| S7 | personal session targeting eta (`git -C`, `gh -R`) | G3 deny |

Filesystem and state effects are asserted separately from hook events.

---

## 5.9 Phase 2 adoptions (`MAE-216-phase2-adoption.md`)
- **Aside is split into two skills** (user, 2026-10-17), so research doesn't dominate:
  - **`aside-collect` (자료수집, collection).**
    - Triggers: "자료수집", "긁어와", "모아줘", "collect", "gather", "scrape".
    - **Gathers material without judgment:** `aside exec` (default permission) with a fixed collection template → raw output saved under `raw/aside/` with a sidecar (prompt, time, session id if any) → normalized **source notes with provenance, deduped by canonical URL/DOI** → an index note.
    - No synthesis, no claim verdicts, no external review. A provenance check only (each item has a resolvable source).
    - In the eta world, notes are tagged `world: eta`.
  - **`aside-research` (리서치, research).**
    - Triggers: "리서치", "조사해서 판단", "분석", "research", "assess".
    - **Collection plus judgment:** scope (question, criteria) → collection via `aside-collect` → the researcher verifies each claim against its source → synthesis with an explicit judgment and confidence → draft → Sol xhigh review with a devil's-advocate lens → at most 2 revise loops (leftovers become Limitations) → finalize (Notion via Sol medium in the personal world; eta Docs via eta rules in the eta world).
  - Phase 4 starts with one manual `aside exec` smoke run (output shape and session ids are unverified). Both skills live in maeng-tools.
- **Global `~/.claude/CLAUDE.md`** (new, ≤30 lines, world-neutral): think before coding (ask when ambiguity is material), simplicity, surgical changes, goal-driven success criteria. It loads in eta_v1 too, so nothing world-specific goes in it.
- **Vault retrieval** works in three layers: compact index, then timeline, then fetch by id. Before a vault write, apply the `<private>` tag and opt-in regex redaction (both from claude-mem).
- **Skill hygiene:**
  - Slim three skills to their deltas over the official/synced ones: frontend-guidance, aside-browser, skill-feedback.
  - Split four skills so each SKILL.md stays under 500 lines: diagram-explainer, frontend-slides, harness-run, work-records.
  - Write "pushy" trigger descriptions.
- **graphify-repository fixes:** a persistent `cache_root`; a dirty check limited to in-scope paths; pin bumped to 0.9.91 after the revision-gate check.
- **Reviewer prompt** adapted from codex-plugin-cc's adversarial-review prompt and schema. Multi-subject reviews run as parallel read-only `codex exec` calls (from ruflo).
- **Everything else is not installed** (global hooks, skills or CLAUDE.md writes). See the table.

## 6. Phase 4 build order
Sonnet implements, Opus reviews each step, and Codex reviews the PR (Sol xhigh per child PR; Astra high for the final integration).

1. Scaffold + `claude plugin validate`.
2. Reconcile and move skills.
3. Guard, dispatcher, G1–G3, evidence, Stop/§5.4, handlers, unit tests.
4. Agents + model check.
5. `maeng-review`, `maeng-verify`, `maeng-ship` (merge), `maeng-eta-isolate` + schemas.
6. harness-run and work-records Claude editions, vault rule edits, and the §5.9 items: aside-collect and aside-research (after the smoke run), global CLAUDE.md, skill hygiene, graphify fixes.
7. Staging smoke S1–S8 via `--plugin-dir`. S8 is a successful `maeng-ship merge` against a local bare remote, run before the real merge in step 8.
8. PR → Astra → fix until pass → `maeng-ship merge` (this is also the first real exercise of the permitted merge route).
9. Release (§1.2) → isolation → retirement sequence → re-run S5–S7 installed.

## 7. Phase 5
- Obsidian ADR + session log.
- A Sol-reviewed Notion outcome, linked to the merge commit and MAE-216.
- Revise the Notion `harness-run` page.
- Close MAE-216.

## 8. Verified facts
- A local `enabledPlugins: false` overrides user scope (live). The docs say local > project > user.
- The home session loads 0 eta skills or hooks. eta_v1 fires eta hooks (live).
- `codex exec` reaches Astra and Sol. Reasoning efforts low through xhigh are enabled in the config. The isolated-reviewer probe matches §4.
- `claude --plugin-dir` exists. `git push --force-with-lease=<ref>:<expect>` gives an atomic expected-old-value check on the server. Claude Code is 2.1.301.
- Branch protection and rulesets are unavailable on this private repo (403).
- OPS-A1-12 wording was read live via Aside.
- eta hooks are active only where eta-rules is enabled.

## 9. Decision record (2026-10-17)
- Records autonomous; code strict, with local guardrails under a cooperative threat model.
- Two plugins. Agents and obsidian-workspace go in maeng-tools.
- eta-world full local logs allowed, with the conflict recorded.
- Review tiers as in §4. Notion uses Sol medium.
- Entry gate retired.
- Isolation file in every eta checkout. **Open for the user to veto.**
- Child-task PR review: Sol xhigh (user, 2026-10-17).
- Review backend: Codex first; Claude fallback after 3 failed codex runs, Fable medium only for parent integration (user, 2026-10-17).
- PR #38 reviews run with `MAENG_REVIEW_BACKEND=claude` on the user's request ("일단 claude로 해줘", 2026-10-17; Codex quota nearly used up): parent integration Fable medium, child PR Opus medium. The variable is set in the review job's environment, not through the agent's Bash tool: the harness denies every `MAENG_*` assignment, export, unset and `env` form there (round-9 fix).
- Merge criterion changed (user, 2026-10-17, during PR #38 round 10): a merge needs pass verdicts with no critical/high findings; medium and low findings are handled after the merge in a follow-up issue (MAE-227). PR #38 merged at `c3eede5` under this rule.
- Release (2026-10-17): release clone `~/.local/share/maeng/agent-harness` at `c3eede5`, marketplace `maeng`, maeng-tools and maeng-harness 0.1.0 plus commit-commands at user scope; installed files hash-match the release clone. `plugin-dev` is installed at **local** scope in this repo (not project scope as planned), so no tracked settings file changes. 29 loose skills and `~/.claude/agents/codebase-explorer.md` were quarantined; both fresh-session checks passed, with `synced/` official skills still listed. Installed S5-S7 re-run: 20/20 pass (tests/live/evidence/assert-2026-10-17-installed-S5-S7.txt).
- Phase 2 adoptions per `MAE-216-phase2-adoption.md` (§5.9).
- Cold storage tier: OneDrive archive + Google Drive backup/search, eta allowed (§3.5, user).
- **Open: final approval of this revision (Q1).**
