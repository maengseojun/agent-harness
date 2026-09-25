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

## Notion workspace

Use the standalone [Harness hub](https://www.notion.so/3e3e203190cd8143bdf5df0b46c1cb57)
as the durable source of truth for personal managed work. Linear holds the
short-term queue; Notion preserves decisions, results and recovery context.
See [workspace destinations and capture contract](NOTION-WORKSPACE.md).
New personal runs require a Notion closeout receipt before Done. The host agent
performs the authorized connector write and readback; the runner validates saved
evidence. No background synchronization service is installed.

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

Status: user-adopted upper-model lead / Luna Max policy, updated on 2026-09-25.
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
If Luna Max is unavailable in the active dispatch tool, disclose that limitation.
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
7. Luna absent from the selected host: disclose the capability gap, keep permitted
   work with the lead and record the fallback; do not claim Luna execution or
   bypass host restrictions with another provider.

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
Mixed-model execution and comparative efficiency benchmarks remain untested by
this documentation update.

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
| Edit an existing PowerPoint deck | Use **Presentations** to inspect and preserve the supplied deck's design and editable content. |
| Edit or follow an existing native Google Slides deck | Use **Google Slides** when available and connected to inspect the source deck, preserve its design system and read back the result. |
| Simple flow, sequence or structure diagram | Use Mermaid source plus SVG or PNG when the diagram syntax can express the relationships clearly. Keep the source editable and inspect the export. |
| Excalidraw-style or freely arranged editable diagram | Deliver the native `.excalidraw` scene and a rendered preview when Excalidraw is the requested editor. Verify any chosen local editor or renderer first; do not install an MCP server or run a pasted setup script solely because a reference mentions it. |
| Quantitative chart | Use the available data-visualization skill and source data, retaining labels, units and an editable chart or source where the destination supports it. |

For each slide or diagram, identify its audience and the one point it must convey.
Make hierarchy visible through clear titles, readable type, alignment, spacing and
a restrained color system with consistent meaning. Favor fewer labels and shorter
paths over shrinking text. Preserve factual content, language, units, citations
and explicitly requested native editability. A deck and its diagram may need
different tools; do not flatten editable evidence into a screenshot for convenience.

Render **every final slide** and each diagram, then inspect the actual output at
its intended viewing size. Check text overflow and Korean glyphs, contrast,
cropping, aligned rows and columns, arrow direction, arrow-label placement and
crossings. Correct visible defects and inspect the new render. Read back the
editable source and export before delivery. A successful file write or render
command is not a visual review. Keep source and preview together when both are
requested or needed for reuse.

This routing draws on the current Presentations and Google Slides skills and
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

One task tracks one primary artifact file. Split independently mutable outputs
into separate tasks. A hash of a manifest alone does not monitor its children.
Changing artifacts or check/review evidence invalidates completion; use `repair`,
record the changed artifact, then rerun checks and review (at most three repairs).
A frozen skill body remains the task's instruction snapshot even if its source
file changes later. Source updates belong in a new task.

Exit 0 means a non-blocked transition, 1 a recorded blocker, and 2 rejected input
or transition. Only a current `stage: done` proves recorded completion.

## Publication and permissions

New runner tasks default to `closeout: {"mode":"managed","github_paths":[]}`.
Notion is required for this personal managed mode. Declare every intended changed
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
false does not waive the managed closeout requirement. Existing user authorization
for the personal hub and reviewed personal repository changes is sufficient.
Do not ask for the same permission twice or extend it to unrelated destinations.

After review and the real Notion write/fetch, keep a simple intended summary and
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
