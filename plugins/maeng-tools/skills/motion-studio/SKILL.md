---
name: motion-studio
description: "Make short startup videos in code: product intro, launch, feature explainer, demo, investor/IR, onboarding, social clip (제품 소개 영상, 런칭 영상, 설명 영상, 데모 영상, 모션 그래픽, 숏폼, motion graphics, explainer video). HeyGen HyperFrames loop: director brief, style guide, beat shot list, motion weights, contact-sheet critique with top-3 fixes, separate 16:9 and 9:16 projects, company lessons. Concept lessons in 3Blue1Brown style go to tutorial-video; still diagrams to diagram-explainer; web decks to frontend-slides."
---

# Motion studio

A prompt makes a clip; a studio makes the next video better. The model writes a frame function (HTML + a paused GSAP timeline that HyperFrames seeks frame by frame), and the system decides what ships: brief, reference, beats, deterministic render, critique on rendered frames, and lessons kept for the next film.

Fits product UI, data stories, typography, diagrams and launch explainers. It does not fit live action or organic motion; say so and stop.

## Studio layout

One studio folder per company, a git repo outside this harness. Ask for its path once; default `~/Documents/Project/motion-studio/`.

```
<studio>/
  brand/frame.md          palette, type, motion character, logo rules (written once, then reused)
  brand/assets/           logos, real product screenshots and recordings, fonts
  lessons.md              rules promoted from repeated defects (read before every film)
  videos/<slug>/
    BRIEF.md  style-guide.md  shotlist.md  cues.json  score.abc  reviews/
    wide/                 HyperFrames project, 1920x1080
    vertical/             HyperFrames project, 1080x1920
```

`<skill>` below is this skill's folder (where this SKILL.md lives).

## HyperFrames rules (verified 2026-10-20, hyperframes 0.8.181)

- Run every command as `HYPERFRAMES_SKIP_SKILLS=1 npx --yes hyperframes@<pin> <cmd>`. Without the variable, `init` and `render` refresh HyperFrames' skills in the global skill folders, where they would claim every video request in every repo, the eta world included. The first `init` of a film uses `hyperframes@latest`; `init` writes that version into the project's `package.json` scripts, and every later command, the second project's `init` included, uses that recorded version as `<pin>`.
- Read HyperFrames docs from GitHub when you need them, never from memory: `gh api repos/heygen-com/hyperframes/contents/skills/<skill>/SKILL.md --jq .content | base64 -d`. Read `hyperframes-core` before writing composition HTML.
- A project has exactly one root composition (`multiple_root_compositions` is a lint error), and a different aspect is a different project. Build `wide/` and `vertical/` as siblings with their own layout, type sizes and element counts. Never crop one into the other.
- Put each beat in its own sub-composition (`compositions/NN-<beat>.html`, mounted with `data-composition-src`). Lint asks for it, and it lets a fix touch one beat.
- Fonts: choose per video. The license must allow commercial use and web embedding (OFL is fine). Copy the `.woff2` files into `assets/fonts/` and declare them with an in-file `@font-face`; lint rejects a named family without one. For Korean set `word-break: keep-all`.
- `hyperframes check` must end with 0 errors before you trust its layout and contrast numbers, because a lint error switches those audits off.

## Flow

Quality layer: for a non-code result the user will show or submit, follow `maeng-harness:quality-layer` (criteria from real examples, independent check, closing walkthrough).

