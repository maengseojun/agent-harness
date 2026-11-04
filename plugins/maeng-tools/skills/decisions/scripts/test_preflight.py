import builtins
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decisions_client as dc  # noqa: E402
import preflight as pf  # noqa: E402

DIFF = "diff --git a/x.py b/x.py\n+DIFF_MARKER_7731 = 1\n"
PLAN = """# Plan

Acceptance:
- **AC-1** First criterion
  wrapped onto a second line.
- **AC-2:** Second criterion
AC-3: Third criterion, plain form
* AC-4 Fourth criterion, star bullet
AC-1 is mentioned in prose and is not a criterion.

Verification:
- AC-1: `python3 -m unittest one`
- AC-9: `a command, not a criterion`

Later notes:
- **AC-2** A repeated id keeps its first text.
"""
PLAN_ACS = [("AC-1", "First criterion wrapped onto a second line."), ("AC-2", "Second criterion"),
            ("AC-3", "Third criterion, plain form"), ("AC-4", "Fourth criterion, star bullet")]
REPO_DOCS = Path(__file__).resolve().parents[5] / "docs" / "design"


def ans(name, choice, probs, conf=0.9):
    return {"name": name, "type": "choice", "status": "ok", "choice": choice, "confidence": conf,
            "probabilities": [{"value": v, "probability": p} for v, p in probs.items()]}


def unknown(name, reason="refused"):
    return {"name": name, "type": "choice", "status": "unknown", "reason": reason}


class FakeDecide:
    """Stands in for pf.DECIDE; records every call, answers with `reply(questions)`."""

    def __init__(self, reply=None):
        self.calls = []
        self.reply = reply or (lambda qs: [ans(q["name"], q["choices"][0]["value"], {q["choices"][0]["value"]: 0.8}) for q in qs])

    def __call__(self, input, questions, pilot):
        self.calls.append((input, questions, pilot))
        return self.reply(questions)


def io_open_guard(allow=()):
    """Patch builtins.open and io.open to refuse any write mode except the paths in `allow`."""
    real = io.open

    def guard(file, mode="r", *a, **k):
        if any(c in mode for c in "wax+") and os.fspath(file) not in allow:
            raise AssertionError(f"opened for writing: {file!r} mode {mode!r}")
        return real(file, mode, *a, **k)
    stack = contextlib.ExitStack()
    stack.enter_context(mock.patch.object(builtins, "open", guard))
    stack.enter_context(mock.patch.object(io, "open", guard))
    return stack


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.plan = self.write("plan.md", PLAN)
        self.ev = self.write("ev.txt", "12 tests OK")

    def write(self, name, text):
        p = self.tmp / name
        p.write_text(text, encoding="utf-8")
        return str(p)

    def run_pf(self, argv, decide=None, diff=DIFF):
        """-> (code, stdout, stderr, decide); the diff function is faked, no git is needed."""
        decide = decide or FakeDecide()
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(pf, "DECIDE", decide), mock.patch.object(pf, "_git_diff", lambda b, h: diff), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = pf.main(argv)
        return code, out.getvalue(), err.getvalue(), decide

    @staticmethod
    def rows(out):
        """Markdown table body rows -> list of cell lists."""
        return [[c.strip() for c in re.split(r"(?<!\\)\|", line.strip("|"))] for line in out.splitlines()
                if line.startswith("| ") and not line.startswith("| AC |") and not line.startswith("| # |")]


class ParseAcs(Base):
    def test_both_forms_full_text_unique_ids_and_no_verification_lines(self):
        self.assertEqual(pf.parse_acs(PLAN), PLAN_ACS)  # AC-9 (Verification) and the later AC-2 are not counted

    def test_repo_plans(self):
        # MAE-306's plan defines AC-1..AC-9 since revision R-3; its Verification section repeats them and must not add any
        plans = {"MAE-306-plan.md": [f"AC-{i}" for i in range(1, 10)], "MAE-301-review-kind-plan.md": ["AC-1", "AC-2"]}
        for name, ids in plans.items():
            f = REPO_DOCS / name
            if not f.exists():
                self.skipTest(f"{name} not in this checkout")
            acs = pf.parse_acs(f.read_text(encoding="utf-8"))
            self.assertEqual([n for n, _ in acs], ids, name)
            self.assertTrue(all(len(t) > 20 and not t.startswith("`") for _, t in acs), name)


