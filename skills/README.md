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
| [prepare-work-deliverable](prepare-work-deliverable/SKILL.md) | Produce a substantial report, pitch or presentation from an agreed brief. |
| [skill-feedback](skill-feedback/SKILL.md) | Revise a skill after a reusable, observed gap. |
| [task-brief](task-brief/SKILL.md) | Prepare a substantial task for execution. |

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
