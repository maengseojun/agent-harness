# Personal skill library

Each folder is one independently selectable skill. GitHub stores the reviewed
source; the local Codex or Work host uses its installed copy. A GitHub change does
not update an installed skill. Keep task outcomes and private examples in the
task record, then use [skill-feedback](skill-feedback/SKILL.md) only when an
observed correction is reusable in that skill's context.

| Skill | Use |
| --- | --- |
| [blockchain-upstream-review](blockchain-upstream-review/SKILL.md) | Map upstream blockchain changes to a project's actual pins and call sites. |
| [execute-code-brief](execute-code-brief/SKILL.md) | Implement an agreed coding brief. |
| [error-fix-manual-1](error-fix-manual-1/SKILL.md) | 오류 수정 매뉴얼 1: trace persistent save/readback verification failures through original responses, the shared comparator and actual runtime activation. |
| [dither-motion-landing](dither-motion-landing/SKILL.md) | Build landing pages with original dithered imagery and purposeful motion. |
| [frontend-guidance](frontend-guidance/SKILL.md) | Optional guidance for general website and app UI design; preserves requested aesthetics and links selected Impeccable references. |
| [prepare-work-deliverable](prepare-work-deliverable/SKILL.md) | Produce a substantial report, pitch or presentation from an agreed brief. |
| [skill-feedback](skill-feedback/SKILL.md) | Revise a skill after a reusable, observed gap. |
| [task-brief](task-brief/SKILL.md) | Prepare a substantial task for execution. |
| [work-records](work-records/SKILL.md) | Keep work maps and drafts in Linear; propose, save with approval, review and refine finished outcomes in personal Notion. Packaged with harness/install.py for its shared local approval helper. |

For a new Codex installation, use the built-in `skill-installer` with this
private repository, the selected `skills/<name>` path and a reviewed Git ref.
It installs only the requested folder and needs access to the private repository.
For example, ask Codex to install `task-brief` from
`maengseojun/agent-harness`, path `skills/task-brief`.
Verify the installed files against the exact reviewed commit before claiming the
version is active. The installer refuses to overwrite an existing skill; inspect
local changes and preserve the old copy before any update. New tasks may need to
start before their skill catalog sees a newly installed skill.

The harness coordinator is a separate packaged skill sourced from
[`../.agents/skills/harness-run/SKILL.md`](../.agents/skills/harness-run/SKILL.md).
Use it only when saved progress, independent review or managed closeout helps the
task. Its [runtime and installation](../harness/README.md) are maintained with the
Python runner. The independent skills above do not require the harness to load.
