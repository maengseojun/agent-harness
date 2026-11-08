# Aside default model in the collect skills: Spec/Plan

Date: 2026-11-08. PR: maengseojun/agent-harness#105. Decided by the user on 2026-11-08: research through the skills uses Aside's own default model, not a pinned `--model openai/...`.

Goal: `aside exec` run by `aside-collect` and `aside-research` takes Aside's default model (the ChatGPT subscription route `openai-codex`, `gpt-6.1-sol` high), so research stops billing the OpenAI API.

Owns: `plugins/maeng-tools/skills/aside-collect/SKILL.md`, `plugins/maeng-tools/skills/aside-research/SKILL.md`, `plugins/maeng-harness/policy/roles.json` (`resources.aside` and the two `research_collect_*` routes), `plugins/maeng-harness/tests/test_roles.py` (route check only).

Exclusions: the `decisions` skill and its OpenAI Decisions API route, its eval `.jsonl` data, `aside-browser`.

Requirements -> acceptance:
- **AC-1** The `aside exec` command in `aside-collect` step 3 passes no `--model`, and one line says the default is the subscription route and that `--model` is passed only when the user names a model. No skill text under `plugins/maeng-tools/skills/aside-*` contains `--model openai/`.
- **AC-2** `roles.json` routes `research_collect_light` and `research_collect_deep` carry `model: null` and `effort: null`, and `resources.aside.note` names the default and when `--model` is passed.
- **AC-3** `test_roles.py` fails when a null-model route meets a `--model openai/` pin in `aside-collect`, and still fails when a route names a model the skill text does not carry.
- **AC-4** `python3 -m pytest -q -n 8` passes and `claude plugin validate` passes for both plugins.
- **AC-5** One real `aside exec` through the collect template with no `--model` runs, and its Aside session record shows provider `openai-codex` and model `gpt-6.1-sol`.

Verification:
- `python3 -m pytest -q -n 8`
- `claude plugin validate plugins/maeng-tools`
- `claude plugin validate plugins/maeng-harness`
- `grep -rn -e "--model openai/" plugins/maeng-tools/skills/aside-collect plugins/maeng-tools/skills/aside-research plugins/maeng-tools/skills/aside-browser` (no output)
