# Choose a Notion structure

This is a routing guide, not a frozen API schema. Discover live tool definitions
before use; last inventory: 2026-10-07. The connected Notion tools and their
`notion://docs/enhanced-markdown-spec` / `notion://docs/view-dsl-spec` resources
are the primary authority for supported syntax.

| Reader need | Structure | Verify |
| --- | --- | --- |
| Read one explanation | Page, headings, table of contents, restrained callouts | Body and heading order |
| Compare options | Static table plus decision toggles | Cell values; toggle nesting |
| Read a long domain independently | Child page + parent navigation + source mentions | Parent and reciprocal links |
| Understand an example or process | Image/diagram with caption and walkthrough | Actual image source, caption and readable preview |
| Explore a parameter | Approved HTML attachment/embed or linked interactive artifact | Actual embed source and rendering; no static-image claim of interactivity |
| Keep source files together | File attachments or page-owned folder | Upload IDs, folder membership, target page |
| Maintain repeated records | Database with minimal typed schema and row pages | Schema, properties, data-source ID and queried rows |
| Compare the same records in different ways | Linked view or DB view | Actual view type/configuration and source identity |
| Show progress/categories | Board/list/table | Group/filter fields and resulting records |
| Explain dates/ranges | Calendar/timeline | Date properties, timezone and start/end mapping |
| Browse visual records | Gallery + explicit cover property | Covers and visible properties |
| Summarize quantitative records | Chart view | Aggregation, filters, units and underlying values |
| Gather responses | Form, only when requested | Open/closed state, anonymous setting and submission permissions |
| Show locations | Map, only with real location data | Location property and intended records |
| Reuse the same maintained text | Synced block/reference | Original ownership and downstream effect |
| Discuss a specific passage | Comment, only if messaging is authorized | Discussion/selection and actual comment |

Native content may include columns, tabs, equations, Mermaid, code, media, embeds
and synced blocks. Use only the syntax the live connection documents. A caption
belongs to its media block and should explain the relationship, not just a filename.

Connected authoring operations include page creation/editing, properties,
icons/covers, template application, database creation/schema/layout changes,
view creation/editing, folders, uploads, duplication and moves. Each actual call
still needs scoped approval and readback. Notion agent sessions, sending messages,
sharing/access administration and unrelated destructive operations are not implied
by a request to format a document. A general authoring skill does not register or
run custom agents.

Known boundaries: merged table cells cannot be authored through this Markdown;
meeting transcripts are not editable through it; custom block definitions must
already exist and be readable. Some verification features require a qualifying
plan. UI-only buttons, automations or unsupported settings need an explicitly
available route; do not invent tool parameters or claim 100% UI/API parity.
