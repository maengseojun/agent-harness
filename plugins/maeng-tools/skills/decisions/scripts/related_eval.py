#!/usr/bin/env python3
"""Offline eval of the related-item pick from vault wikilinks (MAE-306 / MAE-311, AC-9). Stdlib only.

build [--vault PATH] [--cases N] [--seed S] [--check]
    Writes related-v1-cases.jsonl and related-v1-labels.jsonl from the vault's wiki/ and
    hubs/ notes (never raw/, templates/ or anything eta: world eta, an eta or endix path segment, an
    imported eta Notion or Linear source). A case is a query note with at least 2 resolvable links;
    its relevant notes are the first 5 (sorted) it links to, and 10 seeded-random notes that neither
    it nor they link to are the negatives. Candidates are listed sorted by id, so order says nothing
    about the label. Text has <private> spans stripped (the vault's strip_private) and is cut to 1500
    characters. Links are [[stem]], [[stem|alias]], [[stem#heading]] or a path ending in the stem,
    resolved by exact stem when the stem is unique. Sorted keys, byte-identical for the same vault,
    cases and seed. The files hold vault text and the repository is public, so they live in the eval
    directory: env MAENG_DECISIONS_EVAL_DIR, else ~/Documents/maeng-harness/decisions/eval/ (created).
    A directory inside the repository checkout or the skill folder is refused. build, --check and run
    all use it. --check rebuilds into a temp dir, compares with the files there, prints
    `cases=<n> ko=<n> other=<n> identical=<yes|no>` and exits 1 if they differ or there are under
    20 cases. Language is ko when Hangul is over 30% of the letters of the query title and first 600
    characters, else other.

run [--out report.json] [--threshold 0.05]
    Live: one `records.related` call per case, built from the cases file only (the labels file is
    never opened while requests are built). Then score().

score(): pooled over cases. recall = relevant notes selected / relevant notes; selected share =
    selected / candidates; both overall and per language, plus the unknown count. An unknown or a
    refused item is not selected, so it counts against recall. recall_unnamed is the same over the
    relevant notes whose stem and title do not appear in the task text (the task is the query note's
    own opening, so it often names a linked note; those are the easy ones). Reported only: the floor
    for the live trial (plan AC-9) is recall >= 0.9 and selected share <= 0.5 overall.
"""
import argparse
import json
import os
import random
import re
import sys
import tempfile
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import decisions_client  # noqa: E402
import records  # noqa: E402

VAULT = "/Users/maengseojun/Documents/Obsidian Vault"
# the checkout (first ancestor with a .git), or the skill folder when installed without one
ROOT = next((p for p in HERE.parents if (p / ".git").exists()), HERE.parent)
CASES_FILE, LABELS_FILE = "related-v1-cases.jsonl", "related-v1-labels.jsonl"
TEXT_CHARS, TASK_CHARS, MAX_POSITIVES, N_NEGATIVES, MIN_CASES = 1500, 600, 5, 10, 20
PILOT = "records_eval"

def eval_dir():
    """Where the case and label files go. They hold vault text, so never inside the public repo."""
    d = Path(os.environ.get("MAENG_DECISIONS_EVAL_DIR") or "~/Documents/maeng-harness/decisions/eval").expanduser().resolve()
    if d == ROOT or ROOT in d.parents or d == HERE.parent or HERE.parent in d.parents:
        raise ValueError(f"{d} is inside the repository; the eval files hold vault text, set MAENG_DECISIONS_EVAL_DIR elsewhere")
    return d


_FM = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.S)
_ETA_FM = re.compile(r"^world:[ \t]*[\"']?eta[\"']?[ \t]*$|imported/(?:notion|linear)/(?:eta|endix)", re.I | re.M)
_TITLE_FM = re.compile(r"^title:[ \t]*(.*?)[ \t]*$", re.M)
_HEADING = re.compile(r"^# +(.+?)[ \t]*$", re.M)
_LINK = re.compile(r"\[\[([^\[\]|#\\]+)(?:#[^\[\]|]*)?(?:\\?\|[^\[\]]*)?\]\]")
_SKIP_DIRS = {"raw", "templates"}


