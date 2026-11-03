import builtins
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decisions_client as dc  # noqa: E402
import records as rec  # noqa: E402
import related_eval as rev  # noqa: E402


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
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return path


def note(root, rel, body, fm=None):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text((f"---\n{fm}\n---\n" if fm is not None else "") + body, encoding="utf-8")


LEAKS = ["ETA_BODY_1", "ETA_BODY_2", "ETA_BODY_3", "ETA_BODY_4", "ETA_BODY_5", "ETA_BODY_6", "ETA_BODY_7",
         "RAW_BODY", "TEMPLATE_BODY", "PROJECT_BODY", "PRIVATE_SECRET"]
ALPHA = ("Alpha body text. [[Beta]] and [[Gamma|alias]] and [[Delta#Heading]] and [[Alpha]] itself and [[Missing]] "
         "and [[Dup]] and [[EtaWorld]] and [[EtaQuoted]] and [[EtaDir]] and [[wiki/concepts/Epsilon.md]] "
         "and <private>see [[Zeta]] PRIVATE_SECRET</private> the end.")


def make_vault(root):
    n = lambda rel, body, fm=None: note(root, rel, body, fm)
    n("wiki/concepts/Alpha.md", ALPHA, 'id: alpha\ntitle: "Alpha Note"')
    n("wiki/concepts/Beta.md", "# Beta Heading\nBeta body [[Alpha]] <private>PRIVATE_SECRET</private>", "id: beta")
    for stem in ("Gamma", "Delta", "Epsilon", "Zeta"):
        n(f"wiki/concepts/{stem}.md", f"{stem} body")
    n("wiki/answers/Dup.md", "first Dup")
    n("wiki/notes/Dup.md", "second Dup")  # two notes with the stem Dup: a link to it is ambiguous
    n("wiki/answers/EtaWorld.md", "ETA_BODY_1 [[Alpha]]", "world: eta")
    n("wiki/answers/EtaQuoted.md", "ETA_BODY_2", 'world: "eta"')
    n("wiki/sources/imported/notion/Eta-20261014/EtaDir.md", "ETA_BODY_3")
    n("wiki/answers/A-ETA-Named.md", "ETA_BODY_4")
    n("wiki/sources/FromEta.md", "ETA_BODY_5", 'sources: ["wiki/sources/imported/linear/Endix/END-1.md"]')
    n("wiki/eta/Inside.md", "ETA_BODY_6")
    n("eta/Hidden.md", "ETA_BODY_7")  # outside wiki/ and hubs/
    n("wiki/raw/R.md", "RAW_BODY")
    n("wiki/templates/T.md", "TEMPLATE_BODY")
    n("projects/P.md", "PROJECT_BODY")
    n("hubs/areas/Hub.md", "한글로 작성한 허브 노트입니다. 이 노트는 여러 노트를 연결합니다. [[Alpha]] [[Beta]]", 'title: 허브')
    n("wiki/notes/Long.md", "L" * 3000 + " [[Beta]] [[Gamma]]")  # the links come after the text is cut
    n("wiki/notes/Many.md", "Many " + " ".join(f"[[F{i:02d}]]" for i in range(7, 0, -1)))
    for i in range(1, 15):
        n(f"wiki/notes/F{i:02d}.md", f"filler {i}")


