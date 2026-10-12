# Explanation placement and reading order

Use this reference for visual summaries, composite explanation boards, multi-step teaching boards and detailed explanations. The target is a readable lesson, not a large canvas filled with prose. An explicit diagram-only request needs only the relevant visual rules.

## Plan before drawing

Write a short internal plan: reader's task, likely gap, source facts and unknowns, dominant relationship, selected view and reason, takeaway per panel, reading order, intended reading surface, and roles for shapes, fills, and typography. Choose the structure and draft it; use subsequent feedback to repair it. Do not ask the reader to make routine layout decisions.

| Depth | Appropriate when | Deliver |
|---|---|---|
| Overview | The learner asks what connects to what | One overview with short labels, essential premise, and takeaway |
| Walkthrough | The learner asks how or why | Overview plus numbered flow, step explanations, and one worked example |
| Detailed | The learner asks about implementation, assumptions, or tradeoffs | Walkthrough plus relevant state/field changes, failure path, premise consequences, and sourced rationale |

For repeated confusion, expand the missing causal step rather than adding the same explanation again. Detailed does not mean displaying every implementation detail. Keep facts, example simplifications, proposals, and inferred rationale distinct.

## Select the information structure

Separate two uses. For first understanding, orient the reader with the core relationship, unpack the causal steps, and compare alternatives when needed. For a source-of-truth document, make each view understandable without chat history: scope, named entities, boundary/relationship meanings, conditions, and a traceable source/version. Mark proposed or unresolved content; a polished diagram is not evidence of adoption. Neither use requires every panel below.

Before arranging shapes, name what a node represents and what a line, position or enclosure asserts. Distinguish stages, change, categories, containment and logical relationships from dependency and transfer. Identify the difference or decision the reader needs to see, then choose the simplest view that exposes it. Separate measured values from illustrative ones:

| Reader needs to understand | Starting representation | Preserve |
|---|---|---|
| Which stages happen in what order? | Ordered steps or process/actor lanes | Order, handoff and conditions; do not imply a repeating cycle without a supported return path |
| Where does an actor or product participate in a common process? | Labeled span/bracket aligned above or below the covered stages; lanes or a stage × actor table if participation differs by stage | Explicit start/end coverage; do not insert the scope as another process step. For gaps, use separate spans or a table rather than implying continuous coverage. Span length is not duration or effect unless measured |
| What changes from one state to another? | Aligned before/after views; state-transition graph when paths or triggers matter | The same object and comparable attributes; mark the changed value and transition condition. Use a chart for measured change or an explicitly labeled numerical teaching example; do not invent quantitative values for qualitative states |
| Which items are in the same category? | Labeled groups, aligned category columns or a classification table | Membership and naming; group position must not invent order, priority or containment. A classification tree needs a real hierarchy |
| What is contained in what, at which level? | Nested boundaries, part/whole structure or a parent/child tree | Actual containment and levels; adjacency or a shared color alone does not express inclusion |
| What follows from which premises or conditions? | Labeled implication/dependency graph, AND/OR junctions or condition table; set/Euler views for actual set relations | Premise, conclusion, direction and operator. Distinguish logical implication from causal effect or time order; distinguish sufficient from necessary conditions and OR from exclusive OR |
| What depends on or connects to what? | Relationship/dependency graph | Named relation and direction; a connection alone does not mean execution order |
| How does work proceed across actors? | Flow or sequence/actor lanes | Trigger, handoff, conditional paths, resulting state |
| What can happen in each state? | State-transition diagram; state × operation matrix for comparison | Transition condition versus permissions/results within a state |
| How do A/B designs or before/after cases differ? | Aligned comparison table or matching small panels | Same criteria, scope, baseline, units, and abstraction level |
| What are an object's relevant properties? | Field rows inside an object card or attribute table | Property names, values, and links to changing steps |
| How is one object, record, or message internally organized? | Sectioned structure view with bands, dividers, and labeled brackets | Actual membership, repeated parts, and whether position/size encodes order or quantity |
| How do measured category values or trends differ? | Bar chart for category magnitudes; line chart for change over time | Units, time basis, consistent scale, source, and uncertainty |
| How are measured values distributed or related? | Histogram for distribution; scatter plot for paired values | Bin/axis meaning and sample basis; association is not causation |
| Which choices follow from which conditions? | Decision tree or decision table | Complete relevant branches and explicit tests; a classification tree does not imply a decision sequence |
| Which events overlap or exclude one another? | Venn/Euler or another set view | Union, intersection, complement and domain; geometric area is qualitative unless calibrated to quantity |
| Why does a formula or theorem hold? | Annotated formula, aligned derivation or numbered proof beside a visual example | Definitions, assumptions and justified steps; the example illustrates and does not prove the general claim |
| How do events relate to dates or durations? | Timeline with intervals or aligned event lanes | Time basis, gaps and uncertainty; do not use process spacing as measured time |
| What are the main points of mixed material? | Selected prose, table, figure or formula panels | Core answer and conclusion-changing conditions; panel layout follows the content rather than a fixed infographic template |
| How is a whole divided or an amount transferred? | Part-to-whole chart for measured shares; flow for destinations | Denominator/units and totals; do not imply proportional widths without data |

