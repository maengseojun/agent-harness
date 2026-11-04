"""MAE-313 S4: the merge quiz. A real small pytest project is mutated in a throwaway clone; expected values are
hand-derived from the project's text below (line numbers count from 1)."""
import glob
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

from maeng import interview, quiz
from .helpers import HarnessCase, run
from .test_interview import FakeModel, InterviewCase, graded, plain_patch

CALC = """def add(a, b):
    return a + b


def clamp(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def is_even(n):
    return n % 2 == 0


def label(n):
    return "neg" if n < 0 else "pos"
"""
TESTS = """from calc import add, clamp, is_even


def test_add():
    assert add(2, 3) == 5


def test_clamp_low():
    assert clamp(-5, 0, 10) == 0


def test_clamp_high():
    assert clamp(50, 0, 10) == 10


def test_even():
    assert is_even(4) is True
"""
FILES = {"calc.py": CALC, "test_calc.py": TESTS}
PYTEST = "python3 -m pytest -q"

ADD_MINUS = {"kind": "defect", "file": "calc.py", "find": "return a + b", "replace": "return a - b", "question": "q",
             "snippet_start": 1, "snippet_end": 3}  # line 2; test_add fails
EQUIVALENT = {"kind": "defect", "file": "calc.py", "find": "if x < lo:", "replace": "if x <= lo:", "question": "q"}  # same results
UNTESTED = {"kind": "defect", "file": "calc.py", "find": 'return "neg" if n < 0 else "pos"',
            "replace": 'return "neg" if n <= 0 else "pos"', "question": "q"}  # no test calls label
PREDICT_ADD = {"kind": "predict", "file": "test_calc.py", "line": 5, "literal": "5", "question": "무엇?"}
PREDICT_HIGH = {"kind": "predict", "file": "test_calc.py", "line": 13, "literal": "10", "question": "무엇?"}


class Pick:
    """A rng stand-in: the first `choice` among kinds takes the next of `kinds`, any other choice the first option; no shuffle."""

    def __init__(self, *kinds):
        self.kinds = list(kinds)

    def choice(self, seq):
        return self.kinds.pop(0) if "defect-line" in seq else seq[0]

    def shuffle(self, items):
        pass


def snapshot(root):
    """{relative path: (bytes, mtime_ns)} of every file under root except .git."""
    out = {}
    for dirpath, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        for n in names:
            p = os.path.join(dirpath, n)
            out[os.path.relpath(p, root)] = (open(p, "rb").read(), os.stat(p).st_mtime_ns)
    return out


def clones():
    return set(glob.glob(os.path.join(tempfile.gettempdir(), "maeng-quiz-*")))


def own_tmp(case):
    """clones() lists a folder, so under `pytest -n` each test needs its own."""
    t = case.tmp / "tmp"
    t.mkdir()
    case.env["TMPDIR"] = os.environ["TMPDIR"] = str(t)
    patcher = unittest.mock.patch.object(tempfile, "tempdir", str(t))
    patcher.start()
    case.addCleanup(patcher.stop)


