---
name: tutorial-video
description: Create requested tutorial videos or scripts, including 3Blue1Brown-inspired visual lessons with ElevenLabs narration. General explanations do not trigger video production.
---

# Tutorial video

Match the requested deliverable. A script request ends with a script; a finished-video request requires a rendered video or an explicit production blocker.

## Visual tutoring preference

For this user's conceptual tutoring videos, prefer a 3Blue1Brown-inspired teaching approach unless the user requests another format. This is an educational design preference, not a claim of affiliation or an instruction to reproduce a creator's footage, script, branding, or voice. Procedural screen-recording requests still follow the requested format.

- Start with a concrete question or example, build visual intuition, then introduce the general rule or formula. Connect the result back to the initial question.
- Make the important relationship visible through diagrams, geometry, graphs, or object transformations. Use consistent colors for the same entities and reveal one conceptual step at a time. A dark background and restrained accent colors are optional presentation choices, not the teaching goal.
- Give every movement a teaching purpose. Narration and visual emphasis should explain the same idea at the same time; avoid moving text or equations merely for decoration.
- Adapt vocabulary and pacing to the learner. Explain why each step follows, address the main likely misconception, and leave time to inspect a visual before proceeding. Use natural Korean for Korean requests.

## Animation, narration, and assembly

These are separate production roles: animation illustrates the concept, text-to-speech generates narration, and editing assembles them into the final video.

- For precise mathematical animation, consider Manim Community Edition when it is available and fits the scene. Check the actual renderer before committing; do not require Manim for every topic or claim it is installed from documentation alone. Simple SVG/HTML animation or existing rendering tools can suffice.
- Prefer ElevenLabs for requested synthetic narration when the user's connection or API credentials and authorized spending are available. Check available tools and current official language/model support; do not silently substitute another provider. If access is missing, finish the scene plan and narration script, then identify the missing connection or credential configuration. Never ask the user to paste an API key into chat or put credentials in skill files, generated sources, or logs.
- Use a suitable Korean voice with a calm tutoring delivery. Write formulas and symbols in their spoken form in the narration script, while preserving mathematical notation on screen. Scene directions belong outside the text sent to speech generation. Use an existing licensed voice or an authorized user voice, not an imitation of Grant Sanderson.
- Prepare the lesson and spoken script first. When generation is authorized, generate narration in useful scene-sized segments, measure actual audio durations, and time visual events around those durations and deliberate pauses. Assemble visuals and narration with available editing tools; do not guess synchronization from word count alone.
- Keep animation-only, script-only, and finished narrated video deliverables distinct. A finished narrated video needs a playable rendered file with its audio track verified.

Source references for these choices: [3Blue1Brown's teaching and animation guidance](https://www.3blue1brown.com/about/) and [ElevenLabs text-to-speech documentation](https://elevenlabs.io/docs/overview/capabilities/text-to-speech). Read current provider documentation when production needs specific API or model details.

## Production workflow

1. Establish the learning goal and any material constraints missing from the request, such as audience, duration, or source footage. Use reasonable defaults for low-impact choices instead of asking a long intake questionnaire.
2. Write a compact scene plan and spoken script in the user's language. For each scene, identify the teaching point, on-screen action, and approximate duration. Use only enough scenes to teach the topic. Preserve quoted text and code when showing them.
3. Choose available tools after the plan is clear. Prefer existing screen recordings, diagrams, and local rendering tools for procedural teaching. Load a relevant tool's current workflow only when production actually needs it.
4. Do not start paid generation, speech, or rendering APIs without approval covering the provider, requested service, cost or spending cap, and any data sent. Tool availability and a request for a video do not by themselves approve charges. Do not install software without the required approval.
5. If production is blocked, deliver the usable scene plan and script, state that no video was rendered, and ask only for the missing tool access, asset, or approval. Do not substitute an unsolicited paid service or claim the script is the finished video.
6. For a rendered video, check the teaching sequence, legibility of important text, timing, and any audio/video alignment. Check only the relevant outputs; do not create a broad production pipeline for one short tutorial. Report what was actually reviewed.

Deliver the requested artifact with a concise summary. Do not automatically publish it or reuse a person's voice or likeness without appropriate authorization.
