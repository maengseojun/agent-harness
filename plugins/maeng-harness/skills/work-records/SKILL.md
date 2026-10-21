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
4. **No hook gate (maeng-harness 0.2.0).** Since slim gates (MAE-237) no hook checks Notion calls: there is no publish gate, no journal entry and nothing to reconcile. Steps 3, 5 and 6 are your discipline, not something the harness enforces.
5. **Publish exactly that payload.** Send the reviewed `publish/<id>.json` unchanged. Any edit to the payload voids the review; start again at step 3.
6. **Readback.** Fetch the actual page, compare body, properties, parent and links with the payload. A write acknowledgement alone is "uncertain". On a timeout or lost response, search for the page by its stable identity before any retry; retry the same reviewed payload only after confirming the page does not exist, and never create a duplicate.
7. **Backlinks.** Write the canonical Notion URL into the original Linear issue (output/description) and the link into the Notion project index; set `notion` in the draft's frontmatter and move the draft status to `published`. Read both destinations back. Outcome records are not final until both backlinks are verified.
8. **Tell the user the link only**, plus one line on limits if any.

The same Sol flow covers a policy page and a factual refresh of an already saved personal outcome (fetch current page, build the exact update payload, review, publish, read back). `Status: Completed` on a Notion record is the user's call (typed by the user, or relayed by another of their sessions per the global "Approval relayed by another session" rule); otherwise propose it, do not set it.

If a review cannot pass after a good-faith fix loop, leave the draft in the vault, comment the blocker on the Linear issue and report it. Do not publish unreviewed.

## CEO decisions

Every decision the CEO approves (`승인 #N`, a named option, a direction set in chat or relayed by another of their sessions) becomes an ADR in `wiki/decisions/` (`ADR-<MAE-id>-<slug>`) with `audience: [ceo, exec]`, the CEO's words quoted, the date and the Linear issue. Write it in the same turn the decision arrives. A wildcard (harness-run org-chart.md: a one-off override of a DRI) gets no ADR; its `wildcard:` line on the issue is its only record.

## Project archive

When the CEO says a project is finished, or the Linear parent of a project goes Done, set `closed: <YYYY-MM-DD>` in its hub's frontmatter. SessionStart lists hubs closed 14 or more days ago (`Archive candidates`). For each one:

1. Ask the CEO, once, with the hub and the files that would move. Nothing moves without a yes.
2. On yes, run `maeng-archive` (`status`, then `move <path> --store gdrive --dry-run`, then `move <path> --store gdrive`; without `--store` it goes to OneDrive) for the project's notes and raw files. The gdrive store is the school Drive (2025131619@korea.ac.kr), folder `maeng-archive/`; read archived files back with the claude.ai Google Drive connector, which is signed in to that school account (see maeng-archive, "Searching and reading Google Drive"). Fill every stub summary.
3. Keep the hub in the vault as the index: set `status: archived`, and list each moved file with its stub link and one line on what it held.
4. Record the archive on the Linear parent (comment) and in an ADR (step "CEO decisions").

On "later", set `closed` to today (asked again in 14 days); on "no", remove `closed`. Note the answer in the hub either way.

## Review and refine

A saved draft, a reviewed record and final writing are distinct states. After publishing, reread the saved page against the evidence and correct stale facts through the same flow. Keep one canonical result page per outcome and preserve history across revisions.

Record review verdicts and corrections as Linear comments and `wiki/reviews/` notes; they are evidence for future judgment criteria.

## Notion authoring operations

Page structure, native blocks, captions, databases and views: use `notion-authoring`. File uploads, database and view changes are their own payloads with the same review and readback sequence; keep the original responses and verify actual attachment, schema or rows by fetch.
