# Choose a branch by the current obstacle

These are conditional workflow proposals (**S**) drawn from selected observations
(**O**) in the cited public reasoning summaries and manuscripts. They are not
theorems about how problems must be solved. If a branch does not change the next
candidate, skip it. See [sources.md](sources.md) for fixed revisions, page locators,
and limits.

## B01 — Repeated progress with accumulating cost

Use when a useful step repeats and its cost, precision, or memory may grow. Split
the state into a progress measure and resources that must be carried. Write the
transition and total cost. Test only structures the problem supports: a potential
that sums uneven progress, a genuinely one-way layered cost, or a current guarantee
whose future witness cost is charged to a later budget. Carry only the state needed
by the next step. Expand the recurrence through termination; do not invent layers
when a same-layer cost remains or hide an unknown witness in a prior choice.

## B02 — Cancellation or structure lost under a bound

Use when absolute values, scalarization, or independent estimates erase a needed
margin. Keep signs, correlations, or matrix terms together only where an exact
identity supports it. After cancellation, separately bound residual, boundary,
cutoff, commutator, and small-denominator costs. Compare terms under the same
normalization. If the identity is absent, do not assume cancellation; if the
remaining costs exceed the target margin, change candidates.

## B03 — Sampling, conditioning, or information transfer

Use when local or sampled success must support a downstream guarantee. Write the
actual law, comparison law, conditioning event, normalization, and information
available to each step. Identify what the consumer needs: a mean, a finite
marginal, or a joint/path law. Carry only a transfer statement of that strength,
including lost mass and normalization costs. Conditioning on successful cases
does not preserve the original law; matching a first moment does not imply matching
the full distribution.

## B04 — Sharp bounds, nonzero witnesses, or certificates

Use when the result turns on feasibility, nonvanishing, a sharp constant, or a
checkable certificate. Establish that the compared bounds apply to the same object,
input, and normalization. Prove the witness exists before relying on its bound;
include denominators, rounding, and strict-gap costs. If equality is the target,
derive its zero-residual conditions separately. A supplied sharp bound is a premise
unless its proof is independently established.

## B05 — Limits, closure, or extension

Use when a finite construction does not yet imply the final object. State the
topology and property that must survive. Order limits and cutoffs, identify fixed
parameters and uniform bounds, and account for tails or earlier witnesses. Name
the final closure or extension obligation. Pointwise convergence does not supply
a uniform conclusion; an infimum need not be attained; distributional preservation
does not by itself prove generation of an algebra.

## B06 — A witness against a universal claim

This narrow branch is supported by one result family (F197), not a general
experimental success rate. Use only when one valid counterexample is sufficient. State the allowed input class
and violation first. A matrix, finite, or otherwise simplified defect needs an
explicit map or certificate back into the target class. Check every transfer step,
including injectivity or nonvanishing where relevant, and separate an existence
argument from a witness that was actually constructed and run. A counterexample
outside the stated class does not refute the claim.
