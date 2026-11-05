#!/usr/bin/env python3
"""Decisions steps of a research run, with Aside as the reader of pages Python cannot open (MAE-322). Stdlib only.

  aside_step.py triage --run ID --scope TEXT --candidates FILE
      Which search results are worth opening. FILE is the records.py candidates list. An item
      Decisions could not judge stays in `open`. Writes triage.json.
  aside_step.py claims --run ID --claims FILE [--seed N]
      Verify claims. Each page is read by a Python request, then by `aside repl` (the user's
      logged-in browser, no model) when that gave no readable page, then from the source note.
      A page only the user can open goes to needs-login.json, and its claims stay `unknown`. Run the
      same command again after the user signs in: pages already read are kept. Writes claims.json,
      the file `maeng-review --claims` takes, with the verify_claims.py fields plus `gaps`.
  aside_step.py check --run ID
      Lists what the run has and what is missing. Exit 1 when claims.json is missing.

Run folders are under MAENG_DECISIONS_RUNS (default ~/Documents/maeng-harness/decisions/runs), and
pages/ there holds logged-in page text: it stays local. Only the page's main content is read.
Pilot names: aside_triage, aside_access, claim_verification. When Decisions gives no answer on
access, a page with enough text counts as readable, so a dead API never stops a run.
"""
import argparse
import concurrent.futures
import functools
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import decisions_client  # noqa: E402
import records  # noqa: E402
import verify_claims as vc  # noqa: E402

DECIDE = functools.partial(decisions_client.decide, redact_by_name=False)  # tests replace this
KINDS = (
    ("readable", "The article, document or feed itself is there, with content beyond navigation and forms."),
    ("login_required", "The page is mainly a sign-in form or an account wall: username, password, log in, create account."),
    ("paywalled", "Only a preview, with a subscribe or purchase offer."),
    ("refused", "A CAPTCHA, a bot check or an access-denied page."),
    ("gone", "A not-found message."),
    ("js_empty", "A shell with no content, such as a loading message."),
)
ACCESS_CHOICES = [{"value": v, "description": d} for v, d in KINDS]
NEEDS_USER = ("login_required", "paywalled", "refused")
HEAD_CHARS, ACCESS_BATCH, LIVE_WORKERS = 2500, 40, 6  # a wall shows in the first lines of a page


def judge_access(pages):
    """{key: text} -> {key: kind}. A page Decisions gave no answer on is left out."""
    keys, out = list(pages), {}
    for i in range(0, len(keys), ACCESS_BATCH):
        names = {f"p{n}": k for n, k in enumerate(keys[i:i + ACCESS_BATCH])}
        # no URL here: the same wall was judged readable when its address ended in /login
        text = "\n\n".join(f"=== [{n}] ===\n{pages[k][:HEAD_CHARS]}" for n, k in names.items())
        questions = [{"type": "choice", "name": n, "choices": ACCESS_CHOICES,
                      "instructions": f"Judge only the text under [{n}] above. What did the reader get?"} for n in names]
        for a in DECIDE(text, questions, "aside_access"):
            if a.get("status") == "ok" and a.get("name") in names and a.get("choice") in dict(KINDS):
                out[names[a["name"]]] = a["choice"]
    return out


def aside_read(url):
    """The main text of a page in the user's Aside browser, or "" on any failure. The marker is random, so page
    text cannot forge the end of the output."""
    if urlparse(url).scheme not in ("http", "https"):
        return ""
    tag = secrets.token_hex(8)
    code = (f"await openTab({json.dumps(url)});"
            "try { await page.waitForLoadState('networkidle', {timeout: 6000}); } catch (e) {}"
            "const asideText = await page.evaluate(() => "
            "document.querySelector('main,article,[role=main]')?.innerText || document.body.innerText);"
            f"console.log('<<<{tag}'); console.log(asideText); console.log('{tag}>>>'); await closeTab(page);")
    try:
        out = subprocess.run(["aside", "repl", code], capture_output=True, text=True, timeout=90,
                             stdin=subprocess.DEVNULL).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    m = re.search(f"<<<{tag}\n(.*)\n{tag}>>>", out, re.S)
    return m[1] if m else ""


def run_dir(run):
    if not re.fullmatch(r"[\w.-]+", run):
        raise SystemExit(f"bad run id: {run}")
    d = Path(os.environ.get("MAENG_DECISIONS_RUNS") or "~/Documents/maeng-harness/decisions/runs").expanduser() / run
    (d / "pages").mkdir(parents=True, exist_ok=True, mode=0o700)
    return d


