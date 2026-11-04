---
name: cinematic-site
description: Use when building a landing page or startup website that should look designed rather than AI-made, with a generated hero image or video background (시네마틱 랜딩, 히어로 영상 배경, 레퍼런스로 사이트 만들기, 스타트업 소개 사이트, "AI 티 안 나게"). Runs references → GPT Image mock via the OpenAI Images API → optional Weave video → staged build. Not for slides (frontend-slides), product-flow prototypes (html-prototype-interview) or small UI fixes (frontend-guidance).
---

# Cinematic site

A page that does not look AI-made comes from references and fixed inputs, not from a clever build prompt. This skill runs the pipeline from Viktor Oddy's tutorial (YouTube `YhF8Qg2GL80`) with this setup: images from GPT Image through the OpenAI Images API (`codex exec` as the fallback), video from Figma Weave, code by you. Prompts are in [prompts.md](references/prompts.md); loops and blend modes in [video-bg.md](references/video-bg.md).

Work folder for everything generated: `~/Documents/maeng-harness/cinematic/{slug}/` with `refs/ mock/ plate/ video/ site/`.

## Stages

**0. Brief.** Brand, what it is in one line, who the page is for, the one action (CTA), scope (hero only / landing / more pages), language. Ask only for what is missing. Korean copy means `hangul-wrap` at the end.

**1. References, one per role.** Layout (the hero you want to resemble), motif (the object that replaces theirs), palette. Use `design-reference` for the catalog and choice. Capture with headless Chrome:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --hide-scrollbars --window-size=1440,1100 --virtual-time-budget=10000 --screenshot=refs/x.png URL
```

seesaw.website detail pages capture well; land-book.com shows a Cloudflare bot check (open it in a browser instead, never bypass). Crop to the hero. A motif may be words when no clean still exists (animated logos capture mid-frame). Steer away from purple: it is the model default for tech.

**2. Mock.** Run prompts.md §1 with the §2 prompt and the refs, one call per variant (2-3 variants, in the background), saving to `mock/A.png`, `mock/B.png`, ... at `1536x864`. Ask the user before the batch, since each call spends API credit. Check each size with `sips`. **Gate A: the user picks one mock.**

**3. Plate.** prompts.md §1 with the §3 prompt and the chosen mock as the reference, at `2560x1440` `high`, saved to `plate/`: the mock without text, buttons and logos, same framing. Ask before this run too.

**4. Video on Weave (optional; not yet run end to end).** Skip it when a still hero is enough; the plate then serves as the background image. `weave_find_model` "seedance", pick Seedance 2.0 image-to-video (or Reference when you have a motion clip). The plate must reach Weave as an asset or a public https URL; local files are neither, so call `weave_upload_asset` (a file picker the user clicks once, pointing at `plate/`). Input: the plate as first frame, 16:9, 10 s, 1080p, `generate_audio: false`, prompt from §4. `weave_run_model` without `acknowledgedCost` only quotes; show that quote with AskUserQuestion (Approve/Cancel) and run only on Approve, every run. Generate two, keep the spare for a section card. Then `scripts/pingpong.sh` it into `site/assets/` (loop, webm, poster). Without Weave, a free stand-in clip made from the plate (video-bg.md) still gives the hero gentle motion.

**5. Hero only.** Build just the hero from the mock: named Google font, exact accent hex, exact background, then the video as background with no overlay (prompts.md §5-6, video-bg.md). Check it at 375 and 1440 px. **Gate B: the user accepts the hero** before anything else is built.

**6. The rest, one step at a time (from the tutorial; not yet run in a demo here).** Remaining sections (§7), then each extra page alone (§8), spare clips on cards with a blend mode chosen by screenshots (§9).

**7. Verify** per `frontend-guidance`: screenshots at 375 / 768 / 1440 with the video actually playing (`currentTime > 0`), reduced motion shows the poster, file sizes, `hangul-wrap` for Korean. Report what you checked and what you did not.

## Rules

- Hand the model fewer things to interpret: hide decorative extras in the mock before building from it.
- Fonts and colors are given, never left to the model.
- Headline and subline get `text-wrap: balance` so a phone width does not leave one word on its own line.
- One stage per request; do not let a build step run ahead into the next.
- Deploy only when asked (`vercel-deploy`).
