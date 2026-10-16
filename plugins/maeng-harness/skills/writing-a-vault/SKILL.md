---
name: writing-a-vault
description: "Use when you write or review a vault in Solidity, that is a contract that takes in assets and gives out shares: share math, rounding direction, the first-depositor (inflation) attack, accounting for odd tokens, fees, and the order of calls inside deposit and redeem. Know-how for Solidity 0.8.37 and Foundry. The eta vault rules are in eta-mint-redeem."
---

# Writing a vault

A vault owes its holders assets. Shares are the claim on them. Every line you write either keeps the total that
the vault owes at or below what it holds, or breaks that. The code below was compiled with solc 0.8.37 and tested
with forge 1.7.1 in a scratch project; the attack numbers are from those runs.

## The model

- `totalAssets`: what the vault owes its holders. `totalSupply`: all shares. A share is worth
  `totalAssets / totalSupply`.
- Keep `totalAssets` as your own number, updated by deposit, redeem and fee code. Do not read it from
  `asset.balanceOf(address(this))`. Anyone can send tokens to a contract (a plain transfer, or
  `selfdestruct` for ETH), so the raw balance is a number an attacker can set.
- A vault with several tokens holds one balance per token. Pay out pro rata and round per token:
  `payout[i] = floor(balance[i] * shares / totalSupply)`. Never add two tokens' amounts together.
- If the vault should follow ERC-4626, take its function meanings and its rounding (next section) as they are, so
  integrators can rely on them.

## Round against the caller

Whoever calls pays the rounding. The vault never loses a unit to it.

| Function | Result | Round |
| --- | --- | --- |
| `deposit(assets)` and `previewDeposit` | shares out | down |
| `mint(shares)` and `previewMint` | assets in | up |
| `withdraw(assets)` and `previewWithdraw` | shares burned | up |
| `redeem(shares)` and `previewRedeem` | assets out | down |

- Multiply first and divide last, in full precision: `Math.mulDiv(x, y, d, Math.Rounding.Ceil)` (OpenZeppelin 5.7.0)
  rounds up and `Rounding.Floor` rounds down. A plain `x * y / d` rounds down and can overflow on `x * y`.
- Test the direction against the exact ratio with no division (see foundry-testing):
  `assertLe(previewRedeem(x) * (supply + VS), x * (assets + 1))`. A deposit-then-redeem round trip alone does not
  catch a wrong direction: flipping `previewRedeem` to round up still passed the round-trip fuzz test here.

## The first-depositor attack

With a balance-based price and no protection, the first depositor takes the next depositor's money.

1. The attacker deposits 1 wei and gets 1 share.
2. The attacker sends 10,000 tokens straight to the vault. The price is now 10,000 tokens a share.
3. A victim deposits 10,000 tokens: `10,000e18 * 1 / (10,000e18 + 1)` rounds down to 0 shares.
4. The attacker redeems 1 share and takes everything. Run on a test vault: attacker profit +10,000e18, the
   victim's whole deposit.

Defenses, from cheapest:

- **Internal accounting** (above). A donation changes the balance and not `totalAssets`, so step 2 changes no
  price. A test vault kept the same price after a 10,000-token donation.
- **Revert on zero shares** (and on zero assets out). A deposit that buys nothing is refused, not donated.
- **Virtual shares and a virtual asset**, the form OpenZeppelin's ERC-4626 uses:
  `shares = assets * (totalSupply + 10**offset) / (totalAssets + 1)`. With 1e6 virtual shares on a balance-based
  vault the same attack lost the attacker about 5,000e18, half the donation. Use it with internal accounting, not
  instead of it.
- **A minimum first mint**, with the first shares burned to a dead address, makes the first price expensive to
  move. How big it is, and who may make it, is a decision for the Spec.
- **A `minShares` or `minAssets` argument** on deposit and redeem lets the caller refuse a price that moved.

## A core to start from

