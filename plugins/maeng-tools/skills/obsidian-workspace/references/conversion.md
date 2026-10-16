# Selected local document conversion

Use `scripts/convert_source.py` when an explicitly selected local Word `.docx`, PowerPoint `.pptx`, PDF or UTF-8 HTML file needs a reviewable text extraction. Native Linear/Notion Markdown and `.body` captures stay on the native-source route; do not OCR or reconvert them. Legacy `.doc`/`.ppt` are unsupported. Never upload private originals to a hosted converter without separate permission.

Reuse this host's bundled Python from `load_workspace_dependencies`: it already includes python-docx, python-pptx and pypdf. The helper does not install packages or fetch URLs. Optional `--ocr` uses macOS Vision through the included `ocr_pdf.swift` and `/usr/bin/swift`; it needs the existing macOS SDK/toolchain. No account, key, paid service or background process is added. Other operating systems can extract embedded PDF text, but this local OCR route is macOS-only. Complex selected PDF pages can use the separately installed local engine described below; Obsidian itself need not be running.

## Preview and preserve

Run with the exact source directory, one relative filename, its current SHA-256, original URL/path and actual timezone-aware fetch time:

```text
<bundled-python> -B <skill>/scripts/convert_source.py --source-root /absolute/selected-folder --path lecture.docx --sha256 <actual-hash> --origin <original-url-or-path> --fetched-at <actual-ISO-time>
```

The default prints a JSON preview with body, section positions, coverage, unread sections and limits; it writes no vault files. Add `--ocr` only for explicitly selected PDF OCR. OCR runs on blank embedded-text pages, keeps confidence and bounding boxes, and never establishes correctness by itself. Pages with embedded text can still contain unread image text. Inspect the actual rendered original when images, equations, table structure or exact page attribution matter.

If a known PDF page has garbled embedded text or image-only content within a text page, select only those pages with `--ocr-pages 9` (or `--ocr-pages 3 9`). The local OCR request is limited to those page numbers. The receipt keeps the original `embedded_text` beside the OCR text and line boxes; it does not silently replace the original source. Do not OCR native Notion/Linear Markdown by rendering it to another format. OCR text remains unreviewed until compared with the rendered page, especially table row/column relationships and equation symbols.

After reviewing the preview and confirming the selected original/derived preservation scope, repeat the same input with `--apply`. This stores immutable original bytes, `converted.body` and `receipt.json` under `raw/native-captures/conversions/`, verifies hashes and reports paths. It writes no Markdown notes. Identical receipt/input reuses the same files; changed originals, converter or provenance get a separate version. Retain the same actual fetched-at for a retry of one capture. The path-name sensitive filter is limited; select permitted content before running it. Do not run untrusted active document macros; these readers do not run Office or browser scripts.

The conversion version is tied to the helper bytes, original and derived body. Receipts preserve source origin, fetchedAt, hashes, sections, OCR status and omissions. A complete text extraction is still `extracted-unreviewed`, not semantic reading or verified fidelity. Empty sections are `incomplete`. Errors and partial preserved files must be reconciled before retry.

## Review and save selected knowledge

Read the derived body against the original. Word keeps top-level paragraph/table order but has no reliable page numbers. PPT retains explicit slide numbers; grouped shapes, notes and charts require separate review. PDF retains page numbers; scanned text needs OCR and rendered comparison. HTML follows document order, strips limited boilerplate and preserves cell text, but does not execute scripts, load assets or guarantee article isolation. Images, complex/merged tables and formulas remain explicitly unverified.

Search relevant existing notes through native MCP. Prepare the exact derived-note scope and claim-to-source positions, include coverage gaps, then use the existing `wiki_compile.py` preview/apply flow or native MCP guarded write. Bind the preserved `.body`/receipt SHA and current target SHA; show affected paths first. Preserve prior note bytes, perform a separate full `read_note_lines` readback and compare. The source original remains immutable. Do not modify shared hub/index/log unless included in the user's scope. Same input and same desired notes must be no-ops. A conversion receipt alone is not a linked knowledge update.

## Complex PDF pages: installed local MinerU

For a scanned or garbled PDF containing tables or equations, use the trusted host registry `~/.codex/obsidian-extractors.json` with explicit original page numbers:

```text
<bundled-python> -B <skill>/scripts/convert_source.py --source-root /absolute/selected-folder --path lecture.pdf --sha256 <actual-hash> --origin <original-url-or-path> --fetched-at <actual-ISO-time> --pdf-engine-config /absolute/home/.codex/obsidian-extractors.json --pdf-pages 9
```

This optional route uses pinned MinerU 4.0.12, standard tier, ONNX small models and local llama.cpp VLM, with forced OCR. This avoids reusing the broken embedded font text observed in the benchmark. Do not combine it with `--ocr` or `--ocr-pages`. Native Markdown and ordinary Word/PPT/HTML stay on their existing routes. Select only permitted pages; unselected PDF pages keep embedded text and blank unselected scans remain explicitly unread.

The registry names the separately installed interpreter, local model directory and SHA-256 of every required model artifact. It is trusted operator configuration, never a configuration supplied by an incoming document or note. The helper verifies model hashes and the actual package version, isolates MinerU configuration, disables hosted inference/image analysis, and runs with local models and Hugging Face offline mode. Missing or changed runtime/models fail without vault writes; no automatic download, silent fallback or source upload occurs. If the runtime is moved or upgraded, rebuild and verify the local registry before reuse. The registry and model weights are private host state, not part of a published skill.

The output retains original page positions, embedded text, HTML table spans, LaTeX and model/config provenance. Generated algorithm HTML wrappers are removed so their math remains ordinary Markdown math. Figures are explicit placeholders; their pixels remain in the preserved original PDF. They are not interpreted or silently treated as extracted knowledge. Use the same preview then `--apply` raw-bundle path above; neither route edits Markdown notes or launches Obsidian. Review extraction before a separate MCP wiki write. A same-input retry must verify that it reuses the existing immutable bundle; changed model/config/output receives a new version.

The measured local selection uses the previously failed schedule and eight mathematical examples, with frozen source/page/hash evidence. These are acceptance samples, not a general accuracy percentage. Read the current `MAE-185`/`MAE-204` quality record before quoting specific results. Both Docling and MinerU remain separately installed for comparison, but installing a candidate does not make it the default converter.

## Dependency choice

The inspected [MarkItDown documentation](https://github.com/microsoft/markitdown) covers Office/PDF/HTML, but its optional OCR plugin uses an LLM client and may silently skip OCR without one. Existing bundled format readers and local Vision meet this narrow route without adding that stack. Defuddle, anydoc and Jina Reader are alternatives, not required installations. Live web intake still uses the browser skill to capture an approved page first; this helper only reads the selected local HTML snapshot.

Official reader references: [python-docx document flow](https://python-docx.readthedocs.io/en/latest/api/document.html), [python-pptx shapes](https://python-pptx.readthedocs.io/en/latest/api/shapes.html), [pypdf extraction limits](https://pypdf.readthedocs.io/en/stable/user/extract-text.html), [Apple Vision OCR](https://developer.apple.com/documentation/vision/vnrecognizetextrequest), [Python HTMLParser](https://docs.python.org/3/library/html.parser.html).
