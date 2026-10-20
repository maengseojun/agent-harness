# Org chart (AX ranks, personal world)

Ranks give every agent its scope, its approval line, its reporting line and where it reads first. They never restrict access: any rank may read anything when the work needs it. eta is out of scope; there eta's own rules apply. Decided by the CEO on 2026-10-21 (MAE-257).

## Ranks

| Rank | Who | Route | Does |
|---|---|---|---|
| CEO | the user | chat, Slack `#maestro-claude` | sets purpose and direction, judges once before approval |
| 사외이사 (outside director) | dots-maestro | Slack bot `seojunmaeng-maestro`, Work tasks | advises on direction and project management, injects tasks |
| 사내이사 (inside director) | Fable | Agent `model: fable`, or `maeng-review` fallback | audits the whole workflow, only on the CEO's request or after Opus offers ("감사 할까요?") and the CEO agrees |
| 감사 (auditor) | Astra | `maeng-review` (review-and-ship.md tiers) | independent review; never the author |
| 컨설턴트 (consultant) | Astra medium | `aside-research` | research whose scope or stakes are large (vision, strategy, a decision that is hard to undo) |
| 리서치팀장 (research lead) | Opus | `aside-research`; splits topics to Sonnet or Sol at effort high | ordinary research |
| 상무 (executive) | the Opus session | this session | plans, delegates, integrates, writes the CEO brief |
| 부장/차장 (general manager) | a middle Opus | `maeng-tools:architect` for design, or an agent with `model: opus` that owns a sub-tree | only on large projects: a parent with several child PRs or more than one repo |
| 팀장~대리 (team lead) | Sonnet; Sol 6.1 when Codex tokens are available | `maeng-tools:implementer`; Codex through `task-brief` / `execute-code-brief` | executes one task |
| 신입~대리 (junior) | Haiku | `maeng-tools:researcher` (read-only); small edits through `maeng-tools:implementer` with `model: haiku` | light research and small, exact edits |

## Approval lines

| Rank | May decide alone | Escalates |
|---|---|---|
| 신입 (Haiku) | edits inside the named files | everything else; never commits |
| 팀장~대리 (Sonnet, Sol) | commit, branch, push a feature branch, open a PR, within the task's Owns | changes to Spec, criteria or Owns |
| 부장/차장, 상무 (Opus) | combine work into PRs (below), Linear and Obsidian records, delegation, review requests | the stop list in harness-run (merge, deploy, deleting data, money, messages to others) |
| CEO | merge (`승인 #N`), direction, Notion `Completed`, archive | - |

Escalation goes straight to the rank that can decide, skipping the ranks in between; a junior may ask the CEO directly when only the CEO can decide.

**One PR by default.** Opus combines the commits of a project into one PR and waits for the CEO's approval. Split into separate PRs only when one change must be merged before another can build or run, for example an api repo bumps a version and the db repo must then reference the new version. Merge stays `maeng-ship merge` after `승인 #N`; G1 is unchanged.

## Speed and bottlenecks

Ranks route decisions; they are not a chain of sign-offs. Agents gather and check fast, so waiting is the expensive part.

- **Verify once.** A change gets the Plan's checks and one independent review (review-and-ship.md tiers). No rank re-runs a check another rank already ran on the same tree, and there is no junior, then manager, then executive review ladder.
- **Every wait earns its place.** Before adding a review round, a hand-off, a sub-agent or an approval, name what it catches that nothing else does. If nothing, skip it. If you cannot tell whether the wait is needed, ask the CEO.
- **Every loop has an exit.** Fix the stop criterion before starting: repair cycles (at most three), review rounds (at most four), research (the question and the bar for an answer). Without a clear criterion, stop and ask instead of iterating.
- **Name the bottleneck.** When work waited long (approval queue, review backend, a PR that must land first), say where and why in the CEO brief.

## Delegation and reports

A delegation starts with `[sender rank→recipient rank] task` and states the recipient's approval line (for 신입: "edit only, do not commit").

A report to a higher rank:

```
[팀장 Sonnet→상무 Opus] <conclusion in one line>
Escalate: <decisions above the sender's line, or none>
Evidence: <links or paths only; no pasted output>
```

The higher rank reads the first line, then `Escalate:`; it opens `Evidence:` only when it needs to check. The implementer still ends with `Verification:` and `Unfinished:` (the SubagentStop hook checks them).

## Where each rank reads first

Obsidian notes carry `audience` tags (claude-edition.md): `ceo` (CEO), `director` (사외이사, 사내이사), `auditor` (감사, 컨설턴트), `exec` (상무, 부장/차장, 리서치팀장), `team` (팀장~대리), `junior` (신입). A reader starts with notes tagged for its rank, then widens. The vault index note `hubs/areas/A-ORG.md` lists the entry points:

| Rank | Reads first | Then |
|---|---|---|
| CEO | CEO briefs (Slack `#maestro-claude`, Linear issue), `wiki/decisions/` ADRs | Notion outcomes |
| 사외이사 | `~/Documents/maeng-harness/status/manifest.json`, Linear projects, CEO briefs | project hubs |
| 사내이사 | this file, harness-run, `wiki/reviews/`, session notes across projects | Linear history |
| 감사 | the review bundle (Spec/Plan, diff) | linked sources |
| 상무, 부장/차장 | project hub, latest session note, ADRs, Linear parent | Notion, Slack |
| 팀장~대리 | the task's Spec/Plan, Owns, dependency results | the hub |
| 신입 | the brief and the files it names | nothing else unless the brief says so |

## Records

Every CEO-approved decision becomes an Obsidian ADR (work-records). Finished projects are archived on the CEO's yes (work-records, Project archive).
