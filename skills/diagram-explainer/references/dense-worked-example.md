# Worked example: a dense document whose layout carries the explanation

Use this when comparing event/state changes or combining definitions, quantities, rules and responsibility. It is a reference to inspect and adapt, not a mandatory template. For a formula, hierarchy or spatial explanation, choose a better-matched composition instead.

## Inspect the source and relevant view

- [Editable two-page original](../assets/drawio/dense-library-seats.drawio)
- [Synthetic data and assumptions](../assets/drawio/dense-library-seats-data.json)
- [Page 1 preview: six independent situations](../assets/drawio/dense-library-cases.png)
- [Page 2 preview: quantities, rules and responsibilities](../assets/drawio/dense-library-rules.png)

The user accepted this document's overall quality, then corrected the D/E connectors. This is that corrected version. All numbers and operating rules are illustrative, not a real library's policy. Six scenarios and the daily table are separate examples. O = occupied, H = assigned but not entered, F = free, U = unavailable; O+H+F+U=120. Q counts people and is not part of seat capacity. The font is 나눔손글씨 다행체, not embedded; verify glyphs if it is unavailable. Overview previews require zoom for detailed reading; deliver focused views when needed.

## Question → visual decision → check

| Reader question | Construction to inspect | Why it helps / check |
|---|---|---|
| Why can an empty seat be unavailable for allocation? | Page 1 separates O/H series, operating strip and Q row on the same event positions; page 2 B works through 96 occupied + 24 held | Occupancy and allocation availability no longer collapse into one “empty” label. Check that H is not counted again in O and Q is kept in people. |
| What changes when an event happens? | Page 1 cases 3–5: local event guides, consistent scales, capacity boundary and operating intervals | Readers align the event with changed and unchanged quantities. Case 4 loses capacity without moving existing occupants; case 5 pauses allocation, not all activity. Do not infer real-time arrivals between synthetic snapshots. |
| How do exact lookup and overall composition complement each other? | Page 2 C: table beside stacked bars, same time rows, names/colors and seat total | Table preserves exact values; bar lengths expose composition. Check shared row alignment, sum and scale. They have distinct jobs despite using the same data. |
| Are the allocation conditions sequential? | Page 2 D: independent condition ports join at AND, then result | Conjunction is visible without implying that one condition causes the next. Check all conditions and the min(F,Q) outcome. |
| Who changes which state? | Page 2 E: named actors/stores, labeled connections, local lifecycle notes | Responsibility, request and state change have identifiable endpoints. Inspect edge-attached labels on a background-matched mask; use nearby off-line labels only for short/crowded/overlapping routes, per Visual grammar. |

## Adapt the reasoning, not the silhouette

Start with the new question and evidence. Choose the relevant construction and discard unrelated sections. A six-panel board is useful only for six meaningful comparisons; a two-state distinction may need one paired view. Preserve source scope through overview/detail pages, not by shrinking every label. The benefit is shared coordinates and explicit state distinctions, not rounded cards, a handwritten font or the amount of content.

For a qualitative policy comparison, the same principle can become event columns × state rows. Suppose the supplied policies distinguish recorded state, an uncommitted adjustment and the value read by the next decision. Align those states at the same verified events; mark changed/held/unknown rather than inventing numeric trajectories. Give that comparison the central space and keep the common mechanism smaller. Put undecided rules at affected cells with a compact detail register.

For a codebase explanation, choose a different construction when the question concerns membership or ownership rather than time. For example, a nested subsystem view can locate an entrypoint, a short trace can follow one request, and a state table can identify each owner and update. Confirm relationships in code. The reference does not establish implementation or authorize expanding the requested system boundary.

## Recognize the failure this example repairs

A weak translation puts each paragraph in a similar box, connects every box, lists uncertainties remotely and squeezes the decisive comparison into the footer. The words may be accurate while the arrangement adds little understanding. Repair it by identifying the central distinction, selecting a representation that exposes it and making supporting detail local. Apply the [visible distinction contract and rendered review](explanation-layout.md#make-the-essential-distinctions-visible). Do not claim a broad quality benchmark from one accepted example.
