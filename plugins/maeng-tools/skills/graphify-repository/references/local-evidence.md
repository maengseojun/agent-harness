# Local AST execution and evidence

The Graphify source is NOT vendored in this repository. The pin is Graphify 0.9.85, commit `b4e6307bf170f27e0cb888c03f4af9308d531a42`, from https://github.com/Graphify-Labs/graphify (Apache-2.0). The runtime is an external checkout; `references/runtime-location.json` records where the author's machine keeps it (`runtime`, `python`, `version`, `revision`) and is marked `"portable": false`: those are absolute paths under the author's home folder and mean nothing on another machine. On any other machine, obtain the pinned revision yourself and pass its location with `--runtime`.

Trust comes from the manifest check, not from the location: `scripts/index_repository.py` computes a SHA-256 digest over the runtime's `graphify/` source files and refuses to extract unless it equals `PIN_SOURCE_SHA256` (a modified or different version fails before any extraction). No upstream installation skill is adopted. The skill contains no provisioned Python environment; saving it does not install Graphify dependencies.

Provision the reviewed runtime checkout with `uv sync --project <runtime> --python <verified-python-3.11-or-newer> --frozen --no-dev --no-install-project --no-build`. This is an explicit setup action, never an automatic skill step. Inspect the source first and obtain any action-time approval required by the current software-execution policy; a saved skill or a local-machine test does not authorize new upstream execution in another environment. It uses the upstream lock without resolving upgrades and permits wheels only. If the platform denies network/installation, stop that step and report the exact action. Use `<runtime>/.venv/bin/python` and the runtime source via the wrapper; project installation is unnecessary. Do not add optional LLM, media, database, MCP or watch extras. The source is pinned; updating it is a separate task.

Verify `git` and `uv` are available before the approved setup. Select Python 3.11 or newer explicitly: the upstream project permits 3.10 but this wrapper needs `tomllib`. Provision a new isolated runtime in the receiving environment; the recorded location is not portable. The worker uses Python 3.11+ (`tomllib`), tested with Python 3.12.7.

Resolve the installed skill by frontmatter name `graphify-repository`; set `SKILL_DIR` to its current absolute directory, which may be a generated cloud folder name. Set `GRAPHIFY_PYTHON` to the verified isolated Python interpreter created by the approved setup. Example after setup:

```sh
python3 "$SKILL_DIR/scripts/index_repository.py" --repo /absolute/repository --include src --exclude src/generated --out /absolute/new-index-folder --python "$GRAPHIFY_PYTHON" --runtime /absolute/graphify-runtime-checkout
```

Within diagram-explainer or interactive-explainer, invoke this helper only when the requested repository explanation benefits from repeated relationship extraction/reuse. A separate learner indexing request or `$graphify-repository` invocation is unnecessary. Preserve the existing explanation and native diagram workflow; Graphify supplies analysis clues, not a replacement authoring rule or verified answer.

Extraction results are cached in a persistent `cache_root`, default `~/.cache/maeng/graphify/<repo-hash>` (override with `--cache-root`). It lives outside the repository and outside every `--out` directory, so a new index reuses earlier per-file extraction work.

For the next explanation of the same scope, add `--previous /absolute/prior-index/snapshot.json`. If revision, selected-source hashes, scope, extractor settings and the **in-scope** Git status still match and no source extraction failed, the script returns the prior snapshot without parsing or creating a new output. A mismatch rebuilds into the new `--out` directory, recording the previous snapshot and preserving it. This is conservative snapshot refresh, not an upstream watch service or automatic network update. The dirty check covers only the included paths (minus excludes); changes elsewhere in the repository and the index and cache directories themselves do not invalidate reuse. Snapshots made before this change lack `status_scope: in-scope` and rebuild once. If resolver context outside the indexed files or installed dependencies changed, omit `--previous` to force a rebuild. Resolution context is not fully fingerprinted; every consequential relation still needs current source review.

The wrapper admits code extensions only, skips links and sensitive/generated directories, hashes selected files before and after extraction, and runs the AST worker with an allowlisted environment and temporary HOME. It calls `graphify.extract.extract`, never the CLI or semantic extractor. Resolver reads can consult project manifests/neighboring source for resolution; this is not an OS sandbox. Use a reviewed code-only staging copy if the requested boundary forbids those contextual reads. No keys are read or passed. No project Python/JavaScript is imported or executed. JSON output and cache go to the new index directory. `snapshot.json` retains raw nodes and edges, file hashes, revision, dirty status, included/excluded scope and errors. The dirty status records all Git changes but does not copy their content.

Limitations: code-only extraction does not establish runtime order, deployment topology, author motivation, or documentation meaning. A missing source line remains missing. Cache fingerprints are not a substitute for current source checks. For working-tree changes, cite the hash-bearing working snapshot; a commit URL points to committed content and can be misleading.

## Tests

`python3 -m unittest` in `scripts/` runs `test_index_repository.py` offline: graphify is not installed and the worker (`run_worker`) is mocked. It covers the persistent cache root, reuse, the in-scope-only dirty check, scope selection and the unchanged pin.

## Version bump (not done)

The pin stays at Graphify 0.9.85 (commit `b4e6307bf170f27e0cb888c03f4af9308d531a42`). The Phase 2 plan is to move to 0.9.91, but only after re-checking the revision gate: identify the 0.9.91 commit, review its diff and lockfile, confirm `graphify.extract.extract(files, root=, cache_root=, parallel=)` is unchanged, obtain the reviewed source and recompute `PIN_SOURCE_SHA256`, then change `PIN_VERSION`/`PIN_REVISION` together in `scripts/index_repository.py` (see the TODO there) and rerun the tests plus one real index. Nothing was downloaded for this task.
