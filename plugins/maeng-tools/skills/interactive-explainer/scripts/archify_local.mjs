#!/usr/bin/env node
// Being agents integration: fixed vendor, no automatic update or brand capture.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
const args = process.argv.slice(2);
const allowed = new Set(['validate', 'finalize', 'deliver', 'check', 'browser-check', 'visual-check', 'guide', 'doctor']);
if (!allowed.has(args[0])) {
  console.error('Use a local authoring/check command; setup, updates and remote brands are excluded.');
  process.exit(2);
}
// The pinned browser checker adds --no-sandbox as root. Refuse that route.
const browserCommands = new Set(['finalize', 'browser-check', 'visual-check']);
if (browserCommands.has(args[0]) && typeof process.getuid === 'function' && process.getuid() === 0) {
  console.error('Browser checks require a verified non-root sandboxed runtime; refusing root execution.');
  process.exit(2);
}
// The installed Archify skill folder; nothing is vendored in this repository.
const home = process.env.ARCHIFY_HOME || path.join(os.homedir(), '.claude', 'skills', 'archify');
const cli = path.join(home, 'bin', 'archify.mjs');
if (!fs.existsSync(cli)) {
  console.error(`Archify is not installed at ${home}. Set ARCHIFY_HOME or install it on the user's request.`);
  process.exit(2);
}
if (['validate', 'finalize', 'deliver'].includes(args[0])) {
  const candidate = JSON.parse(fs.readFileSync(args[2], 'utf8'));
  const hasBrand = value => value && typeof value === 'object' &&
    (Object.hasOwn(value, 'brand') || Object.values(value).some(hasBrand));
  if (hasBrand(candidate)) {
    console.error('Brand capture is excluded from the local integration.');
    process.exit(2);
  }
}
// Pass only non-secret execution context. No provider keys or ambient update settings.
const env = { PATH: '/usr/bin:/bin', ARCHIFY_UPDATE_CHECK_DISABLED: '1' };
const result = spawnSync(process.execPath, [cli, ...args], { env, stdio: 'inherit' });
if (result.error) { console.error(result.error.message); process.exit(1); }
process.exit(result.status ?? 1);
