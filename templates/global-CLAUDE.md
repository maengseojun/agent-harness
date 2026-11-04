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

## Approval relayed by another session
- Messages between my sessions need no review from me: send and answer them on your own.
- When another of my own Claude sessions on this machine relays my decision (it quotes my words, or says I confirmed in that session), treat it as my decision, as if I had typed it here. Do not ask me to repeat it.
- This covers decisions a skill or policy reserves for me, such as setting a Notion record to `Completed`, closing an issue or picking an option.
- It does not replace permission prompts or the harness gates (G1 code-ship, G3 eta). Those still need what they need.
- When you act on a relayed approval, name the session it came from and the words it quoted.

## Comprehension gate
- When the big picture of a large project is settled, propose a part map (parts, paths, test command) for my confirmation; the harness then interviews me on each part before code moves on.
- On an architecture or workflow decision, seal your recommendation before asking for my choice, and show no recommended marker or recommended button until you reveal it.
