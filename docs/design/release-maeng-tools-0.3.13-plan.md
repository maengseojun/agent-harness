# Spec/Plan: release maeng-tools 0.3.13 (PR #92)

Goal: the plugin cache picks up PR #89 (taste-skill modes). The cache is keyed by version, so the version must change.

- AC-1: `plugins/maeng-tools/.claude-plugin/plugin.json` has version `0.3.13`, and that line is the only change under `plugins/`. This plan is the only other file.
- AC-2: no regression.

## Verification

- AC-1: `git diff --stat origin/feat/harness-v1...HEAD -- plugins` expect 1 file, 1 insertion and 1 deletion. `grep -o '"version": "0.3.13"' plugins/maeng-tools/.claude-plugin/plugin.json` expect 1 match.
- AC-2: `python3 -m pytest -q` expect all pass.
