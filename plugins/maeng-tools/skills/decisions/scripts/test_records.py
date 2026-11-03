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
import records as rec  # noqa: E402


def cand(id, text="body", **kw):
    return {"id": id, "title": f"title {id}", "text": text, "source": "linear-maeng", "date": "2026-11-01", **kw}


def pred(name, p):
    return {"name": name, "type": "predicate", "status": "ok", "probability": p}


def unknown(name, reason="refused"):
    return {"name": name, "type": "predicate", "status": "unknown", "reason": reason}


def choice(choice, probs):
    return {"name": "duplicate_of", "type": "choice", "status": "ok", "choice": choice, "confidence": 0.9,
            "probabilities": [{"value": v, "probability": p} for v, p in probs.items()]}


class FakeDecide:
    """Stands in for rec.DECIDE: records every call and answers with reply(questions)."""

    def __init__(self, reply):
        self.calls = []
        self.reply = reply

    def __call__(self, input, questions, pilot):
        self.calls.append((input, questions, pilot))
        return self.reply(questions)

    def sent(self):
        return json.dumps(self.calls, ensure_ascii=False)


def by_id(answers):
    """reply(questions): answers is {item id: probability | None (unknown) | 'missing'}; an id not listed is unknown."""
    def reply(questions):
        out = []
        for q in questions:
            id_ = re.search(r"item \[(.+?)\] ", q["instructions"]).group(1)
            v = answers.get(id_)
            if v == "missing":
                continue
            out.append(unknown(q["name"]) if v is None else pred(q["name"], v))
        return out
    return reply


@contextlib.contextmanager
def no_writes():
    """Opening anything for writing raises."""
    real = io.open

    def guard(file, mode="r", *a, **k):
        if any(c in mode for c in "wax+"):
            raise AssertionError(f"opened for writing: {file!r}")
        return real(file, mode, *a, **k)
    with mock.patch.object(builtins, "open", guard), mock.patch.object(io, "open", guard):
        yield


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.cwd = self.tmp / "cwd"  # empty, so any file the script writes shows up
        self.cwd.mkdir()
        old = os.getcwd()
        os.chdir(self.cwd)
        self.addCleanup(os.chdir, old)

    def cfile(self, cands):
        p = self.tmp / "candidates.json"
        p.write_text(json.dumps(cands, ensure_ascii=False), encoding="utf-8")
        return str(p)

    def cli(self, argv, fake):
        """-> (exit code, stdout); decide is replaced by `fake`; a SystemExit gives its code."""
        out = io.StringIO()
        with mock.patch.object(rec, "DECIDE", fake), contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            try:
                code = rec.main(argv)
            except SystemExit as e:
                code = e.code
        return code, out.getvalue()


