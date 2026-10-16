# Staging results, 2026-10-17 (MAE-223 / C6, staging part)

Claude Code 2.1.301, main session `claude-sonnet-5-5` (S4: `claude-opus-5-5`), branch `feat/mae-216-claude-plugins`,
plugins loaded with `--plugin-dir` (inline), not installed. Runner: `tests/live/run_smoke.py`; assertions:
`tests/live/assert_smoke.py` (reads only `evidence/*.summary.json`; 56 of 61 checks pass, the 5 failures are listed below);
model check: `tests/live/check_models.py`. Raw stream-json stays in `/private/tmp/maeng-smoke/<id>.jsonl`
(scenario dirs `/private/tmp/maeng-smoke/<id>/`); only condensed evidence (init, hook events, tool calls and results,
final result, filesystem/state facts) is kept in `tests/live/evidence/<id>.summary.json`; per-check results are in
`tests/live/evidence/results.json`.

Isolation used: temp `MAENG_HOME/MAENG_VAULT/MAENG_CACHE_DIR` per scenario, a fake `gh` first on `PATH` and as `MAENG_GH`,
local bare remotes only, `GIT_CONFIG_GLOBAL` temp file, no `--dangerously-skip-permissions`, `--allowedTools` lists only.
The one external write: a single Linear comment on MAE-223 in S2 (comment id `e17c7053-1366-409d-9864-3dc5ccf8fa30`,
body `staging S2 record write (automated)`).

## Results

