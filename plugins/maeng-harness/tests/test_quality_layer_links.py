"""Quality-layer pointers, closing walkthrough and evidence-based audit contracts."""
import json
import re
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
HARNESS = REPO / "plugins/maeng-harness"
RUN = HARNESS / "skills/harness-run/SKILL.md"
AUDIT = RUN.parent / "references/harness-audit.md"
TOOLS_SKILLS = ("aside-research", "coherent-writing", "presentation-design-interview", "motion-studio")
PREFIX = "Quality layer: for a non-code result the user will show or submit, follow "
SUFFIX = " (criteria from real examples, independent check, closing walkthrough)."


def check_pointer(text, target):
    """Keep one shared procedure: callers contain one pointer and no copied body."""
    if text.splitlines().count(PREFIX + target + SUFFIX) != 1:
        raise ValueError("expected exactly one quality-layer pointer line")
    if re.search(r"^(?:### P-|Order:|Output:|You are an independent checker)", text, re.M):
        raise ValueError("copied quality-layer body in pointing skill")


def check_evidence(component):
    """Resolve every evidence path; verified statuses need at least one file."""
    evidence = component.get("evidence", "")
    if not isinstance(evidence, str):
        raise ValueError("expected evidence text")
    paths = re.findall(r"[\w./-]+/[\w.-]+\.[A-Za-z0-9]+", evidence)
    for reference in paths:
        path = Path(reference)
        if path.is_absolute() or ".." in path.parts or not (REPO / path).is_file():
            raise ValueError("unresolvable evidence path: " + reference)
    if component["status"] != "unverified" and not paths:
        raise ValueError("expected at least one existing evidence path")


