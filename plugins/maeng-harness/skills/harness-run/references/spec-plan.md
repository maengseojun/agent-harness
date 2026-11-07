# Spec and Plan templates

Each task has two Linear documents. The Spec holds the `Deliverable`, `must_haves`, the `AC-n` criteria, the `D-n` decisions and the `A-n` assumptions; the Plan holds readiness, routing, steps (citing the `AC-n` they advance), the `Verification` line for every `AC-n`, the `Revisions` log and the `Close-out`. Header of both: `status: draft|current|superseded`, task id, parent id, source links, `updatedAt` seen. A draft is not an execution criterion. A superseded document points to its replacement.

## Spec

```
# Spec: <task title>   (MAE-n, parent MAE-p)
Goal: <one sentence>
Deliverable: <what the user receives, in their terms: form (PR, page, Notion record, message),
             language, length or density, visual or text>
Decisions: D-1 <decision> (reason) - wrong if: <signal> ...   # ids shared with the parent; link, do not restate
                                                             # signal: what would show it was wrong; "none (taste|scope|process)" is fine
Assumptions: A-1 <a choice the user did not state that this Spec fills in: product behavior,
             default value, chain or environment, why a part exists> ...   # "none" is fine
Owns: <paths/modules this task may change>
Exclusions: <explicitly not in scope, in the user's terms, including what was simplified away
            (parts, options, gates) so the user can ask for it back>
Inputs / unresolved: <what is missing>

must_haves:
  truths:      # observable facts that hold when done
    - T1: <statement a check can falsify>
  artifacts:   # files that must exist and what they must contain
    - A1: <path> - <what it provides>
  key_links:   # connections that must be wired
    - K1: <from> -> <to> via <mechanism>

Requirements -> acceptance:
  AC-1: <criterion>   covers T1, A1
  AC-2: <criterion>   covers K1
```

Every requirement maps to an `AC-n`; every `AC-n` maps to a responsible task. Missing ownership or verification means the task is not ready.

## Plan

```
# Plan: <task title>
Readiness: dependencies done? inputs present? Spec status current? every A-n confirmed?
Environment: <tooling, versions, branch>
Routing: implement <model/tool>, review <model/tool>, research <tool, if any>; limits: <quota or availability known now, or none>
Steps:
  1. <step> - done when: <criterion, numbered AC-n it advances>
  2. ...
Sub-tasks:         # harness-run "Sub-tasks"; Grade = quick | standard | deep | design (policy/roles.json grades),
                   # or planner = the session itself does the row (no table row)
  | # | Do | Grade | Writes | Interfaces | Done | Fails-if | After |
  |---|---|---|---|---|---|---|---|
  | S1 | <one deliverable> | <grade> | <files> | <names consumed or produced> | <one command and its expected output> | <what makes it not done, incl. a vacuous pass> | <rows it waits for> |
Verification tier: docs-only | code | gate-code   # verification.md "Verification tiers": what runs while working
                                                  # (affected tests) vs once at the final tree (ship check)
Verification:      # one line per criterion; this is what the gates read (ship checks only, not the inner loop)
  AC-1: <exact command or declared check> expect <result>
  AC-2: <exact command or `maeng-verify ran` check> expect <result>
Failure / change handling: <what to do when a step fails; allowed Plan changes>
Review focus: <what the reviewer should attack>
Revisions:         # one line each time the user corrects the plan or the result
  R-1 <plan|result> <intent|scope|format|constraint|overbuild|criteria|verification|reuse|order|quality> <what changed>
Close-out:         # filled when the task closes; copied into the outcome record
  size: <lines changed> / <files changed>   (from the PR)
  revisions: plan <n> / result <n>
  review rounds to pass: <n>
  unmet AC at close: <n>
```

Rules:
- Finer criteria at depth: a parent has integration criteria (the children meet), children have unit-level ones.
- A slight Plan change (order, file choice within Owns) may proceed when goal, scope, constraints and criteria are unchanged; update the Plan and log previous/new approach and reason. A change to criteria or Owns needs re-agreement first.
- Each criterion names its check in `Verification`, otherwise the gate cannot decide "met".
- A `D-n` is a choice the user made or agreed to; an `A-n` is one the agent filled in. The CEO confirms every `A-n` with the Plan approval. An `A-n` the user changes becomes a `D-n` or is dropped, and is logged in `Revisions`.
- An assumption made mid-task (harness-run: "note the assumption and keep going") is added as an `A-n` and listed in the CEO brief, so it is confirmed once, not found in the result.
- `Revisions` and `Close-out` are the data for judging whether planning helps (Paxel review, MAE-301). When one category repeats with the same content across three tasks, move it to a standing rule instead of asking it in every Plan.

## Reviewer starting point (falsify-first)

"The goal is not achieved." Go through `must_haves`: for each truth, artifact and key link, find the evidence it holds. Fail the task if any has none. Also check missing, extra and misunderstood requirements before judging code quality.