```solidity
contract Vault is ReentrancyGuardTransient {
    using SafeERC20 for IERC20;
    using Math for uint256;

    error ZeroShares();
    error Slippage(uint256 got, uint256 limit);
    error InsufficientShares(uint256 have, uint256 want);

    uint256 internal constant VIRTUAL_SHARES = 1e6;
    IERC20 public immutable asset;
    uint256 public totalAssets;   // what the vault owes: never asset.balanceOf(this)
    uint256 public totalSupply;
    mapping(address account => uint256) public balanceOf;

    constructor(IERC20 asset_) { asset = asset_; }

    function previewDeposit(uint256 assets) public view returns (uint256) {   // shares out: round down
        return assets.mulDiv(totalSupply + VIRTUAL_SHARES, totalAssets + 1, Math.Rounding.Floor);
    }
    function previewRedeem(uint256 shares) public view returns (uint256) {    // assets out: round down
        return shares.mulDiv(totalAssets + 1, totalSupply + VIRTUAL_SHARES, Math.Rounding.Floor);
    }

    function deposit(uint256 assets, uint256 minShares, address to) external nonReentrant returns (uint256 shares) {
        uint256 before = asset.balanceOf(address(this));
        asset.safeTransferFrom(msg.sender, address(this), assets);
        uint256 received = asset.balanceOf(address(this)) - before;  // credit what arrived, not what was declared
        shares = previewDeposit(received);
        if (shares == 0) revert ZeroShares();
        if (shares < minShares) revert Slippage(shares, minShares);
        totalAssets += received;
        totalSupply += shares;
        balanceOf[to] += shares;
    }

    function redeem(uint256 shares, uint256 minAssets, address to) external nonReentrant returns (uint256 assets) {
        uint256 have = balanceOf[msg.sender];
        if (have < shares) revert InsufficientShares(have, shares);
        assets = previewRedeem(shares);
        if (assets < minAssets) revert Slippage(assets, minAssets);
        balanceOf[msg.sender] = have - shares;      // effects first
        totalSupply -= shares;
        totalAssets -= assets;
        asset.safeTransfer(to, assets);             // the transfer out is last
    }
}
```

`previewMint`, `previewWithdraw`, `mint` and `withdraw` follow the table: round up with `Math.Rounding.Ceil`.

## Odd tokens

A vault that takes an arbitrary token meets all of these. Say in the Spec which it supports, and write a mock for
each one it must survive (foundry-testing, Hostile dependencies).

- Fee on transfer: the vault receives less than the amount sent. Credit the balance difference, as in `deposit`.
- Rebasing and interest-bearing tokens change a balance with no transfer, so internal accounting goes stale.
  Refuse them, or wrap them first.
- No return value, or `false` instead of a revert: use `SafeERC20` (`safeTransfer`, `safeTransferFrom`).
- A callback on transfer (ERC-777 style, or a token with hooks) lets the sender call back in mid-transfer.
- A blocklist or a pause on the token: one blocked receiver must not stop everyone's exit. Pay out in a way that
  fails for that receiver only, such as a claim they pull.
- An approval that must be set to 0 first: `forceApprove`.
- Zero-amount transfers that revert, and decimals of 0 or more than 18: do not assume 18.

## Order inside a function

1. Checks: validate the arguments, even from a trusted caller.
2. Effects: update every storage variable.
3. Interactions: external calls and transfers last.
4. For a state-changing entry point, end with a check of the vault's own rule, such as "the balance covers
   `totalAssets`".

`deposit` above pulls the tokens before it updates storage, because it needs the amount that arrived. That
breaks the order on purpose, so `nonReentrant` is required there. A guard is the second line: the order is the
first. A view that another contract reads (a share price) can be read while your own transaction is half done, in
a callback. Finish the effects before any external call, so that read sees a consistent state.

## Fees

- Take a fee by minting shares to the fee holder, not by moving assets: holders are diluted by the fee share `f`
  when the fee holder gets `supply * f / (1 - f)` new shares. For `f = 2%` and a supply of 1,000,000 that is
  20,408.16 shares, which is exactly 2% of the new supply.
- A time-based fee is `f = rate * elapsed / SECONDS_PER_YEAR`. Accrue it at the start of every function that
  changes shares or reads the price, so no period is skipped or charged twice.
- Keep rates in basis points with a named constant, and multiply before you divide.

## Exits stay open

- Keep the exit path short: few external calls, no loop over a list a user can grow, no call to a third party
  whose failure blocks the exit unless the Spec says so.
- Write down, per function, what each pause stops and what it leaves open. A vault that users cannot leave is the
  worst failure.

## Test it

- Properties: a round trip never gains; the share price never falls from a user's call; the vault holds at least
  `totalAssets`; the shares add up to `totalSupply`; each conversion rounds against the caller (direction test).
- Cases: the first deposit; a donation, then a deposit; 1 wei; zero; the largest amount; a 6-decimal and an 18-decimal token.
- Hostile tokens: a fee token, a returns-false token, a token that calls back.
- Math: golden vectors from an exact model, not from the contract.
- All of that, with handlers and ghost variables, is in foundry-testing.

## Where an eta rule applies

- The eta vault and the Mint Redeem Router, including what a first mint and a pause must do: eta rule: load
  eta-mint-redeem.
- Anything under `src/`: eta rule: load eta-security, eta-code-style and eta-natspec. Tests: eta-tests.
- A derivation, a rounding proof or a cost bound before you code: proof-guided-optimization.
- Related craft skills: foundry-testing, solidity-habits, writing-an-auction.
