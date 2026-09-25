---
name: skill-feedback
description: Review a skill-guided task result or user correction and improve a personal skill when the feedback is reusable; keep one-off corrections in their task.
---

# Skill feedback

Use the actual request, result, checks, selected skill text and user feedback as evidence. A user request to revise the output or a reported mistake triggers this check for the skills actually used. First correct the current deliverable within its scope and in the same task. Assess the result against the skill's relevant checks and the user's requirements; record what worked as well as any concrete gap. Identify whether a gap came from the task instructions, the skill, or execution.

When source writes are authorized, update a skill actually used in that same task if the correction expresses a reusable preference or fixes behavior likely to recur in that skill's stated context. One explicit correction can be enough evidence; do not wait for repeated complaints. Create a new skill only when no existing one covers a recognizable recurring context. Do not infer a personal preference from a single unaccepted draft. Keep private examples anonymized.

Put one-off details in the task record. Revise the existing skill's canonical source path; do not create a second copy under `skills/`. New standalone skills in this repository belong at `skills/<name>/SKILL.md`. Put a reusable decision rule and its trigger in that source; put deterministic retry or validation defects in code with a focused check. Keep the skill short and independent of `harness-run` unless its work actually needs the harness.

Check the revised skill against the observed case and one similar case when possible. Record what improved and what remains unknown. Within the authorized repository, commit and push only reviewed files, then fetch the exact remote commit and compare each changed file byte for byte before claiming GitHub storage. Record that commit and each skill path. Confirm the user-level installation separately before claiming that the skill is available. On a later real use, compare the outcome with the prior version and revise again only if that evidence warrants it.
