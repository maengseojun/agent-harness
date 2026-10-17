# Verification and self-recording

The hooks track this for you; know the rules so you satisfy them on the first try.

## Evidence

A recognized command (pytest, `python -m unittest`, npm/pnpm/yarn test|lint|build|typecheck, forge, cargo, go test, make test|check, ruff, mypy, tsc, `claude plugin validate`, playwright test) produces evidence `{cmd, ok, tree_start, tree_finish}` only if the working tree did not change during the run. Do not edit files while a check runs; background commands produce no evidence.

For checks that are not recognized runners (screenshot, dry-run, manual probe) declare them: `maeng-verify ran --ok|--fail "<what>"`. Record an AC result: `maeng-verify plan --met AC-1,AC-2 --unmet AC-3 "<notes>"`. `maeng-verify skip "<reason>"` records a skip.

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
- Evidence is an **allowlist of runner invocations**: an unlisted flag makes a run not count (for example `pytest --cov`, `make -n test`, `go test -list .`, `cargo clippy -- -D warnings`). Use the plain forms: `python3 -m pytest [paths] [-q|-v|-x|-k EXPR|-m EXPR]`, `python3 -m unittest discover [-s DIR] [-t DIR] [-p PAT]`, `npm test` / `npm run lint|build|typecheck`, `forge test|build`, `cargo test|clippy|build [--all|--workspace|-p X]`, `go test ./... [-run X] [-race] [-v]`, `make test|check`, `ruff check [paths]`, `mypy [paths]`, `tsc [--noEmit] [-p X]`, `claude plugin validate PATH`, `playwright test [paths] [--project X]`. Requirements written in Plans should use these forms too.
