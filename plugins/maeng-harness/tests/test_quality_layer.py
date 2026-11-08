"""Non-blocking quality-layer structure, standard validation, and hook boundaries."""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/quality-layer/SKILL.md"
CHECKER = ROOT / "skills/quality-layer/scripts/check_std.py"
FIXTURES = ROOT / "tests/fixtures/quality_layer"


def copied_body(text):
    """Detect a procedure heading or the checker prompt in a pointer skill."""
    return bool(re.search(r"^(?:### P-|Order:)", text, re.M))


def structure_problems(text):
    """Check procedure structure only; this does not measure effectiveness."""
    headings = list(re.finditer(r"^### P-([0-9]+) .+$", text, re.M))
    out = []
    if [int(h[1]) for h in headings] != list(range(1, 12)):
        out.append("expected P-1 through P-11 in order")
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        if not re.search(r"^Fails: .+$", text[heading.end():end], re.M):
            out.append(f"P-{heading[1]} has no failure line")
    return out


class QualityLayerTest(unittest.TestCase):
    def run_std(self, *paths):
        return subprocess.run([sys.executable, str(CHECKER), *map(str, paths)],
                              capture_output=True, text=True, check=False)

    def test_structure_real_skill(self):
        self.assertEqual(structure_problems(SKILL.read_text(encoding="utf-8")), [])

    def test_structure_tampered_and_empty(self):
        text = SKILL.read_text(encoding="utf-8")
        variants = ["", "No procedure markers.",
                    text.replace("### P-4 ", "### P-5 ", 1),
                    text.replace("### P-1 ", "### P-12 ", 1),
                    re.sub(r"^Fails: .+\n?", "", text, count=1, flags=re.M)]
        for variant in variants:
            with self.subTest(variant=variant[:80]):
                self.assertTrue(structure_problems(variant))

    def test_structure_copied_body_helper(self):
        for text in ("### P-1 Establish the target", "Intro\n### P-11 Record\n", "Order:\n1. Read"):
            with self.subTest(text=text):
                self.assertTrue(copied_body(text))
        self.assertFalse(copied_body("Use the quality-layer skill for substantial non-code work."))
        self.assertFalse(copied_body("The Order: label is mentioned in prose."))

    def test_std_fixtures(self):
        for name in ("valid", "missing_tag", "quote_absent", "eight_conditions", "empty", "zero_quotes"):
            with self.subTest(name=name):
                path = FIXTURES / f"{name}.md"
                result = self.run_std(path)
                self.assertEqual(result.returncode, 0 if name == "valid" else 1, result.stdout + result.stderr)
                if name == "valid":
                    self.assertEqual(result.stdout, "")
                else:
                    self.assertRegex(result.stdout, rf"^{re.escape(str(path))}:[0-9]+: .+")
                    self.assertNotIn("Traceback", result.stderr)

    def test_std_field_and_section_errors(self):
        valid = (FIXTURES / "valid.md").read_text(encoding="utf-8")
        variants = [
            (valid.replace("S1 |", "C1 |", 1), "bad condition id"),
            (valid.replace("2026-11-09", "2026-02-30", 1), "bad condition date"),
            (valid.replace("2026-11-09", "20261109", 1), "bad condition date"),
            (valid.replace("current", "unknown", 1), "bad condition status"),
            (valid.replace("| author |", "| other |", 1), "unknown condition tag"),
            (valid.replace("Explain the structure.", "", 1), "empty condition sentence"),
            (valid.replace("source: source.md", "source: missing.md", 1), "cannot read source"),
            (valid.replace("source: source.md", "source: /source.md", 1), "source path must be relative"),
            (valid.replace('"Keep the example brief."', '""', 1), "missing or empty quoted text"),
            (valid.replace("## Conditions", "## Examples"), "no Conditions section"),
            ("## Conditions\n\n## Examples\n- not a condition\n", "zero conditions"),
            ("## Conditions\n- S1\n", "missing condition fields or tag"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "standard.md"
            (path.parent / "source.md").write_text((FIXTURES / "source.md").read_text(), encoding="utf-8")
            for text, expected in variants:
                with self.subTest(expected=expected):
                    path.write_text(text, encoding="utf-8")
                    result = self.run_std(path)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn(expected, result.stdout)

    def test_std_alternate_heading_and_section_boundary(self):
        text = (FIXTURES / "valid.md").read_text(encoding="utf-8")
        text = text.replace("## Conditions", "## \uC870\uAC74")
        text += "\n## Other material\n- this is not a condition\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "standard.md"
            path.write_text(text, encoding="utf-8")
            (path.parent / "source.md").write_text((FIXTURES / "source.md").read_text(), encoding="utf-8")
            result = self.run_std(path)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_std_missing_file_and_multiple_files(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.md"
            result = self.run_std(FIXTURES / "valid.md", missing, FIXTURES / "quote_absent.md")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn(f"{missing}:1: cannot read standard", result.stdout)
            self.assertIn("quote absent from source", result.stdout)
            self.assertNotIn("valid.md:", result.stdout)

    def test_std_usage(self):
        result = self.run_std()
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage:", result.stderr)

    def test_hook_has_no_quality_layer_dependency(self):
        paths = sorted((ROOT / "hooks").glob("*.py"))
        paths += [ROOT / "hooks/hooks.json"]
        paths += sorted((ROOT / "lib/maeng").glob("*.py"))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(path=path):
                self.assertNotRegex(path.read_text(encoding="utf-8"), r"quality-layer|check_std")


if __name__ == "__main__":
    unittest.main()
