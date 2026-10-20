# MAE-257 Spec/Plan-lite: release maeng-harness 0.4.0 and maeng-tools 0.3.0

Linear: MAE-257. Date: 2026-10-21. Small work, no tree.

Goal: the merged org chart (PR #58) reaches new sessions. The plugin cache is keyed by version: maeng-harness is 0.3.3 (SessionStart pointer, archive candidates, harness-run/work-records docs) and maeng-tools is 0.2.0 (agents, claude-edition, maeng-archive gdrive default).

- **AC-1** `plugins/maeng-harness/.claude-plugin/plugin.json` version is 0.4.0 and `plugins/maeng-tools/.claude-plugin/plugin.json` version is 0.3.0; nothing else changes.

## Verification

Verification tier: code (manifest). Ship checks, once at the final tree:
- AC-1: claude plugin validate plugins/maeng-harness
- AC-1: claude plugin validate plugins/maeng-tools
- AC-1: python3 -m pytest -q

After merge (not a gate): pull the release clone (check it is clean), `claude plugin marketplace update maeng`, `claude plugin update maeng-harness@maeng` and `maeng-tools@maeng`, confirm `~/.claude/plugins/cache/maeng/maeng-harness/0.4.0/skills/harness-run/references/org-chart.md` exists, then restart sessions.