1. **Read the studio.** `brand/frame.md`, `lessons.md` and the general findings in [references/huashu/experience.md](references/huashu/experience.md). With no brand yet, write `brand/frame.md` from the user's site, Figma or assets before the first film.
2. **Director brief.** Fill [references/brief-ko.md](references/brief-ko.md). Ask only what the request leaves open, one question at a time; record inferred answers apart from stated ones. Write `BRIEF.md`.
3. **Reference.** Inspect the references the user allows (screenshots, sites, past films) and write `style-guide.md`: palette, typography, composition, pacing, motion, texture, and a DO NOT COPY list. Pick the motion language from the director docs ([references/huashu/README.md](references/huashu/README.md) says which file serves which step; read `om` commands there through its mapping table). Missing real assets: stop and ask; never draw a fake product UI. When there is no reference for a look (mood, background, illustration style), draft 2-3 candidate stills per [references/images.md](references/images.md) into `reviews/drafts/` and let them steer the style guide; they are drafts, not film assets.
4. **Shot list.** Write `shotlist.md` per [references/shotlist.md](references/shotlist.md): beats with timestamps, entry and exit states, purpose. Shape the energy with `references/huashu/rhythm.md`: a hook within 3 s, a burst, a stop before the peak. A shot that cannot state its purpose is cut.
5. **Gate A (user).** First create the `wide/` project from `videos/<slug>/` with `HYPERFRAMES_SKIP_SKILLS=1 npx --yes hyperframes@latest init wide --non-interactive --example=blank`, build only its most representative beat (usually REVEAL or PROOF, sourcing its images per step 6 if it needs any), then take one still of it with `snapshot --at`. Send one message: the brief summary, the style guide in five lines, the shot list, and that still. Build the rest only after approval or edits.
6. **Build.** `init vertical` the same way with the pinned version, set its size to 1080x1920 (`data-width`/`data-height` on the root, on every sub-composition and its host, plus the viewport meta and the `html, body` size), write the remaining beats in both, apply [references/motion-weights.md](references/motion-weights.md), source images per [references/images.md](references/images.md). Keep motion, sound cues and transitions on the one timeline.
6b. **Sound.** Follow [references/sound.md](references/sound.md): write `cues.json` from the shot list (beat starts as scene labels, a hit on every landing that matters, the music direction), optionally a `score.abc`, run `node <skill>/scripts/studio.mjs sound cues.json --out wide/assets/sound.wav` from `videos/<slug>/`, and again with `--out vertical/assets/sound.wav` (with that project's own cues file when its beat times differ), then add one `<audio id="soundtrack" src="assets/sound.wav">` to each project's `index.html`. Re-run it after any timing change.
7. **Check and contact sheet.** `check` with 0 errors, then `snapshot --at <every beat midpoint plus fast transitions> --no-end -o ../reviews/<round>-<aspect>`. It writes the stills and `contact-sheet.jpg`.
8. **Critique.** Follow [references/critic.md](references/critic.md): an independent reviewer judges only the rendered frames and names the three worst defects with timestamp, evidence and a local fix. Patch only those beats, snapshot again. At most three rounds; stop early when a round brings no new evidence.
9. **Render.** `render --quality delivery` in each project. Confirm with `ffprobe -v error -show_entries stream=width,height,r_frame_rate:format=duration -of csv=p=0 renders/*.mp4`, and pull one frame per beat from the MP4 to see that fonts and images survived the render. Run `node <skill>/scripts/studio.mjs qa renders/<file>.mp4` on each render: it lists single-frame pops, dead time and a flat motion curve.
10. **Gate B (user).** Deliver per [references/formats.md](references/formats.md): both MP4s, poster frames, the last contact sheets, source, an assets list with sources, and what still needs a human look.
11. **Lessons.** Log every defect fixed this film in `lessons.md`. A defect seen in two films becomes a rule there, read at step 1 next time.

The user sees two gates (A and B). Everything between them runs without asking, except the approvals below.

For ideas at any step, [references/playbook.md](references/playbook.md) collects optional tips (brief, reference, story, motion, sound, review); consult it as needed, it adds no steps.

## Approvals and limits

- Default sound is local music and effects from `scripts/studio.mjs` (no network, no cost); silence only when the user asks or for a transparent overlay. Ask once before the first `studio.mjs samples build` (a ~55 MB download of CC0/CC-BY instrument samples); without it the music uses synthesized instruments. Narration (ElevenLabs or another TTS), licensed music, Figma Weave or any other paid generation runs only after the user approves the provider, the cost or cap, and the data sent, for that run.
- Generated images never stand in for the real product, real UI or real data. Generated images with text in them are rejected; set text in HTML.
- Do not publish, upload or post a film anywhere; delivery is files in the studio folder and a message to the user.
- HyperFrames is young and releases several times a day. When a command or flag here fails, read the current docs and record the change in `lessons.md` rather than guessing.
