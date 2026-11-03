import contextlib
import io
import itertools
import json
import os
import string
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_claim_eval as bce  # noqa: E402
import verify_claims as vc  # noqa: E402


def seed(i, claim, label="supported", url="u1", note="n.md"):
    return {"id": i, "claim": claim, "url": url, "note": note, "label": label, "source": "test"}


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.eval = self.tmp / "eval"
        self.eval.mkdir()

    def write_seed(self, rows):
        (self.eval / "seed-v1.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    def patch_fetch(self, pages):
        calls = []

        def fetch(url, note=None, refresh=False):
            calls.append(url)
            return pages[url]
        p = mock.patch.object(vc, "fetch_page", fetch)
        p.start()
        self.addCleanup(p.stop)
        return calls

    def read(self, d, name):
        return [json.loads(ln) for ln in (Path(d) / name).read_text(encoding="utf-8").splitlines()]

    def build_main(self):
        with contextlib.redirect_stderr(io.StringIO()):
            bce.main(["--dir", str(self.eval)])

    def run_check(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = bce.main(["--check", "--dir", str(self.eval)])
        return code, out.getvalue().strip()


class MutationTests(unittest.TestCase):
    def test_changed_values_by_token_kind(self):
        cases = {
            "Limit is 400 questions.": "Limit is 403 questions.",
            "Input costs $0.10 per token.": "Input costs $0.13 per token.",
            "A 64k window.": "A 67k window.",
            "Needs 1.13.0 or newer.": "Needs 1.13.3 or newer.",
            "A 20% uplift.": "A 23% uplift.",
            "Holds 1,024 items.": "Holds 1,027 items.",
            "Released 2026-10-08.": "Released 2026-10-11.",
            "Released October 14, 2026.": "Released October 17, 2026.",
            "Announced Sep 15, 2026.": "Announced Sep 18, 2026.",
        }
        for claim, first in cases.items():
            self.assertEqual(bce.mutations(claim, "")[0], first, claim)

    def test_second_rule_on_a_single_token(self):
        self.assertEqual(bce.mutations("Limit is 400 questions.", ""),
                         ["Limit is 403 questions.", "Limit is 407 questions."])
        self.assertEqual(bce.mutations("Released 2026-10-08.", ""), ["Released 2026-10-11.", "Released 2026-10-18."])

    def test_at_most_two_and_different_tokens_first(self):
        self.assertEqual(bce.mutations("A 10 then 20 then 30.", ""),
                         ["A 13 then 20 then 30.", "A 10 then 23 then 30."])

    def test_a_mutation_identical_to_the_original_is_dropped(self):
        with mock.patch.object(bce, "_variants", lambda tok, is_date: [(tok, [tok]), ("999", ["999"])]):
            self.assertEqual(bce.mutations("Limit is 400 questions.", ""), ["Limit is 999 questions."])
        with mock.patch.object(bce, "_variants", lambda tok, is_date: [(tok, [tok])]):
            self.assertEqual(bce.mutations("Limit is 400 questions.", ""), [])

    def test_a_mutated_value_present_in_the_page_is_dropped(self):
        claim = "Limit is 400 questions."
        page = lambda text: bce._norm(text)
        self.assertEqual(bce.mutations(claim, page("The limit is 403 here.")), ["Limit is 407 questions."])
        self.assertEqual(bce.mutations(claim, page("Values 403 and 407.")), [])
        self.assertEqual(bce.mutations(claim, page("The limit is 400 here.")), ["Limit is 403 questions.", "Limit is 407 questions."])

    def test_page_match_ignores_commas_case_and_line_breaks(self):
        # 1,027 on the page as 1027 drops the first mutation; 1,021 is not on it
        self.assertEqual(bce.mutations("Holds 1,024 items.", bce._norm("max 1027")), ["Holds 1,021 items."])
        self.assertEqual(bce.mutations("Holds 1,024 items.", bce._norm("max 1,027")), ["Holds 1,021 items."])
        page = bce._norm("released\nOCTOBER 17,\n2026 and October 24, 2026")
        self.assertEqual(bce.mutations("Released October 14, 2026.", page), [])

    def test_a_date_is_checked_in_every_rendering(self):
        claim = "Released 2026-10-08."
        for text in ("on October 11, 2026", "on Oct 11, 2026", "on 11 October 2026", "on 2026-10-11"):
            self.assertEqual(bce.mutations(claim, bce._norm(text)), ["Released 2026-10-18."], text)
        self.assertEqual(bce.mutations(claim, bce._norm("on 11 October 2026 and 18 Oct 2026")), [])

    def test_an_impossible_date_gives_no_mutation(self):
        self.assertEqual(bce.mutations("Due 2026-13-45.", ""), [])

    def test_a_claim_without_numbers_gives_no_mutation(self):
        self.assertEqual(bce.mutations("The model is called luna.", ""), [])


def letters(n):
    """n distinct number-free words."""
    return ["".join(t) for t in itertools.islice(itertools.product(string.ascii_lowercase, repeat=3), n)]


class BuildTests(Base):
    def seeds(self):
        return [
            seed("p001", "Limit is 400 questions."),
            seed("p002", "Costs $0.10 per call.", url="u2"),
            seed("p003", "No numbers in this claim."),
            seed("n001", "The page names 400 owners.", label="not_in_page"),
            seed("n002", "Costs 7000 per call.", label="contradicted", url="u2"),
            seed("p004", "Gone page has 400 items.", url="u3"),
        ]

    def pages(self):
        return {"u1": ("The limit is 400 questions per request.", "live"),
                "u2": ("Price is $0.10. Also 7000.", "note"),
                "u3": ("", "none")}

    def test_files_have_no_label_in_claims_and_sorted_output(self):
        self.write_seed(self.seeds())
        self.patch_fetch(self.pages())
        bce.build(self.eval / "seed-v1.jsonl", self.eval)
        claims, labels = self.read(self.eval, "claims-v1.jsonl"), self.read(self.eval, "labels-v1.jsonl")
        self.assertTrue(all(set(c) == {"id", "claim", "url", "note"} for c in claims))
        self.assertEqual([c["id"] for c in claims], sorted(c["id"] for c in claims))
        self.assertEqual([c["id"] for c in labels], [c["id"] for c in claims])
        raw = (self.eval / "labels-v1.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertTrue(all(ln == json.dumps(json.loads(ln), sort_keys=True, ensure_ascii=False) for ln in raw))

    def test_mutations_come_from_supported_seeds_with_parent_and_label(self):
        self.write_seed(self.seeds())
        self.patch_fetch(self.pages())
        bce.build(self.eval / "seed-v1.jsonl", self.eval)
        claims = {c["id"]: c for c in self.read(self.eval, "claims-v1.jsonl")}
        labels = {c["id"]: c for c in self.read(self.eval, "labels-v1.jsonl")}
        self.assertEqual(sorted(labels), ["mp001-1", "mp001-2", "mp002-1", "mp002-2", "n001", "n002", "p001", "p002", "p003", "p004"])
        self.assertEqual(labels["mp001-1"], {"id": "mp001-1", "kind": "mutation", "label": "contradicted", "parent": "p001"})
        self.assertEqual(labels["p001"], {"id": "p001", "kind": "seed", "label": "supported"})
        self.assertEqual(labels["n001"]["label"], "not_in_page")  # natural negatives are kept as given
        self.assertEqual(claims["mp001-1"]["claim"], "Limit is 403 questions.")
        self.assertEqual(claims["mp001-2"]["claim"], "Limit is 407 questions.")
        self.assertEqual((claims["mp001-1"]["url"], claims["mp001-1"]["note"]), ("u1", "n.md"))
        # p004's page is unavailable: its absence checks cannot be made, so it gets no mutation
        self.assertNotIn("mp004-1", labels)

    def test_a_mutation_whose_value_is_on_the_page_is_not_written(self):
        self.write_seed([seed("p001", "Limit is 400 questions.")])
        self.patch_fetch({"u1": ("limits 400, 403 and 407", "live")})
        bce.build(self.eval / "seed-v1.jsonl", self.eval)
        self.assertEqual([c["id"] for c in self.read(self.eval, "labels-v1.jsonl")], ["p001"])

    def test_one_fetch_per_url_and_source_counts(self):
        self.write_seed(self.seeds())
        calls = self.patch_fetch(self.pages())
        sources = bce.build(self.eval / "seed-v1.jsonl", self.eval)
        self.assertEqual(sorted(calls), ["u1", "u2", "u3"])
        self.assertEqual(dict(sources), {"live": 1, "note": 1, "none": 1})

    def test_output_is_byte_identical_across_two_runs(self):
        self.write_seed(self.seeds())
        self.patch_fetch(self.pages())
        a, b = self.tmp / "a", self.tmp / "b"
        bce.build(self.eval / "seed-v1.jsonl", a)
        bce.build(self.eval / "seed-v1.jsonl", b)
        for f in bce.FILES:
            self.assertEqual((a / f).read_bytes(), (b / f).read_bytes())


class CheckTests(Base):
    """--check on fixtures: 100 seeds, each with one number the mutations can change."""

    def fixture(self, page_text):
        self.write_seed([seed(f"p{i:03d}", f"Widget {w} has a limit of 100.") for i, w in enumerate(letters(100))])
        self.patch_fetch({"u1": (page_text, "live")})

    def test_passes_with_enough_positives_and_negatives_and_identical_files(self):
        self.fixture("Every widget has a limit of 100.")
        self.build_main()
        self.assertEqual(self.run_check(), (0, "positives=100 negatives=200 identical=yes"))

    def test_fails_when_the_page_holds_every_mutated_value(self):
        # 100 positives; every mutation (103, 107) is on the page, so none may be kept.
        # Without the page-presence check this fixture would give 200 negatives and exit 0.
        self.fixture("Every widget has a limit of 100, or 103, or 107.")
        self.build_main()
        self.assertEqual(self.run_check(), (1, "positives=100 negatives=0 identical=yes"))

    def test_fails_under_100_positives_and_negatives(self):
        self.write_seed([seed("p001", "Limit is 400 questions."), seed("p002", "Limit is 500 questions.")])
        self.patch_fetch({"u1": ("limits 400 and 500", "live")})
        self.build_main()
        self.assertEqual(self.run_check(), (1, "positives=2 negatives=4 identical=yes"))

    def test_fails_when_the_committed_files_differ_or_are_missing(self):
        self.fixture("Every widget has a limit of 100.")
        self.assertEqual(self.run_check(), (1, "positives=100 negatives=200 identical=no"))  # nothing written yet
        self.build_main()
        path = self.eval / "labels-v1.jsonl"
        path.write_text(path.read_text(encoding="utf-8").replace("contradicted", "not_in_page", 1), encoding="utf-8")
        self.assertEqual(self.run_check(), (1, "positives=100 negatives=200 identical=no"))


if __name__ == "__main__":
    unittest.main()
