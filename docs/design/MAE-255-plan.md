# MAE-255 Spec/Plan-lite: release maeng-tools 0.2.0

Linear: MAE-255. Date: 2026-10-20. Small work, no tree.

Goal: Claude Code reinstalls maeng-tools so the merged skills cinematic-site (MAE-254) and motion-studio (MAE-253) reach new sessions. The plugin cache is keyed by version and maeng-tools has stayed at 0.1.0 (cache commit c3eede5).

- **AC-1** `plugins/maeng-tools/.claude-plugin/plugin.json` version is 0.2.0; nothing else changes.

## Verification

Verification tier: code (manifest). Ship checks, once at the final tree:
- AC-1: claude plugin validate plugins/maeng-tools
- AC-1: python3 -m pytest -q

After merge (not a gate): pull the release clone, `claude plugin marketplace update maeng`, `claude plugin update maeng-tools@maeng`, confirm `~/.claude/plugins/cache/maeng/maeng-tools/0.2.0/skills` lists cinematic-site and motion-studio.
