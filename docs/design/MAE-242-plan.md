# MAE-242 Spec/Plan: CEO loop (maeng-harness 0.3.0)

Linear: MAE-242. Date: 2026-10-18.

## Purpose

The user works as CEO: agents run on their own, and the user judges once, before final approval, from the decision's intent, candidates and results. dots (Slack bot `seojunmaeng-maestro`) injects work by running the local `claude` CLI through its Mac Work task and monitors it by reading files. Slack `@Claude` mentions do not reach local sessions, so Claude Code reads and posts Slack itself. The harness must stay practical and easy to maintain, extend or shrink.

## Criteria

- **AC-1 status file (dots contract).** The first personal-world prompt of a session writes `~/Documents/maeng-harness/status/<task_id>.json` (`MAENG_STATUS_DIR` overrides) with state `running` and the real `session_id` (the intake ack). `manifest.json` maps task_id to session_id, cwd, state and updated_at. task_id comes from `MAENG_TASK_ID`, else a `task_id: X` prompt line, else `s-<session8>`. Writes are atomic and hold only the listed fields: no environment and no secrets.
- **AC-2 Stop/SessionEnd update.** The state comes from the last assistant message's marker line: `result:` gives done, `needs input:` gives needs_input, `failed:` gives failed, and no marker gives idle. A stop the hook blocks keeps running. A yielded stop with open obligations is blocked, with the obligations as blocker. The file records head_sha, tree_sha, verify_state (pass / fail / not_run / none), and verified_head_sha when the pass is on the committed head tree. SessionEnd turns running or idle into ended.
- **AC-3 duplicate intake warning.** When a task_id's status belongs to another session in running or needs_input, updated within 12h, the new session's first prompt gets a context note naming that session.
- **AC-4 review round cap.** `maeng-review run --pr N` refuses when the same repo and PR already have 4 stored review runs (`--max-rounds`, raised only on the user's word). The message points to the CEO brief and `승인 #N`.
- **AC-5 maeng/review commit status.** A review with a GitHub repo and head posts commit status `maeng/review`: success on pass, failure otherwise. A posting failure is a warning only. maeng-review also writes pr, review_verdict, review_backend and receipt_path into the session's task status.
- **AC-6 harness-run docs.** An autonomy table by reversibility; a CEO brief before every approval request (intent, candidates, result, evidence, risk and rollback, one decision) posted to Slack `#maestro-claude` and Linear; the dots and Slack rules; review-and-ship notes on the round cap and the commit status.
- **AC-7 tests.** `tests/test_status.py` covers AC-1 to AC-5, and the full suite passes.

## Plan

1. Add `lib/maeng/status.py`: task id, marker outcome, verify state, atomic write plus manifest under a lock, and the commit status post. (AC-1, AC-2, AC-5)
2. Call it from `handlers.py`: `task_running` on UserPromptSubmit, `task_stopped` on Stop, and the ended transition on SessionEnd. (AC-1, AC-2, AC-3)
3. In `bin/maeng-review`, add `prior_rounds` and the `--max-rounds` refusal, and add `report_review` for the commit status and the task status fields. (AC-4, AC-5)
4. Update the harness-run SKILL.md and review-and-ship.md. (AC-6)
5. Add the tests and release 0.3.0. (AC-7)

## Verification

- AC-1 to AC-5: `python3 -m pytest -q tests/test_status.py` in `plugins/maeng-harness`.
- AC-7: `python3 -m pytest -q` in `plugins/maeng-harness` (full suite).
- AC-6: read the diff of the two docs.
- AC-5 live: a commit status write and read on this private repo succeeded on 2026-10-18 (context `maeng/probe`).

## Removal

Delete `lib/maeng/status.py`, its calls in `handlers.py` (`task_running`, `task_stopped` and the SessionEnd block), and `prior_rounds` and `report_review` in `maeng-review`.

## Out of scope

- Workflow-based sweeps, the `correct` loop and arena.
- `CLAUDE_CODE_SUBAGENT_MODEL`: harness-run says not to set it.
- Switching maeng-ship to `gh pr merge` once rulesets require PRs.
- Whether a `승인 #N` relayed by dots through `claude -p` should count as the user's approval: today it does, because the hook cannot tell who typed the prompt. This is the user's decision.
