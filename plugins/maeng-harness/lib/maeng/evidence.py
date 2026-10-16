"""Runner recognition, tree-bound evidence, ship-verified and stop-satisfied predicates."""
import fnmatch
import hashlib
import re
from pathlib import Path

from . import tree as treelib
from .common import now_iso
from .shellparse import ParseError, program, split_segments
from .state import bump

TEST_KINDS = "test"
PY_RE = re.compile(r"^python[\d.]*$")


# ---- runner recognition -------------------------------------------------

def _first_arg(toks, skip_flags=True):
    for t in toks[1:]:
        if not (skip_flags and t.startswith("-")):
            return t
    return None


def _runner(tokens):
    """Return (name, kind) if this segment is a recognized check runner."""
    prog, toks = program(tokens)
    if not prog:
        return None
    if prog in ("uv", "poetry", "pipenv") and len(toks) > 2 and toks[1] == "run":
        rest = [t for t in toks[2:] if t != "--"]
        return _runner(rest)
    if prog == "npx":
        rest = [t for t in toks[1:] if not t.startswith("-")]
        return _runner(rest) if rest else None
    if PY_RE.match(prog):
        if "-m" in toks[1:-1]:
            i = toks.index("-m")
            mod, rest = toks[i + 1], toks[i + 1:]
            return {"pytest": ("pytest", TEST_KINDS), "unittest": ("unittest", TEST_KINDS),
                    "mypy": ("mypy", "check")}.get(mod) or (
                ("ruff check", "check") if mod == "ruff" and _first_arg(rest) == "check" else None)
        return None
    if prog in ("pytest", "py.test"):
        return "pytest", TEST_KINDS
    if prog in ("mypy", "tsc"):
        return prog, "check"
    sub = _first_arg(toks)
    table = {
        "ruff": {"check": ("ruff check", "check")},
        "forge": {"test": ("forge test", TEST_KINDS), "build": ("forge build", "check")},
        "cargo": {"test": ("cargo test", TEST_KINDS), "clippy": ("cargo clippy", "check"),
                  "build": ("cargo build", "check")},
        "go": {"test": ("go test", TEST_KINDS)},
        "make": {"test": ("make test", TEST_KINDS), "check": ("make check", TEST_KINDS)},
        "playwright": {"test": ("playwright test", TEST_KINDS)},
    }
    if prog in table:
        return table[prog].get(sub)
    if prog == "claude" and toks[1:3] == ["plugin", "validate"]:
        return "claude plugin validate", "check"
    if prog in ("npm", "pnpm", "yarn"):
        args = [t for t in toks[1:] if not t.startswith("-")]
        if args[:1] in (["test"], ["t"]):
            return f"{prog} test", TEST_KINDS
        script = args[1] if args[:1] == ["run"] and len(args) > 1 else (args[0] if prog == "yarn" and args else None)
        if script in ("lint", "build", "typecheck"):
            return f"{prog} run {script}", "check"
        if script == "test":
            return f"{prog} test", TEST_KINDS
    return None


def recognize(command):
    """-> {'checks': [(name, kind)], 'cd': dir|None} or None (also for background/compound)."""
    try:
        segs = split_segments(command)
    except ParseError:
        return None
    checks, cd = [], None
    for seg in segs:
        if seg.op_after not in ("&&", ""):
            return None
        prog, toks = program(seg.tokens)
        if prog == "cd" and len(toks) == 2 and not checks:
            cd = toks[1]
            continue
        r = _runner(seg.tokens)
        if r is None:
            return None
        checks.append(r)
    return {"checks": checks, "cd": cd} if checks else None


# ---- recording (pure functions over the state dict) ---------------------

def pre_runner(st, key, command, rec, tree_start, common):
    st["pending"][key] = {"cmd": command, "checks": rec["checks"], "tree_start": tree_start, "common": common}


def post_runner(st, key, ok, tree_finish):
    pend = st["pending"].pop(key, None)
    if not pend:
        return []
    started = pend["tree_start"]
    if ok and (not started or started != tree_finish):
        return []  # code changed during the check, or tree undecidable: no evidence
    added = []
    for name, kind in pend["checks"]:
        added.append(add_evidence(st, name, kind, pend["cmd"], ok, started, tree_finish, pend["common"], "runner"))
    return added


def add_evidence(st, check, kind, cmd, ok, tree_start, tree_finish, common, source):
    ev = {"seq": bump(st), "check": check, "kind": kind, "cmd": cmd, "ok": bool(ok), "tree_start": tree_start,
          "tree_finish": tree_finish, "finished_at": now_iso(), "common": common, "source": source}
    st["evidence"].append(ev)
    return ev


def add_skip(st, reason, tree, common):
    st["skips"].append({"seq": bump(st), "reason": reason, "tree": tree, "common": common, "at": now_iso()})


def add_plan_record(st, met, unmet, notes, tree, common, plan_updated_at):
    st["plan_records"].append({"seq": bump(st), "met": sorted(met), "unmet": sorted(unmet), "notes": notes,
                               "tree": tree, "common": common, "plan_updated_at": plan_updated_at})


# ---- binding / plan -----------------------------------------------------

