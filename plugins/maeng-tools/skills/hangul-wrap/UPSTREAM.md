Source: https://github.com/hanmariyang/giting-skills
Commit: 37fe55a979da4bb373382125da31549bbb72b4ab
Plugin version: 0.1.1
Installed: 2026-10-11
Layout: upstream SKILL.md, scripts, examples, README and MIT LICENSE copied unchanged into one Codex skill directory.

## Codex use

Keep this entire folder together. The upstream plugin's supporting files are
placed beside SKILL.md so its relative paths work after Codex installation.
Run from this skill directory:

```sh
node scripts/wrapcheck.mjs /absolute/path/to/page.html 390,768,1280
```

For Korean HTML/CSS, web UI, HTML documents and web slides, measure before and
after role-specific fixes at mobile and desktop widths. For Word, Google Docs,
PDF, PPTX and canvas/image text, use applicable typography principles and the
format's own rendered checks; this DOM checker does not verify those formats.
Do not apply blanket keep-all. The checker launches Chrome with --no-sandbox:
run it only on trusted local output or trusted pages.

The upstream README uses the original plugin installation paths. For this
repository, install skills/hangul-wrap with the Codex skill-installer.
