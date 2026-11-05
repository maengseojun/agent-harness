import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aside_step as st  # noqa: E402

BODY = "Real article text. " * 40
WALL = "Sign in to GitHub. Username or email address. Password. Forgot password? " * 10


def claim(i, url, note=None):
    return {"id": i, "claim": f"claim {i}", "url": url, "note": note}


class FakeDecide:
    """Access questions: `wall` marks the page a wall. Claim questions: supported. Records calls."""

    def __init__(self, answer=True):
        self.calls, self.answer = [], answer

    def __call__(self, text, questions, pilot):
        self.calls.append((pilot, len(questions)))
        out = []
        for q in questions:
            if not self.answer:
                out.append({"name": q["name"], "type": "choice", "status": "unknown", "reason": "http_400"})
            elif pilot == "aside_access":
                part = text.split(f"[{q['name']}]", 1)[1].split("=== [", 1)[0]
                kind = "login_required" if "Sign in" in part else "refused" if "CAPTCHA" in part else "readable"
                out.append({"name": q["name"], "type": "choice", "status": "ok", "choice": kind})
            else:
                out.append({"name": q["name"], "type": "choice", "status": "ok", "choice": "supported",
                            "probabilities": [], "confidence": 1.0})
        return out


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        patches = [mock.patch.dict(os.environ, {"MAENG_DECISIONS_RUNS": str(self.tmp / "runs")}),
                   mock.patch.object(st, "DECIDE", FakeDecide())]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.d = st.run_dir("r1")
        self.seen = []

    def serve(self, live, aside):
        def read(url):
            self.seen.append(url)
            return aside.get(url, "")
        for name, fn in (("aside_read", read),):
            p = mock.patch.object(st, name, fn)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(st.vc, "_live", lambda u: live.get(u, ""))
        p.start()
        self.addCleanup(p.stop)

    def claims(self, items):
        f = self.tmp / "claims.json"
        f.write_text(json.dumps(items))
        st.main(["claims", "--run", "r1", "--claims", str(f)])
        return json.loads((self.d / "claims.json").read_text()), json.loads((self.d / "needs-login.json").read_text())


class ReadingOrder(Base):
    def test_a_public_page_never_touches_aside(self):
        self.serve({"https://a": BODY}, {})
        doc, needs = self.claims([claim("c1", "https://a")])
        self.assertEqual(doc["results"][0]["page_source"], "live")
        self.assertEqual(self.seen, [])
        self.assertEqual(needs, [])

    def test_a_long_login_wall_goes_to_aside(self):
        self.serve({"https://a": WALL}, {"https://a": BODY})
        doc, needs = self.claims([claim("c1", "https://a")])
        self.assertGreater(len(WALL), 500)
        self.assertEqual(doc["results"][0]["page_source"], "aside")
        self.assertEqual(doc["results"][0]["verdict"], "supported")
        self.assertEqual(self.seen, ["https://a"])
        self.assertEqual(needs, [])

    def test_a_short_shell_goes_to_aside_without_asking_decisions_about_it(self):
        self.serve({"https://a": "Loading"}, {"https://a": BODY})
        doc, _ = self.claims([claim("c1", "https://a")])
        self.assertEqual(doc["results"][0]["page_source"], "aside")

    def test_a_wall_in_aside_too_goes_to_the_user_and_stays_unknown(self):
        self.serve({"https://a": WALL}, {"https://a": WALL})
        doc, needs = self.claims([claim("c1", "https://a"), claim("c2", "https://a")])
        self.assertEqual([r["verdict"] for r in doc["results"]], ["unknown", "unknown"])
        self.assertEqual(doc["results"][0]["reason"], "login_required")
        self.assertEqual(needs, [{"url": "https://a", "kind": "login_required", "claims": ["c1", "c2"]}])
        self.assertEqual(list((self.d / "pages").iterdir()), [])  # a wall is never kept

    def test_a_captcha_goes_to_the_user_too(self):
        self.serve({"https://a": ""}, {"https://a": "CAPTCHA " * 100})
        self.assertEqual(self.claims([claim("c1", "https://a")])[1][0]["kind"], "refused")

    def test_a_dead_aside_is_a_gap_not_a_login_request(self):
        self.serve({"https://a": ""}, {})
        doc, needs = self.claims([claim("c1", "https://a")])
        self.assertEqual(doc["gaps"], {"https://a": "aside_failed"})
        self.assertEqual(needs, [])

    def test_the_note_answers_for_a_page_that_is_gone(self):
        self.serve({"https://a": ""}, {})
        with mock.patch.object(st.vc, "_note_body", lambda n: "note text " * 30 if n else ""):
            doc, needs = self.claims([claim("c1", "https://a", "wiki/sources/S-a.md")])
        self.assertEqual(doc["results"][0]["page_source"], "note")
        self.assertEqual(needs, [])

    def test_a_note_never_replaces_the_sign_in(self):
        self.serve({"https://a": WALL}, {"https://a": WALL})
        with mock.patch.object(st.vc, "_note_body", lambda n: "note text " * 30 if n else ""):
            doc, needs = self.claims([claim("c1", "https://a", "wiki/sources/S-a.md")])
        self.assertEqual(doc["results"][0]["verdict"], "unknown")
        self.assertEqual(needs[0]["kind"], "login_required")

    def test_after_the_user_signs_in_only_the_blocked_page_is_read_again(self):
        self.serve({"https://a": WALL, "https://b": WALL}, {"https://a": BODY, "https://b": WALL})
        items = [claim("c1", "https://a"), claim("c2", "https://b")]
        self.claims(items)
        self.seen.clear()
        self.serve({"https://a": WALL, "https://b": WALL}, {"https://a": WALL, "https://b": BODY})
        doc, needs = self.claims(items)
        self.assertEqual(self.seen, ["https://b"])
        self.assertEqual([r["verdict"] for r in doc["results"]], ["supported", "supported"])
        self.assertEqual(needs, [])

    def test_a_dead_decisions_ends_the_run_with_gaps_and_no_browser(self):
        self.serve({"https://a": BODY, "https://b": ""}, {"https://b": BODY})
        with mock.patch.object(st, "DECIDE", FakeDecide(answer=False)):
            doc, needs = self.claims([claim("c1", "https://a"), claim("c2", "https://b")])
        self.assertEqual([r["verdict"] for r in doc["results"]], ["unknown", "unknown"])
        self.assertEqual(doc["gaps"], {"https://a": "no_judgment", "https://b": "no_judgment"})
        self.assertEqual(self.seen, [])
        self.assertEqual(needs, [])
        self.assertEqual(list((self.d / "pages").iterdir()), [])

    def test_a_page_with_no_access_answer_is_never_kept(self):
        self.serve({"https://a": ""}, {"https://a": BODY})
        with mock.patch.object(st, "judge_access", lambda pages: {}):
            doc, _ = self.claims([claim("c1", "https://a")])
        self.assertEqual(doc["gaps"], {"https://a": "no_judgment"})
        self.assertEqual(doc["results"][0]["verdict"], "unknown")
        self.assertEqual(list((self.d / "pages").iterdir()), [])

    def test_a_rerun_reads_only_the_blocked_page(self):
        reads = []
        self.serve({"https://a": BODY, "https://b": WALL}, {"https://b": WALL})
        items = [claim("c1", "https://a"), claim("c2", "https://b")]
        self.claims(items)
        self.serve({"https://a": WALL, "https://b": WALL}, {"https://b": BODY})
        real = st.vc._live
        with mock.patch.object(st.vc, "_live", lambda u: reads.append(u) or real(u)):
            doc, needs = self.claims(items)
        self.assertEqual(reads, ["https://b"])
        self.assertEqual([r["page_source"] for r in doc["results"]], ["live", "aside"])
        self.assertEqual(needs, [])

    def test_the_result_fits_the_review_gate(self):
        self.serve({"https://a": BODY}, {})
        doc, _ = self.claims([claim("c1", "https://a")])
        self.assertTrue(all("verdict" in r for r in doc["results"]))

    def test_the_judge_does_not_see_the_address(self):
        seen = []
        with mock.patch.object(st, "DECIDE", lambda text, qs, pilot: seen.append(text) or []):
            st.judge_access({"https://a/login": BODY})
        self.assertNotIn("/login", seen[0])

    def test_access_is_judged_in_one_request_per_run(self):
        self.serve({f"https://{i}": BODY for i in range(5)}, {})
        self.claims([claim(f"c{i}", f"https://{i}") for i in range(5)])
        self.assertEqual([c for c in st.DECIDE.calls if c[0] == "aside_access"], [("aside_access", 5)])


