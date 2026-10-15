# Native Notion and Linear sources

Use an authorized connector or logged-in Aside read for one explicitly selected source. Do not re-OCR or replace a returned native body with a summary. This helper does not fetch services or edit source services.

## Receipt and preview

Create one UTF-8 JSON receipt outside the vault with exactly these fields:

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

Use actual timestamps; missing coverage remains unknown, never silently false. For Notion record the page ID, URL, reported last edited time, and the selected block/body coverage. Child page links do not prove their bodies, tables, or media were exported. An old response `as of` time differs from the current request time; cross-check or expose the freshness gap. Connector/Aside Markdown is a representation of the service, not an original local `.md` byte copy. For Linear preserve the native status at the returned revision; it does not establish team adoption or product completion.

No credentials/transport headers belong in a receipt. The helper rejects common sensitive field names, but this is not a general secret scanner. Inspect the selected receipt before capture.

```text
python3 -B scripts/source_snapshot.py --vault '/Users/maengseojun/Documents/Obsidian Vault' --receipt /absolute/selected-receipt.json --impact-note wiki/sources/S-LING-005.md --impact-note wiki/concepts/K-LINEAR-STATUS-HISTORY.md --impact-note wiki/answers/A-LING-001.md
```

Default is read-only preview. It shows body/revision differences and reads only exact listed source/concept/answer notes through Obsidian CLI. These are candidates selected by Codex; the helper does not infer semantic dependencies. Do not dump large bodies into user progress output.

## Apply and lineage

After presenting the change and affected-note candidates, apply only the selected or already authorized scope by adding `--apply`. Before it acts, the helper verifies the exact supplied folder and CLI target. Body attachments use `.body`; separate raw responses use deterministic JSON. Current-version metadata is in `raw/native-captures/catalog.json`. Identity includes service, source ID and exact URL; keep a source's URL stable across repeated captures. Same body/revision reuses captures; a new observation may update receipt metadata without duplicating body bytes. Same revision with different body fails. Earlier captures stay immutable. An old selected revision may become the pointer when explicitly applied, so verify source freshness before treating a pointer as latest.

After capture, Codex must create/update the source description and searchable native body note through the CLI, preserving old raw/conversion versions. Connect the source to hub/index/log, inspect actual claims and update only affected knowledge. Undemonstrated claims remain draft with a reason. Read each saved note back separately. Capture success is not semantic update success.

Large bodies travel in the explicit receipt/staging file, not command arguments. When a searchable note exceeds practical CLI argument size, CLI `eval` may load that explicitly selected staged input and call the application's vault methods; note control still uses the CLI. Do not read/edit vault notes directly with filesystem tools or use native UI.

On CLI, identity, coverage or conflict failure, keep the original state, inspect any reported partial capture paths, and reconcile before retrying. There is no whole-vault transaction or background sync.
