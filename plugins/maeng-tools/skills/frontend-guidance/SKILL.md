---
name: frontend-guidance
description: Use when building or refining a website, landing page or app UI and the user wants a specific visual style, a Korean-language UI, or a UI accessibility/compliance audit (웹 디자인, 랜딩페이지, 화면 다듬기, UI 감사, 접근성 점검), or names taste-skill (taste 그대로, taste 참고). Adds only the user's deltas on top of the official frontend-design skill - use that one for general design craft. Not for backend work or HTML slide decks (use frontend-slides).
---

# Frontend guidance (deltas only)

For general design craft (hierarchy, type, layout, motion, avoiding generic AI looks) use the official `frontend-design` skill. This skill adds only these rules:

- **Read the product's `DESIGN.md` first** when the repo has one (see `design-reference`): build to its tokens and accepted choices, with a page section overriding the global one. A choice that departs from it goes back into the file, not only into the code.
- **The user's inputs win.** Requested fonts, palettes, references and aesthetics override taste-based warnings. Inspect the existing product and references first; ask only when a missing fact changes the outcome.
- **Preserve product facts and behavior** while refining; change presentation, not content or logic.
- **Surface decides emphasis.** An operating dashboard favors scanability; a landing page supports its message and one action.
- **Korean UI:** run `hangul-wrap` before shipping so words do not split mid-syllable-group; do not claim a fix without its measurement.
- **Verify the rendered result,** not the code: relevant desktop and mobile widths, keyboard focus, text overflow, reduced motion when anything moves. Report what was actually checked and what was not. Optional style advice never waives accessibility or correctness checks. Before delivery, take a final pass over the CRITICAL and HIGH categories of the [UI checklist](references/ui-checklist.md); for a page or flow, have the `maeng-tools:design-reviewer` agent review the rendered result.
- **taste-skill** named by the user: follow `design-reference`'s [taste-skill modes](../design-reference/references/taste-skill.md). Follow mode replaces the style rules above with taste's run; Borrow mode keeps them.
- **HTML deck:** use `frontend-slides`; do not apply responsive page rules to a fixed slide canvas.
- **Cinematic landing page** (references, generated hero image or video background, built in stages): use `cinematic-site`.
- **Generated images** (hero, illustration, background, mock): GPT Image through the OpenAI Images API, `codex exec` as the fallback, asked before each run, as in `cinematic-site` prompts §1. Never generate the real product UI, logos or data.
- **Dithered/stippled motion landing page:** recover the archived `dither-motion-landing` guidance from the MAE-127 GitHub archive when needed; do not silently reinstall it.
- **UI compliance audit** (former `web-design-guidelines`): only when asked or concretely needed, follow [UI audit](references/ui-audit.md). Do not stack equivalent reviews.

Optional upstream reading (Impeccable, pinned revision, fetch only when it resolves a real question): [design references](references/design.md).
