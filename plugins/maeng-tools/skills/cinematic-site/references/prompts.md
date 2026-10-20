# Prompt templates

Fill the `{braces}`. Write image and video prompts in English (the models follow it best); talk to the user in their language. Source: Viktor Oddy's tutorial (YouTube `YhF8Qg2GL80`); the wording below is what worked there, adapted.

## 1. Image request (`codex exec`)

Run from the work folder; codex generates with GPT Image and saves the file itself. The prompt goes before `-i` (`-i` takes every following argument as an image).

```bash
cd ~/Documents/maeng-harness/cinematic/{slug}
codex exec --skip-git-repo-check -s workspace-write "{prompt} Save it as {stage}/{A}.png. Reply only with the saved path." -i refs/1-{role}.png -i refs/2-{role}.png < /dev/null
sips -g pixelWidth -g pixelHeight {stage}/{A}.png
```

Images are numbered in `-i` order, so "image 1" in the prompt is the first `-i`.

## 2. Mock (stage 2)

One reference per role. A motif may be words instead of an image when no clean image exists.

```
Take image 1 as the layout reference and redesign it as the hero section of a landing page for "{brand}", {one-line what it is}. Instead of {object in the reference}, place {motif}, {where}. Use the colors of image {n}: {palette in words}, with one accent ({hex}). Do not use purple or pink. Keep everything else similar: centered headline "{headline}", subline "{subline}", small wordmark "{wordmark}" top-left, pill button "{cta}" top-right. 16:9, cinematic, soft volumetric light, high detail.
```

Ask for 2-3 variants that differ in one thing (motif shape, or palette kept from the reference). AI defaults to purple in tech; say so explicitly.

## 3. Plate: background without UI (stage 3)

Attach the chosen mock.

```
Create an image exactly like this one in the highest resolution you can, 16:9. Remove the text, buttons, logos and navigation. I want the exact same background and the same positions. No zoom in or zoom out.
```

## 4. Video on Weave (stage 4) (not yet demo-verified)

Image-to-video, first frame = the plate:

```
Animate this image. Slow, calm, continuous motion of {what should move}; the camera stays still. Do not zoom in or out. No text, no new objects.
```

With a motion reference (the tutorial's better result; a rough screen recording is enough, it only conveys smoothness):

```
Animate the first image the same way as the video attached. The motion should feel the same. Do not zoom in or out.
```

Params: 16:9, 10 s, 1080p, `generate_audio: false`.

## 5. Build: hero only (stage 5)

Sections 5-9 are build briefs: hold yourself to them, or hand them as-is to an implementer agent.

Attach the mock with decorative extras hidden if they would distract (the tutorial hid the circles in Figma before sending).

```
Build out this hero section. Just the hero section; do not build the rest of the website, we will do that later.
Keep the background {pure black | #hex}. Use {hex} as the accent color. Use the font "{font}" from Google Fonts:
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family={Font}:wght@300;400;500;600;700&display=swap" rel="stylesheet" />
```

Name the font; models fall back to the same few fonts and that is what reads as "AI made".

## 6. Video into the hero

```
Place {assets/hero.mp4} (with hero.webm and poster hero.jpg) as the background of the hero section. Do not add any overlay or dimming; the video is already dark enough for the text. It is a pre-rendered ping-pong loop, so use a plain muted, playsinline, autoplay, loop video. Under prefers-reduced-motion show the poster instead.
```

## 7. Rest of the landing page (tutorial wording; not yet demo-verified)

```
Build the rest of the landing page with {4-5} sections: {sections, e.g. features, how it works, testimonials, portfolio cards}, plus any section you think fits. Keep the hero untouched.
```

## 8. One more page (tutorial wording; not yet demo-verified)

```
In the navbar there is a "{page}" link. Build that complete page with {5-6} sections. Do not build any other pages.
```

## 9. Second video on a card (tutorial wording; not yet demo-verified)

```
In the {section} card "{card title}", replace the current graphic with {assets/x.mp4} as the card background. Scale it to about {150}% so it is not cropped, and blend it with mix-blend-mode: {mode} so its background disappears into the card.
```

Pick `{mode}` by comparing screenshots, see [video-bg.md](video-bg.md).
