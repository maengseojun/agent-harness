---
id: ASIDE-SMOKE-20261017
linear: [MAE-222]
date: 2026-10-17
---

# aside exec smoke run (C5 step 1, AC-1)

**Command.** `aside exec --effort low "<COLLECTION ONLY … fixed template>"` with default Guard permission and stdin closed.
- Target: https://github.com/anthropics/claude-plugins-official (public; read-only prompt).
- Result: exit 0 in 12 s. stdout 14,082 bytes; stderr 46 bytes.

**Observed output contract**
- **stderr:** `created new session: <id>` (ANSI-dimmed). Example id: `6kgJz0FfrviB11Ex`. Use it for the sidecar and for `aside session resume <id> "<follow-up>"`.
- **stdout, in this order:**
  1. The agent's REPL tool calls, ANSI-colored.
  2. The **full page snapshot**, which includes the logged-in user's navigation, e.g. "You have unread notifications".
  3. The **final answer, in the requested template**: one `=== ITEM === … === END ===` block with `url`, `title`, `retrieved_at`, `content`.
- **Template compliance:** 1/1 block, all fields present.
- **Not observed:** no JSON mode, no output-file flag. The final answer is not separated from the transcript except by the template markers.

**Consequences for the skills**
- `aside-collect`:
  - always demands the `=== ITEM ===` template;
  - strips ANSI codes;
  - saves the raw output to `raw/aside/<ts>-<slug>.md` and a sidecar `.json` (prompt, model/effort, session id from stderr, timings, exit code);
  - parses **only the last contiguous run of ITEM blocks**;
  - treats the transcript and snapshot as non-source data.
- **Privacy:** the raw snapshot can contain account details from the logged-in browser. Raw files stay in `raw/aside/` and are never promoted. Source notes take only the parsed block fields.
- **Failure handling:** if no ITEM block is found, the agent records `parse_failed` in the sidecar and asks Aside again once via `aside session resume <id> "Reply only in the template"`.
