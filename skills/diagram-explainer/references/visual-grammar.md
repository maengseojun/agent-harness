# Visual grammar in draw.io

Use marks whose visible meaning matches the information. This applies to prose, tables, charts, formulas and drawings as well as node-and-edge views. [Representation selection](representation-selection.md) governs what to show; [Explanation layout](explanation-layout.md) governs reading order.

## Lines, position and logical operators

Before drawing, identify what each line/position/shape asserts. Use only the vocabulary the view needs:

| Visible mark | Possible meaning | Check |
|---|---|---|
| Action/transfer arrow | Something happens or moves to a target | Action/object, direction, trigger/branch and result |
| Logical implication arrow or ⇒ | Premises imply a conclusion | Direction, necessary/sufficient/iff, explicit AND/OR; not chronology or cause |
| Headless relation line | Association, membership or dependency | Name the relation; direction only when meaningful |
| Bracket/brace/span | These items/stages/interval belong to this scope | Exact start/end and gaps; no extra process node |
| Nested/overlapping boundary | Containment, intersection, excluded region | Domain and membership; distinguish set from responsibility/reading group |
| Leader/callout | This explanation refers to that item/value | Unambiguous target; it is not a process edge |
| Axis, tick, grid or reference line | Quantitative location/baseline/threshold | Units, map, range and actual value; no arrow for an actor handoff |
| Trace or paired-value connector | Series continuity or difference between values | Data/time basis; no invented causality or intermediate observations |
| Divider/alignment/whitespace | Reading hierarchy or comparison | Does not assert containment or execution order |

Declare local meanings when ambiguous, preferably directly; use a small editable legend only when needed. Dashed is not universally uncertain, conditional or asynchronous. A sequence can use dashed returns and vertical lifelines; a chart's dashed reference line and a boundary's dashed outline have different jobs. Color alone must not carry a consequential distinction. Use actual editable swatches/line samples when a legend is present, matching the marks.

For joint premises, explicitly show AND, OR or XOR or use a condition table. Converging arrows without an operator do not define a Boolean rule. Distinguish logical implication, permission, cause, correlation, message and transfer. Preserve formal/domain notation when required; do not replace it with generic arrowheads for stylistic consistency.

Bind genuine relationship/action connectors to their shapes, preserve source/target IDs and perimeter ports, and use only the bends needed for legibility. Straight segments work for clear short paths; elbows avoid unrelated objects; curves can clarify a return. Keep separate request/return paths when order matters. Quantitative lines and brackets attach to their data/scope geometry, not fictional nodes. Automatic routing/layout must not move measured or meaningful spatial coordinates.

## Surfaces and shape roles

The user's rounded rectangle preference applies to ordinary cards, action/entity nodes, notes, headers and group enclosures (`rounded=1;arcSize=16`; yEd `ROUND_RECTANGLE`). Data bars, grid cells, axes, equation glyphs, geographic/set geometry, formal notation and sectional dividers keep their proper geometry. Do not wrap every sentence or number in a box. Sectioned records can use one outer shape with bands/field rows and an external bracket. Label size/order schematic unless the source establishes actual offsets/sizes.

Keep outer reading groups quiet; emphasize the data, important difference or condition. Stable category colors can recur across views. Status/error/uncertainty needs an explicit label separate from actor/category identity. Icons can identify roles when useful, with names; they are not mandatory decorations. Patterns are optional and native, never hundreds of hand-made lines. Keep text and small cells on quiet fills. Domain meaning outranks a preferred palette or reference silhouette.

## Korean typography and connector labels

Use the configured Korean family where supported. Keep multi-line prose/field rows left-aligned; center short peer labels consistently. Reserve actual glyph footprint and line height with padding. Grow/split the node, label corridor or canvas before shrinking text. Equivalent cards share font size, height, alignment and padding. Inspect Korean/Latin mixed labels, subscripts/equations and real line wrapping at the intended size.

Standalone text/headings/captions are transparent (`fillColor=none`). For an edge label on a clear line segment, use a small borderless mask matching the **local** surface (`labelBackgroundColor=#<local color>;labelBorderColor=none`), with enough stroke still visible on both sides. Transparent labels cannot mask a line. Do not mask endpoints, arrowheads, dividers, junctions or a cluster. Where three or more connectors crowd one local area, separate ports/routes and offset each label beside its own clear segment. Short/mixed-background paths may need offset labels even with fewer lines. If masking does not render or cannot match, offset instead. Route-specific placement is required; one fixed offset for all arrows creates new overlaps.

### Optical centering of Korean labels

`verticalAlign=middle` centers a text layout box, which can leave the visible glyphs below a shape's apparent center. Inspect the glyph block against the node silhouette and surrounding whitespace, not just its baseline or nominal box. For the current 나눔손글씨 다행체 sample, start with about 4–6 diagram units upward at 24–28px, then judge the actual export. This is a local calibration, not a universal offset for all fonts, zoom levels or editors.

For a centered draw.io node, use `verticalAlign=middle;spacingTop=0;spacingBottom=10` as the tested starting bias (about 5 units upward), without moving its shape or connection ports. For an edge, adjust the label-only `mxGeometry` offset y by a small negative amount (the 24px sample uses -5), adding it to any existing route-specific offset rather than overwriting that offset. Keep the borderless background mask attached to the label, and ensure it still covers the stroke after the lift. A vertical segment, bend or off-line caption needs its own placement check. Do not move waypoints or node coordinates merely to center the text.

Keep equivalent labels on the same font, size and correction. Check a short name, a Korean/Latin mixed label and the whole multi-line glyph block; grow the card if padding or wrapping is inadequate. Left-aligned field rows, titles and explanatory prose are not centered node labels and should not receive a blanket upward shift. Recalibrate after font substitution or device/editor changes. Preserve horizontal centering and clipping clearance while correcting the vertical impression.

## Native construction and verification

Use editable text, shapes, points/paths, groups, tables/field rows, axes/bands and annotations supported by the live tool. Preserve IDs and unrelated work. Inspect actual labels, endpoints, equations, geometry and consistent color roles in the native export; XML parsing is only a structural check. The [setup record](diagrams-net-setup.md) documents tested local configurations, not capabilities of every browser/device. A unsupported feature should use a simpler truthful mark or a disclosed plotting companion, not an invented property or flattened screenshot.