class RefusalTests(Base):
    ETA = [
        ("world eta", cand("W1", "ETA_TEXT_1", world="eta")),
        ("world ETA, spaced", cand("W2", "ETA_TEXT_2", world=" ETA ")),
        ("path eta/", cand("P1", "ETA_TEXT_3", path="eta/Notes/x.md", source="obsidian")),
        ("path ./eta/", cand("P2", "ETA_TEXT_4", path="./eta/x.md", source="obsidian")),
        ("path ETA/", cand("P3", "ETA_TEXT_5", path="ETA/x.md", source="obsidian")),
        ("path through ..", cand("P4", "ETA_TEXT_6", path="wiki/../eta/x.md", source="obsidian")),
        ("absolute vault path", cand("P5", "ETA_TEXT_7", path="/Users/me/Documents/Obsidian Vault/eta/x.md", source="obsidian")),
        ("imported eta notion", cand("P6", "ETA_TEXT_8", path="wiki/sources/imported/notion/Eta-20261014/eta Docs/x.md", source="obsidian")),
        ("imported eta linear", cand("P7", "ETA_TEXT_9", path="wiki/sources/imported/linear/Endix/END-1.md", source="obsidian")),
        ("eta checkout", cand("P8", "ETA_TEXT_10", path="/Users/me/Documents/Project/eta_v1/README.md", source="obsidian")),
        ("source notion-eta", cand("S1", "ETA_TEXT_11", source="notion-eta")),
        ("source linear-eta", cand("S2", "ETA_TEXT_12", source="linear-eta")),
        ("source eta", cand("S3", "ETA_TEXT_13", source="eta")),
        ("source Notion_ETA", cand("S4", "ETA_TEXT_14", source="Notion_ETA")),
        ("source notionEta", cand("S5", "ETA_TEXT_15", source="notionEta")),
    ]
    PERSONAL = [
        cand("K1", source="linear-maeng"), cand("K2", source="notion-maeng", world="personal"),
        cand("K3", source="obsidian", path="wiki/concepts/K-DESIGN.md"), cand("K4", source="beta"),
        cand("K5", source="meta-ads", path="wiki/notes/zeta-planning.md"), cand("K6", source="notion"),
    ]

    def test_every_eta_variant_is_dropped_with_its_reason(self):
        items, dropped = rec.prepare([c for _, c in self.ETA] + self.PERSONAL)
        self.assertEqual([i["id"] for i in items], ["K1", "K2", "K3", "K4", "K5", "K6"])
        self.assertEqual([d[0] for d in dropped], [c["id"] for _, c in self.ETA])
        self.assertEqual(dropped[0][1], "world eta")
        self.assertEqual(dropped[2][1], "path in an eta area")
        self.assertEqual(dropped[10][1], "source eta")

    def test_dropped_items_never_appear_in_a_request(self):
        for command, call in (("related", lambda f: rec.related("the task", f.cands, decide=f)),
                              ("cleanup", lambda f: rec.cleanup(f.cands, decide=f)),
                              ("duplicate", lambda f: rec.duplicate("a new thing", f.cands, decide=f))):
            fake = FakeDecide(lambda qs: [unknown(q["name"]) for q in qs])
            fake.cands = [c for _, c in self.ETA] + self.PERSONAL
            call(fake)
            self.assertEqual(len(fake.calls), 1, command)
            sent = fake.sent()
            for label, c in self.ETA:
                self.assertNotIn(c["id"], sent, f"{command}: {label} id")
                self.assertNotIn(c["text"], sent, f"{command}: {label} text")
                self.assertNotIn(c["title"], sent, f"{command}: {label} title")
            self.assertIn("title K1", sent)  # the personal items did go

    def test_when_every_item_is_eta_nothing_is_sent_and_the_exit_is_zero(self):
        cands = [c for _, c in self.ETA]
        for argv in (["related", "--task", "t"], ["cleanup"], ["duplicate", "--new", "n"]):
            fake = FakeDecide(lambda qs: self.fail("decide must not be called"))
            code, out = self.cli(argv + ["--candidates", self.cfile(cands)], fake)
            self.assertEqual((code, fake.calls), (0, []), argv)
            self.assertIn("nothing was sent", out)
            for _, c in self.ETA:
                self.assertIn(f"dropped, not sent: {c['id']} (", out)

    def test_an_empty_list_sends_nothing_either(self):
        fake = FakeDecide(lambda qs: self.fail("decide must not be called"))
        self.assertEqual(self.cli(["cleanup", "--candidates", self.cfile([])], fake)[0], 0)
        self.assertEqual(fake.calls, [])

    def test_malformed_candidates_are_refused(self):
        for bad in ([cand("a"), cand("a")], [cand("")], [{"title": "no id"}], ["x"], {"id": "a"}):
            with self.assertRaises(ValueError, msg=bad):
                rec.prepare(bad)
        code, _ = self.cli(["cleanup", "--candidates", self.cfile([cand("a"), cand("a")])], FakeDecide(lambda qs: []))
        self.assertEqual(code, 2)


