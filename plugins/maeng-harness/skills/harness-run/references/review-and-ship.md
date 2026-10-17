# Review tiers and shipping

Author is never the reviewer. `maeng-review` runs an isolated, read-only reviewer and writes a verdict bound to the exact subject. Codex (Astra/Sol, table below) always comes first. If codex fails 3 times in a row (e.g. usage exhausted), `maeng-review` falls back to an isolated headless `claude -p` reviewer and records `reviewer.fallback_from`: parent integration uses Fable (`claude-fable-5-1`) at medium (`MAENG_FABLE_EFFORT` changes it, only on the user's request); every other subject uses Opus (`claude-opus-5-5`) at the Claude effort in the table. The requested Claude model must appear in the run's `modelUsage` and be the primary one, i.e. the most output tokens; other models it uses internally are recorded as `reviewer.aux_models`; an absent or non-primary requested model is rejected. `MAENG_REVIEW_BACKEND=claude` skips codex and is set only when the user asks. When the user asks, prefix the command (`MAENG_REVIEW_BACKEND=claude maeng-review run ...`); run `maeng-review --help` for the current flags.

Commands (tier is picked from the bound issue; see the table below):

| Subject | Command |
|---|---|
| Child-task PR / small work | `maeng-review run --kind code --pr <N>` |
| Parent integration | `maeng-review run --kind parent --pr <N>` |
| Design / rules doc | `maeng-review run --kind docs --draft <path>` |
| Research draft | `maeng-review run --kind research --draft <path> --source <S- note>` (one `--source` per cited note) |
| Notion outcome payload | `maeng-review run --kind notion --payload publish/<id>.json --destination <db-or-page-id> --op create\|update --draft wiki/drafts/DRAFT-….md` |
| Uncertain outcome | `maeng-review reconcile` (add `--notion` for Notion journal entries) |

Store payloads under the session repo's `publish/` directory (`publish/<id>.json`, git-ignored) so the reviewed bytes and the published bytes are the same file.

| Subject | Codex reviewer | Effort | Claude fallback | Use when |
|---|---|---|---|---|
| Child-task PR in a structured implementation | Sol | xhigh | Opus medium | the bound issue has a parent and the task has a Plan with `AC-n` |
| Parent integration / boundary (children meet) | Astra | high | Fable medium | children merged; review the combined diff against the parent Spec/Plan and child contracts |
| Architecture, rules, design documents | Astra | medium | Opus high | document review |
| Small implementation without a task tree | Sol | high | Opus high | no parent/child structure |
| Notion outcome payload | Sol | medium | Opus medium | `work-records` flow |
| Research draft | Sol | xhigh | Opus high | `aside-research`, with a devil's-advocate lens |

## Bundle (reviewer reports `blocked` if anything is missing)

- Code: repo, PR, base/head SHAs, diff, full changed files, Spec/Plan `AC-n` with `updatedAt`, verification evidence (tree ids, commands, results).
- Parent: plus the child Spec/Plans and their merged PRs.
- Docs: document, digest, the requirements it answers.
- Notion: payload, digest, draft, sources.

## Verdict handling

Verdict `{verdict, subject, reviewer, findings[]}` is stored per subject. Route it to a Linear comment on the bound issue and to `wiki/reviews/REV-<MAE>-<YYYYMMDD-HHMM>-<digest7>.md`. On `fail`: fix each finding, re-verify, request a new review (new head means a new subject).

## Receipts

Single use. Only `maeng-review run` writes usable receipts (`reviewer.provenance: review-run`); `maeng-review store` and fixture receipts exist for the test suite only (`MAENG_TEST_FIXTURES=1`) and the gates reject them otherwise. A `pass` receipt is consumed only when the gated action succeeded (merge push accepted). A rejected action leaves it unconsumed. A changed head, base, criteria or digest needs a new review. If the client failed but the remote may have changed, the receipt stays `pending` until `maeng-review reconcile`.

## Shipping

- The hook blocks only two things: a push to the default branch (`main`/`master`/`trunk`, the remote's HEAD, or `protected_branches`; `--all`/`--mirror` too) and a merge outside `maeng-ship` (`gh pr merge`, `mcp__github__merge_pull_request`/`update_pull_request_branch`). Feature-branch pushes, `gh pr create`, other gh writes, compound commands and force pushes to feature branches are allowed; verify before you push because that is the workflow, not because a gate checks it.
- Merge is only `maeng-ship merge <PR>`: it requires the base to be an ancestor of the head, a ship-verified head tree and a matching `pass` receipt, then does a lease-guarded fast-forward push. If it reports "base moved", update the branch, re-verify, re-review.
- After `gh pr create`, the hook reminds you which review tier applies.
