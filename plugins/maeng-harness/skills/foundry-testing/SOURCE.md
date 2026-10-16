# Source

- **Author:** written new for eta-craft on 2026-10-13 (Claude, for Henry; END-687). Henry asked for the craft skills the team planned: Foundry testing, a vault, an auction and Solidity habits.
- **What it draws on:**
  - The team's own research on Solidity gates and tests (`sol-gates.md`, sections 1.3, 3.1 and 4.1, from the gate research of 2026-10-09): the direct-target invariant suite next to handler suites, the handler argument, Foundry's default settings, a fixed seed per base commit, `forge test` exiting 0 when no test matches, and the Foundry 1.8 items (isolate default, `forge fuzz`, `--mutate`, its `--json` score). The 1.8 items are marked in the skill and were not run.
  - Public sources: the Foundry book (getfoundry.sh: best practices, invariant testing, testing configuration, mutation testing), forge-std `StdUtils` for `bound`, and Optimism's Semgrep rules on `vm.expectRevert` (named in the research).
- **Run, not just read:** every other behavior in the skill was run on 2026-10-13 in a scratch project (forge 1.7.1, solc 0.8.37, forge-std at its 2026-10-05 commit, OpenZeppelin 5.7.0). That includes the `prank` argument trap, `expectRevert` depth, a handler assertion swallowed under `fail_on_revert = false`, `vm.assume` rejects, the `max_time_delay` gap, the settings block, and the two rounding mutations. The scratch project is not in this repo.
- **Why it is here:** a craft skill: know-how with no eta rule (Testing and quality §8, OPS-A4-16). It names eta-tests and the part skills where an eta rule applies.
- **Open:** no eval yet (`evals/foundry-testing/`); Foundry 1.8 itself was not available here.