class AcInput(Base):
    def test_every_input_carries_diff_and_each_evidence_text(self):
        e1, e2 = self.write("e1.txt", "EVIDENCE_ONE_OK 12 tests"), self.write("e2.log", "EVIDENCE_TWO_FAIL")
        _, out, _, d = self.run_pf(["ac", "--plan", self.plan, "--evidence", e1, e2])
        self.assertEqual(len(d.calls), 1)
        text, questions, pilot = d.calls[0]
        self.assertEqual(pilot, "review_preflight")
        for needle in ("DIFF_MARKER_7731", "EVIDENCE_ONE_OK 12 tests", "EVIDENCE_TWO_FAIL", "Fourth criterion, star bullet"):
            self.assertIn(needle, text)
        self.assertLess(text.index("First criterion"), text.index("DIFF_MARKER_7731"))
        self.assertLess(text.index("DIFF_MARKER_7731"), text.index("EVIDENCE_ONE_OK"))
        self.assertEqual([q["name"] for q in questions], [n for n, _ in PLAN_ACS])
        q = questions[1]
        self.assertEqual(q["type"], "choice")
        self.assertEqual(q["instructions"], "Criterion AC-2: Second criterion\n"
                                            "Judge only from the plan, diff and verification output above.")
        self.assertEqual([c["value"] for c in q["choices"]], ["met", "unmet", "unclear"])
        self.assertEqual(q["choices"][0]["description"], "The diff and the verification output show this criterion is satisfied.")

    def test_evidence_flag_can_repeat(self):
        e1, e2 = self.write("e1.txt", "EVIDENCE_ONE_OK"), self.write("e2.txt", "EVIDENCE_TWO_OK")
        _, _, _, d = self.run_pf(["ac", "--plan", self.plan, "--evidence", e1, "--evidence", e2])
        self.assertTrue("EVIDENCE_ONE_OK" in d.calls[0][0] and "EVIDENCE_TWO_OK" in d.calls[0][0])

    def test_no_evidence_sends_nothing(self):
        empty = self.write("empty.txt", " \n")
        for argv in (["ac", "--plan", self.plan], ["ac", "--plan", self.plan, "--evidence", empty]):
            d = FakeDecide()
            with self.assertRaises(SystemExit) as e:
                self.run_pf(argv, d)
            self.assertEqual(e.exception.code, 2)
            self.assertEqual(d.calls, [])

    def test_truncated_diff_says_so(self):
        _, _, _, d = self.run_pf(["ac", "--plan", self.plan, "--evidence", self.ev, "--max-diff-chars", "10"], diff="a" * 10 + "ZZZZ")
        text = d.calls[0][0]
        self.assertIn("diff truncated: the first 10 of 14 characters", text)
        self.assertNotIn("ZZZZ", text)

    def test_an_empty_diff_sends_nothing(self):
        code, _, err, d = self.run_pf(["ac", "--plan", self.plan, "--evidence", self.ev], diff="  \n")
        self.assertEqual((code, d.calls), (0, []))
        self.assertIn("nothing was sent", err)

    def test_a_diff_limit_below_one_is_an_argument_error(self):
        d = FakeDecide()
        with self.assertRaises(SystemExit) as e:
            self.run_pf(["ac", "--plan", self.plan, "--evidence", self.ev, "--max-diff-chars", "0"], d)
        self.assertEqual((e.exception.code, d.calls), (2, []))

    def test_git_failure_sends_nothing_and_still_exits_zero(self):
        d, out, err = FakeDecide(), io.StringIO(), io.StringIO()
        boom = mock.Mock(side_effect=RuntimeError("bad revision"))
        with mock.patch.object(pf, "DECIDE", d), mock.patch.object(pf, "_git_diff", boom), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = pf.main(["ac", "--plan", self.plan, "--evidence", self.ev])
        self.assertEqual((code, d.calls), (0, []))
        self.assertIn("bad revision", err.getvalue())

    def test_wrong_arguments_exit_2(self):
        for argv in (["ac"], ["ac", "--plan", str(self.tmp / "missing.md")], ["ac", "--plan", self.plan, "--base", "--output=x"],
                     ["ac", "--plan", self.plan, "--evidence", str(self.tmp / "missing.txt")],
                     ["triage", "--findings", self.plan, "--evidence", self.ev]):  # not JSON
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
                self.run_pf(argv)
            self.assertEqual(cm.exception.code, 2)


