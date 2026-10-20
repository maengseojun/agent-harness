# Motion weights

Give each element class its own weight. Not everything springs.

| Class | Feel | Duration | GSAP ease | Overshoot |
|---|---|---|---|---|
| Micro UI (chips, cursors, toggles, counters) | Quick, precise | 0.15-0.3 s | `power2.out` | none |
| Panels and cards | Controlled settle | 0.5-0.9 s | `back.out(1.2)` or `power3.out` | small |
| Camera (push, pan, zoom on a wrapper) | Almost invisible | 1.5-4 s | `sine.inOut` | none |
| Headlines | Strong entry, then hold | 0.6-0.8 s in, hold 1 s or more | `power4.out` | none |
| Mascot or character | Playful, deliberate | free | `elastic` or keyframes | allowed |
| Exits | Faster than entries | 0.2-0.3 s | `power1.in` | none |

Rules:

- Stagger lists at 0.1-0.2 s; longer reads as lag.
- A headline must hold long enough to read twice: about 0.3 s per Korean 어절, at least 1 s.
- Set start states inside `fromTo`, never with CSS `transform` on a tweened node (lint `gsap_css_transform_conflict`).
- Animate a child of a `.clip`, never the clip's `visibility` or `autoAlpha` (lint `gsap_animates_clip_element`).
- No unseeded `Math.random`, clocks or network at render time; every frame must be reachable by seeking.
- Before hand-building a named effect (glitch, grain, shimmer, confetti, whip pan), browse the HyperFrames registry with `catalog` and install with `add <name>`.