class QualityLayerLinks(unittest.TestCase):
    def test_pointer_in_each_skill_without_copied_body(self):
        check_pointer(RUN.read_text(), "[quality-layer](../quality-layer/SKILL.md)")
        for name in TOOLS_SKILLS:
            with self.subTest(skill=name):
                path = REPO / "plugins/maeng-tools/skills" / name / "SKILL.md"
                check_pointer(path.read_text(), "`maeng-harness:quality-layer`")

    def test_pointer_helper_rejects_tampered_strings(self):
        target = "`maeng-harness:quality-layer`"
        valid = PREFIX + target + SUFFIX + "\n"
        check_pointer(valid, target)
        for tampered in ("", valid * 2, valid + "### P-1: copied procedure\n", valid + "Order: copied steps\n",
                         valid + "Output: copied instructions\n", valid + "You are an independent checker.\n"):
            with self.subTest(tampered=tampered), self.assertRaises(ValueError):
                check_pointer(tampered, target)
        checker = (HARNESS / "skills/quality-layer/references/checker-prompt.md").read_text()
        output = "Output:" + checker.split("Output:", 1)[1].split("\n## ", 1)[0]
        coherent = (REPO / "plugins/maeng-tools/skills/coherent-writing/SKILL.md").read_text()
        check_pointer(coherent, target)
        with self.assertRaises(ValueError):
            check_pointer(coherent + "\n" + output, target)

    def test_closing_understanding_in_ceo_brief_and_merge_quiz_unchanged(self):
        text = RUN.read_text()
        brief = text.split("**CEO brief.**", 1)[1].split("\n\n**dots", 1)[0]
        item = re.search(r"^7\. \*\*Understanding\*\*: (.+)$", brief, re.M)
        self.assertIsNotNone(item)
        for phrase in ("3-5 questions", "only the user", "structure and design", "what was decided and why",
                       "discarded alternatives", "where the result differs from the request",
                       "what to check before shipping", "by default for every finished task", "skipping blocks nothing"):
            self.assertIn(phrase, item.group(1))
        self.assertIn("A PR over 150 changed lines, or one touching a mapped part, also needs the user's merge quiz "
                      "(comprehension-gate), started last once the review passed;", text)

    def test_inventory_covers_components_and_requires_evidence(self):
        inventory = json.loads((HARNESS / "policy/inventory.json").read_text())
        self.assertTrue(inventory["_comment"].strip())
        components = inventory["components"]
        paths = [c["path"] for c in components]
        self.assertEqual(len(paths), len(set(paths)), "duplicate inventory paths")
        expected = {p.relative_to(REPO).as_posix(): "skill" for p in (HARNESS / "skills").iterdir() if p.is_dir()}
        expected.update({p.relative_to(REPO).as_posix(): "bin" for p in (HARNESS / "bin").iterdir() if p.is_file()})
        expected.update({"plugins/maeng-harness/hooks/hooks.json": "hooks",
                         "plugins/maeng-harness/policy/roles.json": "policy"})
        self.assertIn("plugins/maeng-harness/skills/quality-layer", paths)
        self.assertEqual(set(paths), set(expected))
        for component in components:
            with self.subTest(path=component["path"]):
                path = Path(component["path"])
                self.assertFalse(path.is_absolute())
                self.assertNotIn("..", path.parts)
                self.assertTrue((REPO / path).exists(), str(path))
                self.assertEqual(component["kind"], expected[component["path"]])
                self.assertIn(component["status"], {"helps", "no-effect", "unverified", "safety"})
                self.assertIsInstance(component["assumes"], str)
                self.assertTrue(component["assumes"].strip())
                self.assertEqual(len(component["assumes"].splitlines()), 1)
                check_evidence(component)
        by_path = {c["path"]: c for c in components}
        for path in ("bin/maeng-verify", "bin/maeng-ship", "bin/maeng-review", "hooks/hooks.json"):
            component = by_path["plugins/maeng-harness/" + path]
            self.assertEqual(component["status"], "safety")
            tests = re.findall(r"plugins/maeng-harness/tests/test_[\w]+\.py", component["evidence"])
            self.assertTrue(tests, component["evidence"])
            for test in tests:
                self.assertTrue((REPO / test).is_file(), test)
        self.assertEqual(by_path["plugins/maeng-harness/skills/quality-layer"]["status"], "unverified")

    def test_evidence_helper_rejects_unsupported_claims_and_missing_references(self):
        inventory = json.loads((HARNESS / "policy/inventory.json").read_text())
        chart = next(c for c in inventory["components"] if c["path"].endswith("/chart-style"))
        existing = "plugins/maeng-harness/tests/test_quality_layer_links.py"
        missing = "docs/nonexistent-paired-results.json"
        check_evidence(chart)
        for status in ("helps", "no-effect", "safety", "unverified"):
            check_evidence(dict(chart, status=status, evidence=f"`{existing}`; named behavior tests"))
            for evidence in (missing, existing + "; " + missing):
                with self.subTest(status=status, evidence=evidence), self.assertRaises(ValueError):
                    check_evidence(dict(chart, status=status, evidence=evidence))
            if status != "unverified":
                for evidence in ("", "paired results exist", None):
                    with self.subTest(status=status, evidence=evidence), self.assertRaises(ValueError):
                        check_evidence(dict(chart, status=status, evidence=evidence))

    def test_audit_paths_proposal_and_paired_measurement_rule(self):
        text = AUDIT.read_text()
        paths = set(re.findall(r"tools/testperf/[\w-]+\.py", text))
        self.assertGreaterEqual(len(paths), 4)
        required = {"loopstats", "mutate", "review_replay", "impact_replay", "periodic_checks",
                    "plugin_checks", "subagent_context", "deny_coverage"}
        self.assertTrue({f"tools/testperf/{name}.py" for name in required} <= paths)
        for path in paths:
            self.assertTrue((REPO / path).is_file(), path)
        for phrase in ("## Proposal (not adopted): I-4", "Status: proposal only, awaiting the user's decision.",
                       "with/without pair on a fixed task", "order swapped", "Never conclude an effect from one run",
                       "Record noise", "statuses only with evidence", "**The user approves.**"):
            self.assertIn(phrase, text)
        for goal in range(1, 6):
            self.assertIn(f"G{goal}:", text)
        self.assertIn("[harness-audit.md](references/harness-audit.md)", RUN.read_text())


if __name__ == "__main__":
    unittest.main()
