# Spec/Plan: image generation via codex exec

- AC-1: motion-studio references/images.md names `codex exec` as the default image route, Weave as fallback; no Slack/dots/maestro route remains in motion-studio.
- AC-2: motion-studio step 3 (reference) allows drafting candidate look stills via that route when no reference exists, kept as drafts not film assets.
- AC-3: cinematic-site stages 2 (mock) and 3 (plate) and prompts.md §1 use `codex exec` with references passed as `-i`; no maestro/Slack route remains.
- AC-4: frontend-guidance sends generated web UI images to the same route.
- AC-5: the documented command works: prompt before `-i`, `-s workspace-write`, file saved in the target folder.
