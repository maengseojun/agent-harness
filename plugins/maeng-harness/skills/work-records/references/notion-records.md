# Personal Notion locators and schema

Locators to verify before use, not proof of current content. Personal Notion only; eta records live in eta Docs.

- Hub: https://www.notion.so/3e3e203190cd8143bdf5df0b46c1cb57
- Knowledge & Skills database: `e1e730a4-4301-4b53-8eb6-1f0fabc43840` (data source `399492eb-3723-43a8-8002-8b660f136add`)
- Runs & Evaluations database: `0326e3f3-e997-4ae3-b14c-36ba87596197` (data source `7903c212-74ce-4738-997f-88c4421ab21d`)
- Maintained harness-run index: https://www.notion.so/3e5e203190cd813c997ff252160dceff
- Canonical skill key: `skill:harness-run`

## Runs & Evaluations (outcomes)

Search by stable `Task ID` before creating; reuse that page on retry. Multiple matches are a reconciliation conflict. Notion search-before-create is not an atomic uniqueness constraint.

Properties: `Task ID` (text, unique within the hub: project/context plus a stable run id), `Linear Issue` (URL), `Session` (Claude session id or note link; the old `Codex Task` field is historical), `GitHub Revision` (URL), plus `Evidence`, `Knowledge`, `Outcome`, `Date`, `Status` (`Proposed`, `In progress`, `Completed`; only the user sets `Completed`, in person or relayed by another of their sessions per the global rule).

Body: objective and requirements; decisions, reasons and the Knowledge page affected; actual result and immutable evidence links; checks and review verdict; limits, remaining work, next action; Middleman decisions when present.

## Knowledge & Skills (policies)

Properties: `Canonical Key`, `Installed Release`, `Source`, `State` (`Maintained`, `Reference`, `Historical`), `Review Status` (`Unreviewed`, `Evidence checked`, `User accepted`), `Updated`, `Last Used`, `Reuse Outcome` (`Applied`, `Revised`, `Not useful`, `Blocked`).

- `Evidence checked` only after reading the cited source; `User accepted` only on an explicit user decision and only for the current claims and version. A material change downgrades to `Evidence checked` (new source checked) or `Unreviewed`.
- Empty values mean unknown, not approved.
- When a task actually used a Knowledge item, record the outcome in its Run and update only that item's `Last Used` and `Reuse Outcome` with readback. Changing reuse fields never promotes `Review Status`.
- Maintained policy pages are `record_kind: policy` and need no outcome backlinks.
