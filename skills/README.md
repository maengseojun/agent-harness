# Personal skill library

Each folder is one independently selectable skill. Reviewed personal skill
creations and updates must reach this repository's live main/default branch,
not remain only on a feature branch. The user has authorized this skill-only
publication loop; verify the remote files and local installation separately.
Do not force-push or change repository settings to satisfy it. GitHub stores the reviewed
source; the local Codex or Work host uses its installed copy. A GitHub change does
not update an installed skill. Keep task outcomes and private examples in the
task record, then use [skill-feedback](skill-feedback/SKILL.md) only when an
observed correction is reusable in that skill's context.

| Skill | Use |
| --- | --- |
| [blockchain-upstream-review](blockchain-upstream-review/SKILL.md) | Map upstream blockchain changes to a project's actual pins and call sites. |
| [coherent-writing](coherent-writing/SKILL.md) | Compose connected Korean and English prose with faithful evidence, paragraph reasoning, examples and relevant objections. |
| [endix-workflow](endix-workflow/SKILL.md) | Check migration into Endix and read live workflow and code Rules for subsequent team work. |
| [explainer](explainer/) | Diagram Design first for explanations and research; direct HTML/SVG output, explicit text-only routes and verified delivery. |
| [diagram-explainer](diagram-explainer/) | Original Diagram Design skill and 45 visual types; direct HTML/SVG, one-canvas overviews and school Drive verification. |
| [html-prototype-interview](html-prototype-interview/SKILL.md) | Plan websites and apps through a working HTML prototype, screen-based interviews and iterative revisions. |
| [interactive-explainer](interactive-explainer/SKILL.md) | Choose the view first, then add useful table/tree/path exploration or parameter simulation; static summaries need no app. |
| [tutorial-video](tutorial-video/SKILL.md) | Produce requested tutorial scripts or videos with visual tutoring and authorized ElevenLabs narration. |
| [execute-code-brief](execute-code-brief/SKILL.md) | Implement an agreed coding brief. |
| [dither-motion-landing](dither-motion-landing/SKILL.md) | Build landing pages with original dithered imagery and purposeful motion. |
| [hangul-wrap](hangul-wrap/SKILL.md) | Measure and fix Korean word splits and overflow in HTML at multiple widths; other document formats require their own rendered checks. |
| [frontend-guidance](frontend-guidance/SKILL.md) | Optional guidance for general website and app UI design; preserves requested aesthetics and links selected Impeccable references. |
| [prepare-work-deliverable](prepare-work-deliverable/SKILL.md) | Produce a substantial report, pitch or presentation from an agreed brief. |
| [presentation-design-interview](presentation-design-interview/SKILL.md) | Co-design presentations through focused interviews, real visual references, layout previews and typography refinement. |
| [skill-feedback](skill-feedback/SKILL.md) | Revise a skill after a reusable, observed gap. |
| [task-brief](task-brief/SKILL.md) | Prepare a substantial task for execution. |
| [notion-authoring](notion-authoring/SKILL.md) | Compose and verify illustrated Notion pages, subpages, databases and views. |
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

## Share the explanation skills

This repository stays private. Invited collaborators can use the source paths
`skills/explainer`, `skills/diagram-explainer`, `skills/interactive-explainer`, and
`skills/tutorial-video`. For file-based sharing, use the reviewed
`explanation-skills.zip` asset on an [explanation-skills release](https://github.com/maengseojun/agent-harness/releases).
The archive must include the sibling explainer and diagram-explainer folders plus the selected companions, their references, and a short
installation guide; it does not include the harness, task records, or settings.
Keep each complete skill folder together, including `references/` when present.

After changing an explanation skill, publish its reviewed source here and refresh
the sharing archive. Update and read back its local and ChatGPT Cloud copies
separately; publishing GitHub source does not synchronize either installation.

The harness coordinator is a separate packaged skill sourced from
[`../.agents/skills/harness-run/SKILL.md`](../.agents/skills/harness-run/SKILL.md).
Use it only when saved progress, independent review or managed closeout helps the
task. Its [runtime and installation](../harness/README.md) are maintained with the
Python runner. The independent skills above do not require the harness to load.