def make_big_vault(root, size=30):
    for i in range(size):
        note(root, f"wiki/notes/N{i:02d}.md", f"note {i} [[N{(i + 1) % size:02d}]] [[N{(i + 2) % size:02d}]]")


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.vault = self.tmp / "vault"
        self.vault.mkdir()
        self.eval = self.tmp / "eval"
        p = mock.patch.dict(os.environ, {"MAENG_DECISIONS_EVAL_DIR": str(self.eval)})
        p.start()
        self.addCleanup(p.stop)

    def main(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            try:
                code = rev.main(argv)
            except SystemExit as e:
                code = e.code
        return code, out.getvalue()


class ScanTests(Base):
    def setUp(self):
        super().setUp()
        make_vault(self.vault)
        self.notes, self.eta_skipped = rev.scan(self.vault)

    def test_links_resolve_by_unique_stem_without_self_missing_ambiguous_or_eta_targets(self):
        c = "wiki/concepts/"
        self.assertEqual(self.notes[c + "Alpha.md"]["links"], {c + "Beta.md", c + "Gamma.md", c + "Delta.md", c + "Epsilon.md"})
        # [[Alpha]] itself, [[Missing]], [[Dup]] (two notes), the three eta notes and Zeta (linked inside <private>) are dropped
        self.assertEqual(self.notes["hubs/areas/Hub.md"]["links"], {c + "Alpha.md", c + "Beta.md"})
        self.assertEqual(self.notes[c + "Beta.md"]["links"], {c + "Alpha.md"})
        self.assertEqual(self.notes["wiki/notes/Long.md"]["links"], {c + "Beta.md", c + "Gamma.md"})

    def test_only_wiki_and_hubs_without_eta_raw_or_templates_are_scanned(self):
        ids = set(self.notes)
        for gone in ("wiki/answers/EtaWorld.md", "wiki/answers/EtaQuoted.md", "wiki/sources/imported/notion/Eta-20261014/EtaDir.md",
                     "wiki/answers/A-ETA-Named.md", "wiki/sources/FromEta.md", "wiki/eta/Inside.md", "eta/Hidden.md",
                     "wiki/raw/R.md", "wiki/templates/T.md", "projects/P.md"):
            self.assertNotIn(gone, ids)
        self.assertEqual(self.eta_skipped, 6)  # world eta x2, imported eta folder, ETA in the name, eta source, wiki/eta/
        self.assertEqual(len(ids), 25)  # 6 concepts, 2 Dup, Hub, Long, Many, 14 fillers

    def test_title_is_frontmatter_then_first_heading_then_stem(self):
        self.assertEqual(self.notes["wiki/concepts/Alpha.md"]["title"], "Alpha Note")
        self.assertEqual(self.notes["wiki/concepts/Beta.md"]["title"], "Beta Heading")
        self.assertEqual(self.notes["wiki/concepts/Gamma.md"]["title"], "Gamma")
        self.assertEqual(self.notes["hubs/areas/Hub.md"]["title"], "허브")

    def test_text_is_the_stripped_body_cut_to_1500(self):
        t = self.notes["wiki/concepts/Alpha.md"]["text"]
        self.assertTrue(t.startswith("Alpha body text."))
        self.assertNotIn("id: alpha", t)
        self.assertIn("[private omitted] the end.", t)
        self.assertEqual(self.notes["wiki/notes/Long.md"]["text"], "L" * 1500)
        self.assertEqual(self.notes["wiki/concepts/Beta.md"]["text"], "# Beta Heading\nBeta body [[Alpha]] [private omitted]")

    def test_a_decomposed_korean_file_name_still_resolves_a_composed_link(self):
        v = self.tmp / "ko"
        note(v, "wiki/notes/" + unicodedata.normalize("NFD", "한글노트") + ".md", "본문")
        note(v, "wiki/notes/Q.md", "[[한글노트]] [[Other]]")
        note(v, "wiki/notes/Other.md", "o")
        notes, _ = rev.scan(v)
        self.assertEqual(notes["wiki/notes/Q.md"]["links"], {"wiki/notes/한글노트.md", "wiki/notes/Other.md"})


class LanguageTests(unittest.TestCase):
    def test_ko_means_more_than_30_percent_of_the_letters_are_hangul(self):
        self.assertEqual(rev.language("가나다abc"), "ko")  # 3 of 6
        self.assertEqual(rev.language("가나다" + "abcdefg"), "other")  # 3 of 10 is exactly 30%, not more
        self.assertEqual(rev.language("가나다" + "abcdef"), "ko")  # 3 of 9
        self.assertEqual(rev.language("가나다 1234 !!! ---"), "ko")  # digits and punctuation are not letters
        self.assertEqual(rev.language("plain english"), "other")
        self.assertEqual(rev.language("1234 !!!"), "other")  # no letters at all


class CaseTests(Base):
    def setUp(self):
        super().setUp()
        make_vault(self.vault)
        self.notes, _ = rev.scan(self.vault)
        self.cases, self.labels = rev.make_cases(self.notes, 40, 0)
        self.by_id = {c["id"]: c for c in self.cases}
        self.rel = {r["id"]: r["relevant"] for r in self.labels}

    def test_eligible_queries_are_notes_with_two_or_more_links(self):
        self.assertEqual([c["id"] for c in self.cases], ["hubs/areas/Hub.md", "wiki/concepts/Alpha.md", "wiki/notes/Long.md", "wiki/notes/Many.md"])
        self.assertEqual([c["lang"] for c in self.cases], ["ko", "other", "other", "other"])

    def test_positives_are_the_first_five_sorted_links(self):
        c = "wiki/concepts/"
        self.assertEqual(self.rel["wiki/concepts/Alpha.md"], [c + "Beta.md", c + "Delta.md", c + "Epsilon.md", c + "Gamma.md"])
        self.assertEqual(self.rel["wiki/notes/Many.md"], [f"wiki/notes/F{i:02d}.md" for i in range(1, 6)])  # 7 links, 5 kept, sorted

    def test_negatives_are_ten_notes_with_no_link_either_way(self):
        for q, cand in ((c["id"], c["candidates"]) for c in self.cases):
            ids = [x["id"] for x in cand]
            self.assertEqual(ids, sorted(ids))  # order carries no label
            neg = [i for i in ids if i not in self.rel[q]]
            self.assertEqual(len(neg), 10)
            self.assertEqual(len(ids), len(set(ids)))
            for i in neg:
                self.assertNotEqual(i, q)
                self.assertNotIn(i, self.notes[q]["links"])
                self.assertNotIn(q, self.notes[i]["links"])
        # Hub links to Alpha and Beta, so Alpha (a query) never gets Hub as a negative
        self.assertNotIn("hubs/areas/Hub.md", [x["id"] for x in self.by_id["wiki/concepts/Alpha.md"]["candidates"]])
        # Many links to F01..F07, so none of them is a negative, only the first 5 are positives
        many = {x["id"] for x in self.by_id["wiki/notes/Many.md"]["candidates"]}
        self.assertTrue(many.isdisjoint({f"wiki/notes/F{i:02d}.md" for i in (6, 7)}))

    def test_candidate_and_task_fields(self):
        alpha = self.by_id["wiki/concepts/Alpha.md"]
        self.assertTrue(alpha["task"].startswith("Continue the work in this note: Alpha Note\nAlpha body text."))
        gamma = next(x for x in alpha["candidates"] if x["id"] == "wiki/concepts/Gamma.md")
        self.assertEqual(gamma, {"id": "wiki/concepts/Gamma.md", "title": "Gamma", "text": "Gamma body",
                                 "source": "obsidian", "path": "wiki/concepts/Gamma.md"})
        self.assertEqual(len(self.by_id["wiki/notes/Long.md"]["task"]), len("Continue the work in this note: Long\n") + 600)

    def test_eta_and_private_content_is_in_no_case_label_or_file(self):
        rev.build(self.vault, self.tmp / "out")
        blob = "".join((self.tmp / "out" / f).read_text(encoding="utf-8") for f in (rev.CASES_FILE, rev.LABELS_FILE))
        for leak in LEAKS:
            self.assertNotIn(leak, blob)
        self.assertNotIn("private>", blob)
        self.assertNotIn("[Zeta", blob)
        for c in self.cases:
            for x in c["candidates"]:
                self.assertNotRegex(x["id"], r"(?i)(?<![a-z0-9])(?:eta|endix)(?![a-z0-9])|/raw/|/templates/")  # Beta is fine
                self.assertNotIn(x["id"], ("wiki/concepts/Zeta.md",) if x["id"] in self.rel[c["id"]] else ())

    def test_fewer_eligible_notes_than_asked_gives_all_of_them(self):
        cases, _ = rev.make_cases(self.notes, 2, 0)
        self.assertEqual(len(cases), 2)
        self.assertEqual([c["id"] for c in cases], sorted(c["id"] for c in cases))
        self.assertEqual(len(rev.make_cases(self.notes, 99, 0)[0]), 4)


class BuildTests(Base):
    def test_rebuild_is_byte_identical_and_keys_are_sorted(self):
        make_vault(self.vault)
        a, b = self.tmp / "a", self.tmp / "b"
        sa, sb = rev.build(self.vault, a), rev.build(self.vault, b)
        self.assertEqual(sa, sb)
        for f in (rev.CASES_FILE, rev.LABELS_FILE):
            self.assertEqual((a / f).read_bytes(), (b / f).read_bytes())
        row = json.loads((a / rev.CASES_FILE).read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(list(row), sorted(row))
        self.assertEqual(list(row["candidates"][0]), sorted(row["candidates"][0]))
        self.assertTrue((a / rev.CASES_FILE).read_text(encoding="utf-8").endswith("\n"))

    def test_the_seed_changes_the_negatives_and_the_same_seed_repeats_them(self):
        make_vault(self.vault)
        notes, _ = rev.scan(self.vault)
        c0, _ = rev.make_cases(notes, 40, 0)
        self.assertEqual(c0, rev.make_cases(notes, 40, 0)[0])
        self.assertNotEqual(c0, rev.make_cases(notes, 40, 1)[0])

    def test_build_cli_writes_into_eval_and_prints_the_counts_and_size(self):
        make_vault(self.vault)
        code, out = self.main(["build", "--vault", str(self.vault)])
        self.assertEqual(code, 0)
        text = "".join((self.eval / f).read_text(encoding="utf-8") for f in (rev.CASES_FILE, rev.LABELS_FILE))
        self.assertIn("cases=4 ko=1 other=3", out)
        self.assertIn("eta_skipped=6", out)
        self.assertIn(f"{len(text)} characters", out)
        self.assertEqual(self.main(["build", "--vault", str(self.vault), "--cases", "2"])[1].count("cases=2 "), 1)

    def test_check_fails_under_20_cases_even_when_identical(self):
        make_vault(self.vault)
        self.main(["build", "--vault", str(self.vault)])
        code, out = self.main(["build", "--vault", str(self.vault), "--check"])
        self.assertEqual((code, out), (1, "cases=4 ko=1 other=3 identical=yes\n"))

    def test_check_passes_when_identical_with_20_or_more_cases_and_fails_when_not(self):
        make_big_vault(self.vault)
        self.main(["build", "--vault", str(self.vault)])
        self.assertEqual(self.main(["build", "--vault", str(self.vault), "--check"]), (0, "cases=30 ko=0 other=30 identical=yes\n"))
        (self.eval / rev.CASES_FILE).write_text("changed\n", encoding="utf-8")
        self.assertEqual(self.main(["build", "--vault", str(self.vault), "--check"]), (1, "cases=30 ko=0 other=30 identical=no\n"))
        (self.eval / rev.LABELS_FILE).unlink()
        self.assertEqual(self.main(["build", "--vault", str(self.vault), "--check"])[0], 1)

    def test_check_never_touches_the_eval_files(self):
        make_big_vault(self.vault)
        self.main(["build", "--vault", str(self.vault), "--check"])  # nothing there yet: identical=no
        self.assertFalse(self.eval.exists())
        with mock.patch.object(rev, "build", wraps=rev.build) as b:
            self.main(["build", "--vault", str(self.vault), "--check"])
        self.assertNotEqual(Path(b.call_args.args[1]), self.eval)


def tree(root):
    """{relative path: size} of every file under root, bytecode caches left out."""
    return {str(Path(d, f).relative_to(root)): os.path.getsize(Path(d, f))
            for d, ds, fs in os.walk(root) for f in fs if "__pycache__" not in d}


class EvalDirTests(Base):
    def test_the_default_directory_is_outside_the_repository_and_the_skill_folder(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("MAENG_DECISIONS_EVAL_DIR", None)
            d = rev.eval_dir()
        self.assertEqual(d, Path("~/Documents/maeng-harness/decisions/eval").expanduser().resolve())
        for inside in (rev.ROOT, rev.HERE.parent):
            self.assertNotIn(inside, [d, *d.parents])
        self.assertNotIn("agent-harness", d.parts)

    def test_the_env_var_moves_it_and_a_directory_inside_the_repository_is_refused(self):
        self.assertEqual(rev.eval_dir(), self.eval.resolve())
        for bad in (rev.ROOT, rev.ROOT / "docs" / "x", rev.HERE.parent, rev.HERE.parent / "eval", rev.HERE):
            with mock.patch.dict(os.environ, {"MAENG_DECISIONS_EVAL_DIR": str(bad)}):
                with self.assertRaisesRegex(ValueError, "inside the repository"):
                    rev.eval_dir()
        make_vault(self.vault)
        with mock.patch.dict(os.environ, {"MAENG_DECISIONS_EVAL_DIR": str(rev.HERE.parent / "eval-tmp-never-created")}):
            before = tree(rev.HERE.parent)
            for argv in (["build", "--vault", str(self.vault)], ["build", "--vault", str(self.vault), "--check"], ["run"]):
                self.assertEqual(self.main(argv)[0], 2, argv)
            self.assertEqual(tree(rev.HERE.parent), before)
            self.assertFalse((rev.HERE.parent / "eval-tmp-never-created").exists())

    def test_build_with_no_env_writes_nothing_under_the_skill_folder(self):
        make_vault(self.vault)
        home = self.tmp / "home"
        before = tree(rev.HERE.parent)
        with mock.patch.dict(os.environ, {"HOME": str(home)}):
            os.environ.pop("MAENG_DECISIONS_EVAL_DIR", None)
            code, out = self.main(["build", "--vault", str(self.vault)])
            check_code, check_out = self.main(["build", "--vault", str(self.vault), "--check"])
        target = home / "Documents" / "maeng-harness" / "decisions" / "eval"
        self.assertEqual(code, 0)
        self.assertEqual(sorted(p.name for p in target.iterdir()), [rev.CASES_FILE, rev.LABELS_FILE])
        self.assertIn(f"to {target.resolve()}:", out)
        self.assertEqual(check_out, "cases=4 ko=1 other=3 identical=yes\n")  # --check reads the same place
        self.assertEqual(tree(rev.HERE.parent), before)  # the skill folder is untouched
        self.assertFalse(self.eval.exists())


def case(id, lang, pos, neg):
    return {"id": id, "task": f"task {id}", "lang": lang,
            "candidates": [{"id": i, "title": f"title {i}", "text": f"text {i}", "source": "obsidian", "path": f"wiki/{i}.md"}
                           for i in pos + neg]}


def fake_decide(input, questions, pilot):
    """0.9 for items whose id starts with p, 0.1 for the rest."""
    return [{"name": q["name"], "type": "predicate", "status": "ok",
             "probability": 0.9 if re.search(r"item \[p", q["instructions"]) else 0.1} for q in questions]


class RunTests(Base):
    def files(self):
        self.eval.mkdir()
        cases = jsonl(self.eval / rev.CASES_FILE, [case("c1", "ko", ["p1", "p2"], ["n1", "n2", "n3"]), case("c2", "other", ["p3"], ["n4", "n5"])])
        labels = jsonl(self.eval / rev.LABELS_FILE, [{"id": "c1", "relevant": ["p1", "p2"]}, {"id": "c2", "relevant": ["p3"]}])
        return cases, labels

    def test_run_never_opens_the_labels_file(self):
        cases, labels = self.files()
        with forbid(labels):
            with self.assertRaises(AssertionError):  # the guard works: this is what run() would hit
                open(labels, encoding="utf-8")
            with self.assertRaises(AssertionError):
                labels.read_text(encoding="utf-8")
            out = rev.run(cases, decide=fake_decide)
        self.assertEqual([r["selected"] for r in out["results"]], [["p1", "p2"], ["p3"]])
        self.assertEqual(out["results"][0], {"id": "c1", "lang": "ko", "candidates": ["p1", "p2", "n1", "n2", "n3"],
                                             "named": [], "selected": ["p1", "p2"], "unknown": [], "dropped": []})

    def test_named_ids_are_the_candidates_whose_stem_or_title_is_in_the_task(self):
        task = "Continue the work in this note: Gamma note\nsee Beta for details"
        cands = [{"id": "wiki/concepts/Beta.md", "title": "Beta Heading"},  # stem Beta is in the task
                 {"id": "wiki/concepts/Other.md", "title": "Gamma note"},  # title is in the task
                 {"id": "wiki/concepts/Third.md", "title": "Third"},
                 {"id": "wiki/concepts/Empty.md", "title": ""},  # an empty title is in every text, so it must not count
                 {"id": "wiki/concepts/None.md", "title": None},
                 {"id": "wiki/concepts/beta-lower.md", "title": "beta heading"}]  # case-sensitive
        self.assertEqual(rev.named_ids(task, cands), ["wiki/concepts/Beta.md", "wiki/concepts/Other.md"])
        self.eval.mkdir()
        row = {"id": "c1", "task": task, "lang": "other", "candidates": [dict(c, text="t", source="obsidian", path=c["id"]) for c in cands]}
        cases = jsonl(self.eval / rev.CASES_FILE, [row])
        self.assertEqual(rev.run(cases, decide=fake_decide)["results"][0]["named"], ["wiki/concepts/Beta.md", "wiki/concepts/Other.md"])

    def test_run_by_default_reads_the_cases_file_in_eval_and_never_the_labels(self):
        _, labels = self.files()
        with forbid(labels):
            rev.run(decide=fake_decide)

    def test_extra_fields_in_the_cases_file_never_reach_a_request(self):
        row = case("c1", "ko", ["p1"], ["n1"])
        row["relevant"] = ["LEAKED_LABEL"]
        row["candidates"][0]["label"] = "LEAKED_LABEL"
        self.eval.mkdir()
        cases = jsonl(self.eval / rev.CASES_FILE, [row])
        calls = []
        out = rev.run(cases, decide=lambda *a: calls.append(a) or fake_decide(*a))
        self.assertEqual(len(calls), 1)
        self.assertNotIn("LEAKED", json.dumps(calls) + json.dumps(out))
        self.assertEqual(calls[0][2], "records_eval")

    def test_unknown_and_dropped_items_are_not_selected(self):
        self.eval.mkdir()
        row = case("c1", "ko", ["p1", "p2"], ["n1"])
        row["candidates"][1]["world"] = "eta"  # not a kept field: stripped, so it is judged like the rest
        row["candidates"][1]["path"] = "eta/p2.md"  # but a path under eta/ is refused
        cases = jsonl(self.eval / rev.CASES_FILE, [row])

        def decide(input, questions, pilot):
            return [{"name": q["name"], "type": "predicate", "status": "unknown", "reason": "refused"} if "[n1]" in q["instructions"]
                    else {"name": q["name"], "type": "predicate", "status": "ok", "probability": 0.9} for q in questions]
        r = rev.run(cases, decide=decide)["results"][0]
        self.assertEqual((r["selected"], r["unknown"], r["dropped"]), (["p1"], ["n1"], ["p2"]))

    def test_usage_comes_from_a_run_ledger_the_env_is_restored_and_the_main_ledger_gets_the_lines(self):
        self.files()
        sentinel = str(self.tmp / "main-ledger.jsonl")

        def post(url, body, headers, timeout):
            return {"answers": [{"name": q["name"], "type": "predicate", "probability": 0.2} for q in body["questions"]],
                    "usage": {"input_tokens": 1_000_000, "input_tokens_details": {"cached_tokens": 400_000}}}
        env = {"OPENAI_API_KEY": "sk-test-EVALKEY1234567890", "MAENG_ETA_ROOT": str(self.tmp / "eta"), "MAENG_DECISIONS_LEDGER": sentinel}
        with mock.patch.dict(os.environ, env), mock.patch.object(dc, "_post", post):
            os.environ.pop("MAENG_DECISIONS", None)
            out = rev.run()
            self.assertEqual(os.environ["MAENG_DECISIONS_LEDGER"], sentinel)
        main = [json.loads(ln) for ln in Path(sentinel).read_text(encoding="utf-8").splitlines()]
        self.assertEqual([r["pilot"] for r in main], ["records_eval"] * 2)
        self.assertEqual([r["selected"] for r in out["results"]], [[], []])  # 0.2 is under the threshold
        # two cases, two calls; each: 600000 fresh * $0.10/1M + 400000 cached * $0.01/1M = $0.064
        self.assertEqual(out["usage"], {"input_tokens": 2_000_000, "cached_tokens": 800_000, "cost_usd": 0.128})

    def test_env_without_a_ledger_variable_is_left_without_one(self):
        cases, _ = self.files()
        with mock.patch.dict(os.environ):
            os.environ.pop("MAENG_DECISIONS_LEDGER", None)
            rev.run(cases, decide=fake_decide)
            self.assertNotIn("MAENG_DECISIONS_LEDGER", os.environ)

    def test_run_cli_writes_the_report_and_prints_a_summary(self):
        self.files()
        out_path = self.tmp / "report.json"
        stdout = io.StringIO()
        with mock.patch.object(rec, "DECIDE", fake_decide), contextlib.redirect_stdout(stdout):
            self.assertEqual(rev.main(["run", "--out", str(out_path)]), 0)
        rep = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual((rep["recall"], rep["selected_share"], rep["pass"]), (1.0, 0.375, True))  # 3 of 3 found; 3 of 8 selected
        self.assertTrue(stdout.getvalue().startswith("# Related-pick eval: PASS"))
        self.assertIn("| ko | 1 | 2/2 = 1.000 | 2/2 = 1.000 | 2/5 = 0.400 | 0 |", stdout.getvalue())  # "task c1" names no candidate
        self.assertEqual((rep["recall_unnamed"], rep["relevant_unnamed"]), (1.0, 3))


def res(id, lang, candidates, selected, unknown=(), named=()):
    return {"id": id, "lang": lang, "candidates": candidates, "named": list(named), "selected": selected,
            "unknown": list(unknown), "dropped": []}


class ScoreTests(Base):
    def labels(self, rows):
        return jsonl(self.tmp / "labels.jsonl", [{"id": i, "relevant": r} for i, r in rows.items()])

    def test_fixed_results_give_hand_computed_numbers(self):
        # c1 ko: 10 candidates, relevant a b c, selected a b x y (2 found, 4 selected), one unknown; the task names a and x
        # c2 ko: 12 candidates, relevant d e,   selected d e z   (2 found, 3 selected); the task names d and e
        # c3 other: 15 candidates, relevant f g h i j, selected f (1 found, 1 selected), two unknown; the task names g
        # c4 other: 13 candidates, relevant k l, selected k l m n o p (2 found, 6 selected); the task names l
        results = [res("c1", "ko", [f"x{i}" for i in range(10)], ["a", "b", "x", "y"], ["u1"], named=["a", "x"]),
                   res("c2", "ko", [f"x{i}" for i in range(12)], ["d", "e", "z"], named=["d", "e"]),
                   res("c3", "other", [f"x{i}" for i in range(15)], ["f"], ["u2", "u3"], named=["g"]),
                   res("c4", "other", [f"x{i}" for i in range(13)], ["k", "l", "m", "n", "o", "p"], named=["l"])]
        labels = self.labels({"c1": ["a", "b", "c"], "c2": ["d", "e"], "c3": ["f", "g", "h", "i", "j"], "c4": ["k", "l"]})
        rep = rev.score({"results": results, "usage": {"input_tokens": 12345, "cached_tokens": 2000, "cost_usd": 0.0012}}, labels)
        # overall: relevant 3+2+5+2 = 12, found 2+2+1+2 = 7, candidates 10+12+15+13 = 50, selected 4+3+1+6 = 14
        self.assertEqual((rep["cases"], rep["relevant"], rep["found"], rep["candidates"], rep["selected"], rep["unknown"]), (4, 12, 7, 50, 14, 3))
        self.assertAlmostEqual(rep["recall"], 7 / 12)  # 0.5833
        self.assertAlmostEqual(rep["selected_share"], 0.28)
        ko, other = rep["by_lang"]["ko"], rep["by_lang"]["other"]
        self.assertEqual((ko["cases"], ko["relevant"], ko["found"], ko["candidates"], ko["selected"], ko["unknown"]), (2, 5, 4, 22, 7, 1))
        self.assertAlmostEqual(ko["recall"], 0.8)
        self.assertAlmostEqual(ko["selected_share"], 7 / 22)  # 0.3182
        self.assertEqual((other["cases"], other["relevant"], other["found"], other["candidates"], other["selected"], other["unknown"]), (2, 7, 3, 28, 7, 2))
        self.assertAlmostEqual(other["recall"], 3 / 7)  # 0.4286
        self.assertAlmostEqual(other["selected_share"], 0.25)
        # unnamed relevant (not named in the task; a named x is not relevant, so it changes nothing):
        #   c1 b c (b found) = 1 of 2, c2 none, c3 f h i j (f found) = 1 of 4, c4 k (found) = 1 of 1
        self.assertEqual((rep["relevant_unnamed"], rep["found_unnamed"]), (7, 3))
        self.assertAlmostEqual(rep["recall_unnamed"], 3 / 7)  # 0.4286
        self.assertEqual((ko["relevant_unnamed"], ko["found_unnamed"]), (2, 1))
        self.assertAlmostEqual(ko["recall_unnamed"], 0.5)
        self.assertEqual((other["relevant_unnamed"], other["found_unnamed"]), (5, 2))
        self.assertAlmostEqual(other["recall_unnamed"], 0.4)
        self.assertEqual(rep["missed"], {"c1": ["c"], "c3": ["g", "h", "i", "j"]})
        self.assertEqual((rep["input_tokens"], rep["cached_tokens"], rep["cost_usd"]), (12345, 2000, 0.0012))
        self.assertEqual(rep["floors"], {"recall": False, "selected_share": True})  # the floors ignore the unnamed recall
        self.assertFalse(rep["pass"])

    def test_the_unnamed_recall_does_not_change_the_floors(self):
        # every relevant note is named in the task, so the unnamed recall is undefined, yet the floors still judge recall 9/10
        rel = [f"r{i}" for i in range(10)]
        rep = rev.score([res("c1", "other", [f"x{i}" for i in range(20)], rel[:9] + ["o0"], named=rel)], self.labels({"c1": rel}))
        self.assertEqual((rep["relevant_unnamed"], rep["found_unnamed"], rep["recall_unnamed"]), (0, 0, None))
        self.assertEqual(rep["floors"], {"recall": True, "selected_share": True})
        self.assertTrue(rep["pass"])
        # none named and the same selection: unnamed recall equals recall
        rep = rev.score([res("c1", "other", [f"x{i}" for i in range(20)], rel[:9] + ["o0"])], self.labels({"c1": rel}))
        self.assertEqual((rep["relevant_unnamed"], rep["found_unnamed"], rep["recall_unnamed"]), (10, 9, 0.9))

    def edge(self, found, selected_extra):
        """One case, 10 relevant, 20 candidates; `found` of the relevant selected plus `selected_extra` others."""
        rel = [f"r{i}" for i in range(10)]
        sel = rel[:found] + [f"o{i}" for i in range(selected_extra)]
        return rev.score([res("c1", "other", [f"x{i}" for i in range(20)], sel)], self.labels({"c1": rel}))

    def test_floors_pass_exactly_at_their_edges_and_fail_beyond(self):
        rep = self.edge(9, 1)  # recall 9/10 = 0.9, selected 10 of 20 = 0.5
        self.assertEqual((rep["recall"], rep["selected_share"]), (0.9, 0.5))
        self.assertEqual(rep["floors"], {"recall": True, "selected_share": True})
        self.assertTrue(rep["pass"])
        self.assertEqual(self.edge(8, 2)["floors"], {"recall": False, "selected_share": True})  # 0.8
        self.assertEqual(self.edge(9, 2)["floors"], {"recall": True, "selected_share": False})  # 11 of 20 = 0.55

    def test_an_unselected_unknown_relevant_item_counts_against_recall(self):
        rel = ["a", "b"]
        rep = rev.score([res("c1", "ko", ["a", "b", "n"], ["a"], ["b"])], self.labels({"c1": rel}))
        self.assertEqual((rep["found"], rep["recall"], rep["unknown"], rep["missed"]), (1, 0.5, 1, {"c1": ["b"]}))

    def test_a_language_with_no_cases_has_no_numbers_and_nothing_to_judge_is_not_a_pass(self):
        rep = rev.score([res("c1", "ko", ["a", "n"], ["a"])], self.labels({"c1": ["a"]}))
        self.assertEqual(rep["by_lang"]["other"]["cases"], 0)
        self.assertIsNone(rep["by_lang"]["other"]["recall"])
        self.assertIsNone(rep["by_lang"]["other"]["selected_share"])
        self.assertIsNone(rep["by_lang"]["other"]["recall_unnamed"])
        rep = rev.score([res("c1", "ko", ["a"], [])], self.labels({"c1": []}))
        self.assertIsNone(rep["recall"])
        self.assertFalse(rep["floors"]["recall"])
        self.assertFalse(rep["pass"])

    def test_results_and_labels_must_cover_the_same_cases(self):
        with self.assertRaises(ValueError):
            rev.score([res("c1", "ko", ["a"], ["a"])], self.labels({"c1": ["a"], "c2": ["b"]}))


if __name__ == "__main__":
    unittest.main()
