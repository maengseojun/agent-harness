#!/usr/bin/env python3
"""Run claim verification on the eval set and score it against the A-2 floors (MAE-306, AC-3). Stdlib only.

run(claims_path)   builds requests from the claims file ONLY and never opens the labels
                   file; keeps just id, claim, url and note of each row, so a stray label
                   field cannot reach a request. Claim ids encode the kind of claim (p, n, mp),
                   so requests carry neutral names in a seeded order, and a claim never shares
                   a request with its own mutation. The run writes its own ledger (a temp
                   file via MAENG_DECISIONS_LEDGER, restored afterwards) whose token and
                   cost totals go into the returned usage. -> {results, route, usage}
score(results, labels_path)  results is the run() dict or its results list.
                   positives = label supported, negatives = every other label.
                   negative_recall = share of negatives not judged supported (unknown counts
                   as caught: it goes to the researcher). over_flag = share of positives not
                   judged supported. Wilson 95% intervals. A run with an unknown negative cannot pass: an
                   outage on the rounds that hold the mutations would otherwise count as caught. Latency is per request group of a page
                   (pages with a request only), nearest-rank percentiles. Pass = negative_recall >= 0.95 and
                   its Wilson lower bound >= 0.90 and over_flag <= 0.30 and p50 < 2000 ms.

CLI: python3 eval_claims.py [--claims ...] [--labels ...] [--out report.json]
"""
import argparse
import json
import math
import os
import random
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

import verify_claims as vc

EVAL = Path(__file__).resolve().parent.parent / "eval"
Z = 1.96


