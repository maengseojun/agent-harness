---
name: motion-studio
description: Use when the user wants a short startup video made in code - product intro, launch, feature explainer, demo, investor/IR, onboarding or social clip (제품 소개 영상, 런칭 영상, 설명 영상, 데모 영상, 모션 그래픽, 숏폼, motion graphics, explainer video). Runs a studio loop on HeyGen HyperFrames - director brief, style guide, beat shot list, motion weights, contact-sheet critique with top-3 local fixes, separate 16:9 and 9:16 projects, and a company lessons file so each video improves the next. 3Blue1Brown-style concept lessons go to tutorial-video, still diagrams to diagram-explainer, web decks to frontend-slides.
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
    BRIEF.md  style-guide.md  shotlist.md  reviews/
    wide/                 HyperFrames project, 1920x1080
    vertical/             HyperFrames project, 1080x1920
```

## HyperFrames rules (verified 2026-10-20, hyperframes 0.8.181)

- Run every command as `HYPERFRAMES_SKIP_SKILLS=1 npx --yes hyperframes@<pin> <cmd>`. Without the variable, `init` and `render` refresh HyperFrames' skills in the global skill folders, where they would claim every video request in every repo, the eta world included. Take `<pin>` from the project's `package.json` after `init`.
- Read HyperFrames docs from GitHub when you need them, never from memory: `gh api repos/heygen-com/hyperframes/contents/skills/<skill>/SKILL.md --jq .content | base64 -d`. Read `hyperframes-core` before writing composition HTML.
- A project has exactly one root composition (`multiple_root_compositions` is a lint error), and a different aspect is a different project. Build `wide/` and `vertical/` as siblings with their own layout, type sizes and element counts. Never crop one into the other.
- Put each beat in its own sub-composition (`compositions/NN-<beat>.html`, mounted with `data-composition-src`). Lint asks for it, and it lets a fix touch one beat.
- Fonts: choose per video. The license must allow commercial use and web embedding (OFL is fine). Copy the `.woff2` files into `assets/fonts/` and declare them with an in-file `@font-face`; lint rejects a named family without one. For Korean set `word-break: keep-all`.
- `hyperframes check` must end with 0 errors before you trust its layout and contrast numbers, because a lint error switches those audits off.

## Flow

1. **Read the studio.** `brand/frame.md` and `lessons.md`. With no brand yet, write `brand/frame.md` from the user's site, Figma or assets before the first film.
2. **Director brief.** Fill [references/brief-ko.md](references/brief-ko.md). Ask only what the request leaves open, one question at a time; record inferred answers apart from stated ones. Write `BRIEF.md`.
3. **Reference.** Inspect the references the user allows (screenshots, sites, past films) and write `style-guide.md`: palette, typography, composition, pacing, motion, texture, and a DO NOT COPY list. Missing real assets: stop and ask; never draw a fake product UI.
4. **Shot list.** Write `shotlist.md` per [references/shotlist.md](references/shotlist.md): beats with timestamps, entry and exit states, purpose. A shot that cannot state its purpose is cut.
5. **Gate A (user).** One message: the brief summary, the style guide in five lines, the shot list, and one representative still (`snapshot --at`). Build only after approval or edits.
6. **Build.** `init` both projects, write the beats, apply [references/motion-weights.md](references/motion-weights.md), source images per [references/images.md](references/images.md). Keep motion, sound cues and transitions on the one timeline.
7. **Check and contact sheet.** `check` with 0 errors, then `snapshot --at <every beat midpoint plus fast transitions> --no-end -o ../reviews/<round>-<aspect>`. It writes the stills and `contact-sheet.jpg`.
8. **Critique.** Follow [references/critic.md](references/critic.md): an independent reviewer judges only the rendered frames and names the three worst defects with timestamp, evidence and a local fix. Patch only those beats, snapshot again. At most three rounds; stop early when a round brings no new evidence.
9. **Render.** `render --quality delivery` in each project. Confirm with `ffprobe -v error -show_entries stream=width,height,r_frame_rate:format=duration -of csv=p=0 renders/*.mp4`, and pull one frame per beat from the MP4 to see that fonts and images survived the render.
10. **Gate B (user).** Deliver per [references/formats.md](references/formats.md): both MP4s, poster frames, the last contact sheets, source, an assets list with sources, and what still needs a human look.
11. **Lessons.** Log every defect fixed this film in `lessons.md`. A defect seen in two films becomes a rule there, read at step 1 next time.

The user sees two gates (A and B). Everything between them runs without asking, except the approvals below.

## Approvals and limits

- Default sound is none, with on-screen text carrying the message. Narration (ElevenLabs or another TTS), licensed music, Figma Weave or any other paid generation runs only after the user approves the provider, the cost or cap, and the data sent, for that run.
- Generated images never stand in for the real product, real UI or real data. Generated images with text in them are rejected; set text in HTML.
- Do not publish, upload or post a film anywhere; delivery is files in the studio folder and a message to the user.
- HyperFrames is young and releases several times a day. When a command or flag here fails, read the current docs and record the change in `lessons.md` rather than guessing.
