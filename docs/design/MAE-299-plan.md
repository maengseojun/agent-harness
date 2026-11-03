# Spec/Plan: MAE-299 — nine analysis charts for easy-understanding

## Goal
The user shared a reference image (`IMG_1534.jpeg`, sample data, @isaac.perform) with nine analysis charts. They want easy-understanding to use them, built in the diagram-design way:
- a type guide with layout, colour, honest-data rules and anti-patterns;
- a real example drawn in house tokens.

The nine charts:
1. cohort retention
2. small multiples
3. control chart
4. forest plot
5. fan chart
6. survival curve
7. contribution decomposition
8. lift chart
9. ROC curve

## Placement
diagram-explainer owns figure types. easy-understanding chooses figures by checking diagram-explainer's visual-type guide, so the charts live there as a personal addition. Nothing in the 45 upstream type files changes.

| File | Change |
|---|---|
| `plugins/maeng-tools/skills/diagram-explainer/references/type-analysis.md` | New. One section per chart. |
| `plugins/maeng-tools/skills/diagram-explainer/references/visual-type-guide.md` | Add an "Analysis charts" table after the 45-row table. |
| `plugins/maeng-tools/skills/diagram-explainer/scripts/build_analysis_example.py` | New. Stdlib only. Builds the example from deterministic sample data and asserts the labelled statistics. |
| `plugins/maeng-tools/skills/diagram-explainer/assets/example-analysis.html` | New. Generated gallery of the nine charts. |
| `plugins/maeng-tools/skills/easy-understanding/references/look.md` | Point "Choosing the figure" at the analysis section. |
| `plugins/maeng-tools/.claude-plugin/plugin.json` | 0.3.11 → 0.3.12. |

## Acceptance criteria
- AC-1: `type-analysis.md` has nine sections: cohort retention, small multiples, control chart, forest plot, fan chart, survival curve, contribution decomposition, lift chart and ROC curve. Each section states:
  - Best for, and Not for with the better alternative;
  - Layout conventions;
  - Colour, by semantic role and never by hex;
  - Honest-data rule;
  - How to read it, as a caption the reader gets;
  - Anti-patterns;
  - Reader level: intermediate or advanced.
  It ends with sources.
- AC-2: `visual-type-guide.md` keeps its 45-row table unchanged. It adds an "Analysis charts" table with nine rows, each linking to an existing anchor in `type-analysis.md`.
- AC-3: `python3 scripts/build_analysis_example.py --check`, run in the diagram-explainer folder, exits 0.
  - It regenerates the gallery from fixed sample data.
  - It asserts that every labelled statistic matches the plotted data: cohort cells, control limits (mean ± 3σ), forest-plot intervals, fan bands nesting around the median, the Kaplan–Meier median, contributions summing to the stacked total, decile lift averaging 1×, and AUC by trapezoid. It also asserts every chart description's claim against the computed data, control limits taken from a stable baseline period, and cohort cell text contrast of 4.5:1 or more in both themes.
  - It confirms the committed `example-analysis.html` is byte-identical to the output.
- AC-4: `example-analysis.html` meets the house look.
  - `python3 ../easy-understanding/scripts/check_palette.py assets/example-analysis.html` prints `palette: house tokens only`.
  - Light and dark come from tokens, using the local fonts.
  - Every chart says it shows sample data.
  - The page body does not scroll sideways at 375 px.
- AC-5: each example follows its own honest-data rule:
  - the survival curve is a step function with censor ticks;
  - the control chart marks points outside the limits;
  - the forest plot has a zero line and states the interval level;
  - the fan chart's bands are labelled as percentiles of the forecast;
  - lift and ROC draw the 1× baseline and the chance diagonal.
- AC-6: easy-understanding `look.md` tells the agent to check the analysis-chart section when the question is about data: retention, segments, monitoring, experiments, forecasts, time to an event, attribution or model performance. An advanced chart always carries its "how to read it" caption.
- AC-7: maeng-tools version is 0.3.12.

## Verification
- `python3 -m pytest -q` from the repo root passes.
- AC-3: the `--check` run.
- AC-4: check_palette, plus one rendered look at desktop width and at 375 px.
- AC-2 and AC-6: a link and anchor check.
- AC-1 and AC-5: content, judged in review.
