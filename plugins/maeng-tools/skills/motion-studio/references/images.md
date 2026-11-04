# Generated images

Order (user decision, 2026-11-04): the OpenAI Images API first, `codex exec` when the API fails or its credit runs out, Figma Weave last. Real product screens, logos and data always come from the user or the product itself, never from generation.

## 1. OpenAI Images API (default)

`openai-image.sh` lives in the sibling `cinematic-site` skill; `<cinematic-site>` below is `../cinematic-site` from this skill's folder. It reads the key from the Keychain and saves the file. Each call spends API credit, so ask the user before each run or batch.

```bash
cat > <outdir>/<name>.prompt.txt <<'EOF'
<prompt>
EOF
<cinematic-site>/scripts/openai-image.sh <outdir>/<name>.prompt.txt <outdir>/<name>.png 1536x864 low <ref1.png> <ref2.png>
sips -g pixelWidth -g pixelHeight <outdir>/<name>.png
```

- The prompt in English: the subject, the palette from `brand/frame.md`, where to leave empty space for text, `no text, no letters, no logos`.
- Arguments: prompt file, output, size, quality (`low`, `medium`, `high`), then any reference images (PNG or JPEG). `low` for drafts, `high` for the final image.
- Size sets the aspect: `1536x864` wide, `864x1536` vertical, `1024x1024` square. Both sides must divide by 16 and the ratio stays within 3:1; sizes above `2560x1440` are experimental.
- The script does not retry. On a non-zero exit, read the API's message. When the credit is out or the call keeps failing, use route 2 instead of repeating it.
- Verified 2026-11-04: one `1024x1024` `low` call without references. The edits endpoint that takes references follows OpenAI's reference but has not been called live; report it if the first such run fails.

## 2. GPT image through `codex exec` (fallback)

Codex CLI generates the image and saves the file itself; no Slack round trip.

```bash
cat > <outdir>/<name>.prompt.txt <<'EOF'
<prompt>
Save it as <name>.png in the current directory. Reply only with the saved path.
EOF
codex exec --skip-git-repo-check -s workspace-write -C <outdir> "$(cat <outdir>/<name>.prompt.txt)" -i <ref1.png> -i <ref2.png> < /dev/null
sips -g pixelWidth -g pixelHeight <outdir>/<name>.png
```

- The prompt is the same with the save line added, and it names the aspect (`wide 16:9`, `vertical 9:16`, `square`) because there is no size argument.
- Put the prompt before `-i`: `-i` takes every following argument as an image. `< /dev/null` stops it waiting on stdin. The quoted heredoc keeps quotes in the prompt intact. `--full-auto` is not a flag in codex-cli 0.163.
- One image takes about a minute; run batches in the background.
- Verified 2026-10-21 (codex-cli 0.163): a square prompt gave 1254x1254, a wide prompt with one reference image gave 2048x1152.

From either route, copy the file into the project's `assets/img/`, look at a downscaled preview (`sips -Z 768`) before using it, and reject any image with text, letters, watermarks or a fake UI.

## 3. Figma Weave (last fallback)

Use only when both routes above fail or the image needs a model it does not have. `weave_find_model` returns the model and an approximate cost; `weave_run_model` without `acknowledgedCost` only quotes. Show the quote and get the user's approval for every run, reruns included. As of 2026-10-20 the account holds a Starter View seat and a student Collab guest seat, so Weave or editing may be refused; report that and stop rather than guess.

## Use in the film

- Resolution: check the size you got. Use generated images for soft backgrounds, textures and illustration, never for UI or small detail.
- Leave a dark or blurred layer between a busy image and text, then let `check` confirm contrast.
- A slow camera move on the image (scale 1.0 to about 1.08 over the film, `sine.inOut`) keeps a still image alive.
- Record each file in `assets/SOURCES.md`: route (Images API, codex GPT image or Weave), prompt, reference files, date.