class PrivateTests(Base):
    def test_private_spans_never_reach_the_request(self):
        cands = [cand("a", "keep <private>SECRET_ONE</private> tail", title="T <private>SECRET_TWO</private> end"),
                 cand("b", "fine start <private>SECRET_THREE and no closing tag, SECRET_FOUR"),
                 cand("c", "<private>outer <private>SECRET_FIVE</private> SECRET_SIX</private>after")]
        for call in (lambda f: rec.related("task <private>SECRET_SEVEN</private>", cands, decide=f),
                     lambda f: rec.cleanup(cands, decide=f),
                     lambda f: rec.duplicate("new <private>SECRET_SEVEN</private> item", cands, decide=f)):
            fake = FakeDecide(lambda qs: [unknown(q["name"]) for q in qs])
            call(fake)
            sent = fake.sent()
            self.assertNotRegex(sent, "SECRET_")
            self.assertNotIn("private>", sent)
            self.assertIn("[private omitted]", sent)
            self.assertIn("keep [private omitted] tail", sent)
            self.assertIn("after", sent)

    def test_text_is_cut_after_stripping(self):
        # cut first and the private span would be left open at 4000 chars, so "keep" would vanish
        text = "<private>" + "x" * 5000 + "</private>keep"
        items, _ = rec.prepare([cand("a", text)])
        self.assertEqual(items[0]["text"], "[private omitted]keep")
        items, _ = rec.prepare([cand("a", "0123456789" * 3)], max_item_chars=12)
        self.assertEqual(items[0]["text"], "012345678901")
        items, _ = rec.prepare([cand("a", "y" * 9000)])
        self.assertEqual(len(items[0]["text"]), 4000)

    def test_the_cli_cuts_with_max_item_chars(self):
        fake = FakeDecide(lambda qs: [unknown(q["name"]) for q in qs])
        self.cli(["cleanup", "--candidates", self.cfile([cand("a", "z" * 50)]), "--max-item-chars", "7"], fake)
        self.assertIn("\nzzzzzzz", fake.calls[0][0])
        self.assertNotIn("zzzzzzzz", fake.calls[0][0])


