---
name: work-records
description: Manage personal work in Linear and propose finished outcomes for a user-approved Notion record, then review and refine the saved writing. Use for substantive tasks and completed or concluded experiments.
---

# Work records

## Roles and authority

Linear is the brain / memo / draft: goals, full task maps, dependencies, ideas,
decisions, working drafts, progress and source links belong there. Personal
Notion is the library / papers / books: concluded work and its story belong
there after the user approves a concrete draft. GitHub was an analogy, not a
mandatory platform or finish criterion. This policy supersedes older automatic
personal Notion closeout permission. Skill storage is a separate concern.

Use personal Linear for personal work and private Endix development; do not
infer team write permission from that freedom. Verify the connection and target
before writes. Endix workspace Notion needs separate explicit approval for the
exact content and destination, after official adoption or overall completion.
Do not transfer unrelated confidential team material into a personal workspace.

## Project/task workflow

This is the canonical document contract for task-brief, execute-code-brief and
prepare-work-deliverable. Reuse existing Linear documents, relations and working
records; this contract does not introduce a database, bot, runtime or lock system,
or prove that hooks enforce it.

- For a project, use relevant interviews and source research to agree Architecture,
  then Environment & Rules, then decompose and assign Tasks with each task's
  separate Spec/Plan. Preserve the overall goal and decision context. Architecture
  is the top entry: goal and success criteria, structure and responsibilities,
  decision reasons, open questions, and Rules/Tasks links. Each task links to its
  relevant Architecture section; navigation is not a native issue-parent claim.
- After assignment, the lead reads the task/Spec/Plan and relevant Architecture/Rules
  and identifies concrete blockers: conditions preventing accurate execution,
  such as missing required facts, domain knowledge, tacit conventions or inputs.
  Record a blocker only when its impact on execution is concrete; not every open
  research question is a blocker. Use one blocker identity for one underlying
  condition, list every affected task, and define its resolution boundary, owner,
  exit criteria and required evidence. Independent causes remain separate.
  If resolution needs independent work, create a blocker-resolution task with its
  own separate Spec/Plan, Owns, lead and permitted scope; link it as blocking all
  affected tasks. Do not duplicate resolution work per consumer. Small reads stay
  in the consuming Plan; ready tasks proceed without a blocker or extra task.
  Read actual resolution evidence before unblocking affected work; issue Done
  alone, a proposed role or a readiness report is not proof of resolution.
  Within agreed Architecture/Rules, incorporate task-specific knowledge in the
  consuming Spec/Plan. A finding changing upper decisions or scope returns to the
  affected decision before execution; resolution cannot silently authorize it.
  No universal stage before task decomposition or recursive planning-for-planning.
  Task-map design and document binding are ordinary coordination work, not blockers
  merely because they precede execution. Preparation is not deployment proof.
- Each task links separate Spec and Plan documents. Keep Spec focused on goal,
  source criteria, Owns/change boundaries, numbered requirements, Acceptance,
  exclusions and unresolved inputs. Plan covers readiness/dependencies, actual
  environment, steps, checks, failure/change handling and review focus. Map every
  requirement to its responsible task and Acceptance check/evidence; missing
  ownership or verification means not ready. Standalone short/mid tasks retain
  their own Spec/Plan and acceptance without unnecessary Architecture or project
  hierarchy. Scale detail to the task; trivial edits need no document scaffolding.
- Distinguish document status `draft`, `current` and `superseded`. Record each
  source's stable document ID/link, fetched `updatedAt` and user approval reference
  in its header/index and the execution record. `current` identifies the agreed
  applicable revision; a draft is not an execution criterion and a superseded
  revision points to its replacement. Document agreement and execute authorization
  are separate: record the user's requested task and permitted execution scope.
  A title, date, approval for an older revision or task-list snippet is insufficient.
- Before execution or resumption, read task current state → linked Spec/Plan →
  relevant Architecture/Rules → dependency results. Check revision/approval,
  readiness, actual inputs and Owns against the requested scope. Resolve conflicting
  or stale criteria before affected work. Keep the task's current body useful:
  goal, phase/progress, decision reason, blocker, next action, source links and
  artifacts/check results. Reflect settled decisions in the canonical documents,
  not only comments; preserve meaningful previous decisions and their references.
