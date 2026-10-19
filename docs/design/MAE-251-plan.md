# MAE-251 Spec/Plan: eta notes may be linked from personal Linear

Linear: MAE-251. Date: 2026-10-19. Single task, docs-only (every path matches `non_code_globs`).

## Decision

User, 2026-10-19: "개인 linear에 연결해도 될 것 같아" ("linking it from personal Linear seems fine"). This answered the question raised when aside-collect's world rule blocked a personal Linear reference issue (MAE-250) for eta research.

## Criteria

- **AC-1** The live skill texts no longer forbid linking `world: eta` notes from personal Linear. Each one says a personal Linear issue may link them as a reference: aside-collect, aside-research, obsidian-workspace SKILL.md (2 places) and references/claude-edition.md.
- **AC-2** These rules stay unchanged:
  - eta notes keep `world: eta` and live under P-ETA.
  - They are never promoted to personal Notion.
  - eta's work record stays in eta's own tools.
  - No personal record flows (work-records, personal Notion) run in the eta world.
  - The Middleman locator stays "never use for eta". It is a personal code-question convention, not a reference link.
- **AC-3** The MAE-216 design doc records the amendment at both places that stated the old rule. Archived copies under `archive/` stay as historical text.

## Done

- `grep -rn -iE "linked from personal|link from personal|link it from personal|touch personal Linear" plugins docs/design/MAE-216-two-harness.md` prints nothing.
- The review with `--plan docs/design/MAE-251-plan.md` passes.