def _read(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def _blind(claims, seed):
    """-> ([claims under neutral names, one list per round], {neutral name: real id}). A mutated id ends in -1 or
    -2, so each mutation level gets its own round, apart from the claim it was made from."""
    shuffled = list(claims)
    random.Random(seed).shuffle(shuffled)
    rounds, real = {}, {}
    for n, c in enumerate(shuffled):
        real[f"q{n}"] = c["id"]
        level = re.fullmatch(r"m.*-(\d+)", c["id"])
        rounds.setdefault(int(level.group(1)) if level else 0, []).append(dict(c, id=f"q{n}"))
    return [rounds[k] for k in sorted(rounds)], real


def run(claims_path, *, decide=None, seed=0):
    claims = [{k: c.get(k) for k in ("id", "claim", "url", "note")} for c in _read(claims_path)]
    rounds, real = _blind(claims, seed)
    old = os.environ.get("MAENG_DECISIONS_LEDGER")
    with tempfile.TemporaryDirectory() as d:
        ledger = Path(d) / "ledger.jsonl"
        os.environ["MAENG_DECISIONS_LEDGER"] = str(ledger)
        try:
            judged = {real[r["id"]]: dict(r, id=real[r["id"]], round=k) for k, group in enumerate(rounds)
                      for r in vc.verify(group, pilot="claim_verification_eval", decide=decide)}
        finally:
            if old is None:
                os.environ.pop("MAENG_DECISIONS_LEDGER", None)
            else:
                os.environ["MAENG_DECISIONS_LEDGER"] = old
        lines = [json.loads(ln) for ln in ledger.read_text(encoding="utf-8").splitlines()] if ledger.exists() else []
    for r in lines:  # eval spend also counts in the trial report's overhead
        vc.decisions_client._log(r)
    usage = {"input_tokens": sum(r["input_tokens"] for r in lines), "cached_tokens": sum(r["cached_tokens"] for r in lines),
             "cost_usd": round(sum(r["cost_usd"] for r in lines), 8)}
    results = [judged[c["id"]] for c in claims]
    return {"results": results, "route": vc.route(results, seed=seed), "usage": usage}


def wilson(k, n, z=Z):
    """95% Wilson score interval for k of n -> (lower, upper)."""
    if n == 0:
        return None, None
    p, z2 = k / n, z * z
    den = 1 + z2 / n
    mid = (p + z2 / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / den
    return max(mid - half, 0.0), min(mid + half, 1.0)


def _pct(xs, q):
    """Nearest-rank percentile of a non-empty list."""
    xs = sorted(xs)
    return xs[max(math.ceil(q / 100 * len(xs)), 1) - 1]


def score(results, labels_path, usage=None):
    if isinstance(results, dict):
        usage, results = results.get("usage", usage), results["results"]
    usage = usage or {}
    labels = {r["id"]: r["label"] for r in _read(labels_path)}
    if {r["id"] for r in results} != set(labels):
        raise ValueError("results and labels cover different claim ids")
    pos = [r for r in results if labels[r["id"]] == "supported"]
    neg = [r for r in results if labels[r["id"]] != "supported"]
    missed = [r["id"] for r in neg if r["verdict"] == "supported"]
    flagged = [r["id"] for r in pos if r["verdict"] != "supported"]
    recall = (len(neg) - len(missed)) / len(neg) if neg else None
    over = len(flagged) / len(pos) if pos else None
    r_lo, r_hi = wilson(len(neg) - len(missed), len(neg))
    o_lo, o_hi = wilson(len(flagged), len(pos))
    lat = [ms for src, ms in {(r["url"], r.get("round")): (r["page_source"], r["latency_ms"]) for r in results}.values()
           if src != "none"]
    p50, p95 = (_pct(lat, 50), _pct(lat, 95)) if lat else (None, None)
    floors = {
        "every_negative_judged": not any(r["verdict"] == "unknown" for r in neg),
        "negative_recall": recall is not None and recall >= 0.95,
        "negative_recall_wilson_lower": r_lo is not None and r_lo >= 0.90,
        "over_flag": over is not None and over <= 0.30,
        "p50_latency_ms": p50 is not None and p50 < 2000,
    }
    return {
        "positives": len(pos), "negatives": len(neg),
        "negative_recall": recall, "negative_recall_wilson": [r_lo, r_hi],
        "over_flag": over, "over_flag_wilson": [o_lo, o_hi],
        "p50_latency_ms": p50, "p95_latency_ms": p95,
        "input_tokens": usage.get("input_tokens", 0), "cached_tokens": usage.get("cached_tokens", 0),
        "cost_usd": usage.get("cost_usd", 0.0),
        "pages_by_source": dict(Counter({r["url"]: r["page_source"] for r in results}.values())),
        "unknown": sum(r["verdict"] == "unknown" for r in results),
        "negatives_judged_supported": missed, "positives_not_judged_supported": flagged,
        "floors": floors, "pass": all(floors.values()),
    }


def _f(x, nd=4):
    return "n/a" if x is None else f"{x:.{nd}f}"


def _ids(ids, n=10):
    return (", ".join(ids[:n]) + (f" (+{len(ids) - n} more)" if len(ids) > n else "")) or "none"


def summary(rep):
    w, o, fl = rep["negative_recall_wilson"], rep["over_flag_wilson"], rep["floors"]
    ok = lambda b: "ok" if b else "FAIL"
    return "\n".join([
        f"# Claim verification eval: {'PASS' if rep['pass'] else 'FAIL'}",
        f"positives {rep['positives']}, negatives {rep['negatives']}, unknown verdicts {rep['unknown']}",
        "",
        "| metric | value | floor | |",
        "|---|---|---|---|",
        f"| negative recall | {_f(rep['negative_recall'])} | >= 0.95 | {ok(fl['negative_recall'])} |",
        f"| negative recall, Wilson 95% | {_f(w[0])} to {_f(w[1])} | lower >= 0.90 | {ok(fl['negative_recall_wilson_lower'])} |",
        f"| over-flag | {_f(rep['over_flag'])} ({_f(o[0])} to {_f(o[1])}) | <= 0.30 | {ok(fl['over_flag'])} |",
        f"| p50 per page (ms) | {rep['p50_latency_ms']} | < 2000 | {ok(fl['p50_latency_ms'])} |",
        f"| p95 per page (ms) | {rep['p95_latency_ms']} | | |",
        "",
        f"tokens in {rep['input_tokens']} (cached {rep['cached_tokens']}), cost ${rep['cost_usd']:.4f}, pages {rep['pages_by_source']}",
        f"negatives judged supported: {_ids(rep['negatives_judged_supported'])}",
        f"positives not judged supported: {_ids(rep['positives_not_judged_supported'])}",
    ])


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run the claim eval live and score it.")
    ap.add_argument("--claims", default=str(EVAL / "claims-v1.jsonl"))
    ap.add_argument("--labels", default=str(EVAL / "labels-v1.jsonl"))
    ap.add_argument("--out", help="write the JSON report here")
    a = ap.parse_args(argv)
    rep = score(run(a.claims), a.labels)
    if a.out:
        Path(a.out).write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(summary(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
