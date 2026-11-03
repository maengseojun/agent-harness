# MAE-301 follow-up Spec/Plan-lite: review kind for a merge-bound docs PR

Linear: MAE-301. Date: 2026-11-03. Skill feedback from PR #90.

Goal: a docs-only PR that will be merged gets reviewed with a receipt `maeng-ship merge` accepts.
Deliverable: one PR with two rules-doc lines, a version bump to 0.4.10, and a short note in Korean to the user.
Source: PR #90 was reviewed with `--kind docs --pr 90`, which passed. `maeng-ship merge` then refused it, because `receipts.find_code` accepts only `code` or `parent` receipts. By then the PR had hit the 4-run cap and needed a fresh `승인 #90`.
Decisions: D-1 fix the guidance, not the code. A guard that makes `maeng-review` refuse `--kind docs --pr` is gate code with a full process suite; one clear line is enough after one occurrence. Wrong if: the same mistake happens again.
Assumptions: A-1 a version bump is included so the installed plugin picks the change up (as in MAE-301).
Owns: `plugins/maeng-harness/skills/harness-run/references/review-and-ship.md`, `plugins/maeng-harness/skills/harness-run/SKILL.md`, `plugins/maeng-harness/.claude-plugin/plugin.json`, this file.
Exclusions: no change to `maeng-review` or `maeng-ship` code.

- **AC-1** The review-and-ship command table and tier table, and SKILL.md step 10, say that a PR to be merged takes `--kind code --pr N` even when it is docs-only, and that `--kind docs` reviews a `--draft`.
- **AC-2** maeng-harness is 0.4.10, `claude plugin validate plugins/maeng-harness` passes and the root suite passes.

Routing: write in this session; review Sol high with `--kind code --pr N` (this very rule); limits: none known.
Verification tier: code (plugin.json).
Verification:
- AC-1: `grep -c "accepts only \`code\` or \`parent\` receipts" plugins/maeng-harness/skills/harness-run/references/review-and-ship.md` prints 1, and `grep -c "takes \`--kind code\` even when it is docs only" plugins/maeng-harness/skills/harness-run/SKILL.md` prints 1.
- AC-2: `claude plugin validate plugins/maeng-harness` prints `Validation passed`; `python3 -m pytest -q` passes.
Checked against: the observed case (PR #90, docs-only) and one similar case, a release PR that only bumps a version. Both now point to `--kind code --pr N`.

Revisions:
- none

Close-out:
- size: (filled at close)
- revisions: plan 0 / result 0
- review rounds to pass:
- unmet AC at close:
