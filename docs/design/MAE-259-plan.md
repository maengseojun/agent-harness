# MAE-259 Spec/Plan: DRI and the rank communication rules

status: current. Linear: MAE-259 (children MAE-260..264; deferred MAE-265). Date: 2026-10-21. Single PR, personal world only.

## Spec

Goal: give every piece of tree-sized work one named decider who also executes and records what was learned, and make the ranks a communication protocol (what each message carries) instead of a status label, using only what the evidence supports.

Decisions (CEO, 2026-10-21: "제안 1~5 모두 MAE 이슈로 만들고 PR까지 진행해. maeng-review PROMPT와 스키마는 다른 세션 작업 끝난 뒤로 미뤄"):
- D-1 (MAE-260) One `DRI:` line per parent and child Linear issue of a task tree (not in the Spec/Plan, which the reviewer reads): the one agent who decides, executes and records the learning. Default: parent = the Opus session; child = the agent executing it inside the Spec. A sub-agent DRI owns the how and reports what it learned; the parent's DRI passes it relevant earlier learnings, writes the learning lines and judges every `D-n` of the tree at close. Three layers: whether (CEO), what (executive: Spec, AC-n, split, integration), how (executor, inside the Spec). The auditor gives verdicts only; the author decides how to fix (blocking severities unchanged). The CEO brief asks only a whether-question. Signal it was wrong: in the next task trees two agents dispute a decision and the DRI line does not settle it, or CEO briefs still ask how-questions.
- D-2 (MAE-261) Accountability is learning, kept in records because agents forget between sessions: each `D-n` carries a "signal it was wrong" (or "none (taste)"); at close each `D-n` is judged held, broke or open (signal not observable yet; judged later by the next DRI who reads it); a broke decision's DRI sends one learning line through the existing Feedback routes; before deciding, a DRI reads earlier learnings in its area; no blame records. Signal it was wrong: the held/broke judgment is skipped at the close of the next two task trees, or a broke decision recurs without a learning line.
- D-3 (MAE-262) Wildcard: a CEO intervention is a direction (says "앞으로/항상/이제부터" or is phrased as a general rule; recorded as ADR or memory) or a wildcard (this case only; a `wildcard:` line on the issue is its only record, no ADR). The DRI states dissent once, then follows. A third wildcard against the same rule (found by searching personal Linear when one is recorded) triggers a proposed direction in the CEO brief, which becomes one only on the CEO's word. Unclear which: one question at wrap-up. Signal it was wrong: the CEO corrects the classification more than once.
- D-4 (MAE-263) Optional, non-blocking `Dissent:` report line ("against X because Y; proceeding as told"); the DRI records every ruling as `dissent: <X> -> kept|changed` on the issue; the same dissent is not raised again without new evidence. Signal it was wrong: unused across five delegations, or nearly every ruling is "no change" (then drop the line).
- D-5 (MAE-264) Rank communication protocol: a delegation carries `Why:` (purpose and the AC-n it serves) and a stop condition; a repair request carries `Keep:` (what works, by location), `Change:` (location, reason, action) and `Scope:` (only what the fix needs); pushback carries evidence; send-backs follow a check, taste goes into a note; the third repair cycle goes to a fresh agent with a brief that includes what was learned; review requests carry no author rank, self-assessment or praise; rank names route, the body states the job; plain sentences with a reason instead of capitals; per-model delegation lines; the executive translates CEO input into this format. Evidence: Obsidian `wiki/answers/A-AGENT-FRAMING-EVIDENCE.md` (claims verified 2026-10-21). Signal it was wrong: in repair cycles with a `Keep:` list, edits outside the findings' locations do not drop compared with cycles without one.
- D-6 Rules only: no hook, gate, schema or code change. The maeng-review PROMPT and the finding schema wait for MAE-265 (CEO). Signal it was wrong: none (scope).
- D-7 No plugin version bump in this PR; the release is a follow-up commit after approval (as in MAE-257). Signal it was wrong: none (process).
- D-8 MAE-257 D-9 holds: rank names stay out of PR and commit text. Signal it was wrong: a rank name appears in PR or commit text.

Owns: `plugins/maeng-harness/skills/harness-run/references/org-chart.md`, `plugins/maeng-harness/skills/harness-run/SKILL.md`, `plugins/maeng-harness/skills/harness-run/references/spec-plan.md`, `plugins/maeng-tools/agents/{implementer,architect,researcher}.md`, `plugins/maeng-harness/skills/work-records/SKILL.md` (the wildcard exception to CEO-decision ADRs), this plan. Vault note `hubs/areas/A-ORG.md` (record, through Obsidian MCP).

Exclusions: `plugins/maeng-harness/bin/maeng-review` and `schemas/verdict.schema.json` (MAE-265); `review-and-ship.md` (the repair rule lives in org-chart.md and SKILL.md Failure handling); the SessionStart pointer line and its test; the Codex edition under `.agents/`; eta; plugin versions.

