import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_claims as vc  # noqa: E402

PAGE_A = "Page A text. " * 60   # 780 characters
PAGE_B = "Page B text. " * 60
CHOICE_VALUES = ["supported", "contradicted", "not_in_page"]


def claim(i, url, note=None):
    return {"id": i, "claim": f"claim {i}", "url": url, "note": note}


class FakeDecide:
    """Answers by claim id from `answers` (id -> choice); records every call."""

    def __init__(self, answers=None, status="ok", **extra):
        self.answers, self.status, self.extra, self.calls = answers or {}, status, extra, []

    def __call__(self, input, questions, pilot):
        self.calls.append((input, questions, pilot))
        out = []
        for q in questions:
            a = {"name": q["name"], "type": "choice", "status": self.status}
            if self.status == "ok":
                a.update({"choice": self.answers.get(q["name"], "supported"), "confidence": 0.9,
                          "probabilities": [{"value": "supported", "probability": 0.9}]})
            else:
                a["reason"] = "refused"
            a.update(self.extra)
            out.append(a)
        return out


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        (self.tmp / "vault").mkdir()
        env = mock.patch.dict(os.environ, {"MAENG_DECISIONS_PAGES": str(self.tmp / "pages"),
                                           "MAENG_VAULT": str(self.tmp / "vault")})
        env.start()
        self.addCleanup(env.stop)

    def patch_fetch(self, pages):
        """pages: url -> (text, source); fetch_page is replaced, nothing touches the network."""
        p = mock.patch.object(vc, "fetch_page", lambda url, note=None, refresh=False: pages[url])
        p.start()
        self.addCleanup(p.stop)


class VerifyTests(Base):
    def test_one_call_per_page_with_choice_question_per_claim(self):
        self.patch_fetch({"u1": (PAGE_A, "live"), "u2": (PAGE_B, "note")})
        d = FakeDecide({"c2": "contradicted", "c3": "not_in_page"})
        res = vc.verify([claim("c1", "u1"), claim("c2", "u2"), claim("c3", "u1"), claim("c4", "u2")], decide=d)
        self.assertEqual(len(d.calls), 2)  # 4 claims, 2 pages
        (in1, qs1, pilot), (in2, qs2, _) = d.calls
        self.assertEqual(in1, f"Source page (u1):\n\n{PAGE_A}")
        self.assertEqual(in2, f"Source page (u2):\n\n{PAGE_B}")
        self.assertEqual(pilot, "claim_verification")
        self.assertEqual([q["name"] for q in qs1], ["c1", "c3"])
        self.assertEqual([q["name"] for q in qs2], ["c2", "c4"])
        q = qs1[0]
        self.assertEqual(q["type"], "choice")
        self.assertEqual(q["instructions"], "Claim: claim c1\nJudge the claim only against the page text above.")
        self.assertEqual([c["value"] for c in q["choices"]], CHOICE_VALUES)
        self.assertEqual(q["choices"][0]["description"],
                         "The page states this claim, with the same numbers, names, dates and qualifiers.")
        self.assertEqual(q["choices"][1]["description"],
                         "The page states something that conflicts with the claim, such as a different number or the opposite statement.")
        self.assertEqual(q["choices"][2]["description"], "The page does not state the claim, or states only part of it.")
        # results come back in input order with the page's source
        self.assertEqual([(r["id"], r["verdict"], r["page_source"]) for r in res],
                         [("c1", "supported", "live"), ("c2", "contradicted", "note"),
                          ("c3", "not_in_page", "live"), ("c4", "supported", "note")])
        self.assertEqual(res[0]["confidence"], 0.9)
        self.assertEqual(res[0]["probabilities"], [{"value": "supported", "probability": 0.9}])
        self.assertEqual(res[0]["latency_ms"], res[2]["latency_ms"])  # per page

    def test_refused_answer_is_unknown(self):
        self.patch_fetch({"u1": (PAGE_A, "live")})
        res = vc.verify([claim("c1", "u1")], decide=FakeDecide(status="unknown"))
        self.assertEqual(res[0]["verdict"], "unknown")
        self.assertIsNone(res[0]["probabilities"])
        self.assertIsNone(res[0]["confidence"])

    def test_off_list_choice_is_unknown(self):
        self.patch_fetch({"u1": (PAGE_A, "live")})
        res = vc.verify([claim("c1", "u1"), claim("c2", "u1")], decide=FakeDecide({"c1": "maybe", "c2": "SUPPORTED"}))
        self.assertEqual([r["verdict"] for r in res], ["unknown", "unknown"])

    def test_missing_answer_is_unknown(self):
        self.patch_fetch({"u1": (PAGE_A, "live")})
        res = vc.verify([claim("c1", "u1")], decide=lambda *a: [])
        self.assertEqual(res[0]["verdict"], "unknown")

    def test_none_page_sends_nothing(self):
        self.patch_fetch({"u1": ("", "none"), "u2": (PAGE_B, "live")})
        d = FakeDecide()
        res = vc.verify([claim("c1", "u1"), claim("c2", "u2")], decide=d)
        self.assertEqual(len(d.calls), 1)
        self.assertEqual(d.calls[0][0], f"Source page (u2):\n\n{PAGE_B}")
        self.assertEqual([r["verdict"] for r in res], ["unknown", "supported"])
        self.assertEqual((res[0]["page_source"], res[0]["latency_ms"]), ("none", 0))

    def test_401_claims_on_one_page_make_two_calls(self):
        self.patch_fetch({"u1": (PAGE_A, "live")})
        d = FakeDecide()
        res = vc.verify([claim(f"c{i}", "u1") for i in range(401)], decide=d)
        self.assertEqual([len(c[1]) for c in d.calls], [400, 1])
        self.assertEqual(len(res), 401)

    def test_duplicate_ids_are_refused(self):
        self.patch_fetch({"u1": (PAGE_A, "live")})
        with self.assertRaises(ValueError):
            vc.verify([claim("c1", "u1"), claim("c1", "u1")], decide=FakeDecide())

    def test_note_of_first_claim_with_a_note_reaches_fetch(self):
        seen = []
        p = mock.patch.object(vc, "fetch_page", lambda url, note=None, refresh=False: seen.append(note) or (PAGE_A, "live"))
        p.start()
        self.addCleanup(p.stop)
        vc.verify([claim("c1", "u1"), claim("c2", "u1", "n.md")], decide=FakeDecide())
        self.assertEqual(seen, ["n.md"])


