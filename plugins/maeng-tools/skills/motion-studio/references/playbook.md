# Playbook (optional)

Tips to reach for when a film needs them. None of this is a step or a gate; the Flow in SKILL.md stays the contract. Source: seeco, "Opus 5.5 Motion Design: What the Viral 'One-Prompt' Videos Are Hiding" (X, 2026-10-03).

## Brief
- A short vibe prompt gets the safest defaults (centered title on a gradient, everything fading in), and everyone's reel starts to rhyme. When the user gives only a vibe, ask for one sentence the viewer should keep and one hard line.
- Keep one studio folder per brand: the next film reuses its renderer, sound and lessons and comes out faster.
- A one-line showreel prompt ("make a 15-second showreel of what you can do, go all out") is good for testing the setup, not for a real film.

## Reference
- Naming a style ("PC-98", "Swiss poster") works better than describing it.
- Good sources: one frame of a film you like, a short clip sliced every 0.5 s with ffmpeg, or the user's own past work. For launch films: whatships.com, Dribbble motion, competitors' launch videos.
- Spell out the look and the limits, and let the model pick the technique.

## Story
- One container that morphs from state to state, driven by real cursor clicks, with the last frame matching the first, reads as one story and loops cleanly.
- Staging the film inside a made-up UI (an editor, a dashboard) works like a film set: every element has a known state.

## Motion
- Give each class of object its own feel: small UI snaps with little overshoot, panels settle, the camera glides, headlines land hard and hold long enough to read. If everything overshoots, nothing feels precise.

## Sound
- With a user-supplied track, measure it before animating (e.g. librosa: bpm, beats, downbeats, onsets into a `beats.json`). State changes on beats, big moments on downbeats, clicks and whooshes on hits.
- Blindfold test: listen without the picture. If the audio has no shape on its own, the sound design is not finished.

## Review
- Besides the contact sheet: a strip of ~12 consecutive frames around the fastest move, the frames scaled to 360 px wide for phone readability, the clip played twice back to back for a loop stutter.
- Watch for overlapping text, elements that slide where they should ease, blurry scaled type, a dead beat with nothing happening.

## Bigger films
- For a long or complex film, a 960x540 animatic with placeholder audio before the full pass catches pacing problems cheaply.
- Generate-then-trace: a video model renders base shots for characters and physics, then the film is redrawn in code on top. Paid generation still needs the approval in SKILL.md.
- Effort: xhigh for a new film, max when the first seconds carry a launch, medium for small fixes.
