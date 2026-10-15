# This user's vault

Primary knowledge folder:

`/Users/maengseojun/Documents/Obsidian Vault`

The app registers the operating folder as `Obsidian Vault`. The user explicitly selected their existing vault on 2026-10-14, and the MAE-166 knowledge content was integrated there while preserving existing notes and plugin/provider settings. The earlier folder `/Users/maengseojun/Documents/ChatGPT/Being agents/outputs/obsidian-mae166/vault` is retained as a recovery source, not the default working target. There are no feature tiers implied by these names.

Read AGENTS.md, Home.md and the relevant rules under the primary folder. Current hubs include `hubs/courses/C-LING414.md`, `hubs/projects/P-ETA.md`, and `hubs/projects/P-MAE166.md`. Select from the current files rather than assuming this list is exhaustive. Rules and templates are Korean; source language stays unchanged. No development/marketing-only folder taxonomy is required.

## Application access

CLI executable: `/Applications/Obsidian.app/Contents/MacOS/obsidian`. Use the absolute executable in scripts: a login-disabled shell was observed to lack `obsidian` on PATH. The shorter form below is appropriate only after verifying that command resolves to this executable.

User instruction on 2026-10-14: Obsidian control is CLI-only. Do not drive or inspect the desktop UI or ask the user to unlock it for vault verification.

**Put the vault selector before the command and quote the name containing spaces.** A trailing selector was observed to follow the active vault instead. Before each CLI write, run:

```text
obsidian 'vault=Obsidian Vault' vault info=path
```

It must resolve to the primary absolute folder above. Empty output, a different folder or an error means do not write. Use exact note paths and inspect current content; never rely on the active tab or exit code alone. Working examples:

```text
obsidian 'vault=Obsidian Vault' read path=Home.md
obsidian 'vault=Obsidian Vault' search query=MAE166 path=wiki/answers format=json
```

The CLI needs the app running. If unavailable, report the exact CLI access gap and preserve existing notes; do not switch to GUI. The sync helper's selected attachment capture and local backup/hash comparisons remain explicit filesystem operations. Note read/search/writes and application verification use the CLI. Readback can be delayed: inspect the command result and saved file before retrying any write; empty output is not verified success.

## Storage and ownership

- `raw/`: retained external inputs; original captures are immutable.
- `wiki/sources/`: provenance/coverage and source descriptions, with conversion files where appropriate.
- `wiki/concepts/`, `wiki/entities/`: useful reusable knowledge.
- `wiki/answers/`: grounded derived answers/results.
- `assets/deliverables/<project-id>/`: project output files and helper version catalog.
- `hubs/`, `wiki/index.md`, section indexes and `log.md`: navigation and processing history.

MAE-177 owns this skill's source. For current workflow scope, read the [live MAE-177 issue](https://linear.app/maeng/issue/MAE-177/obsidian-프로젝트-저장갱신-및-위키-운영-스킬-구현), the active task's current Spec/Plan, and the selected vault's current AGENTS/Rules. MAE-166 Research and older source audits are lineage evidence, not a substitute for current decisions. Source code is in the personal repository's `skills/obsidian-workspace/`; discoverable installed files live at `/Users/maengseojun/.codex/skills/obsidian-workspace/`. Copy reviewed changes to the install and compare bytes before claiming an update. A local source change does not imply installation or GitHub publication.

## Source lineage and capability limits

This skill adapts the repeated ingest/query/lint loop from [second-brain-os](https://github.com/undefined-ui/second-brain-os) and explicit save/provenance principles from [claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian). It is independently written for the existing personal workflow, not an upstream installation. MAE-166's [Research](https://linear.app/maeng/document/5e1490d269ac) and MAE-177 source audit preserve observed coverage and adoption decisions.

The operating vault retains obsidian-git/realclaudian. Their presence does not establish authentication, enabled models, or actual Sync/Git behavior. MAE-197 records one verified user-triggered Claudian dialogue; it does not prove every session path, attachment or inline-edit feature, current model availability, or current service state. Check the active task and current capability evidence when those features matter. The Obsidian CLI is the note-control route and requires the app to be running; `eval` uses version-specific local application APIs, not a stable plugin API. Do not treat historical UI messages as current readiness proof.

Project refresh means selected local originals→vault, with model-assisted linked knowledge updates. `qmd_search.py` provides local retrieval from CLI-exported wiki/hub snapshots; it does not interpret sources or write wiki knowledge. Multi-device cloud Sync, automatic transcript capture, scheduled execution, MCP and whole-vault concurrent transactions are outside this skill's contract. The known-sensitive-path filter is not a general secret scanner. Existing same-disk backups are snapshots, not protection from disk failure.

## Current workflow

Read the selected vault's current Architecture/Rules and the active task's current Linear Spec/Plan before substantive changes; version counts and historical task phases can change. Native Notion/Linear capture uses [native-sources.md](native-sources.md); selected local attachments use the existing sync helper. Neither helper executes semantic knowledge updates. Finish proposals and current-first, related-knowledge resume use [session-flow.md](session-flow.md). They run when the skill is invoked, not as a global hook. Preserve immutable captures, preview changes and affected notes, and verify selected updates with separate CLI reads.
