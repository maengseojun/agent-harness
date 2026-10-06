---
name: notion-authoring
description: Design, create and verify Notion libraries, documents, illustrated reports, linked subpages, databases, views and attachments using connected tools. Use for a requested Notion deliverable, page/block structure proposal, or improving organization and readability.
---

# Notion authoring

Apply this skill whenever creating, reorganizing or publishing a Notion deliverable,
including requests phrased only as “save to Notion.” The user need not name it.
This is agent-side guidance, not a background Notion automation: it does not
retroactively update pages or run when someone edits Notion outside this agent.

Choose a structure for the reader's job. Use the connected capabilities when they
help; do not promise every Notion UI feature or add a database just to showcase it.
Keep progress/tasks in Linear when that is the user's working system. A Notion
review sample is a saved draft, not an adopted specification or Completed record.

## Discover and design

1. Verify the actual parent, workspace ownership and existing record. Fetch before
   editing. Search by stable task identity; reuse the canonical page.
2. Discover current tool schemas and read `notion://docs/enhanced-markdown-spec`.
   Read the relevant live view/schema documentation for database work. Tool
   availability, plan limits and actual successful use are different facts.
3. Pick the smallest useful structure using [capabilities](references/capabilities.md).
   For a library, mixed document types or a consequential unfamiliar layout, read
   [composition design](references/composition-design.md) before choosing blocks.
   Inspect supplied references and research only the cases/capabilities that affect
   this choice. Propose one structure with its reasons and verification path;
   resolve routine details yourself. Reuse an accepted design for routine additions.
   Keep the main conclusion visible. Put supporting options/evidence in toggles;
   move an independently useful domain to a linked child page. Link existing
   common foundations instead of copying them.
4. For images/diagrams, include a descriptive caption and the nearby explanation
   needed to interpret them. State assumptions and unresolved choices. Preserve
   an editable source when requested; label independently drawn previews honestly.
   Use the requested diagram skill for creation, not a placeholder pretending to
   be a diagram. Use a preview or short interview only when a material audience,
   purpose or structure choice is missing.

Before writing, bound the deliverable: intended pages, records, diagrams and
views. Do not expand that inventory without a concrete user need.

## Navigation before detail

When a document spans several substantive sections or readers need to revisit
specific decisions, put navigation near the top, after a short purpose/status:

- **Reader index:** link each domain/child page and say what question it answers.
  For a single page, use verified section links when available. Never invent
  block anchors. A reading order without clickable destinations is not an index.
- **Table of contents:** use Notion's native table-of-contents block for headings
  within the page, using the current enhanced-Markdown specification. Keep it
  outside toggles and before the detailed body; it complements the reader index.
- Use a consistent heading hierarchy: major topics, then their explanations or
  diagrams. Keep the conclusion and decision summary visible; put alternatives
  and evidence inside toggles. Do not expect plain toggle titles to enter a TOC.
- Domain child pages link back to their parent and have their own TOC when long.
  A short note needs neither an empty TOC nor a redundant navigation section.

When the user supplies reference pages, inspect their navigation and apply the
relevant pattern without copying unrelated content. If inaccessible, distinguish
the user's described preference from an observed reference layout. During
readback, verify the TOC block, heading order, index destinations, preserved child
pages and captions. Do not claim click behavior or rendered layout without a
browser check.

## Compose for two reading depths

Start substantive review documents with the question they answer, their scope,
source/parent links and approval status. Give a short answer-first summary before
navigation or detail. State the review completion criterion when useful; do not
turn a draft into an approved design merely because its open questions are closed.

Choose the page role before arranging blocks:
- **Hub:** summarize the domain, then an ordered index of linked documents with
  the question each answers. Use an existing database view when appropriate;
  otherwise a small linked table is sufficient. Do not reproduce every child.
- **Detail:** explain what it is, why it matters, how it works and a concrete
  example where useful. Use tables for real comparisons and specify the source,
  payer or authority when those distinctions matter. Link adjacent topics at the
  point of use instead of re-explaining them.

End with explicit open decisions (or a verified statement that none remain),
not vague TODOs. For review packages, keep the current preference visible and
alternatives/evidence expandable. Do not force every paragraph into identical
labels or add navigation properties/databases to a short standalone note.

## Author and deliver

Use `work-records` for personal record approval and the exact-call helper contract.
Present the complete content, assets and destination once. Existing approval
covers the same material after mechanical transport substitutions (returned IDs,
upload references and equivalent native markup); a changed claim, audience or
scope needs a new decision. Never ask again solely because a parent returned an ID.
Personal approval does not authorize team publication, comments to other people,
sharing, agent messages, deletion or moving unrelated material.

- Preserve native page/database children during updates. A `<page>` or `<database>`
  tag can move content; use mentions for references. Prefer targeted edits.
- Indent toggle children with tabs. Use native tables for static comparisons.
  Keep file names in inline code to avoid accidental domain autolinks.
- For local media, bind its actual path/hash to an approved upload operation;
  call create_file_upload, then exactly one multipart POST as instructed by its
  live schema. Keep returned upload headers/URLs out of logs and evidence.
  Recheck the file hash before POST. Use returned suggested_markdown, never a
  local file path or an invented public URL. Upload success is not attachment
  success: attach it to the approved page and fetch the page separately.
- Create a database only for repeated records that need properties, queries or
  multiple views. Fetch its data-source ID before rows, relations or views.
  Do not confuse a database block, data source and view ID. Define the smallest
  schema; verify computed fields with sample data if requested. Schema drops,
  moving content, public forms and access changes need explicit scope.
- Use async status until success before dependent actions. On a timeout, reconcile
  the actual object before retrying. Never generate duplicate pages or upload
  attempts to hide an uncertain response.

## Verify the saved result

Fetch actual body, parent, properties and children; query DB rows and fetch view
configuration when used. Verify toggle nesting, image/file references, captions,
links and expected counts. Paginate queries until every intended record has been
checked; one returned batch is not complete coverage. An acknowledgement is not
readback. Keep original responses separate from normalized comparisons.

For attachments used as evidence or the original record, check the actual file,
version and ability to open/read it through the supported route. A filename,
upload receipt or local path alone does not prove a usable attachment. Record
unreadable or inaccessible items and their effect on the document's conclusions.
Inspect the rendered page through
an available authorized browser when layout matters; otherwise disclose that
only structured content was checked. No browser or shell route may bypass a
write denial. In an active native Harness task, automatic provider readback is
currently limited to basic page writes. Rich operations may be supported by the
personal record coordinator yet blocked by that task gate. Do not complete or
unregister a task to evade this check; report the unsupported adapter and keep
the draft. Report unsupported capabilities and partial delivery precisely.

Update the canonical Linear issue with result links and gaps; read it back.
Verify Notion index backlinks without duplicating a child link already present.
Do not label a record Completed without the user's decision.