class RelatedTests(Base):
    def test_request_shape(self):
        fake = FakeDecide(by_id({"MAE-1": 0.9}))
        rec.related("Plan the trial", [cand("MAE-1", "first text"), cand("wiki/a b/Ä.md", "second", title="Ä", source="obsidian", date=None)],
                    decide=fake)
        text, qs, pilot = fake.calls[0]
        self.assertEqual(pilot, "records")
        self.assertEqual(text, "Task:\nPlan the trial\n\nItems:\n[MAE-1] title MAE-1 (linear-maeng, 2026-11-01)\nfirst text"
                               "\n\n[wiki/a b/Ä.md] Ä (obsidian, undated)\nsecond")
        self.assertEqual([q["type"] for q in qs], ["predicate", "predicate"])
        self.assertEqual(qs[0]["instructions"], "Is item [MAE-1] relevant to the task above, so that someone doing the task should read it?")
        self.assertEqual(qs[1]["instructions"], "Is item [wiki/a b/Ä.md] relevant to the task above, so that someone doing the task should read it?")

    def test_question_names_are_safe_and_unique(self):
        fake = FakeDecide(lambda qs: [])
        rec.related("t", [cand("a/b"), cand("a_b"), cand("한글 노트"), cand("x" * 300)], decide=fake)
        names = [q["name"] for q in fake.calls[0][1]]
        self.assertEqual(len(set(names)), 4)
        for n in names:
            self.assertRegex(n, r"^[A-Za-z0-9_-]{1,64}$")

    def test_selected_near_misses_and_unknown(self):
        probs = {"a": 0.9, "b": 0.4, "c": 0.7, "d": 0.1, "e": 0.45, "f": 0.3, "i": 0.5, "g": None, "h": "missing"}
        r = rec.related("t", [cand(k) for k in "abcdefghi"], 0.5, decide=FakeDecide(by_id(probs)))
        self.assertEqual([(i["id"], p) for i, p in r["selected"]], [("a", 0.9), ("c", 0.7), ("i", 0.5)])  # 0.5 is selected
        self.assertEqual([(i["id"], p) for i, p in r["near"]], [("e", 0.45), ("b", 0.4), ("f", 0.3)])  # top 3 below
        self.assertEqual(r["unknown"], ["g", "h"])
        self.assertEqual(r["reasons"], ["no verdict", "refused"])

    def test_unknown_is_never_selected_whatever_it_carries(self):
        def reply(qs):
            return [{"name": qs[0]["name"], "type": "predicate", "status": "unknown", "reason": "http_500", "probability": 0.99},
                    {"name": qs[1]["name"], "type": "predicate", "status": "ok", "probability": 1.5},
                    {"name": qs[2]["name"], "type": "predicate", "status": "ok", "probability": "0.9"},
                    {"name": qs[3]["name"], "type": "predicate", "status": "ok", "probability": True},
                    {"name": qs[4]["name"], "type": "predicate", "status": "ok", "probability": float("nan")},
                    {"name": qs[5]["name"], "type": "predicate", "status": "ok"}]
        r = rec.related("t", [cand(k) for k in "abcdef"], 0.0, decide=FakeDecide(reply))
        self.assertEqual((r["selected"], r["near"]), ([], []))
        self.assertEqual(r["unknown"], list("abcdef"))

    def test_an_unknown_answer_from_the_real_client_is_not_selected_and_sends_nothing(self):
        env = {"MAENG_DECISIONS": "off", "MAENG_DECISIONS_LEDGER": str(self.tmp / "ledger.jsonl")}
        with mock.patch.dict(os.environ, env), mock.patch.object(dc, "_post", side_effect=AssertionError("request sent")):
            r = rec.related("t", [cand("a"), cand("b")])
        self.assertEqual((r["selected"], r["near"], r["unknown"], r["reasons"]), ([], [], ["a", "b"], ["off"]))

    def test_cli_output(self):
        fake = FakeDecide(by_id({"a": 0.9, "b": 0.4, "c": None, "d": 0.7}))
        cands = [cand("a", source="linear"), cand("b"), cand("c"), cand("d"), cand("eta1", world="eta")]
        code, out = self.cli(["related", "--task", "t", "--candidates", self.cfile(cands)], fake)
        self.assertEqual(code, 0)
        self.assertEqual(out, "dropped, not sent: eta1 (world eta)\n"
                              "selected (probability >= 0.5), read these:\n"
                              "  0.90 [a] title a (linear, 2026-11-01)\n"
                              "  0.70 [d] title d (linear-maeng, 2026-11-01)\n"
                              "near misses (below the threshold):\n"
                              "  0.40 [b] title b (linear-maeng, 2026-11-01)\n"
                              "unknown, not judged: c\n")
        code, out = self.cli(["related", "--task", "t", "--candidates", self.cfile(cands), "--threshold", "0.8"], fake)
        self.assertEqual(out, "dropped, not sent: eta1 (world eta)\n"
                              "selected (probability >= 0.8), read these:\n"
                              "  0.90 [a] title a (linear, 2026-11-01)\n"
                              "near misses (below the threshold):\n"
                              "  0.70 [d] title d (linear-maeng, 2026-11-01)\n"
                              "  0.40 [b] title b (linear-maeng, 2026-11-01)\n"
                              "unknown, not judged: c\n")

    def test_no_selection_prints_none(self):
        code, out = self.cli(["related", "--task", "t", "--candidates", self.cfile([cand("a")])], FakeDecide(by_id({"a": 0.1})))
        self.assertIn("read these:\n  none\nnear misses", out)

    def test_more_than_400_candidates_is_an_error_before_any_request(self):
        fake = FakeDecide(lambda qs: self.fail("decide must not be called"))
        with self.assertRaises(ValueError):
            rec.related("t", [cand(f"i{n}") for n in range(401)], decide=fake)
        self.assertEqual(self.cli(["related", "--task", "t", "--candidates", self.cfile([cand(f"i{n}") for n in range(401)])], fake)[0], 2)


