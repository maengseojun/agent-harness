# Requested delivery formats

Choose the deliverable set before drawing. A requested format also authorizes its export in this turn; do not wait for a second export request.

| Request | Deliver and save to school Drive |
| --- | --- |
| “PNG만”, “PNG only” | PNG only |
| “SVG만”, “SVG only” | SVG only |
| “PNG랑 SVG”, “PNG+SVG” | Both PNG and SVG |
| “이미지만”, “그림 파일만”, “image only”, without a named format | PNG only; state this choice briefly |
| No image-only restriction, or an explicit source/HTML request | The inspected HTML, published as a private Artifact, plus requested exports |

**Artifact first (personal, 2026-10-29).** When the delivery includes HTML, publish it with the Artifact tool by default, following that tool's page contract, and give the link. Hand over a local file path or use another route only when the user asks for it. Image-only requests below are unchanged.

For image-only delivery:

1. Author the Diagram Design HTML/inline SVG once, retaining the current local fonts and one-canvas rules. Keep the HTML in a private working-source location, separate from the delivery folder.
2. Export only the selected deliverable formats. For SVG, use the existing `scripts/export_svg.py` with `--system-fonts` to retain the local-font CSS without adding Google Fonts imports. For PNG, follow `export.md`: render the original HTML, await fonts, and capture the SVG element at the requested size/scale. An already installed Node Playwright renderer may perform the same capture when Python Playwright is unavailable; never install a new dependency automatically. Reuse the authored geometry; never draw a second version to make an export.
3. Inspect the selected outputs. Parse SVG as XML and check the exported rendering, IDs, text, connectors and fonts. PNG needs actual rendered inspection. Temporary validation images are private checks, not additional deliverables. Verify that essential titles, units, conditions and legends are inside the SVG; an export drops the surrounding HTML. Put missing meaning inside the diagram rather than quietly returning HTML as a supplement.
4. Preview and link only the requested images in the response. Do not attach/open the HTML or offer unsolicited source/preview files. If this host cannot display SVG inline, link the actual SVG and state the preview limit; do not substitute or deliver an unrequested PNG. A selected-format failure is a disclosed gap, not permission to silently change formats.
5. Upload/read back only the selected delivery files under `delivery-storage.md`. Keep the HTML, temporary captures and logs local unless the user separately requests source delivery/storage. Preserve earlier outputs and use distinct names for new versions.

HTML remains an internal authoring source in this route. “Show/deliver only SVG” does not prohibit that source. This update does not implement HTML-free authoring; do not claim that it satisfies “do not create HTML at all”, or silently introduce a separate authoring/check pipeline.

SVG carries editable vector content, but these local font faces are not embedded; disclose portability limits when relevant. For PNG, confirm text remains readable at its intended viewing size. Existing import, explicit draw.io, text-only, interactive and video boundaries stay unchanged.
