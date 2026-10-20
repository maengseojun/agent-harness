# Claude edition rules (two-world vault conventions)

Contents: [World rule](#world-rule) · [Folders and ids](#folders-and-ids) · [Frontmatter keys](#frontmatter-keys) · [Retrieval](#retrieval-3-layers) · [Private and redaction](#private-and-redaction) · [Write rules](#write-rules)

## World rule

Reading the whole vault is allowed in both worlds. When the session is in the **eta world** (the guard says eta, or the repo is under `eta_v1`, its worktrees, or an `endix-foundation-v1`/`maengseojun/eta_v1` origin):

- every note you write has `world: eta`;
- file it under `hubs/projects/P-ETA.md` and `wiki/sessions/` (or the matching wiki folder), linked from that hub;
- never promote it to personal Notion. A personal Linear issue may link it as a reference (user decision 2026-10-19), but the eta work record stays in eta's own tools, by eta rules;
- no personal record flows (work-records, personal Notion) run in the eta world.

In the personal world write `world: personal`. If you cannot tell which world you are in, ask or write nothing.

Recorded conflict (user decision 2026-10-17): eta rule OPS-A1-12 says nothing about eta is kept outside the teamspace; the user chose full local eta logs in the personal vault anyway. The authoritative eta record stays in eta Docs and eta Linear.

## Folders and ids

| Path | Holds | Unique id |
|---|---|---|
| `wiki/decisions/` | ADRs | `ADR-<MAE-id>-<slug>` |
| `wiki/drafts/` | Notion-bound drafts | `DRAFT-<MAE-id>-<slug>` |
| `wiki/reviews/` | review verdicts | `REV-<MAE-id>-<YYYYMMDD-HHMM>-<digest7>` |
| `wiki/sessions/` | session logs | `SESSION-<MAE-id or none>-<YYYYMMDD-HHMM>-<session_id[:8]>` |
| `wiki/sources/` | sources (also written by aside-collect) | `S-<slug>` |

The `id` equals the filename without `.md`. New files get a new id; never reuse one for a different note. Sessions and reviews include a timestamp plus a short digest or session id so concurrent writers never collide. Replacing an existing note first compares its current hash with what you read. The shared `log.md` is appended only by you, through MCP.

## Frontmatter keys

Existing keys stay. New keys: `linear` (issue ids, list), `world` (`personal` or `eta`), `notion` (published page URL), `commit` (SHA or PR URL), `session` (Claude session id), `audience` (list of reader ranks: `ceo`, `director`, `auditor`, `exec`, `team`, `junior`; see harness-run `references/org-chart.md`), `closed` (project hubs only: `YYYY-MM-DD` when the CEO declared the project finished or its Linear parent went Done). Omit keys that do not apply; do not write empty ones. The self-recording check counts an Obsidian write for a bound issue only if `linear` includes it.

## Retrieval (3 layers)

0. **Your rank first:** start from `hubs/areas/A-ORG.md` and the notes whose `audience` includes your rank. `audience` orders reading; it never hides a note, so widen whenever the work needs more.
1. **Compact index:** `wiki/index.md`, the hub, and `search_notes` / QMD results (id, title, path, one line). Do not read bodies yet.
2. **Timeline:** for the candidates, read the frontmatter and the latest dated entries (session notes in order; `read_note_lines` for a bounded range).
3. **Fetch by id:** read the full note only for the few ids that matter, plus the source behind a claim you will rely on.

Resume order: hub, latest session for the bound issue, linked decisions. Keep any SessionStart-style summary under 2 KB. Never inject the whole vault.

## Private and redaction

- Anything inside `<private>...</private>` is never written to the vault, QMD snapshots, Linear or Notion. Treat the tag as authoritative even inside quoted material.
- Before a vault write run the draft through `scripts/private_filter.py` (stdin to stdout). Pass `--patterns <file>` with `[{"name","pattern"}]` for opt-in regex redaction (API keys, tokens, emails); without it only `<private>` spans are removed. An unclosed `<private>` drops everything after it.
- Raw captures that contain account chrome (for example `raw/aside/`) stay in `raw/` and are not promoted.

## Write rules

New files get unique ids (above); full-note writes pass the whole prepared Markdown as `content`; read the target right before writing; read it back after. One writer for shared hub/index/log notes. Session stubs are written by the Stop hook; add decisions and results to the session note or an ADR yourself.

## Cold storage

Old or bulky material leaves the vault through the `maeng-archive` skill: `move` replaces a file with a hash-verified stub (fill its `## Summary`), `backup` snapshots the vault and harness state to Google Drive and OneDrive, and `restore` is a dry run by default. Stubs have `status: archived` and an `archive:` block; treat them as pointers, not content, and never edit the archive path by hand. eta material is archived with `--world eta` and keeps `world: eta`. See `../../maeng-archive/SKILL.md`.