class DuplicateTests(Base):
    def test_choices_are_the_candidate_ids_plus_none(self):
        fake = FakeDecide(lambda qs: [choice("none", {"none": 0.9})])
        rec.duplicate("A new\nthing", [cand("MAE-1", title="One"), cand("wiki/x.md", title=""), cand("MAE-3", world="eta")], decide=fake)
        text, qs, pilot = fake.calls[0]
        self.assertEqual(pilot, "records")
        self.assertEqual(text, "New item:\nA new\nthing\n\nExisting items:\n[MAE-1] One (linear-maeng, 2026-11-01)\nbody"
                               "\n\n[wiki/x.md]  (linear-maeng, 2026-11-01)\nbody")
        self.assertEqual(len(qs), 1)
        q = qs[0]
        self.assertEqual((q["type"], q["name"]), ("choice", "duplicate_of"))
        self.assertEqual(q["choices"], [{"value": "MAE-1", "description": "One"}, {"value": "wiki/x.md", "description": "wiki/x.md"},
                                        {"value": "none", "description": "None of the items is the same thing as the new one."}])
        self.assertEqual(q["instructions"], "Is the new item described above the same thing as one of the existing items "
                                            "(a duplicate that should be updated instead of created)?")

    def test_a_named_candidate_is_printed_with_the_runner_up(self):
        fake = FakeDecide(lambda qs: [choice("MAE-2", {"MAE-1": 0.07, "MAE-2": 0.86, "none": 0.05, "ghost": 0.5})])
        cands = [cand("MAE-1", title="One"), cand("MAE-2", title="Two")]
        code, out = self.cli(["duplicate", "--new", "n", "--candidates", self.cfile(cands)], fake)
        self.assertEqual(code, 0)
        self.assertEqual(out, "duplicate candidate: [MAE-2] Two (probability 0.86)\n"
                              "runner-up: [MAE-1] One (probability 0.07)\n"  # "ghost" is not on the list, so it is ignored
                              "open it before deciding\n")

    def test_none_chosen_names_no_duplicate(self):
        fake = FakeDecide(lambda qs: [choice("none", {"none": 0.9, "MAE-1": 0.04})])
        code, out = self.cli(["duplicate", "--new", "n", "--candidates", self.cfile([cand("MAE-1", title="One")])], fake)
        self.assertEqual(out, "no duplicate named: none (probability 0.90)\nrunner-up: [MAE-1] One (probability 0.04)\n")

    def test_unknown_or_off_list_is_no_judgment(self):
        bad = [lambda qs: [{"name": "duplicate_of", "type": "choice", "status": "unknown", "reason": "http_500"}],
               lambda qs: [{"name": "duplicate_of", "type": "choice", "status": "unknown", "reason": "off", "choice": "MAE-1"}],
               lambda qs: [choice("ghost", {"ghost": 0.9})],
               lambda qs: [choice("", {})],
               lambda qs: [{"name": "other", "type": "choice", "status": "ok", "choice": "MAE-1"}],
               lambda qs: []]
        for reply in bad:
            r = rec.duplicate("n", [cand("MAE-1")], decide=FakeDecide(reply))
            self.assertEqual((r["status"], r["chosen"]), ("unknown", None))
            code, out = self.cli(["duplicate", "--new", "n", "--candidates", self.cfile([cand("MAE-1")])], FakeDecide(reply))
            self.assertEqual((code, out), (0, "no judgment (unknown)\n"))

    def test_the_real_client_off_gives_no_judgment(self):
        env = {"MAENG_DECISIONS": "off", "MAENG_DECISIONS_LEDGER": str(self.tmp / "ledger.jsonl")}
        with mock.patch.dict(os.environ, env), mock.patch.object(dc, "_post", side_effect=AssertionError("request sent")):
            self.assertEqual(rec.duplicate("n", [cand("MAE-1")])["status"], "unknown")

    def test_at_most_254_candidates(self):
        fake = FakeDecide(lambda qs: [choice("none", {"none": 1.0})])
        eta = [cand(f"e{n}", world="eta") for n in range(5)]
        r = rec.duplicate("n", [cand(f"i{n}") for n in range(254)] + eta, decide=fake)  # the limit counts what is sent
        self.assertEqual((r["status"], len(fake.calls[0][1][0]["choices"])), ("ok", 255))
        over = FakeDecide(lambda qs: self.fail("decide must not be called"))
        with self.assertRaisesRegex(ValueError, "254"):
            rec.duplicate("n", [cand(f"i{n}") for n in range(255)], decide=over)
        code, _ = self.cli(["duplicate", "--new", "n", "--candidates", self.cfile([cand(f"i{n}") for n in range(255)])], over)
        self.assertEqual((code, over.calls), (2, []))

    def test_the_id_none_is_reserved(self):
        with self.assertRaises(ValueError):
            rec.duplicate("n", [cand("none")], decide=FakeDecide(lambda qs: []))