must_haves:
  truths:
    - T1: org-chart.md defines the DRI (decides, executes, records the learning), the three layers and their owners, the default DRI for parent and child with the parent's DRI holding the close-out duties for sub-agent DRIs, that the line lives on the Linear issue, and that the auditor's authority is the verdict only.
    - T2: org-chart.md defines direction (an ADR) vs wildcard (only its issue line), dissent once then follow, and the third-wildcard-against-one-rule proposal; work-records exempts wildcards from CEO-decision ADRs.
    - T3: the report format has an optional, non-blocking `Dissent:` line in org-chart.md and in the architect, implementer and researcher definitions; `Verification:` and `Unfinished:` are unchanged.
    - T4: org-chart.md states the delegation `Why:` and stop condition, the repair format (Keep, Change, Scope), evidence-backed pushback, check-based send-backs, the fresh agent at the third cycle, review-request independence, plain wording, the per-model lines and the CEO-input translation.
    - T5: spec-plan.md puts a "signal it was wrong" (or `none (taste|scope|process)`) in the `D-n` format.
    - T6: harness-run SKILL.md wires D-1..D-5: the task tree step names the DRI; the CEO brief asks only a whether-question and lists wildcards and dissent rulings; outcome records judge each `D-n` held or broke and route the learning; Failure handling hands a fix down in the repair format and gives the third cycle to a fresh agent.
    - T7: no new hook, gate, schema or code; no rank names in PR or commit text.
    - T8: no rule claims a quality effect the evidence refutes (encouragement, politeness, threats, tips or expert personas raising quality); every stated reason matches a confirmed or caveated claim of the evidence note.
  artifacts:
    - A1: org-chart.md - "DRI" section (layers, line, learning, wildcard) and the extended "Delegation and reports" section (why, repair, dissent, review independence, wording, per-model lines, CEO input).
    - A2: spec-plan.md - the `D-n` falsifier.
    - A3: implementer.md - how to take a repair request (Keep untouched, Change only, a conflict goes to Escalate and the skipped change to Unfinished).
  key_links:
    - K1: harness-run SKILL.md (task tree, CEO brief, outcome records, Failure handling) -> org-chart.md sections.
    - K2: three agent definitions -> org-chart.md report format, including `Dissent:`.

Requirements -> acceptance:
  AC-1: T1 and the task-tree and CEO-brief parts of T6 hold.   covers T1, A1, K1 (MAE-260)
  AC-2: T5 falsifier and the outcome-records part of T6 hold.   covers A2 (MAE-261)
  AC-3: T2 and the CEO-brief evidence part of T6 hold.   covers T2 (MAE-262)
  AC-4: T3 holds and the suite passes (SubagentStop still finds `Verification:`/`Unfinished:`).   covers T3, K2 (MAE-263)
  AC-5: T4, A3 and the Failure-handling part of T6 hold.   covers T4, A3 (MAE-264)
  AC-6: T7 and T8 hold; the diff touches only Owns.   covers T7, T8

## Plan

Readiness: decisions settled (this conversation, CEO approval quoted above); evidence note written; base `origin/feat/harness-v1` at 51ba44b; branch `feat/mae-259-dri` in worktree `.claude/worktrees/mae-259-dri`.

Sub-tasks:

| Row | Do | Writes | Done | Fails-if | After |
|---|---|---|---|---|---|
| R1 | DRI line and layers | org-chart.md, SKILL.md (task tree, CEO brief) | review item AC-1 | the CEO keeps a how-decision, or the auditor is made a DRI | - |
| R2 | D-n falsifier and close-out judgment | spec-plan.md (D-n), SKILL.md (outcome records, Feedback), org-chart.md (reads first) | review item AC-2 | the falsifier is mandatory for taste decisions, or a blame record appears | R1 |
| R3 | wildcard | org-chart.md, SKILL.md (CEO brief), work-records SKILL.md | review item AC-3 | every CEO correction becomes a standing rule, or a wildcard silently becomes one | R1 |
| R4 | Dissent line | org-chart.md, three agent definitions | review item AC-4; `python3 -m pytest -q` passes | Dissent can block or replaces Escalate; Verification/Unfinished changed | R1 |
| R5 | communication protocol | org-chart.md, implementer.md, SKILL.md (Failure handling) | review item AC-5 | a rule promises a quality gain from tone or persona; the repair format drops Keep | R4 |
| R6 | integration | all of Owns | `python3 -m pytest -q` at the final tree; `git diff --name-only origin/feat/harness-v1...HEAD` lists only Owns | a path outside Owns, or rank names in PR/commit text | R1..R5 |

Verification tier: docs-only (every changed path matches `**/*.md`).

Verification:
  AC-1: review item (parent review) expect pass
  AC-2: review item (parent review) expect pass
  AC-3: review item (parent review) expect pass
  AC-4: `python3 -m pytest -q` expect pass
  AC-5: review item (parent review) expect pass
  AC-6: review item (parent review) expect pass

Failure / change handling: per harness-run Failure handling; three repair cycles, then split or drop and name it in the CEO brief.

Review focus: does any rule turn a rank into an access restriction, a gate or a status persona; does any stated reason overclaim the evidence (pass `wiki/answers/A-AGENT-FRAMING-EVIDENCE.md` as an evidence file); do the new lines contradict the existing approval lines, the stop list, the one-PR rule or "verify once"; is the wildcard rule implementable without asking the CEO every time; does the doc stay short enough to be read first.
