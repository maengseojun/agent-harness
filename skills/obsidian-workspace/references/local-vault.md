# This user's vault

Primary knowledge folder:

`/Users/maengseojun/Documents/Obsidian Vault`

The app registers the operating folder as `Obsidian Vault`. The user selected this existing vault on 2026-10-14, and MAE-166 knowledge was integrated there while preserving existing notes and plugin/provider settings. The earlier folder `/Users/maengseojun/Documents/ChatGPT/Being agents/outputs/obsidian-mae166/vault` is a recovery source, not the default target. A vault name alone is not its identity.

## Native note route

Use this user's configured native Obsidian MCP server (`obsidian_vault`) for note reads, search, writes and patches. The current session exposes `read_note`, `read_note_lines`, `search_notes`, `list_directory`, `write_note` and `patch_note`. This connection targets the exact folder above and works without opening the Obsidian UI. It is Codex's direct MCP connection, not a Claudian relay. The connection's path filtering is not an OS sandbox claim.

Read `AGENTS.md`, `Home.md`, the applicable rules and the current hub through MCP before substantive work. Current hubs include `hubs/courses/C-LING414.md`, `hubs/projects/P-ETA.md` and `hubs/projects/P-MAE166.md`; discover current paths instead of assuming the list is exhaustive. Rules and templates are Korean; preserve source language. No development/marketing-only folder taxonomy is required.

`read_note` returns frontmatter as a parsed object and the body separately. It is useful for ordinary semantic reading, but reserializing that object can change YAML formatting, comments or other original syntax. For raw Markdown, use `read_note_lines` with the exact path and requested line range. To read the complete note, start at line 1 and request an end line beyond its length; `2147483647` was verified to return the full Markdown including original frontmatter. Use the outline and bounded line ranges for large notes when only a section is needed. Confirm the returned extent and use a filesystem SHA-256 comparison when exact bytes matter.

The note tools do not read or write `.body` or `.json` captures. Use filesystem operations for raw bodies, JSON receipts, original-byte hashes and byte-for-byte backups. The native note tools also cannot write attachments or other binary files. Preserve only selected files and paths.

## Optional CLI diagnostic

CLI executable: `/Applications/Obsidian.app/Contents/MacOS/obsidian`. The Obsidian CLI is optional for a separate route diagnostic, not the primary note workflow. If diagnosing its selected vault, place the selector before the command and quote the name containing spaces:

```text
obsidian 'vault=Obsidian Vault' vault info=path
```

It should resolve to the primary absolute folder above. The CLI needs the app running. An empty result, another folder or an error is a diagnostic access gap; do not switch to GUI control. Do not use a failed CLI helper as evidence that native MCP is unavailable.

## Storage and ownership

- `raw/`: retained external inputs; original captures are immutable.
- `wiki/sources/`: provenance, coverage and source descriptions, with conversion files where appropriate.
- `wiki/concepts/`, `wiki/entities/`: useful reusable knowledge.
- `wiki/answers/`: grounded derived answers and results.
- `assets/deliverables/<project-id>/`: project output files and the helper's version catalog.
- `hubs/`, `wiki/index.md`, section indexes and `log.md`: navigation and processing history.

MAE-177 owns this skill's source. For current workflow scope, read [the live MAE-177 issue](https://linear.app/maeng/issue/MAE-177/obsidian-프로젝트-저장갱신-및-위키-운영-스킬-구현), the active task's current Spec/Plan, and the selected vault's current AGENTS/Rules. MAE-166 Research and older source audits are lineage evidence, not substitutes for current decisions. Source code is in the personal repository's `skills/obsidian-workspace/`; the discoverable installation is `/Users/maengseojun/.codex/skills/obsidian-workspace/`. A local source change does not imply installation or GitHub publication.

## Source lineage and capability limits

This skill adapts the repeated ingest/query/lint loop from [second-brain-os](https://github.com/undefined-ui/second-brain-os) and explicit save/provenance principles from [claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian). It is independently written for the existing personal workflow, not an upstream installation. MAE-166's [Research](https://linear.app/maeng/document/5e1490d269ac) and MAE-177 source audit preserve observed coverage and adoption decisions.

The operating vault retains obsidian-git/realclaudian. Their presence does not establish authentication, enabled models, or actual Sync/Git behavior. MAE-197 records one verified user-triggered Claudian dialogue; it does not prove every session path, attachment or inline-edit feature, current model availability, or current service state. Check the active task and current capability evidence when those features matter. The direct MCP route serves Codex note work and does not prove Claudian can use it.

Project refresh means selected local originals to vault, with model-assisted linked knowledge updates. [`sync_project.py`](../scripts/sync_project.py) is a filesystem-only Python helper for explicitly selected attachments/files; it does not invoke Obsidian CLI, interpret source meaning or update wiki notes. It defaults to a dry run; `--apply` stores immutable copies under `assets/deliverables/<project-id>/files/` and updates the version catalog. It reads only supplied paths, rejects known sensitive path candidates, verifies source and saved-copy hashes, and reuses identical versions. The project ID remains bound to its original source root. Its path-name filter is limited and is not a content scanner; its lock coordinates that helper only.

[`source_snapshot.py`](../scripts/source_snapshot.py), [`wiki_compile.py`](../scripts/wiki_compile.py) and [`qmd_search.py`](../scripts/qmd_search.py) remain Obsidian-CLI-dependent and did not become MCP-enabled. The QMD helper searches snapshots exported through CLI; it does not interpret sources, write wiki knowledge or refresh automatically after MCP edits. Use each legacy helper only when its own CLI preconditions are available. If a helper fails, inspect actual files and notes before deciding whether a retry is safe; do not repeat a failed bulk request blindly.

No daemon, scheduled execution, automatic transcript capture, background hook or whole-vault concurrent transaction is part of this skill. The known-sensitive-path filter is not a general secret scanner. Existing same-disk backups are snapshots, not protection from disk failure.

## Current workflow

Read the selected vault's current Architecture/Rules and the active task's current Linear Spec/Plan before substantive changes. Use native MCP to search and read the selected notes; use filesystem operations for selected originals, attachments, hashes and exact backups. Use [native-sources.md](native-sources.md) for Notion/Linear body capture and [wiki-compile.md](wiki-compile.md) to integrate selected evidence. Finish proposals and current-first, related-knowledge resume use [session-flow.md](session-flow.md). These procedures run when the skill is invoked, not as a global hook. Preserve immutable captures, compare before writes and verify every selected update with a separate MCP readback.
