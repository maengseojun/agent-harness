# MAE-272 Spec/Plan: borrow Archify's methods into our diagram skills, keep our skin

Linear: MAE-272. Date: 2026-10-25. One PR, no child issues.

User approval (2026-10-25, this session): "말한 범위(표현 규칙 reference + 우리 스킨 탐색 컨트롤러 + 기존 Archify 경로 정리)로 PR 진행해."

## Spec

Goal: diagrams and explainer pages made by `diagram-explainer` / `interactive-explainer` keep the Diagram Design skin (paper/ink tokens, 1–2 accents, LINE Seed fonts), while adopting how Archify (tt-a1i/archify v3.2.0, MIT, commit 25cf370) decides relationship meaning and color, places nodes and labels, explains (conclusion first, steps beside the diagram), and lets the reader explore (focus/reach, route, lens, finder, deep links).

Mandatory rules:
- No change to the existing skin tokens in `style-guide.md` or to the motion controller in `assets/template-motion.html`. Amended mid-task (user, 2026-10-25: "근데 색깔 1~2개정도는 더 써도 되겠다" / "가시성을 위해서"): two relationship-color tokens may be added, see D-4.
- Archify's renderer, JSON schemas and viewer code are not copied; only its authoring rules (restated) and interaction ideas. MIT attribution in `THIRD_PARTY_LICENSES.md`.
- Generated pages stay single-file, no remote scripts, no dependencies.

must_haves:
- truths: the new rules reference maps every Archify relationship variant to one of our existing tokens; the explore controller works on plain SVG with `data-node` / `data-edge` markup; `self_check.py` accepts the canonical explore controller and rejects a modified one.
- artifacts: `references/archify-methods.md`, `assets/template-explore.html`, edited `scripts/self_check.py`, edited interactive-explainer docs/wrapper.
- key_links: `SKILL.md` and `animation.md` point to the new reference and template; interactive-explainer routes path/state exploration to the explore template first.

- **AC-1** `diagram-explainer/references/archify-methods.md` exists and covers: relationship variants → our tokens (with `guard`/`data` added to `style-guide.md`, D-4), legend-only-used-variants, placement rules with the label-gap and fan-out formulas (CJK counted twice), conclusion-first panels, steps beside the diagram titled with node labels, text-to-node links, form-by-information-shape table. `SKILL.md` links it.
- **AC-2** `diagram-explainer/assets/template-explore.html` is a working page in our skin: clicking or choosing a node lights its upstream/downstream reach and dims the rest; route mode shows a directed path between two nodes or says there is none; kind lens and finder work; steps list lights nodes with prev/next; `#focus=`, `#route=a~b`, `#lens=` restore on load; Escape clears; status text announces changes; state is never color-only; reduced motion respected.
- **AC-3** `self_check.py` passes `template-explore.html` and `template-motion.html`, still passes existing examples, and fails on: a modified explore controller, an edge whose `data-from`/`data-to` names a missing node, a duplicate `data-node` id. Covered by a test file in the skill's `scripts/`.
- **AC-4** interactive-explainer: the default route for path/state exploration is diagram-explainer + `template-explore.html`; the Archify route is used only when the user asks for Archify's own look or viewer features. The wrapper no longer points at the never-committed `vendor/archify/` path: it uses `ARCHIFY_HOME` or `~/.claude/skills/archify` and fails with a clear message when neither exists.
- **AC-5** MIT attribution for Archify is recorded; `upstream-manifest.json` lists `scripts/self_check.py` as customized with its new hash; maeng-tools version bumped so sessions pick it up.

Decisions:
- **D-1** Restate Archify's rules in our token names rather than vendor its renderer. Signal: a diagram made with the reference renders in our skin and passes self_check. Held/broke judged at close.
- **D-2** The explore controller is a second canonical script (`data-diagram-explore`), enforced like the motion one. Signal: self_check rejects edits to it.
- **D-3** Comet-style motion on every edge is not adopted (conflicts with animation.md budgets).
- **D-4** Add `guard` (#6d3fa0 / dark #b99be8, security/policy) and `data` (#1d7368 / dark #5fc2b3, store read/write) as relationship colors; `accent` stays the single focal color and the explore selection color; security nodes move from accent-dashed to guard-dashed. Signal: both clear 4.5:1 on paper in both skins and the template reads the three relationship kinds apart.

## Plan

Steps:
1. Write `archify-methods.md` (AC-1), link from `SKILL.md`.
2. Build `template-explore.html` with the controller (AC-2).
3. Extend `self_check.py` + tests (AC-3); update `animation.md` sentence on controllers; manifest (AC-5).
4. Edit interactive-explainer `SKILL.md`, `references/archify-local.md`, `scripts/archify_local.mjs` (AC-4).
5. Attribution + version bump (AC-5).

### Sub-tasks

| Do | Writes | Interfaces | Done | Fails-if | After |
|---|---|---|---|---|---|
| Rules reference | references/archify-methods.md, SKILL.md | token names from style-guide.md | parent review item: every Archify variant mapped to an existing token | a token named that style-guide.md lacks | – |
| Explore template | assets/template-explore.html | `data-explore-root`, `data-node`, `data-kind`, `data-edge`, `data-from`, `data-to`, `data-variant`, `data-explore-steps`, `data-target`, `data-node-link` | browser: focus/route/lens/finder/steps/hash checked in the pane | route found by geometry instead of authored edges; dim-only state | – |
| Linter | scripts/self_check.py, scripts/test_self_check.py, references/animation.md, upstream-manifest.json | `data-diagram-explore` script attr | `python3 -m pytest -q scripts/test_self_check.py` passes | test passes when controller body is edited (vacuous) | Explore template |
| Archify route | interactive-explainer/SKILL.md, references/archify-local.md, scripts/archify_local.mjs | `ARCHIFY_HOME` | `node scripts/archify_local.mjs doctor` → "Archify is ready."; with `ARCHIFY_HOME=/nonexistent HOME=/nonexistent` → exit 2 and message | wrapper silently runs a different binary | – |
| Attribution, release | diagram-explainer/THIRD_PARTY_LICENSES.md, plugin.json | – | `claude plugin validate plugins/maeng-tools` | – | all |

## Verification

Verification tier: code (skill scripts) + docs. Ship checks, once at the final tree:
- AC-3: python3 -m pytest -q plugins/maeng-tools/skills/diagram-explainer/scripts/test_self_check.py
- AC-3: python3 plugins/maeng-tools/skills/diagram-explainer/scripts/self_check.py plugins/maeng-tools/skills/diagram-explainer/assets/template-explore.html
- AC-2: browser check of template-explore.html in the app's browser pane (declared with maeng-verify ran)
- AC-4: wrapper doctor and missing-home run (declared with maeng-verify ran)
- AC-5: claude plugin validate plugins/maeng-tools
- AC-5: python3 -m pytest -q
- AC-1: review item in the parent review
