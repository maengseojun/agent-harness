"""Skill names and descriptions load into every session and subagent, so their total bytes are a context budget.

Stdlib only: the frontmatter reader covers the forms the skills use (plain, quoted, indented continuation, `>` and `|`).
"""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "plugins/maeng-harness/lib"))
from maeng.skillbytes import _fields, _frontmatter

# Total UTF-8 bytes of name + description over all plugins/*/skills/*/SKILL.md, counted 2026-11-06 over 49 skills.
BASE_BYTES = 20651


def skill_sizes():
    """Map of each SKILL.md path (repo-relative) to the UTF-8 bytes of its name plus its description."""
    sizes = {}
    for path in sorted(REPO.glob("plugins/*/skills/*/SKILL.md")):
        fields = _fields(_frontmatter(path.read_text(encoding="utf-8")))
        sizes[path.relative_to(REPO).as_posix()] = len(fields["name"].encode("utf-8")) + len(
            fields["description"].encode("utf-8"))
    return sizes


def over_budget(total, base):
    return total > base


def _budget_message(sizes, total, base):
    top = sorted(sizes.items(), key=lambda kv: kv[1], reverse=True)[:3]
    largest = "; ".join("%s (%d bytes)" % (path, size) for path, size in top)
    return ("skill name + description bytes total %d, over the base %d. Largest: %s. Shorten a description, "
            "or raise BASE_BYTES in this file with the user's approval." % (total, base, largest))


class SkillBudgetTest(unittest.TestCase):
    def test_current_total_is_within_budget(self):
        sizes = skill_sizes()
        total = sum(sizes.values())
        self.assertFalse(over_budget(total, BASE_BYTES), _budget_message(sizes, total, BASE_BYTES))

    def test_one_byte_over_base_is_over_budget(self):
        self.assertTrue(over_budget(BASE_BYTES + 1, BASE_BYTES))

    def test_counts_skills_from_both_plugins(self):
        sizes = skill_sizes()
        self.assertGreaterEqual(len(sizes), 40)
        self.assertTrue(any(p.startswith("plugins/maeng-harness/") for p in sizes), sorted(sizes)[:3])
        self.assertTrue(any(p.startswith("plugins/maeng-tools/") for p in sizes), sorted(sizes)[:3])
