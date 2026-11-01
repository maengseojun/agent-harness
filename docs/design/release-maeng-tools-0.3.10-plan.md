# Spec/Plan: release maeng-tools 0.3.10

- AC-1: plugins/maeng-tools/.claude-plugin/plugin.json version is 0.3.10 so the plugin cache refreshes and new sessions get PR #83 (Aside research method: access states, GAP coverage, modes, method.md).
- AC-2: no other file changes besides this plan.

## Verification

- AC-1: `claude plugin validate plugins/maeng-tools` prints `Validation passed` and the manifest version reads 0.3.10.
