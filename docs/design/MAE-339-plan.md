# MAE-339 Plan: icon pass in every structure figure

## Goal
Structure figures drawn by easy-understanding and interactive-explainer (maps, phase figures, whole-flow canvases, slides, interactive widgets) get icons on concrete nodes by the MAE-331 rule, not only figures from a plain diagram-explainer request.

## Scope
- `easy-understanding/references/look.md`: replace the one-line defaults bullet with an "Icons in every figure" section.
- `easy-understanding/SKILL.md` Flow step 5 and `references/review.md`: call the icon pass and check it.
- `diagram-explainer/references/explanation-design.md`: widen "Icons on nodes" to every structure figure.
- `interactive-explainer/SKILL.md`: point at the same rule.
- Out of scope: icons on abstract nodes (decisions, rules); version bump and release (separate change).

## Acceptance criteria
- AC-1: `easy-understanding/references/look.md` has a `### Icons in every figure` section naming the map, phase figures, whole-flow canvas, slide figures and interactive widgets, linking to `explanation-design.md#icons-on-nodes`, and the old defaults bullet is gone. A text-only chat map is exempt from the pass.
- AC-2: `easy-understanding/SKILL.md` Flow step 5 has an icon-pass step, and `references/review.md` has an `**Icons.**` checklist item.
- AC-3: `explanation-design.md` § Icons on nodes says it applies to every structure figure, whichever skill draws it.
- AC-4: `interactive-explainer/SKILL.md` links to `../diagram-explainer/references/explanation-design.md#icons-on-nodes`, and the link resolves.
- AC-5: `python3 -m pytest -q` passes on the final tree.
