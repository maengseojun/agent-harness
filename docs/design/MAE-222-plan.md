---
id: PLAN-MAE222
linear: MAE-222
parent: MAE-216
date: 2026-10-17
---

# MAE-222 (child of MAE-216): skill content

## must_haves
- truths: aside-collect gathers without judging; aside-research judges with verified sources and review; harness-run and work-records follow the Claude workflow and the Sol flow; tool skills are world-aware; every SKILL.md is under 500 lines.
- artifacts: the aside-collect, aside-research and maeng-archive skills; the Claude editions of harness-run and work-records; the obsidian-workspace world rule.

## Acceptance criteria
- AC-1: Aside smoke documented (docs/design/aside-smoke-2026-10-17.md), including the live nonce run.
- AC-2: both Aside skills trigger on their own wording.
- AC-3: every SKILL.md is under 500 lines.
- AC-4: the global CLAUDE.md template is at most 30 lines and world-neutral.
- AC-5: the vault policy edits were read back (docs/design/vault-policy-readback.md).
- AC-6: skill script tests pass (maeng-archive, aside-collect, graphify-repository, obsidian private_filter).

## Verification
- AC-1: aside smoke documented (declared, evidence docs/design/aside-smoke-2026-10-17.md incl. the live nonce run)
- AC-2: aside trigger wording reviewed (declared, evidence aside-collect and aside-research SKILL.md descriptions)
- AC-3: skill line counts (declared, evidence wc -l of every SKILL.md)
- AC-4: global CLAUDE.md template checked (declared, evidence templates/global-CLAUDE.md, at most 30 lines, world-neutral)
- AC-5: vault policy readback (declared, evidence docs/design/vault-policy-readback.md)
- AC-6: python3 -m unittest discover -s plugins/maeng-tools/skills/maeng-archive/scripts -t plugins/maeng-tools/skills/maeng-archive/scripts && python3 -m unittest discover -s plugins/maeng-tools/skills/aside-collect/scripts -t plugins/maeng-tools/skills/aside-collect/scripts && python3 -m unittest discover -s plugins/maeng-tools/skills/graphify-repository/scripts -t plugins/maeng-tools/skills/graphify-repository/scripts && python3 -m unittest discover -s plugins/maeng-tools/skills/obsidian-workspace/scripts -t plugins/maeng-tools/skills/obsidian-workspace/scripts -p test_private_filter.py

## Evidence notes
The test-suite criterion is recorded with `maeng-verify exec` (real runner executions). The other criteria are declared checks recorded with `maeng-verify ran --ok "<check text>"`; each names the file that holds its evidence, attached to the review bundle.
