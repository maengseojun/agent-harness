# Verification and self-recording

The hooks track this for you; know the rules so you satisfy them on the first try.

## Evidence

A recognized command (pytest, `python -m unittest`, npm/pnpm/yarn test|lint|build|typecheck, forge, cargo, go test, make test|check, ruff, mypy, tsc, `claude plugin validate`, playwright test) produces evidence `{cmd, ok, tree_start, tree_finish}` only if the working tree did not change during the run. Do not edit files while a check runs; background commands produce no evidence.

Prefer `maeng-verify exec -- <runner ...>` (e.g. `maeng-verify exec -- python3 -m pytest -q`): the CLI itself runs the allowlisted runner (no shell, current directory), streams its output, exits with its exit code, and records runner evidence with the same identity as the hook path. Anything that is not an allowlisted runner is refused (exit 2). Runner evidence also counts only when the tree is unchanged during the run, and options that disable execution (`go test -count=0`, `-run '^$'`, empty `-k`/`-m`) are not evidence.

A declaration never satisfies a runner requirement: if a required check is itself a recognized runner command (`pytest`, `go test ./...`, ...), only runner evidence (hook-recorded or `maeng-verify exec`) satisfies it. For free-text checks that are not runners (screenshot, dry-run, manual probe) declare them: `maeng-verify ran --ok|--fail "<what>"`. A check with no runner in it is matched as one literal string (punctuation such as `( ; &&` included), so declare its exact text. Record an AC result: `maeng-verify plan --met AC-1,AC-2 --unmet AC-3 "<notes>"`. `maeng-verify skip "<reason>"` records a skip.

If the session state file becomes unreadable, gates deny (the file is never replaced by fresh state) until you run `maeng-verify state --quarantine` and restart the session; quarantine leaves a tombstone so every tool call of that session is denied (whatever the directory) until the restart.

## Evidence ranking

Rank: runner > declared > agent report.

- `runner`: the harness ran it (hook-recorded or `maeng-verify exec`) and the tree did not change. This is the only rank a ship check accepts.
- `declared`: `maeng-verify ran`. It cannot replace a runner check, the full-suite ship check or a count of executed tests. It covers only free-text checks that no runner can run.
- `agent report`: a sub-agent's `Verification:` section. It is a claim; the coordinator re-runs the row's Done.
- Zero executed tests are not evidence, however the exit code reads. A count the runner did not print is `unavailable`, never zero.
- Impact runs (`python3 plugins/maeng-harness/tests/impact.py run`) are working checks. They are never ship evidence and never satisfy the full-suite requirement.
- Flaky: when one check shows both an ok run and a failed run on the same tree, record it as flaky. Keep the failed run on record next to the pass.

## CI observation (D-14: Later small PR)

Sunday 00:00 UTC and manual dispatch run the separate periodic lane; push/PR runs keep the gate lane. Periodic artifacts never satisfy or block the gate aggregate. Before closing periodic wiring, retain one actual scheduled/manual run with nonzero mutation execution and successful restoration/cleanup.

The aggregate remains informational. A separate follow-up PR may add the `maeng-ship` read only after 2026-11-21, a full 14 days from the first plugin-suites run (later if needed), and explicit user judgment of a nonempty sample. Record runs and attempts separately, suite counts and classified causes; preserve first failures, same-head flaky reruns and unresolved failures. Require fixes/readbacks, no unresolved infrastructure/flaky failures, and verified triggers, published check name and exact-head matching. If approved, read the exact head's gate aggregate before receipt reservation; missing, stale, pending, cancelled, skipped, malformed, failed or unreadable results refuse merge. Ordinary code-test failures still refuse merge.

Request user-authorized reversal to informational mode for a false green, a trigger/name change leaving eligible heads without checks, or repeated infrastructure/flaky failures blocking unchanged heads after a confirmed passing rerun. Record the cause, affected runs, authorization and reconsideration evidence. Local full verification, quiz, receipts and lease protection remain required; never silently ignore CI.

## Test trust

- Expected values come from the AC or another independent source, never from running the code under test.
- The Plan's `Fails-if` names the negative paths: null, empty, negative, exception.
- A bug fix starts with a failing reproduction, kept as a test.
- Run each new test once against the base code. The result is informational: a test that passes on the base is reported, not blocked.
- Pin values the code reads (field names, flags, enum values), not English sentences.

## Required checks (precedence)

1. The bound Plan's `Verification` section.
2. Else the repo policy `.maeng/verify.json` `required`.
3. Else at least one recognized test runner.

## Verification tiers (scale the checks to the risk)

Write the tier into the Plan (`Verification tier:` line, see spec-plan.md) and name only the ship check in `Verification`. Checks you run while working are feedback, not evidence; the gate reads only the ship check at the final tree.

