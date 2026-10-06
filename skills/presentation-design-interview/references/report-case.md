# Report-style collaboration case

An anonymized policy-news coursework slide became useful after the user rejected several generic designs and chose an actual venture-capital research report as a visual reference. The reusable result is the process, not a permanent brand template.

## Decisions that changed the result

- Research real company report pages and show them before generating new imagery when the user explicitly wants references.
- Compare layouts with evidence on the left and implications on the right, the reverse arrangement, and a horizontal synthesis. Keep the selected arrangement during later refinement.
- Interview the user's reasoning before writing the conclusion. Preserve the difference between an observed word pattern, a personal change of perspective and a proposed time-period comparison.
- Reduce scope metadata to a small line when it repeats the title. Keep required frequency lists and complete example sentences; give implications more room.
- The accepted treatment used white space, dark navy text, restrained teal and lime highlights, multiple weights of a Korean sans serif and smaller supporting evidence. Rejected elements included gradients, broad decorative background panels and an unnecessary English eyebrow label.
- Phrase-level emphasis replaced a long highlight strip. Thin, light rules separated content without boxing every section. A selected headline phrase received emphasis; the entire body did not.

## Implementation lessons

Starting typography for this dense canvas used weights around 350/400/500/750, body leading around 1.5 times size and slightly tighter large-title tracking. These values depend on the font, export size and viewing distance; verify the rendered result rather than copying them mechanically.

When exporting several static weights from a variable font with ReportLab, verify that each registered font has a distinct internal name. Identical internal names can cause different registrations to render with the same cached face. Confirm that the preview actually shows the intended weight contrast.

For ReportLab transparency, set the fill color before calling `setFillAlpha`, inside a saved/restored graphics state. Setting a color afterward can reset the alpha. Inspect the exported PDF/PNG; numeric settings alone don't prove the opacity was applied.

Compare complete original quotations after normalizing extraction whitespace, while preserving wording in the artifact. Inspect the final rendering separately because extracted text cannot reveal overlap or readability.

Small quotations and long frequency lists may be readable in an enlarged PDF but weak when projected. State that limitation. A successful PDF preview does not establish that a native PPTX or a presentation script has been produced.

## Transfer check

For a multi-page startup results presentation, keep the interview/reference/preview/refinement loop but adapt density to spoken delivery and existing branding. Don't import the coursework's one-page constraint, teal/lime palette or analytical conclusion. If the user already supplies a selected reference and complete brief, begin with a representative slide rather than repeating research and interview.
