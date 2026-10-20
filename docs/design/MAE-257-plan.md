# MAE-257 Spec/Plan: the AX org chart (ranks, approval lines, reports, audience, project archive)

status: current. Linear: MAE-257. Date: 2026-10-21. Single PR, personal world only.

## Spec

Goal: borrow a company's rank system so every agent, sub-agent and outside model knows its scope, who it reports to, what it may decide and where it reads first, without restricting access to any information.

Decisions (CEO interview 2026-10-21, recorded on MAE-257):
- D-1 Ranks: CEO = user; outside director = dots-maestro; inside director = Fable (workflow audit, only on the CEO's request or after Opus offers and the CEO accepts); auditor = Astra; consultant = Astra medium via aside (wide or high-stakes research) vs research lead = Opus (ordinary research); executive (상무) = the Opus session; general/deputy manager (부장/차장) = a middle Opus on large projects; team lead to assistant manager (팀장~대리) = Sonnet and Codex Sol 6.1 (effort high for research asides); junior (신입~대리) = Haiku.
- D-2 Approval lines: Haiku edits only (no commit); Sonnet/Sol commit, branch and open a PR; Opus combines work into one PR by default and splits only when one change must merge before another can build (e.g. an api version bump the db repo must then reference); merge only on the CEO's `승인 #N` (G1 unchanged).
- D-3 Report format: first line `[rank→recipient] conclusion`; `Escalate:` (decisions above the sender's line, `none` if empty); `Evidence:` (links or paths only). The implementer keeps `Verification:`/`Unfinished:`.
- D-4 Obsidian: frontmatter `audience` tags plus one per-rank entry index; access stays open, the tag only orders what to read first.
- D-5 eta world untouched.
- D-6 Archive: when a project hub's `closed` date (the CEO said it is finished, or its Linear parent went Done) is 14 days old or more, ask the CEO; on approval move its files with `maeng-archive move --store gdrive` to the seojunmaeng@gmail.com Drive (`googledrive-maeng`), folder `maeng-archive/`, and keep the hub as the index.
- D-7 Every CEO-approved decision is recorded in Obsidian (an ADR).
- D-8 (CEO, 2026-10-21, mid-run) Speed over ceremony: escalate straight to the rank that can decide (skip levels, up to the CEO); verify once, no sequential rank-by-rank review; every wait must earn its place, and when unsure whether it is needed, ask the CEO; every loop has a stop criterion fixed in advance.

Owns: `plugins/maeng-harness/skills/harness-run/` (SKILL.md, references/org-chart.md), `plugins/maeng-harness/skills/work-records/SKILL.md`, `plugins/maeng-harness/lib/maeng/handlers.py` (SessionStart context only) and its test, `plugins/maeng-tools/agents/*.md`, `plugins/maeng-tools/skills/obsidian-workspace/references/claude-edition.md`, `plugins/maeng-tools/skills/maeng-archive/` (SKILL.md, scripts/archive.py store detection and its test), this plan. Vault note `hubs/areas/A-ORG.md` (record, written through Obsidian MCP).

Exclusions: no new gate or hook enforcement of ranks or report fields (slim gates); no eta change; no Google Drive MCP setup (needs the user's OAuth; separate task); no plugin version bump (release is a follow-up commit after approval).

must_haves:
  truths:
    - T1: one document names every rank, its model/route, what it does, what it may decide, whom it reports to and where it reads first.
    - T6: the org chart states D-8 (skip-level escalation, verify once, justify every wait or ask, loop exit criteria).
    - T2: the PR rule says "one PR by default; split only when a merge must land first for another change to build".
    - T3: the delegation and report format (D-3) appears in the org chart and in the three agent definitions.
    - T4: a SessionStart in the personal world lists project hubs whose `closed` date is 14 or more days old and not archived, and lists nothing for younger, missing, malformed or archived dates.
    - T5: the gdrive store prefers `GoogleDrive-seojunmaeng@gmail.com` when it exists; `MAENG_ARCHIVE_GDRIVE` still overrides.
  artifacts:
    - A1: `plugins/maeng-harness/skills/harness-run/references/org-chart.md` - ranks, approval lines, PR rule, report format, audit trigger, research routing, reading order.
    - A2: `plugins/maeng-tools/skills/obsidian-workspace/references/claude-edition.md` - `audience` and `closed` keys and the audience-first retrieval step.
    - A3: `plugins/maeng-harness/skills/work-records/SKILL.md` - CEO-decision ADR rule and the project archive flow.
  key_links:
    - K1: harness-run SKILL.md -> org-chart.md (link in "Choosing helpers").
    - K2: SessionStart context -> org chart pointer line and the archive-candidate line.
    - K3: work-records archive flow -> `maeng-archive move --store gdrive` -> gmail Drive root.

Requirements -> acceptance:
  AC-1: org-chart.md exists with all ranks of D-1, the lines of D-2, the format of D-3 and the rules of D-8, linked from harness-run.   covers T1, T2, T6, A1, K1
  AC-2: architect, implementer and researcher definitions carry the D-3 report head and Escalate/Evidence fields; implementer says a junior (Haiku) brief means no commit.   covers T3
  AC-3: claude-edition.md documents `audience` (values ceo, director, auditor, exec, team, junior) and `closed`, and the retrieval step reads the reader's audience first without hiding the rest.   covers A2
  AC-4: work-records documents D-6 and D-7.   covers A3, K3
  AC-5: SessionStart archive-candidate listing behaves as T4 and the context still fits 2 KB.   covers T4, K2
  AC-6: gdrive store detection behaves as T5.   covers T5, K3

## Plan

Readiness: decisions settled (MAE-257); base `origin/feat/harness-v1` at 6eaace6; branch `feat/mae-257-org-chart`.

Sub-tasks:

| Row | Do | Writes | Done | Fails-if | After |
|---|---|---|---|---|---|
| R1 | org chart doc + harness-run link | harness-run SKILL.md, references/org-chart.md | review item AC-1 | a rank of D-1 or the PR exception of D-2 is missing or reworded into a different rule | - |
| R2 | agent definitions | maeng-tools/agents/*.md | review item AC-2 | SubagentStop still needs `Verification:`/`Unfinished:`; dropping them breaks it | R1 |
| R3 | vault keys + retrieval | claude-edition.md; vault `hubs/areas/A-ORG.md` | review item AC-3 | audience used as an access filter | R1 |
| R4 | records + archive flow | work-records SKILL.md, maeng-archive SKILL.md | review item AC-4 | archive runs without the CEO's yes | R1 |
| R5 | SessionStart archive candidates + pointer | handlers.py, tests/test_stop_hooks.py | `python3 -m pytest -q plugins/maeng-harness/tests/test_stop_hooks.py -k session_start` passes | vacuous pass: replacing `>= 14` with `>= 0` (or dropping the archived skip) still passes the test | - |
| R6 | gmail Drive default | archive.py, test_archive.py | `python3 -m pytest -q plugins/maeng-tools/skills/maeng-archive/scripts/test_archive.py -k gdrive` passes | vacuous pass: reverting to the first sorted GoogleDrive-* still passes | - |

Verification tier: code (hook context change).

Verification:
  AC-1: review item (parent review, Sol) expect pass
  AC-2: review item; `python3 -m pytest -q plugins/maeng-harness/tests/test_stop_hooks.py` expect pass
  AC-3: review item expect pass
  AC-4: review item expect pass
  AC-5: `python3 -m pytest -q plugins/maeng-harness/tests/test_stop_hooks.py -k session_start` expect pass; mutation `>= 14` -> `>= 0` expect fail
  AC-6: `python3 -m pytest -q plugins/maeng-tools/skills/maeng-archive/scripts/test_archive.py -k gdrive` expect pass; mutation (drop the preference) expect fail
  Ship: `python3 -m pytest -q` at the final tree expect pass

Failure / change handling: per harness-run Failure handling; three repair cycles, then split or drop and name it in the CEO brief.

Review focus: does any text turn ranks into an access restriction or a new gate; does the PR rule match D-2 exactly; does the SessionStart scan stay cheap (hubs/projects only, frontmatter only) and silent on bad dates.