This is a selection aid, not a catalog to fill. If exact lookup matters, prefer a table; if numeric patterns matter, use a chart. Use a flow for order and a graph for structural connections. Qualitative scores must have a stated basis; do not invent precise values to make a chart. Combine views only when each answers a different question, sharing names and references. Explain the choice briefly when it helps the reader, without turning the internal plan into another deliverable.

When relations coexist, encode each separately rather than forcing everything into identical boxes. For example, keep preparation → selection → delivery as a common process, then place one labeled bracket over preparation and another over selection through delivery to show two products' involvement. Keep an independent reuse condition beside the process unless the source establishes a repeat transition. For a permission rule requiring both eligibility and approval, show those premises joining at a labeled AND condition; do not draw eligibility → approval as though one causes the other. Use a legend or direct labels when the line vocabulary changes, and keep qualifications next to the relation they constrain.

For A/B comparison, keep criteria in the same order and use matching layouts and scales. Show common parts neutrally and mark consequential differences; state the tradeoff and the condition under which each choice applies. Keep unknowns explicit rather than scoring them as poor. Before quantitative ranking, check comparable sample populations, measurement definitions, and coverage; incomplete measurements may support a qualified description without establishing a winner. Split overview and detail at a meaningful boundary, not an arbitrary number of shapes.

For graphs paired with process/state diagrams, read [Diagram + graph composition](diagram-graph-composition.md). Keep the quantitative axis separate from process order and align state/event lanes only when they share an explicit time or schematic event basis.

## Compose a mixed explanation or summary

An explanation board can contain different representations. Start with the core answer, then give each needed panel a reader question, a suitable view and an adjacent interpretation. Possible roles include definition/conditions, visual intuition, comparison, mechanism/proof, worked example and application/limits. Select and order only the roles the request needs; do not require every role, a four-panel grid or a mathematics-first layout. For a summary, prioritize the essential facts and their relationships rather than adding a proof, quiz or tutorial automatically.

Choose a dominant reading path and enough space for the most demanding view. Pair a figure with the explanation that lets the reader interpret it; put units/axes beside a chart, criteria in a table header, parent/child meaning beside a tree, and assumptions beside a formula. Reuse terms, example values and semantic colors across panels. Number panels for reading order without implying that categories or proof premises are chronological actions. The board should answer the question on its own when it is the requested reading surface. At narrow widths or a different output format, preserve the reading order and essential content by stacking or splitting panels rather than shrinking all text.

The user-supplied Boole inequality image demonstrates a title/core answer, definition and formula, two-event set picture, indicator proof, generalization and uses arranged together. Adapt that composition when it serves the lesson. Check its wording against the formula: union means “at least one”, while intersection means “all”; a reference image is not authority for a mathematical statement. The overlapping region explains double counting. For a uniform-probability teaching picture, label that assumption before treating area as probability; otherwise mark the geometry qualitative. Do not copy its palette, density, exact sections or incidental mistakes as defaults.