| Scenario | Expected (§5.8) | Observed | Result | Evidence |
|---|---|---|---|---|
| S1 | bind, edit, stop without tests: Stop block (unverified+unrecorded), continuation, final `systemMessage`; stub written | Stop #1 `decision:block` with UNVERIFIED and UNRECORDED; agent got "Stop hook feedback" and declined; Stop #2 returned `systemMessage` "UNVERIFIED / UNRECORDED: ..."; stub `wiki/sessions/SESSION-MAE-223-...md` written in temp vault and finalized with `ended:`. Extra check fails: after SessionEnd the stub says `Status: ended` and no longer lists the open items (suspected bug 1) | PASS (extra check FAIL) | `tests/live/evidence/S1.summary.json` |
| S2 | pytest ok + Linear record on MAE-223, stop: no block; `maeng-verify status` ship-verified | pytest `1 passed`; one `save_comment` on MAE-223 succeeded; Stop output empty (no block, no feedback); `status` -> `"ship_verified": true, "stop_satisfied": true`; state has ok evidence, `last_record_seq >= last_change_seq` | PASS | `tests/live/evidence/S2.summary.json` |
| S3 | force push, `gh pr merge`, `maeng-ship merge` w/o receipt, push of unverified commit: all denied | A: PreToolUse `permissionDecision:deny` "maeng G1: force pushes are denied ..."; B: deny "`gh pr merge` is denied in every mode ..."; C: not a hook deny, the CLI itself refused (exit 1, "head tree is not ship-verified: no passing test-runner evidence"); D: deny "maeng G1: pushed commit f2a15483 (feat -> feat) tree is not ship-verified". Remote refs unchanged, fake gh never ran a merge | PASS | `tests/live/evidence/S3.summary.json` |
| S4 | opus main; researcher=haiku, architect=opus, implementer=sonnet; researcher asked to write: no write tool | `check_models.py`: researcher `claude-haiku-5-5` (x2), architect `claude-opus-5-5`, implementer `claude-sonnet-5-5` (transcript model, `meta.json` toolUseId correlation and parent `resolvedModel` agree). Negative: researcher replied "Tools I have: Read, Grep, Glob, WebFetch, WebSearch ... I did not write note.txt", made 0 tool calls; `note.txt` absent; frontmatter lists no write tool | PASS | `tests/live/evidence/S4.summary.json`, `tests/live/evidence/S4.models.json` |
| S5 | eta_v1, only maeng-tools inline, no write tools: init has eta-rules, eta-craft, maeng-tools, NO maeng-harness, no personal agents; zero maeng hook events; temp MAENG_HOME unchanged | plugins: maeng-tools, eta-rules, eta-craft (+ builtins); no maeng-harness; no hook output mentions maeng; temp home/vault empty; eta_v1 `git status` + HEAD identical before/after; reply `OK`. But init also lists the personal agent `codebase-explorer` (`~/.claude/agents/codebase-explorer.md`) and the loose `~/.claude/skills/*` (harness-run, work-records, obsidian-workspace, ...) | PARTIAL: plugins/hooks/state PASS, personal agent+skills leak FAIL (environment not yet retired per §1.2, not a plugin bug) | `tests/live/evidence/S5.summary.json` |
| S6 | eta-classified temp repo (origin `https://github.com/maengseojun/eta_v1.git`, local only), maeng-harness inline: no side effects except one SessionStart warning | One SessionStart `additionalContext` line ("maeng-harness is loaded in an eta checkout (misconfigured). Personal hooks are inert here. Run `maeng-eta-isolate --apply` ..."); every other hook produced empty output; temp MAENG_HOME and vault empty; no Stop feedback; Write + `git status` unaffected | PASS | `tests/live/evidence/S6.summary.json` |
| S7 | personal session: read-only `git -C eta_v1 status` allowed; `git -C <eta repo> commit`, `gh pr create -R endix-foundation-v1/x`: G3 deny | A allowed (status output returned); B deny "maeng G3: git -C targets an eta checkout (...)"; C deny "maeng G3: gh write targets eta repo `endix-foundation-v1/x`"; eta-classified repo HEAD unchanged; real eta_v1 status unchanged; fake gh never saw `pr create` | PASS | `tests/live/evidence/S7.summary.json` |
| S8 | verified feature branch + fake PR + pass receipt, `maeng-ship merge 1`: push accepted, receipt consumed, merge tree == verified tree | `checkout feat` -> pytest `1 passed` -> `maeng-review store` (pre-made pass verdict, not a Codex run) -> `maeng-ship merge 1` "merged PR 1"; remote `main` == head `689d654b`; receipt history stored -> pending -> consumed, `merge_sha == head`; remote main tree `9b1daf0b` == feat tree == evidence `tree_finish`; no hook deny | PASS | `tests/live/evidence/S8.summary.json` |
| GF1 | broken gate (PreToolUse exits 1): `git push` blocked (`onFailure:"block"`) | Every Bash call blocked: "hook error: [python3 ...maeng_hooks.py]: failed; blocking because onFailure is "block"". The push never ran, remote has no `feat` | PASS | `tests/live/evidence/GF1.summary.json` |
| GF2 | gate script missing | Python exits 2 ("can't open file"), calls blocked with that stderr; SessionStart/UserPromptSubmit/Stop also show exit 2 `error`; remote has no `feat` | PASS | `tests/live/evidence/GF2.summary.json` |
| GF3 | gate timeout (sleeps 30 s, hook timeout 5 s) | outcome `cancelled`; calls blocked: "timed out; blocking because onFailure is "block""; remote has no `feat` | PASS | `tests/live/evidence/GF3.summary.json` |
| GF4 | gate prints malformed output (`{not json`, exit 0) | Claude Code treats it as plain text and does NOT block: the commit and the `git push origin feat` both ran, remote received `feat` (fail-open) | FAIL (see note 2) | `tests/live/evidence/GF4.summary.json` |

Gate-failure variants copy `plugins/maeng-harness` to `/private/tmp/maeng-smoke/GFn/harness-broken`, break only the
PreToolUse path of `hooks/maeng_hooks.py` (or delete it), and load that copy with maeng-tools. The prompt asks for a
commit and `git push origin feat`; because the working gate would deny that push (unverified tree), a successful push
proves the gate was bypassed.

## Suspected product bugs (not fixed; no product code was changed)

1. **SessionEnd erases the open-items list from the stub.** `plugins/maeng-harness/lib/maeng/handlers.py:454`
   calls `stub.write(s, "ended", ended=True)` without `notes`; `plugins/maeng-harness/lib/maeng/stub.py:21-22,26`
   only renders `## Open` from `notes`. Observed in S1: the last Stop wrote the UNVERIFIED/UNRECORDED status, then
   SessionEnd rewrote the stub as `Status: ended` / `## Evidence - none`, so the durable record no longer says the work
   was unverified and unrecorded. Severity low-medium (record quality; no gate impact). Fix idea: persist the last
   `missing` list in state at Stop and re-render it at SessionEnd.
