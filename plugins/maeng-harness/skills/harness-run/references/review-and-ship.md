# Review tiers and shipping

Author is never the reviewer. `maeng-review` runs an isolated, read-only reviewer and writes a verdict bound to the exact subject. Codex (Astra/Sol, table below) comes first, except for parent integration. If codex fails 3 times in a row (e.g. usage exhausted), `maeng-review` falls back to an isolated headless `claude -p` Opus (`claude-opus-5-5`) reviewer at the Claude effort in the table and records `reviewer.fallback_from`. Parent integration goes the other way (user decision 2026-11-01, MAE-296): Fable (`claude-fable-5-1`) high reviews first (`MAENG_FABLE_EFFORT` changes the effort, only on the user's request), and when Fable fails (e.g. its usage is exhausted) Astra high is the standby, recorded in `reviewer.fallback_from`. The requested Claude model must appear in the run's `modelUsage` and be the primary one, i.e. the most output tokens; other models it uses internally are recorded as `reviewer.aux_models`; an absent or non-primary requested model is rejected. `MAENG_REVIEW_BACKEND=claude` skips codex and is set only when the user asks. No model reviews its own family's code: when Sol or another Codex model wrote the change, pass `--author codex` and the code review goes to Opus high without trying codex (user decision 2026-11-01, MAE-295); the receipt records `reviewer.author`. When the user asks, prefix the command (`MAENG_REVIEW_BACKEND=claude maeng-review run ...`); run `maeng-review --help` for the current flags.

Commands (tier is picked from the bound issue; see the table below):

| Subject | Command |
|---|---|
| Child-task PR / small work | `maeng-review run --kind code --pr <N>`; with no session binding (background or dots-run sessions) add `--plan docs/design/MAE-<n>-plan.md`, which reads the `AC-n` from that file as committed at `--head`; add `--author codex` when Sol/Codex wrote the change |
| Parent integration | `maeng-review run --kind parent --pr <N>` |
| Design / rules doc | `maeng-review run --kind docs --draft <path>` reviews a draft before it lands. A PR you will merge is reviewed with `--kind code --pr <N>` even when it changes only docs: `maeng-ship merge` accepts only `code` or `parent` receipts (MAE-301) |
| Research draft | `maeng-review run --kind research --draft <path> --source <S- note>` (one `--source` per cited note) |
| Notion outcome payload | `maeng-review run --kind notion --payload publish/<id>.json --destination <db-or-page-id> --op create\|update --draft wiki/drafts/DRAFT-….md` |
| Uncertain outcome | `maeng-review reconcile` (add `--notion` for Notion journal entries) |

Store payloads under the session repo's `publish/` directory (`publish/<id>.json`, git-ignored) so the reviewed bytes and the published bytes are the same file.

The values below come from `policy/roles.json`; a sync test compares them.

| Subject | Codex reviewer | Effort | Claude fallback | Use when |
|---|---|---|---|---|
| Child-task PR in a structured implementation | Sol | xhigh | Opus high | the bound issue has a parent and the task has a Plan with `AC-n` |
| Parent integration / boundary (children meet) | Astra (standby only) | high | Fable high (first) | children merged; review the combined diff against the parent Spec/Plan and child contracts |
| Architecture, rules, design documents | Astra | medium | Opus high | document review of a `--draft`; not a merge receipt |
| Small implementation without a task tree | Sol | high | Opus high | no parent/child structure |
| Either code row above, written by Sol/Codex | none (skipped) | - | Opus high | `--kind code --author codex` |
| Notion outcome payload | Sol | medium | Opus high | `work-records` flow |
| Research draft | Sol | xhigh | Opus high | `aside-research`, with a devil's-advocate lens |

## Bundle (reviewer reports `blocked` if anything is missing)

- Code: repo, PR, base/head SHAs, diff, full changed files, Spec/Plan `AC-n` with `updatedAt`, verification evidence (tree ids, commands, results).
- Parent: plus the child Spec/Plans and their merged PRs.
- Docs: document, digest, the requirements it answers.
- Notion: payload, digest, draft, sources.

## Verdict handling

Verdict `{verdict, subject, reviewer, findings[]}` is stored per subject. Route it to a Linear comment on the bound issue and to `wiki/reviews/REV-<MAE>-<YYYYMMDD-HHMM>-<digest7>.md`. On `fail`: fix each finding, re-verify, request a new review (new head means a new subject).

- **Verify before review.** `maeng-review run` refuses locally, without calling the reviewer and without using a round, when the reviewed head is not ship-verified (the Plan checks have not passed on that exact head). After every fix commit, re-run the checks, then request the review.
- **needs-external-check.** The reviewer reports tool behavior it cannot observe as a low finding titled `needs-external-check: …`; it never makes the verdict fail or blocked by itself. Run that check yourself and put the result in the CEO brief.
- **Round cap.** `maeng-review run --pr N` refuses once the repo and PR already have 4 stored review runs (`--max-rounds`, raised only on the user's word). Before another round, sort the findings into: caused by this diff, pre-existing, real approval bypass; only the first group blocks. At the cap, send the CEO brief and ask for `승인 #N`.
- **Commit status.** On a GitHub repo every code review posts commit status `maeng/review` (success on pass, failure otherwise) on the reviewed head; a posting failure is a warning only. Nothing requires it yet; once rulesets are enabled (eta by its owners, personal repos after a plan upgrade), make `maeng/review` a required check. maeng-ship then has to merge through `gh pr merge` instead of a direct push, because rulesets that require a PR reject that push.

## Receipts

Single use. Only `maeng-review run` writes usable receipts (`reviewer.provenance: review-run`); `maeng-review store` and fixture receipts exist for the test suite only (`MAENG_TEST_FIXTURES=1`) and the gates reject them otherwise. A `pass` receipt is consumed only when the gated action succeeded (merge push accepted). A rejected action leaves it unconsumed. A changed head, base, criteria or digest needs a new review. If the client failed but the remote may have changed, the receipt stays `pending` until `maeng-review reconcile`.

## Shipping

- The hook blocks only: a push to the default branch (`main`/`master`/`trunk`, the remote's HEAD, `protected_branches`, `--all`/`--mirror`, an implicit push whose upstream or `remote.<r>.push` is the default branch, or a push it cannot place); every merge route other than `maeng-ship` (`gh pr merge|update-branch`, `gh api` merge/ref-write endpoints and merge mutations, git/gh aliases that push or merge, `mcp__github__merge_pull_request`/`update_pull_request_branch`); GitHub MCP file writes to the default branch or with no branch; setting `MAENG_TEST_FIXTURES`/`MAENG_GIT`/`MAENG_GH`/`MAENG_HOME`/`MAENG_CACHE_DIR`/`MAENG_CLAUDE` from Bash; and Edit/Write into the harness state directory. Feature-branch pushes (force included), `gh pr create`, other gh writes, compound commands and other `MAENG_*` prefixes are allowed; verify before you push because that is the workflow, not because a gate checks it. In eta checkouts this gate is inert and eta-rules' code hooks govern pushes, except the comprehension gate (below), which runs in every world (user decision D-5).
- Merge is only `maeng-ship merge <PR>`: it requires the base to be an ancestor of the head, a ship-verified head tree and a matching `pass` receipt, then does a lease-guarded fast-forward push. If it reports "base moved", update the branch, re-verify, re-review.
- User approval instead of a review: when the user sends a message starting with `승인 #N` (or `approve #N`), the UserPromptSubmit hook records an approval of PR N at its current head, and `maeng-ship merge N` accepts it in place of the pass receipt. It works once, for that head only, and still needs a ship-verified head. When reviews will not converge, ask the user to send `승인 #N`; never write it yourself. A `승인 #N` that dots (or another agent) relays from the user through `claude -p` counts as the user's approval (user decision 2026-10-18); relay only an approval the user actually gave.
- After `gh pr create`, the hook reminds you which review tier applies.
- Comprehension gate ([comprehension-gate](../../comprehension-gate/SKILL.md), MAE-313): a PR over 150 changed lines, or one touching a part of the repo's part map, also needs the user's merge-quiz pass (bound to the PR's patch id, so a rebase with the same diff keeps it) or their `면제 #N <reason>`. `maeng-ship merge` refuses without it, even with a receipt or `승인 #N`; outside the personal world `gh pr merge` (with or without `--auto`, also inside `sh -c`/`eval`) and the GitHub MCP merge tool are denied the same way. Start the quiz after the review passed. With a part map, Edit/Write on a mapped path is denied until `overall` and that part have a design pass (headless runs are exempt); Edit/Write and Bash naming the interviews directory are denied in every world.
