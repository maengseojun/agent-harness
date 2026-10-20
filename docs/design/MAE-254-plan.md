# MAE-254 Spec/Plan: cinematic-site skill

Linear: MAE-254. Date: 2026-10-20. Single task, one PR. Branch `feat/cinematic-site`.

## Goal

A personal skill that turns a brief and references into a cinematic landing page the way the Viktor Oddy tutorial does (YouTube `YhF8Qg2GL80`, reposted on X by @robiartec), adapted to this setup: images from GPT Image through the Slack bot maestro, video from Figma Weave (Seedance), code by Claude Code.

## Decisions

- **D-1** Images come first from GPT Image via maestro in `#maestro-claude`; maestro attaches them, saves them under `~/Documents/maeng-harness/cinematic/<slug>/`, and announces completion through the claude CLI with a `task_id:` line, so the session waits on `~/Documents/maeng-harness/status/<task_id>.json`. User, 2026-10-20: "gpt image를 먼저 쓰고 그다음에 weave로 해", "첨부하고 나면 claude cli로 첨부했다고 알려달라고 까지".
- **D-2** Video only on Weave (`weave_run_model`, Seedance 2.0 image-to-video or reference-to-video); each run spends credits, so the session shows the estimate and asks first. Audio off.
- **D-3** Seamless loop by pre-rendering forward+reverse with ffmpeg (`scripts/pingpong.sh`), not the tutorial's canvas frame cache (~620 MB for 10 s at 960 px). The canvas recipe stays documented as a fallback only.
- **D-4** Reuse, do not copy: `design-reference` (reference choice), `frontend-guidance` (render checks), `hangul-wrap` (Korean), `vercel-deploy`.

Owns: `plugins/maeng-tools/skills/cinematic-site/**`, one routing line in `plugins/maeng-tools/skills/frontend-guidance/SKILL.md`, rows in `plugins/maeng-tools/skills/design-reference/references/sites.md`, this file.
Exclusions: no product-UI flow prototyping (that is `html-prototype-interview`), no slides, no automatic reference crawling, no Weave image generation by default.

## must_haves

- T1: The skill names the stage order reference → mock (maestro) → plate (maestro) → video (Weave, approval) → hero only → rest, with the two user gates (pick the mock, accept the hero).
- T2: Every image/video prompt the tutorial proved useful exists as a fill-in template.
- T3: `pingpong.sh` doubles a clip's length with a reversed copy, writes mp4 + webm + poster, and fails when ffmpeg is missing.
- A1: `cinematic-site/SKILL.md`, `references/prompts.md`, `references/video-bg.md`, `scripts/pingpong.sh`.
- K1: `frontend-guidance` routes cinematic/video-hero requests to `cinematic-site`.

## Criteria

- **AC-1** SKILL.md frontmatter `name: cinematic-site` with a description; every `references/...` link resolves. covers A1
- **AC-2** prompts.md holds the maestro request (with the CLI notice), mock, plate, Weave video (plain and with motion reference), hero-only build, video placement, rest-of-page and one-page-only templates. covers T1, T2
- **AC-3** `bash scripts/pingpong.sh --self-test` exits 0; with ffmpeg off PATH it exits non-zero. covers T3
- **AC-4** frontend-guidance has the routing line; sites.md lists seesaw.website and land-book.com with their real access result. covers K1
- **AC-5** The demo ran end to end or every unreached stage is named with its blocker in the PR body.

## Sub-tasks

| Do | Writes | Done | Fails-if | After |
|---|---|---|---|---|
| Demo run | `~/Documents/maeng-harness/cinematic/mae-254/` (outside repo) | hero page renders with the generated video at 375 and 1440 | screenshot taken before the video has `currentTime > 0` | |
| Skill text | SKILL.md, references/* | review item AC-1, AC-2 | a template the demo did not use or contradicted is kept unmarked | Demo run |
| Ping-pong script | scripts/pingpong.sh | `bash plugins/maeng-tools/skills/cinematic-site/scripts/pingpong.sh --self-test` prints `self-test ok` | passes with ffmpeg missing, or output not ~2x input | |
| Routing + catalog | frontend-guidance, sites.md | grep finds `cinematic-site` and both URLs | site marked checked without a real visit | |

## Verification

Verification tier: code (one shell script). Ship checks, once at the final tree:
- AC-1: cinematic-site frontmatter names cinematic-site and every references link resolves
- AC-1: claude plugin validate plugins/maeng-tools
- AC-2: review item: prompts.md covers every stage template listed in AC-2
- AC-3: pingpong.sh --self-test prints self-test ok and exits 1 without ffmpeg on PATH
- AC-4: frontend-guidance routes to cinematic-site and sites.md lists seesaw.website and land-book.com
- AC-5: review item: PR body names every demo stage not reached and why
- Suite: python3 -m pytest -q

Plan change log: 2026-10-20, Verification lines rewritten as one literal check each (the first form mixed backticks and two commands per line, which the gate could not match). Criteria unchanged. User decision 2026-10-20: "weave 빼고 그렇게 진행해" — the demo stops at the hero with a free ffmpeg stand-in instead of a Weave clip, and stage 6 is not demoed ("히어로까지만, skill 마무리").

Review focus: does the skill text match what the demo actually did; is any step here that nobody ran presented as proven.