- A slight Plan change, such as order or file selection within Owns, may proceed
  when goal, architecture, scope, constraints and Acceptance remain unchanged.
  Update the current Plan and log previous/new approach, reason, impact and decision
  basis. Substantive changes to those criteria require re-interview and agreement
  before affected execution; a Plan adjustment cannot widen an exclusive boundary.
- One task has one active lead/chat. Handoff retains the same task ID and records
  outgoing/incoming lead, applied source IDs/revisions/approvals, progress, artifacts,
  checks, blockers and next action before the new lead continues. Different tasks
  may run in parallel only after comparing Owns/dependencies; overlapping files or
  documents require sequencing or explicit handoff. Do not assume a technical lock.
- On connection failure, attempt safe read/reconnection first. Offline execution
  may use only previously fetched, user-approved criteria and execution scope;
  keep a local pending-sync record and disclose the gap. Do not start a new task
  with unread criteria. Stop affected work if freshness or concurrent changes are
  uncertain. After recovery, verify workspace/target, fetch current sources and
  reconcile local changes and uncertain delivery before retrying or syncing;
  separately read back authorized writes. Never retry an uncertain write blindly.
- After Acceptance and required review, record evidence and limitations and leave
  the task awaiting user confirmation. Only the user confirms Linear Done; tests,
  Stop or a merged PR cannot decide it. Use a verified existing status, not an
  invented workflow state. After conclusion, a Notion record is a separate concrete
  draft/destination approval and readback under the policies below; task execution
  or Done approval does not approve its first save or finalization.

## While working

For substantive personal Work and Codex work on this computer, verify the
personal connection and search/reuse or create the issue before substantial
execution. This includes research, documents, specifications, coursework and
coding, whether or not a Harness ledger is used. Personal working notes already
have authorization; do not ask again just to update Linear.
Keep its goal, completion criteria, child tasks, dependencies, related work,
decisions and rationale, conversation/source links, artifacts and next action
current. Use real relations when supported. Break down independently actionable
work; do not create an issue per sentence or duplicate the conversation verbatim.
Update at meaningful milestones and before the final response; read back updates
and include the canonical issue link in the result. Ordinary explanations and
trivial edits need no new issue. Do not mistake a local ledger for Linear sync.
If access fails, preserve a local draft and report the missing sync.
For coding work, personal Linear remains the working map. Open a GitHub issue
only when the repository has a distinct actionable problem worth tracking there;
search first, then cross-link the canonical Linear and GitHub issues. Add the
reviewed commit and PR links to Linear after actual remote readback. A personal
Notion outcome may reference them after its own approved save and review.

In an active native harness, fetch the same connector's `get_workspace` before
preparing a personal Linear issue write. Its observed response binds the actual
workspace. Use the exact input and `purpose:"working-context"` in its write
gate; drafts and progress do not require a completed artifact. Fetch referenced
issues to resolve UUIDs, and request `includeRelations:true` when reading back
relations. Verify the project/parent/dependencies/related issues and source links.
This exception never authorizes team destinations or Notion delivery writes.

## When work concludes

Judge completion from the actual task purpose, current Linear history,
conversation, artifacts and checks. A completed independent milestone or a
failed/abandoned experiment with a conclusion and learning can be recorded.
An end-of-turn signal, PR status or generated draft alone is not evidence.

At Stop, a bounded reminder also covers tool-using turns without a Harness task.
It asks the host to assess actual personal work, reconcile the Linear update and
readback, and decide whether a concluded result merits a Notion proposal. A
document or specification can be a result without code, a PR or an independent
Harness review. Do not create busywork for trivial turns or repeat a proposal
already presented. The reminder does not write services or prove sync succeeded.
It runs only on hosts delivering the registered hooks; installation alone does
not prove Work/cloud coverage. State the actual unavailable surface when needed.

The existing task-result reminder inspects actual session-bound tasks, including
completed tasks, with current artifact, check and review evidence. It requests
one assessment per distinct task result, even if no draft was registered; it
never completes a task or authorizes publication. Use `action=assess` with
`session_id`, `task_id`, the reminder's `result_sha256`, `assessment_ref`, and
either `candidate_id` for a registered proposal or `deferred_reason` explaining
why no record is proposed. Supply `cwd` when needed to locate the bound ledger.
The action rechecks the actual task evidence and stores that basis with the
candidate/revision or reason. Unchanged assessments and presented/rejected/
deferred proposals stay quiet; changed verified results need a new assessment.
Ordinary untracked answers remain silent.

