# MAE-313 Spec/Plan: comprehension gate

status: current. Task MAE-313, no parent. Source: session 29933431 (2026-11-04), design agreed in chat with the user.

Goal: before the work moves on, the user shows, without AI help, that they can explain and defend the project. If they cannot, the next step stays blocked. This keeps their ability to supervise what the agents do.

Deliverable: one PR to `maeng-harness` adding the CLI `maeng-interview`, the gates in both worlds, the skill `comprehension-gate` and the docs. The user receives the Korean CEO brief and merges with `승인 #N` after passing the gate's own check of this PR if it is installed by then.

Decisions:
- D-1 (user) Two layers are checked, implementation understanding and supervision. The bar is whether the user could answer an interview about the project. "구현에 대한 이해와 조금 더 깊은 질문(감독)을 다 답할 수 있어야", "누군가 내게 이 프로젝트에 interview를 할 때 내가 얘기할 수 있느냐". Wrong if: none (user decision).
- D-2 (user) Format follows whether an answer can be checked without an LLM. Overall design and part transitions are interviews (a part takes about 5 minutes, overall about 10). Merge is a short-answer quiz whose answers come from running the code, plus one written question on what differs from the design. Multiple choice is not used. "보완 더한 독립 추천안 좋은듯". Wrong if: the waive rate exceeds 30% or the first-try pass rate exceeds 90% after 4 weeks.
- D-3 (user) A perfect score is required. "만점을 받아야 다음 행동이 가능". Wrong if: none (user decision).
- D-4 (user) The interviewer is Opus in both worlds. The same-family blind spot at design time is accepted because Fable and Astra reviews already exist. "면접관 모델도 Opus가 나을 것 같아", "fable이나 astra를 통한 검토가 harness에 이미 있어서 놓치는 지점은 생각안해도 될듯". Wrong if: none (user decision).
- D-5 (user) maeng gates eta before and after eta's own flow. This is an authorized exception to "maeng does nothing in eta". "eta harness의 전과 후에 maeng을 걸어버리면", "응 eta에서 maeng 해도 돼. 그원칙은 내가 허가할게 수정해도 돼". Wrong if: eta work is blocked by a gate failure and not by a missing pass.
- D-6 (user) Parts are declared when the big picture ends, so a part transition is detectable. "큰 그림을 설계한다음 하나씩 보는 식", e.g. eta's mint, launch and governor. Wrong if: transitions happen without any signal.
- D-7 (user) Any session may be asked for reasons and explanations at any time. Only answers relayed into the gate are barred. "다른 세션에게 그 이유를 묻거나 설명을 요청하는건 되는거지?". Wrong if: none (user decision).
- D-8 (user) A recommendation must not be weighted by the user's choice. It is sealed before the user answers. "내 선택에 따라 추천의 가중치가 바뀌는건 원하지 않아". Wrong if: a revealed recommendation differs from the sealed text.

