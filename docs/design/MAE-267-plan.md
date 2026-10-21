# MAE-267 Spec/Plan: rank rules apply locally everywhere, never in external records

status: current. Linear: MAE-267 (closes MAE-266). Date: 2026-10-21.

## Spec

Decisions (CEO, 2026-10-21: "내 local에서 돌아가는 건 dri, 직급, 소통 규약 적용시켜도 되지 않아? 다만 이제 외부(linear, slack, notion)에 쓸 때만 그걸 표시 안하면 되는거고 난 그렇게 하고 싶은데"; "응" to Slack #maestro-claude and personal Linear counting as external):
- D-1 Ranks, the DRI and the message formats apply to all local work, personal and eta; in eta, eta's rules come first. Wrong if: an eta rule and an org-chart rule collide in practice.
- D-2 External records (Linear, Slack incl. #maestro-claude, Notion, PR, commit, deliverables) carry no rank names; `DRI:` lines use plain names. Wrong if: a rank name reaches an external record again.

Owns: `plugins/maeng-harness/skills/harness-run/references/org-chart.md`, `plugins/maeng-harness/skills/harness-run/SKILL.md`, this plan. Vault `hubs/areas/A-ORG.md`, ADR (records).

Exclusions: eta-rules (checked: no rank, delegation or report-format rules); retro-editing existing Linear issues; code, hooks, versions.

Requirements -> acceptance:
  AC-1: org-chart.md states D-1 in its scope sentence and SKILL.md no longer says the rules are off in eta.
  AC-2: org-chart.md "Internal only" states D-2, names Linear, Slack #maestro-claude, Notion, PR and commit, and the `DRI:` line uses a plain name.

## Plan

Verification tier: docs-only.

Verification:
  AC-1: review item expect pass
  AC-2: review item expect pass

Review focus: does any remaining sentence still exclude eta from local use or still allow rank names in Linear or Slack.
