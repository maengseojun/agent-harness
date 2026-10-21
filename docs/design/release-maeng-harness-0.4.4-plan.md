# Spec/Plan: release maeng-harness 0.4.4

status: current. Linear: MAE-267 (release follow-up of PR #71). Date: 2026-10-21.

- AC-1: plugins/maeng-harness/.claude-plugin/plugin.json version is 0.4.4, so the plugin cache refreshes and new sessions get PR #71 (MAE-267: the org rules apply to local work in both worlds; external records carry plain roles only).
- AC-2: no other file changes besides this plan.

Verification tier: code (plugin manifest).

Verification:
  AC-1: `python3 -m pytest -q` expect pass
  AC-2: review item expect pass
