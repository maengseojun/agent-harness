---
name: writing-an-auction
description: "Use when you write or review a Dutch auction in Solidity: a price that falls over time until someone fills, with the price path, partial fills, rounding and the accounting of what was sold and paid. Know-how for Solidity 0.8.37 and Foundry. The eta rebalancing rules are in eta-rebalancing."
---

# Writing a Dutch auction

A Dutch auction sells a fixed amount of one token for another at a price that starts high and falls. The first taker
who finds the price worth it fills, all or part. Two things must be right: the price at any moment, and the books
after every fill. The code below was compiled with solc 0.8.37 and tested with forge 1.7.1 in a scratch project.

## The price is a function of time

- Compute the price from the clock each time it is asked: `price(now)` from a start time, a start price, a floor
  price and a duration. Do not store a price that someone must update. A stored price is as old as the last update.
- Name the price with its unit. Here it is buy-token base units per sell-token base unit, scaled by 1e18
  (`priceWad`). Tokens with different decimals are handled by that ratio, never by an assumed 18.
- Before the start the price is the start price. After the end it is the floor, or the auction is closed. Decide
  which, write it in the Spec, and test the three moments: the start, the end, and one second either side.

```solidity
function priceWad() public view returns (uint256) {
    // forge-lint: disable-next-line(block-timestamp)
    if (block.timestamp <= startTime) return startPriceWad;
    uint256 elapsed = block.timestamp - startTime;
    if (elapsed >= duration) return floorPriceWad;
    // the fall is rounded down, so the price is rounded up: never below the exact price
    return startPriceWad - (startPriceWad - floorPriceWad) * elapsed / duration;
}
```

- Shapes: linear is the easiest to prove and test. A stepped price (flat inside each step) lets a taker know the
  price their transaction will pay. A decay by half-life needs an `exp` in fixed point: use a tested fixed-point
  library, check its error bound and input range, and fuzz the price for monotonicity over the whole range,
  because an approximation can step the wrong way at the fine scale.
- Compute a linear fall from the whole difference, as above. A per-second slope taken first
  (`(start - floor) / duration`) drops a remainder, and the curve ends slightly above the floor.
- Validate the parameters at creation: `duration > 0` (it is a divisor), `start >= floor`, `floor > 0`, an amount
  above zero. A start in the past is allowed only if the Spec says so.
- The clock is `block.timestamp`, which a block producer can move by a few seconds. The price error is the slope
  times that shift. Make the slope small enough that the error is acceptable. `forge lint` flags every comparison
  with `block.timestamp`; silence it in place with a reason.
- Set the range around a reference price (an oracle or a pool). Start above it, decay through it, floor below it.
  The band pays for the oracle's error, the taker's gas and the taker's risk. A taker fills near the price where the
  trade is just worth it, so a wider band is a cost to the seller.

## A fill and its books

```solidity
function fill(uint256 sellAmount, uint256 maxPriceWad, address to) external nonReentrant returns (uint256 pay) {
    // forge-lint: disable-next-line(block-timestamp)
    if (block.timestamp < startTime) revert NotStarted();
    uint256 price = priceWad();
    if (price > maxPriceWad) revert PriceTooHigh(price, maxPriceWad);
    uint256 amount = Math.min(sellAmount, remaining);        // a partial fill takes what is left
    if (amount == 0) revert NothingToFill();
    pay = Math.mulDiv(amount, price, WAD, Math.Rounding.Ceil); // the taker pays rounded up: never 0 for amount > 0
    remaining -= amount;                                     // effects first
    sold += amount;
    paid += pay;
    buyToken.safeTransferFrom(msg.sender, seller, pay);      // then the interactions
    sellToken.safeTransfer(to, amount);
}
```

- Round the payment up. The taker pays at least `amount * price`, and a one-unit fill still pays one unit. That
  removes the free-token path: with a floor price above zero there is no fill that pays nothing. If you round the
  payment down, you need a check that refuses a zero payment.
- Take a price limit from the caller (`maxPriceWad`). The price only falls with time, so the limit protects a taker
  from an auction that was reset or replaced before their transaction landed.
- A partial fill is capped at what is left, and the books always balance: `remaining + sold` equals the amount at
  the start, and the contract's sell-token balance equals `remaining`.
- Update the books before the transfers, and guard `fill`. A token that calls back during the transfer could fill
  again at a stale `remaining`.
- A buy token that takes a fee on transfer makes `paid` overstate what the seller got. If the buy token can do that,
  pull the payment into the contract, measure what arrived, and revert if it is less than `pay` (see the odd-token
  list in writing-a-vault).
- A taker who gets the sell tokens first and pays in a callback (a flash-style fill) is a strong feature and a
  reentrancy risk. Add it only on purpose, and check the balance after the callback.
- Say what happens to the unsold rest: who may take it back, and when. The seller must not be able to pull tokens
  out while a fill is open.

## Test it

- **Golden vectors.** Compute the price at chosen times with exact integer arithmetic outside the contract, and
  commit the numbers. For 1.10 down to 0.90 over 3,600 seconds the vectors are: t=0 gives 1.100000000000000000e18,
  t=1 gives 1.099944444444444445e18, t=900 gives 1.05e18, t=1800 gives 1.0e18, t=3599 gives 0.900055555555555556e18,
  t=3600 and later give 0.9e18.
- **Two price properties, not one.** The price is monotone: for `t1 <= t2`, `price(t1) >= price(t2)`, and it stays
  between the floor and the start. The price is never below the exact line:
  `price * duration >= start * duration - (start - floor) * elapsed`. Rounding the fall up instead of down passed
  the monotone test and failed the exact-line test and the golden vectors.
- **Fill properties.** `pay * WAD >= amount * price`, and the overpay is less than one unit. The sold amount plus
  `remaining` equals the start amount. The buy tokens the seller holds equal `paid`.
- **Handler campaign.** A handler with a `warp` step and a `fill` step with bounded amounts, ghost totals for sold
  and paid, and invariants: sold plus remaining is constant, the token balance equals `remaining`, the ledger equals
  the ghosts, the average price paid is at least the floor (foundry-testing).
- **Break it on purpose.** Rounding the payment down failed three tests (the fill fuzz test, the partial fill and
  the one-unit fill).
- Boundaries: `t = start - 1`, `start`, `end - 1`, `end`, `end + 1`, and a time far past the end (a huge
  elapsed must not overflow).

## Mistakes to look for

- A stored price, or a `lastPrice` that goes stale.
- A fall rounded the wrong way, or a slope truncated before it is multiplied.
- `duration == 0`, or `start < floor`, so the price formula divides by zero or underflows.
- A multiplication that overflows for a large `elapsed`: clamp the time first, as `priceWad` does.
- A payment rounded down, so a tiny fill is a gift.
- Effects after the transfer, with no guard.
- A fill that checks the price at one time and charges at another.
- Mixing units: a price in WAD times an amount in token base units with a different scale. Put the scale in the name.

## Where an eta rule applies

- The eta rebalancing auction, its price guard, where sells and buys stop, and what a fill must round and measure:
  eta rule: load eta-rebalancing.
- Anything under `src/`: eta rule: load eta-security, eta-code-style and eta-natspec. Tests: eta-tests.
- Prices that come from HyperCore: eta rule: load eta-hypercore.
- The fill-cost scaling, or a proof that the price path or the rounding is what you claim: proof-guided-optimization.
- Related craft skills: foundry-testing, writing-a-vault, solidity-habits.
