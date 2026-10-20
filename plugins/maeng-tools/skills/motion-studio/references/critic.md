# Critique on rendered frames

Judge the film from its frames, not from what was intended. Do not watch the full video on repeat; read the contact sheet.

## Contact sheet

```bash
HYPERFRAMES_SKIP_SKILLS=1 npx --yes hyperframes@<pin> snapshot --at <t1>,<t2>,... --no-end -o ../reviews/<round>-<aspect>
```

Take one time per beat (its midpoint) plus two or three inside fast transitions. The command writes `frame-NN-at-<t>s.png` and `contact-sheet.jpg`. For a close look at small text, add `--zoom "<selector>"`.

## Independent reviewer

The author does not grade its own film. Spawn a subagent with only:

- the contact sheet and stills paths,
- the brief's one sentence and audience,
- the checklist and output format below.

Do not pass the HTML, the shot list's intentions or your opinion.

Reviewer prompt:

```
You review a short video from its rendered frames only.
Do not describe what the makers intended. Judge only what is visible.
The viewer should remember: <one sentence>. Audience: <audience>.
Score 1-5: hook (first 2 s), readability at phone size, continuity, motion, poster quality of the last frame.
Then name the three worst defects. For each: timestamp, evidence (what in which frame), and the smallest local fix.
Name no more than three. If fewer than three are real, say so.
```

## Checklist (reviewer and author)

1. Every word readable at phone size (vertical: body text at least about 44 px, headline at least about 96 px at 1080 wide).
2. Text and key content inside the title-safe box (10% inset), everything inside action-safe (5%).
3. Real assets only; no invented UI, numbers or logos.
4. Consistent type, color and motion across beats.
5. No awkward in-between frames: half-faded text over other text, overlaps mid-transition.
6. Cuts land on sound cues (when there is sound).
7. The first 2 s works with sound off.
8. The last frame works as a poster.

Two more passes before Gate B: watch once muted (the story must still read) and listen once with the screen off when there is sound (it must still have a shape).

## Loop

1. Patch only the beats named, one sub-composition each.
2. `check` (0 errors), snapshot the same times, review again.
3. Stop after three rounds, or earlier when a round finds nothing new. Record each fixed defect in `lessons.md`.
