# Personal installation and maintenance

Use the reviewed source pair `explainer` + `diagram-explainer`. Source files alone are not an installation. The supported personal update route is:

```sh
python3 <source-explainer>/scripts/install_bundle.py --codex <verified-codex-cli> --receipt <private-output>/installation.json
```

The installer stages each folder, preserves unknown user files, removes the explicitly listed retired local format/skin files listed in the installer, keeps previous versions outside discovery, and compares every source file with the installed copy. Both skills remain siblings so their shared references resolve.

With `--codex`, it uses the official app-server `skills/config/write` name selector to persist `excalidraw-style` disabled, then reads `skills/list` with forceReload. This survives an upstream installer recreating its folder/symlink: the skill stays excluded by name. It does not edit team source or uninstall other eta skills. Re-run this supported update after a source change and verify the installed manifest. Do not infer future behavior from a warning alone.

For rollback, `--restore <receipt-backup>` restores the previous folders and preserves the replaced version in the backup too. The intentional Excalidraw exclusion remains. Re-enabling Excalidraw is a separate user decision, using the same official configuration endpoint with enabled=true; restoration of diagram files is not permission to change that preference.

Use a fresh Codex session to verify discovery, the shared reference checks and a real request. An already-running session may retain its initial catalog. Actual HTML/SVG rendering, font/device availability and remote save each require their own evidence.
