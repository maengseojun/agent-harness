# Harness Notion workspace

Updated: 2026-09-24 (Asia/Seoul).

The user selected this standalone private Harness page as the durable source of truth for personal managed work. Store requirements, decisions and their reasons, maintained knowledge, accepted results, evidence links and recovery context here. Personal Linear is the short-term queue, not a substitute for these records. GitHub holds executable sources and their exact versions. This standing scope authorizes relevant personal Harness records and reviewed personal harness synchronization, not unrelated external actions.

- Hub: https://www.notion.so/3e3e203190cd8143bdf5df0b46c1cb57
- Knowledge & Skills database: `e1e730a4-4301-4b53-8eb6-1f0fabc43840`
- Knowledge data source: `399492eb-3723-43a8-8002-8b660f136add`
- Runs & Evaluations database: `0326e3f3-e997-4ae3-b14c-36ba87596197`
- Runs data source: `7903c212-74ce-4738-997f-88c4421ab21d`
- Maintained harness-run index: https://www.notion.so/3e5e203190cd813c997ff252160dceff
- Canonical skill key: `skill:harness-run`
- Personal executable repository: https://github.com/maengseojun/agent-harness (private; verify current branch before pushing).

## Capture and recovery contract

For each substantial personal managed task, search Runs by stable `Task ID` before
creating a record. Reuse that page on retry or resume. Record:

- Objective and relevant requirements.
- Decisions, reasons and the maintained Knowledge page they affect.
- Actual result and immutable evidence/source links.
- Checks and review, explicit limits, remaining work and next action.
- Real Codex task URL, applicable Linear issue, and GitHub revision when relevant.

Choose a Task ID unique within the personal hub (include project/context and a
stable run identifier). Multiple matches are a reconciliation conflict, not
permission to pick one or create another. Notion search-before-create is not an
atomic uniqueness constraint; concurrent writers must reconcile duplicates.

Runs schema adds `Task ID` (text), `Linear Issue`, `Codex Task`, and
`GitHub Revision` (URLs). Existing `Evidence`, `Knowledge`, `Outcome`, `Date`,
`Status` and page bodies remain intact. Use `Knowledge` for the reciprocal link
to the relevant maintained record. Knowledge schema adds `Canonical Key` and
`Installed Release` (text); `Source` points to the exact executable revision.
Unknown or inapplicable references stay empty with an explanation in the body.
Do not create a fake Linear issue merely to fill a field.

Use `In progress` during delivery and `Blocked` for a required inaccessible
destination. Only promote a result to `Completed` after local verification,
independent review and required delivery/readback checks. Read back that final
status too. A run status is a historical outcome, not a duplicate live Linear
queue. At a decision milestone, update the existing Knowledge page immediately;
the final Run links the accepted decisions and recovery context.

Fetch the target and schema before editing. Check the Task ID, parent, relation,
links and intended body after writing. Keep the original fetch response privately
alongside its extracted body and the intended summary. Do not use the write
acknowledgement or a copy of the draft as readback evidence. A timeout triggers
lookup/reconciliation of the same page, not another create.

The runner's `closeout` command compares a separate summary body and readback,
and binds them to the current primary artifact. The summary can differ from a
code artifact. Simple blank-line normalization is allowed for plain summaries;
do not broadly strip syntax or rewrite values to force equality. For rich output,
retain the rich artifact and record a simple, semantically complete result summary.
The host verifies properties/relationships and actual connector provenance.

If skills/hooks/harness code change, declare all intended managed files in
`closeout.github_paths` before execution. Record each file read from the exact
remote commit; the runner compares bytes and detects later local evidence drift.
Remote services are not continuously polled by the runner. Resume by re-fetching
the required target before new writes, and preserve canonical identities.

Ordinary answers need no run record. Explicit local-only/read-only requests can
use a named exception with a reason; missing Notion access is a blocker, not a
reason to pretend that a managed task was local-only. No Endix content is copied
into personal records without authorization. Endix team workflow testing is
deferred until Hyunsu's setup is ready.

## User acceptance checks

After deployment, open a fresh **local Codex** task so the new skill and hooks are
loaded. No terminal commands or credential sharing are needed.

1. Ask for a small personal result with a real decision, for example: "Record my
   decision to use Notion for durable knowledge and Linear for short-term work.
   Explain the reason and finish the Notion record." The answer should include
   the actual Notion page, a stable Task ID and what was verified. The page should
   contain the decision, result, limits and next action and link maintained knowledge.
2. In that same task, ask: "Check the saved result again and continue using the
   same task record; do not create a duplicate." The canonical page URL and Task ID
   should remain the same. An unrelated new task can have a new Run; the maintained
   Knowledge page for the same subject should still be reused.
3. Optional scope check: "Read the current policy only; do not modify any service."
   This must not force a Notion write. Ordinary questions remain ordinary answers.

The coordinator tests GitHub byte matching, missing/stale evidence rejection,
review invalidation, installation and CI. The user does not need to intentionally
break authentication or edit files to test those failures. Endix's full workflow
test waits until the team setup is ready.

## Maintenance

Fetch the current schema and target page before writing. Update existing records for the same subject. Keep maintained management documentation in English; task deliverables follow their requested language. Executable skill sources remain in the repository and installed release, not in Notion.

Knowledge records classify policies, skills and guides. Run records preserve execution outcomes, dates, evidence and a two-way relation to the knowledge used. The hub's status board describes these durable results. Personal Linear owns current todos, progress, blockers and due dates; link the canonical Linear issue when applicable without maintaining a second live queue. Do not invent measurements or mark proposals as executed runs. Historical records remain historical; do not backfill unverified evidence.

## Migration

Three pages were moved with their IDs preserved:

- Model-routing policy: `3e3e2031-90cd-815c-b99d-d42b61d6233f`, now in Knowledge & Skills.
- Original v1 draft: `3e3e2031-90cd-8110-a240-eb3915e6124e`, now Historical in Knowledge & Skills. Its Korean body and old execution context are preserved as history.
- Endix upstream review: `3e3e2031-90cd-8181-8baf-d889cbef93d0`, now in Runs & Evaluations. Completed denotes the research artifact, not the proposed contract tests or live-chain checks.

Added a blockchain-upstream-review skill index and a Proposed Grok/Kimi evaluation protocol. No subscription purchase or worker benchmark was performed by this migration.

Readback verified the hub's empty ancestor path, all moved page destinations, both relation directions and removal of the moved children from the former Project page. Database and view configuration was checked through Notion tools; visual rendering was not inspected.
