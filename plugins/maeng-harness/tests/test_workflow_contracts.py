"""MAE-323 bundle 2 (AC-9, AC-10, AC-11): the rule documents carry the structural fields the workflow relies on, and
every command example in them parses against the real CLI. Values are literals; no English sentence is pinned,
only field names, flags and table cells the code or a reader looks up. Stdlib only."""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # plugins/maeng-harness
REPO = ROOT.parents[1]
RUN = ROOT / "skills" / "harness-run"
REFS = RUN / "references"
AGENTS = REPO / "plugins" / "maeng-tools" / "agents"
CONTEXT = REPO / "tools" / "testperf" / "subagent_context.py"
SKILL = RUN / "SKILL.md"
ORG = REFS / "org-chart.md"
SPEC = REFS / "spec-plan.md"
VERIFY = REFS / "verification.md"
REVIEW = REFS / "review-and-ship.md"
ONBOARD = REFS / "model-onboarding.md"
BRIEFS = [REPO / "plugins/maeng-harness/skills/task-brief/SKILL.md",
          REPO / "plugins/maeng-harness/skills/execute-code-brief/SKILL.md", ORG]
DEFS = [AGENTS / f"{n}.md" for n in ("quick", "standard", "design")]
DOCS = [SKILL, SPEC, ORG, VERIFY, REVIEW, ONBOARD, *BRIEFS[:2], *DEFS]

STAGES = [("interview", "doc"), ("spec/plan", "doc"), ("bind", "code"), ("implement", "doc"), ("verify", "code"),
          ("review", "code"), ("merge", "code"), ("records", "doc")]
FIELDS = ["TASK", "DELIVERABLE", "SCOPE", "VERIFY", "STOP WHEN"]
RETIRED = [r"\bmax(imum)? 4\b", r"\b(4|four) (stored )?(review )?(rounds|runs)\b", r"\bat most four\b",
           r"\bfifth review\b", r"\bStop\b(?![^.\n]*\bnever\b)[^.\n]{0,40}\bblocks\b"]


def table(text, header):
    """Rows (list of cells) of the markdown table whose header row starts with `header`."""
    lines, rows = text.split("\n"), []
    start = next(i for i, l in enumerate(lines) if l.startswith(header))
    for l in lines[start + 2:]:
        if not l.startswith("|"):
            break
        rows.append([c.strip() for c in l.strip().strip("|").split("|")])
    return rows


class StageTable(unittest.TestCase):
    def rows(self):
        return table(SKILL.read_text(), "| Stage |")

    def test_every_stage_in_order(self):
        self.assertEqual([r[0] for r in self.rows()], [s for s, _ in STAGES])

    def test_enforcement_column(self):
        for row, (stage, kind) in zip(self.rows(), STAGES):
            with self.subTest(stage=stage):
                self.assertEqual(len(row), 4)
                self.assertTrue(row[1] and row[2], "entry and exit criteria must be filled")
                tokens = re.findall(r"`([^`]+)`", row[3])
                self.assertEqual(tokens[0], kind)
                if kind == "code":
                    self.assertTrue(tokens[1:], "a code row names the script that enforces it")
                for path in tokens[1:]:
                    self.assertTrue((ROOT / path).is_file(), f"{path} is not a file under plugins/maeng-harness")


class Delegation(unittest.TestCase):
    def test_five_field_brief_everywhere(self):
        for path in BRIEFS:
            for field in FIELDS:
                with self.subTest(doc=path.name, field=field):
                    self.assertIn(f"`{field}:`", path.read_text())

    def test_report_convention_in_personal_definitions(self):
        for path in DEFS:
            t = path.read_text()
            with self.subTest(definition=path.name):
                self.assertTrue(t.index("Status: done | partial | blocked") < t.index("`Verification:`") < t.index("`Unfinished:`"))
                self.assertIn("general-purpose", t)

    def test_omit_claude_md_only_on_design(self):
        has = {p.stem: "omitClaudeMd: true" in p.read_text().split("\n---", 1)[0] for p in sorted(AGENTS.glob("*.md"))}
        self.assertEqual([n for n, v in has.items() if v], ["design"])

    def test_personal_definitions_are_default_in_harness_run(self):
        self.assertIn("general-purpose", SKILL.read_text())


