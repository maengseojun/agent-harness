# Pinned local Archify route

Use this route only when the user asks for Archify's own look or a feature only its viewer has; otherwise interactive-explainer draws in diagram-explainer's skin with `template-explore.html`.

Runtime: the installed Archify skill folder, `$ARCHIFY_HOME` when set, else `~/.claude/skills/archify`. Its `INSTALLED_FROM` file records the upstream commit; as of 2026-10-25 it is `tt-a1i/archify` **v3.2.0**, commit `25cf37080fc8b1dbe758a4efc3935b55f3327083`. Nothing is vendored in this repository: the earlier `vendor/archify/` path was never committed. MIT license, `THIRD_PARTY_NOTICES.md` and font notices remain in that folder. No npm installation is needed for rendering: generated validators and inline viewer are supplied. Upstream tests/build scripts need development dependencies and are not installed automatically. When neither location exists the wrapper exits 2 and says so; install it only on the user's request.

Verify Node.js 18 or newer and the needed browser are present in the current execution environment. The user's local rendering tests do not establish cloud execution or browser availability. Inspect bundled code and obtain any action-time approval required by the current software-execution policy before first running upstream code in this environment.

Use the integration wrapper rather than the upstream skill's update-aware invocation. The wrapper sets the supported `ARCHIFY_UPDATE_CHECK_DISABLED=1`, excludes remote setup/brand capture commands and allowlists the environment. Keep local browser sandboxing enabled. Network brand URLs are excluded from this integration. Use synthetic/user-approved labels; do not fetch marks.

Read `$ARCHIFY_HOME/references/authoring-defaults.md`, the selected mode schema and one example. Choose `architecture`, `workflow`, `sequence`, `dataflow` or `lifecycle` according to what the learner needs to understand. Author fresh JSON; examples are not implementation facts. Preserve teaching content in cards, guided-view notes or a nearby companion explanation. Do not shrink long evidence onto connections.

Resolve this installed skill by its frontmatter name `interactive-explainer` and set `SKILL_DIR` to its current absolute directory; do not assume the folder keeps the skill name. Run from the intended output working directory.

```sh
node "$SKILL_DIR/scripts/archify_local.mjs" finalize architecture candidate.json explanation.html --quality standard --json
```

`meta.output` must match the output's working-directory-relative path. Choose showcase for deliberate presentation diagrams; the minimal Graphify adapter emits a standard draft that still needs appropriate semantic labels, placement and source review. Finalize performs schema, delivery/provenance and browser checks. It can start installed Chrome/Chromium; it does not install a browser. The wrapper refuses `finalize`, `browser-check` and `visual-check` when running as root because the pinned upstream checker would disable its sandbox. Use a verified non-root sandboxed runtime; do not bypass its sandbox if execution is denied. `doctor` checks Node/files/validators, not browser availability or sandbox readiness. The wrapper does not pass host-specific browser-path overrides; report an unavailable browser rather than assuming the Mac installation exists here. Retain failure receipts and disclose the blocked gate. For focused diagnostics, run `validate`, `deliver`, `check`, `browser-check` or `visual-check`. Consult `$ARCHIFY_HOME/references/delivery-contract.md` for the exact CLI contract.

For a clean repository-backed candidate, provide `meta.repository` and `--repo-root` only when URL and commit identity are verified. For dirty/untracked working source, keep the adapter's hash-bearing provenance and working-source references; do not label those lines as verified at HEAD. Archify location checks establish file/line existence at a revision, not that an arrow, rationale or conclusion is true.

For each new deliverable, inspect the actual Korean output in light/dark modes and a focused view. Retain transparent standalone text and rounded nodes, use small local-color connector masks or offset labels, split crowded routes/ports, and optically align the actual Korean font. A successful automated gate alone is not perceptual review. Inline Latin font assets do not prove Korean glyph coverage on another device. For exact editor typography, deliver native draw.io and its verified preview too.

Motion is off by default. Enable trace only for a requested causal/state explanation and offer a reduced-motion alternative. Path highlights show the authored relationships; they are not measured traces. Deliver candidate, HTML, provenance, native source when required, checks and remaining limits. Hosting and Drive saves remain separately authorized destinations.
