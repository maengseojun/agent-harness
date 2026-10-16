# Native Notion and Linear sources

Use an authorized connector or logged-in Aside read for one explicitly selected source. Do not re-OCR or replace a returned native body with a summary. This workflow reads source services; it does not edit them.

## Receipt and preview

Preserve one UTF-8 JSON receipt outside or inside the selected vault using filesystem operations. The native Obsidian note tools do not read or write `.json` or `.body` captures. Keep these fields and values grounded in the actual service response:

```json
{
  "schema": 1,
  "service": "linear",
  "source_id": "MAE-25",
  "url": "https://linear.app/maeng/issue/MAE-25",
  "revision": "actual returned updatedAt",
  "fetched_at": "2026-10-14T09:00:00+09:00",
  "coverage": {"scope": "returned issue description", "truncated": false, "unknown_block_count": null},
  "native_body": "The full selected native body, unchanged.",
  "raw_response": {"description": "The full selected native body, unchanged."}
}
```

Use actual timestamps; missing coverage remains unknown, never silently false. For Notion record the page ID, URL, reported last-edited time, and selected block/body coverage. Child-page links do not prove their bodies, tables or media were exported. An old response `as of` time differs from the current request time; cross-check it or expose the freshness gap. Connector/Aside Markdown is a service representation, not an original local Markdown byte copy. For Linear preserve status at the returned revision; it does not establish team adoption or product completion.

Do not include credentials or transport headers. The existing [`source_snapshot.py`](../scripts/source_snapshot.py) helper defaults to preview and validates the exact configured vault folder. For explicitly selected impact notes under `wiki/sources/`, `wiki/concepts/` or `wiki/answers/`, it starts the configured, pinned standalone MCPVault stdio server and reads complete raw Markdown through `read_note_lines`. Each returned UTF-8 body must match the complete no-follow file hash; missing notes, inaccessible paths, truncation and unsafe entries are rejected. It does not start Obsidian or invoke its CLI/eval. With no impact notes, capture needs no MCP process because all outputs are raw filesystem artifacts. `--apply` stores immutable `.body` and raw-response `.json` captures and updates `raw/native-captures/catalog.json`; it does not write Markdown notes or semantically update knowledge. Its `--receipt` is a staged file path, and `--impact-note` accepts only exact paths in those three wiki folders. Use it only when its preview matches the selected scope. Large bodies belong in the receipt file, not command arguments. If it fails, inspect actual receipt, notes and files before deciding whether a retry is safe; do not repeat a failed bulk capture blindly.

Before applying knowledge changes, use native `search_notes`, `read_note` and `read_note_lines` to inspect the exact listed source, concept and answer notes. These are candidate dependencies selected by the agent; do not infer semantic dependencies from a title alone. Compare source body and revision with current claims, and present the bounded affected-note set for review.

## Apply and lineage

Keep the exact raw response and selected native body as filesystem `.json` and `.body` captures when the requested scope requires them. Record their paths, SHA-256 hashes and fetch time. Treat originals as immutable. Then create or update searchable Markdown source and derived notes through native MCP. Read each exact target immediately before writing. If current raw Markdown already matches the desired version, skip the write. For a small edit use a unique exact `patch_note`; for a full write, pass the complete prepared Markdown string, including YAML frontmatter, as `write_note.content` and omit the `frontmatter` argument. MCPVault 0.16.0 preserves the supplied string exactly in that form. Do not reconstruct original YAML from `read_note`'s parsed object. For a new note, prepare the complete Markdown that should be stored.

After each write, separately read the note with `read_note_lines` and verify the complete Markdown, links and expected scope; use `read_note` for semantic frontmatter checks. Use filesystem hashing and byte backups where exact bytes or recovery evidence matter. Capture success is not semantic update success.

Record service, source ID and stable URL; reported revision; actual fetch time; selected body coverage; exact raw capture/hash; and the source note's hub links. Preserve old raw and conversion versions. A same body/revision reuses its capture; a new observation can update receipt metadata without duplicating body bytes. The same revision with a different body is a conflict to investigate. An old selected revision may become the active pointer only when explicitly requested; verify freshness before calling it latest.

Update only supported claims and links in the requested scope. If a claim is not demonstrated by the selected body, keep it `draft` with a reason. A service revision change with an identical body can be metadata-only. A permission or access error does not prove a page is absent. On identity, coverage or conflict failure, preserve the prior state, inspect any partial capture paths and read affected notes before reconciling; do not retry blindly. There is no whole-vault transaction or background sync.
