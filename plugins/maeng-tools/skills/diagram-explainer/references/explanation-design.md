# Design a complete explanation

Revision: explainer-8. Use the scope, meaning and review principles for prose, tables and visual explanations. Visual composition details apply only when a visual document is the reading surface. Representation choices live in [Diagram Design selection](../../diagram-explainer/SKILL.md#3-selection-semantic-pattern-then-visual-type); marks, lines and typography live in [Diagram Design primitives](../../diagram-explainer/references/primitives-core.md). A reading path is not a process path.

## Plan the meaning and the reading surface

Write a compact internal plan: reader's question, core answer, necessary facts/unknowns, selected representation and reason, section roles, reading order and intended size. Compose and check the reasoning before breaking it into visual units. Facts and a neat layout alone do not explain why a conclusion follows.

Choose depth from the request. An overview may need one figure and interpretation; a how/why explanation may need an example and the missing causal step; a reference document needs definitions, scope, source/version and enough detail to stand alone. None automatically requires a walkthrough, failure flow, proof or quiz. When confusion recurs, repair the missing relation instead of repeating the entire lesson.

## Establish scope and check coverage

Scope is a content decision before it is a canvas decision. Infer it from the user's question, intended reader, purpose and requested depth. Distinguish “explain this part in context” from “explain this codebase/concept as a whole”. For a whole-system request, orient with the main responsibilities and relationships before focusing on a path. For a local request, include enough context and dependencies to make that part understandable without turning it into an encyclopedia.

Build a compact coverage map: reader question/topic → what must be explained → source/evidence → core, necessary context, detail/appendix or excluded/unknown. This can stay internal for small work; a large document needs a visible scope/reading map. Read source before deciding completeness; a repository index or supplied picture alone does not establish coverage. Say what source revision/scope was inspected and do not describe uninspected areas as absent.

- **Codebase:** scan relevant entrypoints, module/public-interface documentation and actual code to understand the system boundary. Follow the asked-about path through callers/callees, responsibilities, inputs/outputs, data/state and consequential dependencies. Include lifecycle, invariants, failure/permission boundaries and deployment/external interfaces when they change the answer. Link important claims to source locations. Separate implemented behavior, tests/docs claims and inferred intent. Inspect related code sufficiently to avoid a function-only explanation, but do not recursively map unrelated files. If a whole-repository explanation is requested, account for the major subsystems and cross-system paths, declaring unsupported/unread scope.
- **Concept:** identify the central definition/question, necessary prerequisites and assumptions, the relation/mechanism or justified derivation, and the consequences or contrasting cases that bound it. Add examples, applications, variants and common confusions when they serve the requested depth. Distinguish definition, theorem, analogy and illustration. These are coverage prompts, not mandatory chapters or permission to introduce every adjacent field.

Before drawing, compare the map against the request: does each required topic have an explanation and evidence, are essential dependencies/conditions visible, and are exclusions justified? After composing, map topics to pages/sections and check again for gaps, duplicated explanations and unresolved assumptions. An overview plus focused pages can preserve scope and readable density. Do not choose the topic boundary from a template's slots, arbitrary node count or a fit-all image. If the intended boundary is materially ambiguous, ask the missing question; otherwise proceed with an explicit reasonable scope and let feedback refine it.

## Make the essential distinctions visible

After scope selection and before coordinates, write a compact working contract for a nontrivial document: **reader question → essential distinction → supported evidence/state → visual encoding → page/region → rendered check**. Keep it in working notes; it is not another panel to add to the deliverable. A small explanation can use one sentence. Prioritize the few distinctions that determine the answer; do not create a quota of charts or panels.

For example, “when does each policy update what?” needs the same event columns across alternatives and separate rows for the stored state and the value used for the next decision. Mark update/hold/unknown at the relevant event. A generic chain of policy-name boxes does not expose that distinction. If durations or magnitudes are unknown, use an explicitly unscaled event sequence or categorical matrix, not invented slopes or values. Conversely, paired actual/target quantities with a justified common unit can use aligned values or paired marks with the difference labeled.

Choose the main figure and its space from the central reader question. A system overview supplies context; an uncertainty register supplies qualifications. Neither should crowd the requested comparison into a tiny footer. Allocate enough room for the decisive evidence and put consequential unknowns at the affected state, edge or row; keep a linked register for further detail without repeating every paragraph. In codebase work, distinguish object/state, operation and responsibility before connecting them; source order need not become reading order.

Before polishing, sketch the main comparison with actual labels and supported values. Check whether position, alignment, grouping, intervals, marks or equations carry the intended relation. Text may be the clearest expression of an exact condition; do not replace useful prose with decorative geometry. If all substantive distinctions remain sentences inside interchangeable cards, reconsider the representation using an inspected reference.

## A diagram is a structure to follow

For a diagram request, default to one coherent structure with a visible main relation and necessary branches. A report, deck or multi-page reference document is a separate requested genre. Keep production history, acceptance logs and long source registers in a companion instead of distributing them across the figure. First draw the relation, then add the labels that explain it. Inspect whether position, paths or geometry let the reader follow the structure; a set of equally styled text cards is not enough. The adapted [personal customization of the migrated skill](../../diagram-explainer/references/personal-additions.md) gives construction and removal checks while preserving direct Diagram Design HTML/SVG production.

## Icons on nodes

This applies to every structure figure, not only a requested diagram: a structure map, tree, flow, layer stack, page schematic, slide figure or interactive explainer, whichever skill draws it (easy-understanding and interactive-explainer link here). Run it as a pass after the figure is laid out: go through the nodes and region headers and mark which are concrete things.

An icon helps when a node is a concrete thing the reader would picture: a document, a set of documents, a person or agent, a store, a message. Put one icon from [primitive-icons.md](primitive-icons.md) above or beside the node label, about 1.5–2× the label's cap height, in the node's ink. Mark an outcome (kept/lost, passed/failed) with the `ok`/`fail` icon next to its word label, never the icon alone. Repeat the same icon for the same kind of thing so the reader can count and compare (four agents, four pages).

Leave abstract nodes (a rule, a property, a step name) as text; an icon there is decoration. Use one icon style per figure: the stroked Tabler set, not mixed with filled brand marks unless the brand is the point. An icon never replaces the label, and decorative icons keep `aria-hidden="true"`. If the needed icon is missing, take it from Tabler (`https://api.iconify.design/tabler.json?icons=<name>`), redraw it at stroke-width 1.5 and add it to the library with its source line.

## Give sections jobs

Lead with the answer or question. Then arrange the needed material by the reader's next question: definition, comparison, evidence, calculation, mechanism, interpretation, consequence or limit. Use those roles only when needed. Select one dominant reading direction with aligned headings and whitespace; avoid an unmarked serpentine canvas. A prose column can be a primary part of the document. Named sections need not have visible enclosing boxes.

Pair each visual with what makes it interpretable: units/period/source beside a chart, criteria and unknown-state meanings in a table, parent/child meaning beside a tree, assumptions and justified steps beside an equation. Use proximity, a local note, a small leader or a stable reference ID. Do not draw long lines across unrelated panels just to associate commentary. Put definitions before first reliance. Keep evidence and interpretation together, with citations at the relevant claim and a compact source section for detail.

Number actions when order matters; number panels only for navigation and distinguish their numbering from action IDs. A two-column comparison is parallel, a derivation order is reasoning, and a timeline is time: document layout does not make all three an execution flow. Match terminology, units, example values and semantic colors across views.

Use the consequence test: if hiding a condition/threshold would change the reader's choice, inferred permission/responsibility or expected result, show it locally. Unknown policies remain unknown. Long evidence or derivations can move to a companion document, but the requested main surface keeps the core answer and essential qualifications. Do not resolve uncertainty by dropping it into a distant footnote.

## Useful compositions, not templates to fill

| Content | Possible composition | What each part contributes |
|---|---|---|
| Compare an evaluation basis | Exact-value table + paired/part-whole marks + short interpretation | Lookup, visible difference and its meaning |
| Explain a mathematical rule | Definition/conditions + annotated equation + geometric intuition + justified step | The rule, intuition and why it holds |
| Document a policy | Rule in words/symbols + condition table + scope/exception notes | What is allowed, which combinations and limits |
| Explain an object's structure | Sectioned/exploded view + field glossary + labeled bracket | Composition, field meaning and group scope |
| Summarize measurements | One main chart + summary values + annotations + definitions/source | Pattern, exact reference, interpretation and evidence basis |
| Explain a real process | Focused flow/lanes + adjacent reasons + before/after state table | Order, responsibility and state changes |

The user-supplied Boole image combines a core claim, formula, qualitative sets, proof and applications. Preserve the logic behind that composition rather than its exact grid/palette/density. Its formula describes a union (“at least one”); “all simultaneously” would describe an intersection. Geometric overlap illustrates double counting; area equals probability only with a justified measure. A reference image is visual evidence, not mathematical authority.

Existing project workflow/responsibility/sectioned-record/chart images likewise inform reading hierarchy, aligned comparisons, scope brackets and local explanation. Do not treat them as verified domain specifications or reproduce their crowding. When attachments are inaccessible, name the inspected subset and the gap instead of claiming a complete project review.

## At the actual reading size

Decide the surface before making a sprawling board. Use a coherent page/panel size and leave room for labels, equations and source notes. Wide/narrow versions can stack or split sections while preserving order and criteria. A fit-all image is not a legibility check. If detailed content needs zoom, deliver focused previews as well and say so; a raster does not become responsive by shrinking it.

Use title > section heading > body/label > supporting source hierarchy, not a different box/shape for every role. Keep multi-line prose left-aligned. A short header or centered symbol can be centered. Retain necessary detail; shorten repetition, split sections or grow the surface before shrinking text.

For an existing board, revise the relevant section in place, preserve IDs/bindings and unrelated user work, and label retained alternatives. Do not keep appending successive drafts below one another. Read back persistence separately from camera focus.

## Review the document

Inspect the actual overview and relevant details at the intended reading size against the working contract:

- **Find the answer:** point to the region that answers each central reader question. Check prominence and reading order; a headline alone is not the supporting explanation.
- **See the distinction:** locate the concrete marks, alignment, state changes, grouping or annotated formula that reveal each planned distinction. Readable boxes are insufficient when their arrangement adds no understanding. For a useful text/table-first document, exact lookup and aligned criteria can satisfy this check without a chart.
- **Follow the evidence:** trace one consequential path or comparison using its nearby conditions, units and sources. Check that routing, distant legends or repeated IDs do not force unnecessary back-and-forth. Keep genuinely necessary feedback loops, but isolate their local roles or use focused views when they obscure the main path.
- **Justify each view:** state what each section adds. A table and chart can serve lookup and pattern recognition; repeated prose with no added interpretation cannot. Keep unknowns visible without making the uncertainty list dominate the answer.
- **Check transfer and limits:** compare the result with the selected reference's useful relationship, not its decorative style. Verify that no copied layout introduced unsupported chronology, hierarchy, data, policy certainty or omitted scope.

Record concrete locations and pass/fail findings in the task notes, not a self-assigned quality score. On failure, revise the encoding, shared coordinates, grouping, reading order or overview/detail split before tweaking color and padding. Re-render the changed view and repeat the failed checks plus any affected content/geometry checks. If evidence cannot support a needed distinction, show the gap rather than manufacturing it. Keep the requested format and source/render checks from the main contract; this inspection does not prove user comprehension or future-task performance.
