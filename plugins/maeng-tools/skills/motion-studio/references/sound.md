# Sound

Music and effects come from the vendored huashu-motion engine (`scripts/huashu/`, MIT). It runs locally, makes no network calls and costs nothing; the same `cues.json` always gives the same WAV. The method behind it is in [huashu/sound.md](huashu/sound.md) and the annotated [scores](huashu/scores/). Read their `OM.*` names through the mapping in [huashu/README.md](huashu/README.md).

## cues.json

Write it from `shotlist.md`. Wide and vertical can share one file when their beats start at the same times; otherwise write one per project.

```json
{
  "id": "<slug>",
  "duration": 15,
  "labels": { "scene:hook": 0, "scene:problem": 2, "scene:reveal": 5, "scene:proof": 9, "scene:close": 13 },
  "hits": [
    { "name": "impact", "at": 0.15 },
    { "name": "whoosh", "at": 5.1 },
    { "name": "chime", "at": 5.5 },
    { "name": "tick", "at": 9.8 }
  ],
  "music": { "product": "devtool", "drop": "reveal", "ending": "button" }
}
```

- `labels`: one `scene:<beat>` per beat start; they are the music's sections.
- `hits`: one per landing that matters, roughly 8-15 per 30 s, at the exact second the motion lands. `node <skill>/scripts/studio.mjs list` prints the 23 effect names and their options (`gain`, `pan`, `pitch`, `note`, `dur`).
- `music`: a built-in direction (`product`: devtool, ai, hardware, consumer, cute, creative, game, data, explainer, calm, guofeng, hype; or `style`), with `drop` (a beat id), `ending` (`ring`, `button`, `stop`), `bpm`, `brand`, `seed`. `{ "off": true }` gives effects only.
- For a launch film, write the score yourself in ABC (`score.abc`, its `!mark:<beat>!` landing on `scene:<beat>`) and pass `--score score.abc`; the built-in direction is the quick fallback.

## Run and place

Run it from `videos/<slug>/` once per project, so each project has its own copy at the path its `index.html` uses:

```bash
node <skill>/scripts/studio.mjs sound cues.json [--score score.abc] --out wide/assets/sound.wav
node <skill>/scripts/studio.mjs sound cues.json [--score score.abc] --out vertical/assets/sound.wav
```

Use `vertical/cues.json` for the second run when the vertical beats start at other times. Each run prints the length, loudness (about -14 LUFS) and number of hits. Add one audio clip to each project's `index.html`, inside the root and next to the other clips:

```html
<audio id="soundtrack" src="assets/sound.wav" data-start="0" data-duration="15" data-track-index="9" data-volume="1"></audio>
```

Verified 2026-10-22 with hyperframes 0.8.181: `check` passes and the render carries an AAC track of the film's length. Every `<audio>` needs an `id`, or the HyperFrames mixer drops it.

You cannot hear the result, so look at it: `ffmpeg -i assets/sound.wav -lavfi showspectrumpic=s=1600x400 reviews/spectrum.png`. A flat energy curve means the film has no contour; give it a stop and a peak (`huashu/rhythm.md`). The final listen is the user's, at Gate B.

## Instruments

Without the pack, the music plays on synthesized instruments. `node <skill>/scripts/studio.mjs samples build` downloads the real-instrument pack once (~55 MB, CC0 and CC-BY: piano, strings, drum kits) to `~/.cache/huashu-motion/samples`. Ask the user once before the first build. Set `OM_SAMPLES=off` to force synthesized instruments.
