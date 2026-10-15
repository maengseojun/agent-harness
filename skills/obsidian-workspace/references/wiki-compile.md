# Compile selected evidence into linked wiki notes

Use this workflow for study, research, reports and projects when the user asks to connect selected material to a topic wiki. It adapts the raw/wiki/schema and ingest/query/lint pattern from [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f); folder and page choices follow the selected vault's rules.

## Read and preserve the selected material

Select only the requested material and inspect its actual contents with an available reader. A filename, byte copy or generated summary is not a semantic read. Keep the original unchanged, record its exact origin and hash where available, and state what the reader could not inspect. For selected Markdown notes already in the vault, use native `read_note` for parsed frontmatter and body, or `read_note_lines` for original Markdown including frontmatter. For exact-byte evidence, compare a filesystem SHA-256; MCP note responses are text, not a `.body` or `.json` file operation.

For native Notion/Linear material, follow [native-sources.md](native-sources.md), and keep service identity, reported revision, fetch time and coverage distinct. For selected local project files, preserve only requested paths with filesystem operations. The [`sync_project.py`](../scripts/sync_project.py) attachment helper is filesystem-only: its dry run reads only explicitly selected source-root-relative files; `--apply` writes immutable copies and a version catalog. It does not interpret those files or update wiki notes. The separate [`wiki_compile.py`](../scripts/wiki_compile.py) helper uses Obsidian CLI and is not native MCP. A saved copy or helper receipt does not interpret the source or compile wiki knowledge.

Choose the least lossy available path for each format:

- **Markdown and CSV:** read the full selected text. For a table, preserve headers, units, row counts, missing values and time fields. If you normalize it for reading, retain the original and report changed or dropped structure.
- **Excalidraw JSON:** keep the JSON intact and inspect its diagram with an available renderer or reader. Compare labels and relationships with the rendered view; record elements or layout the reader could not verify. Raw JSON text alone is not a diagram review.
- **PDF and Office files:** use an available format-specific reader; cite PDF pages or Office sheets/slides and inspect rendered views when layout, formulas, notes or tables affect meaning. Record uninspected pages, hidden content, OCR or extraction loss. If a suitable reader is unavailable, say so and do not claim full review.
- **Web material:** use an authorized browser or connector. Record selected URLs, observation time and access coverage. A fetched excerpt does not establish that pagination, linked pages or inaccessible content were read.

Create or update a source description under `wiki/sources/` when useful. Link the original or retained copy and give exact source path/URL, hash or reported revision, time, reader/conversion method, coverage and known losses. Keep binary originals; a source note can cite the captured file and preserve reviewed text or evidence positions. Do not call a byte capture a conversion.

## Synthesize with state boundaries

Read the selected source for its available scope, then use native `search_notes` and read existing concepts, entities, answers and the selected hub before drafting. Reuse a concept only when its definition and context match. Tie claims to exact source paths and headings, PDF pages, sheet/slide positions, or repository commit and file locations. Preserve conflicting evidence, decisions, open questions and explicit unknowns; label any inference.

Keep separate:

- **Source status:** a source's reported `Current` or `Archive` label is snapshot metadata. If the source does not state it, record `unknown`. It does not make a derived claim current.
- **Knowledge review:** whether evidence has been checked against existing claims, with stale or unresolved claims marked and explained.
- **Design and adoption:** a design, recommendation or proposal remains a draft until responsible people or process explicitly adopt it. No source label or wiki update implies team adoption.

Draft only the requested scope. Build a bounded list of exact target paths and complete desired note bodies. Include the selected hub, `wiki/index.md`, section indexes or `log.md` only when the requested change needs those links. Do not widen one source save into a whole-project refresh or encode append actions that would duplicate on retry.

## Apply a bounded note plan

Before writing, read every exact target again through MCP. Compare the complete desired Markdown with the current raw Markdown from `read_note_lines`; if unchanged, skip the write. For a small edit, call `patch_note` with one exact, unique match and `replaceAll=false`. For a full note write, pass the entire prepared Markdown string, including YAML frontmatter, as `write_note.content` and omit the `frontmatter` argument. MCPVault 0.16.0 preserves that supplied string exactly when `frontmatter` is omitted. Do not reconstruct original YAML from `read_note`'s parsed object. For a new note, prepare the complete Markdown that should be stored.

Before a substantive overwrite, preserve the existing raw note bytes and SHA-256 in a filesystem backup. Keep source files and raw captures immutable. The MCP note tools cannot read or write `.body` and `.json` files; use filesystem operations for these captures, hashes and backups. They also cannot write binary attachments.