Prepare a local record draft: purpose, personal contribution, key choices and
reasons, observed outcome, evidence and limitations, learning, related tasks and
sources. Distinguish team results from personal contribution. Select a verified
personal Notion target. Use an existing project overview as the index and
separate linked records for meaningful results; verify reciprocal navigation.
Search by stable task/result identity before create; multiple matches require
reconciliation. Preserve old records and the canonical page across revisions.

Use `~/.codex/skills/harness-run/scripts/work_records.py` to register the
draft and exact intended Notion call. Read its `--help` for the JSON contract.
It stores local decision metadata and hashes; it does not contact services.
Keep original connector responses separately from extracted readback bodies.
Never place credentials in draft/state/evidence files.
Use the actual `CODEX_THREAD_ID` for `session_id` and the harness owner. The
entry receipt argument is a per-turn routing token, not a chat ID. The local
record dispatcher rejects a different session ID when that environment value
is present.

Present the draft or a clickable complete draft plus destination, completion
basis and limits, and ask whether to record it. Mark it presented only after
actually showing it. Rejected/deferred/presented unchanged candidates stay
quiet; changed content or target requires a fresh proposal. An initial save,
new target, substantive rewrite or `Completed` decision needs user approval;
the narrow personal maintenance exception below does not.
Do not infer approval from silence, completion, a standing preference, or an
agent review. Attach the actual user's decision reference when approving.

After approval, call the prepared tool once, fetch the actual page, compare its
body and intended properties/parent/links, then record the saved receipt with
separate readback evidence. A write acknowledgement means uncertain delivery.
Notion content and property changes are separate commands. Do not include
properties in `replace_content` or `update_content` and assume they were saved.
If a historical mixed call applies only its body, record the verified partial
result before proposing a separate exact `update_properties` call. Never claim
the whole rewrite succeeded from its acknowledgement.
On timeout, reconcile the canonical task/page before retry; never create a
duplicate. Only a separate actual readback confirming absence (`saved` with
`outcome=absent`) allows the same exact revision to be considered for another
attempt. Obtain a NEW explicit `user_decision_ref` through `decide`; replaying
any previous approval fails. Endix requires a new separate
`endix_authorization_ref` as well. That approval permits one new attempt with a
new `tool_use_id`; uncertain or saved delivery never permits a retry. Attempt
history is retained; repeated admission of the same current tool ID is
idempotent and old response events cannot alter a later attempt. Fetch new
readback evidence for each attempt. Resume revokes unused approval, including
an approved retry; present again and obtain a fresh explicit decision.
Named direct Notion writes are mechanically approval-gated; shell,
browser, hosted/cloud and indirect tool routes are not a universal sandbox.
Apply this same approval rule on those routes instead of bypassing the hook.
If the same session still has an active tracked Harness task, prepare the exact
Notion call in that task's tool gate as well. The record approval and tracked
task gate must both admit the write. A completed task needs only the record
approval path; do not treat either gate's denial as approval from the other.

## Review and refine

Saved draft, reviewed record and final writing are distinct states. Inspect the
saved record against evidence and incorporate user feedback before rewriting it.
For an already saved personal outcome on its canonical page, factual Outcome
updates and exact replacements of stale time/status sentences may use the user's
2026-09-29 standing maintenance authorization. Fetch the current page, prepare a
complete new draft and exact `update_content` or `update_properties` input, save
that fresh page fetch separately as `maintenance_current_readback_path`, bind its
`evidence_ref` as `maintenance_evidence_ref`, and use `maintenance:true` plus
`authorization_mode:"standing-maintenance"` in `decide` with
`user_decision_ref:"user:2026-09-29:personal-factual-refresh"`. This admits only
one write; fetch body and properties again. Keep the original response and any
transparent Notion-link normalization. Review the new revision against the
evidence and recheck both backlinks. The exception covers `Outcome` and exact
content replacements; nonfinal `Status` values may track remaining work.
The gate limits the edit to short, structurally bounded replacements or a similar
existing Outcome; it cannot judge whether a claim is true. Use source evidence
and human judgment for that. Larger or materially different claims need an
explicit proposal. It does not create a page, change its target or other
properties, retry an uncertain/absent write, or write to Endix. Ask before those
actions. Only the user may approve `Status: Completed` or reopen a
Completed record. A previously user-completed record keeps that decision after
an evidence-checked maintenance revision and renewed link verification.
The first draft's save approval does not authorize a different substantive payload.
Record each saved revision's review with `reviewed`, a verdict (`approved` or
`needs-revision`) and its actual evidence reference. A later rewrite starts as
`saved-draft` again. Work completion in the harness does not mean the Notion
record is reviewed or final.
After approval or standing maintenance admission, update the canonical page and
read it back. Link related
proposal IDs so one task can have an outcome record, index update and later
rewrite without losing history. Linear tracks any remaining review action, while verified work
can finish even if its optional Notion record awaits approval.

