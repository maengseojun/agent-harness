# Diagram + graph composition

Use this reference when explaining how a quantity changes through events, how a process uses fixed versus live values, or how alternative rules change an outcome. It supplements explanation-layout.md; retain the Korean font, rounded ordinary nodes, transparent standalone text and local-color connector-label masks, native editability and spacing rules. Precision means coherent geometry and verifiable reasoning, not more shapes or smaller text.

## Reference and quality target

The user supplied two images on 2026-10-11: a numbered scenario board with charts and duration lanes, and a two-section flow with calculation cards and an exception return. Observed reusable features are aligned small panels, a shared legend, quiet rounded enclosures, event guides, target lines and bands, state-duration strips, worked quantities, and adjacent outcome explanations. These are visual references, not validated protocol behavior. Do not copy their private content into a public skill, require their exact palette, or imply every future explanation needs all these features.

## Compose around the reader's comparison

- Give each panel a short question or takeaway. Use matching small multiples for cases sharing the same question: heading → conditions → graph → aligned state lanes → outcome and reason. A two-column grid works when panel text remains readable on the intended screen; otherwise stack or split pages. Panel numbers identify cases, not execution order between cases.
- Reserve consistent gutters, plot bounds, caption rows and inner padding. Align comparable plot baselines and repeated lane labels. A broad exception section can span the grid below without implying it happens after every case.
- Put the premise and notation before their first use. Use one shared legend for a board, with local labels where a panel must stand alone. Write the one changed condition in each case instead of repeating the full premise.
- Match axes, units, baselines and drawing conventions across comparable panels. If ranges or durations differ, disclose them; do not compare slopes or apparent speeds across incompatible scales.

## Give every graphical mark one meaning

| Mark | What to declare |
|---|---|
| Quantity axis | Variable, unit, denominator and scale; show relevant ticks and thresholds |
| Horizontal axis | Measured time with units, or explicitly schematic event order; equal spacing must not invent equal elapsed time |
| Target/reference line | Which target/version applies, when it changes, and whether it is fixed or recalculated |
| Shaded band | Defined tolerance, operating range or uncertainty; state its basis and bounds, never let a tolerance band imply a confidence interval |
| Trajectory | Observed, computed, hypothetical or proposed values; identify the comparison baseline |
| Vertical event guide | Named trigger at the same x-coordinate in the plot and relevant lanes; keep guides thin and secondary |
| Duration strip | Named state/activity with start/end and interruption semantics; a strip does not by itself assert progress percentage |

Use solid/dashed trajectories to distinguish named alternatives when useful, and direct-label their endpoints. A dashed target line, dotted event guide and dashed return arrow belong to different layers; declare each locally. Do not apply a flow's connector legend to quantitative traces. Curves, hatch and color never establish uncertainty, approval or causality by themselves.

For numerical examples, label assumptions and synthetic values. Compute positions from declared values and a common axis mapping rather than eyeballing heights. Use a piecewise line only when interpolation is supported or explicitly illustrative; use a step for a discrete target change. Do not smooth invented samples or draw a slope suggesting a rate when only endpoints are known. Label a broken/truncated scale and any omitted interval. For a schematic event axis, avoid claims about elapsed time, velocity or performance.

## Align graphs and state lanes

Use a common x-origin, plot width and event-coordinate map for the quantity graph and strips underneath it. Reserve a left label gutter and a right endpoint-label gutter outside that plot width. Extend an event guide only across the layers it affects, without passing through words. Position its caption above a clear guide segment.

Track independent states in separate named lanes: for example, operation active, configuration version in use, and a pending flag. A flag can span multiple operations; do not merge it into the activity strip. Show the applicable target/band before and after a change and identify which running operation retains an older value. Keep idle, interrupted, completed and unknown intervals distinct with explicit labels. If no value exists during an interval, leave a labeled gap rather than imply an observed zero or continuous trajectory.

Place baseline and alternative traces on the same chart only when their units and premises are comparable. Emphasize the segment where they diverge, then write an adjacent outcome sentence explaining the responsible rule. Keep the unchanged portion quiet. If traces coincide, use a shared segment or an explicit coincidence note; draw order must not conceal an alternative. For multiple changes, separate the latest configured value from the running operation's captured value instead of silently retargeting its trace.

## Show the calculation and state transition together

Use a short sequence of aligned cards when the reader needs to understand conversion: input setting → trigger and snapshot → derived working value → live remaining work. Mark each field as fixed, read at the trigger, or recomputed during execution. Keep identifiers and units stable across cards; one formula or numerical step per short row is clearer than a paragraph of arithmetic.

For a generic teaching example, label all values synthetic: a 40% allocation of a 200-unit budget is 80 units of value; at a price of 10 value-units per item, the working target is 8 items. A current holding of 9 items leaves 1 item to remove. Preserve units, rounding and assumptions; do not reuse these numbers as a product rule. Check totals and dimensional consistency before drawing. Connect the resulting state to its relevant event or branch so the formula explains behavior.

Put success, interruption and unresolved outcomes beside the originating step, with explicit conditions and resulting state. Route a retry below or outside the main lane, label its trigger, and attach it to the exact re-entry step. A pause or interruption must not look like success. Where multiple conditions matter, preserve AND/OR and the version to which a condition applies. An unanswered policy question remains labeled unresolved even inside a polished card. Use parallel restriction cards only when they make a consequential permission or misuse case easier to compare; explain the rule that blocks each action.

## Implement with the existing editors

In diagrams.net, keep panels, axes, ticks, guides, bands, trajectories, strips, labels and formulas as editable native elements, grouping each panel and reusable unit. Use supported points/lines for quantitative traces without pretending every vertex is an execution node. Use source/target bindings for process arrows and route returns around the content. Put background bands behind traces and guide lines; keep standalone labels transparent. Process-arrow labels on long clear segments use local-color masks under the placement rules in explanation-layout.md; offset labels outside clusters of 3 or more connectors; keep quantitative trace labels clear when overlap would hide a value, threshold or divergence.

Use a light, sparse native hatch only if the actual editor supports it and it remains quiet behind the text. For these examples, a subtle category outline and colored heading can carry identity while the hatch reinforces the band or state. If hatch is unavailable or hurts Korean legibility, use a pale solid fill and explicit label; do not fabricate hundreds of diagonal lines or rasterize the chart. Keep outer enclosures quieter than the data and inner nodes. Use yEd for graph/flow layout when useful; an automatic graph layout must not move positions that encode quantitative axes. Preserve the coordinate map separately from automatic process layout.

## Check the delivered result

1. Trace one event through its guide, quantity change, state strips and outcome. They must agree in location, timing basis and state/version; a visually aligned picture cannot repair conflicting rules.
2. Recalculate one worked example and check axis positions, band bounds, totals, units and rounding. Confirm measured data, hypothetical trajectories and proposals are labeled distinctly.
3. Compare two panels: same plot bounds, legend, scales and typography, with exceptions explicitly disclosed. Ensure both overlapping traces remain identifiable and all branches have conditions and destinations.
4. Inspect a whole-board preview and a panel at the actual reading size. Check Korean glyphs, quiet patterns, caption contrast, lane padding, arrows and endpoint labels. Split a board that only works at the attachment's high resolution; do not claim mobile readability from a large export.
5. Parse and read back the editable source and render the exported result when a diagram is produced. A skill-only update needs rule/link validation; it is not evidence that a new chart, editor feature or future generation has been visually tested.