For other topics, use different combinations: an option comparison may need a criteria table and tradeoff paragraph; a taxonomy may need a tree and an ambiguous-membership note; a measurement summary may need a chart and interpretation with source/units. Simple cases can use one representation. Introduce interaction only when an input and its visible consequence answer a learning question; a static summary needs no simulated behavior.

Select the requested output format after selecting the information structure. Freely arranged editable boards retain the draw.io/yEd defaults; requested HTML, documents, PDFs or slides use their relevant authoring and rendering checks. Quantitative figures use appropriate plotting tools and retain data/formulas; embedded previews do not replace separately requested editable sources. Choose a math-capable rendering route when needed and inspect actual notation, subscripts and alignment. A bitmap reference or preview does not replace editable text, equations and shapes in an editable deliverable.

## Decide what stays in the picture

Use a consequence test: if hiding this detail would make the reader choose the wrong path, infer the wrong responsibility/permission, or expect a different result, show its short form at that step. A/B alternatives, retry/stop decisions, and outcome-changing exceptions stay visible. A branch may link to a detailed subflow, but its condition and destination remain in the overview.

Put supporting premises, derivations, detailed limits, and evidence below the relevant panel or in linked text. Numbers are not automatically footnotes: a threshold that chooses a path belongs on its branch; units/ranges needed to interpret a chart belong with the chart. For example, a synthetic “amount < 10 → alternate route” flow keeps that test visible; why 10 was chosen and how it is calculated may be explained below. If a threshold or retry limit has ambiguous units or counting semantics, resolve them from the source or mark them unresolved at the branch; do not invent an exact test.

Use the same step/cell IDs in notes and the diagram. A shared premise can sit below the panel with a clear scope label; a local caveat belongs beside/below its step. Put an essential premise before its first use if reading the flow without it would mislead. “Below” means within the relevant reading section, not several screens away. The picture should convey the structure; adjacent text should explain its mechanism, rationale, and qualifications.

## Board composition

Use named native frames when supported, otherwise clearly titled groups. Keep one learning question per panel. Multiple panels can answer a broader question.

1. **Entry:** title, one-sentence answer, scope, and a short reading map (01 Overview → 02 Processing → 03 Example). Put essential prerequisites before the first step that needs them.
2. **Overview:** actors, assets or objects, and boundaries. Keep this small enough to orient the learner before detailed steps.
3. **Walkthrough:** main flow and its numbered explanation in the same panel. On a wide panel, flow left and commentary right; for a wide flow, commentary directly below. Do not put the explanation several screens away.
4. **Example or comparison:** repeat the same layout, entities, colors, and units across before/after states. Show what changed and what stayed invariant.
5. **Exceptions and evidence:** place consequential failure branches beside their originating step. Put longer caveats, tradeoffs, and source links in a clearly marked lower section or companion report.

Use a single primary reading direction in each flow: left-to-right for short sequences, top-to-bottom for long ones. Arrange panels in a clear top-to-bottom reading order. Avoid an unmarked serpentine path or sprawling canvas. If a panel needs several screens to read, split it at a meaningful state boundary; do not shrink text to fit.

When revising an existing explanation, improve the relevant panel in place instead of continually appending another version below it. Preserve unrelated content and user edits. Label retained alternatives. After verification, focus the updated entry panel or changed section and tell the user its exact title/location. Camera movement is not proof of content persistence; read back shapes separately.

## Text placement and length

These are starting budgets, not hard limits. Increase them only when meaning would otherwise be lost; split content before reducing font size.