class EvidenceAndTrustRules(unittest.TestCase):
    def test_evidence_ranking(self):
        self.assertRegex(VERIFY.read_text(), r"runner\s*>\s*declared\s*>\s*agent report")

    def test_terms_the_rules_name(self):
        t = VERIFY.read_text()
        for term in ("flaky", "unavailable", "impact.py run", "informational", "failing reproduction"):
            with self.subTest(term=term):
                self.assertIn(term, t)

    def test_fails_if_names_negative_paths(self):
        for path in (VERIFY, SPEC):
            with self.subTest(doc=path.name):
                self.assertTrue(any(all(w in l for w in ("null", "empty", "negative", "exception"))
                                    for l in path.read_text().split("\n")))
        self.assertIn("Fails-if", VERIFY.read_text())


class ReviewRules(unittest.TestCase):
    def test_verdict_rules_listed(self):
        t = REVIEW.read_text()
        for n in range(1, 7):
            self.assertRegex(t, rf"\bV-{n}\b")

    def test_max_rounds_default_matches_code(self):
        code = (ROOT / "bin" / "maeng-review").read_text()
        default = re.search(r'"--max-rounds",\s*type=int,\s*default=(\d+)', code).group(1)
        self.assertEqual(default, "2")
        self.assertRegex(REVIEW.read_text(), rf"`--max-rounds`, default {default}\b")

    def test_plan_review_order_matches_prompt(self):
        order = "structure, code quality, tests, performance"
        self.assertIn(order, (ROOT / "bin" / "maeng-review").read_text())
        spec = SPEC.read_text()
        self.assertIn(order, spec)
        self.assertLess(spec.index("scope first"), spec.index(order))

    def test_plan_template_fields(self):
        t = SPEC.read_text()
        self.assertIn("Discarded alternatives:", t)
        head = next(l for l in t.split("\n") if "| Criterion |" in l)
        self.assertEqual([c.strip() for c in head.strip().strip("|").split("|")],
                         ["Criterion", "Responsible row", "Verification"])

    def test_retired_sentences_are_gone(self):
        for path in DOCS:
            for pat in RETIRED:
                with self.subTest(doc=path.name, pattern=pat):
                    self.assertIsNone(re.search(pat, path.read_text()))


class ModelOnboarding(unittest.TestCase):
    def step(self, number, title):
        match = re.search(rf"(?ms)^## {number}\. {title}\n(.*?)(?=^## |\Z)", ONBOARD.read_text())
        self.assertIsNotNone(match, f"missing onboarding step {number}: {title}")
        return match.group(1)

    def test_response_probe_rejects_unusable_responses(self):
        t = self.step(1, "Probe the response")
        for term in ("response probe", "exact model ID", "effort", "CLI", "observed model ID"):
            with self.subTest(term=term):
                self.assertIn(term, t)
        self.assertRegex(t, r"Mark[^.]*`invalid`[^.]*refusal[^.]*empty[^.]*malformed[^.]*failed[^.]*wrong model")
        self.assertRegex(t, r"Stop[^.]*until[^.]*valid response")

    def test_official_documentation_and_deprecation_checks(self):
        t = self.step(2, "Check official sources")
        for term in ("official model documentation", "CLI documentation", "deprecation", "incumbent", "candidate",
                     "source URLs", "checked-at dates", "retirement dates", "`unknown`"):
            with self.subTest(term=term):
                self.assertIn(term, t)

    def test_candidate_row_stays_outside_policy(self):
        t = self.step(3, "Record the candidate")
        self.assertRegex(t, r"outside[^.]*`[^`]*roles\.json`")
        rows = table(t, "| Status |")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "candidate")
        self.assertEqual(len(rows[0]), 9)
        self.assertTrue(all(rows[0]))

    def test_fixed_pair_is_nonempty_and_identical_for_both_models(self):
        t = self.step(4, "Compare a fixed task pair")
        rows = table(t, "| Task ID | Representative task |")
        self.assertEqual([r[0] for r in rows], ["implement", "review"])
        self.assertTrue(all(len(r) == 3 and all(r) for r in rows))
        for term in ("Freeze", "nonempty task IDs", "input bundles", "digests", "judging criteria", "Reject an empty pair",
                     "both tasks", "incumbent", "candidate", "identical inputs and judging criteria", "Restart both models"):
            with self.subTest(term=term):
                self.assertIn(term, t)

    def test_comparison_record_preserves_measurements_and_unknown_usage(self):
        t = self.step(4, "Compare a fixed task pair")
        header = next(l for l in t.splitlines() if l.startswith("| Task ID | Model ID |"))
        self.assertEqual([c.strip() for c in header.strip("|").split("|")],
                         ["Task ID", "Model ID", "CLI ID/version", "Effort", "Response validity", "Quality",
                          "Elapsed seconds", "Usage", "Limitations", "Evidence"])
        self.assertRegex(t, r"usage[^.]*when available[^.]*`unknown`[^.]*never zero")
        self.assertIn("four result rows", t)

    def test_approval_stop_precedes_replacement_and_recheck(self):
        t = self.step(5, "Stop for user approval")
        self.assertRegex(t, r"\*\*STOP[^*]*user approval[^*]*before[^*]*replacing[^*]*role[^*]*editing[^*]*roles\.json[^*]*\*\*")
        self.assertRegex(t, r"candidate row[^.]*not approval")
        self.assertRegex(t, r"After[^.]*approved replacement[^.]*recheck[^.]*sourceUrl[^.]*verifiedAt")
        self.assertIn("python3 -m pytest -q plugins/maeng-harness/tests/test_roles.py plugins/maeng-harness/tests/test_docs_sync.py", t)
        self.assertIn("Record the results", t)

    def test_review_rules_link_to_the_procedure(self):
        self.assertRegex(REVIEW.read_text(), r"\[[^\]]+\]\(model-onboarding\.md\)")


