# Explanation placement and reading order

Use this reference for multi-step teaching boards and detailed explanations. The target is a readable lesson, not a large canvas filled with prose. An explicit diagram-only request needs only the relevant visual rules.

## Plan before drawing

Write a short internal plan: learning question, learner's likely gap, premises, one-sentence takeaway per panel, reading order, and intended reading surface. Choose depth from the question and prior feedback. Do not ask the learner to make routine layout decisions.

| Depth | Appropriate when | Deliver |
|---|---|---|
| Overview | The learner asks what connects to what | One overview with short labels, essential premise, and takeaway |
| Walkthrough | The learner asks how or why | Overview plus numbered flow, step explanations, and one worked example |
| Detailed | The learner asks about implementation, assumptions, or tradeoffs | Walkthrough plus relevant state/field changes, failure path, premise consequences, and sourced rationale |

For repeated confusion, expand the missing causal step rather than adding the same explanation again. Detailed does not mean displaying every implementation detail. Keep facts, example simplifications, proposals, and inferred rationale distinct.

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

Prefer natural Korean and retain exact English identifiers where needed. Introduce an identifier with its meaning. Use relative hierarchy (title > heading > label > source) and inspect Korean at the actual reading zoom. Do not copy the reference's 12px body size into tldraw without checking legibility. Tables compare parallel facts; connected prose explains reasoning that does not fit a cell.

## Step and arrow grammar

- Number actual actions on their arrows (1. 자산 예치), or number processing nodes when no transfer arrow represents the action. Use the same step identifier in commentary and state-field markers. Avoid numbering both with conflicting sequences.
- Separate panel numbers from action numbers: panel 02 can contain R1–R7. A detail of R3 can use R3.1–R3.3. Numbers express execution order, not just visual position.
- Label alternative branches with explicit conditions (검사 통과 / 실패); do not imply both branches execute in sequence. Show failure from every relevant phase or use a clear shared failure note rather than suggesting only the last check can fail.
- Distinguish command, asset transfer, and state update when it matters. Mark atomic transaction, asynchronous wait, custody, or responsibility boundaries. Do not use a single unqualified arrow to imply an asynchronous process is instantaneous.
- Bind arrow endpoints and labels to native shapes where supported. Make labels move with their arrows. Leave enough line length on both sides of a label; lengthen or reroute the connector instead of letting text swallow it.
- Align row/column centers so intended straight arrows remain straight. Route from shape sides, avoid corners and unrelated boxes, and separate opposite-direction transfers into parallel paths. A return arrow must show its destination and trigger.

## Patterns adapted from the supplied style notes

| Learning question | Useful pattern |
|---|---|
| Who acts on whom, in what order? | Actors plus numbered action arrows |
| What is stored and what changes? | Object card with field rows and matching step markers |
| How do alternatives or before/after states differ? | Matching zones with identical inner layout; highlight only meaningful differences |
| Which operation affects which object? | Operation × object matrix, paired with a flow if order matters |
| Where does an amount go? | Labeled amount split with units and conservation check |

Keep role colors consistent across panels; use text labels as well as color. Use restrained strokes and no decorative icons, shadows, or emoji by default. Reserve emphasis for the active flow or important difference. If dashed lines mean optional/conditional behavior, state that meaning and use it consistently. Hachure and special fonts are optional renderer-specific styling, not requirements to install software or emulate unavailable features.

## Final check

- Can a reader find the entry, follow the intended order, and locate the explanation for each step without chat history?
- Are premises visible before use, and does the diagram distinguish execution, waiting, success, and failure correctly?
- Do board text, companion report, quantities, identifiers, and sources agree? Does a comparison preserve the same layout?
- Inspect native rendering at readable panel zoom, not only a fit-all screenshot. Check arrow labels, clipping, overlaps, Korean text, and the diagram-to-explanation distance. Read back the actual shapes after editing.
- An optional prediction question should have an immediately available answer. User understanding remains unverified until their response provides evidence.

Provenance: adapted from the user-provided `message.txt` describing an Excalidraw style attributed to Henry. Its claimed 40-file survey was not independently verified. The attachment describes but does not include the complete `exkit.py`, `render.mjs`, or `svg2png.py` sources. No installation commands or personal filesystem paths from it are required by this reference.