class CleanupTests(Base):
    def test_request_and_suggestions(self):
        fake = FakeDecide(by_id({"a": 0.95, "b": 0.6, "c": 0.59, "d": None, "e": 0.8}))
        cands = [cand(k) for k in "abcde"] + [cand("x", world="eta")]
        code, out = self.cli(["cleanup", "--candidates", self.cfile(cands)], fake)
        text, qs, pilot = fake.calls[0]
        self.assertEqual(pilot, "records")
        self.assertTrue(text.startswith("Items:\n[a] title a (linear-maeng, 2026-11-01)\nbody\n\n[b] "))
        self.assertEqual(qs[0]["instructions"], "According to its own text and the other items listed, is item [a] superseded "
                                                "by a newer item or already done, so it can be archived or closed?")
        self.assertEqual(out, "dropped, not sent: x (world eta)\n"
                              "cleanup suggestions (probability >= 0.6); suggestions only, nothing is archived or closed:\n"
                              "  0.95 [a] title a (linear-maeng, 2026-11-01)\n"
                              "  0.80 [e] title e (linear-maeng, 2026-11-01)\n"
                              "  0.60 [b] title b (linear-maeng, 2026-11-01)\n"
                              "unknown, not judged: d\n")

    def test_unknown_is_never_a_suggestion(self):
        r = rec.cleanup([cand("a"), cand("b")], 0.0, decide=FakeDecide(lambda qs: [unknown(q["name"]) for q in qs]))
        self.assertEqual((r["suggested"], r["unknown"]), ([], ["a", "b"]))


class NoWriteTests(Base):
    def test_no_command_writes_a_file(self):
        cands = [cand("a", "text <private>x</private>"), cand("b"), cand("c", world="eta")]
        path = self.cfile(cands)
        for argv in (["related", "--task", "t"], ["cleanup"], ["duplicate", "--new", "n"]):
            fake = FakeDecide(lambda qs: [unknown(q["name"]) for q in qs] if qs[0]["type"] == "predicate"
                              else [choice("none", {"none": 1.0})])
            with no_writes():
                code, _ = self.cli(argv + ["--candidates", path], fake)
            self.assertEqual(code, 0, argv)
        self.assertEqual(os.listdir(self.cwd), [])  # nothing next to the caller either


class ArgumentTests(Base):
    def test_bad_arguments_exit_2_and_send_nothing(self):
        path = self.cfile([cand("a")])
        fake = FakeDecide(lambda qs: self.fail("decide must not be called"))
        for argv in (["related", "--task", "t", "--candidates", path, "--threshold", "1.5"],
                     ["cleanup", "--candidates", path, "--max-item-chars", "0"],
                     ["related", "--task", "t", "--candidates", str(self.tmp / "missing.json")],
                     ["duplicate", "--candidates", path]):
            self.assertEqual(self.cli(argv, fake)[0], 2, argv)
        bad = self.tmp / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        self.assertEqual(self.cli(["cleanup", "--candidates", str(bad)], fake)[0], 2)
        self.assertEqual(fake.calls, [])


if __name__ == "__main__":
    unittest.main()
