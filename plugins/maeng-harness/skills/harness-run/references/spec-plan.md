# Spec and Plan templates

Each task has two Linear documents. The Spec holds `must_haves`, the `AC-n` criteria and the `D-n` decisions; the Plan holds readiness, steps (citing the `AC-n` they advance) and the `Verification` line for every `AC-n`. Header of both: `status: draft|current|superseded`, task id, parent id, `DRI:` (task-tree work, org-chart.md), source links, `updatedAt` seen. A draft is not an execution criterion. A superseded document points to its replacement.

## Spec

```
# Spec: <task title>   (MAE-n, parent MAE-p)
Goal: <one sentence>
Decisions: D-1 <decision> (reason) - wrong if: <signal> ...   # ids shared with the parent; link, do not restate
                                                             # signal: what would show it was wrong; "none (taste)" is fine
Owns: <paths/modules this task may change>
Exclusions: <explicitly not in scope>
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
Readiness: dependencies done? inputs present? Spec status current?
Environment: <tooling, versions, branch>
Steps:
  1. <step> - done when: <criterion, numbered AC-n it advances>
  2. ...
Verification tier: docs-only | code | gate-code   # verification.md "Verification tiers": what runs while working
                                                  # (affected tests) vs once at the final tree (ship check)
Verification:      # one line per criterion; this is what the gates read (ship checks only, not the inner loop)
  AC-1: <exact command or declared check> expect <result>
  AC-2: <exact command or `maeng-verify ran` check> expect <result>
Failure / change handling: <what to do when a step fails; allowed Plan changes>
Review focus: <what the reviewer should attack>
```

Rules:
- Finer criteria at depth: a parent has integration criteria (the children meet), children have unit-level ones.
- A slight Plan change (order, file choice within Owns) may proceed when goal, scope, constraints and criteria are unchanged; update the Plan and log previous/new approach and reason. A change to criteria or Owns needs re-agreement first.
- Each criterion names its check in `Verification`, otherwise the gate cannot decide "met".

## Reviewer starting point (falsify-first)

"The goal is not achieved." Go through `must_haves`: for each truth, artifact and key link, find the evidence it holds. Fail the task if any has none. Also check missing, extra and misunderstood requirements before judging code quality.
