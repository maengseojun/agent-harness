---
name: presentation-design-interview
description: Co-design presentations and report slides through a focused interview, real visual references, layout previews, and typography refinement. Use when the user wants help discovering or refining a presentation's content and visual direction; pair with the requested artifact-format skill for production.
---

# Presentation Design Interview

Turn the user's material and taste into an evidence-grounded, reviewable presentation. Work in the user's language. Reuse settled decisions; enter at the current stage instead of restarting an interview or generating another deck after every comment.

## Establish the brief

Inspect supplied slides, templates, analysis outputs, reference images and prior feedback first. Separate assignment requirements from document text, the user's instructions, and proposed improvements. Preserve required counts, original quotations, sources and output format.

Ask only unanswered questions that change the result: audience, use (speaking, reading, or both), time/page limits, central finding, desired tone and what the user dislikes. During a content interview, explain a section's role, offer a short faithful wording, and ask one focused question or a small set of meaningful choices. Resolve factual questions from source material rather than asking the user to remember data.

Keep a compact working brief: accepted content, visual choices, rejected approaches, sources and remaining questions. Separate findings, the user's reflection and future research; don't turn an exploratory interpretation into a demonstrated causal claim.

## Find the visual direction

Use the installed `design-reference` skill and its `references/sites.md` catalog for shared reference discovery. If both skills are installed as siblings, its entrypoint is `../design-reference/SKILL.md`; otherwise resolve it from the host's skill catalog (on this host, `~/.codex/skills/design-reference/SKILL.md`). Read the relevant presentation or other design categories, then inspect actual examples. Route requests to add sites through that skill's single catalog; do not keep a duplicate list here. Reuse the established brief and retain the original-company-report and credited-designer sources below when they fit better than catalog entries. If the common skill is unavailable, disclose the gap and continue with supplied references.

If taste is unresolved or the user rejects generic design, inspect actual report or presentation pages before inventing another style. Prefer original company reports, event decks or credited designers. Show actual images with working source links; distinguish a report page from a conference photograph or product screenshot. If browser choice is specified, honor it.

Extract visible design decisions: information hierarchy, content proportions, typography, alignment, spacing, chart grammar, color and emphasis. Don't identify a font by appearance as a confirmed fact. Don't assume a reference's identity or color scheme is what the user likes; ask about the relevant visual choice when needed.

Show a small set of genuinely different layouts, typically two or three if comparison is useful. Use the same representative content so arrangement can be assessed; sparse previews are fine when the user wants design first. Label omitted content and placeholders. State the visual difference plainly. Don't require multiple options when the direction is already settled.

Use real charts, native text and simple shapes for factual material. Generated imagery is optional when it serves the message; don't rasterize the entire slide to solve typography. Use an available image workflow only within its permissions and cost limits. A login error or failed generation is not an artifact; continue with editable layouts if that meets the request.

## Refine content and hierarchy

Before arranging the slides, use the available coherent-writing skill to check the explanation's through-line and evidence-to-conclusion links. Reuse accepted content and interview decisions. Design previews are for unresolved visual choices; they do not replace production when the user asks to execute the agreed work.

Once the user picks a direction, keep that layout and refine section wording. Allocate space according to the confirmed message and mandatory detail. A compact scope/method line can free space for implications and next questions. Preserve the requested template's semantic sections even if the visual arrangement changes.

Distinguish slide text from spoken explanation when relevant. In a constrained one-page report, compact supporting evidence before reducing the main conclusion. If all required evidence needs small type, disclose the reading limit instead of silently omitting material. Don't add slides against a fixed page requirement.

## Tune typography and visual weight

Use a coherent font family with deliberate weights for title, headings, body, numbers and notes. Check Korean glyph coverage and actual weight availability. Readability takes priority over novelty; a familiar report font is suitable if its hierarchy works. Download additional fonts only when needed and verify source/license before distributing them.

Tune title tracking, body leading, line breaks, paragraph spacing and alignment separately. Keep quotations legible rather than applying the lightest weight everywhere. Bold only the phrases that carry the argument. Review word breaks and visual density at the intended presentation size.

Include table cells, chart axes, legends and data labels in that size check; geometry without overlap does not establish legibility. After the final material change, review that revision in the intended renderer or PowerPoint when it is the destination. Resolve Korean theme-font fallback and inspect page/slide breaks instead of assuming an earlier PDF or headless preview proves the editable file. Keep reader comprehension separate from successful export and visual inspection.

Respond to “AI slop” by locating the concrete excess: repeated cards, a large tinted panel, decorative labels, full-width highlight strips, gradients or uniform boldness. Remove or reduce that excess while preserving useful hierarchy. A gradient is neither required nor universally forbidden; explicit user feedback governs. Borrow thin rules, restrained transparency and phrase-level highlights from a selected reference only when they help reading.

For the observed report-style case and production pitfalls, read [references/report-case.md](references/report-case.md). These are example decisions, not mandatory colors, ratios or type sizes.

## Produce and verify

Use the available presentation skill for native PowerPoint/Google Slides, PDF skill for PDF previews, or HTML-slide skill when HTML is requested. This skill coordinates design and content; it does not replace format-specific authoring. Don't force the user into HTML or claim a PDF is an editable PPTX.

Render the actual artifact after material edits. Inspect every page for clipping, overlap, glyphs, line breaks, chart labels, emphasis and opacity; a successful build is insufficient. Check required figures, quotations and counts against the inspected source. Different analytical scopes may require separate denominators; don't imply raw counts are directly comparable.

Deliver a visible preview plus links to the requested files. Briefly state changes, checks and any density/format/access limit. Keep the accepted direction for subsequent small edits. File existence, visual verification and user acceptance are distinct states.
