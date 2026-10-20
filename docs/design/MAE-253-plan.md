# MAE-253 Spec/Plan: motion-studio skill

Linear: MAE-253. Date: 2026-10-20. Single task (one new skill folder, docs only).

## Source and decisions

- Source: the X article "Motion Engineering: Build a Video Studio Around Opus 5.5" by @0xwhrrari (read through Aside, 2026-10-20). Its claim: a prompt makes a clip, a studio (brief, reference, timeline, deterministic renderer, critic) makes the next video better.
- D-1: build a thin layer over HeyGen HyperFrames (Apache-2.0), not a renderer of our own. HyperFrames already owns the brief interview, storyboard, review loop, render and snapshots.
- D-2: images come from GPT image through dots in Slack `#maestro-claude` first; Figma Weave is the fallback with a cost approval per run (user, 2026-10-20).
- D-3: the Korean font is chosen per video and embedded; no house font (user, 2026-10-20).
- D-4: HyperFrames skills are never installed globally from this skill: every `npx hyperframes` call runs with `HYPERFRAMES_SKIP_SKILLS=1`, and HyperFrames workflow docs are read from GitHub on demand.

## S0 spike results (2026-10-20, hyperframes 0.8.181)

- `HYPERFRAMES_SKIP_SKILLS=1 npx hyperframes@latest init clip --non-interactive --example=blank` scaffolded a project whose `package.json` scripts pin the resolved version (`npx --yes hyperframes@0.8.181 ...`), and left `~/.claude/skills` and `~/.agents` unchanged (directory listing diff empty).
- A 15 s, 5-beat Korean composition with local Pretendard `@font-face` passed `hyperframes check` (0 errors; warnings only ask for per-scene sub-compositions).
- One root composition per project (`multiple_root_compositions` error); `hyperframes-studio` says a different aspect starts a new project. So 16:9 and 9:16 are sibling projects.
- `hyperframes snapshot --at <beats>` writes the stills and a `contact-sheet.jpg`, so no contact-sheet script is needed.
- `render` produced 1920x1080 and 1080x1920, 15.000 s, 30 fps, h264 in about 20-24 s each on this Mac. A frame pulled from the MP4 shows the Korean text rendered.
- dots made a 1536x1024 GPT image and attached the original PNG in the thread. It first asked the user to confirm a request posted by Claude; the user approved Claude requests in that channel. The Slack MCP returns images as base64, which is unusable for a 1.9 MB file, so dots also saves the original to `~/Documents/maeng-harness/inbox/<task>/` and notifies with `claude -p "task_id: ..."`.
- The wide film rebuilt as one sub-composition per beat, with the GPT image as a background on a slow camera push, passed `check` (0 errors, 18/18 contrast) and rendered at 1920x1080, 15.000 s, 30 fps with `--quality delivery`; a frame pulled at 11.8 s shows the font and the image.
- Figma MCP is connected, but the account has only a Starter View seat and a student Collab guest seat; Weave and `export_video` were not tried.

## Criteria

- **AC-1** `plugins/maeng-tools/skills/motion-studio/SKILL.md` exists with `name: motion-studio` and a "Use when" description that names its redirects (`tutorial-video`, `diagram-explainer`, `frontend-slides`).
- **AC-2** The skill encodes the article's studio loop on top of HyperFrames: director brief, reference/style guide, beats and states, motion weights, contact-sheet critic with top-3 defects and local re-render, separate aspect projects, gates, company `lessons.md`.
- **AC-3** The skill states D-2, D-3 and D-4 and the spike facts it depends on (one root per project, `snapshot` contact sheet, `HYPERFRAMES_SKIP_SKILLS=1`).
- **AC-4** Paid generation (TTS, music, Weave) needs an approval naming provider, cost cap and data sent; the default is silent with captions.
- **AC-5** SKILL.md stays at or under 150 lines; detail lives in `references/`, each linked from SKILL.md.

## Steps

1. Write SKILL.md (AC-1, AC-2, AC-3, AC-4, AC-5).
2. Write references: `brief-ko.md`, `shotlist.md`, `motion-weights.md`, `critic.md`, `formats.md`, `images.md` (AC-2, AC-3).

## Verification

- AC-1, AC-5: `claude plugin validate plugins/maeng-tools` prints `Validation passed`; `wc -l < plugins/maeng-tools/skills/motion-studio/SKILL.md` prints at most 150; the link check below prints `missing [] unlinked []` and `name ok True redirects True`.

```bash
python3 -I -c "import re,pathlib; d=pathlib.Path('plugins/maeng-tools/skills/motion-studio'); b=(d/'SKILL.md').read_text(); refs=re.findall(r'\]\((references/[^)#]+)', b); print('missing',[r for r in refs if not (d/r).is_file()],'unlinked',sorted({p.relative_to(d).as_posix() for p in (d/'references').glob('*.md')}-set(refs))); fm=b.split('---')[1]; print('name ok','name: motion-studio' in fm,'redirects',all(x in fm for x in ['tutorial-video','diagram-explainer','frontend-slides']))"
```
- AC-2, AC-3, AC-4: review items, checked in the Codex review against this Plan.
- The full root `pytest -q` once at the end (docs-only change, no code touched).
