# Visual-type guide (45)

(Moved from SKILL.md; section heading was `### Visual-type guide (45)`.)

| If you're showing… | Use | Reference |
|---|---|---|
| Components + connections in one snapshot; nested admin vs traffic scopes | **Architecture** | [type-architecture.md](type-architecture.md) |
| Structural change between synchronized Before / After topologies, with a Changes ledger | **Architecture delta** | [type-architecture-delta.md](type-architecture-delta.md) |
| Legacy IT landscape by phase or department; shows the *before* state | **IT current-state** | [type-it-state.md](type-it-state.md) |
| Decision logic with branches | **Flowchart** | [type-flowchart.md](type-flowchart.md) |
| Time-ordered messages between actors | **Sequence** | [type-sequence.md](type-sequence.md) |
| States + transitions + guards | **State machine** | [type-state.md](type-state.md) |
| Entities + fields + relationships | **ER / data model** | [type-er.md](type-er.md) |
| Events positioned in time | **Timeline** | [type-timeline.md](type-timeline.md) |
| Cross-functional process with handoffs | **Swimlane** | [type-swimlane.md](type-swimlane.md) |
| Two-axis positioning / prioritization | **Quadrant** | [type-quadrant.md](type-quadrant.md) |
| Multiple entities scored across 3–5 quantitative criteria | **Radar / Spider** | [type-radar.md](type-radar.md) |
| One quantitative series across cyclic categories; angle=category, radius=magnitude | **Polar chart** | [type-polar.md](type-polar.md) |
| Reinforcing cycle; the last step feeds the first and a hub accumulates state | **Loop** | [type-loop.md](type-loop.md) |
| Hierarchy through containment / scope | **Nested** | [type-nested.md](type-nested.md) |
| Parent → children relationships | **Tree** | [type-tree.md](type-tree.md) |
| Human/agent/team ownership, reporting, routing, escalation | **Org chart** | [type-org-chart.md](type-org-chart.md) |
| Stacked abstraction levels | **Layer stack** | [type-layers.md](type-layers.md) |
| Parts of one object pulled apart along one axis: a teardown, an unboxing, assembly order | **Exploded axonometric** | [type-exploded.md](type-exploded.md) |
| One floor or site seen from above at an angle: rooms with furniture, buildings by phase | **Axonometric plan** | [type-axonometric-plan.md](type-axonometric-plan.md) |
| Overlap between sets | **Venn** | [type-venn.md](type-venn.md) |
| Ranked hierarchy or conversion drop-off | **Pyramid / funnel** | [type-pyramid.md](type-pyramid.md) |
| Quantitative comparison across categories | **Bar chart** | [type-bar.md](type-bar.md) |
| A start total bridged to an end total by signed contributions (budget bridge, headcount deltas) | **Waterfall** | [type-waterfall.md](type-waterfall.md) |
| Part-of-whole where the relative sizes are the story | **Treemap** | [type-treemap.md](type-treemap.md) |
| Cross-tabulated data; fill encodes value per cell | **Heatmap** | [type-heatmap.md](type-heatmap.md) |
| Continuous trends over time, change between exactly two states (slopegraph), one distribution per series (ridgeline), or rank movement across several snapshots (bump) | **Line chart** | [type-line.md](type-line.md) |
| Tasks and phases on a timeline | **Gantt** | [type-gantt.md](type-gantt.md) |
| Correlation or distribution of two variables; bubble (three variables) and beeswarm (one variable, dot per item) variants | **Scatter plot** | [type-scatter.md](type-scatter.md) |
| End-to-end data stack on a container cluster | **High-Level** | [type-high-level.md](type-high-level.md) |
| Multi-actor sequential process with data handoffs | **Process** | [type-process.md](type-process.md) |
| Multi-tier data storage with quality levels and access policies | **Medallion** | [type-medallion.md](type-medallion.md) |
| Role-scoped data flow: who does what at each pipeline step | **Data flow** | [type-data-flow.md](type-data-flow.md) |
| Integration topology of a data platform — sources → core → consumers | **DP integration** | [type-dp-integration.md](type-dp-integration.md) |
| Per-role / per-component access permissions matrix | **DP security matrix** | [type-dp-security-matrix.md](type-dp-security-matrix.md) |
| A quantity splitting and merging across stages, band width = amount | **Sankey** | [type-sankey.md](type-sankey.md) |
| Causes of one observed effect, grouped by category (root-cause analysis) | **Fishbone** | [type-fishbone.md](type-fishbone.md) |
| Value chain against evolution — what to build, buy, and what is moving | **Wardley map** | [type-wardley.md](type-wardley.md) |
| Work-in-progress by state, with WIP limits and blocked items | **Kanban** | [type-kanban.md](type-kanban.md) |
| What a person does across stages of an experience, and how it feels | **User journey** | [type-journey.md](type-journey.md) |
| What the customer does vs what the service hides, across stages, with a line of visibility | **Service blueprint** | [type-service-blueprint.md](type-service-blueprint.md) |
| Where software runs — zones, hosts, artifacts, replicas, ports | **Deployment** | [type-deployment.md](type-deployment.md) |
| What depends on what, with fan-in and cycles a tree cannot express | **Dependency graph** | [type-dependency.md](type-dependency.md) |
| Classes with operations, inheritance, composition (other UML routes elsewhere) | **UML class** | [type-uml-class.md](type-uml-class.md) |
| Narrative backbone sliced into releases, with the cut line | **Story map** | [type-story-map.md](type-story-map.md) |
| Physical tables: SQL types, constraints, indexes, column-level FKs | **Database schema** | [type-db-schema.md](type-db-schema.md) |

Rules of thumb:

- If a 3-column table communicates the same thing, pick the table.
- If two types seem useful, pick the dominant axis; a semantic pattern may add behavior-specific primitives, not a second layout grammar.
- If past the complexity budget (§7), reduce repetition and group related marks; preserve the personal one-canvas overview before adding a separate detail view.

**Always load the chosen type reference linked in the guide before drawing.** When routed above, also load `semantic-patterns.md`; when animation is chosen, load `animation.md`.
