"""policy/roles.json, the agent definitions and the rule-document tables must agree. Stdlib only."""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROLES = REPO / "plugins/maeng-harness/policy/roles.json"
AGENTS = REPO / "plugins/maeng-tools/agents"
SKILL = REPO / "plugins/maeng-harness/skills/harness-run/SKILL.md"
REVIEW = REPO / "plugins/maeng-harness/skills/harness-run/references/review-and-ship.md"

KINDS = ["code_child", "code_small", "parent", "docs", "research", "notion", "plan"]
GRADES = ["quick", "standard", "deep", "design"]
EFFORTS = ["low", "medium", "high", "xhigh", "max"]
NAMES = {"Sol": "gpt-6.1-sol", "Astra": "gpt-6-astra", "Opus": "claude-opus-5-5", "Fable": "claude-fable-5-1"}
# review-and-ship.md subject prefix -> roles.json kind
TIER_ROWS = {"Child-task PR": "code_child", "Parent integration": "parent", "Architecture, rules": "docs",
             "Small implementation": "code_small", "Notion outcome": "notion", "Research draft": "research"}


def _front(path):
    lines = Path(path).read_text().split("\n")
    end = lines.index("---", 1)
    return dict(l.split(": ", 1) for l in lines[1:end] if ": " in l)


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _pair(cell):
    """'Opus high (first)' -> ('claude-opus-5-5', 'high'); '-' or 'none (skipped)' -> None."""
    m = re.match(r"(\w+)(?:\s+(\w+))?", cell)
    return (NAMES.get(m.group(1)), m.group(2)) if m and m.group(1) in NAMES else None


def problems(roles_path, agents_dir, skill_md, review_md):
    out = []
    try:
        d = json.loads(Path(roles_path).read_text())
    except (OSError, ValueError) as e:
        return [f"roles.json unreadable: {e}"]
    roles, grades = d.get("roles", {}), d.get("grades", {})
    for k in KINDS:
        if k not in roles:
            out.append(f"roles.{k} missing")
    for g in GRADES:
        if g not in grades:
            out.append(f"grades.{g} missing")
    rows = [(f"roles.{k}", r) for k, r in roles.items()] + [(f"grades.{k}", r) for k, r in grades.items()]
    for name, r in rows:
        for key in ("model", "effort", "standby"):
            if key not in r:
                out.append(f"{name}.{key} missing")
        if not str(r.get("sourceUrl", "")).startswith("https://"):
            out.append(f"{name}.sourceUrl is not an https url")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(r.get("verifiedAt", ""))):
            out.append(f"{name}.verifiedAt missing or not an ISO date")
        for e in [r.get("effort")] + [s.get("effort") for s in r.get("standby", []) if isinstance(s, dict)]:
            if e not in EFFORTS:
                out.append(f"{name} has effort {e!r}, not one of {EFFORTS}")
        if name.startswith("grades."):
            if r.get("ceiling") in EFFORTS and r.get("effort") in EFFORTS and EFFORTS.index(r["effort"]) > EFFORTS.index(r["ceiling"]):
                out.append(f"{name}.effort is above its ceiling")
        elif r.get("range"):
            lo, hi = r["range"]
            if r.get("effort") in EFFORTS and not EFFORTS.index(lo) <= EFFORTS.index(r["effort"]) <= EFFORTS.index(hi):
                out.append(f"{name}.effort is outside its range")
    for g, r in grades.items():
        f = Path(agents_dir) / f"{r.get('agent')}.md"
        if not f.is_file():
            out.append(f"grades.{g}: agent file {f.name} missing")
            continue
        fm = _front(f)
        if "tools" not in fm:
            out.append(f"{f.name}: no tools")
        if fm.get("model") not in str(r.get("model")):
            out.append(f"{f.name}: model {fm.get('model')!r} does not match grades.{g}.model {r.get('model')}")
        want = grades.get(r.get("agent"), {}).get("effort")
        if fm.get("effort") != want:
            out.append(f"{f.name}: effort {fm.get('effort')!r} differs from grades.{r.get('agent')}.effort {want!r}")
    skill = Path(skill_md).read_text()
    sec = skill.split("## Sub-tasks", 1)[-1].split("\n## ", 1)[0]
    grow = [l for l in sec.split("\n") if l.startswith("| Grade |")]
    if not grow:
        out.append("SKILL.md Sub-tasks table has no Grade row")
    for named in re.findall(r"`(quick|standard|deep|design|\w+)`", grow[0]) if grow else []:
        if named not in grades:
            out.append(f"SKILL.md Grade row names {named!r}, not in grades")
    for line in Path(review_md).read_text().split("\n"):
        c = _cells(line) if line.startswith("|") else []
        kind = next((k for p, k in TIER_ROWS.items() if c and c[0].startswith(p)), None)
        if not kind or kind not in roles or len(c) < 4:
            continue
        r, label = roles[kind], c[0]
        s = r.get("standby", [])
        if kind == "parent":
            want = {"codex": (s[0]["model"], s[0]["effort"]), "claude": (r["model"], r["effort"])}
        else:
            opus = next((x for x in s if x["model"] == NAMES["Opus"]), {})
            want = {"codex": (r["model"], r["effort"]), "claude": (opus.get("model"), opus.get("effort"))}
        got_codex = _pair(c[1])
        got_codex = (got_codex[0], c[2]) if got_codex else None
        if got_codex != want["codex"]:
            out.append(f"review table row {label!r}: reviewer {got_codex} differs from roles.{kind} {want['codex']}")
        if _pair(c[3]) != want["claude"]:
            out.append(f"review table row {label!r}: standby {_pair(c[3])} differs from roles.{kind} {want['claude']}")
    return out


class RolesSync(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        shutil.copy(ROLES, self.tmp / "roles.json")
        shutil.copytree(AGENTS, self.tmp / "agents")
        shutil.copy(SKILL, self.tmp / "SKILL.md")
        shutil.copy(REVIEW, self.tmp / "review.md")

    def check(self):
        return problems(self.tmp / "roles.json", self.tmp / "agents", self.tmp / "SKILL.md", self.tmp / "review.md")

    def edit(self, name, fn):
        p = self.tmp / name
        p.write_text(fn(p.read_text()))

    def test_real_tree_agrees(self):
        self.assertEqual(problems(ROLES, AGENTS, SKILL, REVIEW), [])
        self.assertEqual(self.check(), [])

    def test_definition_effort_changed(self):
        self.edit("agents/standard.md", lambda t: t.replace("effort: medium", "effort: high"))
        self.assertTrue(any("standard.md: effort" in p for p in self.check()))

    def test_grade_row_deleted(self):
        self.edit("SKILL.md", lambda t: "\n".join(l for l in t.split("\n") if not l.startswith("| Grade |")))
        self.assertTrue(any("no Grade row" in p for p in self.check()))

    def test_verified_at_removed(self):
        def f(t):
            d = json.loads(t)
            del d["roles"]["notion"]["verifiedAt"]
            return json.dumps(d)
        self.edit("roles.json", f)
        self.assertTrue(any("roles.notion.verifiedAt" in p for p in self.check()))

    def test_review_cell_back_to_medium(self):
        self.edit("review.md", lambda t: re.sub(r"(Child-task PR[^\n]*\| )Opus high", r"\1Opus medium", t))
        self.assertTrue(any("Child-task PR" in p for p in self.check()))


if __name__ == "__main__":
    unittest.main()
