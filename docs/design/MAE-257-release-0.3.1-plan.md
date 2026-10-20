# MAE-257 release: maeng-harness 0.4.1, maeng-tools 0.3.1

Goal: PR #60 (gdrive store defaults to the school Drive) reaches new sessions; the plugin cache is keyed by version.

AC-1: plugins/maeng-harness/.claude-plugin/plugin.json version is 0.4.1 and plugins/maeng-tools/.claude-plugin/plugin.json version is 0.3.1; both stay valid JSON. Check: `python3 -m pytest -q` passes.