class Secrets(Base):
    SECRETS = ("sk" "-test1234567890abcdef", "gh" "p_abcdefghijklmnop1234")

    def run_real_client(self, argv, diff, post_calls):
        """Real decisions_client.decide with only its _post faked."""
        work = self.tmp / "work"
        work.mkdir(exist_ok=True)
        ledger = self.tmp / "led" / "ledger.jsonl"

        def fake_post(url, body, headers, timeout):
            post_calls.append(body)
            return {"answers": [ans("AC-1", "met", {"met": 0.9, "unmet": 0.05, "unclear": 0.05})]}

        env = {"OPENAI_API_KEY": "sk-dummy-ENVKEY0123456789", "MAENG_DECISIONS_MODEL": "gpt-6-luna", "MAENG_DECISIONS_LEDGER": str(ledger)}
        out, cwd = io.StringIO(), os.getcwd()
        self.addCleanup(os.chdir, cwd)
        os.chdir(work)
        with mock.patch.dict(os.environ, env), mock.patch.object(dc, "_post", fake_post), \
                mock.patch.object(pf, "_git_diff", lambda b, h: diff), io_open_guard(allow={str(ledger)}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            os.environ.pop("MAENG_DECISIONS", None)
            self.assertIs(pf.DECIDE, dc.decide)
            self.assertEqual(pf.main(argv), 0)
        self.assertEqual(os.listdir(work), [])
        self.assertEqual(len(ledger.read_text().splitlines()), 1)
        return out.getvalue()

    def test_planted_secrets_never_reach_the_request_body(self):
        s1, s2 = self.SECRETS
        diff = f"{DIFF}+OPENAI_API_KEY={s1}\n+note: {s2}\n"
        plan = self.write("plan1.md", f"- **AC-1** Works.\n\nNote: token {s2}\n")
        ev = self.write("ev.txt", f"export OPENAI_API_KEY={s1}\nEVIDENCE_OK_5512\n")
        posts = []
        out = self.run_real_client(["ac", "--plan", plan, "--evidence", ev], diff, posts)
        self.assertEqual(len(posts), 1)  # a request really went out
        body = json.dumps(posts[0], ensure_ascii=False)
        for secret in (s1, s2, "1234567890abcdef", "abcdefghijklmnop1234", "ENVKEY0123456789"):
            self.assertNotIn(secret, body)
        self.assertIn("[REDACTED]", body)
        for kept in ("DIFF_MARKER_7731", "EVIDENCE_OK_5512"):
            self.assertIn(kept, body)
        self.assertIn("| AC-1 | met | 0.90 | 0.05 |", out)

    def body_for_diff(self, diff):
        posts = []
        self.run_real_client(["ac", "--plan", self.plan, "--evidence", self.ev], diff, posts)
        self.assertEqual(len(posts), 1)
        return json.dumps(posts[0])

    def test_a_block_secret_never_reaches_the_request_body(self):
        self.assertNotIn("OPAQUEvalue", self.body_for_diff("+client_secret: |-\n+    OPAQUEvalue0123456789\n+next: 1\n"))

    def test_a_quoted_next_line_secret_never_reaches_the_request_body(self):
        self.assertNotIn("OPAQUEvalue", self.body_for_diff('+client_secret:\n+  "OPAQUEvalue0123456789"\n+next: 1\n'))

    def test_a_cut_through_a_secret_leaves_no_prefix(self):
        s = self.SECRETS[1]
        diff = "a" * 19 + " " + s  # the cut at 26 falls inside the token
        posts = []
        self.run_real_client(["ac", "--plan", self.plan, "--evidence", self.ev, "--max-diff-chars", "26"], diff, posts)
        self.assertEqual(len(posts), 1)
        body = json.dumps(posts[0])
        self.assertIn("diff truncated", body)
        self.assertNotIn("ghp_", body)


class Verdicts(Base):
    def test_unknown_missing_and_off_list_answers_print_unknown(self):
        plan = self.write("p5.md", "".join(f"- **AC-{i}** crit {i}\n" for i in range(1, 6)))
        reply = lambda qs: [  # noqa: E731
            unknown("AC-1"),                                                         # refused
            ans("AC-2", "maybe", {"maybe": 0.9}),                                    # off the list
            ans("AC-3", "unmet", {"met": 0.1, "unmet": 0.8, "unclear": 0.1}, 0.75),  # a real verdict
            {**unknown("AC-4", "timeout"), "choice": "met"}]                         # a stray choice on an unknown answer
        # AC-5 is not answered at all
        code, out, err, _ = self.run_pf(["ac", "--plan", plan, "--evidence", self.ev], FakeDecide(reply))
        self.assertEqual(code, 0)
        rows = {r[0]: r for r in self.rows(out)}
        self.assertEqual([rows[f"AC-{i}"][1] for i in range(1, 6)], ["unknown", "unknown", "unmet", "unknown", "unknown"])
        self.assertEqual(rows["AC-3"], ["AC-3", "unmet", "0.10", "0.80", "0.75"])
        self.assertEqual(rows["AC-1"][2:], ["-", "-", "-"])
        self.assertIn("advisory only: 1 unmet, 0 unclear, 4 unknown", out)
        self.assertIn("refused", err)


class Triage(Base):
    def test_questions_names_choices_table_and_input(self):
        cur = self.write("cur.json", json.dumps({"verdict": "fail", "findings": [
            {"severity": "high", "title": "Gate bypass | via env", "body": "BODY_ONE", "file": "a.py", "line": 3},
            {"title": "Only a title"}]}))
        prev = self.write("round1.json", json.dumps({"findings": [{"severity": "low", "title": "PREV_TITLE", "body": "PREV_BODY"}]}))
        probs = {"f1_repeat": ("repeat", {"new": 0.2, "repeat": 0.8}), "f1_cause": ("bypass", {"this_change": 0.2, "pre_existing": 0.1, "bypass": 0.7}),
                 "f2_repeat": ("new", {"new": 0.9, "repeat": 0.1}), "f2_cause": ("pre_existing", {"this_change": 0.3, "pre_existing": 0.6, "bypass": 0.1})}
        reply = lambda qs: [ans(q["name"], probs[q["name"]][0], probs[q["name"]][1]) for q in qs]  # noqa: E731
        _, out, _, d = self.run_pf(["triage", "--findings", cur, "--evidence", self.ev, "--previous", prev], FakeDecide(reply))
        text, questions, pilot = d.calls[0]
        self.assertEqual((len(d.calls), pilot), (1, "review_preflight"))
        self.assertEqual([q["name"] for q in questions], ["f1_repeat", "f1_cause", "f2_repeat", "f2_cause"])
        self.assertEqual([[c["value"] for c in q["choices"]] for q in questions[:2]],
                         [["new", "repeat"], ["this_change", "pre_existing", "bypass"]])
        self.assertEqual(questions[0]["choices"][1]["description"],
                         "The same problem was raised in a previous round, even if worded differently.")
        self.assertEqual(questions[1]["choices"][2]["description"], "A way around an approval, review or ship gate.")
        self.assertTrue(all(q["type"] == "choice" for q in questions))
        for needle in ("DIFF_MARKER_7731", "BODY_ONE", "Only a title", "PREV_TITLE", "PREV_BODY", prev):
            self.assertIn(needle, text)
        rows = self.rows(out)
        self.assertEqual(rows[0], ["1", "high", "Gate bypass \\| via env", "repeat (0.80)", "bypass (0.70)"])
        self.assertEqual(rows[1], ["2", "?", "Only a title", "new (0.90)", "pre_existing (0.60)"])
        self.assertIn("advisory only: 1 repeat, 1 pre_existing, 1 bypass, 0 unknown", out)

    def test_no_previous_round_and_unknown_answer(self):
        cur = self.write("cur.json", json.dumps({"findings": [{"title": "T"}]}))
        reply = lambda qs: [unknown("f1_repeat"), ans("f1_cause", "other", {"other": 1.0})]  # noqa: E731
        _, out, _, d = self.run_pf(["triage", "--findings", cur, "--evidence", self.ev], FakeDecide(reply))
        self.assertIn("No previous round was supplied", d.calls[0][0])
        self.assertEqual(self.rows(out)[0][3:], ["unknown", "unknown"])

    def test_triage_carries_the_verification_output_and_needs_it(self):
        cur = self.write("cur.json", json.dumps({"findings": [{"title": "t", "severity": "high"}]}))
        _, _, _, d = self.run_pf(["triage", "--findings", cur, "--evidence", self.ev], FakeDecide(lambda qs: []))
        self.assertIn("=== VERIFICATION OUTPUT ===\n--- ", d.calls[0][0])
        self.assertIn("12 tests OK", d.calls[0][0])
        empty, d = self.write("empty.txt", " "), FakeDecide()
        for argv in (["triage", "--findings", cur], ["triage", "--findings", cur, "--evidence", empty]):
            with self.assertRaises(SystemExit):
                self.run_pf(argv, d)
        self.assertEqual(d.calls, [])

    def test_no_findings_sends_nothing(self):
        cur = self.write("cur.json", json.dumps({"verdict": "pass", "findings": []}))
        code, out, _, d = self.run_pf(["triage", "--findings", cur, "--evidence", self.ev])
        self.assertEqual((code, d.calls), (0, []))
        self.assertIn("no findings", out)


class NoFileWrites(Base):
    def test_neither_subcommand_writes_a_file(self):
        findings = self.write("f.json", json.dumps({"findings": [{"title": "T", "body": "B"}]}))
        ev = self.write("ev.txt", "output")
        work, cwd = self.tmp / "empty", os.getcwd()
        work.mkdir()
        self.addCleanup(os.chdir, cwd)
        os.chdir(work)
        with io_open_guard():
            with self.assertRaises(AssertionError):  # the guard itself is live, not vacuous
                open(work / "x", "w")
            with self.assertRaises(AssertionError):
                Path(work / "y").write_text("x")
            self.run_pf(["ac", "--plan", self.plan, "--evidence", ev])
            self.run_pf(["triage", "--findings", findings, "--evidence", self.ev, "--previous", findings])
        self.assertEqual(os.listdir(work), [])


if __name__ == "__main__":
    unittest.main()