| Location | What belongs there | Starting budget |
|---|---|---|
| Title | Question or takeaway | One line |
| Premise strip | Conditions needed to read this panel | 2–4 short items; expand premise/consequence pairs below if needed |
| Actor/object | Name, role, current state or key fields | Name plus 1–3 short lines |
| Arrow | Step number + action + thing moved, or branch condition | One short phrase; no explanatory paragraph |
| Beside a step | What happens and why it matters | 1–2 short sentences |
| Walkthrough table | Step / action or state change / reason or failure condition | One row per meaningful step; split tables by phase if crowded |
| Example | Before/after quantities, result, invariant | One consistent worked case |
| Footnote/report | Sources, detailed qualifications, implementation references | As much as needed, outside the flow |

Prefer natural Korean and retain exact English identifiers where needed. Introduce an identifier with its meaning. Use relative hierarchy (title > heading > label > source) and inspect Korean at the actual reading zoom. Do not copy the reference's 12px body size into the selected editor without checking legibility. Tables compare parallel facts; connected prose explains reasoning that does not fit a cell.

## Step and arrow grammar

- Number actual actions on their arrows (1. 자산 예치), or number processing nodes when no transfer arrow represents the action. Use the same step identifier in commentary and state-field markers. Avoid numbering both with conflicting sequences.
- Separate panel numbers from action numbers: panel 02 can contain R1–R7. A detail of R3 can use R3.1–R3.3. Numbers express execution order, not just visual position.
- Label alternative branches with explicit conditions (검사 통과 / 실패); do not imply both branches execute in sequence. Show failure from every relevant phase or use a clear shared failure note rather than suggesting only the last check can fail.
- Distinguish command, asset transfer, and state update when it matters. Mark atomic transaction, asynchronous wait, custody, or responsibility boundaries. Do not use a single unqualified arrow to imply an asynchronous process is instantaneous.
- Bind arrow endpoints and labels to native shapes where supported. Make labels move with their arrows. Leave enough line length on both sides of a label; lengthen or reroute the connector instead of letting text swallow it.
- Align row/column centers so intended straight arrows remain straight. Route from shape sides, avoid corners and unrelated boxes, and separate opposite-direction transfers into parallel paths. A return arrow must show its destination and trigger.

## Visual grammar: tables, boundaries, categories, and connectors

Choose the visual form from the question. Use the smallest combination that exposes the relationship; a rich diagram does not require every pattern below.

| Learning question | Useful pattern |
|---|---|
| Who does what at each step? | Step × actor responsibility table; use actor lanes with arrows when handoffs are the main question |
| Who acts on whom, in what order? | Actors plus numbered action arrows; separate the main path from condition-labeled branches |
| Where does responsibility, permission, or storage change? | Labeled outer boundaries with contained actors/objects and explicit crossing arrows |
| What is stored and what changes? | Object card with field rows and matching step markers |
| How do alternatives or before/after states differ? | Matching zones with identical inner layout; highlight only meaningful differences |
| Which operation affects which object? | Operation × object matrix, paired with a flow if order matters |
| Where does an amount go? | Labeled amount split with units and conservation check |

### Surfaces, shapes, and typography

Treat the canvas as a quiet reading surface. Default a new explanation to a light neutral background with contrasting text; adapt an existing board's theme rather than changing its whole canvas. Set a canvas color only if the actual editor/tool supports it. Otherwise use a supported background shape for the authorized panel, behind its content and connectors. Preserve native editability and bindings.

Standalone explanations, titles, group/lane headings and captions have transparent backgrounds by default. Keep meaningful fills on nodes, table cells and panels. For connector labels, use the following placement rule:

