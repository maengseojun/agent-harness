# MAE-256 Spec/Plan-lite: graphify-repository indexes Solidity

Linear: MAE-256. Date: 2026-10-20. Small work, no tree.

Goal: commit the `.sol` entry that an uncommitted release-clone edit already shipped in the maeng-tools 0.2.0 cache (found in MAE-255). User decision: "커밋정식화". The pinned graphify 0.9.85 extracts `.sol` (`graphify/extract.py` maps `.sol` to `extract_solidity`).

- **AC-1** `index_repository.py` CODE includes `.sol`, byte-identical to the shipped release-clone file; a test proves `select` admits a `.sol` file and fails without the entry.
- **AC-2** The rest of the indexer tests still pass.

## Verification

Verification tier: code. Ship checks, once at the final tree:
- AC-1: python3 -m unittest discover -s plugins/maeng-tools/skills/graphify-repository/scripts
- AC-1: test_select_admits_solidity fails when the .sol entry is removed
- AC-2: python3 -m pytest -q

After merge (not a gate): in the release clone, confirm the local edit equals the merged file, discard it, `git pull --ff-only`; no reinstall needed because the 0.2.0 cache already holds this exact file.
