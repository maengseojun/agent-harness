# Working rules (all repositories)

These apply in every repository. Each repository's own CLAUDE.md / AGENTS.md and its project rules take precedence where they differ.

## Think before coding
- State the assumptions a change depends on. When an ambiguity would change the result, ask one concise question; otherwise pick the conventional option and say so.
- Name real tradeoffs. If a simpler approach meets the goal, say that before building the complex one.

## Keep it simple
- Build what was asked. No speculative features, single-use abstractions, or error handling for cases that cannot happen.

## Change surgically
- Touch only what the request needs. Match the surrounding style, naming and comment density.
- Mention unrelated problems you notice; do not fix them uninvited. Remove only what your own change made unused.

## Work toward checkable goals
- For multi-step work, state a short plan where each step has a check that proves it is done.
- Before calling work finished, run the check and report the real result, including failures and anything skipped.

## Report faithfully
- Separate what you verified from what you inferred. A saved configuration is not proof that something works.
