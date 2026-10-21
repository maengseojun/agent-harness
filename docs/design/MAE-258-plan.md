# MAE-258 Spec/Plan: rendered-UI review, UI checklist and DESIGN.md (from ui-ux-pro-max)

status: current. Linear: MAE-258. Date: 2026-10-21. Single PR, small work (Spec/Plan-lite), personal world.

## Spec

Goal: give maeng's company three things its UI work lacks, borrowed from nextlevelbuilder/ui-ux-pro-max-skill @56ea9cf (MIT) without installing it: a review of the rendered UI with evidence, a prioritized pre-delivery checklist, and design decisions per product that survive sessions.

Decisions (2026-10-21 review, recorded on MAE-258):
- D-1 Skip the search engine, CSV corpus, brand/banner/slides/logo skills and `uipro` CLI. The corpus contradicts itself (11/192 categories) and steers toward template looks. The whole repo stays as a reference snapshot in Drive (vault note `wiki/sources/S-ui-ux-pro-max-skill.md`), read only, never executed.
- D-2 Adapt, with the MIT notice: `stack/.claude/agents/design-review.md` -> `maeng-tools:design-reviewer`; `references/quick-reference.md` + the pre-delivery checklist of `pro-rules.md` -> `frontend-guidance/references/ui-checklist.md`.
- D-3 Borrow the MASTER.md + page-override idea as one `DESIGN.md` at the product repo root, written by design-reference once a direction is accepted and read first by frontend work.
- D-4 The official `frontend-design` plugin (skills only, no hooks) is installed at user scope, since frontend-guidance already defers to it. Done outside the repo on 2026-10-21.

Owns: `plugins/maeng-tools/agents/design-reviewer.md`, `plugins/maeng-tools/skills/frontend-guidance/` (SKILL.md, references/ui-checklist.md), `plugins/maeng-tools/skills/design-reference/SKILL.md`, `plugins/maeng-harness/skills/harness-run/` (SKILL.md "Choosing helpers", references/org-chart.md route cell), this plan.

Exclusions: no hook or gate; no plugin version bump (release follows approval); no taste-skill rules (separate proposal); eta untouched.

Requirements -> acceptance:
  AC-1: `design-reviewer.md` exists with valid agent frontmatter (name, description, model, tools), the observe-first rule, the viewport tiers, the review phases including empty/error/loading states and Korean line breaks (`hangul-wrap`), the evidence-ranked report, the org-chart report head and the MIT notice.
  AC-2: `ui-checklist.md` holds the ten priority categories and the app pre-delivery checklist, with every reference to the upstream search tool removed or replaced by a local route, and the MIT notice.
  AC-3: design-reference documents DESIGN.md (where, what it holds, read before regenerating, never overwrite without reading) and points to the archived snapshot for interview and preview flows; frontend-guidance tells frontend work to read DESIGN.md first and links the checklist and the reviewer.
  AC-4: harness-run lists `maeng-tools:design-reviewer` among the agents and the org chart route cell names it.

## Plan

Readiness: base `origin/feat/harness-v1` at 99fa207; branch `feat/mae-258-uiux`.

| Row | Do | Writes | Done | Fails-if | After |
|---|---|---|---|---|---|
| R1 | reviewer agent | agents/design-reviewer.md | AC-1 grep check below | frontmatter does not parse; a phase or the report head is missing | - |
| R2 | checklist | frontend-guidance/references/ui-checklist.md | `grep -c -- '--domain\|--design-system\|search.py'` prints 0; 10 category headings | an upstream search command survives | - |
| R3 | DESIGN.md + pointers | design-reference SKILL.md, frontend-guidance SKILL.md | review item AC-3 | DESIGN.md may be regenerated over an existing one without reading it | R1, R2 |
| R4 | routing | harness-run SKILL.md, org-chart.md | review item AC-4 | - | R1 |

Verification:
- AC-1: `python3 -c` frontmatter parse of design-reviewer.md (name, description, model, tools present) and `grep` for `375`, `hangul-wrap`, `Escalate:`, `MIT`.
- AC-2: the R2 grep; `grep -c '^### ' ui-checklist.md` >= 10; `grep MIT`.
- AC-3, AC-4: review items in the parent review.
- Repo suite: `python3 -m pytest -q` (unchanged code; confirms docs-sync tests still pass).