FLAG = re.compile(r"(?:(?<=\s)|(?<=[\[|,]))(--?[A-Za-z][\w-]*)")
CHOICES = re.compile(r"(--[\w-]+) \{([^}]*)\}")
SPAN = re.compile(r"`([^`\n]+)`")
HELP = {}


def cli_help(argv):
    key = tuple(argv)
    if key not in HELP:
        p = subprocess.run([*argv, "--help"], capture_output=True, text=True)
        HELP[key] = (p.returncode, p.stdout)
    return HELP[key]


def example_problems(span):
    """What the real CLI's --help says is wrong with one code-span command, or [] (also for a span that is no command)."""
    span = re.sub(r"^(\w+=\S+\s+)+", "", span.strip())
    tokens = span.split()
    if tokens[:3] == ["python3", "-m", "pytest"]:
        argv, rest = [sys.executable, "-m", "pytest"], tokens[3:]
    elif tokens and tokens[0] in ("maeng-review", "maeng-verify", "maeng-ship"):
        if len(tokens) < 2 or tokens[1].startswith("-"):
            return []
        argv, rest = [sys.executable, str(ROOT / "bin" / tokens[0]), tokens[1]], tokens[2:]
    else:
        return []
    if "--" in rest:
        rest = rest[:rest.index("--")]
    rc, text = cli_help(argv)
    if rc != 0:
        return [f"{' '.join(tokens[:2])}: no such command"]
    known = set(FLAG.findall(text)) | {"-h", "--help"}
    out = [f"{f} is not a flag of {' '.join(tokens[:2])}" for f in FLAG.findall(" " + " ".join(rest)) if f not in known]
    for flag, choices in set(CHOICES.findall(text)):
        if flag in rest and rest.index(flag) + 1 < len(rest):
            value = rest[rest.index(flag) + 1]
            if not value.startswith(("<", "-", "[")) and value not in choices.split(","):
                out.append(f"{flag} {value} is not one of {choices}")
    return out


class ExecutableExamples(unittest.TestCase):
    def test_examples_parse_against_the_real_cli(self):
        seen = 0
        for path in DOCS:
            for span in SPAN.findall(path.read_text()):
                bad = example_problems(span)
                seen += bool(re.match(r"(\w+=\S+\s+)*(maeng-(review|verify|ship)|python3 -m pytest)\b", span))
                with self.subTest(doc=path.name, example=span):
                    self.assertEqual(bad, [])
        self.assertGreaterEqual(seen, 12)

    def test_checker_rejects_a_bad_flag_and_a_bad_choice(self):
        self.assertEqual(example_problems("maeng-review run --kind plan --confirm"), [])
        self.assertEqual(len(example_problems("maeng-review run --nonsense")), 1)
        self.assertEqual(len(example_problems("maeng-review run --kind nonsense")), 1)
        self.assertEqual(len(example_problems("maeng-verify nonsense")), 1)
        self.assertEqual(example_problems("python3 -m pytest -q -n 8"), [])


# The context-measurement cases live in test_subagent_context.py (they need a transcript fixture).
if __name__ == "__main__":
    unittest.main()
