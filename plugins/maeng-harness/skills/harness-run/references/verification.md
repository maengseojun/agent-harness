# Verification and self-recording

The hooks track this for you; know the rules so you satisfy them on the first try.

## Evidence

A recognized command (pytest, `python -m unittest`, npm/pnpm/yarn test|lint|build|typecheck, forge, cargo, go test, make test|check, ruff, mypy, tsc, `claude plugin validate`, playwright test) produces evidence `{cmd, ok, tree_start, tree_finish}` only if the working tree did not change during the run. Do not edit files while a check runs; background commands produce no evidence.

Prefer `maeng-verify exec -- <runner ...>` (e.g. `maeng-verify exec -- python3 -m pytest -q`): the CLI itself runs the allowlisted runner (no shell, current directory), streams its output, exits with its exit code, and records runner evidence with the same identity as the hook path. Anything that is not an allowlisted runner is refused (exit 2). Runner evidence also counts only when the tree is unchanged during the run, and options that disable execution (`go test -count=0`, `-run '^$'`, empty `-k`/`-m`) are not evidence.

A declaration never satisfies a runner requirement: if a required check is itself a recognized runner command (`pytest`, `go test ./...`, ...), only runner evidence (hook-recorded or `maeng-verify exec`) satisfies it. For free-text checks that are not runners (screenshot, dry-run, manual probe) declare them: `maeng-verify ran --ok|--fail "<what>"`. A check with no runner in it is matched as one literal string (punctuation such as `( ; &&` included), so declare its exact text. Record an AC result: `maeng-verify plan --met AC-1,AC-2 --unmet AC-3 "<notes>"`. `maeng-verify skip "<reason>"` records a skip.

If the session state file becomes unreadable, gates deny (the file is never replaced by fresh state) until you run `maeng-verify state --quarantine` and restart the session; quarantine leaves a tombstone so every tool call of that session is denied (whatever the directory) until the restart.

## Required checks (precedence)

1. The bound Plan's `Verification` section.
2. Else the repo policy `.maeng/verify.json` `required`.
3. Else at least one recognized test runner.

## States

- **Ship-verified**: every required check has ok evidence at a tree equal to the current one (differing at most in non-code paths such as docs and images); no unresolved failure; with a plan bound, the latest plan record marks every current `AC-n` met and matches the plan's current `updatedAt`.
- **Stop-satisfied**: ship-verified, or an explicit skip.
- A skip never makes a tree ship-verified: pushing, `gh pr create` and `maeng-ship merge` stay blocked.
- Any code edit after the evidence (even a formatter) invalidates it; rerun.
- A changed dependency or build input (`requirements*.txt`, lockfiles, `CMakeLists.txt`) invalidates earlier evidence. A dirty submodule yields no evidence.

## Stop

If something is missing, Stop blocks once with the full list. After that it lets you stop with a visible "UNVERIFIED / UNRECORDED" message and keeps the state. Fix it rather than relying on that.

## Self-recording

After the last substantive change of a turn (a code change, a commit, a decision), write a record for the bound issue: a Linear comment or document update on that issue, or an Obsidian note whose frontmatter `linear` includes it. With no binding, any Linear or Obsidian write after the change counts. Question-only turns need nothing. A "starting work" comment followed by more changes still needs a later record. The session stub in `wiki/sessions/SESSION-<MAE-or-none>-<YYYYMMDD-HHMM>-<session_id[:8]>` is written by the Stop hook; add decisions and results yourself.

## How evidence is recorded
- A check counts only when a recognized test runner runs **as one plain command** (for example `python3 -m pytest -q`, `npm test`, `forge test`). Pipes (`| tail`), `;` and `&&` hide the runner's exit status, so those runs are not evidence; run the check by itself, then inspect output separately.
- The working directory is part of the check: `cd tests/unit && pytest` does not satisfy a root-level `pytest` requirement.
- `--version`, `--help`, `--collect-only` and similar no-run invocations never count.
- Evidence is an **allowlist of runner invocations**: an unlisted flag makes a run not count (for example `pytest --cov`, `make -n test`, `go test -list .`, `cargo clippy -- -D warnings`). Use the plain forms (these satisfy the default rule): `python3 -m pytest [-q|-v|-x]`, `python3 -m unittest discover [-s DIR] [-t DIR]`, `npm|pnpm|yarn test` (also `t` or `run test`), `npm|pnpm|yarn run lint|build|typecheck` (yarn also without `run`; `npm lint`, `pnpm build` and the like do not count), `forge test|build`, `cargo test [--all|--workspace|--all-features|--release|-q]`, `cargo clippy|build [--all|--workspace|--all-features|--release|-q|-p X]`, `go test ./... [-race] [-v]`, `make test|check`, `ruff check [paths]`, `mypy [paths]`, `tsc [--noEmit] [-p X]`, `claude plugin validate PATH`, `playwright test`. Requirements written in Plans should use these forms too. A compound Plan requirement (`a && b`) is allowed, but each constituent that is a runner must be a plain runner command executed separately and recorded as runner evidence (for example one `maeng-verify exec -- <runner>` per constituent); a wrapper (`env`, `sudo`, `nice`, `time`, `command`, ...) or an unsafe/variable assignment makes a run not count.
- Narrowing flags are never evidence (`pytest --ignore|--deselect|--lf|--ff|--last-failed|--failed-first`, `go test -short`, `cargo test -- --skip`); filtered forms (test paths, `pytest -k|-m`, `unittest discover -p PAT`, `go test -run`, `playwright test <paths>|--project X`, `forge --match-*|--no-match-*`) are evidence only for a Plan requirement that names them, never for the default "some passing tests" rule. Filtered as well: `cargo test TESTNAME|--lib|--doc|--bins|--tests|--test X|--bin X|-p X|--package X` (recorded, but a package-scoped `cargo test -p X` counts only for a Plan requirement that names it). Not evidence at all: `npm|pnpm|yarn test -- ...` passthrough, and `make` with `VAR=val`, `-C`, `-f`, `-n`, `-k`, `-i` or any other flag (only plain `make test|check`).
- A run whose output shows that zero tests ran (`Ran 0 tests`, `collected 0 items`, `no tests ran`, `no test files` with nothing else passing) is not evidence, and a PostToolUse response marked interrupted, errored or with a non-zero exit code is recorded as a failure.
