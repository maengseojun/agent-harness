---
name: foundry-testing
description: "Use when you write, review or debug Foundry tests for Solidity: unit, fuzz and invariant tests, handlers and ghost variables, cheatcodes, the test settings in foundry.toml, or a test that passes when it should fail. Know-how for Foundry 1.8 and Solidity 0.8.37. The eta test rules are in eta-tests."
---

# Foundry testing

Write tests that go red when the code is wrong. A green run proves nothing until you know the test can fail, so
break the code on purpose and watch the suite catch it (last section).

Every behavior below was run on forge 1.7.1 with solc 0.8.37, except the items marked "1.8", which come from the
Foundry v1.8.0 release notes and were not run.

## Pick the form

| You want to show | Use |
| --- | --- |
| One named case, a boundary, or one revert | Unit test, one exact expected value |
| A property for every input in a range | Fuzz test (`testFuzz_...`) |
| A property after any sequence of calls | Invariant test (`invariant_...`) with a handler |
| Math is right (prices, fees, share conversion) | Golden vectors from an independent model |

Take golden vectors from exact integer arithmetic outside the contract (Python integers, a spreadsheet) and commit
the numbers in the test. A contract is never the source of its own expected values. For money math write the
golden vectors and the property tests: the first pins the cases you thought of, the second finds the ones you did not.

## Fuzz tests

- `bound(x, min, max)` maps any input into the range. It returns `x` unchanged when `x` is already in range, and it
  wraps 0 to 3 and max-3 to max onto the ends, so the edges are still tried (read in forge-std `StdUtils`).
  `vm.assume(cond)` throws the input away. A narrow `assume` fails the test with "`vm.assume` rejected too many
  inputs (65536 allowed)". Use `assume` to drop one or two values (the zero address), and `bound` for ranges.
- Bound to the range the system really sees, not to the type. A raw `uint256` is mostly near 1e70, so a
  multiplication just overflows and the test checks nothing. Take limits from the real supply, price scale and
  decimals, and widen them on purpose.
- Fuzz the setup as well as the call: the first deposit's size, the time that passed, the state before the call.
- Assert a property, not the formula again. A test that re-implements the function copies its bug. Good properties:
  a round trip never gains, parts add up to the total, a value never moves the wrong way, a result stays in range.
- Check the direction of a rounding against the exact ratio, with no division in the test:
  `assertLe(vault.previewRedeem(x) * supply, x * assets)`. A deposit-then-redeem round trip is a weaker test: in a
  vault, flipping the redeem rounding to round up passed the round-trip fuzz test and failed the direction test at once.
- The fuzzer also feeds literals from your source as inputs. A test with `vm.assume(x == 1234567)` passes because
  1234567 is in the file.
- A fuzz test fails on any revert (`fail_on_revert = true` in `[fuzz]` by default). Expect a revert with
  `vm.expectRevert`.
- A failing case is saved in `cache/fuzz` and replayed on the next run. `--fuzz-seed <n>` fixes the seed and
  `--rerun` runs only the last failures. A fresh CI checkout has no saved cases.

## Invariant tests

Foundry calls random functions on the target contracts, from random senders, `depth` calls in each sequence and
`runs` sequences (defaults 500 and 256). After every call it checks every `invariant_` function.

**Handler.** Point the campaign at a handler, a contract you write that stands between the fuzzer and the system:
it bounds inputs to valid ones, picks an actor, makes the call and records ghost variables. Without one, almost
every call reverts and the campaign tests nothing.

```solidity
contract VaultHandler is Test {
    Vault internal immutable vault;
    MockToken internal immutable token;
    address[] internal actors;
    address internal current;
    uint256 public ghostDeposited;                  // ghost: every asset the vault received
    uint256 public priceFell;                       // ghost: set to 1 when a call lowered the share price
    mapping(bytes32 name => uint256) public calls;  // how often each function really ran

    modifier useActor(uint256 seed) {
        current = actors[bound(seed, 0, actors.length - 1)];
        vm.startPrank(current);
        _;
        vm.stopPrank();
    }

    function deposit(uint256 seed, uint256 amount) external useActor(seed) {
        uint256 bal = token.balanceOf(current);
        if (bal == 0) return;                       // no valid input: skip, do not revert
        amount = bound(amount, 1, bal);
        uint256 before = vault.previewRedeem(1e18);
        vault.deposit(amount, 0, current);
        ghostDeposited += amount;
        calls["deposit"]++;
        if (vault.previewRedeem(1e18) < before) priceFell = 1;   // record; the invariant asserts it
    }
}

// in the test contract
function setUp() public { /* deploy */ targetContract(address(handler)); }
function invariant_balanceCoversTotalAssets() public view {
    assertGe(token.balanceOf(address(vault)), vault.totalAssets());
}
function invariant_sharePriceNeverFalls() public view { assertEq(handler.priceFell(), 0); }
```

- **Reverts hide failures.** `fail_on_revert` is false for invariants by default, so a revert inside the handler is
  ignored, and that includes a failed `assert` inside the handler. A handler whose only job was `assertTrue(false)`
  ran 4096 calls, 4096 reverts, and the invariant test passed. Do not assert inside a handler. Record the
  violation in a ghost variable and assert the ghost in an `invariant_` function, or set `fail_on_revert = true`
  when every handler call must succeed.