def _nfc(s):
    return unicodedata.normalize("NFC", s)  # Korean file names can be stored decomposed, links are typed composed


def _stem(target):
    t = target.strip()
    return _nfc((t[:-3] if t.endswith(".md") else t).rsplit("/", 1)[-1])


def scan(vault):
    """-> ({id: {id, title, text, links}}, number of notes skipped as eta). id = path relative to the vault."""
    vault = Path(vault)
    notes, eta_skipped = {}, 0
    for sub in ("wiki", "hubs"):
        for p in sorted((vault / sub).rglob("*.md")):
            rel = _nfc(p.relative_to(vault).as_posix())
            if any(seg.casefold() in _SKIP_DIRS for seg in rel.split("/")[:-1]):
                continue
            raw = p.read_text(encoding="utf-8", errors="replace")
            m = _FM.match(raw)
            fm, body = (m.group(1), raw[m.end():]) if m else ("", raw)
            if records.is_eta_path(rel) or _ETA_FM.search(fm):
                eta_skipped += 1
                continue
            body = records.strip_private(body)[0]
            t = _TITLE_FM.search(fm)
            h = _HEADING.search(body)
            title = records.strip_private((t and t.group(1).strip("\"'")) or (h and h.group(1)) or Path(rel).stem)[0]
            notes[rel] = {"id": rel, "title": title, "text": body.strip()[:TEXT_CHARS],
                          "stems": [_stem(x) for x in _LINK.findall(body)]}
    by_stem = {}
    for i in notes:
        by_stem.setdefault(Path(i).stem, []).append(i)
    unique = {s: v[0] for s, v in by_stem.items() if len(v) == 1}  # ambiguous and unresolved links are dropped
    for n in notes.values():
        n["links"] = {unique[s] for s in n.pop("stems") if s in unique} - {n["id"]}
    return notes, eta_skipped


def language(s):
    letters = [c for c in s if c.isalpha()]
    ko = sum("가" <= c <= "힣" or "ᄀ" <= c <= "ᇿ" or "㄰" <= c <= "㆏" for c in letters)
    return "ko" if letters and ko / len(letters) > 0.3 else "other"


def make_cases(notes, n=40, seed=0):
    """-> (cases, labels), both sorted by case id."""
    eligible = sorted(i for i, x in notes.items() if len(x["links"]) >= 2)
    picked = sorted(random.Random(seed).sample(eligible, min(n, len(eligible))))
    linked_from = {}
    for i, x in notes.items():
        for t in x["links"]:
            linked_from.setdefault(t, set()).add(i)
    ids, cases, labels = sorted(notes), [], []
    for q in picked:
        pos = sorted(notes[q]["links"])[:MAX_POSITIVES]
        excluded = {q} | notes[q]["links"] | linked_from.get(q, set())
        pool = [i for i in ids if i not in excluded]
        neg = random.Random(f"{seed}:{q}").sample(pool, min(N_NEGATIVES, len(pool)))
        head = f"{notes[q]['title']}\n{notes[q]['text'][:TASK_CHARS]}"
        cases.append({"id": q, "task": f"Continue the work in this note: {head}", "lang": language(head),
                      "candidates": [{"id": i, "title": notes[i]["title"], "text": notes[i]["text"], "source": "obsidian", "path": i}
                                     for i in sorted(pos + neg)]})
        labels.append({"id": q, "relevant": pos})
    return cases, labels


def _dump(rows):
    return "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in rows)


