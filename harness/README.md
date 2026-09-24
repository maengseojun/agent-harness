# Personal harness

Use **harness-run** for substantial research, documents, analysis and coding in
any permitted local workspace. The host agent coordinates work, relevant
specialist skills and an independent reviewer. Python's standard library saves
progress and evidence. No new server, paid API, scheduler or background daemon.

## Notion workspace

Use the standalone [Harness hub](https://www.notion.so/3e3e203190cd8143bdf5df0b46c1cb57)
as the durable source of truth for personal managed work. Linear holds the
short-term queue; Notion preserves decisions, results and recovery context.
See [workspace destinations and capture contract](NOTION-WORKSPACE.md).
New personal runs require a Notion closeout receipt before Done. The host agent
performs the authorized connector write and readback; the runner validates saved
evidence. No background synchronization service is installed.

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

Status: user-selected operating policy, recorded on 2026-09-22. The host follows
this policy when its available tools and permissions allow model selection. The
Python ledger does not dispatch models. Its `route` command freezes skills; it is
not a model router. This update does not implement automatic model switching or
establish a measured cost or quality advantage.

### Preferred phase assignments

- Design: GPT-6 Astra (`gpt-6-astra`). Interpret requirements, inspect the existing
  system, resolve material ambiguity, divide work and define acceptance checks.
- Execution: GPT-5.6 Luna (`gpt-5.6-luna`). Execute bounded, well-specified work,
  including collection, transformation, drafting and scoped implementation.
- Routine verification: GPT-5.6 Terra (`gpt-5.6-terra`). Compare artifacts with the
  original requirements, execute relevant checks and investigate simple failures.
- Complex verification: GPT-5.6 Sol (`gpt-5.6-sol`). Review integration behavior,
  assumptions, edge cases and consequential security, permissions or funds logic.
- Design revision: return to Astra when evidence exposes a requirement conflict
  or architectural defect. Do not repeat the entire project for a local defect.

For an unchanged, previously specified routine task, start with Luna and the
existing acceptance checks. A small format conversion does not need four agents.
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
If a requested model is unavailable, report it and use only a permitted fallback;
do not silently relabel an inherited model as Luna, Terra, Sol or Astra.

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
7. Luna absent from the selected host: disclose the capability gap; do not claim
   this preferred route executed or bypass host restrictions with another provider.

### Maintenance and evidence

Keep skill instructions, model-routing policy, change history and evaluation
records in English. Task deliverables and user-facing explanations follow the
requested language. Model names and platform mechanisms require periodic checks;
this policy's recommendations are not a permanent capability ranking.

Source of the phase preference: the user's design-first proposal in this task.
Platform references: [Models](https://learn.chatgpt.com/docs/models) and
[Advanced configuration](https://learn.chatgpt.com/docs/config-file/config-advanced).
These document model selection and configuration, not the effectiveness of this
particular workflow. Change recorded: 2026-09-22, initial design-first policy.
Mixed-model execution and comparative efficiency benchmarks remain untested by
this documentation update.

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
