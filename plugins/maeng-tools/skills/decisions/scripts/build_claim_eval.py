#!/usr/bin/env python3
"""Build the claim-verification eval set (MAE-306, AC-3). Stdlib only.

Reads eval/seed-v1.jsonl (id, claim, url, note, label, source) and the cached pages
(verify_claims.fetch_page fetches the missing ones). Writes
  eval/claims-v1.jsonl   id, claim, url, note              (no label)
  eval/labels-v1.jsonl   id, label, kind (seed|mutation), parent (mutations only)
both sorted by id, one JSON object per line with sorted keys.

Mutated negatives come from `supported` seeds only. A number token in the claim (integer,
decimal, percentage, money, version, size, ISO or "Month D, YYYY" date) gets a changed
value by a fixed rule (last digit +3, then +7 mod 10; dates +3, then +10 days). A mutation is
kept only if the claim text changed and the new value, normalized (lower case, commas
removed, whitespace collapsed), appears nowhere in the page's normalized text; for dates
every common rendering of the new date is checked. At most 2 per seed, from different
tokens first. A seed whose page is unavailable (source none) gets no mutation, since the
absence cannot be shown. Mutations are labelled `contradicted`, id m<parent>-<k>.

--check rebuilds into a temporary directory and compares byte for byte with the files in
the eval directory; it prints `positives=<n> negatives=<n> identical=<yes|no>` and exits 1
if either count is under 100 or the files differ. The rebuild reads the page cache, so it
is identical only while the cache holds the same pages.
"""
import argparse
import json
import re
import sys
import tempfile
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import verify_claims as vc

_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"]
_LONG = "(?:" + "|".join(_MONTHS + [m[:3] for m in _MONTHS]) + r")\.? \d{1,2}, \d{4}"
_TOKEN = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2}|" + _LONG + r")|(?<![\d.,])\$?\d+(?:,\d{3})*(?:\.\d+)*[%kKmM]?")
FILES = ("claims-v1.jsonl", "labels-v1.jsonl")


def _norm(s):
    return re.sub(r"\s+", " ", s.lower().replace(",", "")).strip()


def _date_variants(tok):
    iso = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", tok)
    try:
        if iso:
            d0 = date(*map(int, iso.groups()))
        else:
            name, day, year = re.fullmatch(r"([A-Za-z]+)\.? (\d{1,2}), (\d{4})", tok).groups()
            d0 = date(int(year), [m[:3].lower() for m in _MONTHS].index(name[:3].lower()) + 1, int(day))
    except ValueError:  # an impossible date makes no mutation
        return []
    first = tok.split()[0] if not iso else ""
    out = []
    for days in (3, 10):
        d = d0 + timedelta(days)
        full, abbr = _MONTHS[d.month - 1], _MONTHS[d.month - 1][:3]
        month = full if len(first.rstrip(".")) > 3 or first == "May" else abbr + ("." if first.endswith(".") else "")
        new = d.isoformat() if iso else f"{month} {d.day}, {d.year}"
        months = (full, abbr, abbr + ".") + (("Sept", "Sept.") if d.month == 9 else ())
        forms = [f"{m} {d.day}, {d.year}" for m in months] + [f"{d.day} {m} {d.year}" for m in months]
        numeric = [f"{d.month}/{d.day}/{d.year}", f"{d.year}年{d.month}月{d.day}日", f"{d.year}년 {d.month}월 {d.day}일"]
        out.append((new, [new, d.isoformat()] + forms + numeric))
    return out


def _variants(tok, is_date):
    """-> [(changed token, forms that must be absent from the page)]."""
    if is_date:
        return _date_variants(tok)
    i = max(j for j, c in enumerate(tok) if c.isdigit())
    news = [tok[:i] + str((int(tok[i]) + k) % 10) + tok[i + 1:] for k in (3, 7)]
    return [(n, [n]) for n in news]


def mutations(claim, page_norm, limit=2):
    """Up to `limit` changed claims whose new value is absent from the page."""
    per_token = []
    for m in _TOKEN.finditer(claim):
        ok = []
        for new, forms in _variants(m.group(), m.group("date") is not None):
            mutated = claim[:m.start()] + new + claim[m.end():]
            if mutated != claim and not any(_norm(f) in page_norm for f in forms):
                ok.append(mutated)
        per_token.append(ok)
    first = [ok[0] for ok in per_token if ok][:limit]
    return (first + [x for ok in per_token for x in ok[1:]])[:limit]


def _dump(rows):
    return "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in sorted(rows, key=lambda r: r["id"]))


def build(seed_path, out_dir):
    """Write the two eval files into out_dir; -> Counter of page sources by page."""
    seeds = [json.loads(ln) for ln in Path(seed_path).read_text(encoding="utf-8").splitlines() if ln.strip()]
    pages, claims, labels = {}, [], []
    for s in seeds:
        if s["url"] not in pages:
            text, source = vc.fetch_page(s["url"], s["note"])
            pages[s["url"]] = (_norm(text), source)
        claims.append({k: s[k] for k in ("id", "claim", "url", "note")})
        labels.append({"id": s["id"], "label": s["label"], "kind": "seed"})
        norm, source = pages[s["url"]]
        if s["label"] != "supported" or source == "none":
            continue
        for k, mc in enumerate(mutations(s["claim"], norm), 1):
            mid = f"m{s['id']}-{k}"
            claims.append({"id": mid, "claim": mc, "url": s["url"], "note": s["note"]})
            labels.append({"id": mid, "label": "contradicted", "kind": "mutation", "parent": s["id"]})
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / FILES[0]).write_text(_dump(claims), encoding="utf-8")
    (out / FILES[1]).write_text(_dump(labels), encoding="utf-8")
    return Counter(src for _, src in pages.values())


def check(eval_dir):
    d = Path(eval_dir)
    with tempfile.TemporaryDirectory() as t:
        build(d / "seed-v1.jsonl", t)
        same = all((d / f).is_file() and (d / f).read_bytes() == (Path(t) / f).read_bytes() for f in FILES)
        labels = [json.loads(ln) for ln in (Path(t) / FILES[1]).read_text(encoding="utf-8").splitlines()]
    pos = sum(r["label"] == "supported" for r in labels)
    neg = len(labels) - pos
    print(f"positives={pos} negatives={neg} identical={'yes' if same else 'no'}")
    return 0 if pos >= 100 and neg >= 100 and same else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build the claim eval set from eval/seed-v1.jsonl.")
    ap.add_argument("--dir", default=str(Path(__file__).resolve().parent.parent / "eval"),
                    help="eval directory holding seed-v1.jsonl (default: ../eval)")
    ap.add_argument("--check", action="store_true", help="rebuild to a temp dir and compare with the committed files")
    a = ap.parse_args(argv)
    if a.check:
        return check(a.dir)
    sources = build(Path(a.dir) / "seed-v1.jsonl", a.dir)
    print(f"pages live={sources['live']} note={sources['note']} none={sources['none']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