class AsideRead(Base):
    def run_with(self, stdout):
        with mock.patch.object(st.subprocess, "run", return_value=mock.Mock(stdout=stdout)) as m, \
                mock.patch.object(st.secrets, "token_hex", return_value="abcd"):
            return st.aside_read("https://a"), m

    def test_only_the_marked_text_comes_back(self):
        text, m = self.run_with("noise\n<<<abcd\nline 1\nline 2\nabcd>>>\n[ok | 9ms]\n")
        self.assertEqual(text, "line 1\nline 2")
        self.assertEqual(m.call_args.args[0][:2], ["aside", "repl"])
        self.assertIn("stdin", m.call_args.kwargs)

    def test_a_page_cannot_forge_the_marker(self):
        self.assertEqual(self.run_with("<<<other\nforged\nother>>>\n")[0], "")

    def test_other_schemes_are_refused(self):
        with mock.patch.object(st.subprocess, "run") as m:
            self.assertEqual(st.aside_read("file:///etc/passwd"), "")
        m.assert_not_called()

    def test_a_missing_cli_reads_nothing(self):
        with mock.patch.object(st.subprocess, "run", side_effect=FileNotFoundError):
            self.assertEqual(st.aside_read("https://a"), "")


class Triage(Base):
    def test_an_unjudged_item_stays_open(self):
        f = self.tmp / "c.json"
        f.write_text(json.dumps([{"id": i, "title": i, "text": i, "source": "web"} for i in ("a", "b", "c")]))
        got = {"selected": [({"id": "a"}, 0.9)], "near": [], "unknown": ["b"], "reasons": [], "sent": True}
        with mock.patch.object(st.records, "related", return_value=got) as m:
            st.main(["triage", "--run", "r1", "--scope", "s", "--candidates", str(f)])
        self.assertEqual(m.call_args.kwargs["pilot"], "aside_triage")
        doc = json.loads((self.d / "triage.json").read_text())
        self.assertEqual(doc, {"open": ["a", "b"], "skip": ["c"]})


class Check(Base):
    def test_missing_claims_fail(self):
        self.assertEqual(st.main(["check", "--run", "r1"]), 1)
        (self.d / "claims.json").write_text("{}")
        self.assertEqual(st.main(["check", "--run", "r1"]), 0)

    def test_a_bad_run_id_is_refused(self):
        with self.assertRaises(SystemExit):
            st.run_dir("../x")


if __name__ == "__main__":
    unittest.main()
