# MAE-268 Spec/Plan: huashu-motion director docs, sound engine and qa in motion-studio

Linear: MAE-268 (related MAE-253). Date: 2026-10-22. Single task.

## Decisions

- D-1 (user, 2026-10-22): take huashu-motion's composition and sound-effect engine and all of its director-rule docs; skip the point-at-frame editor.
- D-2: vendor files verbatim at upstream `5f2608c2e12abcf518f74dde86093b19f7f88603` (MIT). Three stubs (`project.js`, `browser.js`, `capture.js`) replace the om project format and the Chrome probe, so no vendored file is edited and a re-vendor is a copy.
- D-3: cues travel as `cues.json`, the same object `sound.js` read from the page (`labels`, `hits`, `music`), so the engine's `mixdown()` runs unchanged.
- D-4: sound becomes the default (local, free, deterministic). The sample-pack download is asked once. Narration stays under the paid-generation approval rule.
- `about-author.md` is left out (author promotion, not method).

## Criteria

- **AC-1** `scripts/studio.mjs` runs from any install path (spaces, non-ASCII, symlinks). Its `sound` command turns `cues.json` (and an optional ABC score) into a WAV as long as the film, with each hit at its cue. `list`, `samples` and `qa` work. Unknown effect names fail loudly.
- **AC-2** The engine and qa files are byte-identical to upstream at the pinned SHA; `NOTICE.md` and `LICENSE` record the source.
- **AC-3** All upstream `references/` except `about-author.md` sit under `references/huashu/`. `references/huashu/README.md` maps every `om` command and `OM.*` convention to the motion-studio flow. Every relative link in the skill's docs resolves.
- **AC-4** SKILL.md wires the docs, the sound step and qa into the flow and keeps the approval rules (sample download asked once; narration paid). SKILL.md stays at or under 150 lines.

## Verification

- AC-1: `python3 -m pytest -q plugins/maeng-tools/skills/motion-studio/scripts/test_studio.py` reports 1 passed. It runs `node --test scripts/test/studio.test.mjs` and requires `# pass 5` and `# fail 0`; the tests include a CLI run from a path with a space, Hangul and a symlink. Integration was checked once by hand on 2026-10-22 against the MAE-253 spike project: the WAV from `cues.json` was placed as `<audio id="soundtrack">`, `hyperframes check` passed, and the render had an AAC stream of 15.000 s.
- AC-2: `for f in dsp fx composer composed samples samples-build score sound qa; do cmp <upstream>/cli/lib/$f.js plugins/maeng-tools/skills/motion-studio/scripts/huashu/$f.js; done` prints nothing.
- AC-3, AC-4: `claude plugin validate plugins/maeng-tools` prints `Validation passed`. The link check over `references/**/*.md` and SKILL.md prints no missing link. `wc -l < SKILL.md` is at most 150.
- Root `python3 -m pytest -q` once.
