# Review tiers and shipping

Author is never the reviewer. `maeng-review` runs an isolated, read-only reviewer and writes a verdict bound to the exact subject. Codex (Astra/Sol, table below) always comes first. If codex fails 3 times in a row (e.g. usage exhausted), `maeng-review` falls back to an isolated headless `claude -p` reviewer and records `reviewer.fallback_from`: parent integration uses Fable (`claude-fable-5-1`) at medium (`MAENG_FABLE_EFFORT` changes it, only on the user's request); every other subject uses Opus (`claude-opus-5-5`) at the Claude effort in the table. The requested Claude model must appear in the run's `modelUsage` and be the primary one, i.e. the most output tokens; other models it uses internally are recorded as `reviewer.aux_models`; an absent or non-primary requested model is rejected. `MAENG_REVIEW_BACKEND=claude` skips codex and is set only when the user asks. The agent cannot set any `MAENG_*` variable from Bash (assignment, `export`, `unset` and `env` forms are denied), so the user sets these in the session environment (their shell or the settings `env` block); run `maeng-review --help` for the current flags.

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

Single use. Only `maeng-review run` writes usable receipts (`reviewer.provenance: review-run`); `maeng-review store` and fixture receipts exist for the test suite only (`MAENG_TEST_FIXTURES=1`) and the gates reject them otherwise. A `pass` receipt is consumed only when the gated action succeeded (merge push accepted; Notion create/update read back). A rejected action leaves it unconsumed. A changed head, base, criteria or digest needs a new review. If the client failed but the remote may have changed, the receipt stays `pending` until `maeng-review reconcile`.

## Shipping

- Shipping commands must use a **canonical form**: one plain command, no `&&`/`;`/pipes, no `git -c`, wrappers, env prefixes or `$(...)`. Non-canonical forms are denied by design (design D-6):
  - `git push <remote> <branch>`, `git push <remote> <local-branch>:<name|refs/heads/name>`, or `git push <remote> <full-commit-sha>:refs/heads/<name>` (a SHA source requires the full `refs/heads/` destination; optionally `-u`), after the tree is ship-verified;
  - `gh pr create -R <owner/repo> --base <b> --head <h> --title "<t>" --body-file <file>` (optionally `--draft`); `-R` is required and must name origin's repository, and the remote head must be the verified commit, so push first;
  - other gh writes (`gh pr comment|edit|review|ready|close`, `gh issue …`) also need an explicit `-R <owner/repo>`;
  - `maeng-ship merge <PR>` (the only merge route);
  - not allowed: git aliases for mutating commands (run the underlying command), `gh api graphql` unless the query is an inspectable literal `-f query='query ...'` (no mutation, `@file`, `--input` or substitution), `gh pr close --delete-branch`, `gh issue|repo|release delete`, `gh repo archive|rename`, and every GitHub MCP tool outside the allowlist (reads, issue/comment/review writes, verified `create_pull_request`).
- The remote must be plain (one URL, no mirror, no `remote.<r>.push`, no `push.followTags`, no recursive submodule push) and its default branch known and current on the server; if a push is denied for an unknown default branch, run `git remote set-head <remote> --auto` once.
- Merge is only `maeng-ship merge <PR>`: it requires the base to be an ancestor of the head, a ship-verified head tree and a matching `pass` receipt, then does a lease-guarded fast-forward push. If it reports "base moved", update the branch, re-verify, re-review.
- Denied routes: `gh pr merge` (all modes), `gh pr update-branch`, force pushes, pushes to the default branch except via `maeng-ship`, contents-API writes, `mcp__github__merge_pull_request`.
- After `gh pr create`, the hook reminds you which review tier applies.