- On one long, clear segment, a short label may sit on the line with a small, borderless background matching the surface immediately underneath it. Mask only the line behind the label and leave visible strokes on both sides. The effect should be a clean gap in the line, without a visible white box on a colored panel. Fully transparent or partly translucent blocks are insufficient if the stroke remains visible through Korean glyphs.
- Set draw.io `labelBackgroundColor=#<actual local surface color>;labelBorderColor=none` on that edge; do not guess white from the overall canvas when the label is inside a colored panel. Keep text-only cells at `fillColor=none`. For another editor, use its verified native label background or a small editable backing above the connector and behind its text. Group an explicit backing with the label when supported, preserving the connector's bindings. Inspect the actual export before claiming masking works.
- Start with a small text-sized mask and roughly 4–8 diagram units of inner clearance when the native option supports padding, then inspect glyph edges and line ends. Do not use a full-width strip or mask across node outlines, dividers, arrowheads, endpoints, junctions or unrelated lines. Grow the route/corridor or shorten/split the caption if it cannot fit safely.
- When 3 or more connectors cross, overlap or converge in the same local area, place each label outside the cluster beside its own unambiguous segment. Separate attachment ports or use parallel lanes/waypoints so the reader can follow every path. A diagram containing three independent, uncrowded arrows does not trigger this rule. For any number of lines, also offset when a short segment, crossing, node boundary, patterned/gradient surface or mixed backgrounds make the masked label ambiguous.
- If a background cannot be matched or a native mask does not render correctly, return to the established offset-label layout; do not leave a stroke through the words. Preserve direction, endpoint attachment and transparent standalone text. The user's 2026-10-11 masking request supersedes the earlier blanket prohibition on opaque connector-label backgrounds.

Measure the rendered label footprint when reserving a connector corridor. Keep a visible gap from glyphs to the actor silhouette, neighboring node, scope boundary and arrowhead; for an offset label, also leave space from the stroke; 12–16 diagram units is a useful starting margin, then verify at the delivered zoom. Expand the actor-to-node spacing or the panel/canvas before shrinking ordinary labels. Align source/target port heights for a short handoff when possible. Position each label for its actual route, including boundary crossings and vertical returns; a uniform offset can create new overlaps when label placement changes.

Declare a small fill vocabulary by information type. The choices below are starting points, not mandatory notation or permission to invent a status:

| Role | Starting treatment |
|---|---|
| Text-rich object, process, table cell | Solid light fill; category identity in a stable tint, outline, or header |
| Repeated actor/category group | Same subtle native hatch/pattern if useful; keep the mapping stable and label the type |
| Outer boundary or reading section | Quieter neutral fill/outline than its contained entities |
| Supporting explanation | Neutral solid text area, adjacent to its referenced step |
| Proposed/conditional item needing distinction | Explicit label plus a supported secondary outline/pattern; keep category identity separate |

These light-fill presets apply to a new light canvas. On an existing dark canvas, choose foreground and fill together for readable contrast, preserving the theme and the same role distinctions.

Use pattern sparsely: it supplements the type label and color, not the reading hierarchy. Keep long text and small cells on a plain fill; if a patterned entity needs detail rows, give those rows a solid background. If a supported pattern obscures Korean strokes or lacks contrast, use solid fill plus a labeled outline instead. A shape type does not require a unique pattern, and a pattern does not establish permission, completion, or uncertainty by itself.

Choose geometry for logical role, preserving existing/domain notation. This user's default is a **rounded rectangle**, not a sharp-corner rectangle, for ordinary action/entity nodes, cards, notes, headers and enclosures. Use draw.io `rounded=1;arcSize=16` or yEd `ROUND_RECTANGLE`. Use a diamond for a decision with labeled outgoing conditions, an ellipse for a start/end or explicitly identified actor, and a cylinder for storage. A cylinder's internal body may have straight edges because its outer ellipse supplies the rounded silhouette. Use a container for actual containment or a labeled reading group. Do not alternate shapes merely for variety. A title or padding should not be squeezed into a diamond; move long rationale beside it and keep the decision short.

Within a panel, keep peers the same shape and comparable size, align a sequence along its primary direction, put branches beside their originating decision, and route returns outside the main lane. Arrange hierarchy by actual levels, alternatives in matching rows/columns, and actor lanes by responsibility. Arrows and condition labels express direction and order; the silhouette, left/right placement, or numbering alone must not imply a dependency or execution order.

