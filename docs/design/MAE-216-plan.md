---
id: PLAN-MAE216
linear: MAE-216
date: 2026-10-17
---

# MAE-216 parent Plan: acceptance for the integration PR

Spec: `docs/design/MAE-216-two-harness.md` (rev 6.2, approved 2026-10-17).
Children: MAE-218 to MAE-225.

## must_haves
- **truths:**
  - In the eta world, no personal hook runs and no personal record flow is reachable.
  - In the personal world, no eta skill or hook loads.
  - Known code-ship routes are gated by tree-bound verification and review receipts.
  - Records (Linear, Obsidian) are never gated.
- **artifacts:**
  - the `maeng` marketplace;
  - the `maeng-tools` and `maeng-harness` plugins;
  - the hooks, CLIs, tests, live smoke runner and design docs.
- **key_links:**
  - hooks.json → `maeng_hooks.py` → `lib/maeng`;
  - the skills cite the real CLI subcommands;
  - Obsidian rules match the design.

## Decisions
- D-1: two plugins. maeng-tools is ON everywhere; maeng-harness is OFF in the eta world.
- D-2: cooperative threat model with local guardrails (no server-side protection on a free private repo).
- D-3: merges go only through `maeng-ship merge` (a lease-guarded fast-forward).
- D-4: review tiers: child PR → Astra medium; parent integration → Astra xhigh; small → Sol xhigh; Notion → Sol medium.
- D-5: cold storage is OneDrive archive plus Google Drive/OneDrive backups.

## Acceptance criteria
- AC-1: both plugins and the marketplace pass `claude plugin validate`.
- AC-2: the maeng-harness unit suite passes.
- AC-3: the skill script suites pass (maeng-archive, aside-collect parser, graphify-repository).
- AC-4: live staging S1–S4 and S6–S8 pass, and the gate failure modes GF1–GF3 block.
- AC-5: model routing is proven from transcripts (researcher=haiku, architect=opus, implementer=sonnet).
- AC-6: in eta_v1 (S5), maeng-harness is absent, there are zero personal hook events, and eta_v1 is unchanged.

## Verification
- AC-1: claude plugin validate plugins/maeng-tools && claude plugin validate plugins/maeng-harness && claude plugin validate .
- AC-2: python3 -m unittest discover -s plugins/maeng-harness/tests -t plugins/maeng-harness
- AC-3: python3 -m unittest discover -s plugins/maeng-tools/skills/maeng-archive/scripts -t plugins/maeng-tools/skills/maeng-archive/scripts && python3 -m unittest discover -s plugins/maeng-tools/skills/aside-collect/scripts -t plugins/maeng-tools/skills/aside-collect/scripts && python3 -m unittest discover -s plugins/maeng-tools/skills/graphify-repository/scripts -t plugins/maeng-tools/skills/graphify-repository/scripts
- AC-4: live staging smoke
- AC-5: check_models S4
- AC-6: staging S5 plugin-controlled checks

## Evidence notes
The checks for the first three criteria are runner invocations recorded with `maeng-verify exec -- <command>` (real executions, tree-bound). The live-staging criteria are declared checks for the custom live runner (`tests/live/run_smoke.py`, `tests/live/assert_smoke.py`); their full assertion output is attached as evidence.

**Known and dispositioned outside this PR:**
- S5 user-level agent and loose skills → retirement at release (MAE-224).
- GF4, malformed exit-0 hook output → Claude Code host limit (design §5.1).