Assumptions (for the CEO brief):
- A-1 The merge gate opens when a PR's additions plus deletions exceed 150 or it touches a mapped path. 150 is the size harness-run treats as one task. With no part map, design gates do not apply.
- A-2 Sizes: overall 5 exchanges, part 3 questions plus 1 follow-up, merge 4 keyed items plus 1 written question.
- A-3 Headless sessions (`claude -p`, dots) skip the code-write gate but not the merge gate; they end with `needs input:`. Measured 2026-11-04: `CLAUDE_CODE_ENTRYPOINT` is inherited by a child `claude -p` so it cannot tell them apart; the parent process argv carries `-p`, the desktop session's does not.
- A-4 Answers bind to the session id that opened the interview. A child `claude -p` has its own session id (measured). A prompt starting with a system wrapper (`<system-reminder>`, `<task-notification>`, `<cross-session-message>`, `<side-sessions-event>`, `<ci-monitor-event>`) is never an answer. Unmeasured: how a cross-session message reaches UserPromptSubmit.
- A-5 A design pass does not expire and is not bound to a digest; `maeng-interview reopen <part>` clears it. Only merge passes are bound to code.
- A-6 Guardrail level, as with receipts: Edit/Write into the state directory is denied in both worlds, a Bash command that names the `interviews/` directory or sets `MAENG_CLAUDE` is denied, and reading the rubric is barred by the skill text only.
- A-7 State lives under `home_dir()/interviews/<repo slug>/`. Questions, rubrics and answers are deleted when an interview closes; the ledger keeps counts and hashes only.
- A-8 The test command comes from the map's `test`, else `.maeng/verify.json` `required[0]`, else none. With no test command, or fewer than 2 confirmed items, the merge gate falls back to two written questions.
- A-9 Output prediction masks an expected value in an existing passing test instead of running a command the model wrote. Mutations are find/replace pairs of at most 3 lines, in files the PR changed, run in a throwaway clone.
- A-10 `승인 #N` keeps replacing the review only. A Slack relay of `승인 #N` alone no longer merges a gated PR.
- A-11 `면제 #N <reason>` and `면제 <part> <reason>`, typed by the user, waive a gate. A relayed waiver does not count.
- A-12 Clones use `cp -cR` (APFS), so `node_modules`, `lib/` and build output come along. macOS only.
- A-13 A waiver is refused from a headless session as well as from a wrapped prompt, because a child `claude -p` could otherwise waive for itself.
- A-14 A path owned by several parts needs a pass for all of them.
- A-15 A repository with no origin remote has no gate.
- A-16 Outside the personal world, a command that cannot be parsed and names `gh ... merge` is denied.
- A-17 The CLI's session id is `--session`, then `MAENG_SESSION_ID`, then `CLAUDE_CODE_SESSION_ID`. Measured 2026-11-04 in an eta checkout: `MAENG_SESSION_ID` is empty and `CLAUDE_CODE_SESSION_ID` equals the hook's session id.

