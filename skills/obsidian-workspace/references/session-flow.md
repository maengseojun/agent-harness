# Work finish and resume

Use this for a course or project already connected to the selected vault. These are agent procedures, not background hooks.

## Finish: propose first

Present three independent candidate groups:

- **Outputs:** selected deliverables and a reusable result note; retain the original location and byte/hash version when copying.
- **Key decisions:** adopted choices, reasons and source links. Separate a proposal, hypothesis, implemented behavior and human-adopted decision. Link a superseded decision to its current replacement rather than erasing history.
- **Next work:** open questions and the next concrete action, with the owning Linear task. A saved next step does not prove work started or finished.

For each candidate state destination, evidence, intended reuse and freshness/coverage gaps. Candidate generation writes nothing. Save only candidates selected by the user or included in an explicit scoped save request. Do not infer permission for a full transcript, cloud sync, schedule, team publication or Notion approval.

## Save: keep a small handoff

Search the relevant hub and existing session/result notes through native MCP for the same task and result. Read the exact target before editing. Use `templates/session.md` when available; otherwise follow the existing answer/result convention. Retain task/hub ID, work/result, decision state, open items, source links/revisions and next action.

Preserve selected output files and their original paths and hashes with filesystem operations. [`sync_project.py`](../scripts/sync_project.py) is a filesystem-only Python helper for explicit file captures; it does not invoke Obsidian CLI or update notes. It defaults to a dry run, and `--apply` writes immutable versioned copies plus a catalog. For Markdown notes, compare current raw Markdown with the desired full text and skip identical content. Use `patch_note` for a small exact unique edit; for a full write, pass the complete prepared Markdown including YAML as `write_note.content` and omit the `frontmatter` argument. MCPVault 0.16.0 preserves that supplied string exactly in this form. Do not rebuild original YAML from parsed frontmatter and call it the original. Before a substantive overwrite, save a byte-for-byte filesystem backup and its SHA-256.

Link the saved note from the hub/index and add one log entry only when the change needs it. Read each shared target immediately before editing. After each write, separately read back the complete note with `read_note_lines` and inspect links; use `read_note` for parsed field checks. Identical content must not add another handoff, copied output or log entry. If a write is partial or uncertain, inspect actual notes and files before reconciling; do not blindly repeat a batch. A copy-only success is not completion of the knowledge update.

## Resume: current work first

1. Read the current hub and latest applicable session/result through native MCP. Fetch current Linear state when available.
2. Search and read two or three relevant knowledge notes and the source behind consequential claims. Check source freshness against the original or service read. A stored source is a point-in-time capture; an unavailable remote does not become current because a note says `reviewed`.
3. Recover adopted decisions, open items and the next action. Follow explicit supersession and current-source links; a first keyword hit or append-only history is not the current decision resolver.
4. Answer the current task. Separately suggest a few relevant notes from other hubs with their original scope, why the method transfers and any differences. Do not turn another project's hypothesis into this project's verified fact. Do not collect or edit that other project automatically.

An explicit current-work-only request narrows retrieval. Resume alone is read-only. Report unavailable Linear or source access and distinguish metadata/link checks from factual review. User reproduction and user-confirmed Done remain separate from an agent trial.
