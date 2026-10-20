# Video backgrounds

## Seamless loop: pre-render, do not script

A generated clip ends on a different frame than it starts, so `<video loop>` jumps. Bake a ping-pong loop once:

```bash
bash scripts/pingpong.sh video/raw.mp4 site/assets 1920
```

It writes `raw.mp4` (H.264, faststart), `raw.webm` (VP9) and `raw.jpg` (poster, first frame). Then the page needs no JavaScript:

```html
<video class="bg" autoplay muted loop playsinline preload="auto" poster="assets/hero.jpg" aria-hidden="true">
  <source src="assets/hero.webm" type="video/webm" />
  <source src="assets/hero.mp4" type="video/mp4" />
</video>
```

```css
.bg { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
@media (prefers-reduced-motion: reduce) { .bg { display: none; } .hero { background: url(assets/hero.jpg) center / cover; } }
```

Keep video files local (the tutorial had to download its CDN link before the loop worked). Target under ~3 MB for the hero: re-run with a smaller width or raise `-crf` if larger.

### No video model: a stand-in from the plate

When Weave is skipped, make gentle motion from the still plate for free: a slow sideways drift plus a breathing glow. It is not generated motion, so say so in the report.

```bash
ffmpeg -loop 1 -i plate/plate.png -vf "scale=1824:-2,crop=1672:940:'(iw-1672)/2+40*sin(2*PI*t/8)':'(ih-940)/2',eq=brightness='0.04*sin(2*PI*t/4)':eval=frame,format=yuv420p" -t 6 -r 30 -c:v libx264 video/hero.mp4
bash scripts/pingpong.sh video/hero.mp4 site/assets 1672
```

Adjust `scale`/`crop` to the plate's size (crop width = plate width, crop height = the plate height rounded down to an even number). From a 1672x941 plate this gave a 12 s loop of 384 KB mp4 / 171 KB webm.

### Fallback only: in-browser boomerang

Use this only when the clip cannot be processed ahead of time (for example a visitor upload). It is the prompt that fixed the tutorial's lag, kept for reference:

> Do NOT seek via `video.currentTime` to reverse; it lags badly. On mount, play the video forward once with `video.play()`. Use `requestVideoFrameCallback` (fallback `requestAnimationFrame`) to capture every unique frame into an offscreen canvas (max width 960). On `ended`, stop capturing, hide the video and draw the frames to a visible canvas in a 30 fps loop whose index flips direction at either end.

Cost: every frame is kept as a bitmap. 10 s at 30 fps and 960x540 is 300 x ~2 MB, about 620 MB, which phones may not survive.

## Matching a video's background to the page: blend modes

A generated clip's "black" is rarely the page's black, so its edges show as a box. Options, from most to least common:

| Page | Clip | Try |
|---|---|---|
| dark | dark background, bright subject | `mix-blend-mode: screen` or `lighten` |
| light | light background, dark subject | `multiply` or `darken` |
| tinted dark card | dark clip | `exclusion`, `difference` (what the tutorial used) |

Over pure black, `exclusion` and `difference` change nothing (black is their identity), so they only help on a non-black surface. Decide by screenshots of two or three modes at the real size, not by name. Also scale the element (the tutorial used ~150%) so the clip's own edges fall outside the card, and set `overflow: hidden` on the card.

## Checks before calling it done

- The video plays: in a headless check, `document.querySelector('video').currentTime > 0` after a second. With Playwright: open the page per viewport (and once with `reducedMotion: 'reduce'`), wait ~2 s, read `currentTime`, `paused`, the computed `display` of the video and `document.documentElement.scrollWidth > innerWidth`, then screenshot.
- Mobile (375 px): text stays readable over the video; no overlay was needed, or one was added on purpose and said so.
- `prefers-reduced-motion: reduce` shows the poster.
- File sizes listed in the report.