Use a small typography hierarchy: title > section heading > node/cell body > supporting note. Set a supported font family by role and keep it stable across panels; usually one readable family plus an optional identifier/code family is sufficient. Prefer a Korean-readable body font; a hand-drawn title is optional only if its Korean rendering stays clear. Use size, supported weight, and spacing for hierarchy before adding font families. If a style is unsupported, retain the hierarchy through supported sizes and layout rather than inventing a font or custom renderer. Supporting notes must remain readable, not merely smaller.

Keep body text left-aligned for multi-line explanations and field rows; short node names or table headers may be centered. Reserve space for line wrapping and padding, and grow/split the node instead of shrinking the body to fit. Category-colored headings still need readable contrast against their fill. Inspect the actual Korean glyphs, hierarchy, and label backgrounds at the intended reading zoom and in the exported preview when one is delivered.

Match peer and before/after cards by font size, height, vertical alignment and inner padding. For two-line state summaries, reserve both line heights plus top/bottom padding; do not put 28px two-line text and 24px total padding into a 65px card. Use a consistent subordinate body size where the hierarchy calls for it and grow the card when needed. In draw.io set `verticalAlign=middle` explicitly for centered summary cards, then inspect the rendered top/bottom whitespace and baselines of both peers. Matching geometry alone does not prove visual alignment.

### Optical centering of Korean labels

`verticalAlign=middle` centers a text layout box, which can leave the visible glyphs below a shape's apparent center. Inspect the glyph block against the node silhouette and surrounding whitespace, not just its baseline or nominal box. For the current 나눔손글씨 다행체 sample, start with about 4–6 diagram units upward at 24–28px, then judge the actual export. This is a local calibration, not a universal offset for all fonts, zoom levels or editors.

For a centered draw.io node, use `verticalAlign=middle;spacingTop=0;spacingBottom=10` as the tested starting bias (about 5 units upward), without moving its shape or connection ports. For an edge, adjust the label-only `mxGeometry` offset y by a small negative amount (the 24px sample uses -5), adding it to any existing route-specific offset rather than overwriting that offset. Keep the borderless background mask attached to the label, and ensure it still covers the stroke after the lift. A vertical segment, bend or off-line caption needs its own placement check. Do not move waypoints or node coordinates merely to center the text.

Keep equivalent labels on the same font, size and correction. Check a short name, a Korean/Latin mixed label and the whole multi-line glyph block; grow the card if padding or wrapping is inadequate. Left-aligned field rows, titles and explanatory prose are not centered node labels and should not receive a blanket upward shift. Recalibrate after font substitution or device/editor changes. Preserve horizontal centering and clipping clearance while correcting the vertical impression.

### Sectioned object and record views

For internal composition rather than execution, use one outer object silhouette with filled section bands, divider lines, and nested field/repeated-item blocks. Name each section through a heading band or an external bracket/brace spanning exactly that group. A bracket is a grouping annotation, not a directional arrow or a security boundary. Use quiet field fills and stronger section labels; no hatch is required when bands and labels already explain the types.

Arrange parts in source-defined order when it matters; otherwise use a readable grouping and state that it is schematic. Keep repeated parts aligned, showing the first/last item with an ellipsis when the omission is clear. Do not imply byte offsets, field sizes, contiguous storage, hash input, or sequence from geometry without source support; label size/order as schematic when needed. A computed identifier can be shown beside/above the object without implying it is a stored field. Use the attachment's section bands, rounded field blocks, and external brackets as visual reference, not evidence for its blockchain claims.

### Tables and explanation placement

- Give a responsibility table numbered step rows and stable actor columns. Color headers and relevant cells by actor; use a neutral outline for inactive cells. Define empty cells as “no action in this step” only when verified. Write “미확인” for unknown participation and “해당 없음” when inapplicable; do not equate an empty cell with missing evidence.
- Put a short action and meaningful result in each active cell. Keep detailed reasons beside the table or in a step/reason column. Use a separate aligned comparison for definitions, permissions, or alternate paths rather than mixing them into execution rows.
- For a state/alternative matrix, identify the baseline and emphasize cells whose behavior changes, the important restriction, or the requested decision. Use a short label plus outline/weight or a restrained highlight, separate from category colors. Add a nearby note explaining why the marked difference matters. Do not highlight every populated cell equally or rely only on header color.
- Pair a table with a focused flow only if the table hides a consequential handoff or branch. Reuse step IDs and actor colors. Place a one-sentence takeaway above, the relevant explanation beside/below its step, and qualifications below the panel. Avoid arrows through every cell or paragraphs in every node.

