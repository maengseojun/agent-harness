# Hosting CLI compatibility

SessionStart observes the host-designated executable, compares it with
`plugins/maeng-harness/policy/cli-compatibility.json`, and records pending work
in the session's `cli_compatibility` state. It never runs tests. A mismatch or
unknown version emits one `systemMessage` line per session/version, including
one for `unknown`. Repeated startup/resume calls retain the notice history.
Matching known versions add no notice. Unknown never counts as verified.

## Observation evidence

Inspected on 2026-11-08:

- `hooks/maeng_hooks.py` reads stdin JSON and passes it unchanged to
  `handlers.on_session_start`. `tests/helpers.py` supplies `hook_event_name`,
  `session_id`, `cwd` and caller-provided fields; it supplies no version.
- The locally installed Claude Code 2.1.314 and embedded 2.1.317 artifacts
  construct SessionStart input with `session_id`, `transcript_path`, `cwd`,
  `source`, `model` and optional context fields. The inspected common input
  and SessionStart constructor do not supply a CLI version. Hook spawning
  inherits the process environment, then adds hook/plugin variables such as
  `CLAUDE_PROJECT_DIR`, `CLAUDE_PLUGIN_ROOT` and `CLAUDE_ENV_FILE`.
- The current inherited `CLAUDE_CODE_EXECPATH` names the desktop's versioned
  2.1.317 executable. Running that exact absolute path with `--version`
  returned `2.1.317 (Claude Code)` (exit 0, about 0.013 seconds). In contrast,
  PATH's `claude` resolves to the separate 2.1.314 installation. PATH lookup
  would therefore identify the wrong CLI in this environment.
- `CLAUDE_CODE_VERSION` was absent from this inherited environment. In the
  inspected artifacts its explicit version injection belongs to a policy-helper
  subprocess; that does not establish it as an ordinary hook variable. The hook
  does not trust that variable or an invented payload version field.
- A real bundle 2 subagent transcript contains top-level `version: "2.1.314"`
  and the matching `sessionId`, as also read by `tools/testperf/subagent_context.py`.
  A new SessionStart can precede transcript creation, and a resumed transcript
  can contain the previous process's version. Transcript contents are therefore
  not used to assert the current host version.

The implemented source is **`CLAUDE_CODE_EXECPATH --version`**, using an argument
list without a shell or PATH fallback. It accepts only an absolute path,
exit 0 and a complete `<version> (Claude Code)` response. The subprocess has a
one-second timeout within the hook's five-second budget. Missing, relative,
unavailable, timed-out or malformed results remain unknown and pending.

This establishes the version of the executable designated by the host environment,
not an authenticated identity of every possible parent process. A wrapper that
strips or supplies a stale executable path remains a detection limitation. No
fresh Claude session/provider call was launched to capture raw hook stdin;
the input/environment findings above come from existing code, fixtures,
inherited runtime metadata and the installed artifacts. Recheck the contract if
the host changes how it launches hooks or replaces executables in place.

## Explicit verification

From the repository root, after SessionStart has recorded a known host:

```sh
python3 tools/testperf/cli_compat.py verify --session <session_id>
```

`MAENG_SESSION_ID` can supply the session ID instead. The command consumes that
session's observed version; it does not substitute the CLI found on PATH or a
user-supplied version string. It marks compatibility pending, then runs, in order:

1. `python3 -m pytest -q plugins/maeng-harness/tests/test_boundary.py`
2. `python3 -m pytest -q -n 8`

`PYTEST_ADDOPTS` is cleared so ambient selection flags cannot narrow these runs.
Each run must exit 0 and report a known positive executed-test count. Skipped
tests are excluded. Failed, zero, all-skipped, missing-runner, unknown-count or
timed-out checks retain the prior policy bytes and pending work; a failed smoke
does not launch the full suite. The default timeout is 900 seconds per run and
can be set explicitly with `--timeout`.

Only both successful checks permit an atomic policy replacement. The record
binds the observed version/source/time, plugin revision, check time, exact
commands, exit codes, executed counts, durations and output digests. The plugin
revision is a SHA-256 of plugin file names/bytes plus this runner, including new
and uncommitted files, excluding this self-updating policy and Python/pytest
caches. No git index is changed. A source revision or session observation change
during the checks refuses publication. Pending clears only after policy writing
succeeds. Check output is hashed rather than retained as full logs.

The initial `2.1.314` value is a historical seed, supported by top-level
`cli_version` in `docs/design/MAE-323-b2-context.json`. The bundle 2 report records
805 full-suite passes and 802 process-mode passes (3 skipped). The seed leaves
revision, time and check details null rather than inventing a newly bound run.
The integration lead must run the explicit command before claiming fresh
compatibility evidence for this implementation or the observed 2.1.317 host.
