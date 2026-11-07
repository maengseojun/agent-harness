#!/usr/bin/env python3
"""Claim verification against page text with the Decisions API (MAE-306, AC-2). Stdlib only.

fetch_page(url, note) -> (text, source): the page text, cached under
MAENG_DECISIONS_PAGES (default ~/Documents/maeng-harness/decisions/pages) as
<sha256(url)>.txt plus .json (url, fetched_at, source, truncated). source is "live"
(urllib; GitHub repo/blob/release and PyPI through their raw/API forms, other HTML
through a stdlib HTML-to-text), "note" (the vault note body, when the fetch fails or
gives under 500 characters) or "none" (neither worked; text ""). A note fallback is
cached too, so a rerun is offline and identical; pass refresh=True to retry live.
No model ever summarizes a page.

verify(claims) -> one result per claim, in input order: {id, url, verdict,
probabilities, confidence, page_source, latency_ms}. One decide call per page (400
questions per call at most). verdict is supported | contradicted | not_in_page, or
"unknown" for any refusal, error, missing or off-list answer and for a page with
source "none" (no request is sent for it). latency_ms is per page. pages={url: (text, source)}
replaces fetch_page for those URLs (aside_step.py reads them).

route(results) -> ids for the researcher re-check (plan A-4).

CLI: python3 verify_claims.py claims.json [--seed N] [--out path]
"""
import argparse
import hashlib
import functools
import importlib.util
import ipaddress
import json
import math
import os
import random
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

sys.path.append(str(Path(__file__).resolve().parent.parent.parent / "obsidian-workspace" / "scripts"))
import decisions_client  # noqa: E402
from private_filter import strip_private  # noqa: E402

def route_model(name, script=None):
    """Model of the roles.json route `name`, resolved by maeng-harness's routing.py, which is found relative to this
    script: <plugins>/maeng-harness in a checkout, <cache>/maeng-harness/<newest version> beside this plugin's
    version folder in an installation. No default model: a missing table or row raises before any request."""
    here = Path(script or __file__).resolve()
    newest = sorted(here.parents[5].glob("maeng-harness/*"), reverse=True,
                    key=lambda p: [int(n) for n in re.findall(r"\d+", p.name)])
    root = next((p for p in [here.parents[4] / "maeng-harness", *newest] if (p / "policy" / "roles.json").is_file()), None)
    if root is None:
        raise FileNotFoundError(f"maeng-harness/policy/roles.json not found from {here}")
    spec = importlib.util.spec_from_file_location("maeng_routing", root / "lib" / "maeng" / "routing.py")
    routing = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(routing)
    return routing.resolve(routing.load(root / "policy" / "roles.json"), name)["model"]


MAX_CHARS = 400_000
MAX_BYTES = 8_000_000
MIN_LIVE_CHARS = 500
VERDICTS = ("supported", "contradicted", "not_in_page")
CHOICES = [
    {"value": "supported", "description": "The page states this claim, with the same numbers, names, dates and qualifiers."},
    {"value": "contradicted", "description": "The page states something that conflicts with the claim, such as a different number or the opposite statement."},
    {"value": "not_in_page", "description": "The page does not state the claim, or states only part of it."},
]
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"