### Boundaries and categories

- Label each boundary with what it means: actor responsibility, system location, custody, permission, transaction scope, or simply a reading section. Use a quiet outer container and more prominent inner entities. Nest containers only when the nesting represents actual containment; visual grouping does not prove a security or atomicity guarantee.
- Show a meaningful boundary crossing at the edge with a labeled arrow: who requests, what moves, which check applies, or which state changes. Keep request authority, signing, and asset movement distinct when relevant; do not invent those semantics from the reference images.
- Assign colors to the few categories the reader must track, not a new color to every step. Reuse them across header, outline, short category label, and related paths. Use neutral text/containers for context and text labels for category identity. If two categories are visually too similar, choose more distinguishable supported colors.
- Keep category identity separate from status: an actor's color must not change to mean failure. Mark failure, uncertainty, or the active step with explicit text and an additional outline/marker. Put a compact color/line legend near the first panel that uses it; repeat it only where a panel must stand alone. Pair each meaning label with a small native rounded rectangle or circle that matches the actual category fill, outline and pattern. Replace color-name-only keys such as “purple = signing” with a purple swatch + “signing”; retain the meaning text for accessibility. Pair connector meanings with actual solid/dashed/dotted line or arrow samples, preserving their direction and dash style. Align samples and labels with consistent spacing, keep them editable, and do not substitute emoji squares whose appearance varies by platform.
- Pattern/hatch fills can reinforce a category as in the supplied images; follow the surface rules above and inspect text contrast. Use supported native fills; do not hand-build hundreds of diagonal lines. An unfilled outer enclosure can distinguish scope when its text-bearing children have readable filled backgrounds.

### Lines and arrows

Use a small declared connector vocabulary, adapted to the subject. These are useful starting choices, not universal meanings:

| Expression | Suggested meaning and required label |
|---|---|
| Solid directional arrow | Main action or transfer; name the action/object |
| Solid line without arrowhead | Association, membership or connection; not execution order |
| Dashed directional arrow | Conditional/exception path; state the condition and destination |
| Dotted leader without arrowhead | Explanatory annotation, not an executable step |
| Return/loop arrow | Retry, feedback, or re-entry; name the trigger and return step |
| Thin neutral enclosure/divider | Grouping or boundary; name its scope |

Use an arrow's color for its declared category or path; keep cross-category handoffs neutral when no owner is clear. Do not assign two meanings to the same style within one explanation. Dashed does not automatically mean asynchronous or uncertain: label waiting, acknowledgement, and evidence status explicitly. Show distinct request and response arrows when that distinction matters; a double-headed arrow can hide their order.

For a sequence view, declare dashed horizontal arrows as returns and dashed vertical lines as lifelines. For a request/response boundary map, a dashed return can be routed in a separate lane. A dashed enclosure has a scope label; it does not inherit the semantics of a dashed arrow. Show the local vocabulary with short native line samples. Reuse the observed layouts in [Blocks & Arrows design guide](blocks-and-arrows-design.md) when this user requests richer visual expression.

Prefer straight connectors for aligned short paths, elbow routes around obstacles, and curves for returns or competing paths when clearer. Bind endpoints to the intended shapes when supported. Keep branches outside the main reading lane and labels away from crossings; use visible step references instead of a long connector spanning unrelated panels. Use consistent stroke weight, reserving emphasis for an important path/difference. Hand-drawn lines must still make endpoints and arrowheads unambiguous.

### Native diagrams.net and yEd implementation

