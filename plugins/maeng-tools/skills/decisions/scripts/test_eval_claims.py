import builtins
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decisions_client as dc  # noqa: E402
import eval_claims as ec  # noqa: E402
import verify_claims as vc  # noqa: E402

PAGE = "Page text. " * 60


@contextlib.contextmanager
def forbid(path):
    """Opening `path` by any route (open, io.open, Path.open/read_text/read_bytes) raises."""
    target = os.path.realpath(path)

    def wrap(real):
        def guarded(file, *a, **k):
            if isinstance(file, (str, bytes, os.PathLike)) and os.path.realpath(file) == target:
                raise AssertionError(f"opened forbidden file {target}")
            return real(file, *a, **k)
        return guarded
    with mock.patch("builtins.open", wrap(builtins.open)), mock.patch("io.open", wrap(io.open)):
        yield


def jsonl(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def supported_decide(input, questions, pilot, **_):
    return [{"name": q["name"], "type": "choice", "status": "ok", "choice": "supported", "confidence": 0.9,
             "probabilities": [{"value": "supported", "probability": 0.9}]} for q in questions]


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()

    def patch_fetch(self, source="live"):
        p = mock.patch.object(vc, "fetch_page", lambda url, note=None, refresh=False: (PAGE, source))
        p.start()
        self.addCleanup(p.stop)


class RunTests(Base):
    def files(self):
        claims = jsonl(self.tmp / "claims.jsonl", [
            {"id": f"c{i}", "claim": f"claim {i}", "url": "u1", "note": "n.md"} for i in range(5)])
        labels = jsonl(self.tmp / "labels.jsonl", [{"id": f"c{i}", "label": "supported", "kind": "seed"} for i in range(5)])
        return claims, labels

    def test_run_never_opens_the_labels_file(self):
        claims, labels = self.files()
        self.patch_fetch()
        with forbid(labels):
            with self.assertRaises(AssertionError):  # the guard works: this is what run() would hit
                open(labels, encoding="utf-8")
            with self.assertRaises(AssertionError):
                labels.read_text(encoding="utf-8")
            out = ec.run(claims, decide=supported_decide)
        self.assertEqual([r["verdict"] for r in out["results"]], ["supported"] * 5)
        self.assertEqual(len(out["route"]), 3)  # 5 supported: max(3, ceil(1.0)) of them go to the researcher

    def test_extra_fields_in_the_claims_file_never_reach_a_request(self):
        calls = []
        claims = jsonl(self.tmp / "claims.jsonl", [
            {"id": "c0", "claim": "claim 0", "url": "u1", "note": "n.md", "label": "LEAKED_LABEL", "source": "LEAKED_SOURCE"}])
        self.patch_fetch()
        out = ec.run(claims, decide=lambda *a: calls.append(a) or supported_decide(*a))
        self.assertEqual(len(calls), 1)
        self.assertNotIn("LEAKED", json.dumps(calls) + json.dumps(out))

    def test_requests_carry_no_claim_id_and_a_claim_never_meets_its_mutation(self):
        ids = ["p001", "n001", "mp001-1", "mp001-2"]
        claims = jsonl(self.tmp / "claims.jsonl", [{"id": i, "claim": f"claim {i}", "url": "u1", "note": None} for i in ids])
        self.patch_fetch()
        calls = []
        out = ec.run(claims, decide=lambda *a: calls.append(a) or supported_decide(*a))
        self.assertEqual(sorted(sorted(q["name"][0] for q in c[1]) for c in calls), [["q"], ["q"], ["q", "q"]])
        groups = [" ".join(q["instructions"] for q in c[1]) for c in calls]
        for g in groups:
            self.assertFalse("claim mp001-1" in g and ("claim p001" in g or "claim mp001-2" in g), g)
        self.assertEqual([r["id"] for r in out["results"]], ids)  # results come back under the real ids

    def test_usage_comes_from_a_run_ledger_and_the_env_is_restored(self):
        claims = jsonl(self.tmp / "claims.jsonl", [
            {"id": "c0", "claim": "claim 0", "url": "u1", "note": None}, {"id": "c1", "claim": "claim 1", "url": "u2", "note": None}])
        self.patch_fetch()
        sentinel = str(self.tmp / "main-ledger.jsonl")

        def post(url, body, headers, timeout):
            return {"answers": [{"name": q["name"], "type": "choice", "choice": "not_in_page", "confidence": 0.8,
                                 "probabilities": []} for q in body["questions"]],
                    "usage": {"input_tokens": 1_000_000, "input_tokens_details": {"cached_tokens": 400_000}}}
        env = {"OPENAI_API_KEY": "sk-test-EVALKEY1234567890", "MAENG_DECISIONS_LEDGER": sentinel}
        with mock.patch.dict(os.environ, env), mock.patch.object(dc, "_post", post):
            os.environ.pop("MAENG_DECISIONS", None)
            out = ec.run(claims)
            self.assertEqual(os.environ["MAENG_DECISIONS_LEDGER"], sentinel)
        # the run's two calls are copied to the main ledger once, after the run, so eval spend shows in the report
        main = [json.loads(ln) for ln in Path(sentinel).read_text(encoding="utf-8").splitlines()]
        self.assertEqual([r["pilot"] for r in main], ["claim_verification_eval"] * 2)
        self.assertEqual([r["verdict"] for r in out["results"]], ["not_in_page", "not_in_page"])
        # two pages, two calls; each: 600000 fresh * $0.10/1M + 400000 cached * $0.01/1M = $0.064
        self.assertEqual(out["usage"], {"input_tokens": 2_000_000, "cached_tokens": 800_000, "cost_usd": 0.128})

    def test_an_interrupted_run_keeps_the_calls_it_made_in_the_main_ledger(self):
        claims = jsonl(self.tmp / "claims.jsonl", [
            {"id": "c0", "claim": "a", "url": "u1", "note": None}, {"id": "c1", "claim": "b", "url": "u2", "note": None}])
        self.patch_fetch()
        sentinel = str(self.tmp / "main-ledger.jsonl")
        posts = []

        def post(url, body, headers, timeout):
            posts.append(body)
            return {"answers": [], "usage": {}}

        def decide(input, questions, pilot, **kw):
            if posts:
                raise KeyboardInterrupt
            return dc.decide(input, questions, pilot, **kw)
        env = {"OPENAI_API_KEY": "sk-test-EVALKEY1234567890", "MAENG_DECISIONS_LEDGER": sentinel}
        with mock.patch.dict(os.environ, env), mock.patch.object(dc, "_post", post):
            os.environ.pop("MAENG_DECISIONS", None)
            with self.assertRaises(KeyboardInterrupt):
                ec.run(claims, decide=decide)
            self.assertEqual(os.environ["MAENG_DECISIONS_LEDGER"], sentinel)
        self.assertEqual(len(Path(sentinel).read_text(encoding="utf-8").splitlines()), 1)

    def test_env_without_a_ledger_variable_is_left_without_one(self):
        claims, _ = self.files()
        self.patch_fetch()
        with mock.patch.dict(os.environ):
            os.environ.pop("MAENG_DECISIONS_LEDGER", None)
            ec.run(claims, decide=supported_decide)
            self.assertNotIn("MAENG_DECISIONS_LEDGER", os.environ)


def res(i, verdict, url, source="live", ms=100):
    return {"id": i, "url": url, "verdict": verdict, "page_source": source, "latency_ms": ms}


class ScoreTests(Base):
    def labels(self, neg, pos):
        rows = [{"id": f"n{i:02d}", "label": "not_in_page" if i % 2 else "contradicted", "kind": "seed"} for i in range(1, neg + 1)]
        rows += [{"id": f"p{i:02d}", "label": "supported", "kind": "seed"} for i in range(1, pos + 1)]
        return jsonl(self.tmp / "labels.jsonl", rows)

    def test_fixed_results_give_hand_computed_numbers(self):
        # 10 negatives: n10 judged supported, n03 and n09 unknown (caught), the rest not supported
        # 10 positives: p09 not_in_page, p10 unknown, the rest supported
        # 5 pages A..E with latencies 100, 300, 500, 900, 2500 ms; two claims of each kind per page
        verdicts = {"n01": "not_in_page", "n02": "contradicted", "n03": "unknown", "n04": "not_in_page", "n05": "contradicted",
                    "n06": "contradicted", "n07": "not_in_page", "n08": "contradicted", "n09": "unknown", "n10": "supported",
                    "p01": "supported", "p02": "supported", "p03": "supported", "p04": "supported", "p05": "supported",
                    "p06": "supported", "p07": "supported", "p08": "supported", "p09": "not_in_page", "p10": "unknown"}
        page = {"n01": "A", "n02": "A", "p01": "A", "p02": "A", "n03": "B", "n04": "B", "p03": "B", "p04": "B",
                "n05": "C", "n06": "C", "p05": "C", "p06": "C", "n07": "D", "n08": "D", "p07": "D", "p08": "D",
                "n09": "E", "n10": "E", "p09": "E", "p10": "E"}
        lat = {"A": 100, "B": 300, "C": 500, "D": 900, "E": 2500}
        results = [res(i, v, page[i], "note" if page[i] == "C" else "live", lat[page[i]]) for i, v in verdicts.items()]
        usage = {"input_tokens": 12345, "cached_tokens": 2000, "cost_usd": 0.0012}
        rep = ec.score({"results": results, "usage": usage}, self.labels(10, 10))
        self.assertEqual((rep["positives"], rep["negatives"]), (10, 10))
        self.assertAlmostEqual(rep["negative_recall"], 0.9)  # 9 of 10 negatives not judged supported
        self.assertAlmostEqual(rep["negative_recall_wilson"][0], 0.5958, places=4)
        self.assertAlmostEqual(rep["negative_recall_wilson"][1], 0.9821, places=4)
        self.assertAlmostEqual(rep["over_flag"], 0.2)  # 2 of 10 positives not judged supported
        self.assertAlmostEqual(rep["over_flag_wilson"][0], 0.0567, places=4)
        self.assertAlmostEqual(rep["over_flag_wilson"][1], 0.5098, places=4)
        self.assertEqual((rep["p50_latency_ms"], rep["p95_latency_ms"]), (500, 2500))  # nearest rank over 5 pages
        self.assertEqual(rep["pages_by_source"], {"live": 4, "note": 1})
        self.assertEqual((rep["input_tokens"], rep["cached_tokens"], rep["cost_usd"]), (12345, 2000, 0.0012))
        self.assertEqual(rep["unknown"], 3)
        self.assertEqual(rep["negatives_judged_supported"], ["n10"])
        self.assertEqual(rep["positives_not_judged_supported"], ["p09", "p10"])
        self.assertEqual(rep["floors"], {"every_negative_judged": False, "negative_recall": False, "negative_recall_wilson_lower": False,
                                         "over_flag": True, "p50_latency_ms": True})
        self.assertFalse(rep["pass"])

    def perfect(self, n_neg, ms, n_flagged_pos=3):
        out = [res(f"n{i:02d}", "contradicted" if i % 2 == 0 else "not_in_page", "u", ms=ms) for i in range(1, n_neg + 1)]
        return out + [res(f"p{i:02d}", "not_in_page" if i > 10 - n_flagged_pos else "supported", "u", ms=ms) for i in range(1, 11)]

    def test_an_outage_on_the_negatives_cannot_pass(self):
        # 100 negatives unknown (counted as caught) and all positives supported: every other floor holds
        results = [res(f"n{i:02d}", "unknown", "A") for i in range(1, 11)] + [res(f"p{i:02d}", "supported", "A") for i in range(1, 11)]
        rep = ec.score(results, self.labels(10, 10))
        self.assertEqual((rep["negative_recall"], rep["over_flag"]), (1.0, 0.0))
        self.assertFalse(rep["floors"]["every_negative_judged"])
        self.assertFalse(rep["pass"])

    def test_the_floors_pass_exactly_at_their_edges(self):
        # 35 of 35 negatives caught: Wilson lower bound 35 / (35 + 1.96^2) = 0.9011 >= 0.90
        # 3 of 10 positives flagged: over-flag 0.3 <= 0.30; one page at 1999 ms < 2000
        rep = ec.score(self.perfect(35, 1999), self.labels(35, 10))
        self.assertEqual(rep["negative_recall"], 1.0)
        self.assertAlmostEqual(rep["negative_recall_wilson"][0], 0.9011, places=4)
        self.assertAlmostEqual(rep["over_flag"], 0.3)
        self.assertEqual(rep["floors"], {"every_negative_judged": True, "negative_recall": True, "negative_recall_wilson_lower": True,
                                         "over_flag": True, "p50_latency_ms": True})
        self.assertTrue(rep["pass"])
        self.assertEqual(rep["cost_usd"], 0.0)  # no usage given

    def test_each_floor_fails_on_its_own(self):
        # 34 of 34 caught: lower bound 34 / (34 + 1.96^2) = 0.8985 < 0.90 although recall is 1.0
        rep = ec.score(self.perfect(34, 1999), self.labels(34, 10))
        self.assertEqual(rep["negative_recall"], 1.0)
        self.assertAlmostEqual(rep["negative_recall_wilson"][0], 0.8985, places=4)
        self.assertFalse(rep["floors"]["negative_recall_wilson_lower"])
        self.assertFalse(rep["pass"])
        # 4 of 10 positives flagged: 0.4 > 0.30
        rep = ec.score(self.perfect(35, 1999, n_flagged_pos=4), self.labels(35, 10))
        self.assertEqual(rep["floors"], {"every_negative_judged": True, "negative_recall": True, "negative_recall_wilson_lower": True,
                                         "over_flag": False, "p50_latency_ms": True})
        # p50 of 2000 is not under 2000
        rep = ec.score(self.perfect(35, 2000), self.labels(35, 10))
        self.assertEqual(rep["p50_latency_ms"], 2000)
        self.assertFalse(rep["floors"]["p50_latency_ms"])
        self.assertFalse(rep["pass"])

    def test_an_all_unknown_run_cannot_pass(self):
        # no key, MAENG_DECISIONS=off or an eta checkout: every verdict unknown, nothing was requested
        results = [res(f"n{i:02d}", "unknown", "u", "live", 0) for i in range(1, 36)]
        results += [res(f"p{i:02d}", "unknown", "u", "live", 0) for i in range(1, 11)]
        rep = ec.score(results, self.labels(35, 10))
        self.assertEqual(rep["negative_recall"], 1.0)  # unknown counts as caught ...
        self.assertEqual(rep["over_flag"], 1.0)  # ... but every positive is flagged
        self.assertFalse(rep["pass"])

    def test_pages_without_text_are_left_out_of_latency(self):
        results = [res("n01", "unknown", "A", "none", 0), res("n02", "contradicted", "B", "live", 700),
                   res("p01", "supported", "B", "live", 700)]
        rep = ec.score(results, self.labels(2, 1))
        self.assertEqual((rep["p50_latency_ms"], rep["p95_latency_ms"]), (700, 700))
        self.assertEqual(rep["pages_by_source"], {"none": 1, "live": 1})

    def test_no_negatives_is_not_a_pass(self):
        rep = ec.score([res("p01", "supported", "u")], self.labels(0, 1))
        self.assertIsNone(rep["negative_recall"])
        self.assertFalse(rep["pass"])

    def test_results_and_labels_must_cover_the_same_ids(self):
        with self.assertRaises(ValueError):
            ec.score([res("n01", "contradicted", "u")], self.labels(2, 0))


class CliTests(Base):
    def test_main_writes_the_report_and_prints_a_summary(self):
        claims = jsonl(self.tmp / "claims.jsonl", [
            {"id": "n01", "claim": "a", "url": "u1", "note": None}, {"id": "p01", "claim": "b", "url": "u1", "note": None}])
        labels = jsonl(self.tmp / "labels.jsonl", [
            {"id": "n01", "label": "contradicted", "kind": "mutation", "parent": "p01"}, {"id": "p01", "label": "supported", "kind": "seed"}])
        out = self.tmp / "report.json"
        stdout = io.StringIO()
        p = mock.patch.object(vc, "fetch_page", lambda url, note=None, refresh=False: (PAGE, "live"))
        p.start()
        self.addCleanup(p.stop)
        with mock.patch.object(dc, "decide", supported_decide), contextlib.redirect_stdout(stdout):
            self.assertEqual(ec.main(["--claims", str(claims), "--labels", str(labels), "--out", str(out)]), 0)
        rep = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(rep["negatives_judged_supported"], ["n01"])  # the fake judges everything supported
        self.assertFalse(rep["pass"])
        self.assertTrue(stdout.getvalue().startswith("# Claim verification eval: FAIL"))
        self.assertIn("negatives judged supported: n01", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
