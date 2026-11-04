#!/usr/bin/env python3
"""Per-use metrics from the Decisions ledger for the trial-week report (MAE-306).

    python3 report.py [--ledger PATH] [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--eval-report PATH] [--out PATH]

Reads the ledger written by decisions_client.decide (one JSON line per call) and prints Markdown:
per pilot the calls by outcome, requests actually sent, latency p50/p95 over sent requests only,
tokens, cost, unknown answers by reason and the verdict counts. --since/--until are inclusive UTC dates.
"""
import argparse
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

NOT_SENT = {"off", "no_key"}  # no request left the machine; latency and tokens are 0


def percentile(values, p):
    """Nearest-rank percentile; None for no values."""
    if not values:
        return None
    s = sorted(values)
    return s[max(math.ceil(p / 100 * len(s)), 1) - 1]


def load(path, since=None, until=None):
    rows, skipped = [], 0
    for line in Path(path).expanduser().read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except ValueError:  # a line cut by an interrupted write must not cost the whole report
            skipped += 1
            continue
        day = r.get("ts", "")[:10]
        if (since and day < since) or (until and day > until):
            continue
        rows.append(r)
    if skipped:
        print(f"report: skipped {skipped} unreadable ledger lines", file=sys.stderr)
    return rows


def summarize(rows):
    by = defaultdict(list)
    for r in rows:
        by[f"{r.get('pilot', '?')} [{r['model']}]" if r.get("model") else r.get("pilot", "?")].append(r)  # engines apart
    out = {}
    for pilot, rs in sorted(by.items()):
        sent = [r for r in rs if r.get("outcome") not in NOT_SENT]
        lat = [r.get("latency_ms", 0) for r in sent]
        answers = [a for r in rs for a in r.get("answers", [])]
        out[pilot] = {
            "calls": len(rs),
            "outcomes": dict(Counter(r.get("outcome") for r in rs)),
            "sent": len(sent),
            "questions": sum(r.get("n_questions", 0) for r in rs),
            "latency_p50_ms": percentile(lat, 50),
            "latency_p95_ms": percentile(lat, 95),
            "input_tokens": sum(r.get("input_tokens", 0) for r in rs),
            "cached_tokens": sum(r.get("cached_tokens", 0) for r in rs),
            "cost_usd": round(sum(r.get("cost_usd", 0) for r in rs), 6),
            "unknown_by_reason": dict(Counter(a.get("reason") for a in answers if a.get("status") != "ok")),
            "verdicts": dict(Counter(a["choice"] for a in answers if a.get("status") == "ok" and "choice" in a)),
        }
    return out


def markdown(summary, eval_report=None):
    lines = ["| pilot | calls | sent | questions | p50 ms | p95 ms | input tokens | cost USD |",
             "|---|---|---|---|---|---|---|---|"]
    for p, s in summary.items():
        lines.append(f"| {p} | {s['calls']} | {s['sent']} | {s['questions']} | {s['latency_p50_ms']} | "
                     f"{s['latency_p95_ms']} | {s['input_tokens']} | {s['cost_usd']:.6f} |")
    for p, s in summary.items():
        lines.append(f"\n**{p}**: outcomes {s['outcomes']}; verdicts {s['verdicts']}; unknown {s['unknown_by_reason']}")
    total = sum(s["cost_usd"] for s in summary.values())
    lines.append(f"\nTotal cost: ${total:.6f}")
    if eval_report:  # the shape eval_claims.py --out writes
        low = (eval_report.get("negative_recall_wilson") or [None])[0]
        lines.append(f"\nClaim eval: negative_recall={eval_report.get('negative_recall')}, wilson_lower={low}, "
                     f"over_flag={eval_report.get('over_flag')}, p50_latency_ms={eval_report.get('p50_latency_ms')}, "
                     f"pass={eval_report.get('pass')}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ledger", default=os.environ.get("MAENG_DECISIONS_LEDGER")
                    or "~/Documents/maeng-harness/decisions/ledger.jsonl")
    ap.add_argument("--since")
    ap.add_argument("--until")
    ap.add_argument("--eval-report")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    if not Path(a.ledger).expanduser().exists():
        print(f"no ledger at {a.ledger}", file=sys.stderr)
        return 1
    ev = json.loads(Path(a.eval_report).read_text(encoding="utf-8")) if a.eval_report else None
    text = markdown(summarize(load(a.ledger, a.since, a.until)), ev)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
