# Race brief template

Both racers get this brief, word for word. Fill every field; write "none" rather than leaving one out, so a racer never guesses what was meant.

```text
# Race brief: <bug in one line>

## Evidence
- Symptom: <what the user sees, with the exact error text>
- Reproduce: <command or steps with literal inputs>   Repro rate: <e.g. 4 of 5>
- Expected: <...>   Actual: <...>
- Environment: <commit>, <OS / runtime / flags>
- Last known good: <commit or version, or unknown>
- Logs: <paths or excerpts>
- Already tried: <attempt -> result>, one per line

## Purpose
Solved means: <(a) root cause explained, change no code | (b) root cause plus the minimal fix | (c) a workaround is acceptable>.
Find the root cause before writing any fix, and explain why it produces every symptom above, including the repro rate.

## Must not
- Do not edit, delete, skip or weaken tests, the repro (<path>), or the test runner and its config.
- Do not special-case the failing input or hard-code expected values. If a test looks wrong or the fix looks infeasible, say so and stop.
- Do not hide the error: no catch-and-ignore, no lowered log level, no retry loop that masks it.
- Do not refactor, rename or reformat beyond what the fix needs; do not add files that were not asked for.
- Do not upgrade dependencies, change lockfiles, run migrations, delete data or touch secrets.
- Do not push, open a PR or merge. Ask the coordinator before any destructive or hard-to-reverse action.
- <user's additions>

## Scope
- May edit: <paths>
- Must not touch: <paths>

## Done
Done when this passes in your worktree: <check command(s)>, with the repro going from failing to passing.

## Stop
- Budget: <minutes or turns>.
- Stop and report when the bug does not reproduce in your worktree, when no hypothesis explains all of the evidence, or after two failed fix attempts. A clear "not found" with what you ruled out is a valid result.

## Report (send as worker_done; same format for both racers)
1. Root cause: <file:line> and the mechanism, in two or three sentences.
2. Evidence: what you ran or read that proves it.
3. Hypotheses ruled out, and how.
4. Change: files and lines changed, and why each is needed (or "no change" for purpose a).
5. Done check: the command and its output.
6. Not verified, and confidence (high / medium / low).
```

## Why each default is there

| Field | Prevents | Source |
|---|---|---|
| Reproduce, repro rate | a symptom fix for a bug the agent never saw fail | BuildBetter: do not hand off a bug you cannot reproduce once (practitioner) |
| Purpose names a check, root cause first | "make sure it works", which leaves nothing to verify; a plausible patch with no diagnosis | Devin and Codex guides (official); BuildBetter (practitioner) |
| Frozen repro, no test edits | editing or weakening tests to get green | Cursor agent best practices (official blog); EvilGenie benchmark (research) |
| No special-casing; say so when the test is wrong | hard-coded outputs that pass only the known input | Anthropic Claude prompting best practices (official) |
| No destructive actions, ask first | deletion or reset used to get past an obstacle | Anthropic Claude prompting best practices (official) |
| Minimal change, no extra files | over-engineering and unrequested files | Anthropic Claude prompting best practices (official) |
| Do not hide the error | a swallowed exception that looks like a fix | BuildBetter review checklist (practitioner only; no study found) |
| Two failed attempts, then report | a context full of failed tries; Claude's docs say a fresh start beats a third correction | Claude Code best practices (official) |
| Budget | an unattended run that drifts; Claude suggests turn or spend caps, Copilot stops at 59 minutes | Claude Code best practices; GitHub Copilot coding agent docs (official) |
| Judging by root cause, not only by green tests | about 20% of "solved" SWE-bench patches fail stronger tests | SWE-ABS and the overfitting study (research) |

Sources (checked 2026-10-31):
- https://code.claude.com/docs/en/best-practices
- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-4-best-practices
- https://learn.chatgpt.com/guides/best-practices
- https://cursor.com/blog/agent-best-practices
- https://docs.github.com/en/copilot/tutorials/coding-agent/get-the-best-results
- https://docs.devin.ai/essential-guidelines/instructing-devin-effectively
- https://blog.buildbetter.ai/how-to-hand-off-bugs-to-a-coding-agent/
- https://alphaxiv.org/abs/2511.21654 (EvilGenie)
- https://www.alphaxiv.org/abs/2603.00520 (SWE-ABS) and https://arxiv.org/pdf/2511.16858

How to compare two racers' results is not covered by any source found; the Judging order in SKILL.md is our own rule.
