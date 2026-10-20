# Shot list: beats and states

Turn the story into states that change on beats. Write states before shots: for a UI, list the screen states first (for example `SEARCH -> RESULT -> DETAIL -> ACTION -> CONFIRMATION`), then decide which beat shows each change.

## Default 15 s arc (scale the times for 30 or 60 s)

| Time | Beat | Job |
|---|---|---|
| 00-02 s | HOOK | The question or tension; must work with sound off |
| 02-05 s | PROBLEM | The pain, concrete and recognizable |
| 05-09 s | REVEAL | The product or idea enters |
| 09-13 s | PROOF | One real screen, number or flow that shows it works |
| 13-15 s | CLOSE | The one sentence, logo, poster-worthy last frame |

## shotlist.md format

```markdown
| # | Time | Beat | Entry state | Exit state | On screen (text verbatim) | Motion class | Sound cue | Purpose |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.0-2.0 | HOOK | empty | headline held | "설명 영상, 매번 처음부터?" | headline | hit at 0.15 | stop the scroll |
```

- Purpose is required. A shot that cannot say why it exists is cut.
- Times are the timeline: compositions take `data-start` and `data-duration` from this table, and sound cues sit on the same times.
- Keep one idea per beat. Two ideas in one beat become two beats or one is cut.
- Beats map one to one to sub-compositions (`compositions/NN-<beat>.html`), so a critique fix names a beat and touches one file.
