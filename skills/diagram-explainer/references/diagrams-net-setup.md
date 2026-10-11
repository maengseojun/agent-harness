# diagrams.net / draw.io and yEd Live setup

Verified on 2026-10-10. Current user decision: draw.io first, yEd Live for automatic graph layouts, school Google Drive for editable originals, no Obsidian. Earlier Excalidraw setup is historical and its files are preserved.

## Official sources and connection

The [official jgraph/drawio-mcp repository](https://github.com/jgraph/drawio-mcp) offers a local stdio server, hosted MCP App and other integration approaches. The installed route is the [official tool server](https://github.com/jgraph/drawio-mcp/blob/main/mcp-tool-server/README.md), `@drawio/mcp@1.6.3`, Node >=18. Its reviewed npm package is installed under `/Users/maengseojun/.local/share/drawio-mcp/`. No unrelated connector was removed.

Codex `~/.codex/config.toml` has a `drawio` stdio entry using `/Users/maengseojun/.local/bin/node` and `/Users/maengseojun/.local/share/drawio-mcp/node_modules/@drawio/mcp/src/index.js`. TOML readback passed. A real SDK client initialized the same configured executable, discovered seven tools, listed/read native pages, changed a page and separately read it back while asserting the other page remained byte-equivalent. `open_drawio_xml` returned an official editor URL and opened the default browser. See `assets/drawio/mcp-verification.json`.

Observed tools: `open_drawio_xml`, `open_drawio_csv`, `open_drawio_mermaid`, `list_pages`, `get_page`, `set_page`, `search_shapes`. Inspect the live schemas for arguments and versions. These tools do not independently save a file in Drive. Current-chat tool discovery may need a connection reload; a separate client test is not proof that this conversation has live tools. The hosted endpoint `https://mcp.draw.io/mcp` exists but was not configured or tested for this workflow.

## Desktop and storage

Installed official [draw.io Desktop 32.4.1](https://github.com/jgraph/drawio-desktop/releases/tag/v32.4.1) arm64 at `/Users/maengseojun/Applications/draw.io.app`. The DMG SHA-256 matched the official release: `85e3bd6956b79bc0ff6f36237abd7b5527b1654802ead742c8a78b657e01740c`. macOS signature verification passed and Gatekeeper reported accepted/Notarized Developer ID. CLI version and PNG export were executed successfully.

The desktop app is an [offline editor](https://www.drawio.com/docs/security/desktop-secure-diagrams/). Its installation does not authorize Google Drive API access. Browser [Google Drive integration](https://www.drawio.com/docs/integrations/google/) or the already-connected Drive file connector supplies the cloud path. A separately verified Drive Desktop sync directory can also store native files; no new sync client was installed. Compare [storage locations](https://www.drawio.com/docs/manual/file-storage-locations-compare/) before claiming equivalent cloud behavior.

Preferred account `2025131619@korea.ac.kr` was verified by the school connector profile, ID `104845308905950926404`. Folder search found no existing diagram-explainer folder, so a new [school Drive folder](https://drive.google.com/drive/folders/1uKZxJVSlQ_h9IiyW0gV3b8Vc5oG-Wea7) was created. The [36-page native original](https://drive.google.com/file/d/1HW0ep_lNOPdE2lDby5hrDJunaNVQc_0n/view) was uploaded with its native MIME type, metadata read back, then downloaded raw and compared byte-for-byte: SHA-256 `6fb194e687da1b91a83f9134f5f1101e5695b3fd8ab115f50cc1e470776ae2e2`. Sharing/visibility was not changed. Connector upload/readback is not proof of browser-editor OAuth or multi-device sync.

Backup working files: `/Users/maengseojun/Library/Mobile Documents/com~apple~CloudDocs/diagrams/diagram-explainer/`. Old `/excalidraw/` generated masters and prior boards remain intact. Do not overwrite user changes in either location.

## Korean font and rounded defaults

Font file: `/Users/maengseojun/Library/Fonts/NanumDaHaengCe.ttf`; actual family **나눔손글씨 다행체**. The prior [user-supplied Korean font article](https://abluesnake.tistory.com/166) used Obsidian-specific font slots; those are not used here. Apply `assets/drawio/editor-config.json` through Extras → Configuration, accept the ordinary appearance change and reopen when no unsaved user work would be lost. This was applied to the new desktop installation; the native font picker then displayed 나눔손글씨 다행체 at 28px.

The [official configuration reference](https://www.drawio.com/docs/reference/configure-diagram-editor/) describes `customFonts`, default vertex/edge styles and web-font CSS. Defaults: rounded nodes with `arcSize=16`, 28px node labels, 22px edge labels, orthogonal connectors. Individual templates preserve useful 30/44/24px hierarchy and explicit styles. Four representative templates were actually exported by the official desktop renderer and visually checked for Korean labels, connectors, clipping and spacing. Comparison cells are rounded and separated by a gap; storage bodies can retain straight internal sides.

The current in-app browser also imported all 36 pages and visibly rendered the first Korean flow with this font. Its previously empty configuration was updated through the JSON configuration UI with the same font/rounded defaults and returned the ordinary restart notice. The setting is specific to that browser profile; other browsers are not automatically configured. A local system font is not automatically bundled in SVG, Drive or HTML files. Another device needs the installed font or an authorized embeddable web-font route. Use the actual native PNG when exact typography must be preserved. Do not claim web-font setup from desktop configuration alone.

Text-background policy (updated 2026-10-11): standalone text and group/lane headings remain transparent. `assets/drawio/editor-config.json` provides neutral `labelBackgroundColor=none;labelBorderColor=none` defaults, since one global color cannot match every panel. For a connector label placed on its line, explicitly override the edge with the actual local surface color (`labelBackgroundColor=#<color>;labelBorderColor=none`). New text-only cells use `fillColor=none`; semantic node/panel fills stay intact. Small local-color masks were rendered successfully in draw.io Desktop 32.4.1 on white (#FFFFFF), cream (#FAF7F0) and gray (#F4F6F8) surfaces; each removed the line behind the Korean label without a contrasting box. A separate three-input example used different target ports and offset labels. These tests do not establish another editor/browser/device's behavior. Where 3 or more connectors crowd one area, or a mask cannot be matched/rendered, offset the labels and separate routes. This replaces the earlier unmasked inline-label allowance. Configuration does not retroactively change existing styles or a running editor profile; never restart an editor containing unsaved work merely to apply it.

## yEd Live and HTML

[yEd Live](https://www.yworks.com/yed-live/) is an additional graph editor with automatic hierarchical, organic, orthogonal, circular, tree, balloon, radial and other layouts. Actual UI menus also expose edge routing, GraphML download, cloud service buttons and PNG/SVG/PDF export. It is not assumed to have a configured MCP.

`assets/drawio/korean-layout.graphml` is an actual yEd Live export after importing three editable rounded nodes, checking the Korean font, correcting node labels to centered placement and applying the hierarchical layout. Native export/readback checked three nodes, two edges, font-family data and center placement. A native PNG export was visually verified. The user’s other graphs were not replaced. The sample is [stored in school Drive](https://drive.google.com/file/d/1Bmo832wel7fV36-_VLNSvRp2q-rA134x/view); yEd cloud OAuth is separate from connector storage.

The yEd Live menu links to [yFiles App Generator](https://www.yworks.com/products/app-generator). It can generate HTML/JS, React, Vue and Angular visualization source. Generated apps require a valid [yFiles for HTML license](https://docs.yworks.com/yfiles-html/dguide/deployment/licensing.html). No license purchase, evaluation agreement or deployment was performed. Use it for a specifically requested graph app with appropriate authorization. draw.io Desktop also supports native HTML export for simpler diagram viewing; do not imply that every HTML visualization needs yFiles.

## Proportional completion checks

- Native .drawio: all 36 pages/library items, unique element IDs, valid connector references and consistent Korean font style; remote raw readback must match the uploaded file.
- Native rendering: representative flow, architecture, rounded comparison and sequence; inspect new layouts when actually used. Structural coverage is not exhaustive visual approval.
- yEd: import → layout → native GraphML download/readback → PNG inspection. The verified sample does not imply automatic equivalent conversion of all draw.io pages.
- Connection status, local save, cloud save, other-device sync and user understanding are distinct claims. Preserve drafts and disclose the observed gap if any stage fails.