class RouteTests(unittest.TestCase):
    @staticmethod
    def results(n_sup, others=()):
        return ([{"id": f"s{i:02d}", "verdict": "supported"} for i in range(n_sup)]
                + [{"id": o, "verdict": v} for o, v in others])

    def test_every_non_supported_id_is_included(self):
        res = self.results(10, [("x1", "contradicted"), ("x2", "not_in_page"), ("x3", "unknown")])
        out = vc.route(res, seed=1)
        self.assertEqual(out[:3], ["x1", "x2", "x3"])
        self.assertEqual(len(out), 3 + 3)  # 10 supported: max(3, ceil(0.2*10)=2) = 3

    def test_sample_size_rule(self):
        for n, want in [(0, 0), (1, 1), (2, 2), (3, 3), (10, 3), (15, 3), (16, 4), (30, 6), (100, 20)]:
            self.assertEqual(len(vc.route(self.results(n))), want, n)
        self.assertEqual(len(vc.route(self.results(10), rate=0.5)), 5)
        self.assertEqual(len(vc.route(self.results(10), min_sample=7)), 7)

    def test_sampled_ids_are_supported_and_distinct(self):
        res = self.results(30, [("x1", "contradicted")])
        out = vc.route(res, seed=4)
        self.assertEqual(out[0], "x1")
        self.assertEqual(len(set(out)), 7)
        self.assertTrue(all(i.startswith("s") for i in out[1:]))

    def test_same_seed_same_list_regardless_of_input_order(self):
        res = self.results(40, [("x1", "unknown")])
        a = vc.route(res, seed=7)
        self.assertEqual(a, vc.route(res, seed=7))
        self.assertEqual(a, vc.route(list(reversed(res[:-1])) + res[-1:], seed=7))
        self.assertNotEqual(a, vc.route(res, seed=8))


