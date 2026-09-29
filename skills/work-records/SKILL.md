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

## While working

For substantive work, search and reuse the existing personal project/issue.
Keep its goal, completion criteria, child tasks, dependencies, related work,
decisions and rationale, conversation/source links, artifacts and next action
current. Use real relations when supported. Break down independently actionable
work; do not create an issue per sentence or duplicate the conversation verbatim.
Read back updates. Ordinary explanations and trivial edits need no new issue.
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

At Stop, the local reminder inspects actual session-bound tasks, including
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
