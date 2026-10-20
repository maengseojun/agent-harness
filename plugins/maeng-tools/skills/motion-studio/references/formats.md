# Formats and delivery

Each aspect is its own HyperFrames project with its own layout. HyperFrames allows one root composition per project, and its studio guide starts a new project for a different aspect.

| Aspect | Project | Size | Layout notes |
|---|---|---|---|
| 16:9 | `wide/` | 1920x1080 | Rows; more elements per beat; headline about 96-120 px |
| 9:16 | `vertical/` | 1080x1920 | Stacks; fewer elements per beat; type larger relative to width; keep clear of platform UI at the bottom fifth |
| 1:1 | `square/` (only when asked) | 1080x1080 | Fewest elements |

Safe boxes (HyperFrames studio, Premiere defaults): everything visible inside action-safe (5% inset on every edge); captions and key content inside title-safe (10% inset).

## Render and verify

```bash
HYPERFRAMES_SKIP_SKILLS=1 npx --yes hyperframes@<pin> render --quality delivery -o renders/<slug>-<aspect>.mp4
ffprobe -v error -show_entries stream=width,height,r_frame_rate:format=duration -of csv=p=0 renders/<slug>-<aspect>.mp4
ffmpeg -v error -ss <beat midpoint> -i renders/<slug>-<aspect>.mp4 -frames:v 1 ../reviews/final-<aspect>-<t>.png
```

Expected: the project size, the brief's length, 30 fps unless the brief says otherwise. A pulled frame must show the chosen font, not a fallback or empty boxes.

## Deliver (Gate B)

- `renders/<slug>-wide.mp4`, `renders/<slug>-vertical.mp4`
- Poster frame per aspect (`snapshot --at <last beat midpoint>`)
- The last contact sheet per aspect and the review notes
- Source: both projects as they are, with the exact render command
- `assets/SOURCES.md`: every asset with its origin (real, GPT image via codex, Weave, font license)
- What still needs a human look (claims, legal text, brand approval)

Do not run `hyperframes publish`, `cloud` or `lambda`; those upload the project. Delivery stays in the studio folder.
