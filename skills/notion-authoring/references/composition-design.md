# Compose a useful Notion library

Use this reference for library design, mixed document types or a consequential
unfamiliar layout. A short note or routine addition to an accepted structure does
not need fresh template research or another layout interview.

## Establish the reader's job

Inspect the actual material, supplied reference pages and existing destination.
Identify what the reader must find, understand, compare or reuse, the audience,
scope, freshness and whether the material is a draft or an adopted result. Read
referenced attachments when they support a claim; record any coverage gap.

When Linear is the working system, retain tasks, execution criteria and evolving
drafts there. Notion can hold the adopted knowledge and concluded results as the
reader's source of truth. Link their origins, status and as-of date so an archived
result cannot silently become a new execution instruction. Agree a different
division explicitly when requested.

## Select the information structure before blocks

Default for a recurring collection: a library hub with a short purpose and access
to records, domain/project navigation, then detail pages suited to their content.
The domain layer can be a filtered view or section; it need not be another page.

Reuse an existing database for records sharing a schema and management boundary.
Use filters/views for categories rather than copying records or making a database
for every category. A small stable collection can use a linked index instead.
Create a separate database only for independently accumulating data that readers
need to filter, compare or manage, or a real schema/permission boundary. A linked
view is navigation, not a new permission boundary; verify access separately.

Choose only properties readers will use. Title, type/domain, status and as-of may
help a mixed library; owner, source, relations or review dates need a concrete use.
Do not convert these examples into mandatory fields for every page.

## Design properties as well as the body

Database properties are shared record fields, shown as columns/cards in views
and as values on each database page. Names such as `Answers` and `Comes from`
are custom labels, not special Notion blocks. Fetch the existing schema, types
and values before adding fields; reuse equivalent properties instead of creating
duplicate labels. A standalone page does not automatically have DB properties.

For a document library, choose fields by the questions readers need to answer:

| Reader need | Example property and type | Meaning |
| --- | --- | --- |
| Identify the document | Doc — Title | Its stable, recognizable name |
| Know why to open it | Answers — Text | One concrete question answered by this document |
| Understand provenance | Comes from — Text; Source — URL or Relation when useful | Origin and transformation; use URL for an external source, Relation for actual Notion records |
| Follow reading order | Order — Number | An explicit sequence when one exists |
| Identify maturity | Status — Status or existing Select | Draft, adopted/current, superseded etc.; preserve agreed meanings, never infer approval |
| Judge freshness | As of — Date | Date covered or factually verified; Last edited time is not evidence freshness |

Add category, owner, file or relation fields only for an actual retrieval/review
need. A descriptive provenance sentence need not become a relation or a new
Sources DB. Use formulas/rollups only for a requested derived value over actual
related records, and check it with sample values rather than assuming correctness.

Choose which fields are visible in each view and how records are filtered/sorted.
Choose page-property order/visibility separately from the body. An overview view
can show Doc/Answers/Status while the full provenance remains on the detail page.
Keep detailed reasoning/evidence in the body; properties are concise navigation
and context. Shared facts in properties and body must agree.

Native database page layouts apply to the whole database, not just the record
being edited. Treat layout changes as affecting sibling pages; preview/check
representative existing records within the authorized scope. Tool support for
schema/row values does not imply support for native layout customization. Verify
the exact route, saved property types/values, view visibility and rendered detail
header separately; disclose any unsupported layout operation.

## Match the page role and material

| Material | Useful visible structure | Blocks/assets when needed |
| --- | --- | --- |
| Library/domain hub | Brief purpose, what belongs here, access to relevant records | Existing DB views or linked index; one-line descriptions for destinations |
| Research/report | Question, scope/as-of, main finding, analysis/comparisons, sources and limits | Native TOC for long sections; static tables for comparisons; charts for quantitative findings |
| Project/feature explanation | Purpose, adopted structure, actors/flow/boundaries, decisions, result and limits | Diagram when relationships or sequence matter; related-doc index; link working tasks in Linear |
| Resource collection | Scope/selection criteria, each item's purpose/source, useful links/files | Bookmarks or embeds for access; internal DB only for recurring independent records |
| Short note | Answer/context and source | Plain paragraphs/headings; no automatic TOC, DB, PDF or extra child page |

Use native text/headings as the readable backbone. Use a native TOC to navigate
sections of a long page; a reader index links separate destinations. Put the main
answer and decision visible, and secondary evidence or alternatives in toggles.
Use static tables for a fixed comparison and databases for records that keep
changing or need queries. Code blocks preserve exact runnable examples; callouts
should highlight an actual caveat or decision, not decorate every paragraph.

Use `diagram-explainer` when a diagram materially clarifies structure or sequence.
Place its image next to the explanation, with labels/caption and assumptions.
Retain an editable source when needed. A promised diagram or inaccessible local
link is not an image in the saved page.

## Decide what the body and attachments each own

The body should answer the reader's main question without opening every file.
Attachments can preserve originals, reproducible evidence or a fixed layout.
Create a PDF only when that original/distribution/layout has a concrete purpose.
If a finalized PDF already is the canonical report, a summary, reading guide and
that file may suffice. Do not maintain two independently edited full originals.

For each useful attachment, state its purpose, version/as-of, canonical role and
how the reader opens it. Inspect the actual content before deriving claims from
it. Choose image, file, bookmark or embed according to the material and the
verified route. An embed may require login or fail on the reader's device; provide
a working file/link when available and disclose what could not be checked.

Check separately: the native feature exists, the current connector/browser can
author it, and the saved result actually works. No API schema implies support for
every Notion UI block. Use a supported equivalent and name any material loss;
never use another route to bypass a write denial.

## Present one proposal, then verify the reader's path

Present one concrete proposal: the hub/sections/detail inventory, record schema
or view choices when used, main block order, attachment roles, reasons tied to the
material, and how the result will be checked. Describe plausible unknowns; ask
only about choices that change purpose, audience, ownership, approval or scope.
The user need not choose every block. A structure proposal is not approval for
personal Notion saving; follow the skill's exact-content/destination approval.

After authorized authoring, fetch the saved objects separately and check the
reader can enter the hub, find a record, understand its main conclusion/status,
navigate sections and open the relevant attachment. Verify actual DB views,
index destinations and file versions. Inspect rendered layout when meaningful.
Report structured readback, browser checks and unverified access separately.

## Research starting points

Use current official docs for operational capability and inspected templates or
real examples for structural ideas. Research only unresolved choices; record the
source and what was actually inspected. A template listing is not its full
implementation or proof that it suits this user. Old guides may illustrate
information architecture while their UI steps need current verification.

- [Notion knowledge hubs](https://www.notion.com/help/guides/ultimate-guide-to-ai-powered-knowledge-hubs-in-notion): hub/index concepts.
- [User research database](https://www.notion.com/help/guides/user-research-database-product-teams): records, metadata and detail templates; verify current UI separately.
- [Research knowledge hub template](https://www.notion.com/templates/research-knowledge-hub): candidate pattern, inspect actual contents before claiming a match.
- [Writing and editing basics](https://www.notion.com/help/writing-and-editing-basics): native block choices.
- [Images, files and media](https://www.notion.com/help/images-files-and-media): attachments and reader access.
- [Database properties](https://www.notion.com/help/database-properties): field types and per-view visibility.
- [Database layouts](https://www.notion.com/help/layouts): detail-property arrangement and database-wide scope.
- [Relations and rollups](https://www.notion.com/help/relations-and-rollups): linked records and derived summaries when needed.
