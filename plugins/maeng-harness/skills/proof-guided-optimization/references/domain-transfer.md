# Apply the workflow to an engineering domain

These checks are an **engineering transfer proposal (E)**. The sampled math
sources do not establish that they improve DeFi safety, database reliability, or
algorithm performance. Use the actual protocol, schema, code, theorem, and workload
as evidence. Read only the relevant section.

## DeFi calculations

Record the invariant, fee order, token units and decimals, fixed-point scale,
integer width, rounding direction, and who absorbs rounding. Follow each hop's
actual integer operations, including intermediate overflow and accumulated error;
do not compute one continuous quote and round only at the end. State the reserve
snapshot and execution assumptions, then compare net results after fees, slippage,
and gas in consistent units. For a search procedure, justify monotonicity, a
feasible bracket, termination, and an error bound. Check small amounts and boundary
states against an exact oracle where available. A snapshot-optimal route is not an
execution guarantee. Analysis does not authorize a live transaction.

## Database and data flow

Define the database's responsibility, source of truth, read/write mix, scale,
skew, concurrency, consistency/finality, freshness, and failure/recovery target
before choosing an engine or architecture. Trace each record from source through
writes and reads, including identity, duplicates, retries, ordering, reorgs, and
reconciliation when they apply. Compare existing constraints, indexes, query
changes, and batching before adding cache, denormalization, or sharding. Include
I/O, network, locking, write amplification, storage, and recovery costs, not only
CPU complexity. Verify projections on representative replay prefixes and recovery
states; use an execution plan and workload measurement when available. Do not call
a design exactly-once or production-ready from one successful replay.

## Algorithms and multi-stage designs

State the allowed input class, size and encoding, exact or approximate output,
error tolerance, resource budget, and worst-case/expected/amortized model. Clarify
whether precision is fixed or part of the input. Choose exact, approximate, or
heuristic methods against those requirements. General hardness does not establish
hardness of a restricted input family. For composed stages, include conversion and
coordination costs and show that each stage's output satisfies the next stage's
preconditions. Check a small exact oracle and adversarial boundaries when they can
decide correctness; claim measured speed only after measuring the relevant workload.

## Keep transfers narrow

Do not treat a mathematical signed cancellation as a financial guarantee, an
algebraic embedding as database identity, or an existing witness as operational
recoverability. Transfer the question to ask—what information, invariant, or cost
must cross each step—then establish the answer from the actual domain artifacts.
