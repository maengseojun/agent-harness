# Spec/Plan: Aside research method

Linear: none. Date: 2026-11-01. Single task (three skill files, one new reference file, parser change with tests). PR #83.

## Source and decisions

- The user asked to turn the Aside skills into a stronger research tool from real user cases, and agreed the method on 2026-11-01. Proposal: https://claude.ai/artifact/9jrDHXZ73hqs13PaHoJJoP (v2).
- D-1: a claim the verifier cannot open is checked against the raw Aside capture and marked `verified:capture` (user, 2026-11-01). Signal it was wrong: a `verified:capture` claim later turns out to differ from the live page in a way that changes a judgment.
- D-2: licensed material (library VPN, publisher platforms) may be downloaded by topic for the user's own research, after the user signs in. Only selected items, at most 30 per platform per day, stop at the first warning. A separate research profile is allowed; a new account to replace a limited one is not (user, 2026-11-01). Signal: a platform or the library sends a warning or limits access.
- D-3: pacing uses jitter, sequential requests per host and caps. After a block signal there is no change of identity, no simulated input and no `captcha-solver` (user accepted 2026-11-01). Signal: runs often end with `refused` on sources the user needs.
- D-4: the run ledger lives at `raw/aside/ledger/` in the vault, the one mutable file under `raw/` (delegated to Claude). Signal: resuming a run cannot find its ledger, or the ledger holds page text.

## Criteria

- **AC-1** aside-collect: an access failure is `unreachable:<kind>`, with "no material / no new content" allowed only after a full read. The FINAL template has GAP blocks and the prompt carries the fixed run rules. The IDX note has a Coverage table. A "Bulk and watch runs" section names the ledger path `raw/aside/ledger/`. The sentence "Aside does not download files." is gone and downloads go through `aside repl`.
- **AC-2** aside-research: a Mode table (quick, deep, bulk, watch), per-claim verification statuses including `verified:capture`, claim types [O]/[D]/[I]/[H] with hypothesis cards, and a "Not checked" draft section.
- **AC-3** `aside-research/references/method.md` exists and is referenced from aside-collect and aside-research. It has the sections Access diagnosis, Pacing and licensed access (user signs in, 30 per platform per day, `captcha-solver` banned), Claims and hypothesis cards, and Explore, test, stop.
- **AC-4** aside-browser is `version: 5`. It bans `captcha-solver`, bans typing credentials, names the research profile, and applies the rules to every Aside route.
- **AC-5** `parse_aside.py` returns `gaps` from GAP blocks in the FINAL region. A region with only GAP blocks is `gaps_only` and the CLI exits 0. Echoed template GAP blocks are ignored. A GAP quoted inside an item's content is never read as a gap, and content lines escaped as `\===` come back as `===`. A GAP between items keeps the item run. `work_key` merges DOI and arXiv versions, new-style and legacy ids alike.

## Verification

- AC-5: `python3 -m pytest -q` in `plugins/maeng-tools/skills/aside-collect/scripts` passes (27 tests).
- AC-1 to AC-4: the check below prints `ok` five times.

```bash
python3 -I -c "
import pathlib
s=pathlib.Path('plugins/maeng-tools/skills')
c=(s/'aside-collect/SKILL.md').read_text(); r=(s/'aside-research/SKILL.md').read_text()
m=(s/'aside-research/references/method.md').read_text(); b=(s/'aside-browser/SKILL.md').read_text()
checks={
 'AC-1':all(x in c for x in ['unreachable:<kind>','=== GAP ===','Rules for this run','Coverage','raw/aside/ledger/','aside repl']) and 'Aside does not download files' not in c,
 'AC-2':all(x in r for x in ['| quick |','| watch |','verified:capture','[O] observed','Not checked']),
 'AC-3':'references/method.md' in r and 'method.md' in c and all(x in m for x in ['## Access diagnosis','## Pacing and licensed access','## Claims and hypothesis cards','## Explore, test, stop','30 files per platform per day','captcha-solver']),
 'AC-4':'version: 5' in b and all(x in b for x in ['captcha-solver','Never type passwords','--profile','every Aside route']),
 'AC-1..4 lines':len(c.splitlines())<=150 and len(r.splitlines())<=150,
}
[print(k,'ok' if v else 'FAIL') for k,v in checks.items()]"
```
- The full root `python3 -m pytest -q` once at the end.
