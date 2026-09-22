# Harness v1

Run document and coding tasks in this Codex project with the **harness-run** skill.
Codex coordinates native workers and an independent reviewer. A small Python
standard-library ledger keeps recovery state and publication receipts between
turns. There is no added orchestrator, server, paid API or background daemon.

## Start in Codex

Use a new task in this project after the skill is discovered, or explicitly ask
Codex to read `.agents/skills/harness-run/SKILL.md` in an existing task. For example:

> Use harness-run to execute this approved local task: [request]. Done means
> [checkable criteria]. You may change [paths]. Prepare external outputs as drafts.

Codex must inspect the saved task before repeating work. A stopped chat or closed
Mac does not keep this workflow running. Resume in Codex with the task ID.

## Responsibilities and storage

| Component | Responsibility |
| --- | --- |
| Native Codex task | Coordinator, worker/reviewer dispatch, current user authorization |
| `ledger.py` | Recovery stages, pinned inputs, ownership, hash-bound checks and outbox |
| `.agents/skills/harness-run` | Required routing, review and publication procedure |
| `skills.lock.json` / `sync_skills.py` | Immutable GitHub source pin and local integrity check |
| `.harness/` (ignored) | Private runtime state, source cache and raw execution evidence |
| GitHub / Notion / Linear | Code and skills / final documents / Endix task state, subject to authorization |

The current local harness and skill have not been published to GitHub. The real
upstream [skill-creator source](https://github.com/openai/skills/blob/49f948faa9258a0c61caceaf225e179651397431/skills/.system/skill-creator/SKILL.md)
was fetched at that commit and used to author the companion skill. A Notion link
does not install a skill. Local pins remain fixed until an explicitly reviewed
update; in-flight runs keep their previous references.

## Verify the source cache

From the repository root:

```sh
python3 harness/sync_skills.py          # Existing gh authentication; reads GitHub only
python3 harness/sync_skills.py --check  # Offline integrity check
python3 -m unittest discover -s harness -p 'test_*.py'
```

## Inspect, pause and resume

For the included `doc-pilot`, run from this repository root:

```sh
python3 harness/ledger.py --db "$PWD/.harness/pilots.sqlite" status <<'JSON'
{"task_id":"doc-pilot"}
JSON
```

The result includes the actual `owner`, `run_id`, `stage`, `next_action`, input
references, check/review evidence and publications. Task and skill bodies are not
repeated in routine status output. Use `context` with the current owner when a
worker actually needs the frozen skill text.

Ask Codex “pause doc-pilot” or “resume doc-pilot using harness-run”. Codex first
checks that any old worker has stopped, then calls the corresponding ledger
command with the task ID and current/new owner. The exact JSON contract, including
create/route/artifact/check/review/publication commands, is available with:

```sh
python3 harness/ledger.py --db "$PWD/.harness/pilots.sqlite" --help
```

The DB parent directory must already exist. CLI commands consume one bounded JSON
object on stdin and emit JSON. Exit 0 is a non-blocked transition, 1 is a recorded
blocker, and 2 is rejected input/transition; zero alone is not task completion.

One task records one primary artifact. Split independently mutable outputs into
separate tasks; a hash of a manifest alone does not monitor changes to its children.
Mechanical evidence and review files are also checked for changes. A repair
invalidates old approval/check results and allows up to three correction cycles.

No OpenAI API key is required. Native agent work uses this Codex account. Usage
availability is checked with the app's usage tool; token use is not a currency
charge estimate. Grok is optional and currently unauthenticated.

## Operational boundaries

The coordinator is trusted to report actual native agent IDs and check results.
The ledger binds evidence to file hashes; it cannot attest that an arbitrary
caller really ran a reviewer. The native runtime's permissions remain the actual
execution boundary. A paused ledger does not itself stop a running worker.

Local publication can reconcile a completed file write after a process crash.
An interruption before temporary-file cleanup may leave a `.ledger-*` staging
file beside the target. It is not another published result. Inspect it only after
the owning worker has stopped; v1 does not automatically purge these files.
Remote publication uses explicit intent plus connector readback. There is no
claim of exactly-once behavior across GitHub/Notion/Linear or protection against a
concurrent remote edit between read and write. When reliable comparison is absent
or the save result is uncertain, reconcile or block rather than repeat blindly.

Existing Endix policy could not be fetched from Linear. Proposed PR followup
behavior is a local fixture-tested proposal, not installed team automation.
No Current document, team database, schedule, webhook, contract, merge or
deployment is modified by the local harness build.