For every outcome record, maintain both reverse links after the saved page is
verified: put the canonical Notion URL in the original personal Linear issue's
output/description, and link the record from its personal Notion project index.
Bind that original issue as `output_issue_ref` in the proposal; other related
Linear references do not substitute for its output link.
The record already links back to both. Fetch the issue and index separately and
record `linked` with those readbacks; a write response or a link in the draft
does not suffice. The saved record remains `pending` until both reverse links
are verified. The Stop reminder surfaces this once. The `finalized` transition
requires verified links, an approved review of the current saved revision and
the user's final approval reference. For personal outcomes, the user's
2026-09-29 standing authorization covers adding the canonical result URL to the
original personal Linear issue and its personal Notion project index without
another decision. Prepare the exact index link proposal, use that standing
authorization as its `user_decision_ref`, perform each write once, and read both
destinations back before marking `linked`. This authorization covers only these
two reciprocal links after the outcome record is saved and verified. It does
not cover Endix destinations, unrelated content edits, an uncertain retry, or
finalization. The separate factual-maintenance grant above covers only the
already saved personal outcome page. Maintained policy pages use `record_kind:"policy"`
and do not require outcome backlinks.

For another chat continuing the same task, find its candidate with `status` and
the stable `task_id`, then explicitly `resume` with the prior session identity
and the user's continuation reference. This retains canonical links and uncertain
dispatches and revokes unused approval. Reconcile outstanding writes before a
new proposal. Team publication uses a distinct result key with `related_candidates`
linking the personal record; it does not replace that personal canonical page.

Record approval, rejection and correction references in the local workflow and
Linear as useful evidence for future judgment criteria. Autonomous saving is a
future TODO: propose criteria after enough real examples and obtain user approval
before enabling it. Endix workspace consent remains separate.

## Rich Notion authoring operations

Use `notion-authoring` for page structure, native blocks, captions, databases and
views. Approval governs the exact material and destination, not a ban on those
features. Reuse the user's concrete save approval for the same approved content
and assets after returned IDs/native-markup substitutions; do not ask again for
transport details. A substantive addition or different destination still requires
approval. Never upload via another route to bypass a gate denial.

For file uploads, databases, views, folders and other supported authoring calls,
`work_records.py propose` accepts `record_kind:"operation"`. Supply the existing
fields, an explanatory `draft_path`, exact `tool_name`/`tool_input`, explicit
`notion_target`, and nonempty `expected_state` for independent readback. Uploads
also require `asset_paths:[absolute_path]`, binding the bytes and filename. The
operation target for an upload is its intended destination page; registration
is not permission to attach elsewhere. Repeat propose/presented/decide for each
exact call, referencing the existing user approval within scope. Future or agent
messaging tools are not admitted automatically.

The normal one-attempt rule applies. An upload response/POST is not final page
publication. `saved` operation evidence uses a separate readback file containing
`target`, `evidence_ref`, `resource_url` (actual object/upload ID) and
`observed_state`, which must match the proposed expected state. Keep the original
response. For media, also verify the eventual page attachment/caption by fetch;
for databases/views, verify actual schema/configuration/rows. These are cooperative
coordinator attestations, not authenticated external-state proofs. Unknown or
unreadable results remain uncertain, without a blind retry. Operations are not
outcome records and do not trigger outcome backlink/finalization requirements.

An active native Harness task also needs a supported provider readback adapter.
Currently this covers basic page creation and content/property edits, not rich
operations such as uploads, views or database schema changes. The task gate
rejects unsupported calls before dispatch. Operation approval does not bypass
it; do not change task status or reroute the write to evade that restriction.
