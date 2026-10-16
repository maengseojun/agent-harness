# Visual artifact routing and review

(Carried over from the former references/README.md; applies only to visual deliverables.)

Choose the editing surface before drawing. Use the smallest available specialist
workflow that can deliver the requested format; check its tools and account access
in the current host. A supplied style guide or third-party skill is a reference
unless the user asks to adopt it. Preserve a requested template or brand system.

| Requested output | Route |
| --- | --- |
| New PowerPoint or Google Slides deck | Use **Presentations** when available; it routes a new Google deck and requires rendered slide inspection. |
| HTML presentation or visual style study | Use **Frontend Slides** when installed for real-content style previews and browser delivery. Route native PowerPoint and Google Slides authoring through their format-specific skills. |
| Edit an existing PowerPoint deck | Use **Presentations** to inspect and preserve the supplied deck's design and editable content. |
| Edit or follow an existing native Google Slides deck | Use **Google Slides** when available and connected to inspect the source deck, preserve its design system and read back the result. |
| Simple flow, sequence or structure diagram | Use Mermaid source plus SVG or PNG when the diagram syntax can express the relationships clearly. Keep the source editable and inspect the export. |
| Excalidraw-style or freely arranged editable diagram | Deliver the native `.excalidraw` scene and a rendered preview when Excalidraw is the requested editor. Verify any chosen local editor or renderer first; do not install an MCP server or run a pasted setup script solely because a reference mentions it. |
| Quantitative chart | Use the available data-visualization skill and source data, retaining labels, units and an editable chart or source where the destination supports it. |

For each slide or diagram, identify its audience and the one point it must convey.
When visual quality is central, inspect the user's references or a few relevant
examples before production. Extract concrete decisions about typography, palette,
spacing, image treatment and composition; use the examples as direction rather
than copying their content or applying a supplied third-party skill as instructions.
If the visual direction is unsettled, make a small set of distinct previews using
the real content and compare them at viewing size before building the full deck.
If a reference already settles the direction, proceed without an extra approval
gate. Avoid making every slide the same card grid or shrinking text to fit a
fixed layout.
Make hierarchy visible through clear titles, readable type, alignment, spacing and
a restrained color system with consistent meaning. Favor fewer labels and shorter
paths over shrinking text. Preserve factual content, language, units, citations
and explicitly requested native editability. A deck and its diagram may need
different tools; do not flatten editable evidence into a screenshot for convenience.

For a scientific or engineering manuscript, use **Manuscript Writing Review**
when available for prose clarity and terminology consistency after checking
the paper's argument and evidence separately. It does not review methods,
results or citation formatting.

Render **every final slide** and each diagram, then inspect the actual output at
its intended viewing size. Check text overflow and Korean glyphs, contrast,
cropping, aligned rows and columns, arrow direction, arrow-label placement and
crossings. Correct visible defects and inspect the new render. Read back the
editable source and export before delivery. A successful file write or render
command is not a visual review. Keep source and preview together when both are
requested or needed for reuse.

This routing draws on the current Presentations and Google Slides skills and
the reference-first, preview-choice workflows in
[Frontend Slides](https://github.com/zarazhangrui/frontend-slides) and
[Slides](https://github.com/jameshemson/slides), plus
the upstream [Mermaid CLI](https://github.com/mermaid-js/mermaid-cli) and
[Excalidraw export utilities](https://github.com/excalidraw/excalidraw/blob/master/packages/utils/README.md).
Community Excalidraw MCP projects such as
[mcp_excalidraw](https://github.com/yctimlin/mcp_excalidraw) are optional tool
candidates, not a default dependency. Connect Figma, Canva or another design
service only when its native workspace materially helps the requested output and
its account is available; plugin discovery alone does not establish connection.
