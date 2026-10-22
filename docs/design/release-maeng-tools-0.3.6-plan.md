# Spec/Plan: release maeng-tools 0.3.6

- AC-1: plugins/maeng-tools/.claude-plugin/plugin.json version is 0.3.6 so the plugin cache refreshes and new sessions get PR #73 (MAE-268: huashu-motion director docs, sound engine and qa in motion-studio).
- AC-2: no other file changes besides this plan.

## Verification

- AC-1: `claude plugin validate plugins/maeng-tools` prints `Validation passed` and the manifest version reads 0.3.6.
