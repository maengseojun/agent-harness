---
name: skill-feedback
description: Use when the user corrects the result of a skill-guided task, says a skill got something wrong, or states a reusable preference ("앞으로는 이렇게", "이 스킬 고쳐줘", "that's not how I want it done"). Captures the correction and updates the personal skill actually used when it is reusable; one-off fixes stay in the task. Evals, benchmarks and description tuning go to skill-creator.
---

# Skill feedback (correction capture)

1. **Fix the current deliverable first,** within its scope, in the same task.
2. **Classify the correction** from the actual request, result, skill text and the user's words:
   - one-off detail: keep it in the task record (Linear comment);
   - reusable preference or recurring failure in the skill's stated context: update that skill;
   - deterministic retry/validation defect: put it in code with a focused test.
   One explicit correction is enough evidence; do not infer a preference from a single unaccepted draft. Create a new skill only when no existing one covers a recognizable recurring context. Anonymize private examples.
3. **Edit the canonical source** of the skill that was used (the plugin's `skills/<name>/`), not a copy. Put the decision rule and its trigger in that file; keep it short and under 500 lines.
4. **Check** the revised skill against the observed case and one similar case. Record what improved and what is unknown.
5. **Ship** through the normal code route (branch, verification, review, `maeng-ship merge`); no direct pushes to the default branch.

For evals, benchmarks with variance, or tuning a skill's trigger description, use the `skill-creator` skill instead of doing it here.
