# Repository-qualified `승인` and `면제` - Spec/Plan

## Problem
The UserPromptSubmit hook records `승인 #N` and `면제 #N <reason>` under the repository of the session's cwd. A session that works on a PR in another repository cannot approve or waive it. On 2026-11-09 the user's `면제 #1` and `승인 #2` for maengseojun/agent-feeds were recorded against agent-harness, because the session ran in an agent-harness worktree that cannot move. Merges of agent-feeds PR #1 and #2 were blocked.

## Change
- `승인 owner/name#N` and `면제 owner/name#N <reason>` name the PR's repository. Bare `#N` keeps its current meaning (the session's own repository).
- The approval reads the PR head with `gh pr view N --repo owner/name`, so the approval is bound to that repository's head.
- The waiver is recorded under `slug(normalize_repo("owner/name"))`, the same key `repo_key` gives a checkout of that repository.
- The gate messages in `maeng-ship` and the merge-quiz notice show the qualified form.
- Rejected alternative: guessing the repository from recent `gh`/`maeng-ship` calls in the session. A guess could approve the wrong PR; an explicit name cannot.
- Version 0.4.19 (0.4.18 is taken by open PR #114).

## Acceptance criteria
- AC-1 `승인 owner/name#N` sent from a session outside any checkout records an approval that `maeng-ship merge N` accepts, and `gh` is called with `--repo owner/name` (test `test_an_approval_naming_its_repository_counts_from_a_session_in_another_one`).
- AC-2 `면제 owner/name#N <reason>` records the waiver under that repository's key and not under the session's (test `test_a_pr_waiver_naming_its_repository_is_recorded_there`).
- AC-3 Existing approval and waiver tests still pass, and both new tests fail without the change.

## Verification
AC-1, AC-2, AC-3: `python3 -m unittest discover -s plugins/maeng-harness/tests -t plugins/maeng-harness` or the repository's full test command.
