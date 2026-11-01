# Research method (shared by aside-collect and aside-research)

Read the section your mode needs; no mode needs all of it.

| Section | quick | deep | bulk | watch |
|---|---|---|---|---|
| Access diagnosis | yes | yes | yes | yes |
| Pacing and licensed access | - | if downloading | yes | yes |
| Claims and hypothesis cards | - | yes | - | - |
| Explore, test, stop | - | yes | - | - |

## Access diagnosis

An access failure is a state, not a finding. Never conclude the cause from one status code (a 403 can be a login wall, a region block, a bot block or a missing permission). Record:

- status code, final URL after redirects, the first visible lines, body length
- whether other pages on the host load
- whether the same URL loads in the user's own logged-in Aside session
- headers you can see: `Retry-After`, `Last-Modified`, `Age`

An empty read is not an empty page. Before recording zero results, take a fresh snapshot, check that the selector matched, and look at the network response or a screenshot. A REPL run that ends `ok` very quickly without its expected output, or `error` after a step already took effect, is an aborted script, not a result.

| Kind | Evidence | Allowed next step | Stop when |
|---|---|---|---|
| `login_required` | redirect to sign-in, 401, only a preview | read in the Aside profile if it is already signed in; else ask the user to sign in; look for a public copy | no account or sign-up needed: list it for the user. Never type passwords |
| `session_expired` | a host that worked earlier in this run now shows sign-in | pause that host, ask the user to sign in again, continue other hosts | first detection for that host |
| `forbidden` | 403 with permission text, other pages fine | if the user has the permission, use that session | the body is a bot or "access denied" page: reclassify as `refused` |
| `rate_limited` | 429, `Retry-After`, "too many requests" after a burst | honor `Retry-After`; that host goes to one request at a time; back off x2, at most 3 tries | 3 in a row, or the wait exceeds the run: `deferred` to the next run |
| `timeout` | no response (not slow), other hosts fine | one retry with a longer timeout | 2 failures: record, retry next run |
| `js_empty` | 200 with a tiny body, empty root element, `noscript` notice | render in Aside and `snapshot`; use the public JSON or RSS the page itself calls | still empty after rendering: suspect login or refusal and reclassify |
| `gone` | 404/410, or 200 with "not found" text (soft 404) | site search for a moved copy, the author's copy, a public archive snapshot with its date | no copy: record `gone` |
| `stale_copy` | body date, `Last-Modified`, snippet differs from the live page | read the live page; record both dates; prefer live | live unreadable: label "copy as of <date>" |
| `paywalled` | truncated body, subscribe overlay, abstract only | the user's licensed session (see below); else author manuscript, institutional repository, abstract | no copy: record `paywalled`, cite the abstract only |
| `refused` | CAPTCHA, bot challenge, "unusual traffic", robots.txt Disallow, terms forbidding automated access | the site's own API, export, RSS, sitemap, official mirror; list the URL for the user to open | immediately, for the rest of the run |

Fallbacks, in order: the site's own API, export, RSS or sitemap; an official mirror; the author's own copy or an institutional repository; a public archive snapshot. A fallback is labelled as a substitute and records its date and version next to the original's, e.g. `source: arXiv 2208.06046v3; original: journal version not read (paywalled)`.

`refused` is final for the run: do not retry it through another tool, account, network or IP, do not solve or hand off CAPTCHAs, never use Aside's `captcha-solver` skill, and do not imitate human behaviour to continue.

## Pacing and licensed access

- One request at a time per host, a few seconds apart with random jitter, a longer pause between batches, and per-run and per-day caps. Google searches run strictly one at a time.
- At most 3 concurrent Aside sessions unless the user asks for more.
- When a host signals a limit (429, `Retry-After`, CAPTCHA, bot check, "unusual traffic"), stop that host for the run and record it. Do not continue by changing the user agent, fingerprint, IP or account, or by simulating mouse or keyboard behaviour.

Licensed collections (library VPN or proxy, publisher platforms, subscriptions), for the user's own research:

- The user connects the VPN and signs in inside the Aside profile. Never type credentials.
- Topic-level download is allowed for items that passed selection for this research question: one file at a time, sequential, at most 30 files per platform per day unless the user sets another cap.
- Never sweep whole journals, issues, volumes or result pages.
- Stop the platform for the day at the first warning: a download-limit notice, "systematic downloading", a CAPTCHA or an access-suspended page. Publishers may block the whole institution's IP range, not just the user.
- Files stay personal: Drive offload only (see aside-collect), never shared or re-published.

Research profile: when the user has set up a separate Aside profile for research, pass `--profile <id>` (ids from `aside host profiles` or the MCP `browser_profiles` tool). The user creates and signs in to that profile. Never create an account to replace one that was limited or suspended.

## Claims and hypothesis cards

Tag every sentence in Judgment and Evidence with one type:

- **[O] observed**: stated in a source, with location (S- id + page, section or timestamp).
- **[D] deduced**: follows if the listed premises hold; list the premises.
- **[I] induced**: a pattern across n independent cases; give n and how the cases were chosen.
- **[H] hypothesis**: an explanation you propose; needs a card.

Independence: trace each supporting source to its origin (who measured or observed first). Sources that repeat one origin count as one. Write "n independent origins (m restatements)", not "n sources".

Causation: a claim that X causes Y needs time order, a mechanism, and the main alternatives (confounder, reverse direction, selection) addressed. Otherwise write it as an association.

Write cards only for the 2-4 claims that could change the judgment:

```
H-<n>: <claim in one sentence>
Starting facts: [O] <fact> - S-xxx p.4 / 12:30 / §2.1
Extra premises: <needed, not yet checked>
Steps: fact -> step -> claim
Weakest link: <the step most likely to break>
Competing explanations: H-a <...> / H-b <...>
Evidence against: <...> (n independent origins)
Would be wrong if: <one concrete observation>
Next check: <search, data or experiment that separates it from the competitors; cost>
State: candidate | leading | rejected | parked
```

A claim with no "would be wrong if" is an opinion, not a hypothesis.

Search pattern, from any field: anchor -> mechanism -> boundary conditions -> support and opposition -> gaps.

| | Academic | Product | Market | Technology |
|---|---|---|---|---|
| Anchor | one core paper | a flagship use case or launch | a reference event | a reference design write-up |
| Mechanism | the causal path the authors give | where users save time or money | the price or flow mechanism | why the design works |
| Boundary conditions | moderators, sample | task frequency, site policies, trust | concurrent shocks, parameters | task coupling, budget |
| Support / opposition | replications, critiques | churn reports, incidents, competitor reviews | governance threads, on-chain or filings data | counter-essays, own run logs |

## Explore, test, stop

- Explore wide first: every source type in the source map, both languages if relevant, no leading hypothesis yet. Narrow when the query log saturates (two queries in a row add <10% new unique candidates) or 2-3 competing explanations exist.
- Spend verification on claims that would flip the judgment if wrong, ranked by impact x uncertainty, cheapest decisive check first.
- When a hypothesis becomes the leading one, run at least one search aimed at its "would be wrong if" observation and one for its strongest competitor (criticism, failure, replication, the other language).
- When sources conflict, check in this order: same thing measured (definition, unit, period); dates and versions; shared origin; method and sample; incentives; transcription or extraction errors.
- Before searching, write what would change the judgment, and look for that first.
- Stop when two rounds aimed at falsifiers and gaps leave the judgment and its confidence unchanged, and every required source type is read or recorded as unreachable. If a cap ends the run first, say so and list what is left.
- Source count, search count and report length are not measures of quality.
