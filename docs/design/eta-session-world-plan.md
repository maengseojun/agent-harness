# Spec/Plan: session world follows the project root

Problem: handlers.world_of classified st["cwd"] (first cwd the hooks saw). In a Claude desktop side session that is the notes folder (~/Library/Application Support/Claude/side-session-notes/<id>, personal), so Stop blocked an eta checkout with UNVERIFIED while maeng-verify refused as eta.

Plan: guard.session_root(cwd, first) = CLAUDE_PROJECT_DIR, else `first` only while it is a checkout (git repo or under the eta root), else cwd; never raises. world_of, on_session_start and cli_common.require_personal classify that root. Bump plugin to 0.3.3. Keep maeng-harness enabled in eta (DESIRED_PLUGINS unchanged).

- AC-1: an eta project whose state cwd lies outside any checkout does not block at Stop (test_eta_project_with_state_cwd_outside_checkout_does_not_block).
- AC-2: with CLAUDE_PROJECT_DIR on an eta checkout, hooks treat the session as eta and maeng-verify refuses the same way (test_eta_project_dir_env_decides_world).
- AC-3: a personal project whose state cwd lies outside any checkout still blocks at Stop (test_personal_project_with_state_cwd_outside_checkout_still_blocks).
- AC-4: already-wrong state needs no migration: the next hook call ignores a recorded cwd outside a checkout (covered by AC-1, which writes such state first).
- AC-5: full suite passes (314 passed).
