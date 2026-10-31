# Spec/Plan: motion-studio optional playbook

Date: 2026-10-31. One PR (#80), no Linear issue, no child tasks.

User approval (2026-10-31, this session): "무조건 해야한다보다 내가 어떻게 하면 좋을까 했을때 가이드라인 그리고 영상 만들 때 참고하는 정도로 반영해도 좋을 것 같아", then "커밋+PR 올려줘".

## Spec

Goal: ideas from seeco's X article "Opus 5.5 Motion Design: What the Viral 'One-Prompt' Videos Are Hiding" (2026-10-03) are available to motion-studio as guidance to consult, not as rules.

Mandatory rules:
- The Flow steps, gates A/B and the approvals in `SKILL.md` do not change.
- The article is summarized in our words, not copied.
- Only ideas the skill did not already cover are added.

- **AC-1** (judged in review) `plugins/maeng-tools/skills/motion-studio/references/playbook.md` exists, says it is optional and adds no steps or gates, and covers brief, reference, story, motion, sound, review and bigger films.
- **AC-2** (judged in review) `SKILL.md` gains exactly one pointer line to the playbook, outside the numbered Flow; no other `SKILL.md` text changes.
- **AC-3** (judged in review) nothing in the playbook loosens an existing approval: paid generation still points back to the SKILL.md approvals.
- **AC-4** `python3 -m pytest -q` passes.

Decisions:
- **D-1** No plugin version bump in this PR; installed caches pick it up at the next release.

## Plan

1. Write `references/playbook.md` (AC-1, AC-3).
2. Add the pointer line to `SKILL.md` (AC-2).
3. Run the full suite (AC-4).
