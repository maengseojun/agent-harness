# Archify methods in our skin

How [Archify](https://github.com/tt-a1i/archify) (v3.2.0, MIT, commit `25cf370`) decides what a relationship means, where nodes go, how a page explains, and how a reader explores, restated for this skill's tokens. Our look does not change: paper/ink, one focal `accent`, the local fonts, our node treatments and connector rules. Archify's renderer, schemas and viewer are not used here; for its own look use the Archify route in interactive-explainer.

Read this for architecture, flow, data-flow, sequence and lifecycle diagrams, and for any explainer page. [primitives-core.md](primitives-core.md) connector rules still win where they are stricter.

## Relationship variants

Classify every relationship before drawing it, then paint it by meaning. Draw a legend entry only for the variants the diagram uses, worded so it is true of every relationship that uses it.

| Variant | Means | Stroke | Arrowhead | Label |
|---|---|---|---|---|
| `default` | An ordinary call or dependency | `muted` 1.4px solid | `muted` | `muted` |
| `primary` | The reader's main journey | `ink` 2px solid | `ink` | `ink` |
| `data` | A read or write to a store | `data` 1.4px solid | `data` | `data` |
| `security` | A policy, auth or approval check | `guard` 1.4px dashed `4,4` | `guard` | `guard` |
| `async` | A queued, batched or background handoff | `muted` 1.4px dashed `5,4` | `muted` | `muted` |
| `return` | Back to an earlier main-path node | `muted` 1.4px dotted `2,3` | `muted` | `muted` |
| external API | An HTTP/API call leaving the system | `link` 1.4px solid | `link` | `link` |

- `accent` is not a variant. It marks the 1–2 focal nodes and, in an explore page, the reader's current selection.
- `guard` and `data` are the two relationship colors in [style-guide.md](style-guide.md). Do not add a third; anything else is `default`.
- A condition that changes behavior (approval, auth, a state gate) sits on the relationship or node it qualifies. A side note cannot make an unconditional arrow conditional.
- Labels carry the action, protocol or direction. Omit one only when both ends already say it.
- Mark each relationship in markup with `data-variant` so the explore controller, the legend and a reviewer agree.

## Placement

Classify each relationship, then place nodes so it stays straight. The router cannot move boxes; placement decides whether lines bend.

- **Main path**: neighbors adjacent in reading order. A long path steps through rows instead of one thin strip.
- **Branch or store**: directly above or below the node that owns, reads or writes it, centered on that node so the edge is one straight segment. Keep every store and branch of one row on the same side.
- **Return**: put it on the side of the main path with no branches or stores, so it runs through an empty corridor.
- **Second entrance** into a node that already has an incoming edge: bring it in from another side, usually directly above or below.
- **Fan-out**: a box side with k relationships needs at least `32 + 14 × (k − 1)` px (four need 74px). Spread a hub's counterparts over two or three sides, or make the hub bigger. Center a parent on its children; align a child with its only parent.
- **Label gap**: two side-by-side boxes joined by a labeled edge need `6.5 px × text units + 21 px` of clear gap, counting each CJK character as two units. Budget each edge by its own label, not a row-wide gap.
- **Sublabels** at 9px need box width `5.4 px × text units + 8 px`, CJK counted twice.
- Before writing coordinates, trace every non-main relationship: its straight or one-bend corridor must not pass another node or cross another relationship. If it does, move the endpoint that is off the main path.
- Start the first actor near the canvas origin (about `40, 40`) and let content rows set the height. Empty margins do not improve reading.
- A boundary is the padded box around all its members. Keep members in one compact cluster and every non-member outside it.

## Explaining a page

When the answer is a page rather than a lone diagram, build it as an explainer:

- **Conclusion first.** The answer and its reasons lead. Every section after it supports, qualifies or applies it. Stop when nothing is left to support.
- **One question per panel**, titled with that question. A small answer gets the conclusion plus one or two panels; a how-it-works, diagnosis or checklist answer usually needs three to five.
- **Steps beside the diagram.** Steps that walk through a diagram sit next to it, not under it. Title each step with the label of the node it points at, so text and picture match at a glance. In an explore page each step lights its node.
- **Text points at the diagram.** A node name in the prose links to that node (`<a href="#focus=id">`), and a path described in prose links to that route (`#route=a~b`).
- **One term per thing** across title, panels, labels and table headers.
- **Do not restate** what a table or diagram already shows; add its reason or exception.
- End with a checklist panel when the reader must act or verify, one concrete check per item.

Choose the form by the shape of the information:

| Shape of the information | Form |
|---|---|
| Messages between parties in order | sequence |
| A process with steps and branches | flowchart / swimlane |
| Parts of a system and how they connect | architecture |
| A hierarchy | tree |
| Events over time | timeline |
| Entities with fields and relationships | ER / db-schema |
| Options compared on several criteria | table with good / caution / bad cells |
| Ordered actions or checks | numbered steps |
| Numbers across items or over time | a chart type from the visual-type guide |
| A warning or open question | a callout |

## Exploring a diagram

For a diagram the reader will study rather than glance at, start from [`assets/template-explore.html`](../assets/template-explore.html). Its controller is canonical: copy the script byte for byte; `self_check.py` rejects edits.

Markup contract:

| Attribute | On | Meaning |
|---|---|---|
| `data-explore-root` | the page's main element, once | scope of the controller |
| `data-node="id"` | each node `<g>` | stable id; letters, digits, `-`, `_` |
| `data-kind="…"` | each node | lens group; use the node treatment names (`backend`, `store`, `external`, `security`, `focal`, …) |
| `data-label="…"` | each node, optional | the name the picker, finder and status use; defaults to its text |
| `data-edge data-from data-to data-variant` | each relationship `<g>` | an authored directed relationship |
| `data-explore-steps` + `data-target="id"` | an ordered list beside the diagram | steps that light their node |
| `data-explore-status` | one `role=status aria-live=polite aria-atomic=true` element | announces every change in words |

What the reader gets: choosing or clicking a node lights everything upstream and downstream of it; choosing an end node shows the directed route between them, or says there is none; kind buttons light one group; the finder lights matches; prev/next walks the steps; `#focus=id`, `#route=a~b`, `#lens=kind` and `#step=n` restore a view, so a link can share it; Escape clears.

Rules:

- Reach and route follow only authored `data-edge` relationships, never geometry. Call the result "connected", not "impact" or "what breaks".
- The SVG stays `role="img"` with its title and desc. Clicking nodes is a pointer shortcut; the node picker is the keyboard path.
- Selection is never color-only: lit edges thicken, the focused node gets a heavier outline, and the status line says what is lit.
- Without script the whole diagram, legend and steps stay readable; say so in `<noscript>`.
- Archify's always-on edge animation is not adopted. Motion follows [animation.md](animation.md).