Use native rectangles, ellipses, diamonds, editable text, lines, arrows and groups. Build tables from aligned cells and group each reusable unit. Use named frames when supported, checking clipping and cross-frame arrows. Preserve native page/element IDs and connector source/target references when editing.

Read the live draw.io MCP schema and the diagrams.net setup reference before selecting tools; use native .drawio files or the browser UI when MCP is unavailable. Set semantic fills, dash styles and typography explicitly; remembered editor preferences must not leak into unrelated categories. Library items are starting structures, not evidence. Split a relationship across focused native views when it is crowded; never replace the editable content with a screenshot. Use the registered Korean font by its actual family name in this installation.

These patterns are adapted from the user's supplied workflow, responsibility-table, and key/permission-map images. They are visual references, not verified product documentation or a fixed palette. Retain useful hierarchy and category consistency; do not reproduce tiny text or a sprawling board just to match the reference. No decorative icons, shadows, or emoji are needed by default.

## Final check

- Can a reader find the entry, follow the intended order, and locate the explanation for each step without chat history? Does the chosen form expose the requested relationship or comparison?
- Are decision-changing conditions and alternative paths visible, including relevant thresholds? Are supporting notes close to their steps and essential premises visible before use? Does the diagram distinguish execution, waiting, success, and failure correctly?
- Do board text, companion report, quantities, identifiers, and sources agree? Does a comparison use the same criteria/layout/scale and expose the meaningful differences? Does a reference view identify its scope and source/version?
- Inspect native rendering at readable panel zoom, not only a fit-all screenshot. Check transparent text backgrounds, meaningful shape fills, pattern contrast, role-consistent shapes, typography hierarchy, arrow labels, clipping, overlaps, Korean text, and the diagram-to-explanation distance. For a label on a connector, verify that the local-color mask removes strokes behind the glyphs, matches the surrounding surface, and leaves enough line visible on both sides; for an offset label, verify its gap and unambiguous association. Inspect clusters of 3 or more connectors for separated ports/routes and labels outside the crowded region. In both cases keep divider lines, junctions and arrowheads identifiable. Check legend swatches and line samples against the actual diagram styles. Read back the actual shapes after editing.
- Can the reader distinguish actor/category, boundary scope, main path, conditional path, and annotation from the visible labels and legend? Do tables distinguish no action from unknown evidence, and do connector endpoints remain attached to the intended entities?
- An optional prediction question should have an immediately available answer. User understanding remains unverified until their response provides evidence.

Provenance: adapted from the user-provided `message.txt` describing an Excalidraw style attributed to Henry. Its claimed 40-file survey was not independently verified. The attachment describes but does not include the complete `exkit.py`, `render.mjs`, or `svg2png.py` sources. No installation commands or personal filesystem paths from it are required by this reference.

## Grounds for these choices

These are applied design recommendations, not a single universal standard. The representation mapping and consequence test above combine the user's agreed use cases with the following guidance; they do not claim that every source prescribes every rule.

- [C4 notation](https://c4model.com/diagrams/notation): architecture views should explain their scope, entities, relationships, and notation, with consistent color roles. Apply that clarity without requiring the full C4 model for every subject.
- [Government Analysis Function: Choosing visualisations](https://analysisfunction.civilservice.gov.uk/support/communicating-analysis/introduction-to-data-visualisation-e-learning/data-visualisation-e-learning-module-2-choosing-the-right-data-visualisation/): choose the message before the visual; tables support lookup/comparison, bars compare categories, and lines show changes over time.
- [NN/g: Proximity](https://www.nngroup.com/articles/gestalt-proximity/): position related items together and separate unrelated groups. Applied here to step explanations and qualifications.
- [NN/g: Visual design principles](https://www.nngroup.com/articles/principles-visual-design/): use hierarchy and contrast to guide attention; reduce decorative weight without making text unreadable.

Consult a relevant primary guide for an unfamiliar chart, notation, or domain-specific convention. Do not browse for every routine shape, copy a fixed palette, or treat a visual reference as proof of source content.
