import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { soundtrack } from '../studio.mjs';
import { readWav } from '../huashu/sound.js';

process.env.OM_SAMPLES = 'off'; // synthesized instruments: no download, same result on every machine
const CLI = fileURLToPath(new URL('../studio.mjs', import.meta.url));
const cues = { id: 'test', duration: 6, labels: { 'scene:hook': 0, 'scene:reveal': 3 }, hits: [{ name: 'impact', at: 3 }], music: { off: true } };

const rms = (x, a, b) => { let e = 0; for (let i = a; i < b; i++) e += x[i] * x[i]; return Math.sqrt(e / (b - a)); };

test('effects only: the WAV is as long as the film and the hit lands at its cue', () => {
  const r = soundtrack(cues);
  const dir = mkdtempSync(join(tmpdir(), 'ms-'));
  writeFileSync(join(dir, 'a.wav'), r.wav);
  const w = readWav(join(dir, 'a.wav'));
  assert.equal(r.music, 'off');
  assert.ok(Math.abs(w.data.length / w.rate - 6) < 0.02, `length ${w.data.length / w.rate}`);
  const at = (s) => Math.round(s * w.rate);
  const quiet = rms(w.data, at(1), at(2.5)), loud = rms(w.data, at(3), at(3.3));
  assert.ok(loud > quiet * 20, `hit ${loud} vs before ${quiet}`); // would fail if hits were dropped or placed elsewhere
});

test('music from a style and from an ABC score both render', () => {
  const styled = soundtrack({ ...cues, music: { product: 'devtool' } });
  assert.notEqual(styled.music, 'off');
  const abc = 'X:1\nT:t\nM:4/4\nL:1/4\nQ:1/4=120\nK:C\n!mark:hook! C D E F | !mark:reveal! G A B c |';
  const scored = soundtrack({ ...cues, music: {} }, abc);
  assert.equal(scored.music, 'score');
  assert.ok(isFinite(scored.lufs));
});

test('CLI writes the file; unknown effect names fail loudly', () => {
  const dir = mkdtempSync(join(tmpdir(), 'ms-'));
  writeFileSync(join(dir, 'cues.json'), JSON.stringify(cues));
  const ok = spawnSync('node', [CLI, 'sound', join(dir, 'cues.json'), '--out', join(dir, 'out.wav')], { encoding: 'utf8', env: process.env });
  assert.equal(ok.status, 0, ok.stderr);
  assert.ok(readFileSync(join(dir, 'out.wav')).length > 44);
  writeFileSync(join(dir, 'bad.json'), JSON.stringify({ ...cues, hits: [{ name: 'nope', at: 1 }] }));
  const bad = spawnSync('node', [CLI, 'sound', join(dir, 'bad.json'), '--out', join(dir, 'x.wav')], { encoding: 'utf8', env: process.env });
  assert.notEqual(bad.status, 0);
  assert.match(bad.stderr, /unknown sound effect/);
});

test('qa reads a rendered video and finds a dead stretch', () => {
  const dir = mkdtempSync(join(tmpdir(), 'ms-'));
  const mp4 = join(dir, 'still.mp4');
  const f = spawnSync('ffmpeg', ['-v', 'error', '-f', 'lavfi', '-i', 'color=c=gray:s=320x180:d=3:r=30', '-pix_fmt', 'yuv420p', mp4]);
  assert.equal(f.status, 0);
  const r = spawnSync('node', [CLI, 'qa', mp4], { encoding: 'utf8' });
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /still for ≥1 s/);
});
