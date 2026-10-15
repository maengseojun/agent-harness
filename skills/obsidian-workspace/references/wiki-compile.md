# Compile selected evidence into linked wiki notes

Use this workflow for study, research, reports and projects when the user asks to connect selected material to a topic wiki. It adapts the raw/wiki/schema and ingest/query/lint pattern from [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f); the folder and page choices below follow this vault's rules.

## Read and preserve the selected material

Select only the requested material and inspect its actual contents with an available reader. A filename, byte copy, source receipt or generated summary is not a semantic read. Keep the original unchanged, record its exact origin and hash where available, and state what the reader could not inspect. For native Notion/Linear material, follow [native-sources.md](native-sources.md), which uses [source_snapshot.py](../scripts/source_snapshot.py), and keep service identity, reported revision, fetch time and coverage distinct. For selected local project outputs, [sync_project.py](../scripts/sync_project.py) captures only supplied files and provenance; it does not interpret them or compile wiki knowledge.

Choose the least lossy available path for each format:

- **Markdown and CSV:** read the full selected text directly. For a table, preserve headers, units, row counts, missing values and time fields. If you normalize it for reading, retain the original and report dropped or changed structure.
- **Excalidraw JSON:** keep the JSON intact and inspect its diagram with an available renderer or reader. Compare the interpreted labels and relationships with the rendered view; record elements or layout the reader could not verify. Raw JSON text alone is not a diagram review.
- **PDF and Office files:** use an available format-specific reader; cite PDF pages or Office sheets/slides and inspect rendered views when layout, formulas, notes or tables affect meaning. Record uninspected pages, hidden content, OCR or extraction loss. If a suitable reader is unavailable, say so and do not claim full review.
- **Web material:** use an authorized browser or connector. Record the selected URLs, observation time and access coverage. A fetched page or excerpt does not establish that pagination, linked pages or inaccessible content were read.

Create or update a source description under `wiki/sources/` when useful. Link the original or retained copy and give exact source path/URL, hash or reported revision, time, reader/conversion method, coverage and known losses. A local output copied by `sync_project.py` lives under `assets/deliverables/`; the compile helper does not accept that folder as a source. A source note can cite the captured file and preserve the actually reviewed text or evidence positions. Do not call a byte capture a conversion.

## Synthesize with state boundaries

Read the selected source in full for its available scope, then search existing concepts, entities, answers and the hub before drafting. Reuse a concept only when its definition and context match. Keep claims tied to exact source paths and headings, PDF pages, sheet/slide positions, or repository commit and file locations. Preserve conflicting evidence, decisions, open questions and explicit unknowns; do not fill gaps by inference without labeling it.

Keep separate:

- **Source status:** a source's reported `Current` or `Archive` label is snapshot metadata. If the source does not state it, record `unknown`. It does not make a derived claim current.
- **Knowledge review:** whether the evidence has been checked against the existing claims, with stale or unresolved claims marked and explained.
- **Design and adoption:** a design, recommendation or proposal remains a draft until the responsible people or process explicitly adopt it. No source label or wiki update implies team adoption.

Draft only the requested scope. Do not widen an isolated save into a whole-project refresh. For repeated source-to-wiki changes, use one explicit plan with complete desired note bodies, including the selected hub/index/log text; do not encode append operations that duplicate on retry.

## Preview and apply a bounded plan

Create an explicit UTF-8 JSON plan outside the vault. Its top-level keys are exactly `operation_id`, `hub`, `sources` and `notes`. The helper accepts selected text sources under `raw/` or `wiki/sources/`; each source has `path` and the SHA-256 of the exact current UTF-8 body. Read the full body through Obsidian CLI. For a source-snapshot capture, use its verified body hash; otherwise hash the complete CLI-returned body, not a truncated shell display. The `hub` is one exact Markdown path under `hubs/`.

Each note has an exact vault-relative `path`, `expected_sha256` and complete `body`. Use `null` only when creating a note; for an update, use the current body's SHA-256. Targets are limited to derived notes under `wiki/concepts/`, `wiki/entities/` or `wiki/answers/`, `wiki/index.md`, `log.md`, and the one selected hub. The helper rejects raw/source targets, assets, configuration, root instructions and arbitrary paths. Include any index, hub or log edits in the same bounded plan only when they are part of the requested change. Selected UTF-8 source-snapshot `.body` captures under `raw/` are accepted as sources; generated version files under `raw/wiki-compile-versions/` remain excluded.

Preview first. The plan file must be an absolute regular file outside the vault; plan bodies travel through that staged file, not shell arguments:

```text
python3 -B <skill-folder>/scripts/wiki_compile.py --vault <exact-absolute-vault> --plan <absolute-plan.json>
```

Review the returned source hashes, create/update/no-op actions, conflicts and link checks against the actual requested scope. Apply only when the scope is already requested or explicitly selected:

```text
python3 -B <skill-folder>/scripts/wiki_compile.py --vault <exact-absolute-vault> --plan <absolute-plan.json> --apply
```

The helper verifies the exact CLI vault, reads source and note bodies through Obsidian CLI, checks source hashes, target preconditions and planned/existing note links before writing, and rechecks them during apply. Link validation covers Obsidian `[[wikilinks]]` and ordinary inline local Markdown links of the form `[label](path.md)` (including escaped spaces, `<path with spaces.md>`, percent-encoded paths, and `./` or `../` paths); the inline Markdown parser ignores simple fenced and inline code, while wikilinks retain their existing parser behavior. It skips external URLs, images, and non-Markdown destinations. Reference-style links, nested labels or parentheses, multiline links, HTML links, and other complex Markdown forms are not parsed. If any may occur, do not apply until the skill's separate read-only `lint` operation has checked the affected notes through Obsidian CLI; run it again after apply. Attachment links need a separate check. An identical actual body is a no-op before the old-target hash check; source hashes are always checked. Changed prior derived bodies are preserved under `raw/wiki-compile-versions/<operation_id>/`. This is a per-note guarded workflow, not a multi-file transaction: on partial or uncertain failure, report the receipt's performed paths and separate CLI readback of observed paths, then reconcile before retrying. Do not claim a successful save without readback.

The helper validates plan structure, hashes and links; it does not decide whether a claim is true, whether a source is authoritative, whether a design was adopted, or whether a proposal is Done. Those are evidence review and human/process decisions. After verified apply, refresh the affected QMD collection using [qmd_search.py](../scripts/qmd_search.py) when available. Query and lint remain read-only; QMD refresh updates only rebuildable local search snapshots.
