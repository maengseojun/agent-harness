# Review tiers and shipping

Author is never the reviewer. `maeng-review` runs a read-only `codex exec` reviewer and writes a verdict bound to the exact subject; run `maeng-review --help` for the current flags.

Commands (tier is picked from the bound issue; see the table below):

| Subject | Command |
|---|---|
| Child-task PR / small work | `maeng-review run --kind code --pr <N>` |
| Parent integration | `maeng-review run --kind parent --pr <N>` |
| Design / rules doc | `maeng-review run --kind docs --draft <path>` |
| Notion outcome payload | `maeng-review run --kind notion --payload publish/<id>.json --destination <db-or-page-id> --op create\|update --draft wiki/drafts/DRAFT-….md` |
| Uncertain outcome | `maeng-review reconcile` (add `--notion` for Notion journal entries) |

Store payloads under the session repo's `publish/` directory (`publish/<id>.json`, git-ignored) so the reviewed bytes and the published bytes are the same file.

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

- Shipping commands must use a **canonical form**: one plain command, no `&&`/`;`/pipes, no `git -c`, wrappers, env prefixes or `$(...)`. Non-canonical forms are denied by design (design D-6):
  - `git push <remote> <branch>` or `git push <remote> <src>:refs/heads/<name>` (optionally `-u`), after the tree is ship-verified;
  - `gh pr create --base <b> --head <h> --title "<t>" --body-file <file>` (also `--draft`, `-R <owner/repo>`); the remote head must be the verified commit, so push first;
  - `maeng-ship merge <PR>` (the only merge route).
- The remote must be plain (one URL, no mirror, no `remote.<r>.push`, no `push.followTags`) and its default branch known; if a push is denied for an unknown default branch, run `git remote set-head <remote> --auto` once.
- Merge is only `maeng-ship merge <PR>`: it requires the base to be an ancestor of the head, a ship-verified head tree and a matching `pass` receipt, then does a lease-guarded fast-forward push. If it reports "base moved", update the branch, re-verify, re-review.
- Denied routes: `gh pr merge` (all modes), `gh pr update-branch`, force pushes, pushes to the default branch except via `maeng-ship`, contents-API writes, `mcp__github__merge_pull_request`.
- After `gh pr create`, the hook reminds you which review tier applies.