class ConfirmItems(HarnessCase):
    def setUp(self):
        super().setUp()
        self.proj = self.make_repo("proj", with_remote=False, files=FILES)
        self.runs = self.tmp / "runs.log"
        self.cmd = f"echo run >> {self.runs}; {PYTEST}"
        own_tmp(self)
        self.before_clones = clones()

    def confirm(self, cands, cmd="default", **kw):
        kw.setdefault("rng", Pick("defect-line"))
        return quiz.confirm_items(cands, str(self.proj), self.cmd if cmd == "default" else cmd, **kw)

    def run_count(self):
        return len(self.runs.read_text().splitlines()) if self.runs.exists() else 0

    def test_a_caught_mutation_an_equivalent_one_and_an_untested_one(self):
        items = self.confirm([ADD_MINUS, EQUIVALENT, UNTESTED], rng=Pick("failing-test"))
        item, = items  # only the mutation a test catches survives
        self.assertEqual(item["kind"], "failing-test")
        self.assertEqual(item["key"], ["test_add"])
        self.assertIn("2:     return a - b", item["question"])  # the mutated snippet, lines 1 to 3, numbered from 1
        self.assertEqual(self.run_count(), 4)  # head, then the three mutations: every candidate was really run

    def test_found_defects_go_in_before_predicted_values(self):
        low = {"kind": "predict", "file": "test_calc.py", "line": 9, "literal": "0", "question": "무엇?"}
        clamp_high = {"kind": "defect", "file": "calc.py", "find": "if x > hi:", "replace": "if x < hi:", "question": "q"}
        items = self.confirm([PREDICT_ADD, PREDICT_HIGH, low, ADD_MINUS, clamp_high], rng=Pick("failing-test", "failing-test"))
        self.assertEqual([it["kind"] for it in items], ["predict", "predict", "failing-test", "failing-test"])

    def test_a_prediction_must_pin_the_value_the_code_gives(self):
        body = ("import pytest\n" + TESTS + "\n\ndef test_not_zero():\n    assert add(2, 3) != 0\n\n\n"
                "def test_big():\n    assert add(2, 3) > 1\n\n\ndef test_no():\n    assert is_even(4) is not False\n\n\n"
                "@pytest.mark.skip\ndef test_off():\n    assert add(2, 3) == 9\n")
        (self.proj / "test_calc.py").write_text(body)
        rows = body.split("\n")
        at = lambda text: rows.index(text) + 1
        wrong = [{"kind": "predict", "file": "test_calc.py", "line": at("    assert add(2, 3) != 0"), "literal": "0", "question": "?"},
                 {"kind": "predict", "file": "test_calc.py", "line": at("    assert add(2, 3) > 1"), "literal": "1", "question": "?"},
                 {"kind": "predict", "file": "test_calc.py", "line": at("    assert is_even(4) is not False"), "literal": "False", "question": "?"},
                 {"kind": "predict", "file": "test_calc.py", "line": at("    assert add(2, 3) == 9"), "literal": "9", "question": "?"}]
        self.assertEqual(self.confirm(wrong), [])
        right = {"kind": "predict", "file": "test_calc.py", "line": at("    assert add(2, 3) == 5"), "literal": "5", "question": "?"}
        self.assertEqual([it["key"] for it in self.confirm([right])], ["5"])

    def test_a_literal_that_cannot_be_varied_safely_is_dropped(self):
        self.assertEqual([quiz._other(x) for x in ("5", "1.5", "True", "false", "'neg'", "[]", "a + b", "x")],
                         ["6", "2.5", "False", "true", "'zzneg'", None, None, None])

    def test_a_delta_quiz_stays_on_the_delta(self):
        item, = self.confirm([ADD_MINUS], want=1, rng=Pick("defect-line"), touched={"calc.py": {2}})
        self.assertEqual(item["key"]["lines"], [2])  # never swapped for a clean snippet of old code
        two = {"kind": "defect", "file": "calc.py", "find": "def add(a, b):\n    return a + b",
               "replace": "def add(a, b):\n    return a - b", "question": "q"}
        self.assertEqual(self.confirm([two], touched={"calc.py": {1}}), [])  # only line 2 changes
        self.assertEqual(len(self.confirm([two], touched={"calc.py": {2}}, rng=Pick("failing-test"))), 1)

    def test_an_unchanged_line_inside_a_mutation_is_not_the_answer(self):
        c = {"kind": "defect", "file": "calc.py", "find": "    if x < lo:\n        return lo\n    if x > hi:",
             "replace": "    if x > lo:\n        return lo\n    if x < hi:", "question": "q"}
        self.assertEqual(quiz._defect(c, str(self.proj), self.cmd, None)["changed"], [6, 8])

    def test_a_deleted_line_can_only_be_a_failing_test_item(self):
        gone = {"kind": "defect", "file": "calc.py", "find": "    if x > hi:\n        return hi\n", "replace": "", "question": "q"}
        item, = self.confirm([gone], rng=Pick("defect-line"))
        self.assertEqual((item["kind"], item["key"]), ("failing-test", ["test_clamp_high"]))
        with unittest.mock.patch.object(quiz, "run_tests", return_value=(False, ["exit status 1"])):
            self.assertIsNone(quiz._defect(gone, str(self.proj), "x", None))  # no test name to ask for

    def test_mutations_stop_once_there_are_enough(self):
        items = self.confirm([ADD_MINUS, EQUIVALENT, UNTESTED], want=1)
        self.assertEqual(len(items), 1)
        self.assertEqual(self.run_count(), 2)  # head, then ADD_MINUS: the other two are never run

    def test_a_defect_with_no_test_name_in_its_failure_is_a_defect_line_item(self):
        d = {"file": "calc.py", "failing": ["exit status 1"], "window": (1, 3), "rows": CALC.split("\n"), "changed": [2]}
        self.assertEqual(quiz._defect_items(d, Pick("failing-test"))["kind"], "defect-line")

    def test_a_defect_line_answer_is_the_changed_line(self):
        clamp_high = {"kind": "defect", "file": "calc.py", "find": "if x > hi:", "replace": "if x < hi:", "question": "q",
                      "snippet_start": 6, "snippet_end": 9}  # line 8; clamp(50, 0, 10) then returns 50
        first, second = self.confirm([ADD_MINUS, clamp_high], rng=Pick("defect-line", "defect-line"))
        self.assertEqual(first["key"], {"lines": [], "file": "calc.py"})  # the first defect-line item became the clean one
        self.assertEqual((second["kind"], second["key"], second["reveal"]), ("defect-line", {"lines": [8], "file": "calc.py"}, "calc.py:8"))
        self.assertIn("8:     if x < hi:", second["question"])
        self.assertIn("6:     if x < lo:", second["question"])  # the window the candidate asked for, lines 6 to 9

    def test_a_clean_snippet_replaces_a_defect_line_item_and_answers_none(self):
        items = self.confirm([PREDICT_ADD, PREDICT_HIGH, ADD_MINUS], rng=Pick("defect-line"))
        self.assertEqual([it["kind"] for it in items], ["predict", "predict", "defect-line"])
        clean = items[2]
        self.assertEqual(clean["key"], {"lines": [], "file": "calc.py"})
        self.assertEqual(clean["reveal"], quiz.CLEAN)
        self.assertIn("3: \n4: \n5: def clamp(x, lo, hi):", clean["question"])  # lines 3 to 5 of the untouched file
        self.assertNotIn("a - b", clean["question"])
        self.assertTrue(quiz.grade_keyed(clean, "없음"))
        self.assertFalse(quiz.grade_keyed(clean, "2"))

    def test_without_a_defect_line_nothing_is_replaced(self):
        items = self.confirm([PREDICT_ADD, ADD_MINUS], rng=Pick("failing-test"))
        self.assertEqual([it["kind"] for it in items], ["predict", "failing-test"])

    def test_predict_masks_the_last_literal_of_a_passing_test_line(self):
        add, high = self.confirm([PREDICT_ADD, PREDICT_HIGH])[:2]
        self.assertEqual((add["key"], high["key"]), ("5", "10"))
        self.assertTrue(add["question"].endswith("test_calc.py:5\n    assert add(2, 3) == ___"))
        self.assertTrue(high["question"].endswith("test_calc.py:13\n    assert clamp(50, 0, 10) == ___"))
        self.assertNotIn("== 5", add["question"])

    def test_a_question_that_gives_the_answer_away_is_replaced(self):
        item = self.confirm([{**PREDICT_ADD, "question": "Is it 5?"}])[0]
        self.assertNotIn("Is it 5", item["question"])

    def test_unusable_candidates_are_dropped(self):
        bad = [
            {**PREDICT_ADD, "line": 17},                                  # the literal is not on that line
            {**PREDICT_ADD, "file": "calc.py", "line": 2, "literal": "a"},  # not a test file
            {**PREDICT_ADD, "line": 99}, {**PREDICT_ADD, "literal": ""}, {**PREDICT_ADD, "file": "../proj-secret/test_x.py"},
            {**PREDICT_ADD, "literal": "2"}, {**PREDICT_ADD, "literal": "3"},  # arguments, not the expected value
            {**PREDICT_HIGH, "literal": "0"},                              # a piece of the expected 10
            {**ADD_MINUS, "find": "return"},                              # not unique in the file
            {**ADD_MINUS, "find": "nothing like this"},
            {**ADD_MINUS, "replace": "return a + b"},                      # no change
            {**ADD_MINUS, "find": "a\nb\nc\nd"}, {**ADD_MINUS, "replace": "1\n2\n3\n4"},  # over 3 lines
            {**ADD_MINUS, "file": "../x.py"}, {**ADD_MINUS, "file": "missing.py"},
            {**ADD_MINUS, "replace": "return a +"},                        # breaks the module: no test failure to learn from
            {"kind": "other"}, {"kind": "defect"}, {},
        ]
        self.assertEqual(self.confirm(bad), [])
        self.assertEqual(self.run_count(), 2)  # head and the syntax-breaking one; every other candidate never ran

    def test_a_mutation_outside_the_prs_files_is_never_applied(self):
        self.assertEqual(self.confirm([ADD_MINUS, PREDICT_ADD], changed={"test_calc.py"}, rng=Pick("failing-test"))[0]["kind"], "predict")
        self.assertEqual(self.run_count(), 2)  # the run at head and the prediction's own check: ADD_MINUS never ran
        self.assertEqual(len(self.confirm([ADD_MINUS], changed={"calc.py"})), 1)

    def test_no_truth_means_no_items(self):
        self.assertEqual(self.confirm([ADD_MINUS, PREDICT_ADD], cmd=None), [])
        self.assertEqual(self.confirm([ADD_MINUS, PREDICT_ADD], cmd=""), [])
        self.assertEqual(self.confirm([ADD_MINUS, PREDICT_ADD], cmd="false"), [])  # the suite fails at head
        with unittest.mock.patch.object(quiz, "TIMEOUT", 1):
            self.assertEqual(self.confirm([ADD_MINUS], cmd="sleep 5"), [])
        (self.proj / "test_calc.py").write_text(TESTS + "\n\ndef test_broken():\n    assert add(1, 1) == 3\n")
        self.git(self.proj, "add", "-A"); self.git(self.proj, "commit", "-qm", "broken")
        self.assertEqual(self.confirm([ADD_MINUS, PREDICT_ADD]), [])

    def test_the_users_checkout_is_untouched_and_the_clone_is_gone(self):
        before, status = snapshot(self.proj), self.git(self.proj, "status", "--porcelain").stdout
        self.confirm([ADD_MINUS, EQUIVALENT, UNTESTED, PREDICT_ADD])
        self.assertEqual(snapshot(self.proj), before)  # same bytes and mtimes; no .pytest_cache, no __pycache__
        self.assertEqual(self.git(self.proj, "status", "--porcelain").stdout, status)
        self.assertEqual(clones(), self.before_clones)

    def test_the_clone_is_removed_even_when_the_run_dies(self):
        with unittest.mock.patch.object(quiz, "run_tests", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                self.confirm([ADD_MINUS])
        self.assertEqual(clones(), self.before_clones)

    def test_a_linked_worktree_clone_does_not_point_at_the_users_git_dir(self):
        wt = self.tmp / "wt"
        self.git(self.proj, "worktree", "add", "-q", "-b", "side", str(wt))
        tmp, repo = quiz.clone(str(wt))
        try:
            self.assertTrue(os.path.exists(os.path.join(repo, "calc.py")))
            self.assertFalse(os.path.exists(os.path.join(repo, ".git")))
        finally:
            shutil.rmtree(tmp)
        self.assertTrue((wt / ".git").is_file())  # the user's worktree still points at its git dir

    def test_plain_cp_is_the_fallback_when_cloning_fails(self):
        real, calls = subprocess.run, []

        def fake(args, *a, **kw):
            calls.append(args[:2])
            if args[:2] == ["cp", "-cR"]:
                return subprocess.CompletedProcess(args, 1, b"", b"not APFS")
            return real(args, *a, **kw)
        with unittest.mock.patch("subprocess.run", side_effect=fake):
            items = self.confirm([ADD_MINUS])
        self.assertEqual(len(items), 1)
        self.assertEqual(calls[:2], [["cp", "-cR"], ["cp", "-R"]])


class Keyed(HarnessCase):
    def test_predict_compares_after_strip_and_casefold_and_numbers_by_value(self):
        five, word = {"kind": "predict", "key": "5"}, {"kind": "predict", "key": "'Hello'"}
        for ok in ("5", " 5 ", "5.0", "05", "'5'", '"5"'):
            self.assertTrue(quiz.grade_keyed(five, ok), ok)
        for bad in ("6", "", None, "five", "55"):
            self.assertFalse(quiz.grade_keyed(five, bad), bad)
        for ok in ("hello", "HELLO ", " 'hello' "):
            self.assertTrue(quiz.grade_keyed(word, ok), ok)
        self.assertFalse(quiz.grade_keyed(word, "hell"))

    def test_defect_line_takes_a_number_or_file_and_number(self):
        item = {"kind": "defect-line", "key": {"lines": [2], "file": "src/calc.py"}}
        for ok in ("2", " 2 ", "src/calc.py:2", "calc.py:2"):
            self.assertTrue(quiz.grade_keyed(item, ok), ok)
        for bad in ("3", "src/calc.py:3", "other.py:2", "없음", "line 2", "", "2:src/calc.py"):
            self.assertFalse(quiz.grade_keyed(item, bad), bad)

    def test_a_clean_snippet_answers_none_only(self):
        clean = {"kind": "defect-line", "key": {"lines": [], "file": "calc.py"}}
        self.assertTrue(quiz.grade_keyed(clean, " 없음 "))
        for bad in ("2", "calc.py:1", "", "none"):
            self.assertFalse(quiz.grade_keyed(clean, bad), bad)

    def test_failing_test_needs_the_name_of_a_test_that_failed(self):
        item = {"kind": "failing-test", "key": ["test_add"]}
        for ok in ("test_add", "TEST_ADD", " test_calc.py::test_add ", "calc.py::test_add", "`test_add`", "test_add()", "test_add[1]"):
            self.assertTrue(quiz.grade_keyed(item, ok), ok)
        for bad in ("add", "", "test", "assert", "FAILED", "tests_add", "test_clamp_low", None):
            self.assertFalse(quiz.grade_keyed(item, bad), bad)

    def test_names_of_failing_tests_per_runner(self):
        self.assertEqual(quiz.test_names(["test_calc.py::TestA::test_add[1] - assert -1 == 5"]), ["test_add"])  # pytest
        self.assertEqual(quiz.test_names(["test_calc.py::test_add - AssertionError: latest result is wrong"]), ["test_add"])
        self.assertEqual(quiz.test_names(["[: revert] testMint() (gas: 1234)"]), ["testMint"])  # forge
        self.assertEqual(quiz.test_names([": test_add (test_calc.Case.test_add)"]), ["test_add"])  # unittest
        self.assertEqual(quiz.test_names(["--- : TestFoo (0.00s)"]), ["TestFoo"])  # go
        self.assertEqual(quiz.test_names(["some tests in test_calc.py: exit status 1"]), [])  # nothing names a test

    def test_large_numbers_keep_their_low_digits(self):
        amount = {"kind": "predict", "key": "1000000000000000000"}
        self.assertTrue(quiz.grade_keyed(amount, "1000000000000000000"))
        self.assertFalse(quiz.grade_keyed(amount, "1000000000000000001"))

    def test_grading_needs_no_model(self):
        self.assertTrue(quiz.grade_keyed({"kind": "predict", "key": "1"}, "1"))  # MAENG_CLAUDE points at nothing here


class PatchId(HarnessCase):
    def raw(self, repo, base, head):
        return plain_patch(self.git(repo, "diff", f"{base}...{head}").stdout)

    def test_two_binary_edits_get_different_ids(self):
        repo = self.make_repo("proj", files=FILES)
        base = self.head(repo)
        self.git(repo, "checkout", "-qb", "feat")
        (repo / "blob.bin").write_bytes(b"\0\1\2one")
        one = self.commit_all(repo, "one")
        (repo / "blob.bin").write_bytes(b"\0\1\2two")
        two = self.commit_all(repo, "two")
        self.assertNotEqual(quiz.patch_id(repo, base, one), quiz.patch_id(repo, base, two))

    def test_an_indentation_change_gets_another_id(self):  # `git patch-id` would call these the same
        repo = self.make_repo("proj", files=FILES)
        base = self.head(repo)
        self.git(repo, "checkout", "-qb", "feat")
        (repo / "calc.py").write_text(CALC.replace("    return a + b", "    if a:\n        a += b\n        return a"))
        one = self.commit_all(repo, "indented")
        (repo / "calc.py").write_text(CALC.replace("    return a + b", "    if a:\n        a += b\n    return a"))
        two = self.commit_all(repo, "dedented")
        self.assertNotEqual(quiz.patch_id(repo, base, one), quiz.patch_id(repo, base, two))

    def test_same_diff_on_another_base_same_id_and_a_changed_diff_another(self):
        repo = self.make_repo("proj", files=FILES)
        base = self.head(repo)
        self.git(repo, "checkout", "-qb", "feat")
        (repo / "calc.py").write_text(CALC.replace("a + b", "a + b + 0"))
        head = self.commit_all(repo, "feat")
        pid = quiz.patch_id(repo, base, head)
        self.assertEqual(pid, self.raw(repo, base, head))
        self.git(repo, "checkout", "-q", "main")
        (repo / "notes.txt").write_text("main moved\n")
        moved = self.commit_all(repo, "main moved")
        self.git(repo, "checkout", "-q", "feat")
        self.git(repo, "rebase", "-q", "main")
        self.assertNotEqual(self.head(repo), head)
        self.assertEqual(quiz.patch_id(repo, moved, self.head(repo)), pid)
        (repo / "calc.py").write_text(CALC.replace("a + b", "a + b + 1"))
        self.assertNotEqual(quiz.patch_id(repo, moved, self.commit_all(repo, "edit")), pid)

    def test_no_diff_or_an_unknown_commit_has_no_id(self):
        repo = self.make_repo("proj", files=FILES)
        self.assertIsNone(quiz.patch_id(repo, self.head(repo), self.head(repo)))
        self.assertIsNone(quiz.patch_id(repo, "0" * 40, self.head(repo)))


class MergeQuizCli(FakeModel, InterviewCase):
    """AC-3 and AC-6 through `maeng-interview start --stage merge`, in a checkout with a real bare remote."""

    def setUp(self):
        super().setUp()
        self.fake_model()
        base_files = {"calc.py": "def add(a, b):\n    return a + b\n\n\ndef is_even(n):\n    return n % 2 == 0\n",
                      "test_calc.py": "from calc import add, is_even\n\n\ndef test_add():\n    assert add(2, 3) == 5\n\n\n"
                                      "def test_even():\n    assert is_even(4) is True\n"}
        self.repo = self.make_repo("proj", files=base_files)
        self.key = interview.repo_key(self.repo)
        self.base = self.head(self.repo)
        self.git(self.repo, "checkout", "-qb", "feat")
        (self.repo / "calc.py").write_text(CALC)
        (self.repo / "test_calc.py").write_text(TESTS)
        self.h = self.commit_all(self.repo, "feat")
        self.declare(test=PYTEST)
        self.pr_json = self.tmp / "pr.json"
        self.set_pr(self.h)
        fake = self.tmp / "fake-gh"
        fake.write_text(f"#!{sys.executable}\nimport os\nprint(open(os.environ['FAKE_GH_JSON']).read())\n")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        self.env.update(MAENG_GH=str(fake), FAKE_GH_JSON=str(self.pr_json))
        own_tmp(self)
        self.before_clones = clones()

    def set_pr(self, head, base=None):
        self.pr_json.write_text(json.dumps({"number": 7, "additions": 3, "deletions": 1, "files": [{"path": "calc.py"}],
                                            "baseRefOid": base or self.base, "headRefOid": head}))

    def quiz(self, *extra):
        return self.cli("maeng-interview", ["start", "--stage", "merge", "--pr", "7", *extra], self.repo)

    def say(self, text):
        return self.hook("UserPromptSubmit", self.repo, prompt=text)

    def right_answer(self, it):
        """What a user who understands the code says, derived from the project text above and the question shown."""
        q = it["question"]
        if it.get("rubric"):
            return "a written answer"
        if it["kind"] == "predict":
            return "5" if "test_calc.py:5" in q else "10" if "test_calc.py:13" in q else "8"
        if it["kind"] == "defect-line":
            return "2" if "a - b" in q else quiz.CLEAN
        return "test_add"

    def finish(self, grades=(), wrong=None):
        """Answer every item rightly (the first item of kind `wrong` wrongly); `grades` are the model's gradings of the
        written items, in order. -> the last `next` result."""
        grades, result, missed = list(grades), None, False
        while self.rec() and self.rec()["awaiting"] == "answer":
            it = next(i for i in self.rec()["items"] if not i["done"] and i["given"] is None)
            answer = self.right_answer(it)
            if wrong and not missed and it.get("kind") == wrong:
                answer, missed = "zzzz", True
            self.say(answer)
            if it.get("rubric"):
                self.queue(grades.pop(0))
            result = self.cli("maeng-interview", ["next"], self.repo)
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def raw_patch(self, base, head):
        return plain_patch(self.git(self.repo, "diff", f"{base}...{head}").stdout)

    CANDIDATES = {"candidates": [ADD_MINUS, EQUIVALENT, UNTESTED, PREDICT_ADD, PREDICT_HIGH]}
    WRITTEN = {"questions": [{"layer": 2, "topic": "design", "question": "Q-diff", "rubric": ["R-diff-1"]}]}

    def test_a_confirmed_quiz_is_three_keyed_items_and_one_written_question(self):
        before = snapshot(self.repo)
        self.queue(self.CANDIDATES, self.WRITTEN)
        r = self.quiz()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Question:", r.stdout)
        items = self.rec()["items"]
        self.assertEqual(len(items), 4)  # two predictions and the one caught mutation, then the written question
        keyed = [it["kind"] for it in items[:-1]]
        self.assertEqual(keyed.count("predict"), 2)
        self.assertIn(set(keyed) - {"predict"}, ({"defect-line"}, {"failing-test"}))
        self.assertEqual(items[-1]["rubric"], ["R-diff-1"])
        self.assertEqual(snapshot(self.repo), before)
        self.assertEqual(clones(), self.before_clones)
        out = self.finish([graded(True)])
        self.assertIn("PASSED: the merge quiz of PR #7", out.stdout)
        self.assertEqual(len(self.model_calls()), 3)  # candidates, the written question, its grading: keyed answers cost no call
        self.assertTrue(interview.passed(self.key, 7, "merge", self.raw_patch(self.base, self.h)))
        record, = json.loads((self.maeng_home / "interviews" / self.key / "passes.json").read_text())["merge"]
        self.assertEqual((record["pr"], record["head"]), (7, self.h))
        line, = self.ledger()
        self.assertEqual((line["stage"], line["pr"], line["attempts"], line["first_try"], line["waived"]), ("merge", "7", 1, True, False))
        self.assertIsNone(self.rec())

    def test_a_wrong_keyed_answer_shows_the_answer_from_the_run_and_the_retry_asks_again(self):
        self.queue(self.CANDIDATES, self.WRITTEN)
        self.quiz()
        out = self.finish([graded(True)], wrong="predict")
        self.assertIn("NOT YET", out.stdout)
        self.assertRegex(out.stdout, r"- \(predict\) the answer is `(5|10)` \(found by running the code\)")
        self.assertFalse(interview.passed(self.key, 7, "merge", self.raw_patch(self.base, self.h)))
        total = len(self.rec()["items"])
        self.queue(self.CANDIDATES)
        r = self.quiz()
        self.assertEqual(r.returncode, 0, r.stderr)
        items = self.rec()["items"]
        self.assertEqual(self.rec()["attempts"], 2)
        self.assertEqual((sum(i["done"] for i in items), sum(not i["done"] for i in items)), (total - 1, 1))  # what passed stays
        self.assertEqual(len({i["id"] for i in items}), total)
        self.finish()
        self.assertEqual((self.ledger()[0]["attempts"], self.ledger()[0]["first_try"]), (2, False))

    def test_a_miss_on_the_written_question_can_be_appealed(self):
        self.queue(self.CANDIDATES, self.WRITTEN)
        self.quiz()
        out = self.finish([graded(False)])
        self.assertIn("- (design) R-diff-1", out.stdout)
        self.say("이의 I did name the difference")
        wid = next(i["id"] for i in self.rec()["items"] if i.get("rubric"))
        self.queue({"items": [{"id": wid, "met": [True]}]})
        out = self.cli("maeng-interview", ["appeal"], self.repo)
        self.assertIn("PASSED", out.stdout)

    def test_a_miss_found_by_running_the_code_cannot_be_appealed(self):
        self.queue(self.CANDIDATES, self.WRITTEN)
        self.quiz()
        self.finish([graded(True)], wrong="predict")
        self.say("이의 I am sure it is 5")
        out = self.cli("maeng-interview", ["appeal"], self.repo)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("nothing to appeal", out.stderr)
        self.assertEqual(len(self.model_calls()), 3)  # no regrading call was made

    def test_fewer_than_two_confirmed_items_fall_back_to_two_written_questions(self):
        two = {"questions": [{"layer": 2, "topic": f"t{i}", "question": f"Q-w{i}", "rubric": [f"R-w{i}"]} for i in (1, 2)]}
        self.queue({"candidates": [ADD_MINUS, EQUIVALENT]}, two)
        r = self.quiz()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([("rubric" in it) for it in self.rec()["items"]], [True, True])
        self.assertIn("Question: Q-w1", r.stdout)
        self.assertIn("2 questions", self.model_calls()[1]["prompt"])
        self.finish([graded(True), graded(True)])
        self.assertTrue(interview.passed(self.key, 7, "merge", self.raw_patch(self.base, self.h)))

    def test_without_a_test_command_it_falls_back_too(self):
        self.declare(test=None)
        two = {"questions": [{"layer": 2, "topic": f"t{i}", "question": f"Q-w{i}", "rubric": [f"R-w{i}"]} for i in (1, 2)]}
        self.queue(two)  # no test command: the candidates are not even asked for
        self.quiz()
        self.assertEqual(len(self.rec()["items"]), 2)
        self.assertEqual(len(self.model_calls()), 1)
        (self.repo / ".maeng").mkdir()
        (self.repo / ".maeng/verify.json").write_text(json.dumps({"required": [PYTEST]}))
        self.git(self.repo, "add", "-A"); h = self.commit_all(self.repo, "policy")
        self.set_pr(h)
        interview.close_open(self.key, self.sid)
        self.queue(self.CANDIDATES, self.WRITTEN)
        self.quiz()
        self.assertEqual(len(self.rec()["items"]), 4)  # A-8: verify.json required[0] is the test command

    def test_a_dirty_tree_or_a_head_that_is_not_the_prs_is_refused_before_any_model_call(self):
        (self.repo / "scratch.txt").write_text("x")
        r = self.quiz()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("clean checkout", r.stderr)
        (self.repo / "scratch.txt").unlink()
        self.set_pr(self.base)
        self.assertIn("clean checkout", self.quiz().stderr)
        self.assertEqual(self.model_calls(), [])

    def test_a_headless_run_cannot_start_a_quiz(self):
        self.env["MAENG_TASK_ID"] = "t1"
        r = self.quiz()
        self.assertIn("headless", r.stderr)
        self.assertEqual(self.model_calls(), [])

    def test_a_second_run_with_the_same_patch_is_already_passed(self):
        interview.record_pass(self.key, "merge", pr=7, patch=self.raw_patch(self.base, self.h), head="an-older-head")
        r = self.quiz()
        self.assertIn("already has a merge pass", r.stdout)
        self.assertEqual(self.model_calls(), [])

    def test_a_pass_whose_head_is_an_ancestor_asks_one_item_about_the_delta(self):
        self.queue(self.CANDIDATES, self.WRITTEN)
        self.quiz()
        self.finish([graded(True)])
        (self.repo / "calc.py").write_text(CALC + "\n\ndef double(x):\n    return x * 2\n")
        (self.repo / "test_calc.py").write_text(TESTS.replace("clamp, is_even", "clamp, double, is_even") +
                                                "\n\ndef test_double():\n    assert double(4) == 8\n")
        h2 = self.commit_all(self.repo, "delta")
        self.set_pr(h2)
        n = len(self.model_calls())
        self.queue({"candidates": [{"kind": "predict", "file": "test_calc.py", "line": 21, "literal": "8", "question": "?"}]})
        r = self.quiz()
        self.assertEqual(r.returncode, 0, r.stderr)
        item, = self.rec()["items"]
        self.assertTrue(item["question"].endswith("test_calc.py:21\n    assert double(4) == ___"))
        self.assertEqual(len(self.model_calls()), n + 1)  # candidates only: no written question
        self.assertIn("calc.py, test_calc.py", self.model_calls()[n]["prompt"])
        self.finish()
        self.assertTrue(interview.passed(self.key, 7, "merge", self.raw_patch(self.base, h2)))

    def test_a_delta_item_must_be_on_the_new_lines(self):
        self.queue(self.CANDIDATES, self.WRITTEN)
        self.quiz()
        self.finish([graded(True)])
        (self.repo / "test_calc.py").write_text(TESTS + "\n\ndef test_more():\n    assert add(4, 4) == 8\n")
        h2 = self.commit_all(self.repo, "delta")
        self.set_pr(h2)
        self.assertEqual(quiz.added_lines(self.repo, f"{self.h}..{h2}"), {"test_calc.py": {18, 19, 20, 21}})
        self.queue({"candidates": [PREDICT_ADD]}, self.WRITTEN)  # an unchanged assertion: not about the delta
        r = self.quiz()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([("rubric" in it) for it in self.rec()["items"]], [True])

    def test_a_head_that_does_not_descend_from_the_passed_one_asks_a_full_quiz(self):
        self.queue(self.CANDIDATES, self.WRITTEN)
        self.quiz()
        self.finish([graded(True)])
        self.git(self.repo, "reset", "-q", "--hard", self.base)
        (self.repo / "calc.py").write_text(CALC)
        (self.repo / "test_calc.py").write_text(TESTS)
        (self.repo / "extra.txt").write_text("a different history\n")
        h3 = self.commit_all(self.repo, "rewritten")
        self.set_pr(h3)
        self.queue(self.CANDIDATES, self.WRITTEN)
        self.assertEqual(self.quiz().returncode, 0)
        self.assertEqual(len(self.rec()["items"]), 4)

    def test_a_rebase_that_keeps_the_patch_keeps_the_pass(self):
        self.queue(self.CANDIDATES, self.WRITTEN)
        self.quiz()
        self.finish([graded(True)])
        other = self.tmp / "other"
        self.git(self.tmp, "clone", "-q", str(self.tmp / "proj-remote.git"), str(other))
        (other / "elsewhere.txt").write_text("main moved\n")
        self.git(other, "add", "-A"); self.git(other, "commit", "-qm", "moved")
        self.git(other, "push", "-q", "origin", "main")
        self.git(self.repo, "fetch", "-q", "origin")
        self.git(self.repo, "rebase", "-q", "origin/main")
        self.set_pr(self.head(self.repo), base=self.git(self.repo, "rev-parse", "origin/main").stdout.strip())
        self.assertNotEqual(self.head(self.repo), self.h)
        self.assertIn("already has a merge pass", self.quiz().stdout)


if __name__ == "__main__":
    unittest.main()
