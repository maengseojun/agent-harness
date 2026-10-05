---
name: interactive-explainer
description: Build a small interactive explanation when changing a parameter, comparing states, or stepping through a process helps learning. Use for requested simulations or explorable explanations; do not turn a simple static diagram into an app.
---

# Interactive explainer

Build around one learning question and the smallest interaction that answers it. Use the user's language for labels and the explanation. State important model assumptions and limits.

## Teaching defaults

- For this user, start with the core intuition and add necessary background afterward. Infer prior knowledge from the conversation; ask only if the answer would materially change the lesson.
- Before building, identify the learning question, likely misconception, the input the learner changes, the visible consequence, and any invariant. Use a concrete example → visual intuition → general rule or formula when useful → return to the question. This is a 3Blue1Brown-inspired teaching structure, not a required aesthetic or video request.
- Default to a short guided sequence followed by free exploration. Keep back, next, skip-to-explore, and reset available where relevant. Do not force completion of the guide. Explain one change and its cause at each step; keep entity names, colors, units, and example values consistent.
- Use optional prediction questions only when they expose a useful misconception. Provide an immediately available answer with a reason and allow skipping. Never lock progress behind a submitted or correct answer; do not introduce scoring or a quiz system without a request.
- Apply ASD-STE100-inspired clarity, not formal compliance: natural Korean for Korean requests, short sentences with one main idea, concrete subjects and verbs, consistent terms, and brief definitions when needed. Preserve necessary detail, uncertainty, code, and quotations.
- Use motion to show a causal or state change, not for decoration. Make the same explanation available without motion and distinguish illustrative transitions from actual system timing.
- Example: guide the learner through a fixed 10% ownership share before and after an exchange. Then let them vary the exchanged amount and inspect the quantities owed. Optionally ask whether changing the asset mix changes the ownership percentage, with an immediate answer. State the simplified assumptions.
- When paired with diagram-explainer, keep the chosen native diagram (tldraw by default, or Excalidraw for its selected use case) and this interactive companion consistent. The HTML simulation does not satisfy a separately requested editable board or diagram file.

## Build and verify

- Default to one self-contained HTML file with inline CSS, SVG, and plain JavaScript. Use existing project conventions when editing an existing app. No remote assets, tracking, API calls, or package installs are needed for a simple explainer.
- Prefer a slider, toggle, or step button with visible labels and an immediately visible result. Include a short explanation of what changed. Make controls keyboard-usable; do not rely only on color or motion.
- Use React Flow only when editable node-and-edge interactions genuinely require it and the environment already supports it, or the user approves the needed setup. A flowchart alone does not justify a framework.
- Keep example data synthetic unless the user supplies appropriate data. Do not publish, upload, or send private data to external services without authorization.
- Validate the main interaction and the few boundary values that matter. Check the displayed result against the underlying rule. Verify the guided-to-explore transition, reset, and immediate answer/skip when present. Use an available browser to inspect readability and interaction; report browser testing as not run when it is unavailable. Avoid broad test scaffolding for a small illustration.

Deliver the runnable file, one sentence on how to use it, and the main insight. Hosting is a separate action and requires the user's requested destination or approval. Do not describe a generated file as a live website.
