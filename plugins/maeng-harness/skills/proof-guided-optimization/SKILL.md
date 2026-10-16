---
name: proof-guided-optimization
description: Explore and justify algorithms, DeFi calculations, database designs, and data flows when correctness proofs, complexity bounds, or explicit performance tradeoffs matter. Use for design optimization, including underspecified requests that need a problem model; not routine CRUD or arithmetic.
---

# Proof-guided optimization

Turn an engineering question into a precise model, eliminate invalid approaches,
and recommend the simplest justified design. Separate correctness, optimality
within a stated model, and measured system performance. The research habits are
informed by sampled public reasoning summaries; the workflow is a conditional
synthesis, not OpenAI's internal method or a guarantee of success.

Read only what changes the current decision:

- Read [sources.md](references/sources.md) when explaining provenance, checking a
  repository result, or discussing the evidence limits.
- Read [problem-structures.md](references/problem-structures.md) only when the
  unresolved bottleneck matches one of its branches.
- Read the relevant section of [domain-transfer.md](references/domain-transfer.md)
  for a DeFi, database/data-flow, or algorithm task.

## Model the requested result

Inspect the supplied equations, relevant code and callers, schema, queries, or
design. Preserve the user's objective and constraints. Resolve only missing inputs
that change the answer; otherwise proceed under labeled assumptions.

State the input class, decision variables and units, objective and cost model,
valid outputs and invariants, permitted error, baseline, and acceptance condition
in proportion to the task. Distinguish fixed parameters from values that grow or
are part of the input. For example, “polynomial for each fixed ε” differs from
“polynomial when ε is input.” Do not invent weights for competing objectives.

Use the current implementation, a known algorithm, or a native platform feature
as the baseline. If it already meets the requirement and no measured bottleneck or
stronger theoretical target is supplied, retain it and identify the one check or
measurement that could change the decision.

## Explore, falsify, and refine

Compare only plausible alternatives; a baseline and one strong candidate may be
enough. For each changed representation, state what it preserves, what information
or structure it loses, how the result returns to the requested output, and the
added cost. Describe a candidate as:

`new representation → easier obligation → return obligation → added cost`

Attack the weakest assumption early with a small exact instance, boundary case,
degeneracy, or counterexample. Record whether the result is a contradiction, a
cost failure, an unresolved obligation, or only a small-case pass. A failed route
does not establish impossibility or hardness. Keep exploring by narrowing the
missing lemma, trying a materially different representation, or solving a
restricted case; do not assume an unproved step or repeat an unchanged failed
route without new evidence.

For iteration or composition, track total work, error, memory, progress, and
parameter-choice order as relevant. A one-step gain is not enough if conversions,
conditioning, or refinement consume it. If current acceptance and future witness
cost depend on one another, separate the current guarantee from the budget for
future changes or choose another candidate. Keep unlike resources as a vector.

Select a structure branch only when its obstacle is present:

| Obstacle | Read |
| --- | --- |
| Repeated progress adds an expanding resource cost | B01 in `problem-structures.md` |
| Taking absolute values or scalarizing destroys needed margin | B02 |
| Sampling, conditioning, or local success does not reach the final claim | B03 |
| Sharp bounds, nonzero witnesses, or certificates decide the result | B04 |
| A finite construction works but a limit or extension remains | B05 |
| One valid witness would refute a universal claim | B06 |

These branches are optional synthesis, not universal proof recipes. A problem can
need more than one, but do not run branches that cannot change the candidate.

Use a search budget proportional to the request. Stop when acceptance is met, a
bound closes the relevant gap, the budget is spent, or required input is unavailable.
At the limit, return the best valid result, exact unresolved obligation, attempted
routes, and next decisive experiment. An unresolved lemma alone is not a reason
to stop an authorized search.

## Prove the right claim

For the selected candidate, establish feasibility and correctness first: state
the invariant, its preservation, termination where relevant, and correspondence
to the requested output. Name unresolved obligations. For imported results, check
the actual theorem, hypotheses, quantifiers, parameter order, encoding, precision,
randomness, and approximation convention; a source summary or analogy is not a
verified theorem.

Classify each claim separately:

| Claim | Evidence required |
| --- | --- |
| Globally optimal objective in the model | Feasible solution plus matching bound/certificate, or an applicable exact theorem |
| Asymptotically optimal algorithm | Upper bound and matching lower bound in a stated input and cost model |
| Best among compared candidates | Comparable costs and guarantees for the candidates actually compared |
| Approximation guarantee | Proven ratio or additive bound, direction, assumptions, and tolerance |
| Heuristic or local optimum | State the local conditions or empirical evidence; do not imply a global guarantee |
| Measured improvement | Actual workload, environment, method, results, and limits |

Also distinguish existence, an explicit construction, a computable procedure or
threshold, a proved cost bound, an executed result, and a measured effect. Do not
promote one level to the next. A termination proof is not a practical cost bound;
a saved certificate is not a passed checker. Formalization is optional; use
existing proof tools only when their benefit justifies the cost.

## Domain checks and authorization

Read only the applicable checks in `domain-transfer.md`. They are engineering
guidance and must be grounded in the actual protocol, schema, algorithm, code, and
workload. The research examples do not establish production safety or performance.

Analysis does not authorize a live transaction, deployment, or external data
mutation. Preserve the user's stated permission boundary and obtain authorization
before an action that changes an external system.

## Verify and deliver

Use the smallest decisive check available: a small exact oracle, a certificate
checker, boundary cases, an invariant check, or a representative workload. Tests
and benchmarks do not prove a universal theorem. Separate checks actually run
from proposed checks, and follow project-required checks for code changes. Do not
build a new benchmark framework or install a proof system merely to use this skill.

Lead with the recommendation. Include assumptions that change it, the decisive
comparison, the proof or derivation and unresolved obligations, the cost and
optimality classification, and checks actually performed. Scale the detail to the
request. Preserve a runnable check for nontrivial executable logic; otherwise
concise worked reasoning may suffice.