def parse_plan_text(text):
    criteria = list(dict.fromkeys(re.findall(r"\bAC-\d+\b", text)))
    checks, in_section = [], False
    for line in text.splitlines():
        if re.match(r"^#+\s*verification\b", line, re.I):
            in_section = True
            continue
        if in_section and re.match(r"^#+\s", line):
            in_section = False
        if in_section:
            m = re.match(r"^\W*AC-\d+\W+(.+)$", line.strip())
            if m:
                checks.append(m.group(1).strip().strip("`"))
    return criteria, checks


def make_binding(issue, plan_doc=None, plan_updated=None, criteria=None, checks=None, parent=None, repo=None,
                 world="personal"):
    b = {"issue": issue, "plan_doc": plan_doc, "plan_updated_at": plan_updated, "criteria": criteria or [],
         "checks": checks or [], "parent": parent, "repo": repo, "world": world, "plan_hash": None}
    if plan_doc and Path(plan_doc).is_file():
        text = Path(plan_doc).read_text(encoding="utf-8")
        c, ch = parse_plan_text(text)
        b["criteria"] = criteria or c
        b["checks"] = checks or ch
        b["plan_hash"] = hashlib.sha256(text.encode()).hexdigest()[:16]
        b["plan_updated_at"] = plan_updated or time_of(plan_doc)
    return b


def time_of(path):
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(Path(path).stat().st_mtime))


def plan_is_stale(binding):
    """A local plan file edited after bind -> criteria are stale until re-bound."""
    doc = binding.get("plan_doc")
    if not doc or not Path(doc).is_file() or not binding.get("plan_hash"):
        return False
    return hashlib.sha256(Path(doc).read_bytes()).hexdigest()[:16] != binding["plan_hash"]


# ---- predicates ---------------------------------------------------------

def _matches(ev, pat):
    pat_l, check = pat.lower(), ev["check"].lower()
    rec = recognize(pat)
    if rec:
        return ev["check"] in [n for n, _ in rec["checks"]]
    return fnmatch.fnmatch(check, pat_l) or pat_l in check or check in pat_l or pat_l in ev["cmd"].lower()


class Verifier:
    def __init__(self, st, top, common):
        self.st, self.top, self.common = st, top, common
        self.policy = treelib.load_policy(top)
        self._memo = {}

    def eq(self, a, b):
        if not a or not b:
            return False
        k = (a, b)
        if k not in self._memo:
            self._memo[k] = treelib.relevant_equal(self.top, a, b, self.policy)
        return self._memo[k]

    def required(self):
        binding = self.st.get("binding")
        if binding and binding.get("checks"):
            return "plan", binding["checks"]
        if self.policy.get("required"):
            return "policy", list(self.policy["required"])
        return "default", []

    def _evidence(self):
        return [e for e in self.st["evidence"] if e.get("common") == self.common]

    def ship_verified(self, tree):
        """(ok, reasons). Skips never count here."""
        if not tree:
            return False, ["tree id unavailable (dirty submodule or git failure)"]
        reasons = []
        evs = self._evidence()
        good = [e for e in evs if e["ok"] and e["tree_start"] and e["tree_start"] == e["tree_finish"]
                and self.eq(e["tree_finish"], tree)]
        mode, pats = self.required()
        if mode == "default":
            if not any(e["kind"] == TEST_KINDS for e in good):
                reasons.append("no passing test-runner evidence for this tree")
        else:
            for p in pats:
                if not any(_matches(e, p) for e in good):
                    reasons.append(f"required check not passed on this tree: {p}")
        for f in evs:
            if not f["ok"] and f["tree_finish"] and self.eq(f["tree_finish"], tree):
                if not any(g["check"] == f["check"] and g["seq"] > f["seq"] for g in good):
                    reasons.append(f"unresolved failure: {f['check']}")
        reasons += self._plan_reasons(tree)
        return not reasons, reasons

    def _plan_reasons(self, tree):
        b = self.st.get("binding")
        if not b:
            return []
        if plan_is_stale(b):
            return ["plan changed since bind: re-run maeng-verify bind"]
        if not b.get("criteria"):
            return []
        recs = [r for r in self.st["plan_records"] if r.get("common") == self.common and self.eq(r["tree"], tree)]
        if not recs:
            return ["no plan record (maeng-verify plan --met ...) for this tree"]
        last = max(recs, key=lambda r: r["seq"])
        out = []
        if last["plan_updated_at"] != b.get("plan_updated_at"):
            out.append("plan record is stale (criteria updatedAt changed)")
        missing = [c for c in b["criteria"] if c not in last["met"]]
        if last["unmet"]:
            out.append("unmet criteria: " + ", ".join(last["unmet"]))
        if missing:
            out.append("criteria not marked met: " + ", ".join(missing))
        return out

    def skipped(self, tree):
        return any(s.get("common") == self.common and self.eq(s["tree"], tree) for s in self.st["skips"])

    def stop_satisfied(self, tree):
        ok, _ = self.ship_verified(tree)
        return ok or self.skipped(tree)

    def code_changed_since(self, base_tree, tree):
        if not base_tree:
            return False
        diff = treelib.relevant_diff(self.top, base_tree, tree, self.policy)
        return diff is None or bool(diff)
