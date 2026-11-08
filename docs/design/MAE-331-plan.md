# MAE-331 Plan: icons on nodes in explanation diagrams

## Goal
Explanation diagrams drawn by diagram-explainer and easy-understanding use icons for concrete things and outcomes, as in Anthropic's blog figures, instead of text boxes only.

## Scope
- Add a Concepts section of Tabler (MIT) icons to `diagram-explainer/references/primitive-icons.md` and the gallery `assets/icons.html`, in the house format.
- Add an "Icons on nodes" rule to `diagram-explainer/references/explanation-design.md`.
- Point to the rule from `diagram-explainer/SKILL.md` and `easy-understanding/references/look.md`.
- Out of scope: changing the 211 existing examples; new tooling or dependencies.

## Acceptance criteria
- AC-1: `primitive-icons.md` has a `## Concepts` section with 12 icons (document, documents, write, read, ok, fail, link, merge, agreement, message, model, time). Each uses the house SVG format (24×24 viewBox, `fill="none"`, `stroke="currentColor"`, `stroke-width="1.5"`, `aria-hidden="true"`) and has a `Source: Tabler Icons / <name> (MIT)` line.
- AC-2: `assets/icons.html` shows the same 12 icons in a Concepts section, so the gallery and the doc both list 99 icons.
- AC-3: `explanation-design.md` has a `## Icons on nodes` section. It says when to use an icon (concrete things, outcomes next to a word label), when not to (abstract nodes), one style per figure, the label is never replaced, and how to add a missing Tabler icon.
- AC-4: `diagram-explainer/SKILL.md` and `easy-understanding/references/look.md` link to `explanation-design.md#icons-on-nodes`, and the links resolve.
- AC-5: `python3 -m pytest -q` passes on the final tree.
