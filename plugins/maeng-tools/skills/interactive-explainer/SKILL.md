---
name: interactive-explainer
description: Choose suitable tables, charts, trees or diagrams, then add interaction when changing values, comparing cases or tracing paths helps learning. Use for requested simulations or explorable explanations; keep static summaries simple and preserve paired editable sources.
---

# Interactive explainer

Build around one learning question and the smallest interaction that answers it. Use the user's language for labels and the explanation. State important model assumptions and limits.

## Select the view before the interaction

For explanations and summaries, first identify what the reader needs to understand and what the supplied information can support. Choose the representation before choosing a renderer or control. Distinguish a quantitative chart from a relationship graph; the word “graph” alone does not select either.

| Information / reader task | Useful starting view | Interaction when it helps |
|---|---|---|
| Compare or look up exact attributes | Table or matrix | Select comparable cases and highlight changed cells |
| Understand quantities, trends or distributions | Appropriate chart with units, scale and data basis | Change a supported parameter and update the chart and values together |
| Understand a hierarchy or parts within a whole | Tree or nested boundaries | Expand a branch or inspect a level without losing its parent context |
| Follow connections, handoffs or state changes | Relationship graph, lanes, timeline or before/after views | Trace a selected path or step through a meaningful transition |
| Understand overlap, conditions or a mathematical rule | Set view, decision tree, annotated formula or worked calculation | Change a valid case or reveal a derivation step and explain its effect |
| Summarize a mixed topic | Short prose with selected tables, figures and adjacent explanations | Add a control only where it resolves a specific question |

These are starting choices, not a closed catalog. Use another form when it better expresses the information; do not invent numbers, hierarchy or causality to fit a template. When paired with diagram-explainer, use its Representation selection reference for choosing views and Explanation layout for document composition; a paired static document follows its native delivery contract. Keep the core answer, conditions and interpretation visible without clicking every item.

For each proposed interaction, identify the input, visible consequence and learning benefit. If a static view answers the request, deliver that view with its explanation; an ordinary explanation or summary does not require an app. Honor an explicit interactive request with the smallest useful interaction. Pan/zoom, hover decoration and an expandable paragraph do not establish a causal simulation. In a composite explainer, keep unaffected panels stable and update related values, labels and interpretation together.

## Choose the rendering route

- After selecting a useful path/state interaction, prefer the pinned **Archify 3.0.1** route for architecture, relationship/path exploration, request sequences, workflows, data flows and lifecycle/state diagrams. Read [local Archify route](references/archify-local.md) and the selected vendor schema/example. Use `scripts/archify_local.mjs`; it disables automatic update checks and passes no provider keys. Keep typed candidate JSON, evidence and the final HTML/SVG together.
- Keep self-contained HTML/SVG/JS for variable controls, numerical charts, probability/mathematics and causal simulations. A sequence diagram or path highlight does not simulate quantities, runtime timing or probability. A combined lesson can use both routes with the same example and assumptions.
- Within a user-requested repository-grounded explanation, use graphify-repository as an internal helper when repeated relationship extraction/reuse is useful; no separate learner invocation or indexing request is required. Use `scripts/index_repository.py --previous <snapshot.json>` from that helper to reuse a matching local AST index or rebuild a changed scope into a new snapshot, then re-read consequential relationships in source and select a focused subgraph. Read [minimal adapter contract](references/graphify-adapter.md). Small one-off source questions and repository-free conceptual/simulation lessons do not need Graphify. Its graph remains an analysis clue; do not infer architecture, direction or causal order merely from links, and preserve extracted/inferred/unverified status and omissions.
- Pair with diagram-explainer's editable **draw.io first / yEd GraphML supplement** for authoring. Archify HTML/SVG explains and explores the same entities, learning question, premises, evidence, worked example and optional question/answer. It does not replace an editable original or a separately requested simulation.

## Teaching defaults

- For this user, start with the core intuition and add necessary background afterward. Infer prior knowledge from the conversation; ask only if the answer would materially change the lesson.
- Before building, identify the learning question, likely misconception, the input the learner changes, the visible consequence, and any invariant. Use a concrete example → visual intuition → general rule or formula when useful → return to the question. This is a 3Blue1Brown-inspired teaching structure, not a required aesthetic or video request.
- Default to a short guided sequence followed by free exploration. Keep back, next, skip-to-explore, and reset available where relevant. Do not force completion of the guide. Explain one change and its cause at each step; keep entity names, colors, units, and example values consistent.
- Use optional prediction questions only when they expose a useful misconception. Provide an immediately available answer with a reason and allow skipping. Never lock progress behind a submitted or correct answer; do not introduce scoring or a quiz system without a request.
- Apply ASD-STE100-inspired clarity, not formal compliance: natural Korean for Korean requests, short sentences with one main idea, concrete subjects and verbs, consistent terms, and brief definitions when needed. Preserve necessary detail, uncertainty, code, and quotations.
- Use motion to show a causal or state change, not for decoration. Make the same explanation available without motion and distinguish illustrative transitions from actual system timing.
- Example: guide the learner through a fixed 10% ownership share before and after an exchange. Then let them vary the exchanged amount and inspect the quantities owed. Optionally ask whether changing the asset mix changes the ownership percentage, with an immediate answer. State the simplified assumptions.
- When paired with diagram-explainer, keep the draw.io/GraphML original and interactive companion consistent. Preserve transparent standalone text, small borderless connector-label masks matching the local surface, separated ports/routes in crowded areas, and font-specific Korean optical alignment. Inspect the actual rendering; diagram-explainer's draw.io spacing values do not automatically transfer to Archify SVG.

## Build and verify

- For custom interactions such as table comparison, tree exploration or numerical simulation, default to one self-contained HTML file with inline CSS, SVG, and plain JavaScript. Use existing project conventions when editing an existing app. No remote assets, tracking, API calls, or package installs are needed for a simple explainer. For Archify, use the bundled renderer and its local verification commands; do not run upstream installers, network update/brand capture or silently add dependencies.
- Prefer a slider, toggle, or step button with visible labels and an immediately visible result. Include a short explanation of what changed. Make controls keyboard-usable; do not rely only on color or motion.
- Use React Flow only when editable node-and-edge interactions genuinely require it and the environment already supports it, or the user approves the needed setup. A flowchart alone does not justify a framework.
- Keep example data synthetic unless the user supplies appropriate data. Do not publish, upload, or send private data to external services without authorization.
- Validate the main interaction and the few boundary values that matter. Check the displayed result against the underlying rule. Verify the guided-to-explore transition, reset, and immediate answer/skip when present. Use an available browser to inspect readability and interaction; report browser testing as not run when it is unavailable. Avoid broad test scaffolding for a small illustration.

For an interactive deliverable, return the runnable file, one sentence on how to use it, and the main insight. For a selected static route, deliver the appropriate visual and explanation instead. Hosting is a separate action and requires the user's requested destination or approval. Do not describe a generated file as a live website.
