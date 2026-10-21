---
name: design-reference
description: Maintain the user's design reference site catalog and use actual examples to choose a visual direction for presentations, websites, apps, logos, icons, posters, social previews, or motion. Use when the user asks to add a reference site or wants a design interview and reference-based previews; pair with the relevant production skill.
---

# Design Reference

Use [the site catalog](references/sites.md) as the shared starting point for design references. It is a source list, not a universal style preference or an asset license. Work in the user's language and retain previously accepted choices.

## Add or maintain sites

When the user asks to add a site, update `references/sites.md` in this skill rather than leaving the URL only in chat. If this installed skill is a symlink, edit its resolved source so there is one catalog. Do not create a second list in the presentation skill or in each project.

- Read the current catalog first. Remove message-format escaping from a supplied URL. Compare host and meaningful path for duplicates; ignore a trailing slash, a `www` prefix, and tracking parameters for comparison, but retain meaningful paths and query parameters in stored URLs. Merge notes into an existing entry instead of duplicating it. Treat HTTP/HTTPS variants as duplicate candidates; do not change the stored scheme without checking support.
- Inspect the site through the available browser workflow. Record the category, useful situations, the user's specific liked feature if provided, date added, and the last actual check with access notes. If access fails, still save the requested site with its description attributed to the user and its access gap explicit. Never record a successful check from a search snippet or a request acknowledgement.
- Add to the closest category or add a category when needed. Use the existing row fields. Leave unknown taste, access, or dates explicit rather than guessing.
- Re-read the changed catalog and confirm the saved URL, category, and any access gap. Do not claim the site was added until the file contains it.

A local addition does not publish to GitHub. Keep changes locally for a later grouped PR; push, PR creation, and merge need the user's authorization. If the installed skill is a separate copy, update its known source and installed catalog together and compare them; do not claim synchronization with an unavailable source or host.

## Interview and choose a direction

Inspect supplied content and references, then ask only unanswered questions that affect the result: audience and use, required content, output and size, desired impression, and dislikes. For presentations, pair with `presentation-design-interview` and reuse its brief instead of restarting the interview.

Read the relevant catalog categories, then open suitable actual works or screens. The catalog is a starting point; use other sources when they better fit the brief. Do not browse every site on every task. Follow the host's browser routing and disclose inaccessible sources.

Show actual reference images or accessible previews with direct source links. Explain which visible choices would transfer: hierarchy, typography, spacing, alignment, color, imagery, navigation, or motion. Separate observed features from proposed adaptations. Adding a site does not mean the user likes every style on it; distinguish user-stated preferences from your inferences. Do not infer confirmed fonts or asset reuse permission from appearance.

When comparison helps, create two or three small, meaningfully different previews using the same representative user content. Label placeholders and omitted content. If the direction is already settled, refine it instead of generating alternatives. After selection, keep a compact brief of accepted and rejected choices, source links, and open questions.

For a checklist of interview questions or of axes to vary between previews (for example variance, motion and density), the archived ui-ux-pro-max snapshot (vault note `wiki/sources/S-ui-ux-pro-max-skill.md`) lists where to look. It is reading material: never install it or run its scripts, and do not take a direction from its product-to-style tables.

## Keep the direction in DESIGN.md

For a product with its own repository, write the accepted brief to `DESIGN.md` at the repo root so later sessions build to the same decisions. It holds: the direction in one paragraph with its source links; tokens layered primitive → semantic → component (components use semantic tokens, never raw hex); accepted and rejected choices with the date and who decided; open questions; and one `## Page: <name>` section per page that overrides the global rules.

- Read an existing `DESIGN.md` before changing it. Update the sections the new decision touches; never regenerate the file over earlier decisions. A change to an accepted choice needs the user's say-so and is recorded as a new dated line, not a silent edit.
- A one-off artifact (a deck, a single explainer) keeps its brief in the task, not in a `DESIGN.md`.

## Produce with the relevant skill

Pass the accepted brief to the appropriate presentation, document, frontend, image, or motion workflow. This skill supplies reference selection and direction, not a replacement authoring tool. Preserve the requested format and editable elements where required. Verify the actual output using that production skill's checks; distinguish a preview, a rendered artifact, and user acceptance.
