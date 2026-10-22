# Vendored from huashu-motion

Source: https://github.com/alchaincyf/huashu-motion at `5f2608c2e12abcf518f74dde86093b19f7f88603` (v0.1.1), MIT, Copyright (c) Huashu. The license text is in `LICENSE` next to this file.

Copied verbatim from `cli/lib/`: `dsp.js`, `fx.js`, `composer.js`, `composed.js`, `samples.js`, `samples-build.js`, `score.js`, `sound.js`, `qa.js`.

Written for motion-studio (not upstream code): `project.js`, `browser.js` and `capture.js` are stubs. They satisfy the imports of `sound.js` and `qa.js` without the om project format, the Chrome probe or the studio. `../studio.mjs` is the entry point.

Not vendored: the om CLI, the studio and inbox editor, voice/Kokoro, the renderer, the templates and the "bean Huashu" character, which is not MIT.

`samples build` downloads instrument samples from their own sources on first use (CC0 and CC-BY). Their credits are written to `<pack>/NOTICE.txt`; copy the CC-BY lines into the film's `assets/SOURCES.md`.

To update, re-copy the same files from a newer commit, change the SHA above, and run `node --test ../test/studio.test.mjs`.