def build(vault, out_dir, n=40, seed=0):
    notes, eta_skipped = scan(vault)
    cases, labels = make_cases(notes, n, seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    texts = {CASES_FILE: _dump(cases), LABELS_FILE: _dump(labels)}
    for name, text in texts.items():
        (out / name).write_text(text, encoding="utf-8")
    ko = sum(c["lang"] == "ko" for c in cases)
    return {"cases": len(cases), "ko": ko, "other": len(cases) - ko, "notes": len(notes), "eta_skipped": eta_skipped,
            "chars": sum(len(t) for t in texts.values()), "bytes": sum(len(t.encode("utf-8")) for t in texts.values())}


def check(vault, against, n=40, seed=0):
    with tempfile.TemporaryDirectory() as d:
        s = build(vault, d, n, seed)
        same = all((against / f).is_file() and (Path(d) / f).read_bytes() == (against / f).read_bytes()
                   for f in (CASES_FILE, LABELS_FILE))
    print(f"cases={s['cases']} ko={s['ko']} other={s['other']} identical={'yes' if same else 'no'}")
    return 0 if same and s["cases"] >= MIN_CASES else 1


def _read(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def named_ids(task, candidates):
    """Ids of the candidates whose stem or title appears in the task text. Needs no label."""
    return [c["id"] for c in candidates if any(t and t in task for t in (Path(c["id"]).stem, c.get("title")))]


def run(cases_path=None, *, decide=None, threshold=records.RELATED_THRESHOLD):
    """Builds every request from the cases file only; keeps just id, task, lang and the candidate fields
    (so a stray label field cannot reach a request). Own ledger (a temp file via MAENG_DECISIONS_LEDGER,
    restored afterwards), copied to the main ledger once the run is over. -> {results, usage}"""
    fields = ("id", "title", "text", "source", "path")
    cases = [{"id": c["id"], "task": c["task"], "lang": c["lang"],
              "candidates": [{k: x.get(k) for k in fields} for x in c["candidates"]]}
             for c in _read(cases_path or eval_dir() / CASES_FILE)]
    old = os.environ.get("MAENG_DECISIONS_LEDGER")
    results = []
    with tempfile.TemporaryDirectory() as d:
        ledger = Path(d) / "ledger.jsonl"
        os.environ["MAENG_DECISIONS_LEDGER"] = str(ledger)
        try:
            for c in cases:
                r = records.related(c["task"], c["candidates"], threshold, decide=decide, pilot=PILOT)
                results.append({"id": c["id"], "lang": c["lang"], "candidates": [x["id"] for x in c["candidates"]],
                                "named": named_ids(c["task"], c["candidates"]),
                                "selected": [i["id"] for i, _ in r["selected"]], "unknown": r["unknown"],
                                "dropped": [i for i, _ in r["dropped"]]})
        finally:
            if old is None:
                os.environ.pop("MAENG_DECISIONS_LEDGER", None)
            else:
                os.environ["MAENG_DECISIONS_LEDGER"] = old
        lines = [json.loads(ln) for ln in ledger.read_text(encoding="utf-8").splitlines()] if ledger.exists() else []
    for r in lines:  # eval spend also counts in the trial report's overhead
        decisions_client._log(r)
    usage = {"input_tokens": sum(r["input_tokens"] for r in lines), "cached_tokens": sum(r["cached_tokens"] for r in lines),
             "cost_usd": round(sum(r["cost_usd"] for r in lines), 8)}
    return {"results": results, "usage": usage}


def score(results, labels_path, usage=None):
    if isinstance(results, dict):
        usage, results = results.get("usage", usage), results["results"]
    usage = usage or {}
    labels = {r["id"]: set(r["relevant"]) for r in _read(labels_path)}
    if {r["id"] for r in results} != set(labels):
        raise ValueError("results and labels cover different case ids")

    def tally(rs):
        rel, found = sum(len(labels[r["id"]]) for r in rs), sum(len(labels[r["id"]] & set(r["selected"])) for r in rs)
        unnamed = {r["id"]: labels[r["id"]] - set(r["named"]) for r in rs}
        rel_u, found_u = sum(len(v) for v in unnamed.values()), sum(len(unnamed[r["id"]] & set(r["selected"])) for r in rs)
        cand, sel = sum(len(r["candidates"]) for r in rs), sum(len(r["selected"]) for r in rs)
        return {"cases": len(rs), "relevant": rel, "found": found, "recall": found / rel if rel else None,
                "relevant_unnamed": rel_u, "found_unnamed": found_u, "recall_unnamed": found_u / rel_u if rel_u else None,
                "candidates": cand, "selected": sel, "selected_share": sel / cand if cand else None,
                "unknown": sum(len(r["unknown"]) for r in rs)}
    rep = tally(results)
    floors = {"recall": rep["recall"] is not None and rep["recall"] >= 0.9,
              "selected_share": rep["selected_share"] is not None and rep["selected_share"] <= 0.5}
    rep.update({
        "by_lang": {lang: tally([r for r in results if r["lang"] == lang]) for lang in ("ko", "other")},
        "missed": {r["id"]: sorted(labels[r["id"]] - set(r["selected"])) for r in results if labels[r["id"]] - set(r["selected"])},
        "input_tokens": usage.get("input_tokens", 0), "cached_tokens": usage.get("cached_tokens", 0),
        "cost_usd": usage.get("cost_usd", 0.0), "floors": floors, "pass": all(floors.values())})
    return rep


def _f(x):
    return "n/a" if x is None else f"{x:.3f}"


def summary(rep):
    ok = lambda b: "ok" if b else "FAIL"
    row = lambda name, t: (f"| {name} | {t['cases']} | {t['found']}/{t['relevant']} = {_f(t['recall'])} | "
                           f"{t['found_unnamed']}/{t['relevant_unnamed']} = {_f(t['recall_unnamed'])} | "
                           f"{t['selected']}/{t['candidates']} = {_f(t['selected_share'])} | {t['unknown']} |")
    return "\n".join([
        f"# Related-pick eval: {'PASS' if rep['pass'] else 'FAIL'}",
        f"floor: recall >= 0.9 ({ok(rep['floors']['recall'])}) and selected share <= 0.5 ({ok(rep['floors']['selected_share'])}), overall",
        "",
        "| group | cases | recall | recall, unnamed | selected share | unknown |",
        "|---|---|---|---|---|---|",
        row("overall", rep), row("ko", rep["by_lang"]["ko"]), row("other", rep["by_lang"]["other"]),
        "",
        f"tokens in {rep['input_tokens']} (cached {rep['cached_tokens']}), cost ${rep['cost_usd']:.4f}",
        f"cases with a missed relevant note: {len(rep['missed'])}",
    ])


def main(argv=None):
    ap = argparse.ArgumentParser(prog="related_eval.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("build", help="write the eval files from the vault")
    p.add_argument("--vault", default=VAULT)
    p.add_argument("--cases", type=int, default=40)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--check", action="store_true", help="rebuild into a temp dir and compare with eval/")
    p = sub.add_parser("run", help="run the eval live and score it")
    p.add_argument("--out", help="write the JSON report here")
    p.add_argument("--threshold", type=float, default=records.RELATED_THRESHOLD)
    a = ap.parse_args(argv)
    try:
        out = eval_dir()
    except ValueError as e:
        ap.error(str(e))
    if a.cmd == "build":
        if a.cases < 1:
            ap.error("--cases must be >= 1")
        if a.check:
            return check(a.vault, out, a.cases, a.seed)
        s = build(a.vault, out, a.cases, a.seed)
        print(f"notes={s['notes']} eta_skipped={s['eta_skipped']}")
        print(f"cases={s['cases']} ko={s['ko']} other={s['other']}")
        print(f"wrote {CASES_FILE} and {LABELS_FILE} to {out}: {s['chars']} characters ({s['bytes']} bytes)")
        return 0
    if not 0 <= a.threshold <= 1:
        ap.error("--threshold must be between 0 and 1")
    rep = score(run(threshold=a.threshold), out / LABELS_FILE)
    if a.out:
        Path(a.out).write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(summary(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
