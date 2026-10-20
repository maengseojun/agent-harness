# Generated images

Order (user decision, 2026-10-21): GPT image through `codex exec` first, Figma Weave only as the fallback. Real product screens, logos and data always come from the user or the product itself, never from generation.

## 1. GPT image through `codex exec` (default)

Codex CLI generates the image and saves the file itself; no Slack round trip.

```bash
codex exec --skip-git-repo-check -s workspace-write -C <outdir> "<prompt> Save it as <name>.png in the current directory. Reply only with the saved path." -i <ref1.png> -i <ref2.png> < /dev/null
sips -g pixelWidth -g pixelHeight <outdir>/<name>.png
```

- The prompt in English: the subject, the palette from `brand/frame.md`, where to leave empty space for text, `no text, no letters, no logos`, and the aspect (`wide 16:9`, `vertical 9:16`, `square`).
- Put the prompt before `-i`: `-i` takes every following argument as an image. `< /dev/null` stops it waiting on stdin. `--full-auto` is not a flag in codex-cli 0.163.
- One image takes about a minute; run batches in the background.
- Verified 2026-10-21 (codex-cli 0.163): a square prompt gave 1254x1254, a wide prompt with one reference image gave 2048x1152.

Copy the file into the project's `assets/img/`, look at a downscaled preview (`sips -Z 768`) before using it, and reject any image with text, letters, watermarks or a fake UI.

## 2. Figma Weave (fallback)

Use only when the codex route fails or the image needs a model it does not have. `weave_find_model` returns the model and an approximate cost; `weave_run_model` without `acknowledgedCost` only quotes. Show the quote and get the user's approval for every run, reruns included. As of 2026-10-20 the account holds a Starter View seat and a student Collab guest seat, so Weave or editing may be refused; report that and stop rather than guess.

## Use in the film

- Resolution: check the size you got. Use generated images for soft backgrounds, textures and illustration, never for UI or small detail.
- Leave a dark or blurred layer between a busy image and text, then let `check` confirm contrast.
- A slow camera move on the image (scale 1.0 to about 1.08 over the film, `sine.inOut`) keeps a still image alive.
- Record each file in `assets/SOURCES.md`: route (codex GPT image or Weave), prompt, reference files, date.