Owns: `plugins/maeng-harness/bin/maeng-interview`, `plugins/maeng-harness/lib/maeng/interview.py`, `plugins/maeng-harness/lib/maeng/quiz.py`, `plugins/maeng-harness/lib/maeng/handlers.py`, `plugins/maeng-harness/lib/maeng/gates.py`, `plugins/maeng-harness/lib/maeng/guard.py` (comment only), `plugins/maeng-harness/bin/maeng-ship`, `plugins/maeng-harness/bin/maeng-review` (the reviewer prompt's switch list), `plugins/maeng-harness/tests/test_interview.py`, `plugins/maeng-harness/tests/test_quiz.py`, `plugins/maeng-harness/skills/comprehension-gate/**`, `plugins/maeng-harness/skills/harness-run/**`, `plugins/maeng-harness/.claude-plugin/plugin.json`, `templates/global-CLAUDE.md`, `README.md`, this file.

Exclusions: code written through Bash (`sed`, a heredoc) or by Codex and Orca workers, which the write gate does not see; invalidating a design pass when the design changes (A-5); hard blocking of a part transition during design talk with no code write, which stays a prompt note plus the agent's stop; a command the model writes for output prediction (A-9); per-question time limits and asking one fact twice; blocking reads of the rubric (A-6); PRs merged by hand on GitHub; Linux clones.

must_haves:
- truths:
  - T1: With a map, Edit/Write on a mapped path is denied until `overall` and that part have a design pass, in personal and eta. Without a map, or on an unmapped path, nothing changes.
  - T2: In personal, `maeng-ship merge` refuses a gated PR without a pass for its patch-id, even with `승인 #N`. In eta, `gh pr merge`, with or without `--auto`, and `mcp__*__merge_pull_request` are refused the same way.
  - T3: Only a prompt from the session that opened the interview becomes an answer.
  - T4: Every keyed answer in a merge quiz comes from a recorded execution; a mutation no test catches never becomes a question.
  - T5: A rubric is stored before the first question is printed.
  - T6: `reveal` refuses until a user message was captured after `seal`, and prints the sealed text unchanged.
  - T7: An exception while matching a call never denies it. `test_eta_session_has_zero_side_effects` passes unedited.
- artifacts:
  - A1: `lib/maeng/interview.py` - map, parts, passes, capture, waivers, seal, `gate`, `on_prompt`, `require_merge`, `headless`, `run_model`.
  - A2: `lib/maeng/quiz.py` - clone, item confirmation, keyed grading.
  - A3: `bin/maeng-interview` - `map`, `switch`, `reopen`, `start`, `next`, `appeal`, `seal`, `reveal`, `status`.
  - A4: `skills/comprehension-gate/SKILL.md` - the protocol the agent follows.
- key_links:
  - K1: `handlers.on_pre` -> `interview.gate` before the eta return.
  - K2: `handlers.on_prompt` -> `interview.on_prompt` before the world return.
  - K3: `maeng-ship merge` -> `interview.require_merge` after `ship_verified`.

Acceptance:
- **AC-1** Write gate per T1, in both worlds; a headless session is exempt. covers T1, K1
- **AC-2** `maeng-interview switch B` refuses while the current part has no design pass; a prompt naming another part adds a context note and changes nothing else. covers T1, K2
- **AC-3** Merge gate per T2; a PR at or under 150 lines touching no mapped path passes; a rebase with the same patch-id keeps the pass; a changed diff asks for a new one-item quiz on the delta when the old head is an ancestor of the new head, otherwise a full quiz. covers T2, K3
- **AC-4** Answers per T3: another session's prompt, a wrapped prompt and an agent call to `next` without a captured answer record nothing. covers T3, K2
- **AC-5** Design interview with a fake model: the sizes in A-2; all rubric items must be met; a retry asks new questions on missed topics only and keeps passed ones; `appeal` re-grades in a fresh model call with the user's argument; `중단` closes it with no penalty. covers T5, A3
- **AC-6** Merge quiz on a real temporary pytest repository: a confirmed mutation yields `failing-test` or `defect-line` items, an equivalent mutation is dropped, a clean snippet answers `없음`, `predict` masks a literal in a passing test, keyed grading needs no model, and A-8's fallback works. covers T4, A2
- **AC-7** Waivers per A-11, recorded only from a prompt and counted in the ledger. covers T3
- **AC-8** Seal per T6, including the digest printed before the user answers. covers T6
- **AC-9** T7 holds: a raising matcher allows the call and warns; the state directory rules of A-6 hold in eta. The comment in `guard.py` names the exception. covers T7, K1
- **AC-10** The skill and docs are in place, `templates/global-CLAUDE.md` has the seal rule and the map rule, and the plugin is 0.4.11. covers A4
- **AC-11** One real `claude -p` Opus call through `run_model` returns a schema-valid interview. covers A1

Readiness: dependencies done; no inputs missing; Spec current. Measured before writing: PreToolUse deny holds in bypass mode; A-3 and A-4 facts.
Environment: Python stdlib only, as the rest of the plugin. Branch `feat/mae-313-comprehension-gate`, worktree `.claude/worktrees/comprehension-gate`, base `feat/harness-v1`.
Routing: implement `maeng-tools:implementer` (Sonnet); review Sol xhigh through `maeng-review run --kind code --pr <N>`; limits: none known.

Steps:
1. S1 to S5 below, in order - done when: each row's Done re-run by the session. Advances AC-1 to AC-10.
2. Live call of `run_model` - done when: AC-11's check is declared.
3. Full suite, plan record, PR, review, CEO brief - done when: `승인 #N`.

Sub-tasks:

| # | Do | Writes | Interfaces | Done | Fails-if | After |
|---|---|---|---|---|---|---|
| S1 | State: map, passes, capture, waivers, seal | `lib/maeng/interview.py`, `tests/test_interview.py` | `repo_key(cwd)`, `load_map(key)`, `save_map(key, m)`, `parts_of(m, rel)`, `passed(key, part, stage, digest=None)`, `record_pass(...)`, `on_prompt(payload) -> str or None`, `headless()`, `seal(text) -> digest`, `reveal(digest) -> text` | `python3 -m pytest -q plugins/maeng-harness/tests/test_interview.py` OK | a wrapped prompt is recorded; another session's prompt is recorded; `reveal` works before a captured message; the tests pass with `capture` replaced by a no-op | - |
| S2 | Gates in both worlds | `lib/maeng/handlers.py`, `lib/maeng/gates.py`, `lib/maeng/guard.py`, `bin/maeng-ship`, tests | `gate(payload, world) -> str or None`, `require_merge(cwd, repo, pr, base, head) -> str or None` | same test file OK, plus `test_stop_hooks.py` unedited OK | the eta test was edited; a raising matcher denies; `승인 #N` passes a gated PR; `--auto` slips through; a segment such as `sh -c 'gh pr merge'` slips through | S1 |
| S3 | Design interview | `bin/maeng-interview`, `lib/maeng/interview.py`, tests | `run_model(prompt, schema, cwd, tools)`; env `MAENG_CLAUDE` for the fake; command `claude -p --setting-sources "" --strict-mcp-config --tools Read,Grep,Glob --model claude-opus-5-5 --effort high --output-format json --json-schema <schema>` | `test_interview.py` OK | a question prints before its rubric is stored; a run on another model passes; grading reads anything but the rubric, the question and the answer | S1 |
| S4 | Merge quiz | `lib/maeng/quiz.py`, `bin/maeng-interview`, `tests/test_quiz.py` | `confirm_items(candidates, top, test_cmd) -> items`, `grade_keyed(item, answer) -> bool`, `patch_id(cwd, base, head)` | `python3 -m pytest -q plugins/maeng-harness/tests/test_quiz.py` OK | expected values come from the model and not from a run; a mutation no test catches survives; a mutation outside the PR's files is applied; the user's checkout is touched | S1 |
| S5 | Skill, docs, version | `skills/comprehension-gate/SKILL.md`, `skills/harness-run/**`, `plugin.json`, `templates/global-CLAUDE.md`, `README.md` | - | `claude plugin validate plugins/maeng-harness` prints `Validation passed` | harness-run still says the user judges only once; the skill omits D-7 or the seal order | S2, S3, S4 |

Verification tier: gate-code.
Verification:
- AC-1 to AC-10: `python3 -m pytest -q` passes from the repo root; before merge also with `HARNESS_TEST_PROCESS=1`.
- AC-10: `claude plugin validate plugins/maeng-harness` prints `Validation passed`.
- AC-11: `live run_model returned a schema-valid interview` declared with `maeng-verify ran --ok`.

Failure / change handling: Failure handling in harness-run. A change to an `AC-n`, the Owns or a `D-n` needs the user.

Review focus: can an agent pass or skip a gate by mistake; does any path deny eta work when nothing is wrong; does a keyed answer ever come from the model; does `on_prompt` swallow a normal prompt when no interview is open.

Revisions:
- R-1 result quality: a `failing-test` answer must be the name of a failing test. Any 4 characters of a failing line passed before, so `test` was always right.
- R-2 result quality: an unreadable map allows the edit and warns (T7). It denied every edit in the repository before.
- R-3 result scope: a merge-quiz retry on the same patch keeps what passed and asks one new item per miss, as the user was told; mutation runs stop once there are enough items.
- R-4 result quality: the written question names the design only when a design file was given.
- R-5 plan scope: `bin/maeng-review` joined the Owns for the reviewer prompt's switch list.

Close-out:
- filled at close
