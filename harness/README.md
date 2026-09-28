# Personal harness

Use **harness-run** for substantial research, documents, analysis and coding in
any permitted local workspace. The host agent coordinates work, relevant
specialist skills and an independent reviewer. Python's standard library saves
progress and evidence. No new server, paid API, scheduler or background daemon.

## Independent skill library

This private repository stores each standalone personal skill under its own
`skills/<name>/SKILL.md` path. GitHub is the versioned source; a skill is usable in
a local host only after that host installs or discovers that folder. A commit to
this repository does not update an installed copy. The separate
`skills/skill-feedback/SKILL.md` skill turns observed,
reusable task feedback into a focused skill revision. It can be used without
`harness-run`; the harness remains an optional coordinator for substantial work.
The [personal skill catalog](https://github.com/maengseojun/agent-harness/blob/feat/harness-v1/skills/README.md) lists the independent skills
currently stored here and how to install a selected skill from a reviewed commit.

For ordinary work, select the relevant specialist skill directly, complete the
request and apply its relevant checks to the actual result. Record what worked
and any concrete gap; correct that gap. When feedback is reusable, apply
`skill-feedback` to the matching skill's canonical source. Check the revised
skill on a representative request, review, commit and push only its source files,
fetch and compare those files from the exact remote commit, install the reviewed
version, and inspect the next real use. Keep one-off
corrections in the task. This is a host-directed loop, not an automatic
background learner or a claim that every task produces a new skill.

The existing private `maengseojun/agent-harness` repository is the single
publication path. Skill folders are independent; they do not need separate GitHub
repositories to be selected independently. The older local `Documents/ChatGPT/Skills`
draft is not an installation or publication source. Create a separate repository
only when a skill needs distinct access, licensing or release ownership.
Existing skills can have another canonical path: `harness-run` is sourced from
`.agents/skills/harness-run/SKILL.md` and packaged by `harness/install.py`.

## Advisory skill routing

Skills can supply optional guidance without turning their entire workflow into
task requirements. Consider relevant guidance from the requested outcome, not
only a keyword. Read it when it adds value; skip redundant advice. A requested
style or existing design system wins over aesthetic preferences. Repository
rules, safety boundaries and necessary artifact checks remain binding.

Keep one existing skill responsible for each capability. Explicitly requesting
an upstream workflow is different from consulting its advice.

### Reading or acquiring a skill

The user authorizes both routes for personal tasks, without a fresh confirmation
for each task-relevant skill:

1. **Read and apply:** inspect relevant GitHub SKILL.md files, references or other
   source files; apply useful recommendations as advisory guidance. This is enough
   for a one-off question or guidance already covered by an existing skill.
2. **Acquire and use:** when a task needs a missing capability or repeated use
   benefits from a packaged skill, inspect and bring in only the selected folder.
   Prefer the linked mattpocock/skills and pbakaus/impeccable repositories first;
   search other GitHub sources when they do not fit. No blanket collection install.

Before acquisition, review SKILL.md, referenced files, scripts, agent metadata,
license and required dependencies at an exact commit. Compare with installed
skills: reuse an existing owner when equivalent; add only useful missing guidance
to its canonical source, or install a distinct capability under a non-conflicting
name. Preserve local edits and old versions; do not overwrite namesakes.
Announce the source, capability and overlap decision, then use skill-installer
where available and compare installed bytes with the reviewed source. Preserve
provenance and explain any adaptation instead of claiming it is an unmodified
upstream install. Newly installed skills may need a catalog refresh; for the
current task, explicitly read their verified local files before using them.

The standing authorization covers skill files, not executing bundled code,
automatic runtime downloads, hook registration, paid services, account changes,
external publication or team installations. Evaluate those actions under the
actual task authorization. Optional acquisition failures do not block independent
work; report the concrete gap. Acquiring a skill does not make every upstream
recommendation mandatory or override the user's style and scope.

| Request or action | Existing owner | Optional addition and overlap decision |
| --- | --- | --- |
| General website or app UI, including a named style | frontend-guidance | Read selected Impeccable guidance or acquire its reviewed skill folder when justified; bundled runtime/hook execution is separate. |
| Dithered artwork and purposeful motion | dither-motion-landing | Keep its asset and motion guidance; frontend-guidance only for a distinct design question. |
| HTML presentation | frontend-slides | Keep deck-specific layout; do not substitute general web rules. |
| UI compliance audit | web-design-guidelines | Keep the existing reviewer; avoid a duplicate Impeccable audit. |
| Clarify an assignment | task-brief | [Grilling](https://github.com/mattpocock/skills/blob/c55ee46073ed923f86ce59a5eb3b6d895095d1b7/skills/productivity/grilling/SKILL.md) can inform questions; omit exhaustive interviews and confirmation gates unless requested. |
| Implement or debug agreed work | execute-code-brief | [Diagnosis](https://github.com/mattpocock/skills/blob/c55ee46073ed923f86ce59a5eb3b6d895095d1b7/skills/engineering/diagnosing-bugs/SKILL.md) for difficult repros; [TDD](https://github.com/mattpocock/skills/blob/c55ee46073ed923f86ce59a5eb3b6d895095d1b7/skills/engineering/tdd/SKILL.md) for behavior tests. No new pre-test approval ritual. |
| Review a code change | Installed code-review and project checks | [Two review axes](https://github.com/mattpocock/skills/blob/c55ee46073ed923f86ce59a5eb3b6d895095d1b7/skills/engineering/code-review/SKILL.md) can distinguish requirements from code quality; no duplicate skill or tracker setup. |
| Create or revise agent instructions | skill-creator / skill-feedback | [Writing for agents](https://github.com/mattpocock/skills/blob/c55ee46073ed923f86ce59a5eb3b6d895095d1b7/skills/productivity/writing-for-agents/SKILL.md) can inform pruning and conditional references; keep canonical local sources. |

The Matt Pocock pointers above are pinned to reviewed revision
`c55ee46073ed923f86ce59a5eb3b6d895095d1b7`. Fetch only useful sections as reading
material. Do not execute embedded setup, install hooks, publish to a tracker or
apply unconditional upstream instructions merely because a reference was read.
Missing optional access does not block permitted implementation.

For tracked work, snapshot the selected local adapters in `start.skill_paths`.
Record external reading URL/revision and the useful or skipped recommendation in
existing brief/evidence; do not put raw advisory upstream skills into the frozen
required-skill set. Review the user's acceptance conditions and the checks needed
for the artifact, not compliance with every advisory recommendation. Additional
optional reading can be recorded without changing frozen requirements; a genuine
new requirement still follows the existing bounded follow-up rule.

Discovery uses skill descriptions and these conditional pointers, not an enforced
classifier. It permits implicit selection but does not guarantee every request
will load a guide. Check routing and actual benefit on representative real tasks.

## Ownership and destination checks


Resolve the owner from the requested output, explicit target, issue and live
project entry. A folder name or Endix mention does not decide ownership. Personal
work uses the personal workflow; actual Endix work follows the current project
entry and reuses its existing issue, umbrella and flow identity. Mixed work keeps
separate outputs, destinations and permissions. A private analysis about Endix
can remain personal. This personal harness cannot stand in for Endix's team
workflow, approve a gate, or change Endix services. When its entry or access is
missing, make a bounded read-only handoff.

Endix bootstrap locators last checked 2026-09-24: [END-462](https://linear.app/endix-labs/issue/END-462)
(overview), END-464 (Docs decisions) and END-471 (flows). They are locators, not
copies of current instructions or proof that automation is deployed. Read only
the live flow and domain sources this handoff needs. The observed personal
Linear team was `maeng` / `MAE`, and Endix was `endix-labs` / `END`; revalidate
the active workspace, team and canonical target before every authorized write.
Do not infer access or permission from a display name or a saved URL. Missing
access blocks that write; it never redirects a team result into personal Notion
or Linear. Do not send team messages or impersonate a human approval.

For a tracked run, keep a private route record with source/check time,
destination and existing issue/flow, permitted writes and next action. Unknowns
stay unknown. `start.refs` can link this evidence; it is not a gate or a new
runner command. Recheck on resume. The ledger's `owner` denotes its coordinating
agent, not the personal/team output owner. A material change in destination or
authority needs a new bounded handoff rather than silently repurposing the frozen
task. The [entry hook](https://github.com/maengseojun/agent-harness/blob/feat/harness-v1/harness/ENTRY-HOOK.md) explains the configured local routing and
its limits.

## Notion workspace

Use the standalone [Harness hub](https://www.notion.so/3e3e203190cd8143bdf5df0b46c1cb57)
as the personal library of concluded work. Linear is the brain/memo/draft for
full task maps, dependencies, drafts, decisions and progress.
See [workspace destinations and capture contract](NOTION-WORKSPACE.md).
New personal runs use library closeout: verified work can finish while its
Notion draft awaits approval. The work-records skill proposes a record, saves
only after concrete user approval, reads it back, then reviews and refines it.
The record then needs separately read and verified backlinks from the original
personal Linear issue and the personal Notion project index. A saved draft is
not a reviewed or final record; finalization requires approved review and both
backlinks. Index writes need their own concrete approval. In a native Codex
session use `CODEX_THREAD_ID` for the owner and record session ID, never the
entry receipt token.
Endix workspace Notion requires separate explicit approval. GitHub is not a
universal completion condition. Historical managed tasks retain their frozen
delivery contracts, but do not grant fresh Notion-write permission.

### Learning from actual reuse

The [reuse feedback contract](NOTION-WORKSPACE.md#reuse-feedback) links the entry
question, inspected Knowledge/source, actual use and observed result through the
existing Run. `Last Used` and `Reuse Outcome` make that evidence findable in the
existing Knowledge database; they do not imply user acceptance or source freshness.
This adapts OSK's distinction between navigation and evidence and Hindsight's
retain/recall/reflect cycle without a second store or agent runtime. A single
reuse is a functional check, not proof of reduced cost or better general recall.

Design references checked 2026-09-25: [OSK navigation and evidence](https://github.com/lpaiu-cs/osk-system/blob/bf32df027350b9dcfeafac43881d2ffd80d8e8d0/_governance/records/2026-08-29-navigation-evidence-separation.md),
[Hindsight concepts](https://github.com/vectorize-io/hindsight/blob/ac1962e6f577339ef10a39f2c72b03306b377cbf/README.md#core-concepts),
[Superpowers requirement/quality review](https://github.com/obra/superpowers/blob/5bf4e78011075bcfc0dc295f0724994cd123ee71/skills/subagent-driven-development/task-reviewer-prompt.md),
and [Strands stop reasons](https://github.com/strands-agents/harness-sdk/blob/7ae759d3ad43916d373cf0f3251ac7f57e95339c/site/src/content/docs/user-guide/sdk/agents/agent-loop.mdx#stop-reasons).

## Install once for this user

From the source repository:

```sh
python3 harness/install.py
```

The installer copies a self-contained release to
`~/.local/share/agent-harness/releases/<digest>/harness-run` and registers the same
release in `~/.agents/skills/harness-run` and `~/.codex/skills/harness-run`.
It never changes shell startup, model configuration, permission settings or other
skills. User-created conflicting files are preserved. Reinstall to adopt reviewed
changes; old releases remain available for in-flight tasks. There is no automatic
update. You may move the source checkout after installation.

`harness/install.py` manages only `harness-run`. Install a reviewed standalone
skill folder separately in each host's user-level skill directory, then compare
its `SKILL.md` with the exact reviewed GitHub revision. This keeps each skill's
availability and update independent of the harness release. On this machine,
`skill-feedback` is copied to both `~/.agents/skills/skill-feedback` and
`~/.codex/skills/skill-feedback` after its first reviewed publication.

Open a fresh local task so its skill catalog can discover **harness-run**, or ask
an existing task to read `~/.agents/skills/harness-run/SKILL.md` explicitly. Say:

> Use harness-run in this workspace to [request]. Done means [criteria].

Select the actual target folder; a Git repository is optional. The host should
use document/spreadsheet/slide/research specialist skills when the output needs
them. The harness provides recovery and review, not domain expertise.

## Current environment boundary

The Python runtime is portable across local POSIX environments with Python 3.10+
and a local filesystem. It requires neither Being agents nor a GitHub login for
ordinary tasks. Standalone skills are available in the desktop app and Codex;
user-scope skill discovery is described in the
[official skills documentation](https://learn.chatgpt.com/docs/build-skills).
[Work supports local files and tools](https://learn.chatgpt.com/docs/get-started-with-work)
when available. Check Python/file access and independent-review tools in the
actual Work task. Installing here alone is not evidence of a completed Work run.
Cloud tasks and other computers need their own installation and accessible input
files; this installation does not synchronize local SQLite or credentials.

## Design-first model routing

Status: user-adopted upper-model lead / Luna Max policy, updated on 2026-09-27.
The host follows
this policy when its available tools and permissions allow model selection. The
Python ledger does not dispatch models. Its `route` command freezes skills; it is
not a model router. This update does not implement automatic model switching or
establish a measured cost or quality advantage.

### Preferred phase assignments

- Lead: the current upper-capability model, preferably GPT-6 Astra (`gpt-6-astra`)
  when selecting a lead. Own design, material decisions, decomposition,
  integration and final acceptance; do not create a second orchestrator.
- Execution: GPT-6 Luna (`gpt-6-luna`), reasoning effort `max`. Explicitly select
  it for bounded, well-specified collection, transformation, drafting and scoped
  implementation when supported by the active dispatch tool. This is the default
  delegation rule, not a claim that every host offers this model.
- Routine verification: GPT-5.6 Terra (`gpt-5.6-terra`). Compare artifacts with the
  original requirements, execute relevant checks and investigate simple failures.
- Complex verification: GPT-5.6 Sol (`gpt-5.6-sol`). Review integration behavior,
  assumptions, edge cases and consequential security, permissions or funds logic.
- Design revision: return to Astra when evidence exposes a requirement conflict
  or architectural defect. Do not repeat the entire project for a local defect.

For an unchanged approved brief, delegate to Luna Max without another design
phase. Keep trivial, tightly coupled and open-ended judgment work with the lead.
Parallel workers need independent tasks and disjoint write scopes. Workers must
preserve others' edits, escalate material decisions and plan changes, and must
not spawn further agents. Return result, changed paths/evidence, checks and open
issues. The lead inspects actual artifacts and diagnoses failures before retrying.
Use compact briefs and referenced files; request isolated context when supported
instead of assuming a full-history fork will select the intended worker model.
A small format conversion does not need four agents.
Deterministic comparison, arithmetic, hashes and tests should use existing code
or tools; models choose and interpret checks rather than replace execution.
Important tasks may need a specialist review regardless of the chosen model.

### Handoff contract

Before assigning execution, provide the objective, in/out of scope, inspected
source versions, input and output paths, acceptance criteria, relevant checks,
allowed writes, unresolved decisions and conditions for returning to design.
Design must use real code or source evidence and small experiments when needed.
If a decision could change scope, correctness or permissions, execution returns
that question to the designer instead of silently making a new assumption.

The independent reviewer receives the original brief, actual artifacts and raw
check outputs, not only an implementation summary. It must not be the task owner
or an artifact author, even if an author changes models between phases. Review
coverage must satisfy the existing harness acceptance and evidence contract.

### Failure handling

- Local implementation defect: return the failed check and affected scope to
  the worker for one focused correction. Persistent or complex defects go to Sol.
- Requirement or architecture contradiction: return the evidence and affected
  decision to Astra, update the brief, then rerun affected work and checks.
- Authentication, network, missing tool or permission failure: reconcile the
  environment or record a blocker. A stronger model does not repair credentials.
- Keep the existing maximum of three repair cycles per task across all models.
  A handoff does not reset this limit. Stop with an explicit unresolved condition
  when the limit or another real blocker prevents completion.

### Dispatch and accounting boundary

Use only a host-supported model-selection mechanism, such as an authorized Codex
execution with an explicit model or an available native agent tool. Verify exact
model IDs, allowed reasoning effort, tool access and current authorization first.
Availability may differ between the desktop app, CLI, native subagents and Work.
For the user's explicit or standing Luna Max request, prefer a native subagent
for internal execution. Supply the handoff contract in `message` and set
`model="gpt-6-luna"`, `reasoning_effort="max"`, and `fork_context=false` when
supported. Omitting `model` inherits the lead model and is not Luna execution.
An internal worker does not require switching the lead, changing global settings,
or creating a new user-owned Work task.

A discovery list that omits Luna is insufficient evidence of unavailability.
When the tool permits an explicit user-requested model string, dispatch one
useful bounded task and inspect its returned result or error. Respect an explicit
tool restriction or a schema that rejects that selection; do not bypass it.
An unrestricted string field alone does not authorize overriding an explicit
model allowlist. Distinguish a discovery omission from a stated prohibition;
a completed run with runtime model metadata is evidence for that same host and
dispatch mechanism, not for other surfaces.
A returned agent ID proves creation only: check completion, the actual artifact
and runtime model metadata when exposed. Record requested and observed model
separately; unavailable metadata leaves the observed model unknown.
A terminal run without a usable result is incomplete. Record its status/error
and inspect existing outputs before any justified retry; do not automatically
dispatch a duplicate worker.

If the dispatch is prohibited or returns a concrete model, access or quota failure,
record that restriction/error and disclose the unavailable route.
The lead may continue authorized work directly and record the fallback; do not
silently delegate to another model or label that work as Luna execution. A model
listed in another surface is not proof it can be selected by this dispatch tool.
For review roles, report unavailable preferences and use a permitted independent
reviewer. A lead's final acceptance does not replace independent review.

This policy does not change global model settings, create scheduled jobs, enable
new billing routes, forward credentials, or authorize external publication. A
ChatGPT subscription-backed session and a metered API session are distinct routes;
record the actual route and leave pricing/usage unknown when not exposed.

Save a compact routing record in the task's private evidence directory: requested
and observed model, phase, selection reason, actual run/agent ID, brief version,
artifact and check references, retries, elapsed time, and usage when available.
The ledger remains responsible for its existing artifact/check/review/publication
records; this policy adds no new ledger fields. Judge efficiency by total time,
usage, rework and acceptance success, not token price alone. Independent review
and a successful mixed-model run are separate claims from a performance benchmark.

### Representative acceptance cases

1. New blockchain integration: Astra defines units, state transitions and checks;
   Luna implements a bounded part; Sol independently reviews consequential logic.
2. Existing weekly report with unchanged inputs and rules: Luna executes the
   established brief; deterministic checks and proportionate independent review
   verify it. No new Astra design phase solely because a schedule fired.
3. Small document formatting task: use the existing template and mechanical checks;
   skip harness-run entirely if the request is trivial.
4. A persistent implementation test failure: one focused worker correction, then
   Sol for the affected implementation; preserve the task's total repair count.
5. Conflicting requirements or an unsafe architectural assumption: return to Astra;
   do not ask Luna to invent a new design to make a test pass.
6. Login or network failure: report/reconcile the environment, without model escalation.
7. Luna absent from a discovery list but accepted by the native tool: dispatch the
   bounded task with an explicit Luna Max override and inspect completion; do not
   substitute an inherited worker solely because the list omitted Luna.
8. Native dispatch rejects or prohibits Luna: record the exact restriction/error,
   disclose the gap and keep permitted work with the lead; do not claim Luna
   execution or bypass host restrictions with another provider.

### Maintenance and evidence

Keep skill instructions, model-routing policy, change history and evaluation
records in English. Task deliverables and user-facing explanations follow the
requested language. Model names and platform mechanisms require periodic checks;
this policy's recommendations are not a permanent capability ranking.

Source of the phase preference: the user's design-first proposal in this task.
Platform references: [Models](https://learn.chatgpt.com/docs/models) and
[Advanced configuration](https://learn.chatgpt.com/docs/config-file/config-advanced).
These document model selection and configuration, not the effectiveness of this
particular workflow. Change recorded: 2026-09-22, initial design-first policy;
2026-09-25, adopted upper-model lead and Luna Max execution at the user's request,
informed by [Baton](https://github.com/w00ing/skills/blob/4acf4c45cab7876fa63e4f8ae046bc95abf6bbc6/baton/SKILL.md).
2026-09-27, made native subagent dispatch and failure evidence explicit after a
run substituted inherited Sol workers without attempting the requested Luna route.
Comparative efficiency benchmarks remain untested by this documentation update.

## UI reference selection

For UI work needing a visual direction, use [Dribbble](https://dribbble.com/) to
find relevant dashboard, landing-page, mobile-app or portfolio examples. Start
with the audience and task, select a few examples, and save each source URL,
author and useful pattern in the task's Notion record. Explain which patterns
fit the actual content before implementing an original design. Treat imagery as
reference, not automatically reusable assets. Verify accessibility, responsive
behavior and loading/error states in the implementation; a shot proves none of
these. Use the relevant specialist skill rather than a new generic UI wrapper.

## Visual artifact routing and review

Choose the editing surface before drawing. Use the smallest available specialist
workflow that can deliver the requested format; check its tools and account access
in the current host. A supplied style guide or third-party skill is a reference
unless the user asks to adopt it. Preserve a requested template or brand system.

| Requested output | Route |
| --- | --- |
| New PowerPoint or Google Slides deck | Use **Presentations** when available; it routes a new Google deck and requires rendered slide inspection. |
| HTML presentation or visual style study | Use **Frontend Slides** when installed for real-content style previews and browser delivery. Route native PowerPoint and Google Slides authoring through their format-specific skills. |
| Edit an existing PowerPoint deck | Use **Presentations** to inspect and preserve the supplied deck's design and editable content. |
| Edit or follow an existing native Google Slides deck | Use **Google Slides** when available and connected to inspect the source deck, preserve its design system and read back the result. |
| Simple flow, sequence or structure diagram | Use Mermaid source plus SVG or PNG when the diagram syntax can express the relationships clearly. Keep the source editable and inspect the export. |
| Excalidraw-style or freely arranged editable diagram | Deliver the native `.excalidraw` scene and a rendered preview when Excalidraw is the requested editor. Verify any chosen local editor or renderer first; do not install an MCP server or run a pasted setup script solely because a reference mentions it. |
| Quantitative chart | Use the available data-visualization skill and source data, retaining labels, units and an editable chart or source where the destination supports it. |

For each slide or diagram, identify its audience and the one point it must convey.
When visual quality is central, inspect the user's references or a few relevant
examples before production. Extract concrete decisions about typography, palette,
spacing, image treatment and composition; use the examples as direction rather
than copying their content or applying a supplied third-party skill as instructions.
If the visual direction is unsettled, make a small set of distinct previews using
the real content and compare them at viewing size before building the full deck.
If a reference already settles the direction, proceed without an extra approval
gate. Avoid making every slide the same card grid or shrinking text to fit a
fixed layout.
Make hierarchy visible through clear titles, readable type, alignment, spacing and
a restrained color system with consistent meaning. Favor fewer labels and shorter
paths over shrinking text. Preserve factual content, language, units, citations
and explicitly requested native editability. A deck and its diagram may need
different tools; do not flatten editable evidence into a screenshot for convenience.

For a scientific or engineering manuscript, use **Manuscript Writing Review**
when available for prose clarity and terminology consistency after checking
the paper's argument and evidence separately. It does not review methods,
results or citation formatting.

Render **every final slide** and each diagram, then inspect the actual output at
its intended viewing size. Check text overflow and Korean glyphs, contrast,
cropping, aligned rows and columns, arrow direction, arrow-label placement and
crossings. Correct visible defects and inspect the new render. Read back the
editable source and export before delivery. A successful file write or render
command is not a visual review. Keep source and preview together when both are
requested or needed for reuse.

This routing draws on the current Presentations and Google Slides skills and
the reference-first, preview-choice workflows in
[Frontend Slides](https://github.com/zarazhangrui/frontend-slides) and
[Slides](https://github.com/jameshemson/slides), plus
the upstream [Mermaid CLI](https://github.com/mermaid-js/mermaid-cli) and
[Excalidraw export utilities](https://github.com/excalidraw/excalidraw/blob/master/packages/utils/README.md).
Community Excalidraw MCP projects such as
[mcp_excalidraw](https://github.com/yctimlin/mcp_excalidraw) are optional tool
candidates, not a default dependency. Connect Figma, Canva or another design
service only when its native workspace materially helps the requested output and
its account is available; plugin discovery alone does not establish connection.

## Start, inspect, resume

Resolve the runner once, using its real release path for the life of the task:

```sh
runner=$(python3 -c 'from pathlib import Path; print((Path.home()/".agents/skills/harness-run/scripts/run.py").resolve())')
python3 "$runner" --project /absolute/workspace doctor
python3 "$runner" --project /absolute/workspace list
```

`doctor` validates installed file hashes and reports the runtime/database paths.
It creates no project state. `start` creates private `.harness/tasks.sqlite` in
the selected workspace. All calls take a JSON object on stdin except `doctor`
and `list`. Substitute the host's actual coordinator ID, never a fabricated
reviewer identity, in real execution:

```sh
python3 "$runner" --project /absolute/workspace start <<'JSON'
{"task_id":"meeting-summary","owner":"ACTUAL_COORDINATOR_ID","kind":"doc","description":"Summarize the supplied meeting notes","acceptance":["Every action has its recorded owner and deadline; missing values stay unassigned","Durable result saved and verified in the personal Harness hub"],"authorization_scope":["Read notes.md; write summary.md and private evidence; save the relevant result in the personal Harness Notion hub"],"publication_required":false,"skill_paths":[],"closeout":{"mode":"managed","github_paths":[]}}
JSON

python3 "$runner" --project /absolute/workspace status <<'JSON'
{"task_id":"meeting-summary"}
JSON
```

`skill_paths` optionally names additional real specialist `SKILL.md` files. The
harness is included automatically. Local pins store actual bytes and SHA256 with
`source: local`; this is honest local provenance, not a claim of GitHub origin.
Existing immutable GitHub pins are still accepted by `route`. Skills are frozen
per task; use `context` with the current owner to read their saved text. The
optional `sync_skills.py` in the source checkout verifies historical GitHub pins;
it is not a prerequisite for every task.

For ordinary execution, the coordinator calls `artifact` with a primary file and
real worker ID, runs a relevant check and saves output, calls `check`, obtains a
separate agent's review and calls `review`, records required `closeout` receipts,
then calls `complete`. `review` must cover
all zero-based acceptance indices. File/evidence paths may be project-relative;
the runner resolves them against `--project` and rejects escapes and symlinks. Skill input
paths may be outside the project. Ledger internals still require canonical paths.

The complete command/field contract is in:

```sh
python3 "$runner" --help
```

`list` returns compact task IDs, owners, stages and next actions. Always inspect
`status` before repeating work. To transfer ownership, confirm the old worker has
stopped, then `pause` under its current owner and `resume` under the new actual
coordinator ID. These commands require only `task_id` and `owner`. A ledger pause
does not interrupt native agents. Retain the prior output's absolute `runtime`
path when resuming after an installation upgrade. A stopped host does not keep
this workflow running.

`list` checks whether tracked source files are still current. A historical Run
that was saved Done may display `repair-required` after later edits to those
sources. Inspect its saved completion and remote receipts before treating it as
unfinished work; a new revision belongs in a new task. The Stop reminder excludes
stored completed Runs rather than reopening them on later source changes.

One task tracks one primary artifact file. Split independently mutable outputs
into separate tasks. A hash of a manifest alone does not monitor its children.
Changing artifacts or check/review evidence invalidates completion; use `repair`,
record the changed artifact, then rerun checks and review (at most three repairs).
A frozen skill body remains the task's instruction snapshot even if its source
file changes later. Source updates belong in a new task.

Exit 0 means a non-blocked transition, 1 a recorded blocker, and 2 rejected input
or transition. Only a current `stage: done` proves recorded completion.

## Publication and permissions

New runner tasks default to `closeout: {"mode":"library","source_paths":[]}`.
Declare changed code, skill and hook paths in `source_paths`; checks and review
bind these bytes without requiring remote publication. A source change requires
repair and renewed verification. Work completion and Notion record approval are
separate. Use the work-records skill and its approval hook for that record.
While a tracked task remains active in the same session, its tool gate also
requires a prepared exact Notion call. Both admissions are required; neither
approval bypasses the other. After task completion, the record gate remains.
When GitHub delivery is requested, use a separate `github` task with
`github_paths` for the exact reviewed files. Its closeout requires an immutable
remote commit and byte-matched file readbacks, without requiring a Notion write.
Keep the personal Linear issue as the work map; add a cross-linked GitHub issue
only for a distinct actionable repository problem. Link the resulting commit
and PR after separate remote fetches. PR merge remains a separate decision.

Explicit `managed` delivery is retained for historical or separately requested
contracts. Notion is required in that mode. Declare every intended changed
skill, hook and harness file in `github_paths` when GitHub delivery is required.
Managed code tasks must declare a nonempty file list or use an applicable
reasoned scope exception. The declaration is frozen; the reviewer compares it
with the actual managed diff. Checks and review bind the declared source bytes;
changing them requires repair, new checks and independent review before delivery.
This is not an automatic detector of omitted files or semantic scope.

Use `{"mode":"local-only","reason":"..."}` or
`{"mode":"read-only","reason":"..."}` only for an explicit request with that
scope. An outage is not an exemption. Existing older tasks retain their original
policy. `publication_required` still controls the primary-artifact outbox below;
false does not waive an explicit managed closeout requirement. The 2026-09-28
draft-first policy supersedes older standing personal Notion-write permission.
Reviewed personal repository synchronization retains its existing scope.

For an approved record, after review and the real Notion write/fetch, keep a simple intended summary and
the independently fetched body as separate files. For example:

```json
{"task_id":"meeting-summary","owner":"ACTUAL_COORDINATOR_ID","service":"notion","target":"https://www.notion.so/ACTUAL_PAGE_ID","summary_path":"summary.md","readback_path":".harness/meeting-summary/notion-body.md","receipt_ref":"actual fetch response path and retrieval time"}
```

Pass that JSON to `closeout`. The primary artifact can be a code file while the
Notion summary explains its result. The host separately checks page identity,
parent, Task ID, properties and links. Preserve raw fetch metadata privately.
The comparison tolerates empty-line differences in plain summaries, preserving
content-bearing lines; code/math bodies use stricter comparison.

For a GitHub requirement, commit only reviewed authorized files, push normally,
then fetch every declared path at the actual immutable remote commit. Pass:

```json
{"task_id":"harness-change","owner":"ACTUAL_COORDINATOR_ID","service":"github","repository":"maengseojun/agent-harness","commit":"ACTUAL_40_CHARACTER_COMMIT_SHA","files":[{"path":"harness/entry_hook.py","readback_path":".harness/harness-change/remote-entry-hook.py"}],"receipt_ref":"actual remote commit/file fetch evidence"}
```

The file set must match the frozen `github_paths`, and every local/remote pair
must match byte for byte. Missing evidence leaves `awaiting-closeout`; `complete`
rejects it. Later changes to the artifact, summary, readback or declared local
source invalidate the relevant receipt. Retrying a verified delivery updates its
receipt; the host must reuse the existing remote page/task identity.

These are cooperative local checks. The host supplies authenticated remote
evidence; the runner does not inspect credentials, poll remote services, prove
that a fetch was authentic, or push automatically. CI runs the focused harness
suite and fresh installation check on GitHub. CI alone does not force a push or
activate branch protection. The optional local Stop hook requests one recovery
pass for unfinished managed tasks in the current project/session, then reports
unresolved work; it cannot turn a missing receipt into Done.

For publication, prepare an intent with `enqueue`, bind authorization with
`approve`, and call `publish`. Local publication never replaces conflicting
content and reconciles matching files after interruption. Remote `publish` only
records reconciliation-required; a connector performs the authorized write and
readback before the coordinator calls `receipt`. On timeout, inspect the saved
target/marker before retrying. A missing approval leaves a reviewable draft.

Native tool permissions and the coordinator enforce the full write scope. The
ledger trusts the coordinator's reported agent IDs, executed checks and consent;
it does not authenticate identities, attest execution, or sandbox other tools.
It provides local cooperative-client guarantees on a POSIX filesystem. No claim
of remote exactly-once writes or protection from subsequent remote edits is made.
Keep the SQLite database and journal together. A crash before cleanup may leave
`.ledger-*` staging files, which are not additional publications.

## Development checks and prior evidence

From the source repository:

```sh
python3 -m unittest discover -s harness -p 'test_*.py'
python3 harness/sync_skills.py --check
```

The historical document/code pilots remain in `.harness/pilots.sqlite` and can be
read with `python3 harness/ledger.py --db /absolute/path/.harness/pilots.sqlite status`.
They are separate from each target project's new `.harness/tasks.sqlite`.
The previously published v1 is in the private repository
[maengseojun/agent-harness](https://github.com/maengseojun/agent-harness).
Local edits are not published merely by installing them. Existing Endix policy
was not verified; no team automation, schedule, merge or deployment is enabled.

## Four runtime hooks

The existing four lifecycle gates now have an optional native event bridge:
`PreToolUse` runs write/delegation checks, `PostToolUse` records write responses,
actual fetch readback and final native agent results, and `Stop` checks completion.
`SubagentStop` requests final confirmation because another hook may continue the
agent; it does not alone certify termination. No phase classifier or new model
call is needed. Existing entry and managed closeout handlers are preserved.

Install the reviewed package, then explicitly register its frozen handler:
`python3 -B harness/install_tool_hooks.py --release <absolute-installed-release> --module all`.
This switches the tool and work-record launchers to the same frozen release in
one configuration update; compare both registered paths before claiming sync.
The installer preserves unrelated config and old releases and backs up hooks.json.
New definitions still require Codex's hook trust review; registration and synthetic
wire tests do not prove desktop dispatch. Never manufacture trusted_hash entries.

Use the actual Codex session ID (`CODEX_THREAD_ID`) as the coordinator owner.
The runner CLI automatically indexes `start`/`resume` projects for that session,
including managed worktrees outside the session cwd. Hooks check live ownership,
not just cached task IDs. Historical tasks without the creation marker keep their
contract; ordinary untracked tools and other sessions are unaffected.

Before an intended action, freeze its exact input once with `prepare-tool`:
`call_id`, `kind` (`write`, `delegate`, `readback`), `tool_name`, `input_path`
(a JSON object containing actual tool arguments), and `gate`. This is an action
plan, not a successful check or permission grant. The actual native event runs
the gate atomically; omitting the plan denies protected calls. Arguments and the
planned file must still match. Do not manually run before/after gates for a call
already managed by the bridge. Existing direct runner gates remain available
for hosts without native event support.

- Write `gate`: existing `before-write` fields, including exact payload/hash.
  For PR creation, also supply `expected_head_sha` at the top level from the
  reviewed remote delivery commit; readback must confirm that exact PR head.
  Add `purpose: "working-context"` only for authorized personal Linear issue
  drafts and progress. This checks destination, input and actual readback before
  a final artifact exists. Delivery writes retain the check/review prerequisite.
  The bridge records any write response as uncertain, never as proof of storage.
- Delegate `gate`: existing `before-delegate` fields. The pre-hook injects the
  returned frozen contract into `message` or text `items` with `updatedInput`.
  The actual created agent ID and final `wait_agent` result are recorded.
- Readback `gate`: only `write_call_id`. The provider adapter binds the fetch
  tool, account and resource to the actual write and compares returned fields
  with the reviewed canonical JSON payload. Caller-selected projections and
  local echoed JSON are not storage evidence.

```json
{"task_id":"TASK","owner":"ACTUAL_CODEX_SESSION_ID","call_id":"fetch-run","kind":"readback","tool_name":"mcp__codex_apps__notion_fetch","input_path":"evidence/fetch-input.json","gate":{"write_call_id":"save-run"}}
```

Supported writes use the exact `mcp__codex_apps__` provider names: Notion single
page creation, full content replacement and property updates; Linear issue
creation/update; GitHub issue creation/update, file creation/update and PR creation.
PR creation uses explicit base/head branches, title, body and draft state; fetch
the actual created PR number to verify the branch and content. `gh pr create`
remains unsupported for tracked runs; use the typed GitHub connector. Unsupported
fields or operations are denied. Native `mcp__linear__save_issue/get_issue` and
`mcp__linear_endix__save_issue/get_issue` are also supported. Before native writes,
fetch `get_workspace` through the same connector: its actual PostToolUse result
binds the workspace to the frozen destination. Wrong workspace/connector owner
or failed identity reads deny writes. Native tools do not take `link_id`; legacy
Codex Apps Linear still requires it to equal the authorized workspace/account.
Fetch referenced issues first when using UUIDs so returned identifier aliases
can be compared. Personal working-context permission never grants Endix writes.
Issue project/parent/blockedBy/blocks/relatedTo/links/labels are supported;
fetch with `includeRelations:true` for relation writes. Additive relations/links
must contain every requested item; existing unrelated items are preserved.
Use complete supported values rather than an unverified description patch.
Notion creation supports exactly one explicit page or data-source parent; actual
fetch ancestry is checked against that parent. Notion content uses the existing plain-summary normalization;
other requested fields use canonical JSON. Full native Notion fetch envelopes
supply body/properties and parent identity; truncated/unknown-block results fail.
Each create should include a stable task marker. Plan its fetch after the write
returns the actual created ID; an unavailable ID requires explicit reconciliation
instead of certifying an unrelated matching record. GitHub file identity is fixed
by its repository/branch/path.

Direct GitHub pushes require `git push REMOTE SOURCE:BRANCH`, an explicit working
directory (or `git -C`), a GitHub remote and no force flags. Authorize the exact
API ref URL (`https://api.github.com/repos/OWNER/REPO/git/refs/heads/BRANCH`) with
payload `{"commit":"LOCAL_COMMIT_SHA","ref":"refs/heads/BRANCH"}`. Read back with
plain `gh api repos/OWNER/REPO/git/ref/heads/BRANCH`. All shell arguments, including
working directory, remain part of the frozen input. Other mutating `gh` commands
are intercepted but require a supported typed connector instead. Actual raw
provider responses are retained privately, separate from normalized readback.

The bridge observes named Linear/GitHub/Notion MCP writes, native `spawn_agent`,
and direct `git push`/mutating `gh` calls. Indirect shell scripts, hosted search,
UI actions and tool paths bypassing native hooks are outside that coverage; use
the existing explicit runner gates for these host limitations. This is not an OS sandbox,
service-account authenticator or complete permission boundary. It binds actual
calls to coordinator-supplied, authorized destinations and reviewed versions.
Unknown write outcomes block retries; reliable absence can be supplied through
the existing reconciliation gate before another admitted attempt. A fresh fetch
showing drift after verification records a blocker rather than weakening receipts.

New tasks start in `configuring` with next action `configure-hooks`; recording
an artifact or completing is rejected until the policy is frozen. Call
`configure-hooks` after `start` and before recording an artifact. This freezes
the output owner, exact authorized destinations, worker write paths and mandatory requirements. Empty arrays explicitly mean
no planned service writes, worker writes or extra requirements. Historical tasks
created before mandatory configuration (without the creation marker) keep their original completion contract; do not retroactively
change an active task's requirements. No reference grants new authorization.

```json
{"task_id":"TASK","owner":"COORDINATOR","output_owner":"personal","destinations":[{"id":"run-page","service":"notion","workspace":"VERIFIED_WORKSPACE_ID","target":"EXACT_RESOURCE_URL","output_owner":"personal","operations":["update"],"authorization_ref":"EXISTING_USER_AUTHORIZATION"}],"write_paths":["output"],"requirements":[{"id":"installation","kind":"evidence","target":"source/install hashes and installed doctor"},{"id":"appendix","kind":"child","target":"APPENDIX_TASK_ID"}]}
```

Paths are project-relative through `run.py`; the lower-level ledger requires
canonical absolute paths. Worker scopes cannot escape the selected project or
use symlinks. A mixed run lists bounded personal and team destinations separately;
team writes still need their live team entry and actual permission. Prefer separate
runs where destinations or outputs change independently.

### Before external writes

For deliveries, after current checks and independent review, prepare a payload file representing
all intended content and properties. For GitHub, use a canonical manifest of the
exact revision/files and their hashes. Call `before-write` with a stable
`operation_id`, destination ID, observed workspace and target, operation, payload
path/hash and the same authorization reference frozen in the policy. Save the
returned attempt number before calling the connector. Its `hook.should_write`
is false for an already verified operation: skip the write. Pending, uncertain
or conflicting attempts deny another write. A second ID cannot bypass an
identical binding. Destination comparison is exact, not URL-prefix guessing.

Personal Linear working context uses the same exact-input, authorized-destination
and readback path, with `purpose:"working-context"`. It needs no final artifact or
review and its verified receipts remain valid when a later artifact is recorded.
Pending/uncertain progress writes still require reconciliation before completion.
Notion, GitHub and team deliveries cannot use this purpose to bypass review.

This hook binds a reviewed work version and durable intent before the side effect.
It checks coordinator-supplied destination facts; it cannot validate an account
or decode every service's payload. A create operation must use the canonical
parent/collection as its target and include the stable Task ID/marker in the
payload. The host separately checks the newly created resource's parent and ID.

### After writes and before retries

Call `after-write` with the matching operation ID/attempt, workspace and target,
`evidence_path`, and `outcome`: `verified`, `absent`, `uncertain` or `conflict`.
Only `verified` accepts `readback_path`, which must be a separate file whose bytes
match the intended payload. Normalize actual fetched content/properties to the
same canonical representation; preserve the raw fetch privately as evidence.
Do not copy the intended payload and label it fetched evidence.

An `absent` result needs a real reliable lookup proving no result for that intent;
only then can the same operation prepare another attempt. A timeout, missing
access, partial result or multiple matching records is not absence. Inspect the
known target/Task ID/marker before recording a result. Uncertain/conflicting
writes prevent completion. A delayed valid receipt can reconcile an older version.
A repair supersedes verified or confirmed-absent old-version intents while
preserving their resolution and history; it never discards pending or uncertain
writes. Confirmed absence after repair also terminates that historical intent;
prepare a new operation ID for the new version when a write is still required.

### Before delegation

Call `before-delegate` with a stable delegation ID, role, bounded description,
acceptance conditions, source references and allowed write paths. Forward the
returned `hook.contract` to the native worker together with actual request/source
context. It contains the frozen skill text, output owner, parent task, authority
scope, actual artifact and check evidence. Active worker write scopes must not
overlap. Reviewers have no write paths and need current checks; the coordinator
saves their returned evidence. Do not dispatch a second agent for an already
running delegation just because the preparation was repeated.

After the real result, call `after-delegate` with the actual agent ID, outcome
`finished` or `blocked`, and saved evidence. The ledger rejects owners as delegates
and authors as reviewers; a later worker registration invalidates that agent's
review. A blocked result can be recovered with a real finished result. Finished
receipts are immutable. All registered delegations are required; leave optional
follow-ups outside this run. These ID checks do not authenticate native agents.

### Before completion

`complete` automatically checks every frozen requirement and registered write or
delegation. For an `evidence` requirement, call `requirement` with a current file
and an actual independent verifier ID after review. Evidence binds the reviewed
artifact and declared source hashes, so repair requires renewed verification.
A target is a human-readable condition, not an automatic installer or file check.
The verifier must inspect that condition and put its result in the evidence.

A `child` requirement names a task in this project's ledger. Completion checks
its live effective state, not merely a supplied Done label; missing, blocked,
paused or stale children prevent Done. Cycles fail closed. Dependency inspection
is bounded to 16 levels; split deeper workflows rather than assuming success.
Missing runtime evidence is reported as a blocker and can be restored/resolved.
Historical completed runs are not re-opened by the global Stop reminder.

Focused regression command from the repository root:
`python3 -B -m unittest discover -s harness -p 'test_runtime_hooks.py'`.
