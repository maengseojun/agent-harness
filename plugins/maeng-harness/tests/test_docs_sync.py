"""verification.md's runner forms must stay in sync with the lib/maeng/evidence.py allowlist."""
import itertools
import re
import unittest

from maeng import evidence
from .helpers import ROOT

DOC = ROOT / "skills" / "harness-run" / "references" / "verification.md"
FAMILIES = ("pytest", "unittest", "npm", "pnpm", "yarn", "forge", "cargo", "go test", "make", "ruff", "mypy", "tsc",
            "claude plugin validate", "playwright")
NOTES = {"t", "run", "run test", "npm lint", "pnpm build"}  # backticked asides in the sentence, not runner forms
PLACEHOLDER = {"DIR": "tests", "PATH": "plugins/x", "paths": "src", "X": "pkg"}


def forms():
    text = DOC.read_text()
    sentence = re.search(r"Use the plain forms[^:]*:(.*?)\. Requirements written", text, re.S).group(1)
    return [f for f in re.findall(r"`([^`]+)`", sentence) if f not in NOTES]


def expand(form):
    """Concrete instances of a documented form: alternatives `a|b` pick each one, `[...]` groups are tried absent and
    with each option, bare placeholders get a value."""
    m = re.search(r"\[([^\[\]]*)\]", form)
    if m:
        opts = m.group(1).split("|")
        out = [form[:m.start()] + form[m.end():]]
        for o in opts:
            out.append(form[:m.start()] + o + form[m.end():])
        return [x for f in out for x in expand(f)]
    m = re.search(r"(\S+(?:\|\S+)+)", form)
    if m:
        return [x for o in m.group(1).split("|") for x in expand(form[:m.start()] + o + form[m.end():])]
    return [" ".join(PLACEHOLDER.get(w, w) for w in form.split())]


class RunnerFormsInSync(unittest.TestCase):
    def test_doc_lists_forms(self):
        self.assertGreaterEqual(len(forms()), 14)

    def test_every_documented_form_is_recognized(self):
        for form in forms():
            if form.startswith("npm|pnpm|yarn"):
                continue  # covered by test_package_manager_forms
            for inst in expand(form):
                with self.subTest(form=form, instance=inst):
                    self.assertIsNotNone(evidence.recognize(inst), f"verification.md lists `{form}` but {inst!r} is not evidence")

    def test_package_manager_forms(self):
        for form in (f for f in forms() if f.startswith("npm|pnpm|yarn")):
            for inst in expand(form):
                with self.subTest(form=form, instance=inst):
                    self.assertIsNotNone(evidence.recognize(inst))
        for pm, tail in itertools.product(("npm", "pnpm", "yarn"), ("t", "run test")):
            self.assertIsNotNone(evidence.recognize(f"{pm} {tail}"), f"{pm} {tail}")  # the "(also t or run test)" note
        self.assertIsNotNone(evidence.recognize("yarn lint"))
        for bad in ("npm lint", "pnpm build"):  # the doc says these do not count
            self.assertIsNone(evidence.recognize(bad), bad)

    def test_every_runner_family_is_documented(self):
        text = DOC.read_text()
        sentence = re.search(r"Use the plain forms.*?Requirements written", text, re.S).group(0)
        for fam in FAMILIES:
            self.assertIn(fam, sentence, f"evidence.py recognizes {fam} but verification.md's plain-forms list omits it")
        # every family named is really recognized
        samples = {"pytest": "python3 -m pytest -q", "unittest": "python3 -m unittest discover", "npm": "npm test",
                   "pnpm": "pnpm test", "yarn": "yarn test", "forge": "forge test", "cargo": "cargo test",
                   "go test": "go test ./...", "make": "make test", "ruff": "ruff check", "mypy": "mypy",
                   "tsc": "tsc --noEmit", "claude plugin validate": "claude plugin validate plugins/x",
                   "playwright": "playwright test"}
        self.assertEqual(set(samples), set(FAMILIES))
        for fam, cmd in samples.items():
            self.assertIsNotNone(evidence.recognize(cmd), fam)


if __name__ == "__main__":
    unittest.main()
