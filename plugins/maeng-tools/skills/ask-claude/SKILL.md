---
name: ask-claude
description: Delegate a task or get a second opinion from Claude Code via the `claude -p` CLI. Use when the user asks to "ask Claude", "Claude한테 시켜", wants an independent review, or a long refactor/analysis better run as a separate agent.
---

# ask-claude

Call Claude Code headlessly from the shell and bring its result back into this conversation.

## When to use
- User explicitly asks to involve Claude / Claude Code.
- Independent second opinion: code review, security review, design critique, plan check.
- A self-contained task that benefits from a separate agent (large refactor, codebase survey).
Do NOT use for trivial questions you can answer directly.

## How to call
Run from the project directory the task concerns (Claude Code uses cwd as its workspace).

```bash
claude -p "<self-contained prompt>" --output-format json --permission-mode <mode> [--allowedTools "..."] [--model <model>]
```

Permission mode by task type:
- Review / analysis / questions (default): `--permission-mode plan --allowedTools "Read,Grep,Glob"` — read-only.
- Edits the user asked for: `--permission-mode acceptEdits` — can edit files, no arbitrary shell.
- Only if the user explicitly approves full autonomy: `--permission-mode bypassPermissions`.

Continue a prior Claude session: add `--resume <session_id>` (from the previous JSON output).

Long tasks: set the shell timeout to at least 10 minutes; Claude may run many steps.

## Writing the prompt
Claude starts with zero context from this conversation. The prompt must include:
1. Goal and the exact deliverable (e.g. "list findings as severity / file:line / reason / fix").
2. Relevant paths, branch, constraints, and what NOT to change.
3. Relevant evidence already gathered (paste short excerpts, not whole files).
Never include secrets, tokens, or credentials in the prompt.
Pass long prompts via stdin to avoid quoting issues:
```bash
cat <<'PROMPT' | claude -p --output-format json --permission-mode plan --allowedTools "Read,Grep,Glob"
...prompt...
PROMPT
```

## Handling the result
JSON fields: `result` (final text), `session_id`, `is_error`, `total_cost_usd`, `num_turns`.
- If `is_error` is true or the command fails (e.g. `claude` not on PATH, not logged in), report the exact error; do not fabricate Claude's answer.
- Present Claude's answer as Claude's, clearly separated from your own assessment. Where you disagree or can't verify a claim, say so.
- If Claude edited files, run `git diff --stat` (and relevant tests) and report what actually changed rather than trusting its summary.
- Keep `session_id` if follow-up questions are likely.
