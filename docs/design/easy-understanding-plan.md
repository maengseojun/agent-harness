# Spec/Plan: easy-understanding skill (PR #86)

## Goal
The user wants explanations that make learning and deciding easy:
1. A map of the whole flow, plus what was missed and what must be decided.
2. The logic from its first step.
3. Textbook chapters for a smart newcomer that build on each other.

Reference .md files are copied verbatim and merged. Each reference serves narrow roles, never a whole output, so a merged output never switches style part by part. A past slide deck broke when each slide followed a different reference.

## Acceptance criteria
- AC-1: `plugins/maeng-tools/skills/easy-understanding/SKILL.md` exists. Its frontmatter has `name: easy-understanding` and a "Use when" description of at most 1024 characters. SKILL.md has fewer than 500 lines.
- AC-2: SKILL.md has a role table.
  - Each role has one merged rule in one place.
  - Every vendored reference appears in the table.
  - Only the Colors, fonts row decides colors, fonts and backgrounds.
  - A second table settles the reference conflicts. `references/method.md`, `references/look.md` and `references/review.md` exist. Every relative link and anchor in SKILL.md and references/ resolves.
- AC-3: Every file under `upstream/` is byte-identical to its pinned upstream commit.
  - `cd upstream && shasum -a 256 -c SHA256SUMS` passes for all 35 files.
  - Each upstream folder carries its upstream license file.
  - `SOURCES.md` lists repository@commit, upstream path and license for each file.
  - No file under `upstream/` is named `SKILL.md`, so the host does not discover the copies as skills.
- AC-4: look.md sets the look rules.
  - One token set per output.
  - The default set is diagram-explainer's style guide. Another diagram-explainer profile is used only on request; it is read directly, without overwriting the installed style guide.
  - Frontend-slides "Design Aesthetics" and its style presets are off.
  - The figure type is checked against diagram-explainer's visual-type guide for each structured phase and for the whole flow.
  - isas1 modes apply to the whole flow, in house tokens only.
- AC-5: `scripts/check_palette.py` checks the output file's colors.
  - It exits 1 and lists each color that is not in the effective token set, and exits 0 otherwise. Colors are hex, `rgb()`/`rgba()`, `hsl()`/`hsla()`, and CSS named colors in color-bearing declarations or SVG paint attributes.
  - Only token-table rows count as allowed colors. Prose mentions and the opt-in `terminal-*` skin do not.
  - `--allow` admits a named color, and `--tokens` selects the token file.
  - `python3 -m unittest test_check_palette`, run in `scripts/`, passes 7 tests.
- AC-6: method.md sets the explanation rules.
  - The map has five sections: destination, settled, to decide, missed, out of scope.
  - The chain starts from the first premise, using a 0.x prerequisite chain.
  - Chapters carry terms forward through a term ledger.
  - The output ends with a 1–3 item check list and has no quiz pauses.
  - Obsidian continuity applies only on request.
  - The Drive upload is asked once, when the output looks finished.
  - The fixed labels are written in Korean. For any other reply language they come from a fixed-label table and stay identical across the output.
- AC-7: The `explainer` skill is removed from maeng-tools. Its `explanation-design.md` lives in `diagram-explainer/references/`, and every link in `diagram-explainer/references/explanation-layout.md` resolves. No file under `plugins/` links into the removed plugin `explainer` folder.
- AC-8: `plugins/maeng-tools/.claude-plugin/plugin.json` has version `0.3.11`.

## Verification
- `python3 -m pytest -q` from the repo root (maeng-harness suite) passes.
- AC-3: `shasum -c`. AC-5: the unit tests. AC-2 and AC-7: a link and anchor check.
- AC-4 and AC-6 are document content, judged in review.
