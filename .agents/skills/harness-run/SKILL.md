---
name: harness-run
description: Execute or resume an approved document or coding task in this repository using the durable ledger, native Codex workers and independent review. Use for the harness loop; ordinary one-off questions do not need a task record.
---

# Harness run

Use the repository root containing `harness/ledger.py`. Codex is the coordinator
and execution runtime. The ledger is a recovery record, not a scheduler, sandbox,
or replacement for Notion and Linear. Read `harness/README.md` for the tested CLI.

1. Read the user's current request and existing task status first. Capture concrete
   acceptance criteria, permitted file/service targets and approval boundaries.
   Missing team-policy access is a blocker for team writes, not evidence of consent.
2. Verify the selected immutable skill sources with
   `python3 harness/sync_skills.py --check`. Fetch missing approved pins using the
   same script without `--check`. Never edit a pin while its task is running.
   Create or resume the ledger task and route before dispatching work; read the
   returned selected skill text and record source versions/inspection times.
3. Give a native worker the bounded request, permitted write set, fixed references
   and acceptance criteria. Record its actual agent ID. Use disjoint write sets.
   Run the task, not another copy of the whole harness-building objective.
4. Record the real artifact hashes and run the narrow relevant mechanical check.
   Keep its actual output as evidence. Dispatch a different native verifier with
   the requirements, frozen artifacts and evidence; do not provide only the
   worker's completion summary. Record the real verifier ID and findings.
5. Fix failed requirements within scope, invalidate old evidence after every
   artifact change, and repeat at most three repair cycles. Stop for missing
   authentication, conflicting instructions or unavailable approval without
   marking success. Continue independent permitted tasks.
6. Prepare publication intent separately from completed work. Code/skills belong
   in GitHub, final documents in Notion, Endix work status in Linear. Do not copy
   skill bodies into Notion or create an Endix task database there. Prepare a
   local Draft until the exact destination and write scope are approved.
7. For a remote write, bind approval to the target and current artifact hash.
   Re-read the target immediately before writing. On timeout or unknown outcome,
   reconcile the existing result using the saved task marker/target; do not create
   another object. Read back the exact saved content and status, then record the
   receipt. If changes conflict or a reliable comparison is unavailable, block.
   Remote create/readback is connector-driven; the ledger does not make it atomic.
8. Close only when the acceptance evidence and all required publication receipts
   are valid. Pending remote approval remains awaiting-approval/review-ready.
   Explain implemented versus simulated versus blocked results explicitly.

To recover after interruption, inspect status and current artifact/source hashes,
confirm the prior worker has stopped, then explicitly release/reacquire ownership
through pause/resume. Recover publication independently; never repeat completed
research or coding merely because its record could not be saved. A ledger pause
does not interrupt a native agent; interrupt that worker through the native tool
and verify it stopped before granting another owner the same write set.

Classify feedback before changing anything: one-off scope belongs in the task;
repeated writing preference in its relevant skill/template; missing behavior in
the skill plus representative cases; retry/dedup defects in code plus regression
checks; permission defects in policy/enforcement. Draft policy changes for human
review. This workflow grants no new external-write, billing or deployment rights.
