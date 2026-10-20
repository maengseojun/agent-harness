# Spec/Plan: collect skills keep the vault text-only

Vault rule 2026-10-21 (`rules/자료와쓰기.md`, "바이너리는 Drive에").

- AC-1: `obsidian-workspace/scripts/vault_drive.py` stores one binary at Drive `maeng-archive/vault-offload/<vault-relative path>` (immutable, sha256 readback, `manifest-*.json`) and prints its `file://` URL; same file types as `vault-maint/offload.py`.
- AC-2: `convert_source.py --apply` puts the original (Office, PDF, full HTML page) on Drive and only `converted.body` + `receipt.json` in the vault; it stops before vault writes when Drive is missing.
- AC-3: HTML conversion keeps `<main>`/`<article>` and drops nav/header/footer/aside/form/script/style and menu/sidebar/comment/ad/share/related/cookie blocks. No new dependency (defuddle not needed: the existing HTMLParser route covers it).
- AC-4: `sync_project.py` refuses binaries with `binary_to_drive` before any vault write.
- AC-5: aside-collect asks Aside for body Markdown only and routes any kept file through `vault_drive.py`.
- Check: `python3 -m unittest` in both skills' `scripts/`; `test_web_capture_keeps_body_markdown_and_sends_original_to_drive` shows a web capture saved body-only with nothing but `converted.body` and `receipt.json` in the vault.
