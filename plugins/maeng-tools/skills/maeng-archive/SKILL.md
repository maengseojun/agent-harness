---
name: maeng-archive
description: Move old or bulky vault material to cold storage (OneDrive archive, Google Drive and OneDrive backups) and restore it. Use whenever the user says 아카이브, 보관, 백업, 정리해서 치워, 오래된 맥락 옮겨, archive, backup, cold storage, restore, or when the vault carries distilled-away raw dumps, superseded notes or old transcripts that should leave the hot tier. Also use to search or read files kept in Google Drive.
---

# maeng-archive

The Obsidian vault is the **hot** tier: what the LLM reads. OneDrive and Google Drive (Korea University accounts) are the **cold** tier: kept, never loaded into context. This skill moves material between them without losing anything.

Script: `scripts/archive.py` (stdlib, Python 3.11+). Run it as `python3 <skill-dir>/scripts/archive.py <command>`. Add `--json` for machine output.

## Tiers

| Tier | Where | Holds |
|---|---|---|
| Hot | Obsidian vault (`MAENG_VAULT`, default `~/Documents/Obsidian Vault`) | notes, stubs, wiki |
| Cold archive | OneDrive `maeng-archive/<world>/<YYYY>/<vault-relative path>` | originals moved out of the vault |
| Cold backup | Google Drive and OneDrive `maeng-backup/maeng-<timestamp>.zip` + manifest | snapshots of vault and harness state |

Store roots are auto-detected (`~/Library/CloudStorage/OneDrive-*`, `GoogleDrive-*/My Drive`) and can be set with `MAENG_ARCHIVE_ONEDRIVE`, `MAENG_ARCHIVE_GDRIVE`. Harness state defaults to `~/.local/share/maeng-harness` (`MAENG_HOME`).

## When to archive

Archive only after the key points were distilled into notes. Candidates:
- Bulky raw or `raw/aside/` dumps whose substance now lives in a wiki note.
- Superseded notes and old transcripts.
- Source originals (PDFs, exports) whose conversion note already exists.

Do not archive anything still being edited, anything no note summarizes yet, or notes other notes depend on for content. Ask the user for a list of candidates before moving more than a few files.

## Commands

1. `status`: shows which stores were found, free space and the last backup per store. Run it first. A missing store is reported, not an error.
2. `move <vault-relative-path> [--store onedrive|gdrive] [--world personal|eta] [--dry-run]`
   - Always `--dry-run` first and show the destination.
   - Copies to the store (temp file, fsync, rename), verifies sha256, and only then replaces the vault file with a stub. A `.md` keeps its name; any other file gets a sibling `<name>.archived.md` and the original is removed after verification.
   - Aborts with the vault untouched on hash mismatch, missing store, or a destination with a different hash. Re-running is safe (idempotent).
3. `backup [--to onedrive,gdrive] [--keep N] [--dry-run]`: zips the vault (minus workspace state, `.trash`, `.DS_Store`, cache dirs) and harness state, writes a manifest of sha256 hashes, verifies the zip, and prunes beyond N (default 10) only after verification. Missing stores are skipped with a message; tell the user which backup copy is missing.
4. `restore <stub-path|backup-zip> [--apply] [--target DIR]`: dry run by default.
   - Stub: copies the archived file back after a hash check; with `--apply` the stub is kept as `<name>.restored.md`.
   - Zip: lists what it holds. `--apply` needs `--target`, which must be outside the live vault; it refuses to overwrite files.

## The stub and your job

The stub keeps the original frontmatter, adds `status: archived` and `archive: {store, path, sha256, size, archived_at}`, and a link line to the archive path. Its body contains a placeholder comment under `## Summary`.

**You must fill the summary** right after each move: read the original (still in the archive, or before moving), write 3 to 5 lines on what was here and why it was archived, using Obsidian MCP `patch_note` or `write_note`. A stub with the placeholder still in it is unfinished work. Keep existing links in the stub intact.

## Rules

- Never delete without a verified copy. The script enforces this; do not delete vault files or archive copies by hand.
- The cold tier is never the only copy of anything essential: stubs stay in the vault, and backups go to both clouds when both are available.
- eta material is allowed: use `--world eta`, keep it under `eta/` in the vault, and the stub carries `world: eta`. Never mix eta and personal archive paths.
- Respect `<private>` rules: backups exclude any file containing a `<private` tag (listed under `excluded_private` in the manifest, warning printed, originals untouched). Backup aborts, with no pruning, if the vault root is missing or has no `.md` file; the harness root is optional but reported. Moves and restores refuse symlinked paths and anything resolving outside the vault, and a binary move refuses to overwrite an existing `<name>.archived.md` unless it is a stub for the same sha256. Do not `move` a note that contains `<private>` text.
- Do not write to the vault or cloud folders outside these commands. Restoring a backup never overwrites the live vault in place.

## Searching and reading Google Drive

Cold files in Google Drive are found and read with the claude.ai Google Drive connector tools (`search_files`, `read_file_content`, `download_file_content`, `get_file_metadata`), not through the local sync folder. OneDrive archive files are read from the local sync path recorded in the stub. Summarize what you read into a note; do not paste whole files into the vault.

## Workflow

1. `status`; confirm stores.
2. Choose candidates and confirm that their content is distilled.
3. `move --dry-run`, then `move`; fill each stub summary.
4. Periodically `backup` (before big refactors or deletions); check the reported result for both stores.
5. To bring something back: `restore <stub>` (dry run), then `--apply`.
