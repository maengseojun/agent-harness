#!/usr/bin/env node
// motion-studio sound and QA, on the vendored huashu-motion engine (scripts/huashu/, MIT).
//   node studio.mjs sound <cues.json> [--score score.abc] [--out sound.wav]
//   node studio.mjs list                  effects, products and styles
//   node studio.mjs samples [build]       real-instrument pack status, or download it once (~55 MB)
//   node studio.mjs qa <video.mp4> [--loop]
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { LIST, mixdown, toWav } from './huashu/sound.js';
import { loadPack, packDir } from './huashu/samples.js';
import { qa, report } from './huashu/qa.js';

const [cmd, ...rest] = process.argv.slice(2);
const flag = (name) => { const i = rest.indexOf(name); return i >= 0 ? rest[i + 1] : null; };
const VALUED = new Set(['--score', '--out']);
const positional = rest.filter((a, i) => !a.startsWith('--') && !VALUED.has(rest[i - 1]));

// cues.json is the probe the engine expects: { id, duration, labels: { "scene:<beat>": seconds }, hits: [{ name, at, ... }], music: { ... }, words: [...] }
export function soundtrack(cues, score = null) {
  if (!(cues.duration > 0)) throw new Error('cues.json needs duration > 0 (seconds)');
  const { p, hits, out2, finalLufs, peak, musicOn } = mixdown(cues, { score, words: cues.words || [] });
  return { wav: toWav(out2), duration: p.duration, lufs: finalLufs, peak, hits: hits.length, music: musicOn ? (score ? 'score' : p.style) : 'off' };
}

async function main() {
  if (cmd === 'sound') {
    const cuesFile = positional[0];
    if (!cuesFile) throw new Error('usage: studio.mjs sound <cues.json> [--score score.abc] [--out sound.wav]');
    const score = flag('--score') ? readFileSync(flag('--score'), 'utf8') : null;
    const out = resolve(flag('--out') || 'assets/sound.wav');
    const r = soundtrack(JSON.parse(readFileSync(cuesFile, 'utf8')), score);
    mkdirSync(dirname(out), { recursive: true });
    writeFileSync(out, r.wav);
    console.log(`sound  ${out}  ${r.duration.toFixed(2)}s  ${r.lufs.toFixed(1)} LUFS  peak ${r.peak.toFixed(1)} dBFS  music ${r.music}  hits ${r.hits}`);
  } else if (cmd === 'list') {
    console.log(LIST());
  } else if (cmd === 'samples') {
    if (positional[0] === 'build') { const { buildSamples } = await import('./huashu/samples-build.js'); await buildSamples({ only: positional.length > 1 ? positional.slice(1) : null, log: (l) => console.error(l) }); }
    const pack = loadPack();
    console.log(pack ? `samples  ${pack.dir} (credits: ${pack.dir}/NOTICE.txt)` : `samples  none at ${packDir()}; music uses synthesized instruments`);
  } else if (cmd === 'qa') {
    if (!positional[0]) throw new Error('usage: studio.mjs qa <video.mp4> [--loop]');
    console.log(report(qa(resolve(positional[0]), { loop: rest.includes('--loop') })));
  } else {
    console.log(readFileSync(new URL(import.meta.url), 'utf8').split('\n').slice(1, 7).map((l) => l.replace(/^\/\/ ?/, '')).join('\n'));
    if (cmd) process.exitCode = 1;
  }
}

if (import.meta.url === `file://${process.argv[1]}`) main().catch((e) => { console.error(`error  ${e.message}`); process.exit(1); });
