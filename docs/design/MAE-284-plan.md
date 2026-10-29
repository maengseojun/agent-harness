# MAE-284 Spec/Plan: hooks stop timing out under load

status: current. Linear: MAE-284. Date: 2026-10-29.

## Spec

Measured 2026-10-29: since 10-15 the transcripts show about 140 maeng_hooks.py timeouts, almost all PreToolUse (5s, `onFailure: block`, so the call is denied). `on_pre` itself takes 0.05-0.08s; the timeouts cluster while heavy background jobs run. `tree.tree_id` starts from an empty temporary index, so `git add -A` rehashes every file: 7.8s cold in a 244-file contracts checkout, 0.55s when it starts from a copy of the repo's index, same tree id in 4 repos.

Decisions (CEO, 2026-10-29: "1+2 진행"):
- D-1 PreToolUse gets 15s. A slow gate still fails closed; only a gate that cannot answer in 15s blocks. Wrong if: PreToolUse timeouts keep appearing in transcripts after 0.4.5.
- D-2 `tree_id` starts from a copy of the repo's own index; it falls back to `read-tree HEAD` when the index is missing or unreadable, or when any entry is assume-unchanged or skip-worktree (git would not look at those files, so a change could hide). Wrong if: a tree id ever differs from the tree of a fresh `git add -A` of the same worktree.

Owns: `plugins/maeng-harness/hooks/hooks.json`, `plugins/maeng-harness/lib/maeng/tree.py`, `plugins/maeng-harness/tests/test_plugin.py`, a new `plugins/maeng-harness/tests/test_tree_index.py`, `docs/design/MAE-216-two-harness.md` §5.5 table, `plugins/maeng-harness/.claude-plugin/plugin.json` (0.4.5), this plan.

Exclusions: caching the world classification, moving Stop's git calls out of the state lock (later, only if timeouts remain); other hook timeouts.

Requirements -> acceptance:
  AC-1: hooks.json PreToolUse timeout is 15, `onFailure: block` unchanged; the MAE-216 §5.5 table and test_plugin say 15s.
  AC-2: `tree_id` equals the tree of a fresh `git add -A` for a worktree with a modified, a staged-then-modified, a deleted and an untracked file.
  AC-3: a modified file flagged assume-unchanged or skip-worktree still changes the tree id.
  AC-4: plugin.json version is 0.4.5.

## Plan

Verification tier: gate-code.

1. hooks.json + MAE-216 table + test_plugin (AC-1).
2. tree.py `_seed_index` and its use in `tree_id` (AC-2, AC-3); tests in `test_tree_index.py` whose expected tree comes from git itself with a fresh index, not from `tree_id`.
3. plugin.json 0.4.5 (AC-4).

Verification:
  AC-1: `python3 -m pytest -q` expect pass
  AC-2: `python3 -m pytest -q` expect pass
  AC-3: `python3 -m pytest -q` expect pass
  AC-4: review item expect pass

Review focus: can the copied index make `tree_id` miss a worktree change (flags, split index, sparse checkout, unmerged entries)?