2. **Malformed gate output fails open (GF4).** This is Claude Code behavior (non-JSON stdout with exit 0 is treated as
   plain text), not a bug in `maeng_hooks.py`, which only prints `json.dumps(...)` and returns 2 on handler exceptions
   (`hooks/maeng_hooks.py:30-33`). The §5.8 line "malformed output" cannot be satisfied by `onFailure:"block"` alone.
   Risk only if Python itself prints partial output with exit 0, which is unlikely; the doc should state the limit
   instead of promising a block.

## Environment findings (not plugin bugs)

- S5 shows `~/.claude/agents/codebase-explorer.md` and the loose `~/.claude/skills/*` still load in an eta session
  (they are user scope). Closing this is the §1.2 loose-skill retirement step at release, so the "no personal agents/
  skills in eta" expectation will only hold after that step. The eta repo's own agents (explorer, implementer,
  planner, researcher, reviewer from `eta_v1/.claude/agents`) are allowed.
- Models in permission-restricted sessions still try the real `mcp__obsidian_vault__write_note` (S3, S8) to satisfy the
  Stop hook's UNRECORDED request. `MAENG_VAULT` does not redirect that MCP server; it was denied only because it was not
  in `--allowedTools`. Never grant it in staging.
- S3 step C ("`maeng-ship merge` without receipt") is refused inside the CLI, not by a PreToolUse deny, and the first
  failure reported is "head tree is not ship-verified" (verification is checked before the receipt). The receipt path
  ("no pass receipt") is covered by `plugins/maeng-harness/tests/test_merge.py`, not by this live run.
- Scratch repos carry a `.gitignore` for `__pycache__/` and `.pytest_cache/`. Without one, a pytest run could alter the
  tree id between `tree_start` and `tree_finish` (tree id uses `git add -A`); this was not exercised live.
- S8 used `maeng-review store` with a pre-made verdict, not `maeng-review run` with `MAENG_CODEX`; the Codex invocation
  path is not covered live.

## Reproduce

```
python3 tests/live/run_smoke.py S1 S3 S4 S5 S6 S7 S8 GF1 GF2 GF3 GF4   # S2 posts a real Linear comment; run it deliberately
python3 tests/live/assert_smoke.py
python3 tests/live/check_models.py --summary tests/live/evidence/S4.summary.json
```


## Opus review (2026-10-17)
- **Verdict:**
  - Staging passes for everything the plugins control.
  - S5's FAIL comes from two sources outside the plugins:
    1. the user-level agent `~/.claude/agents/codebase-explorer.md`, now added to the retirement inventory and checked again after release (MAE-224);
    2. eta_v1's tracked `.claude/agents` (explorer/planner/researcher/reviewer/implementer), removed by the user's own PR.
- **Suspected bug 1 (stub open items erased at SessionEnd) is fixed.** `stub.write` now remembers the last Stop's status and open items, and SessionEnd keeps them. A regression assertion was added to `test_session_stub_written_and_refreshed_in_place`.
- **GF4 is a host limit, not a dispatcher bug.** It is documented in design §5.1.
- **The real Obsidian MCP was attempted in staging.** Staging must never grant `mcp__obsidian_vault__*`. Noted in `run_smoke.py` usage.
- **Model routing proven from transcripts:**
  - researcher → `claude-haiku-5-5`
  - architect → `claude-opus-5-5`
  - implementer → `claude-sonnet-5-5`
  - main session → opus

## Re-run and redaction (2026-10-17)
- **S1 re-run live after the stub fix:** 8/8 PASS, including "stub still lists the open items after SessionEnd".
- **Totals: 57/61 PASS.** The 4 remaining are known and dispositioned:
  - S5 ×2 (user-level agent and loose skills): retirement at release, MAE-224, re-checked there.
  - GF4 ×2: Claude Code host limit, documented in design §5.1.
- **Privacy fix.**
  - S5/S7 evidence had stored eta_v1 `git status` output (eta file paths) in this personal repo. Replaced with `porcelain_sha256` + line count. Before and after match: `eb2d9150f3bc…`, 565 lines, so "unchanged" is still proven.
  - `run_smoke.py` now scrubs eta_v1 content (`scrub_eta`) before writing any summary.
  - The earlier commit `1785bca` on this branch still contains those paths in git history (private repo, file names only, no content).
