---
name: comprehension-gate
description: Use when a project needs a part map or a gate says an interview, quiz, seal or waiver is missing - the user must show, without AI help, that they can explain and defend the work before it moves on (이해 확인, 인터뷰, 파트 맵, 머지 퀴즈, 봉인, 면제, 중단, 이의, maeng-interview). Also when you must recommend on an architecture or workflow decision before the user chooses, and before merging a PR over 150 changed lines.
---

# Comprehension gate (MAE-313)

The user shows, without AI help, that they can explain and defend the project. If they cannot, the next step stays blocked. Two layers are checked: how it is built, and why, what was rejected and when it breaks. A perfect score is required. The interviewer is Opus; you never grade, answer or hint. The gate runs in the personal and eta worlds alike.

## The part map

When the big picture is designed, propose parts: a name, path globs, a few aliases (words the user uses for it) and the test command. Show the proposal in chat. Only after the user confirms, write a file and run `maeng-interview map <file>`:

```json
{"parts": {"mint": {"paths": ["src/mint/**"], "aliases": ["민트"]}}, "test": "python3 -m pytest -q"}
```

`overall` always exists. Change the map only on the user's word. From then on Edit/Write on a mapped path is denied until `overall` and that part have a design pass. With no map, or on an unmapped path, nothing changes. Headless runs (`claude -p`, dots) skip the write gate.

## Design interview (overall, then each part)

1. Write the design in plain words to a file: what the part does, why this way, alternatives rejected, when it breaks. That is the interviewer's material.
2. `maeng-interview start --stage design --part <P> --material <file>` (or `--overall`). It prints one question.
3. Relay the question verbatim. No hint, no rewording, no example, nothing else in that message.
4. The user's next message is recorded by the hook as the answer. Then run `maeng-interview next`. If it says no answer is recorded, the user has not answered yet: ask them to, never answer for them.
5. `next` prints the next question, `PASSED`, or `NOT YET` with the missing items. On a miss, tell the user plainly what was missing so they can study. You may explain when they ask. A retry (`start` again, same arguments) asks new questions on the missed topics only and keeps the passed ones.
6. `중단` is the user's: if they send exactly `중단`, the interview closes with no penalty; do not restart it unless they ask. If they send `이의 <argument>`, run `maeng-interview appeal`: a fresh grader reads their argument and may read the repo.
7. When work on a part begins, run `maeng-interview switch <P>`: the hook's note and the check below follow the current part. Moving to the next part: `maeng-interview switch <B>` refuses while the current part has no pass. If the user's message names another part first, the hook adds a note; finish the current part. A design pass does not expire; `maeng-interview reopen <P>` clears one when the user wants it asked again.

## Whose answers count

Any session may explain or give reasons at any time: the user can ask you, another session or a subagent. But an answer counts only when the user types it in their own message in the session that opened the interview. Relayed text (`<cross-session-message>`, `<system-reminder>` and the like), your own writing and a child `claude -p` never count. Never call `next` to "try", never paste an answer. Never read, list or write the interviews directory under the maeng-harness state folder, and never set `MAENG_CLAUDE`: the questions, rubrics and answers there are not yours, and the hooks deny it.

## Merge quiz

A PR over 150 changed lines, or one touching a mapped path, needs the user's quiz before `maeng-ship merge` (personal) or `gh pr merge` and the merge MCP tool (eta, denied without it). `승인 #N` replaces only the review; the user's `해당 작업 면제 <사유>` replaces review and quiz for this session's merges for 24 hours (harness-run review-and-ship). Start the quiz last, after the review passed and the head is final: a changed diff asks again, a rebase with the same diff keeps the pass.

In a clean checkout of the PR head: `maeng-interview start --stage merge --pr <N> [--material <plan file>]`. It runs the project's tests in a throwaway copy, which can take minutes: use a long timeout or run it in the background. The user gets four short-answer items whose answers come from running the code (a predicted value, the changed line, a failing test or `없음`), then one written question on what differs from the design. If the tests give fewer than two items, it asks two written questions instead. When an older pass of the same PR sits on an ancestor head, it asks one item about the change. Relay each question and call `next` exactly as above. A headless run cannot start it: end with `needs input:`.

## Waivers

`면제 #<N> <reason>` waives a PR and `면제 <part> <reason>` waives a part. Only the user types them, in an interactive session; a relayed waiver does not count. Never suggest typing one as the default, and never type it for them. They are counted in a ledger.

## Sealing a recommendation (architecture and workflow decisions)

A recommendation must not be weighted by the user's choice.

1. Write your recommendation and reasons to a file and run `maeng-interview seal <file>`. It prints a 12-character digest; show it to the user.
2. Ask for the user's choice with the options in a neutral order. Show no "recommended" marker, no recommended button and no default label before the reveal.
3. After the user answers in their own message, run `maeng-interview reveal <digest>` and show the text unchanged, then compare it with their choice. `reveal` refuses until that message exists.
4. After the reveal the recommendation changes only for a new fact, written as `변경: <근거>`. The user's choice is not a fact.
5. If the user states an opinion before you seal, do not recommend yourself: give a fresh subagent a neutral question (the options and constraints, not the user's opinion) and seal its recommendation as it is.

## Commands

`map`, `switch`, `reopen`, `start`, `next`, `appeal`, `seal`, `reveal`, `status` (`maeng-interview --help`). `status` shows passes and the open step, never questions or rubrics.
