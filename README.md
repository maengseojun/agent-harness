# agent-harness

My personal harness for Claude Code: the skills, agents and hooks I use every day to research, write, design and ship code with AI agents.

It is a Claude Code plugin marketplace named `maeng` with two plugins:

| Plugin | What it holds | Hooks |
| --- | --- | --- |
| [`maeng-tools`](plugins/maeng-tools) | About 30 craft skills (research, diagrams, writing, front-end, browser automation, Obsidian notes) and four model-routed agents | None, so it is safe in any repository |
| [`maeng-harness`](plugins/maeng-harness) | The work loop: planned task trees, independent review, ship gates and work records | Yes: session start, prompt, and before and after tool use |

## How the work loop runs

1. **Plan.** `harness-run` turns a large request into an interview, a Spec and Plan, and a task tree. `task-brief` prepares a smaller handoff.
2. **Route.** Each task goes to the model that fits it. The agents in `maeng-tools` are routed by role: `architect` (Opus) for design, `implementer` (Sonnet) for code, `researcher` (Haiku) for reading, `design-reviewer` for rendered UI.
3. **Verify.** `maeng-verify` checks the result against the working tree it was built on. `maeng-review` sends it to an independent reviewer model.
4. **Ship.** Hooks block a direct push to the default branch. Merges go through `maeng-ship`, after review and checks pass.
5. **Record.** `work-records` keeps the task map in Linear and writes the finished outcome to Notion. `skill-feedback` turns a reusable correction into a revision of the skill that caused it.

## Selected skills

**Research and writing**
- `aside-collect` and `aside-research`: gather sources without judgment, then turn them into a cited, reviewed judgment.
- `coherent-writing`, `personal-essay`, `manuscript-writing-review`: connected prose in Korean and English.
- `easy-understanding`: explains a concept or a decision from first principles, with a map of what the reader must decide.

**Visuals**
- `diagram-explainer`: about 45 diagram and chart types as HTML and SVG.
- `interactive-explainer`, `frontend-slides`, `motion-studio`, `tutorial-video`.

**Front-end**
- `frontend-guidance`, `cinematic-site`, `design-reference`.
- `hangul-wrap`: measures Korean line breaks in a real browser and fixes words split in half.

**Code**
- `solidity-habits`, `foundry-testing`, `writing-a-vault`, `writing-an-auction`, `proof-guided-optimization`.
- `gh-fix-ci`, `gh-address-comments`, `blockchain-upstream-review`.

**Knowledge**
- `obsidian-workspace`: saves sources and outputs into an Obsidian vault as linked notes.
- `notion-authoring`, `linear`, `work-records`.

Each skill is one folder with a `SKILL.md`, under `plugins/*/skills/`.

## Install

In Claude Code:

```
/plugin marketplace add maengseojun/agent-harness
/plugin install maeng-tools@maeng
```

`maeng-harness` installs the same way (`/plugin install maeng-harness@maeng`). Its hooks and record skills assume my own Linear, Notion and Obsidian setup, so treat it as a reference rather than a drop-in.

## Layout

```
plugins/maeng-tools/     hookless skills, agents, third-party licenses
plugins/maeng-harness/   hooks, CLIs (bin/), skills, schemas, tests
harness/                 runner, ledger, installer and hook tests (Python standard library)
skills/                  standalone copies of skills for other hosts such as Codex
archive/                 retired skills, kept for reference
```

Tests run with `pytest` from the repository root.

## Contributing

This is a personal repository. Issues and pull requests are limited to collaborators. You are welcome to fork it and adapt any skill.

Some skills adapt open-source work. Their sources are named in each skill, and their licenses are in [`plugins/maeng-tools/licenses`](plugins/maeng-tools/licenses).