class _Text(HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer", "svg", "noscript"}
    BLOCK = {"p", "div", "br", "li", "ul", "ol", "tr", "table", "section", "article", "main", "pre",
             "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in ("td", "th"):
            self.out.append(" | ")
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(self.skip - 1, 0)
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def _html_text(html):
    p = _Text()
    p.feed(html)
    p.close()
    lines = (re.sub(r"[ \t\r\f\v\xa0]+", " ", ln).strip() for ln in "".join(p.out).split("\n"))
    return "\n".join(ln for ln in lines if ln)


def _route(url):
    """-> (url to GET, kind: raw | release | pypi | html)."""
    u = urlparse(url)
    host, parts = u.netloc.lower().removeprefix("www."), [p for p in u.path.split("/") if p]
    if host == "github.com" and len(parts) >= 2:
        o, r = parts[:2]
        if len(parts) == 2:
            return f"https://raw.githubusercontent.com/{o}/{r}/HEAD/README.md", "raw"
        if parts[2] == "blob" and len(parts) >= 5:
            return f"https://raw.githubusercontent.com/{o}/{r}/{parts[3]}/{'/'.join(parts[4:])}", "raw"
        if parts[2:4] == ["releases", "tag"] and len(parts) >= 5:
            return f"https://api.github.com/repos/{o}/{r}/releases/tags/{parts[4]}", "release"
    if host == "pypi.org" and len(parts) >= 2 and parts[0] == "project":
        return f"https://pypi.org/pypi/{parts[1]}/json", "pypi"
    return url, "html"


def _public(url):
    """True only for an http(s) URL whose host resolves to public addresses alone (no loopback,
    private, link-local, metadata or reserved ranges), so page text sent on is public text."""
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        return False
    try:
        infos = socket.getaddrinfo(u.hostname, u.port or (443 if u.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
        return bool(infos) and all(ipaddress.ip_address(i[4][0].split("%")[0]).is_global for i in infos)
    except (OSError, ValueError):
        return False


class _PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _public(newurl):
            raise urllib.error.URLError(f"redirect to a non-public address: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_PublicRedirect)


def _get(url):
    # shortcut: the address is checked by DNS before connecting, not pinned for the connection itself
    # (DNS rebinding); pin the resolved IP if claim files ever come from untrusted sources.
    if not _public(url):
        raise ValueError(f"not a public http(s) address: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"})
    with _OPENER.open(req, timeout=20) as r:
        return r.read(MAX_BYTES).decode(r.headers.get_content_charset() or "utf-8", "replace")


def _live(url):
    """Page text from the network, or "" on any failure."""
    target, kind = _route(url)
    try:
        body = _get(target)
        if kind == "html":
            return _html_text(body)
        if kind == "raw":
            return body
        j = json.loads(body)
        if kind == "release":
            return "\n".join(str(j[k]) for k in ("name", "published_at", "body") if j.get(k))
        return str((j.get("info") or {}).get("description") or "")
    except Exception:  # network, decode and JSON errors all mean "no live text"
        return ""


def _note_body(note):
    """The vault note without its YAML frontmatter and <private> spans, or "". Stays inside the vault."""
    if not note:
        return ""
    vault = Path(os.environ.get("MAENG_VAULT") or "~/Documents/Obsidian Vault").expanduser().resolve()
    path = (vault / note).resolve()
    if vault not in path.parents:
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return ""
    return strip_private(re.sub(r"\A---[ \t]*\n.*?\n---[ \t]*(?:\n|\Z)", "", text, count=1, flags=re.S))[0].strip()


def fetch_page(url, note=None, refresh=False):
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    d = Path(os.environ.get("MAENG_DECISIONS_PAGES") or "~/Documents/maeng-harness/decisions/pages").expanduser()
    txt, meta = d / f"{key}.txt", d / f"{key}.json"
    if not refresh:
        try:
            return txt.read_text(encoding="utf-8"), json.loads(meta.read_text(encoding="utf-8"))["source"]
        except (OSError, ValueError, KeyError):
            pass
    text, source = _live(url), "live"
    if len(text) < MIN_LIVE_CHARS:
        text, source = _note_body(note), "note"
    if not text:
        return "", "none"
    truncated, text = len(text) > MAX_CHARS, text[:MAX_CHARS]
    try:
        d.mkdir(parents=True, exist_ok=True)
        txt.write_text(text, encoding="utf-8")
        meta.write_text(json.dumps({"url": url, "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                    "source": source, "truncated": truncated}), encoding="utf-8")
    except (OSError, ValueError) as e:  # the text still goes back; the next run fetches again
        print(f"decisions: page cache write failed: {getattr(e, 'strerror', None) or e}", file=sys.stderr)
    return text, source


def _question(c):
    return {"type": "choice", "name": c["id"], "choices": CHOICES,
            "instructions": f"Claim: {c['claim']}\nJudge the claim only against the page text above."}


def verify(claims, *, pilot="claim_verification", decide=None, pages=None):
    decide = decide or functools.partial(decisions_client.decide, redact_by_name=False,
                                         model=route_model("claim_check"))  # not MAENG_DECISIONS_MODEL
    ids = [c["id"] for c in claims]
    if len(set(ids)) != len(ids):
        raise ValueError("claim ids must be unique")
    groups = {}
    for c in claims:
        groups.setdefault(c["url"], []).append(c)
    by_id = {}
    for url, group in groups.items():
        text, source = (pages or {}).get(url) or fetch_page(url, next((c["note"] for c in group if c.get("note")), None))
        answers, ms = {}, 0
        if source != "none":
            for i in range(0, len(group), 400):
                t0 = time.monotonic()
                got = decide(f"Source page ({url}):\n\n{text}", [_question(c) for c in group[i:i + 400]], pilot)
                ms += int((time.monotonic() - t0) * 1000)
                answers.update({a.get("name"): a for a in got})
        for c in group:
            a = answers.get(c["id"]) or {}
            ok = a.get("status") == "ok" and a.get("choice") in VERDICTS
            by_id[c["id"]] = {
                "id": c["id"], "url": url, "verdict": a["choice"] if ok else "unknown",
                "probabilities": a.get("probabilities") if ok else None,
                "confidence": a.get("confidence") if ok else None,
                "page_source": source, "latency_ms": ms, "reason": a.get("reason"),
            }
    return [by_id[i] for i in ids]


def route(results, *, rate=0.2, min_sample=3, seed=0):
    """Ids for the researcher: every verdict other than supported, then a seeded
    sample of the supported ones, max(min_sample, ceil(rate * n)) capped at n."""
    flagged = [r["id"] for r in results if r["verdict"] != "supported"]
    supported = sorted(r["id"] for r in results if r["verdict"] == "supported")
    k = min(len(supported), max(min_sample, math.ceil(round(rate * len(supported), 9))))
    return flagged + sorted(random.Random(seed).sample(supported, k))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Verify claims against their pages with the Decisions API.")
    ap.add_argument("claims", help="JSON list of {id, claim, url, note?}")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    claims = json.loads(Path(a.claims).read_text(encoding="utf-8"))
    results = verify(claims)
    doc = json.dumps({"results": results, "route": route(results, seed=a.seed)}, ensure_ascii=False, indent=2)
    if a.out:
        Path(a.out).write_text(doc + "\n", encoding="utf-8")
    else:
        print(doc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
