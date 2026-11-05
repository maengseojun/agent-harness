"""Skill names and descriptions load into every session and subagent, so their total bytes are a context budget.

Stdlib only: the frontmatter reader covers the forms the skills use (plain, quoted, indented continuation, `>` and `|`).
"""
import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
# Total UTF-8 bytes of name + description over all plugins/*/skills/*/SKILL.md, counted 2026-11-06 over 49 skills.
BASE_BYTES = 20651


def _frontmatter(text):
    lines = text.split("\n")
    if lines[0] != "---":
        raise ValueError("no opening ---")
    end = lines.index("---", 1)
    return lines[1:end]


def _value(first, cont):
    """The value of one top-level key: `first` is the text after `key:`, `cont` the indented lines under it."""
    if first[:1] in (">", "|"):
        lines = [c.strip() for c in cont]
        if first[0] == "|":
            return "\n".join(lines).strip("\n")
        paragraphs, cur = [], []
        for line in lines + [""]:
            if line:
                cur.append(line)
            elif cur:
                paragraphs.append(" ".join(cur))
                cur = []
        return "\n".join(paragraphs)
    raw = " ".join([first] + [c.strip() for c in cont]).strip()
    if raw.startswith('"'):
        return json.loads(raw)
    if raw.startswith("'"):
        return raw[1:-1].replace("''", "'")
    return raw


def _fields(block):
    """Top-level `name` and `description` values of a frontmatter block."""
    out = {}
    i = 0
    while i < len(block):
        m = re.match(r"^([A-Za-z_][\w-]*):(?:[ \t]+(.*))?$", block[i])
        i += 1
        if not m:
            continue
        cont = []
        while i < len(block) and (block[i][:1] in (" ", "\t") or not block[i].strip()):
            cont.append(block[i])
            i += 1
        while cont and not cont[-1].strip():
            cont.pop()
        if m.group(1) in ("name", "description"):
            out[m.group(1)] = _value((m.group(2) or "").rstrip(), cont)
    return out


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
