# Personal additions to Diagram Design

The upstream skill is the authoring method, not an intermediate format or a gallery to imitate after another drawing pass. Read the selected type guide and actual example, then create the final HTML/inline SVG once. Use original export helpers for mechanical derivatives. The original semantic colors, connector grammar and shapes take priority over former local skins; apply the user's current five-face [local font default](local-fonts.md) instead of the original typography.

## One canvas and visible structure

For a research summary, combine the useful comparisons, dependencies, causes or process regions on one coherent canvas. Use shared positions, axes or paths to expose relationships; avoid a grid of paragraph cards. A complete timeline stays on one canvas where readable; without reliable dates, label it as an ordinal event sequence. Do not interpret adjacency as causation. If detail genuinely needs another view, retain an overview of the whole and link the detail instead of turning the result into a slide deck by default.

## Preserve and verify

- Preserve unrelated user files and earlier delivered outputs. Edit an existing artifact in its requested format unless the user asks to migrate or redesign it. Do not silently re-author it.
- Follow upstream HTML/SVG export rules, check SVG IDs/defs, text bounds, connectors and actual fonts, and inspect the real rendered result. A geometry reconstruction, hash check or file listing is not rendered validation.
- Use the selected LINE Seed/Nunito faces. Inspect actual Hangul glyphs and word-boundary line breaks; SVG needs text-bound measurements, while HTML prose needs role-specific wrapping checks at desktop and mobile widths. Do not install alternate fonts or apply blanket keep-all by default.
- Use an already available renderer for a short preview, close task-created tabs, and avoid new browser/dependency installations. Do not open a draw.io Desktop or browser editor. If rendering is unavailable, preserve the HTML/SVG and state the precise gap.
- Generate only a useful supporting symbol, object or partial illustration when it adds information. Keep overall geometry, labels and relationships in the authored SVG. A whole generated image is a different explicitly requested format.
- A native `.drawio` result is an optional explicit format request, using available draw.io MCP capabilities directly. Check those capabilities before promising it; never create it as an intermediate for default Diagram Design output or use editor control as a silent fallback.

## Delivery

Return the actual requested files under [delivery-formats.md](delivery-formats.md), not only a plan or skill-installation claim. Image-only requests deliver only their selected PNG/SVG files; keep HTML source, validation captures and long logs private. Save the selected delivery set through [delivery-storage.md](delivery-storage.md). Confirm source copy, installation, host discovery, actual current-task execution and remote save separately.
