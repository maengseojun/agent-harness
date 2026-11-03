import json
import tempfile
import unittest
from pathlib import Path

import report

# Fixture: expected values below are computed by hand from these lines, not by running report.py.
ROWS = [
    {"ts": "2026-11-04T10:00:00+00:00", "pilot": "claim_verification", "n_questions": 10, "outcome": "ok",
     "latency_ms": 100, "input_tokens": 1000, "cached_tokens": 0, "cost_usd": 0.0001,
     "answers": [{"name": "a", "status": "ok", "choice": "supported"}, {"name": "b", "status": "ok", "choice": "not_in_page"}]},
    {"ts": "2026-11-05T10:00:00+00:00", "pilot": "claim_verification", "n_questions": 5, "outcome": "partial",
     "latency_ms": 300, "input_tokens": 3000, "cached_tokens": 1000, "cost_usd": 0.00021,
     "answers": [{"name": "c", "status": "ok", "choice": "supported"}, {"name": "d", "status": "unknown", "reason": "refused"}]},
    {"ts": "2026-11-05T11:00:00+00:00", "pilot": "claim_verification", "n_questions": 4, "outcome": "off",
     "latency_ms": 0, "input_tokens": 0, "cached_tokens": 0, "cost_usd": 0.0,
     "answers": [{"name": "e", "status": "unknown", "reason": "off"}]},
    {"ts": "2026-11-06T09:00:00+00:00", "pilot": "review_preflight", "n_questions": 3, "outcome": "ok",
     "latency_ms": 200, "input_tokens": 2000, "cached_tokens": 0, "cost_usd": 0.0002,
     "answers": [{"name": "AC-1", "status": "ok", "choice": "met"}, {"name": "AC-2", "status": "ok", "choice": "unmet"}]},
    {"ts": "2026-11-09T09:00:00+00:00", "pilot": "review_preflight", "n_questions": 1, "outcome": "ok",
     "latency_ms": 999, "input_tokens": 9, "cached_tokens": 0, "cost_usd": 0.5, "answers": []},
]


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.tmp.name, "ledger.jsonl")
        self.ledger.write_text("".join(json.dumps(r) + "\n" for r in ROWS) + "\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_percentile_nearest_rank(self):
        self.assertEqual(report.percentile([400, 100, 300, 200], 50), 200)
        self.assertEqual(report.percentile([400, 100, 300, 200], 95), 400)
        self.assertEqual(report.percentile([7], 50), 7)
        self.assertIsNone(report.percentile([], 50))

    def test_date_range_is_inclusive_and_excludes_later_days(self):
        rows = report.load(self.ledger, "2026-11-04", "2026-11-08")
        self.assertEqual(len(rows), 4)  # the 11-09 row is outside

    def test_claim_verification_metrics(self):
        s = report.summarize(report.load(self.ledger, "2026-11-04", "2026-11-08"))["claim_verification"]
        self.assertEqual(s["calls"], 3)
        self.assertEqual(s["sent"], 2)  # the "off" call sent nothing
        self.assertEqual(s["questions"], 19)
        self.assertEqual(s["latency_p50_ms"], 100)  # sent latencies [100, 300]; the off call's 0 is excluded
        self.assertEqual(s["latency_p95_ms"], 300)
        self.assertEqual(s["input_tokens"], 4000)
        self.assertEqual(s["cached_tokens"], 1000)
        self.assertAlmostEqual(s["cost_usd"], 0.00031)
        self.assertEqual(s["outcomes"], {"ok": 1, "partial": 1, "off": 1})
        self.assertEqual(s["verdicts"], {"supported": 2, "not_in_page": 1})
        self.assertEqual(s["unknown_by_reason"], {"refused": 1, "off": 1})

    def test_preflight_metrics_and_markdown(self):
        summary = report.summarize(report.load(self.ledger, "2026-11-04", "2026-11-08"))
        self.assertEqual(summary["review_preflight"]["verdicts"], {"met": 1, "unmet": 1})
        # the fields eval_claims.score() writes (Codex review, PR #93: the old keys printed None)
        ev = {"negative_recall": 0.96, "negative_recall_wilson": [0.9101, 0.9844], "over_flag": 0.12,
              "p50_latency_ms": 640, "pass": True}
        md = report.markdown(summary, ev)
        self.assertIn("| review_preflight | 1 | 1 | 3 | 200 | 200 | 2000 | 0.000200 |", md)
        self.assertIn("Total cost: $0.000510", md)
        self.assertIn("negative_recall=0.96, wilson_lower=0.9101, over_flag=0.12, p50_latency_ms=640, pass=True", md)
        self.assertNotIn("None", md)

    def test_missing_ledger_exits_1(self):
        self.assertEqual(report.main(["--ledger", str(Path(self.tmp.name, "none.jsonl"))]), 1)


if __name__ == "__main__":
    unittest.main()
