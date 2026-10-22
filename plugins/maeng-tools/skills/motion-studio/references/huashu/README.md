# huashu-motion director docs, read through motion-studio

These files are vendored from [huashu-motion](https://github.com/alchaincyf/huashu-motion) at `5f2608c` (MIT, by Huashu). They are the method: how to direct, pace, colour and score a launch film. They were written for huashu's own `om` tool, so read every `om ...` command, `OM.*` call and `data-om-*` attribute through the table below. `about-author.md` was left out.

## Where to read what

| Step in motion-studio | Read |
|---|---|
| Brief and direction (steps 2-3) | `director.md` (read the product, the message's shape, three directions), `library/README.md`, `library/product-fit.md`, the matching `library/languages/*.md`, `colour.md`, `visual-direction.md` |
| Shot list (step 4) | `rhythm.md` (route, energy curve, hook within 3 s, burst, a stop before the peak), `library/techniques.md`, `grammars.md` (shapes only; its templates are not vendored) |
| Build (step 6) | `craft.md`, `product-demo-continuity.md` for UI demos, `talking-head.md` for footage, `library/formats.md` |
| Sound (step 6b) | `sound.md`, the annotated `scores/*.abc` |
| Critique (steps 7-8) | `verification.md` |
| Lessons (step 11) | `experience.md` holds general findings measured across films; read it at step 1 next to `lessons.md`. This user's taste goes to `lessons.md`, never into `experience.md`. |
| Background | `contract.md` (om's file contract, see the table), `provenance.md` (what was measured) |

## om → motion-studio

| In these docs | In motion-studio |
|---|---|
| `om learn` / `om learn harvest` | Read `lessons.md` and `experience.md` at step 1; log defects at step 11 |
| `om new`, `om templates` | `hyperframes init` (SKILL.md step 5); the om templates are not vendored |
| `om check`, `om still`, `om look` | `hyperframes check`, `hyperframes snapshot --at` |
| `om studio`, `om inbox`, `om done`, `om set`, `om undo` | Not vendored. Notes come in chat at Gate A/B; HyperFrames Studio (`preview`) is the visual check |
| `om swatch` | Not vendored; show palettes in the Gate A still |
| `tl.addLabel('scene:<id>', t)` | The beat start times in `shotlist.md`, written into `cues.json` as `"labels": { "scene:<id>": t }` |
| `OM.sfx(name, at, { gain, pan, note, dur })` | An entry in `cues.json` `"hits": [{ "name": ..., "at": ... }]`; names from `node scripts/studio.mjs list` |
| `OM.music({ product, style, drop, ending, bpm, motif, brand })` | `cues.json` `"music": { ... }`, same keys |
| `<script type="text/vnd.abc" id="om-score">` | A `score.abc` file passed with `--score`; its `!mark:<id>!` lands on `scene:<id>` |
| `OM.beat(n)`, `OM.music({ bpm })` | Set `"bpm"` in `cues.json` and place beat starts on multiples of `60 / bpm` |
| `om sound` → `assets/sound.wav` + `<audio id="om-sound">` | `node scripts/studio.mjs sound cues.json [--score score.abc] --out assets/sound.wav`, then one `<audio id="soundtrack" ...>` in each project's `index.html` |
| `om voice`, `OM.cue('word')` | Not vendored. Narration is a paid or user-supplied asset under the approval rule |
| `om render`, `--blur` | `hyperframes render --quality delivery` |
| `om qa` | `node scripts/studio.mjs qa renders/<file>.mp4 [--loop]` |
| `om fonts` | Choose and embed a font per video (SKILL.md); the om font pack has no Hangul |
| `data-om-id`, `OM.vars`, `OM.region`, `OM.camera`, `OM.spring`, `OM.random`, `vendor/om.js` | Not available. Use GSAP and HyperFrames equivalents: a seeded PRNG, a camera wrapper tween, `back`/`elastic` eases |
