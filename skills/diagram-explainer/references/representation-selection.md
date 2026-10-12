# Choose what the reader should see

Use this for explanations, summaries and documentation. The starting point is a reader question and supported information, not a diagram type. Separate three choices: **what is asserted**, **which marks show it**, and **how the document is read**. A table can contain a chart; a drawing can contain prose; a logical rule can need no process nodes.

## A small selection process

Extract the relevant fields, categories, numbers, temporal/spatial basis, logical operators and evidence status. Identify the reading operation: lookup, comparison, trend, distribution, composition, relation, scope, calculation or action. Ask which distinctions the reader must see immediately. Compare two useful candidates when the choice matters: for example, a table preserves exact attributes while dots on one axis expose a difference. Select one or combine them if both jobs matter. Prefer a familiar view when equally effective; novelty and variety are not goals. Explain the choice only when it helps the user.

These are starting candidates, not a required menu:

| Reader question / available information | Useful expression | Meaning to preserve |
|---|---|---|
| What is the exact value or attribute? | Table, aligned field rows, glossary | Stable criteria, units, comparable precision, source and unknowns |
| Which is larger, ranked or different? | Sorted bars/dots; table with in-cell bars; paired dots/dumbbell; slope for two time points | Common baseline/axis, comparable scope, paired values and difference |
| How does a value change over time? | Line/step plot, small multiples; sparkline beside exact values | Actual dates/spacing, interpolation basis, gaps and changing definitions |
| How are values distributed? | Histogram, strip/dot plot, box/range summary | Sample/denominator, bins or quantiles; not a category bar chart |
| How do two quantities relate? | Scatter plot, paired-value table | Each point's observation, axes/units and grouping; association is not cause |
| How is a whole divided? | Stacked bar, waffle, part/whole drawing, treemap for a real hierarchy | Denominator, totals and mutually compatible categories; use a table if exact slices matter |
| What changes an initial total into a final total? | Waterfall or aligned arithmetic | Signed contributions, start/end totals and actual additive rule |
| Which combinations differ? | Matrix, heatmap, state × operation table | Row/column meaning; quantitative color scale versus categorical status |
| Which category/level contains an item? | Labeled groups, tree, nested/sectioned structure | True parent/child, membership and part/whole; a mind map is not necessarily a hierarchy |
| What overlaps, excludes or implies what? | Euler/Venn, Boolean condition table, annotated implication | Domain, AND/OR/XOR, necessary/sufficient conditions; qualitative area unless calibrated |
| Why does an equation hold? | Annotated formula, aligned derivation, geometric example + justification | Definitions, assumptions, each justified step; an example is not general proof |
| What is inside, next to or assembled from what? | Sectioned object, exploded/cutaway view, labeled spatial drawing | Parts and actual placement/order; label schematic dimensions/locations |
| What covers which stage or interval? | Bracket/span, duration strip, timeline | Explicit covered range and gaps; coverage is not another action or progress percentage |
| What happens in what order, by whom? | Short process, sequence/lane view, step table | Trigger, action, handoff, resulting state and consequential branches |
| What connects or depends on what? | Labeled relationship graph, adjacency/dependency matrix | Named direction/relation; no invented chronology |
| Where does an amount move? | Transfer view; Sankey/alluvial when widths have valid data | Units, conservation/cohort/time basis; ordinary arrows when only destinations are known |
| What should the reader know from mixed material? | Visual document: prose, facts, selected tables/figures, notes and sources | A connected argument and reading hierarchy, not a compulsory panel grid |

For unfamiliar candidates, inspect a relevant actual reference in [Visual reference library](visual-reference-library.md). Data Viz Project's input/function views broaden the search; do not blindly inherit its tags or pick a chart for its silhouette. Maps need a meaningful geographic question and source geometry, not arbitrary positions.

## Tables are designed reading surfaces

Choose the row's unit and each column's job. Use stable aligned criteria across alternatives; group rows or use section bands when the hierarchy matters. Write meaningful headings, units and period. Align names/prose left and comparable numbers right; use consistent precision and explain rounding. Keep **0**, unknown, missing and not applicable distinct. Define blanks if they remain. Avoid repeating a unit or explanation in every cell when a header/nearby note can carry it.

Make the important comparison visible with ordering, a difference column, restrained emphasis or an in-cell mark. Numeric bars share a stated zero and range; sparklines need a period and comparable scales for cross-row magnitude claims. A heatmap needs a scale and the values/labels needed for lookup. Categorical highlights are a separate semantic channel. Table rules can be light dividers or spacing; do not place a heavy rounded box around every value. Keep an explanation or limitation beside the relevant row/group, not detached in chat.

Static draw.io can express these marks but does not acquire Datawrapper's sorting/search/mobile behavior by visual imitation. If those interactions answer the question, use the interactive companion; if the requested surface is small, split columns/sections rather than make tiny text.

## Quantities require truthful geometry

Retain the data/formula and compute positions from an explicit map, such as x = origin + (value − minimum)/(maximum − minimum) × width. Recalculate a meaningful value and position. Keep comparable views on comparable scales or clearly label differences. Bars use a zero baseline; any truncated/nonlinear axis is explicit and justified. Encode area proportionally if area carries quantity; a circle's radius cannot be linear in its value when area is read. Direct labels reduce legend lookup; annotate the relevant point/interval without hiding it.

Preserve population, denominator, time basis, measurement definition, missingness, sources and uncertainty that affect interpretation. A range is not automatically a confidence interval. Separate observed data, model/projection and illustrative values; do not smooth synthetic observations into claimed trends, join missing intervals, or use line slopes to imply a rate on an unscaled event axis. Percentage and percentage-point change differ.

For small, verifiable teaching data, native draw.io bars, dots, lines, axes, bands and labels can remain editable. Scientific/high-volume plots, geographic geometry or difficult statistics use appropriate plotting tools, retain source data/formulas and compose their verified figure in draw.io with editable surrounding text. Disclose embedded versus natively editable parts. Do not redraw a complex plot by eye to claim exact geometry, or turn the whole document into a screenshot.

## Relationships use more than arrows

Consult [Visual grammar](visual-grammar.md). Position/spacing can express aligned comparison, enclosures membership, brackets coverage, and a formula an implication. Draw a connector only when its relation is needed and label that relation. Distinguish process order, transfer, dependency, causality, logical implication and annotation. Do not join section headings or peer facts merely to make a drawing look connected.

A sufficient condition A ⇒ B does not assert B ⇒ A; a necessary condition for B points in the opposite logical direction. Multiple premises join at an explicit AND/OR operator, not a chain that implies one premise creates another. If a rule defines the outcome exactly, say “iff/when and only when” and show relevant countercases. Use a truth/condition table when it makes combinations easier to inspect. Set inclusion, exclusion and overlapping categories may be clearer as spatial sets than as a flow.
