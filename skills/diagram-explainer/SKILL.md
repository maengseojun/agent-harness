---
name: diagram-explainer
description: Structure explanations, summaries and human-readable documentation as editable visual documents in draw.io. Choose and combine prose, tables, charts, annotated drawings, formulas, timelines, sets and relationship views from the reader's question and available evidence. Use for explicit invocation or when visual structure materially helps; add interaction only when it helps exploration.
---

# Diagram explainer

Use **draw.io / diagrams.net first as an editable visual-document workspace**. The skill name does not restrict the result to node-and-edge diagrams. A document may be mostly a well-designed table, an annotated formula, a spatial drawing, quantitative plots, or connected prose with selected figures. Decide what the reader needs to understand before choosing marks, layout or templates. Drawing a box around every sentence is not information design.

## Delivery contract

For an explicit explanation, summary or documentation request with this skill, create the actual native `.drawio` result, inspect its draw.io rendering, and return the editable source with a verified preview/link and the explanation at the requested depth. A chat table, Mermaid block or statement that the skill was used alone is insufficient. Static means no app or simulation; it still follows this contract. Honor an explicit text-only/no-file request, a diagram-only request, or another requested output format. Editing/discussing this skill is not a request to draw a lesson.

For implicit use, make the smallest useful visual when it materially helps; short prose can be enough. Do not force a dense board, teaching sequence, quiz, graph or app onto every answer. A visual document can consist of one view and a short interpretation. When it is the reading surface, keep the core answer, necessary definitions, conditions and interpretation on it so it works without chat history.

## Design from information

1. **Understand the reading task.** What should the reader find, compare, infer, calculate or do? Identify the audience, core answer, relevant facts/data, units, scope and unknowns. Compose the reasoning before distributing it into panels. Infer routine layout choices; ask only for missing information that materially changes the result.
2. **Choose representations.** Read [Representation selection](references/representation-selection.md). Select from the information's structure and the reader's task, not the word “diagram”, a familiar template or an available shape. For a nontrivial choice, compare the few useful candidates internally and choose what exposes the intended distinction with the least reading effort. Use another form when none fits; never invent numbers, hierarchy, chronology or causality to fit one.
3. **Compose the document.** Read [Explanation layout](references/explanation-layout.md) for a mixed/detailed document. Give each section a reader question and nearby answer/evidence. Combine views only when they contribute different information, sharing terms, examples and units. Use whitespace, aligned rows, section bands, brackets or annotations where those express the relation; connections are optional. Read [Visual grammar](references/visual-grammar.md) for logical relations, line meanings, typography and native marks.
4. **Check meaning before styling.** Keep observed facts, illustrative values, proposals and inferred rationale distinguishable. Preserve consequential conditions and show what changes when a premise fails. A convincing picture, successful example or automatic layout does not establish a general proof, causation, implementation or adoption.

## Use references without narrowing the work

- For an unfamiliar representation or richer expression, use [Visual reference library](references/visual-reference-library.md): Blocks & Arrows for relational structure, Data Viz Project for input/function alternatives, Datawrapper for tables/quantitative grammar, and Our World in Data for claim–figure–definition–source composition. Inspect the relevant actual example; a site/category name alone is not a design or correctness authority. A familiar task need not revisit every site.
- [Structure catalogue](references/structure-catalogue.md) and the [36 native pages](assets/drawio/structure-templates.drawio) / [library](assets/drawio/diagram-explainer.drawio-library.xml) are optional starting layouts, not a menu or the full capability of draw.io. Copy a suitable unit and adapt it; start from native elements when none fits. Never use placeholders or a screenshot as the final editable content.
- [Composition examples](assets/drawio/composition-examples.drawio) show an annotated numeric comparison, formula/set explanation, joint logical conditions, and a reference document. Their [data](assets/drawio/composition-data.json) are synthetic. Reuse their construction, not their facts or a mandatory page structure.
- For quantities aligned with event/state lanes, read [Diagram + graph composition](references/diagram-graph-composition.md). Keep axis coordinates meaningful; do not run graph auto-layout on quantitative/spatial geometry.

## Author, save and verify

Read [draw.io setup](references/diagrams-net-setup.md) for the selected environment's tested routes, font and storage. Inspect live MCP schemas before using tools. Use exposed native draw.io tools when useful; retain the actual `.drawio` source separately. If MCP is unavailable/fails, generate valid native XML and use the official Desktop/browser editor. A missing MCP is not a reason to return only chat prose. yEd Live is a supplement for automatic relationship-graph layouts; preserve `.graphml` when used. Obsidian is excluded. Preserve old boards, unrelated elements, page/element IDs, bindings and concurrent user edits; never bulk migrate or delete them.

The preferred remote destination remains the school account **2025131619@korea.ac.kr**, [diagram-explainer folder](https://drive.google.com/drive/folders/1uKZxJVSlQ_h9IiyW0gV3b8Vc5oG-Wea7). Verify the connected account and destination before writes, upload the actual editable original, then retrieve its metadata/raw content and compare. iCloud is a preserved backup. Do not substitute accounts or change sharing. A local file or opened editor URL proves neither cloud save nor cross-device sync. If remote access/rendering fails, keep and link the local native draft, disclose the exact failed stage and stop claiming that stage complete.

Use the user's Korean font **나눔손글씨 다행체** where supported; enlarge/split the reading surface before shrinking text. Keep rounded ordinary cards and role-consistent colors, but do not round data bars, distort set/formal geometry or turn every table cell/text paragraph into a card. Typography and connector-mask calibration live in Visual grammar; verify actual glyphs after font/device changes. Files do not transport an installed font automatically.

Verify the applicable result:

- **Content:** requested scope/depth covered; claims, conditions, sources and conclusions agree; the artifact is understandable without omitted chat context.
- **Representation:** table criteria/unknowns, chart units/scales/data positions, logical operators, set membership, grouping and any genuine flow are truthful. Recalculate consequential values. No decorative edge implies an unsupported relation.
- **Native integrity:** editable text/marks, valid XML, unique IDs and intact page/parent/edge references; read back/reopen the saved source.
- **Rendered usability:** inspect overview and relevant details at intended reading size; Korean wrapping, actual equations, alignment, clipping, contrast, data labels, annotation targets and connected endpoints. Correct observed defects. Parsing/registration/CI alone is not rendering evidence.

Report artifact links, checks and concrete gaps accurately. Instruction edits, demonstrated generation and user-understood results are different outcomes; claim comprehension only from the user's response.

## Conditional companions

For learning, a concrete example → visible relation → general rule → return to the question is useful when the subject needs it. A reference document or short comparison need not become a tutorial. A prediction/teach-back question is optional with its answer immediately available; repair the missing step instead of repeating the whole document.

Pair with interactive-explainer only when manipulating an input, inspecting a path or stepping through a state answers a question, or when explicitly requested. Keep the core static answer visible and share examples, assumptions and units. Archify's HTML/SVG route is a conditional companion for useful graph/path/state exploration; it does not replace the native original. Mathematical/quantitative simulations use the existing self-contained HTML/SVG/JS route; pan/zoom alone is not a simulation.

For repository-grounded work, use Graphify only when repeated tracing, a large scope or a matching index helps. Small source questions use direct source reading; conceptual documents need no index. Read graphify-repository's local-evidence guidance, verify/reuse the previous snapshot or rebuild into a new one when source/revision/scope changes, and re-read consequential relationships in actual source. Retain direction, path/line, extracted/inferred/unverified status and omissions. No automatic semantic document/media extraction or external model transmission.
