---
name: solidity-habits
description: "Use when you write or review Solidity and want the habits that prevent bugs and noise: compiler settings, imports, custom errors, constants, safe casts and math, order of calls, events, access control, loops, assembly and gas. Know-how for Solidity 0.8.37 and Foundry 1.8. The eta code rules are in eta-code-style, eta-security and eta-natspec."
---

# Solidity habits

Small habits, each of which closes a class of bug or removes review noise. The snippets were compiled with solc
0.8.37 and forge 1.7.1. Where a habit is also an eta rule, the skill says "eta rule: load" and names the skill that
holds it.

## Build settings

- Pin the compiler in a contract you deploy: `pragma solidity 0.8.37;`. Use a range (`^0.8.20`) only in a library
  or interface that other code imports.
- Make warnings errors: `deny = "warnings"` in `foundry.toml` (the old `deny_warnings = true` is deprecated).
  A compiler warning is the compiler telling you the code does not do what you wrote.
- Set `evm_version` to what the target chain runs. `bool transient locked;` compiles with `cancun` and fails with an
  older version ("Transient storage is not supported by EVM versions older than cancun").
- Run `forge fmt --check` and `forge lint` on every change. `forge lint` runs during `forge build`, and under
  `deny = "warnings"` a finding fails the build. Silence a finding in place, with the reason:
  `// forge-lint: disable-next-line(unsafe-typecast)` and a line saying why the cast is safe.
- Check the size: `forge build --sizes --skip test` shows the margin to the 24,576-byte limit for deployed code.

## Layout and imports

- Order the file as the Solidity style guide does: pragma, imports, then interfaces, libraries and contracts. Inside
  a contract: types, state variables, events, errors, modifiers, then functions by visibility (constructor,
  receive, fallback, external, public, internal, private), with `view` and `pure` last in each group. Keep lines
  to 120 characters.
- Import by name: `import {IERC20} from "..."`. A bare `import "file.sol";` pulls in every name and hides where one
  came from. Delete an import the file no longer uses.
- Keep inheritance shallow, write `override` every time, and mark a function `virtual` only where you designed it
  to be overridden. Prefer a library or a small contract you call over a deep tree.

## Errors, constants and names

- Revert with a custom error that carries the values: `error Slippage(uint256 got, uint256 limit);` and
  `revert Slippage(got, limit);`. It is cheaper than a string, a test can match its selector, and the caller sees the
  numbers. `require(cond, Slippage(got, limit))` also works on 0.8.37 (the Solidity changelog adds it in 0.8.26 for
  the IR pipeline and 0.8.27 for the legacy one; not re-checked here).
- Give every literal a name: `uint256 internal constant BPS_DENOMINATOR = 10_000;`,
  `SECONDS_PER_YEAR = 365 days`, `WAD = 1e18`. Put the unit or the scale in the name (`feeBps`, `priceWad`,
  `durationSeconds`) so a reader cannot add a basis-point value to a WAD value. Use `1e18` and `10_000` forms,
  not a row of zeros.
- Use `immutable` for a value set once in the constructor and `constant` for a compile-time value. Both cost no
  storage read.
- A scaled number can have its own type, so the compiler refuses to mix scales:

```solidity
type Wad is uint256;
using {add as +, mul as *} for Wad global;
function add(Wad a, Wad b) pure returns (Wad) { return Wad.wrap(Wad.unwrap(a) + Wad.unwrap(b)); }
function mul(Wad a, Wad b) pure returns (Wad) { return Wad.wrap(Wad.unwrap(a) * Wad.unwrap(b) / 1e18); }
```

- Naming, the interface file, event names and the Dictionary's words: eta rule: load eta-code-style.

## Arithmetic and casts

- Arithmetic is checked since 0.8, so an overflow reverts. A narrowing cast is not: `uint8(300)` is 44, with no
  revert. Cast with `SafeCast` (`value.toUint128()` reverts when the value does not fit), or check the range first.
- Put `unchecked { ... }` around a line only when you can state why it cannot overflow, and write that reason
  above it. A bare `unchecked` is a bug waiting.
- Multiply before you divide, and choose the rounding on purpose. `x * y / d` rounds down and can overflow on
  `x * y`; `Math.mulDiv(x, y, d, Math.Rounding.Ceil)` is full precision and rounds where you say. Write the
  direction in a comment or the name, and test it (foundry-testing). The rounding of a vault and of an auction:
  writing-a-vault and writing-an-auction.
- Division and modulo by zero revert with a panic. Validate a divisor that comes from a parameter when you set it.
- Do not test a balance with `==`. Anyone can send ETH to a contract with `selfdestruct`, so
  `address(this).balance == x` can be made false from outside.

## Calls and state

- Order a function: checks, then effects (every storage write), then interactions (external calls), last. Add a
  `nonReentrant` guard as the second line, not the first. A transient guard is cheap:
  `bool transient locked;` and a modifier that reverts when it is set.
- Use `SafeERC20` for tokens: `safeTransfer`, `safeTransferFrom` and `forceApprove`. Some tokens return nothing,
  return `false`, or need an approval of 0 before a new one.
- Send ETH with `call{value: x}("")` and check the result. `transfer` and `send` forward only 2,300 gas and fail
  for a receiver that does anything in `receive`.
- A call to an address with no code succeeds and returns nothing. Before a low-level call, check that the target has
  code, or use a high-level call on a typed interface.
- Pull, not push, for anything that can fail for one receiver: record what a user is owed and let them claim it, so
  one reverting receiver cannot block a loop of payouts.
- Give state the narrowest visibility. Make a variable `private` or `internal` and add a getter where callers need
  one. Emit an event right after the state change it reports, and index the fields people filter on.
- Pack storage that is read together (a `uint128` pair, a `uint64` time next to an address) into one slot.
  Copy a storage value into a local when you read it more than once.
- Mark access in one named modifier (`onlyOwner` or a role check) so it is easy to find and to test. Validate
  arguments even from a trusted caller, and check a role setter's address against zero.
- Never use `tx.origin` to decide who may act. Never use `block.timestamp` or `prevrandao` as randomness.

## Loops and assembly

- Bound every loop. Do not loop over an array a user can grow, and do not make an external call inside a loop.
- Avoid inline assembly. If you need it, comment each block with what it assumes and keeps true, and mark it
  `assembly ("memory-safe")` only when it is.
- Use `calldata` for external array and `bytes` parameters you only read.
- Measure before you trade readability for gas: `forge test --gas-report` and `forge snapshot`.

## Before you hand off

- [ ] The build has no warning, `forge fmt --check` and `forge lint` pass.
- [ ] Each external call is last in its function, or has a guard and a reason.
- [ ] Each `unchecked` has its reason, and each cast is a `SafeCast` or a checked range.
- [ ] Each division has its rounding direction stated and tested.
- [ ] No literal without a name, no `require` with a string, no import without a name.

## Where an eta rule applies

- Layout, names, errors, events and math habits in an eta repo: eta rule: load eta-code-style.
- Comments and NatSpec: eta rule: load eta-natspec.
- Anything under `src/` for security: eta rule: load eta-security, and the part's skill (eta-mint-redeem,
  eta-rebalancing, eta-amm, eta-hypercore).
- Tests: eta rule: load eta-tests.
- Related craft skills: foundry-testing, writing-a-vault, writing-an-auction.
