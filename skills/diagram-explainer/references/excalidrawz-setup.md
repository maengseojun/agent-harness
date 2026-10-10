# ExcalidrawZ local setup

Verified on this Mac on 2026-10-10. Treat this as a dated installation record; inspect current tool availability before using it.

## Connection

- App: `/Applications/ExcalidrawZ.app`, MCP server identifies itself as ExcalidrawZ 2.4.4.
- Codex configuration: `/Users/maengseojun/.codex/config.toml`, section `[mcp_servers.ExcalidrawZ]`, `url = "http://127.0.0.1:8490/mcp"`. TOML parsed and the saved entry read back successfully.
- ExcalidrawZ Settings → AI → Settings → MCP is enabled. The app must be running; closing it stops the endpoint.
- `initialize` and `tools/list` succeeded over HTTP. Basic mode exposes `read_me`, `create_view`, `save_checkpoint`, `read_checkpoint`. Do not claim full file editing from this discovery.
- The current chat now exposes ExcalidrawZ tools. Earlier in setup, the newly added server was not yet registered in that chat. Reconnect/reload MCP in Codex or use a new chat if missing; do not restart the user's whole application without preserving their work.
- The app documents an optimized mode with file selection, editing, library insertion, visual inspection and export. Its public source gates this mode on `Store.canUseOptimizedMCPServices`. On this installation, attempts to select it left the server in basic mode. No purchase or entitlement change was made. Do not bypass this gate or pretend optimized tools are exposed.

## Observed blocker

The first full-scene `create_view` request timed out after 40 seconds. A subsequent minimal request with one rectangle and an English label returned JSON-RPC error `-32603`: **The MCP target file did not finish loading in ExcalidrawZ.** Opening a generated scene displayed **JavaScript 예외가 발생했습니다**. A retry and import with a reduced appState were attempted, but successful editable canvas load was not confirmed.

Therefore the HTTP connection is verified; actual MCP creation, in-app editing, library import and app-generated export are not yet verified. Native thumbnails and the failed-open background showed Korean text, but these do not prove a working editor. The failure also occurred with a minimal basic MCP request; this is not evidence that the Korean font alone caused it. Do not repeatedly re-run the same mutation, patch the app bundle, install Obsidian or switch output editors to conceal this blocker.

## Korean font

- Source article: [Excalidraw usage and font guide](https://abluesnake.tistory.com/166), dated 2023-07-16. Its fourth-font setting belongs to the Obsidian plugin and must not be copied into this standalone app.
- Official download: [Naver font collection](https://hangeul.naver.com/fonts/search?f=clova), [NanumDaHaengCe.ttf](https://hangeul.naver.com/hangeul_static/webfont/clova/NanumDaHaengCe.ttf).
- Installed at `/Users/maengseojun/Library/Fonts/NanumDaHaengCe.ttf`. macOS Font Book reported **설치된 서체** for **나눔손글씨 다행체**.
- Added through ExcalidrawZ Settings → Fonts → Add → search `다행` → select → Done. The app's Added fonts list separately showed **나눔손글씨 다행체**; screenshot: `assets/verification/font-settings.png` in this skill.
- The bundled renderer's font picker includes registered native family-name strings. Generated text uses `fontFamily: "나눔손글씨 다행체"`; this is installation-specific. Do not assume another renderer/device shares the same support. Readable native thumbnails were observed; successful full editor/exports still need verification after the canvas blocker is resolved.
- iCloud synchronizes diagram files, not proof that this font is installed on every device. Install/register a compatible font on each target device, then inspect Korean there. Do not promise identical web rendering.

## Storage and templates

Connected storage named `excalidraw` was visible in the app. Its local iCloud folder exists at:

`/Users/maengseojun/Library/Mobile Documents/com~apple~CloudDocs/excalidraw`

Outputs:

- `diagram-explainer/templates/`: 36 native `.excalidraw` teaching layouts.
- `diagram-explainer/templates/diagram-explainer.excalidrawlib`: all 36 grouped reusable items.
- `diagram-explainer/templates/index.json`: names, purposes and file names.
- `diagram-explainer/양식 안내.md`: catalogue, selection rules and research coverage.
- `diagram-explainer/font-validation.excalidraw`: a copied flow template with minimal appState used to isolate loading behavior.

Local files were written, parsed again, and appeared in the app's connected-storage/recent-file listing. Other-device sync was not checked. Preserve these masters; adapt copies in `diagram-explainer/outputs/` or another user-requested destination. Never overwrite edited diagrams when rebuilding templates.

For app library import, use the native Library panel's import controls and the `.excalidrawlib` file, when the editor is working. Check item count and insert one item into a new test scene; this has not yet been demonstrated. Existing native individual files remain available even before library import.

## Proportional checks after recovery

1. Open a newly created empty app file. Confirm it reaches an editable canvas before adding custom content.
2. Call the live basic `create_view` with one shape. Confirm successful result and the returned checkpoint; save/export if the app supports it. Do not confuse checkpoint persistence with iCloud file persistence.
3. Open the flow template and a table/sequence template. Inspect readable Korean, branch labels, connectors, clipping and native editing at usable zoom. Fix actual defects only.
4. Import the 36-item library and insert one grouped template. Preserve individual text/shapes/bindings.
5. Save a copied output into the connected iCloud folder; read back its native elements and open it again. Check a second device only if cross-device sync is part of the request.

Source references: [ExcalidrawZ repository](https://github.com/chocoford/ExcalidrawZ), [MCP mode entitlement gate](https://github.com/chocoford/ExcalidrawZ/blob/main/ExcalidrawZ/Utils/MCP/Runtime/ExcalidrawZMCPServerController.swift), [mode selection/paywall handling](https://github.com/chocoford/ExcalidrawZ/blob/main/ExcalidrawZ/Settings/AISettings/AISettingsView%2BMCP.swift). Public main can differ from the installed build; live responses above are the installation evidence.


## Design update — 2026-10-10

All 36 templates revised with the requested rounded rectangles and declared connector grammar. Six Blocks & Arrows source boards/visible portions inspected; design guide records provenance. Existing masters matched their original generated scenes before revision; originals backed up at /tmp/diagram-rounded-before. Native ExcalidrawZ tools are now exposed in this chat. Calling create_view with the revised architecture returned -32603: The MCP target file did not finish loading in ExcalidrawZ. This confirms the editor blocker remains even through the connected tool. No alternate editor was used.