class FetchTests(Base):
    def fake_get(self, mapping):
        calls = []

        def get(url):
            calls.append(url)
            if url not in mapping:
                raise OSError("no route")
            return mapping[url]
        p = mock.patch.object(vc, "_get", get)
        p.start()
        self.addCleanup(p.stop)
        return calls

    def test_github_pypi_and_release_routes(self):
        body = "z" * 600
        calls = self.fake_get({
            "https://raw.githubusercontent.com/o/r/HEAD/README.md": body,
            "https://raw.githubusercontent.com/o/r/main/runs/a/report.md": body + "blob",
            "https://api.github.com/repos/o/r/releases/tags/v0.6.0": json.dumps(
                {"name": "v0.6.0", "published_at": "2026-10-01T00:00:00Z", "body": "R" * 600}),
            "https://pypi.org/pypi/llm2jev/json": json.dumps({"info": {"description": "D" * 600}}),
        })
        self.assertEqual(vc.fetch_page("https://github.com/o/r"), (body, "live"))
        self.assertEqual(vc.fetch_page("https://github.com/o/r/blob/main/runs/a/report.md"), (body + "blob", "live"))
        self.assertEqual(vc.fetch_page("https://github.com/o/r/releases/tag/v0.6.0"),
                         ("v0.6.0\n2026-10-01T00:00:00Z\n" + "R" * 600, "live"))
        self.assertEqual(vc.fetch_page("https://pypi.org/project/llm2jev/"), ("D" * 600, "live"))
        self.assertEqual(len(calls), 4)

    def test_html_to_text(self):
        html = ("<html><head><title>T</title><style>.a{x:1}</style><script>var secret=1;</script></head><body>"
                "<header>HEADERTEXT</header><nav>NAVTEXT</nav><svg><text>SVGTEXT</text></svg><noscript>NOSCRIPT</noscript>"
                "<h1>Title   here</h1><p>First   para &amp; more.</p>"
                "<table><tr><th>Model</th><th>Price</th></tr><tr><td>luna</td><td>$0.10</td></tr></table>"
                "<footer>FOOTERTEXT</footer></body></html>")
        self.assertEqual(vc._html_text(html), "T\nTitle here\nFirst para & more.\n| Model | Price\n| luna | $0.10")

    def test_html_page_is_fetched_and_cached(self):
        html = "<html><body><p>" + "word " * 200 + "</p></body></html>"
        calls = self.fake_get({"https://example.com/x": html})
        text, source = vc.fetch_page("https://example.com/x")
        self.assertEqual((source, text.startswith("word word")), ("live", True))
        self.assertEqual(vc.fetch_page("https://example.com/x"), (text, "live"))
        self.assertEqual(len(calls), 1)  # second call from the cache
        vc.fetch_page("https://example.com/x", refresh=True)
        self.assertEqual(len(calls), 2)
        files = sorted(p.suffix for p in (self.tmp / "pages").iterdir())
        self.assertEqual(files, [".json", ".txt"])
        meta = json.loads(next((self.tmp / "pages").glob("*.json")).read_text())
        self.assertEqual((meta["url"], meta["source"], meta["truncated"]), ("https://example.com/x", "live", False))
        self.assertIn("fetched_at", meta)

    def test_short_or_failed_fetch_falls_back_to_the_note_body(self):
        note = self.tmp / "vault" / "wiki" / "S-x.md"
        note.parent.mkdir()
        note.write_text("---\nid: S-x\ntitle: t\n---\nBody line one.\nBody two.\n", encoding="utf-8")
        self.fake_get({"https://short.example/": "<p>tiny</p>"})
        self.assertEqual(vc.fetch_page("https://short.example/", "wiki/S-x.md"), ("Body line one.\nBody two.", "note"))
        self.assertEqual(vc.fetch_page("https://down.example/", "wiki/S-x.md"), ("Body line one.\nBody two.", "note"))

    def test_neither_fetch_nor_note_is_none_and_not_cached(self):
        self.fake_get({})
        self.assertEqual(vc.fetch_page("https://down.example/", "wiki/missing.md"), ("", "none"))
        self.assertEqual(vc.fetch_page("https://down.example/"), ("", "none"))
        self.assertFalse((self.tmp / "pages").exists())

    def test_note_path_cannot_leave_the_vault(self):
        (self.tmp / "secret.md").write_text("outside the vault", encoding="utf-8")
        self.fake_get({})
        self.assertEqual(vc.fetch_page("https://down.example/", "../secret.md"), ("", "none"))

    def test_text_is_truncated_to_400000_and_recorded(self):
        self.fake_get({"https://big.example/": "a" * 450_000})
        text, source = vc.fetch_page("https://big.example/")
        self.assertEqual((len(text), source), (400_000, "live"))
        meta = json.loads(next((self.tmp / "pages").glob("*.json")).read_text())
        self.assertTrue(meta["truncated"])

    def test_the_request_carries_a_browser_user_agent(self):
        seen = []

        class R:
            headers = type("H", (), {"get_content_charset": lambda s: None})()

            def read(self, n):
                return b"x"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        with mock.patch.object(vc.urllib.request, "urlopen", lambda req, timeout: seen.append(req) or R()):
            vc._get("https://example.com/")
        self.assertTrue(seen[0].get_header("User-agent").startswith("Mozilla/5.0"))


if __name__ == "__main__":
    unittest.main()
