# MAE-293 Spec/Plan: orca-race and orca-big-task

Linear: MAE-293. Date: 2026-10-31. Single task (two new skill folders and a version bump, docs only).

## Source and decisions

- The user installed Orca 1.4.243 and wants it for two cases only: racing an ambiguous bug across Claude and Codex, and spreading a large task tree across models (user, 2026-10-31).
- D-1: both skills are pre-flight interviews. They fix the boundaries with the user and end in one question, "이렇게 Orca 실행할까요?". Nothing launches before a yes. Signal it was wrong: the user skips the interview on most runs or says it asks too much.
- D-2: Claude:Codex is about 2:1 by worker rows. Opus is the main model and the coordinator. Astra raises architecture-level issues and never authors. Grok takes only the smallest leaf rows (user, 2026-10-31). Signal: the counted ratio drifts far from 2:1 on real runs, or Grok rows fail their Done check more often than other rows.
- D-3: model strengths are re-checked on every run against a dated baseline (`references/models.md`). The baseline is refreshed when it is older than 30 days or the installed model lists change. Signal: a proposal cites a model that the local CLIs no longer list.
- D-4: Orca handles the loop up to an open PR. Verification, `maeng-review`, the CEO brief and `maeng-ship merge` after `승인 #N` stay as harness-run defines them. Signal: an Orca gate or worker pushes or merges outside maeng-ship.
- D-5: both skills live in maeng-harness, the plugin that is on in personal and eta checkouts and already holds harness-run and the org chart that orca-big-task builds on.

## Local facts (checked 2026-10-31)

- `orca orchestration worker-start` takes `--agent <claude|codex|...>`, `--model <id>`, `--effort <level>`, `--worktree new-child`, or `--terminal <handle>` instead of `--agent`. Grok is not an Orca agent id.
- Codex models list `gpt-6-astra`, `gpt-6.1-sol`, `gpt-6.1-terra`, `gpt-6-luna`, `gpt-reserve` (`~/.codex/models_cache.json`). `grok models` lists `grok-4.7` (default), `grok-4.7-build-fast`, `grok-4.6` and `grok-4.5`, and `grok -p` runs one headless prompt.

## Criteria

- **AC-1** `plugins/maeng-harness/skills/orca-race/SKILL.md` and `plugins/maeng-harness/skills/orca-big-task/SKILL.md` exist. Each frontmatter has its `name` and a "Use when" description that names the trigger ("Orca - race" or "Orca - big task") and where other requests go.
- **AC-2** orca-race interviews before launch. It covers evidence, purpose, guardrails, scope, done and stop criteria, the report format and how the user judges. Its defaults come from the research on how people brief AI agents on bugs, cited in the reference file. It ends with one launch question.
- **AC-3** orca-big-task reads the task tree and refreshes model strengths (D-3). It asks only what it cannot read, proposes a placement table that shows the Claude:Codex count against 2:1, keeps Astra and Grok in their D-2 roles, and ends with one launch question. It hands verification, review and merge back to harness-run (D-4).
- **AC-4** Each SKILL.md is at most 150 lines and every `references/` file is linked from its SKILL.md. maeng-harness is bumped to 0.4.6.

## Steps

1. Research how people brief AI agents on bugs, and what current models are good at (AC-2, AC-3).
2. Write orca-race SKILL.md and `references/brief-template.md` (AC-1, AC-2, AC-4).
3. Write orca-big-task SKILL.md and `references/models.md` (AC-1, AC-3, AC-4).
4. Bump maeng-harness to 0.4.6 (AC-4).

## Verification

- AC-1, AC-4: `claude plugin validate plugins/maeng-harness` prints `Validation passed`, and the check below prints `ok` for both skills.

```bash
python3 -I -c "
import re,pathlib,json
for n,t in [('orca-race','Orca - race'),('orca-big-task','Orca - big task')]:
    d=pathlib.Path('plugins/maeng-harness/skills')/n; b=(d/'SKILL.md').read_text(); fm=b.split('---')[1]
    refs=set(re.findall(r'\]\((references/[^)#]+)',b)); files={p.relative_to(d).as_posix() for p in (d/'references').glob('*.md')}
    print(n,'ok' if f'name: {n}' in fm and t in fm and len(b.splitlines())<=150 and refs==files else 'FAIL',len(b.splitlines()))
print(json.load(open('plugins/maeng-harness/.claude-plugin/plugin.json'))['version'])"
```
- AC-2, AC-3: review items, checked in the Astra docs review against this Plan.
- The full root `pytest -q` once at the end (docs-only change, no code touched).
