# MAE-312 Spec/Plan-lite: OpenAI Images API as the default image route

Linear: MAE-312. Date: 2026-11-04.

Goal: skills that generate images call the OpenAI Images API first and keep `codex exec` as the fallback.
Deliverable: one PR against `feat/harness-v1`, English skill text, with a small shared script and its test.
Source: the user's decision of 2026-11-04, after one `gpt-image-2` `low` `1024x1024` call worked. The credit is API credit, so calls stop when it runs out; that is why `codex exec` stays. Edits request shape from OpenAI's reference (`developers.openai.com/api/reference/resources/images/methods/edit`), read 2026-11-04.
Decisions: D-1 API first, `codex exec` fallback, Weave last (user). Wrong if: none (user decision).
D-2 one script, not a documented curl line. Key handling, JSON escaping, multipart, base64 decoding and failure handling would otherwise be copied into two skills. Wrong if: the script grows options nobody uses.
Assumptions: A-1 the model stays `gpt-image-2`, the model of the working call. OpenAI also lists newer `gpt-image-2.5-*` models; moving is a later choice.
A-2 the script lives in `cinematic-site/scripts/`, since `frontend-guidance` and `taste-skill` already point at `cinematic-site` prompts §1. `motion-studio` reaches it as a sibling folder.
A-3 quality `low` for drafts and `high` for finals, with `2560x1440` `high` for the cinematic-site plate. Neither has run live.
A-4 falling back is the agent's decision from the error message, not automatic, and the script never retries, since each call spends credit.
A-5 a failed rerun leaves the earlier image at the output path, because deleting it would lose a paid image. Both docs chain `&& sips`, so a failed run does not inspect the old file (review round 1).
Owns: `plugins/maeng-tools/skills/cinematic-site/` (SKILL.md, references/prompts.md, scripts/openai-image.sh, scripts/test_openai_image.py), `plugins/maeng-tools/skills/motion-studio/references/{images,formats}.md`, `plugins/maeng-tools/skills/frontend-guidance/SKILL.md`, `plugins/maeng-tools/skills/design-reference/references/taste-skill.md`, `plugins/maeng-tools/.claude-plugin/plugin.json`, this file.
Exclusions: no live image call in this task (each one spends the user's credit), so the edits route is untested live. No price per image. `docs/design/codex-image-route-plan.md` stays as the past plan. `plugins/maeng-tools/skills/decisions/` is another session's. Weave's video step does not change.

- **AC-1** `motion-studio/references/images.md`, `cinematic-site/SKILL.md`, `cinematic-site/references/prompts.md` §1, `frontend-guidance/SKILL.md` and `design-reference/references/taste-skill.md` name the Images API as the default and `codex exec` as the fallback. Each route text with a credit-spending call says to ask first, and both copies of the route say the edits endpoint is not verified live.
- **AC-2** `openai-image.sh` posts JSON to `/images/generations` without references and multipart `image[]` to `/images/edits` with them, in order. It saves the decoded image, never puts the key in argv, output or files, does not retry and ignores `~/.curlrc`. On any failure it exits non-zero and writes nothing to the output path, so an earlier image there stays as it was. Tests reach only a local fake server, and `security` is faked, so they cannot spend credit.
- **AC-3** maeng-tools is 0.3.14 and `claude plugin validate plugins/maeng-tools` passes.
- **AC-4** The root suite passes.

Routing: write in this session; review Sol high with `--kind code --pr N` (small work, no tree); limits: none known.
Verification tier: code.
Verification:
- AC-1: `AC-1 grep: route text names Images API first and codex exec as fallback in all 5 files`
- AC-2: `python3 -m unittest discover -s plugins/maeng-tools/skills/cinematic-site/scripts`
- AC-3: `claude plugin validate plugins/maeng-tools`
- AC-4: `python3 -m pytest -q`

Checked against: 8 mutations of the script (key in argv, edits route removed, references reversed, reference path unquoted, HTTP status ignored, curl retries added, null image accepted, output folder check removed), plus 2 after review round 1 (curl `-q` removed, output deleted on failure). The tests caught all 10. The empty-image test from round 2 failed before its fix and passes after it.

Revisions:
- none

Close-out:
- size: (filled at close)
- revisions: plan 0 / result 0
- review rounds to pass:
- unmet AC at close:
