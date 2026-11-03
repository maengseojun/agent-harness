# Spec/Plan: taste-skill as a reference in two selectable modes

status: current · PR #89 · base `feat/harness-v1`

Goal: the user can point HTML mockups and UI builds at [leonxlnx/taste-skill](https://github.com/leonxlnx/taste-skill), choosing per request between following it as its author intended and borrowing its references and code under their own direction, always on its latest revision.

Decisions:
- D-1: not installed as a plugin, because its description claims every web page task and would remove the choice. Wrong if: a plugin setting can stop auto-invocation while keeping the skill callable.
- D-2: hook into `design-reference` and `frontend-guidance` and add no new skill. `html-prototype-interview` already routes visual direction through design-reference. Wrong if: a fresh session asked for "taste 참고" loads neither skill.
- D-3: always use the latest revision (user, 2026-11-03), with changed scripts read before they run. Wrong if: none (user preference).

Owns: `plugins/maeng-tools/skills/design-reference/{SKILL.md,references/taste-skill.md}`, `plugins/maeng-tools/skills/frontend-guidance/SKILL.md`, this file.
Exclusions: version bump (#88 holds 0.3.12), vendoring taste-skill code into this repo, `maeng-harness` skills.

- AC-1: `references/taste-skill.md` maps "taste 그대로" to Follow and "taste 참고" to Borrow. When taste is named without a mode, it asks once. When taste is not named, it is not used.
- AC-2: both SKILL.md descriptions name taste-skill with both trigger phrases, both bodies link to `references/taste-skill.md`, and every relative link resolves.
- AC-3: the update block clones on first use, prints a first-clone notice so all scripts are read before any runs, and checks out `origin/HEAD` on every use. It prints `taste-skill <sha> <date>`, prints a `scripts/` diffstat only when the revision moved, and keeps the cached copy with exit 0 when the fetch fails.
- AC-4: Follow runs upstream `SKILL.md` as written. Brand colour and type enter through `--keep`, naming only the fields the brand fixes; the logo and other `DESIGN.md` choices stay as brief constraints. Borrow keeps the user's direction, offers composition as library blueprints and never as `--options` directions, treats house rules as opt-in and the inspector as advisory, and requires the upstream MIT notice on any copied file. No taste-skill code is vendored here.
- AC-5: no regression.

Verification tier: docs-only.

Verification:
- AC-1: `grep -cE '"taste 그대로".*Follow|"taste 참고".*Borrow|Ask once|Neither' plugins/maeng-tools/skills/design-reference/references/taste-skill.md` expect 4
- AC-2: `grep -c 'taste 그대로, taste 참고' plugins/maeng-tools/skills/{design-reference,frontend-guidance}/SKILL.md` expect 1 each. Every `](path)` in both files exists relative to its folder.
- AC-3: declared check. Extract the bash block under "Update to the latest" with `T` set to a scratch folder and run it four ways: fresh, rerun, after `checkout HEAD~15`, and with origin set to an unresolvable host. Expect a revision line in all four, a diffstat only in the third, and exit 0 in all.
- AC-4: `git ls-files | grep -c '/taste-skill/'` expect 0 (no vendored upstream folder). `grep -c 'taste-skill@<revision> (MIT)' plugins/maeng-tools/skills/design-reference/references/taste-skill.md` expect 1.
- AC-5: `python3 -m pytest -q` expect all pass.

Review focus: can a request trigger the wrong mode, or trigger taste when it was not named? Can the update step run changed upstream scripts unread? Does Follow contradict a rule the user keeps?