- **Read the metrics table** (calls, reverts and discards for each selector; `show_metrics`). A selector whose calls
  all revert is untested. Count how often each handler function really ran, and print the counts in `afterInvariant()`.
- Only state-changing functions are targets. A `view` or `pure` handler function is never called, and a handler with
  nothing else fails with "No contracts to fuzz".
- Name the target yourself with `targetContract`. Narrow it with `targetSelector` and `excludeSelector`, and set the
  callers with `targetSender`.
- A **ghost variable** is a ledger kept outside the system (all assets deposited, all redeemed, the last price).
  The invariant compares the system with the ledger.
- Good invariants: conservation (the balance covers what is owed), the parts add up to the total, a value never
  moves the wrong way, a value stays between its bounds. Write each as one `view` function named for the property.
- Give the handler the hostile moves too: a `donate` function that sends tokens straight to the contract, a
  `warp` function that moves time by a bounded step. `max_time_delay` and `max_block_delay` in `[invariant]` let the
  fuzzer itself advance time and blocks between calls by up to that much (with `max_time_delay = 500` the gap
  between calls reached 494 seconds; by default there is no gap).
- Keep one campaign that targets the contract directly, with no handler, as a catch-all: a function added later is
  fuzzed with no handler change. Most of its calls revert, so it finds little by itself.
- A failing sequence is printed and shrunk (`shrink_run_limit`). It is saved in `cache/invariant` and replayed
  first on the next run, so a local rerun can look like "found every time".

## Cheatcodes that bite

- `vm.prank` covers only the next external call, and an argument that is itself an external call uses it up.
  `vm.prank(a); vault.redeem(vault.balanceOf(a))` called `redeem` from the test contract. Read the value into a
  local first, or use `vm.startPrank` and `vm.stopPrank`.
- `vm.expectRevert` needs the revert to happen one call deeper than the cheatcode. A revert in an internal function
  of the test fails with "call didn't revert at a lower depth than cheatcode call depth". Call an external function.
- Pass the error: `vm.expectRevert(Vault.ZeroShares.selector)` or
  `vm.expectRevert(abi.encodeWithSelector(Vault.Slippage.selector, got, limit))`. A bare `vm.expectRevert()` accepts
  any revert, including the wrong one.
- `vm.expectEmit` checks only the fields you switch on, and the expected event must be emitted right after it and
  before the call.
- A low-level call to an address with no code succeeds and returns empty data. An address you never deployed in a
  test is not a failing dependency. Deploy a mock, or `vm.etch` one.
- `vm.warp` and `vm.roll` set the time and block for the next calls. Use `makeAddr("name")` and `deal` for actors
  and balances.

## Hostile dependencies

Test each way a dependency can go wrong with a small mock, one test per mock: a token that takes a fee on transfer,
returns `false` instead of reverting, returns nothing, calls back into the caller, changes balances by itself
(rebasing), blocks a receiver, or has 0 or more than 18 decimals. A fee token is ten lines: override `_update` to
burn 1% of each transfer, and assert that the contract credits what arrived, not what was sent.

## Settings

```toml
[profile.default]
solc = "0.8.37"
evm_version = "cancun"       # set it to what the target chain supports
deny = "warnings"            # a warning fails the build (deny_warnings is deprecated)
fuzz.runs = 256
invariant.runs = 64
invariant.depth = 64

[profile.deep]               # FOUNDRY_PROFILE=deep forge test, for a scheduled run
fuzz.runs = 10000
invariant.runs = 1000
invariant.depth = 200
```

- Pin a seed in CI (`FOUNDRY_FUZZ_SEED`, or `--fuzz-seed`) so a red run can be reproduced, and use more runs on a schedule.
- `forge build` runs `forge lint`, and under `deny = "warnings"` a lint finding fails the build. Silence one
  finding in source, with the reason, as `// forge-lint: disable-next-line(block-timestamp)`.
- `forge test --match-test x` exits 0 when no test matches. A gate that runs named tests must also check how many ran.
- 1.8: isolate mode is the default (each top-level call runs as its own transaction, so gas and warm or cold
  storage costs match a real one: re-baseline gas snapshots). `forge fuzz` replays and minimizes saved cases.

## Check the tests

- Break the code on purpose: flip a rounding direction, change a `<` to `<=`, delete a check. The suite must go
  red. In one vault and one auction built for this skill, every flip was caught by at least one test, and for the
  vault's redeem rounding only the direction test and the price invariant caught it, not the round-trip fuzz test.
- 1.8: `forge test --mutate` does this for you. It has no threshold flag yet; read `mutation_score` and
  `survived_mutants` from `--json`. It refuses a project with `ffi = true`. Necessist removes statements from a
  test and reports the tests that still pass.
- Coverage shows which lines ran, not which were checked.
- A test with no assertion, a `try/catch` that swallows the failure, and an `assert` inside an `if` pass for ever.

## Where an eta rule applies

- Test names, error selectors, fuzz bounds, the fixture, test rows: eta rule: load eta-tests.
- The contract under test in `src/`: eta rule: load eta-security and eta-code-style; NatSpec: eta-natspec.
- Tests for a part: eta rule: load the part's skill (eta-mint-redeem, eta-rebalancing, eta-amm, eta-hypercore).
- Math that needs a derivation or a proof first: proof-guided-optimization.
- Related craft skills: writing-a-vault, writing-an-auction, solidity-habits.