After each `write_note` or `patch_note`, make a separate `read_note_lines` call and compare the complete returned Markdown against the desired result; use `read_note` for semantic frontmatter checks and read linked targets as needed. Compare an actual filesystem SHA-256 when exact bytes matter. Do not infer success from a write response alone. MCP writes are per note, not a multi-note transaction. On partial or uncertain failure, read all affected notes and inspect backup paths before reconciling; do not blindly repeat the whole batch.

### Legacy CLI helper behavior and limits

[`wiki_compile.py`](../scripts/wiki_compile.py) remains a separate CLI plan-and-apply route. It requires an external UTF-8 JSON plan with exactly `operation_id`, `hub`, `sources` and `notes`. Sources are selected text under `raw/` or `wiki/sources/`, with each full current UTF-8 body hash. The hub is one exact Markdown path under `hubs/`. Each note has an exact vault-relative path, expected old-body SHA-256 (or `null` only for creation), and complete desired body. Targets are limited to `wiki/concepts/`, `wiki/entities/`, `wiki/answers/`, `wiki/index.md`, `log.md` and the selected hub; raw/source notes, assets, configuration, root instructions and arbitrary paths are rejected. Plan files are absolute regular files outside the vault.

The helper's default is preview; `--apply` is separate. Plan bodies travel in the staged file, not command arguments:

```text
python3 -B <skill-folder>/scripts/wiki_compile.py --vault <exact-absolute-vault> --plan <absolute-plan.json>
python3 -B <skill-folder>/scripts/wiki_compile.py --vault <exact-absolute-vault> --plan <absolute-plan.json> --apply
```

It verifies the exact CLI vault, source hashes, note preconditions and planned/existing links, then rechecks them during apply. Link validation covers Obsidian `[[wikilinks]]` and ordinary inline local Markdown `[label](path.md)` links, including escaped spaces, angle-bracket paths, percent encoding, and `./` or `../` paths. The inline parser ignores simple fenced and inline code. It skips external URLs, images and non-Markdown destinations. Reference-style links, nested labels or parentheses, multiline links, HTML links and other complex Markdown forms are not parsed. Check affected notes with the skill's read-only lint and separately check attachment links when these forms may occur.

An identical actual note body is a no-op before the old-target hash check; source hashes are always checked. Changed prior derived bodies are preserved under `raw/wiki-compile-versions/<operation_id>/`. This is per-note guarded, not a multi-note transaction. On partial or uncertain failure, inspect the helper receipt and separately read every affected note before reconciling; do not claim a successful save without readback. The helper checks plan structure, hashes and supported links; it does not establish claim truth, source authority, adoption or Done. Do not present native MCP operations as invoking this helper or inheriting its link validation. Native MCP writes do not refresh QMD automatically; use the explicit refresh command in the skill when a search snapshot should be rebuilt.

### QMD search and refresh

[`qmd_search.py`](../scripts/qmd_search.py) has its own read-only MCPVault route. It starts the existing configured `obsidian_vault` stdio server only after validating the exact vault argument and pinned MCPVault 0.16.0 package. For a refresh, it enumerates eligible Markdown under `wiki/` and `hubs/` with MCP `list_directory`; it excludes hidden and `SYN-` paths, and rejects symlinked or unsafe entries. It reads complete raw Markdown with `read_note_lines` from line 1 through the verified full-range end, preserving original YAML text rather than rebuilding it from parsed frontmatter. Before saving a snapshot, it compares the returned UTF-8 bytes with a separately computed SHA-256 of the source file. Search freshness repeats that raw read and hash check for each returned source path.

This QMD route does not invoke Obsidian CLI, `eval` or the app, and it does not write vault notes. It still invokes the existing local QMD executable and embedding model. A refresh changes only the helper-managed derived snapshot and local QMD index; it does not compile knowledge or refresh automatically after a note write. On server, root, path, read or hash failure, stop and inspect state before any retry. The separate `source_snapshot.py` and `wiki_compile.py` routes remain Obsidian-CLI-dependent.

## Same route for a course or project

For a course question, read the current course hub, search for the selected lecture/topic, and read the existing source and concept notes. Inspect the requested lecture material, draft only the needed source or concept update and hub link, then apply and separately read back each changed note through MCP. Keep the original lecture file and its hash as a filesystem capture when required.

For a project result, read that project's current hub and latest relevant session/result, then search and read only the linked evidence needed for the requested update. Preserve selected output files by their original paths and hashes, write the result note and necessary hub/index links through MCP, and read them back. Label proposal, implementation and adoption separately. Neither route copies an entire course or repository, automatically updates another hub, or refreshes the QMD snapshot.
