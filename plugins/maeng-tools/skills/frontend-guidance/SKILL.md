---
name: frontend-guidance
description: Use when building or refining a website, landing page or app UI and the user wants a specific visual style, a Korean-language UI, or a UI accessibility/compliance audit (웹 디자인, 랜딩페이지, 화면 다듬기, UI 감사, 접근성 점검). Adds only the user's deltas on top of the official frontend-design skill - use that one for general design craft. Not for backend work or HTML slide decks (use frontend-slides).
---

# Frontend guidance (deltas only)

For general design craft (hierarchy, type, layout, motion, avoiding generic AI looks) use the official `frontend-design` skill. This skill adds only these rules:

- **The user's inputs win.** Requested fonts, palettes, references and aesthetics override taste-based warnings. Inspect the existing product and references first; ask only when a missing fact changes the outcome.
- **Preserve product facts and behavior** while refining; change presentation, not content or logic.
- **Surface decides emphasis.** An operating dashboard favors scanability; a landing page supports its message and one action.
- **Korean UI:** run `hangul-wrap` before shipping so words do not split mid-syllable-group; do not claim a fix without its measurement.
- **Verify the rendered result,** not the code: relevant desktop and mobile widths, keyboard focus, text overflow, reduced motion when anything moves. Report what was actually checked and what was not. Optional style advice never waives accessibility or correctness checks.
- **HTML deck:** use `frontend-slides`; do not apply responsive page rules to a fixed slide canvas.
- **Dithered/stippled motion landing page:** recover the archived `dither-motion-landing` guidance from the MAE-127 GitHub archive when needed; do not silently reinstall it.
- **UI compliance audit** (former `web-design-guidelines`): only when asked or concretely needed, follow [UI audit](references/ui-audit.md). Do not stack equivalent reviews.

Optional upstream reading (Impeccable, pinned revision, fetch only when it resolves a real question): [design references](references/design.md).