| Change | While working (after each edit) | Ship check (Plan `Verification`, once at the final tree) |
|---|---|---|
| **Docs only**: every changed path matches `non_code_globs` | nothing | nothing new: evidence at the last code tree still holds, because non-code paths never invalidate it. With no earlier evidence, run the default check once (a `maeng-verify ran` declaration counts only for a Plan `Verification` line with that literal text) |
| **Code** | the affected tests only (a repo's impact selector, e.g. `python3 plugins/maeng-harness/tests/impact.py run`, or the test files that cover what changed) | the full suite once |
| **Gate code**: anything a gate decision runs through (lib/maeng, hooks/, bin/ here) | the affected tests | the full suite once (it includes the real-process boundary tests); also before merge, the suite with `HARNESS_TEST_PROCESS=1` when the hook or CLI entry points changed |

- Review rounds: fix findings with the affected tests, then run the ship check once before asking for the next review (the receipt binds the exact head anyway). Do not re-run the full suite for each finding.
- A lightened check is a Plan change: update the Spec and the Plan together, and say what was not re-run.
- Evidence matches the Plan's check text literally: a Plan naming `python3 -m pytest -q -n 8` (parallel, needs `requirements-dev.txt`) is not satisfied by a serial run, and the other way round. Name the form you will run. Without a bound Plan, only an unfiltered runner command counts: a test path operand, `-n auto` or a run from a subdirectory makes it partial.
- This repo's ship check is `python3 -m pytest -q -n 8` from the repo root; the root `pytest.ini` limits it to `plugins/maeng-harness/tests`.

## States

- **Ship-verified**: every required check has ok evidence at a tree equal to the current one (differing at most in non-code paths such as docs and images); no unresolved failure; with a plan bound, the latest plan record marks every current `AC-n` met and matches the plan's current `updatedAt`.
- **Stop-satisfied**: ship-verified, or an explicit skip; otherwise Stop gives the notice above.
- A skip never makes a tree ship-verified: `maeng-ship merge` stays blocked.
- Any code edit after the evidence (even a formatter) invalidates it; rerun.
- A changed dependency or build input (`requirements*.txt`, lockfiles, `CMakeLists.txt`) invalidates earlier evidence. A dirty submodule yields no evidence.

## Stop

Stop notifies and never blocks. If verification or a record is missing, it stores an "UNVERIFIED / UNRECORDED" notice that the next prompt receives as model context, and keeps the state: the notice does not clear the missing work. Review entry (`maeng-review`) and merge (`maeng-ship`) still require a ship-verified head, so fix it rather than relying on the notice.

## Self-recording

After the last substantive change of a turn (a code change, a commit, a decision), write a record for the bound issue: a Linear comment or document update on that issue, or an Obsidian note whose frontmatter `linear` includes it. With no binding, any Linear or Obsidian write after the change counts. Question-only turns need nothing. A "starting work" comment followed by more changes still needs a later record. The session stub in `wiki/sessions/SESSION-<MAE-or-none>-<YYYYMMDD-HHMM>-<session_id[:8]>` is written by the Stop hook; add decisions and results yourself.

## How evidence is recorded
- A check counts only when a recognized test runner runs **as one plain command** (for example `python3 -m pytest -q`, `npm test`, `forge test`). Pipes (`| tail`), `;` and `&&` hide the runner's exit status, so those runs are not evidence; run the check by itself, then inspect output separately.
- The working directory is part of the check: `cd tests/unit && pytest` does not satisfy a root-level `pytest` requirement.
- `--version`, `--help`, `--collect-only` and similar no-run invocations never count.
- Evidence is an **allowlist of runner invocations**: an unlisted flag makes a run not count (for example `pytest --cov`, `make -n test`, `go test -list .`, `cargo clippy -- -D warnings`). Use the plain forms (the test runners among them satisfy the default rule; check-kind forms such as `ruff check`, `mypy`, `tsc`, `cargo clippy|build`, `forge build`, `npm run lint|build|typecheck` and `claude plugin validate` count only where a Plan names them): `python3 -m pytest [-q|-v|-x] [-n 8]` (any number after -n; -n auto does not count), `python3 -m unittest discover [-s DIR] [-t DIR]`, `npm|pnpm|yarn test` (also `t` or `run test`), `npm|pnpm|yarn run lint|build|typecheck` (yarn also without `run`; `npm lint`, `pnpm build` and the like do not count), `forge test|build`, `cargo test [--all|--workspace|--all-features|--release|-q]`, `cargo clippy|build [--all|--workspace|--all-features|--release|-q|-p X]`, `go test ./... [-race] [-v]`, `make test|check`, `ruff check [paths]`, `mypy [paths]`, `tsc [--noEmit] [-p X]`, `claude plugin validate PATH`, `playwright test`. Requirements written in Plans should use these forms too. A compound Plan requirement (`a && b`) is allowed, but each constituent that is a runner must be a plain runner command executed separately and recorded as runner evidence (for example one `maeng-verify exec -- <runner>` per constituent); a wrapper (`env`, `sudo`, `nice`, `time`, `command`, ...) or an unsafe/variable assignment makes a run not count.
- Narrowing flags are never evidence (`pytest --ignore|--deselect|--lf|--ff|--last-failed|--failed-first`, `go test -short`, `cargo test -- --skip`); filtered forms (test paths, `pytest -k|-m`, `unittest discover -p PAT`, `go test -run`, `playwright test <paths>|--project X`, `forge --match-*|--no-match-*`) are evidence only for a Plan requirement that names them, never for the default "some passing tests" rule. Filtered as well: `cargo test TESTNAME|--lib|--doc|--bins|--tests|--test X|--bin X|-p X|--package X` (recorded, but a package-scoped `cargo test -p X` counts only for a Plan requirement that names it). Not evidence at all: `npm|pnpm|yarn test -- ...` passthrough, and `make` with `VAR=val`, `-C`, `-f`, `-n`, `-k`, `-i` or any other flag (only plain `make test|check`).
- A run whose output shows that zero tests ran (`Ran 0 tests`, `collected 0 items`, `no tests ran`, `no test files`, `no tests found`, `Tests: 0 total`, `running 0 tests`, `0 passing`, with nothing else passing) is not evidence, and a PostToolUse response marked interrupted, errored or with a non-zero exit code is recorded as a failure.
