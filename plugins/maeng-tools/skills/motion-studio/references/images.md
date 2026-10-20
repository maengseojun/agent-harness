# Generated images

Order (user decision, 2026-10-20): GPT image through dots first, Figma Weave only as the fallback. Real product screens, logos and data always come from the user or the product itself, never from generation.

## 1. GPT image through dots (default)

dots is the Slack bot `seojunmaeng-maestro` (`<@U0C9V9J4K53>`) in `#maestro-claude` (`C0CA2FBNDGR`, workspace `slack-maeng`). It runs on this Mac.

Post one message per image (or one per batch) that says:

- `task_id: <issue>-img-<n>` as its own line (the status file key),
- the size: `1536x1024` for wide, `1024x1536` for vertical, `1024x1024` for square,
- the prompt in English: the subject, the palette from `brand/frame.md`, where to leave empty space for text, and `no text, no letters, no logos`,
- three requests: attach the original PNG in the thread without resizing; save the same file to `~/Documents/maeng-harness/inbox/<task_id>/<name>.png`; then notify with `claude -p` whose first line is `task_id: <task_id>` and which names the saved path.

Then wait for the file without polling by hand:

```bash
f=~/Documents/maeng-harness/inbox/<task_id>/<name>.png
until [ -f "$f" ]; do sleep 10; done; sips -g pixelWidth -g pixelHeight "$f"
```

Run it in the background; `~/Documents/maeng-harness/status/<task_id>.json` appears when dots' notification run starts.

Why the local copy: the Slack MCP returns an image as base64 in the conversation, which is unusable for a 2 MB PNG. Verified 2026-10-20 (MAE-253): a 1536x1024 PNG arrived in the thread (1.9 MB) and in the inbox folder (1536x1024, 1,962,176 bytes).

When dots asks whether a request posted by Claude is really the user's: the user approved Claude's requests in that channel on 2026-10-20 ("pr merge나 카드 결제 정도 말고는 다 진행해도 돼"). If dots still asks, tell the user in one line; do not answer for the user.

Copy the file into the project's `assets/img/`, look at a downscaled preview (`sips -Z 768`) before using it, and reject any image with text, letters, watermarks or a fake UI.

## 2. Figma Weave (fallback)

Use only when the dots route fails or the image needs a model dots does not have. `weave_find_model` returns the model and an approximate cost; `weave_run_model` without `acknowledgedCost` only quotes. Show the quote and get the user's approval for every run, reruns included. As of 2026-10-20 the account holds a Starter View seat and a student Collab guest seat, so Weave or editing may be refused; report that and stop rather than guess.

## Use in the film

- Resolution: generated sizes are below 1920x1080 and 1080x1920. Use them for soft backgrounds, textures and illustration, where a 1.25x upscale does not show. Never for UI or small detail.
- Leave a dark or blurred layer between a busy image and text, then let `check` confirm contrast.
- A slow camera move on the image (scale 1.0 to about 1.08 over the film, `sine.inOut`) keeps a still image alive.
- Record each file in `assets/SOURCES.md`: route (dots GPT image or Weave), prompt, date, thread link.