def _page_file(d, url):
    return d / "pages" / f"{hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]}.txt"


def read_pages(d, claims):
    """-> ({url: (text, source)}, {url: kind for a page nobody could read})."""
    notes = {}
    for c in claims:
        notes[c["url"]] = notes.get(c["url"]) or c.get("note")
    pages, gaps = {}, {}
    for url in notes:
        if _page_file(d, url).is_file():
            pages[url] = (_page_file(d, url).read_text(encoding="utf-8"), "aside")
    todo = [u for u in notes if u not in pages]
    with concurrent.futures.ThreadPoolExecutor(LIVE_WORKERS) as pool:
        live = dict(zip(todo, pool.map(vc._live, todo)))
    kinds = judge_access({u: t for u, t in live.items() if len(t) >= vc.MIN_LIVE_CHARS})
    rest = []
    for u in todo:
        if len(live[u]) >= vc.MIN_LIVE_CHARS and kinds.get(u, "readable") == "readable":
            pages[u] = (live[u][:vc.MAX_CHARS], "live")
        else:
            rest.append(u)
    texts = {u: aside_read(u) for u in rest}  # one at a time: these are the user's own sessions
    kinds = judge_access({u: t for u, t in texts.items() if t.strip()})
    for u in rest:
        text = texts[u][:vc.MAX_CHARS]
        kind = kinds.get(u, "readable") if text.strip() else "aside_failed"
        if kind == "readable":
            _page_file(d, u).write_text(text, encoding="utf-8")
            pages[u] = (text, "aside")
            continue
        note = vc._note_body(notes[u])
        pages[u] = (note[:vc.MAX_CHARS], "note") if note else ("", "none")
        if not note:
            gaps[u] = kind
    return pages, gaps


def cmd_claims(a, d):
    claims = json.loads(Path(a.claims).read_text(encoding="utf-8"))
    pages, gaps = read_pages(d, claims)
    results = vc.verify(claims, decide=DECIDE, pages=pages)
    for r in results:
        if r["url"] in gaps:
            r["reason"] = gaps[r["url"]]
    needs = [{"url": u, "kind": k, "claims": [c["id"] for c in claims if c["url"] == u]}
             for u, k in gaps.items() if k in NEEDS_USER]
    doc = {"results": results, "route": vc.route(results, seed=a.seed), "gaps": gaps}
    (d / "claims.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (d / "needs-login.json").write_text(json.dumps(needs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sources = [r["page_source"] for r in results]
    print(f"{len(results)} claims: " + ", ".join(f"{s} {sources.count(s)}" for s in sorted(set(sources))))
    print(f"route to the re-check: {len(doc['route'])}; other gaps: {len(gaps) - len(needs)}")
    print(f"needs the user: {len(needs)} page(s), listed in {d / 'needs-login.json'}" if needs else "needs the user: none")
    print(d / "claims.json")


def cmd_triage(a, d):
    cands = records.load_candidates(a.candidates)
    r = records.related(a.scope, cands, pilot="aside_triage")
    chosen = {i["id"] for i, _ in r["selected"]} | {str(u) for u in r["unknown"]}
    ids = [str(c.get("id")) for c in cands]
    doc = {"open": [i for i in ids if i in chosen], "skip": [i for i in ids if i not in chosen]}
    (d / "triage.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"open {len(doc['open'])} of {len(ids)}: {d / 'triage.json'}")


def cmd_check(a, d):
    have = {n: (d / f"{n}.json").is_file() for n in ("triage", "claims")}
    print("\n".join(f"{n}: {'present' if v else 'missing'}" for n, v in have.items()))
    if (d / "needs-login.json").is_file():
        needs = json.loads((d / "needs-login.json").read_text(encoding="utf-8"))
        print("\n".join(f"needs the user: {n['url']} ({n['kind']})" for n in needs) or "needs the user: none")
    return 0 if have["claims"] else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Decisions steps of a research run.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("triage")
    t.add_argument("--scope", required=True)
    t.add_argument("--candidates", required=True)
    c = sub.add_parser("claims")
    c.add_argument("--claims", required=True)
    c.add_argument("--seed", type=int, default=0)
    k = sub.add_parser("check")
    for p in (t, c, k):
        p.add_argument("--run", required=True)
    a = ap.parse_args(argv)
    return {"triage": cmd_triage, "claims": cmd_claims, "check": cmd_check}[a.cmd](a, run_dir(a.run)) or 0


if __name__ == "__main__":
    sys.exit(main())
