# taste-skill: two modes

[taste-skill](https://github.com/leonxlnx/taste-skill) (MIT, © 2026 Leonxlnx) is an art-direction skill for web pages and app screens: a library distilled from studied gallery sites, a script that deals directions, house rules, and a real-browser inspector. It is used only when the user names it, in one of two modes, always at its latest revision.

## Pick the mode

| The user says | Mode |
| --- | --- |
| "taste 그대로", "taste 따라서", "follow taste" | **Follow**: taste-skill directs the design, as its author intended |
| "taste 참고", "taste 레퍼런스", "taste 코드 빌려", "borrow from taste" | **Borrow**: the user's direction leads; taste supplies references and code |
| names taste without a mode | Ask once: 그대로 or 참고 |
| does not name taste | Neither. Work as before |

The mode holds for the task until the user changes it. It is not installed as a plugin on purpose: its description claims every web page task, which would remove the choice.

## Update to the latest before each use

```bash
T=~/.cache/maeng/taste-skill
[ -d "$T/.git" ] || { git clone -q https://github.com/leonxlnx/taste-skill "$T" && echo "first clone: read skills/taste-skill/scripts before running any"; }
OLD=$(git -C "$T" rev-parse HEAD)
git -C "$T" fetch -q origin && git -C "$T" checkout -q --detach origin/HEAD
git -C "$T" log -1 --format='taste-skill %h %cs'
[ "$OLD" = "$(git -C "$T" rev-parse HEAD)" ] || git -C "$T" diff --stat "$OLD" HEAD -- skills/taste-skill/scripts
```

Run it every time the skill is used and name the revision it prints in one line. When the fetch fails (offline), continue on the cached copy and say so. On a first clone, read all of `scripts/` before running any script; when the last line lists changed scripts, read that diff. `grep -rhoE 'https?://[a-zA-Z0-9.-]+|child_process' "$T/skills/taste-skill/scripts" | sort | uniq -c` lists every host and process call to start from. The scripts should call only open-collection APIs (Openverse, Wikimedia Commons, Art Institute of Chicago, the Met, Internet Archive, NASA) and spawn only a local browser. A new host or process is reported to the user before use. When the revision moved, also skim the new `CHANGELOG.md` entries, since the run below defers to whatever `SKILL.md` now says.

`<skill>` below is `$T/skills/taste-skill`. Its scripts need Node 22+ and Chrome, Edge or Chromium; `assets.mjs` needs network access. If `draw.mjs --list scenes` prints "No scene library yet" (true on 2026-11-03), skip scroll-scene steps.

## Follow mode

Read `<skill>/SKILL.md` whole and run it as written: page or app screen, the run (brief, argument, draw, idea, words, build, gate, look, move, report), its house rules and its gate. Adopt the dealt direction sheet; do not blend it with your own layout or with `frontend-design` taste. Its rules replace the user's general style preferences for this task; these still hold because they do not contradict it:

- Brand colours and typefaces enter through taste's `--keep`, naming only what the brand fixes (`palette`, `type`, or `palette,type`); a field left out is dealt, and the flag keeps nothing else. The logo and every other fixed fact or accepted `DESIGN.md` choice go into the brief and the build as constraints (taste's "existing brand" case: keep the asset, say so, `--allow <rule>` for a house rule it breaks). Record the dealt direction (id and seed) in `DESIGN.md` as a new dated line.
- Generated images go through `codex exec` (`cinematic-site` prompts §1), asked before each run. Taste's own picture search (`assets.mjs`) needs no extra approval.
- Korean UI: run `hangul-wrap` after taste's gate.
- An HTML prototype keeps `html-prototype-interview`'s working flows and interview; taste decides how its screens look.
- `.taste-skill/` holds working files; keep it out of commits unless the user wants it.

Report in taste's step 10 form.

## Borrow mode

The user's direction, references and `DESIGN.md` lead. Taste's house rules (no gradients, no monospace, no eyebrows and the rest) are its author's taste: apply one only when the user agrees.

**References.** Search the studied sites by the user's words, then open the real site under this skill's browser rules and show it with its link:

```bash
node -e 'const [f,...w]=process.argv.slice(1);for(const x of require(f))if(w.some(k=>x.mood.includes(k)||String(x.archetype).includes(k)||x.kind===k))console.log(x.score,x.id,x.url,"-",x.idea)' "$T/skills/taste-skill/library/sites.json" editorial warm | sort -rn | head -12
node <skill>/scripts/draw.mjs --site <id>    # the full notes: idea, hero, sections, type, palette
```

Moods include playful, warm, confident, technical, dark, editorial, cinematic, precise, calm, bold, quiet, minimal. When the user's direction leaves composition open, show two or three hero or section blueprints set in that direction and let the user pick. Do not use `--options`: it deals whole taste directions (idea, field colour, manner) that can override the user's.

```bash
node -e 'const [l,r]=process.argv.slice(1);const a=r==="hero"?require(l+"/heroes.json"):require(l+"/sections.json").filter(s=>s.role===r);for(const s of a)console.log(s.id,"-",s.name,"-",s.blueprint.split(". ")[0])' "$T/skills/taste-skill/library" pricing   # or hero, features, faq …
```

 `references/type.md`, `colour.md`, `layout.md`, `motion.md`, `copy.md` and `critique.md` are reading: open the section that answers a real question.

**Code.** Copy into the project and adapt it to its stack and tokens; add no dependency.

| Need | Take |
| --- | --- |
| A neutral start: reset, token names, fluid type steps, grid, focus | `assets/base.css`, `assets/base.js` |
| Dashboard or app screen: panels, tables, controls, small SVG charts | `assets/app.css`, `assets/charts.js`, `references/app-screens.md` |
| Entrance, hover and scroll motion with reduced-motion fallbacks | recipes in `references/motion.md` |

A copied file or a substantial part of one carries the upstream notice: add the upstream `LICENSE` to the project (for example `third_party/taste-skill/LICENSE`) and a first-line comment `from leonxlnx/taste-skill@<revision> (MIT)`. Ideas, measurements and a few lines need no notice.

**Checks.** `lint.mjs` and `inspect.mjs` may run for their measurements (overflow, contrast, headline lines, margins, blank stretches). Pass `--allow <rule>` for each house rule the user's direction breaks on purpose; a remaining house-rule FAIL is advice, not a gate. The `frontend-guidance` checks still decide delivery.
