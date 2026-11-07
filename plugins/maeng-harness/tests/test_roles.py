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
COLLECT = REPO / "plugins/maeng-tools/skills/aside-collect/SKILL.md"
TEMPLATE = REPO / "plugins/maeng-harness/skills/harness-run/references/spec-plan.md"

KINDS = ["code_child", "code_small", "parent", "docs", "research", "notion", "plan"]
GRADES = ["quick", "standard", "deep", "design"]
EFFORTS = ["low", "medium", "high", "xhigh", "max"]
ENFORCED = ["code", "hook", "skill"]
COLLECT_ROUTES = ["research_collect_light", "research_collect_deep"]
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


def route_problems(d, collect_md):
    """resources and routes: every route names a listed resource, says what forces it, and the
    collection skill carries the same model and effort as the two research routes."""
    out = []
    resources, routes = d.get("resources", {}), d.get("routes", {})
    if not resources or not routes:
        return ["resources or routes missing"]
    for name, r in routes.items():
        for key in ("when", "resource", "enforcedBy", "where", "decidedBy"):
            if not r.get(key):
                out.append(f"routes.{name}.{key} missing")
        if r.get("resource") not in resources:
            out.append(f"routes.{name}.resource {r.get('resource')!r} is not in resources")
        if r.get("enforcedBy") not in ENFORCED:
            out.append(f"routes.{name}.enforcedBy {r.get('enforcedBy')!r} is not one of {ENFORCED}")
        if r.get("effort") is not None and r["effort"] not in EFFORTS:
            out.append(f"routes.{name} has effort {r['effort']!r}, not one of {EFFORTS}")
        v = r.get("verifiedAt")
        if v is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(v)):
            out.append(f"routes.{name}.verifiedAt is neither null nor an ISO date")
    text = Path(collect_md).read_text()
    for name in COLLECT_ROUTES:
        r = routes.get(name)
        if not r:
            out.append(f"routes.{name} missing")
            continue
        flag = f"--model openai/{r.get('model')} --effort {r.get('effort')}"
        if flag not in text:
            out.append(f"aside-collect SKILL.md does not carry {flag!r} of routes.{name}")
    if "aside exec --effort low" in text:
        out.append("aside-collect SKILL.md still runs aside exec without a model")
    return out


def problems(roles_path, agents_dir, skill_md, review_md, collect_md=None, template_md=None):
    out = []
    try:
        d = json.loads(Path(roles_path).read_text())
    except (OSError, ValueError) as e:
        return [f"roles.json unreadable: {e}"]
    roles, grades = d.get("roles", {}), d.get("grades", {})
    if collect_md is not None:
        out += route_problems(d, collect_md)
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
    if template_md is not None:  # the Plan template a planner copies, not only the SKILL.md glossary (AC-3)
        tsec = Path(template_md).read_text().split("Sub-tasks:", 1)[-1].split("\nVerification", 1)[0]
        if not any("| Grade |" in l for l in tsec.split("\n")):
            out.append("spec-plan.md Sub-tasks block has no Grade column")
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
        shutil.copy(COLLECT, self.tmp / "collect.md")
        shutil.copy(TEMPLATE, self.tmp / "spec-plan.md")

    def check(self):
        return problems(self.tmp / "roles.json", self.tmp / "agents", self.tmp / "SKILL.md", self.tmp / "review.md",
                        self.tmp / "collect.md", self.tmp / "spec-plan.md")

    def edit(self, name, fn):
        p = self.tmp / name
        p.write_text(fn(p.read_text()))

    def test_real_tree_agrees(self):
        self.assertEqual(problems(ROLES, AGENTS, SKILL, REVIEW, COLLECT, TEMPLATE), [])
        self.assertEqual(self.check(), [])

    def test_definition_effort_changed(self):
        self.edit("agents/standard.md", lambda t: t.replace("effort: medium", "effort: high"))
        self.assertTrue(any("standard.md: effort" in p for p in self.check()))

    def test_template_grade_column_deleted(self):
        self.edit("spec-plan.md", lambda s: s.replace("| Grade |", "|"))
        self.assertTrue(any("spec-plan.md" in p for p in self.check()))

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


    def test_collect_effort_changed(self):
        self.edit("collect.md", lambda t: t.replace("openai/gpt-6-astra --effort medium", "openai/gpt-6-astra --effort low"))
        self.assertTrue(any("routes.research_collect_deep" in p for p in self.check()))

    def test_route_names_unknown_resource(self):
        def f(t):
            d = json.loads(t)
            d["routes"]["claim_check"]["resource"] = "nowhere"
            return json.dumps(d)
        self.edit("roles.json", f)
        self.assertTrue(any("claim_check.resource" in p for p in self.check()))

    def test_routes_section_removed(self):
        def f(t):
            d = json.loads(t)
            del d["routes"]
            return json.dumps(d)
        self.edit("roles.json", f)
        self.assertTrue(any("resources or routes missing" in p for p in self.check()))


if __name__ == "__main__":
    unittest.main()
