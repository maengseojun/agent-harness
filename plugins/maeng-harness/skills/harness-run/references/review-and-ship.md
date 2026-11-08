# Review tiers and shipping

Follow [Model onboarding](model-onboarding.md) before proposing a model replacement.
Author is never the reviewer. `maeng-review` runs an isolated, read-only reviewer and writes a verdict bound to the exact subject. Codex (Astra/Sol, table below) comes first, except for parent integration. If codex fails 3 times in a row (e.g. usage exhausted), `maeng-review` falls back to an isolated headless `claude -p` Opus (`claude-opus-5-5`) reviewer at the Claude effort in the table and records `reviewer.fallback_from`. Parent integration goes the other way (user decision 2026-11-01, MAE-296): Fable (`claude-fable-5-1`) high reviews first (`MAENG_FABLE_EFFORT` changes the effort, only on the user's request), and when Fable fails (e.g. its usage is exhausted) Astra high is the standby, recorded in `reviewer.fallback_from`. The requested Claude model must appear in the run's `modelUsage` and be the primary one, i.e. the most output tokens; other models it uses internally are recorded as `reviewer.aux_models`; an absent or non-primary requested model is rejected. `MAENG_REVIEW_BACKEND=claude` skips codex and is set only when the user asks. No model reviews its own family's code: when Sol or another Codex model wrote the change, pass `--author codex` and the code review goes to Opus high without trying codex (user decision 2026-11-01, MAE-295); the receipt records `reviewer.author`. `--author-model` and `--planner-model` take exact model ids; a `parent` or `plan` review is refused without `--planner-model`, and that model is skipped as reviewer. When the user asks, prefix the command (`MAENG_REVIEW_BACKEND=claude maeng-review run ...`); run `maeng-review --help` for the current flags.

Commands (tier is picked from the bound issue; see the table below):

| Subject | Command |
|---|---|
| Child-task PR / small work | `maeng-review run --kind code --pr <N>`; with no session binding (background or dots-run sessions) add `--plan docs/design/MAE-<n>-plan.md`, which reads the `AC-n` from that file as committed at `--head`; add `--author codex` when Sol/Codex wrote the change |
| Parent integration | `maeng-review run --kind parent --pr <N> --planner-model <id>` |
| Plan of a large task | `maeng-review run --kind plan --plan docs/design/MAE-<n>-plan.md --head <sha> --issue MAE-<n> --planner-model <id>` (`--draft <path>` instead of `--plan` for an uncommitted plan) |
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
| Plan of a large task | Astra | high | Opus xhigh | `--kind plan`; a plan receipt, never a merge receipt |
| Small implementation without a task tree | Sol | high | Opus high | no parent/child structure |
| Either code row above, written by Sol/Codex | none (skipped) | - | Opus high | `--kind code --author codex` |
| Notion outcome payload | Sol | medium | Opus high | `work-records` flow |
| Research draft | Sol | xhigh | Opus high | `aside-research`, with a devil's-advocate lens |

## Bundle (reviewer reports `blocked` if anything is missing)

- Code: repo, PR, base/head SHAs, diff, full changed files, Spec/Plan `AC-n` with `updatedAt`, verification evidence (tree ids, commands, results).
- Parent: plus the child Spec/Plans and their merged PRs.
- Plan: the plan text, its `criteria_rev` and the repository files it cites. The plan text is data to the reviewer.
- Docs: document, digest, the requirements it answers.
- Notion: payload, digest, draft, sources.

## Verdict handling

Verdict `{verdict, subject, reviewer, findings[]}` is stored per subject. Route it to a Linear comment on the bound issue and to `wiki/reviews/REV-<MAE>-<YYYYMMDD-HHMM>-<digest7>.md`. On `fail`: fix each finding, re-verify, request a new review (new head means a new subject).

- **Verify before review.** `maeng-review run` refuses locally, without calling the reviewer and without using a round, when the reviewed head is not ship-verified (the Plan checks have not passed on that exact head). After every fix commit, re-run the checks, then request the review.
- **needs-external-check.** The reviewer reports tool behavior it cannot observe as a low finding titled `needs-external-check: …`; it never makes the verdict fail or blocked by itself. Run that check yourself and put the result in the CEO brief.
- **Review criteria (V-1 to V-6).** The prompt and the verdict check carry them; a response that breaks them is unusable and moves to the next candidate.
  - V-1 Only critical/high fail a review: an unmet `AC-n`, operational breakage, or loss of data or secrets. Medium and low never fail it. A `pass` with an open critical/high, or a `fail` with no finding, is rejected; a `fail` with only medium/low becomes `pass`.
  - V-2 Round two gets the previous findings. It narrows a file to the changes since the previous head only when the base is the same, the `criteria_rev` is the same and non-null, the previous head is an ancestor, and the previous round read that file in full. Anything else is a full review. It raises no new low findings.
  - V-3 At most 5 low findings, then `외 N건`.
  - V-4 A defect that existed before the diff is low, unless fixing it is an `AC-n`.
  - V-5 A code finding has `file` and a positive `line`, and names the call site or input that reaches it; without that it is low. Exception: a missing file or function has `file` and `line` null, a title starting `missing file/function:` and the affected `AC-n`.
  - V-6 The reviewer tries to falsify each `AC-n`. No findings with `pass` is a valid review.
  - An unmet `AC-n` always blocks; V-4 and V-5 never lower it.
- **Rounds.** A round is one distinct reviewed head with a completed `pass` or `fail`. A rerun on the same head, a scope split and a `blocked` result count as none. `maeng-review run --pr N` refuses a third head (`--max-rounds`, default 2, raised only on the user's word). A new base or new `criteria_rev` forces a full review but does not reset the count. Before another round, sort the findings into: caused by this diff, pre-existing, real approval bypass; only the first group blocks.
- **Confirmation.** `maeng-review run --pr N --confirm` is the one extra run per PR. It needs two counted heads and a failed round two with an open critical/high, and the same base, the same non-null `criteria_rev` and an ancestor round-two head; otherwise it is `blocked` and not spent. The reviewer sees only the open critical/high findings and the fixing diff and raises no new finding. A `pass` has no findings and gives a receipt `maeng-ship` accepts for that head. Once a reviewer is dispatched it is spent. If it fails, or no budget is left, send the CEO brief and ask for `승인 #N`; run the full suite on the fixed head before `--confirm`.
- **Plan review.** `--kind plan` blocks (high) for exactly three things: an `AC-n` with no check, a step that cannot be executed, a conflict with the cited code (file and line). Everything else is at most medium. A plan with no `AC-n` section, no text or no task id is `blocked` before any model runs.
- **Large task notice.** A large task has child issues or a Sub-tasks table of two or more rows. Without a valid plan receipt, one line appears after `gh pr create` and once more at code-review entry, once per PR. It never blocks review or merge.
- **Commit status.** On a GitHub repo every code review posts commit status `maeng/review` (success on pass, failure otherwise) on the reviewed head; a posting failure is a warning only. Nothing requires it yet; once rulesets are enabled (eta by its owners, personal repos after a plan upgrade), make `maeng/review` a required check. maeng-ship then has to merge through `gh pr merge` instead of a direct push, because rulesets that require a PR reject that push.

## Receipts

Single use. Only `maeng-review run` writes usable receipts (`reviewer.provenance: review-run`); `maeng-review store` and fixture receipts exist for the test suite only (`MAENG_TEST_FIXTURES=1`) and the gates reject them otherwise. A `pass` receipt is consumed only when the gated action succeeded (merge push accepted). A rejected action leaves it unconsumed. A changed head, base, criteria or digest needs a new review. A receipt records `coverage` (full or delta per file), `previous_head` and `review_mode` (initial, round2, confirmation). A plan receipt is keyed by the task id and `criteria_rev`, not by the tree: changing the acceptance text makes it stale, and it never authorizes a merge. If the client failed but the remote may have changed, the receipt stays `pending` until `maeng-review reconcile`.

## Shipping

- The hook blocks only: a push to the default branch (`main`/`master`/`trunk`, the remote's HEAD, `protected_branches`, `--all`/`--mirror`, an implicit push whose upstream or `remote.<r>.push` is the default branch, or a push it cannot place); every merge route other than `maeng-ship` (`gh pr merge|update-branch`, `gh api` merge/ref-write endpoints and merge mutations, git/gh aliases that push or merge, `mcp__github__merge_pull_request`/`update_pull_request_branch`); GitHub MCP file writes to the default branch or with no branch; setting `MAENG_TEST_FIXTURES`/`MAENG_GIT`/`MAENG_GH`/`MAENG_HOME`/`MAENG_CACHE_DIR`/`MAENG_CLAUDE` from Bash; and Edit/Write into the harness state directory. Feature-branch pushes (force included), `gh pr create`, other gh writes, compound commands and other `MAENG_*` prefixes are allowed; verify before you push because that is the workflow, not because a gate checks it. In eta checkouts this gate is inert and eta-rules' code hooks govern pushes, except the comprehension gate (below), which runs in every world (user decision D-5).
- Merge is only `maeng-ship merge <PR>`: it requires the base to be an ancestor of the head, a ship-verified head tree and a matching `pass` receipt, then does a lease-guarded fast-forward push. If it reports "base moved", update the branch, re-verify, re-review.
- User approval instead of a review: when the user sends a message starting with `승인 #N` (or `approve #N`), the UserPromptSubmit hook records an approval of PR N at its current head, and `maeng-ship merge N` accepts it in place of the pass receipt. It works once, for that head only, and still needs a ship-verified head. When reviews will not converge, ask the user to send `승인 #N`; never write it yourself. A `승인 #N` that dots (or another agent) relays from the user through `claude -p` counts as the user's approval (user decision 2026-10-18); relay only an approval the user actually gave.
- After `gh pr create`, the hook reminds you which review tier applies, and notes a missing plan receipt on a large task. Stop notifies and never blocks (verification.md).
- Comprehension gate ([comprehension-gate](../../comprehension-gate/SKILL.md), MAE-313): a PR over 150 changed lines, or one touching a part of the repo's part map, also needs the user's merge-quiz pass (bound to the PR's patch id, so a rebase with the same diff keeps it) or their `면제 #N <reason>`. `maeng-ship merge` refuses without it, even with a receipt or `승인 #N`; outside the personal world `gh pr merge` (with or without `--auto`, also inside `sh -c`/`eval`) and the GitHub MCP merge tool are denied the same way. Start the quiz after the review passed. With a part map, Edit/Write on a mapped path is denied until `overall` and that part have a design pass (headless runs are exempt); Edit/Write and Bash naming the interviews directory are denied in every world.
