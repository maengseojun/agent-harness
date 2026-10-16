# Review tiers and shipping

Author is never the reviewer. `maeng-review` runs a read-only `codex exec` reviewer and writes a verdict bound to the exact subject; run `maeng-review --help` for the current flags.

| Subject | Reviewer | Effort | Use when |
|---|---|---|---|
| Child-task PR in a structured implementation | Astra | medium | the bound issue has a parent and the task has a Plan with `AC-n` |
| Parent integration / boundary (children meet) | Astra | xhigh | children merged; review the combined diff against the parent Spec/Plan and child contracts |
| Architecture, rules, design documents | Astra | high | document review |
| Small implementation without a task tree | Sol | xhigh | no parent/child structure |
| Notion outcome payload | Sol | medium | `work-records` flow |
| Research draft | Sol xhigh (small) or Astra (structured) | per tier | `aside-research`, with a devil's-advocate lens |

## Bundle (reviewer reports `blocked` if anything is missing)

- Code: repo, PR, base/head SHAs, diff, full changed files, Spec/Plan `AC-n` with `updatedAt`, verification evidence (tree ids, commands, results).
- Parent: plus the child Spec/Plans and their merged PRs.
- Docs: document, digest, the requirements it answers.
- Notion: payload, digest, draft, sources.

## Verdict handling

Verdict `{verdict, subject, reviewer, findings[]}` is stored per subject. Route it to a Linear comment on the bound issue and to `wiki/reviews/REV-<MAE>-<YYYYMMDD-HHMM>-<digest7>.md`. On `fail`: fix each finding, re-verify, request a new review (new head means a new subject).

## Receipts

Single use. A `pass` receipt is consumed only when the gated action succeeded (merge push accepted; Notion create/update read back). A rejected action leaves it unconsumed. A changed head, base, criteria or digest needs a new review. If the client failed but the remote may have changed, the receipt stays `pending` until `maeng-review reconcile`.

## Shipping

- Feature-branch `git push` and `gh pr create` need a ship-verified tree.
- Merge is only `maeng-ship merge <PR>`: it requires the base to be an ancestor of the head, a ship-verified head tree and a matching `pass` receipt, then does a lease-guarded fast-forward push. If it reports "base moved", update the branch, re-verify, re-review.
- Denied routes: `gh pr merge` (all modes), `gh pr update-branch`, force pushes, pushes to the default branch except via `maeng-ship`, contents-API writes, `mcp__github__merge_pull_request`.
- After `gh pr create`, the hook reminds you which review tier applies.
