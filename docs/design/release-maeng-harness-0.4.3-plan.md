# Spec/Plan: release maeng-harness 0.4.3 and maeng-tools 0.3.5

status: current. Linear: MAE-259 (release follow-up of PR #69). Date: 2026-10-21.

- AC-1: plugins/maeng-harness/.claude-plugin/plugin.json version is 0.4.3, so the plugin cache refreshes and new sessions get PR #69 (MAE-259: DRI section and message formats in harness-run org-chart.md, SKILL.md and spec-plan.md; the wildcard exception in work-records).
- AC-2: plugins/maeng-tools/.claude-plugin/plugin.json version is 0.3.5, so new sessions get PR #69's agent changes (optional `Dissent:` in the architect, implementer and researcher reports; repair-brief handling in the implementer).
- AC-3: no other file changes besides this plan.

Verification tier: code (plugin manifests).

Verification:
  AC-1: `python3 -m pytest -q` expect pass
  AC-2: review item expect pass
  AC-3: review item expect pass
