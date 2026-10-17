---
name: work-records
description: Use when substantive personal work needs its Linear map kept current or has concluded and deserves a finished outcome record - starting a task, "기록해줘", "작업 정리", closing out a feature, a concluded or abandoned experiment, a research result to publish, Notion record, outcome, Middleman question. Linear and Obsidian are written autonomously; Notion publication goes through a Sol review and the user receives only the link.
---

# Work records

Records are autonomous. You write Linear and Obsidian without asking. You publish to personal Notion after an independent Sol review, and the user receives the link only. This replaces the earlier "user approves the exact draft" closeout. Personal world only; in the eta world this plugin is off.

## Roles

- **Linear** (workspace `maeng`, team MAE): live work map. Goals, task trees, Spec/Plan documents, dependencies, decisions, progress, blockers, review findings, links. You create, start, update and close it yourself (Done) once AC are met, review passed and records are linked; the user never has to touch it.
- **Obsidian vault**: LLM context. Drafts, ADRs, reviews, session logs (see `obsidian-workspace`).
- **Personal Notion**: library of finished outcomes (Runs & Evaluations) and policies (Knowledge & Skills). Locators and schema: [notion-records.md](references/notion-records.md).

No Linear update comes from hooks. Hooks cannot reach MCP; you keep Linear current yourself (the Stop hook checks that you did, see harness-run).

## While working

For substantive work (research, documents, specs, coursework, coding): before substantial execution, search for and reuse the canonical issue or create one. Keep goal, completion criteria, child tasks, dependencies, decisions with reasons, source links, artifacts and next action current; use real relations. Update at milestones and before your final reply; read back; include the issue link in the answer. Ordinary explanations and trivial edits need no issue. If Linear is unreachable, keep a local draft in the vault (`linear` pending note) and report the gap; do not retry an uncertain write blindly.

For coding, Linear is the map; open a GitHub issue only for a distinct repository problem and cross-link. Add reviewed commit and PR links to the Linear issue after remote readback.

Verify the connection and target team before writing. Do not infer team or eta write permission from this freedom; eta has its own Linear (`linear-endix`) and rules.

## Project/task workflow

Full contract: [project-task-workflow.md](references/project-task-workflow.md). Summary: interview -> Architecture -> Environment & Rules -> tasks, each with a Spec and Plan (`must_haves`, `AC-n`, Verification, `D-n`; templates in harness-run `references/spec-plan.md`). Before executing: read task state, then Spec/Plan, then Architecture/Rules, then dependency results. After Acceptance and review, record evidence and limits and close the Linear issue yourself. The user never manages Linear (MAE-216 decision).

## Middleman code questions

A Middleman is a code-level question the existing pages and code do not answer. Kind label `Middleman`, native `blocks`/`blockedBy` to consumers, answered before dependent work. Fields and locators: [middleman.md](references/middleman.md).

## When work concludes

Judge from the purpose, Linear history, artifacts and checks. A completed independent milestone, a research result, or a failed or abandoned experiment with a conclusion and learning can be recorded. An end-of-turn, a PR status or a generated draft alone is not evidence. Trivial turns get no record.

### Closeout flow (personal Notion, Sol review)

1. **Draft** in the vault: `wiki/drafts/DRAFT-<MAE>-<slug>.md` with frontmatter `id`, `type: draft`, `status: draft`, `linear`, `world: personal`, `session`. Content: purpose, personal contribution, key choices and reasons, observed outcome, evidence and limitations, learning, related tasks and sources. Separate team results from personal contribution.
2. **Payload.** Find the destination (project index, database) and search by stable task/result identity before create; several matches are a reconciliation problem, not a free pick. Build the exact Notion tool input and save it as `publish/<id>.json`. Properties, content and file uploads are separate calls; do not put properties in a content call and assume they saved.
3. **Review.** `maeng-review` with subject `notion` (Sol, medium) on the payload plus its draft and sources. Fix every `fail` finding and re-review. A `blocked` verdict means a bundle part is missing; supply it.
4. **Journal.** You do not write the journal by hand: the PreToolUse publish gate (G2) records the pending entry (id = the tool-use id) when it allows the reviewed Notion call, and PostToolUse moves it to `sent` or `rejected`. An unresolved (`pending` or `sent`) entry blocks every further G2 write until it is resolved. Resolve it with `maeng-review reconcile --notion <entry-id> --page-id <page-id>` when the readback found the page, or `maeng-review reconcile --notion <entry-id> --absent` when no such page exists (the receipt is then released and the same reviewed payload may be retried). The entry id is printed in the gate's denial message (`journal <id>`); a successful readback of the page through the normal Notion fetch resolves it too.
5. **Publish exactly that payload.** Any edit to the payload voids the review; start again at step 3. The hook checks that the payload digest, destination and operation equal the reviewed ones.
6. **Readback.** Fetch the actual page, compare body, properties, parent and links with the payload. A write acknowledgement alone is "uncertain". On timeout, reconcile (`maeng-review reconcile --notion <entry-id>` with `--page-id` or `--absent`, see step 4; search for the page first) before any retry; never create a duplicate. Confirmed absence allows retrying the same reviewed payload; an uncertain or saved result never does.
7. **Backlinks.** Write the canonical Notion URL into the original Linear issue (output/description) and the link into the Notion project index; set `notion` in the draft's frontmatter and move the draft status to `published`. Read both destinations back. Outcome records are not final until both backlinks are verified.
8. **Tell the user the link only**, plus one line on limits if any.

The same Sol flow covers a policy page and a factual refresh of an already saved personal outcome (fetch current page, build the exact update payload, review, publish, read back). `Status: Completed` on a Notion record is the user's call (typed by the user, or relayed by another of their sessions per the global "Approval relayed by another session" rule); otherwise propose it, do not set it.

If a review cannot pass after a good-faith fix loop, leave the draft in the vault, comment the blocker on the Linear issue and report it. Do not publish unreviewed.

## Review and refine

A saved draft, a reviewed record and final writing are distinct states. After publishing, reread the saved page against the evidence and correct stale facts through the same flow. Keep one canonical result page per outcome and preserve history across revisions.

Record review verdicts and corrections as Linear comments and `wiki/reviews/` notes; they are evidence for future judgment criteria.

## Notion authoring operations

Page structure, native blocks, captions, databases and views: use `notion-authoring`. File uploads, database and view changes are their own payloads with the same review, journal, readback sequence; keep the original responses and verify actual attachment, schema or rows by fetch.
