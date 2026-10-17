"""Runner recognition, tree-bound evidence, ship-verified and stop-satisfied predicates."""
import fnmatch
import hashlib
import os
import posixpath
import re
from pathlib import Path

from . import tree as treelib
from .common import now_iso
from .shellparse import ENV_ASSIGN, WRAPPER_PREFIX, ParseError, program, split_segments
from .state import bump

TEST_KINDS = "test"
PY_RE = re.compile(r"^python[\d.]*$")


# ---- runner recognition (closed-world allowlist) -------------------------
#
# A command is evidence only when it matches a canonical runner form with an allowlisted set of flags. Any flag,
# operand or launcher option not listed below makes the invocation "not evidence" (deny by default): dry runs,
# listings, --collect-only, --help, --version and the like are therefore never evidence.

BENIGN_FLAG = re.compile(r"^(?:-v+|-q+|--verbose|--quiet)$")
PYTEST_BENIGN = re.compile(r"^(?:-v+|-q+|-s|-x|--verbose|--quiet|--no-header|-r[aAsSxXfFpPEeQw]+|--color=\S+|--tb=\S+)$")
PATH_RE = re.compile(r"^[A-Za-z0-9_./:\[\]@+,%-]+$")
VALUE_RE = re.compile(r"^[^\s$`-][^$`]*$")
NAME_RE_ = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")
UNSAFE_ENV = re.compile(r"ADDOPTS|FLAGS|OVERRIDES|_OPTIONS$|^(?:PATH|PYTHON\w*|LD_\w+|DYLD_\w+|PYTEST_\w+)$", re.I)

# Output that shows no test ran: such a run is not evidence even when it exits 0. A positive marker (some tests ran,
# e.g. `go test ./...` printing `[no test files]` for one package) wins.
ZERO_TESTS = re.compile(r"\bRan 0 tests?\b|collected 0 items|\bno tests ran\b|\bno test files\b", re.I)
RAN_SOME = re.compile(r"\bRan [1-9]\d* tests?\b|collected [1-9]\d* items?|\b[1-9]\d* passed\b|^ok\s", re.I | re.M)

# Narrowing flags that are never evidence at all (the run can silently skip tests); selectors that merely filter
# (pytest -k/-m, forge --match-*/--no-match-*, go -run) stay allowed but are never default-mode evidence.
NARROWING_REJECTED = ("--ignore", "--ignore-glob", "--deselect", "--lf", "--last-failed", "--ff", "--failed-first",
                      "--nf", "--new-first", "--sw", "--stepwise", "-short", "--skip", "--exact")


def ran_zero_tests(text):
    """True when the runner output shows that zero tests ran."""
    text = text or ""
    return bool(ZERO_TESTS.search(text)) and not RAN_SOME.search(text)


def _narrowed(args):
    for a in args:
        name = a.partition("=")[0]
        if name in NARROWING_REJECTED:
            return True
    return False
INT_RE = re.compile(r"^\d+$")
PY_PLAIN_OPTS = {"-B", "-u", "-I", "-E", "-s"}
LAUNCHER_PLAIN = {"-y", "--yes", "--no-install", "--no", "--quiet", "-q"}
LAUNCHER_VALUE_OPTS = {"-p", "--package"}


def _result(name, kind, args):
    """(name, kind, identity): identity = runner + args, whitespace-normalized, minus verbosity-only flags."""
    benign = PYTEST_BENIGN if name == "pytest" else BENIGN_FLAG
    kept = [a for a in args if not benign.match(a)]
    return name, kind, " ".join([name, *kept])


def _parse_args(args, bools=(), values=None, pos=None, pos_min=0, pos_max=None, eq_short=False):
    """Validate `args` against an allowlist spec. `bools`: exact strings or compiled regexes; `values`: {flag:
    value-regex} accepted as `--flag=V` / `--flag V` / `-f V`; `pos`: regex for operands (None: no operands).
    -> True when every token is allowed."""
    values = values or {}
    n_pos, i = 0, 0
    while i < len(args):
        t = args[i]
        if "$" in t or "`" in t:
            return False
        name, eq, val = t.partition("=")
        if any(b == t if isinstance(b, str) else b.match(t) for b in bools):
            pass
        elif t.startswith("-"):
            rx = values.get(name if eq else t)
            if rx is None or (eq and not (name.startswith("--") or eq_short)):
                return False
            if eq:
                if not rx.match(val):
                    return False
            else:
                if i + 1 >= len(args) or not rx.match(args[i + 1]):
                    return False
                i += 1
        else:
            if pos is None or not pos.match(t):
                return False
            n_pos += 1
        i += 1
    return n_pos >= pos_min and (pos_max is None or n_pos <= pos_max)


R = re.compile
PYTEST_BOOLS = (R(r"^-v+$"), R(r"^-q+$"), "-x", "-s", "--verbose", "--quiet", "--no-header", R(r"^-r[a-zA-Z]+$"),
                R(r"^--color=(yes|no|auto)$"), R(r"^--tb=(auto|long|short|line|native|no)$"), "-pno:cacheprovider",
                R(r"^-n\d+$"))
PYTEST_VALUES = {"-k": VALUE_RE, "-m": VALUE_RE, "--maxfail": R(r"^\d+$"), "-p": R(r"^no:cacheprovider$"),
                 "-n": R(r"^(\d+|auto)$")}
UNITTEST_BOOLS = (R(r"^-v+$"), "-q", "--quiet", "--verbose")
UNITTEST_VALUES = {"-s": PATH_RE, "-t": PATH_RE, "-p": R(r"^[A-Za-z0-9_.*?-]+$"), "--start-directory": PATH_RE,
                   "--top-level-directory": PATH_RE, "--pattern": R(r"^[A-Za-z0-9_.*?-]+$")}
FORGE_VALUES = {f"--{p}match-{k}": VALUE_RE for p in ("", "no-") for k in ("test", "contract", "path")}
CARGO_BOOLS = ("--all", "--workspace", "--all-features", "--release", "-q")
CARGO_VALUES = {"-p": NAME_RE_, "--package": NAME_RE_}
GO_BOOLS = ("-v", "-race", "-json")
# -count=0 (and `-run` patterns that cannot select a test) make `go test` exit 0 without running any test
GO_RUN_RE = R(r"^(?=.*[A-Za-z0-9_])(?!.*[^|(/]\^)[A-Za-z0-9_|()./*+?\[\]^-]+$")
GO_VALUES = {"-run": GO_RUN_RE, "-count": R(r"^[1-9]\d*$")}
SCRIPTS = ("lint", "build", "typecheck")


def _unwrap_launcher(args):
    """npx / pnpm dlx / yarn dlx / npm exec: only the listed launcher options are skipped; the runner's own
    arguments must then pass that runner's allowlist."""
    i = 0
    while i < len(args):
        t = args[i]
        if t == "--":
            i += 1
            break
        if not t.startswith("-"):
            break
        if t in LAUNCHER_PLAIN:
            i += 1
        elif t in LAUNCHER_VALUE_OPTS and i + 1 < len(args):
            i += 2
        else:
            return None  # any other launcher option (--help, --version, -c, --call, ...): not evidence
    rest = args[i:]
    return _runner(rest) if rest else None


def _runner(tokens):
    """Return (name, kind, identity) if this segment is exactly an allowlisted runner invocation."""
    toks0 = list(tokens)
    i = 0
    while i < len(toks0) and ENV_ASSIGN.match(toks0[i]):  # every leading assignment is checked
        name, _, val = toks0[i].partition("=")
        if UNSAFE_ENV.search(name) or "$" in val or "`" in val:
            return None
        i += 1
    if i < len(toks0) and os.path.basename(toks0[i]) in WRAPPER_PREFIX:
        return None  # env/sudo/nice/nohup/command/exec/time/builtin change what runs: not evidence
    prog, toks = program(tokens)
    if not prog or any("$" in t or "`" in t for t in toks):
        return None
    if prog in ("uv", "poetry", "pipenv") and len(toks) > 2 and toks[1] == "run":
        rest = [t for t in toks[2:] if t != "--"]
        return _runner(rest)
    if prog == "npx":
        return _unwrap_launcher(toks[1:])
    if prog in ("pnpm", "yarn", "npm") and len(toks) > 2 and toks[1] in ("dlx", "exec"):
        return _unwrap_launcher(toks[2:])
    if PY_RE.match(prog):
        i = 1  # only `<python> [-B|-u|-I|-E|-s ...] -m <runner> ...`; any other interpreter option is no evidence
        while i < len(toks) and toks[i] in PY_PLAIN_OPTS:
            i += 1
        if i + 1 < len(toks) and toks[i] == "-m":
            mod, rest = toks[i + 1], toks[i + 2:]
            return _module_runner(mod, rest)
        return None
    if prog in ("pytest", "py.test"):
        return _module_runner("pytest", toks[1:])
    if prog == "mypy":
        return _module_runner("mypy", toks[1:])
    if prog == "ruff":
        return _module_runner("ruff", toks[1:])
    if prog == "tsc":
        ok = _parse_args(toks[1:], ("--noEmit",), {"-p": PATH_RE, "--project": PATH_RE})
        return _result("tsc", "check", toks[1:]) if ok else None
    args = toks[1:]
    sub, rest = (args[0], args[1:]) if args else (None, [])
    if prog == "forge" and sub in ("test", "build"):
        if _parse_args(rest, (R(r"^-v+$"),), FORGE_VALUES):
            return _result(f"forge {sub}", TEST_KINDS if sub == "test" else "check", rest)
        return None
    if prog == "cargo" and sub in ("test", "clippy", "build"):
        if _narrowed(rest):
            return None
        if _parse_args(rest, CARGO_BOOLS, CARGO_VALUES):
            return _result(f"cargo {sub}", TEST_KINDS if sub == "test" else "check", rest)
        return None
    if prog == "go" and sub == "test":
        if _narrowed(rest):
            return None
        if _parse_args(rest, GO_BOOLS, GO_VALUES, pos=PATH_RE, eq_short=True):
            return _result("go test", TEST_KINDS, rest)
        return None
    if prog == "make":
        # only target names; no -n/--dry-run/-q/--question/-t/--touch (or any other flag or VAR=value)
        if len(args) == 1 and args[0] in ("test", "check"):
            return _result(f"make {args[0]}", TEST_KINDS, [])
        return None
    if prog == "playwright" and sub == "test":
        if _parse_args(rest, (), {"--project": VALUE_RE}, pos=PATH_RE):
            return _result("playwright test", TEST_KINDS, rest)
        return None
    if prog == "claude" and args[:2] == ["plugin", "validate"]:
        if _parse_args(args[2:], (), None, pos=PATH_RE, pos_min=1, pos_max=1):
            return _result("claude plugin validate", "check", args[2:])
        return None
    if prog in ("npm", "pnpm", "yarn"):
        if args in (["test"], ["t"]):
            return _result(f"{prog} test", TEST_KINDS, [])
        if len(args) == 2 and args[0] == "run" and args[1] == "test":
            return _result(f"{prog} test", TEST_KINDS, [])
        if len(args) == 2 and args[0] == "run" and args[1] in SCRIPTS:
            return _result(f"{prog} run {args[1]}", "check", [])
        if prog == "yarn" and len(args) == 1 and args[0] in SCRIPTS:
            return _result(f"yarn run {args[0]}", "check", [])
    return None


def _module_runner(mod, rest):
    if mod in ("pytest", "unittest") and _narrowed(rest):
        return None
    if mod == "pytest":
        if _parse_args(rest, PYTEST_BOOLS, PYTEST_VALUES, pos=PATH_RE):
            return _result("pytest", TEST_KINDS, rest)
    elif mod == "unittest":
        if _parse_args(rest, UNITTEST_BOOLS, UNITTEST_VALUES, pos=PATH_RE):
            return _result("unittest", TEST_KINDS, rest)
    elif mod == "mypy":
        if _parse_args(rest, (), None, pos=PATH_RE):
            return _result("mypy", "check", rest)
    elif mod == "ruff":
        if rest[:1] == ["check"] and _parse_args(rest[1:], (), None, pos=PATH_RE):
            return _result("ruff check", "check", rest[1:])
    return None



# Default mode ("some passing tests") only accepts an UNFILTERED suite run: selectors such as pytest -k/-m or
# paths, go -run or package lists, forge --match-*, unittest -p/names and playwright paths/--project can
# select nothing and still exit 0. Filtered runs satisfy only an explicit Plan requirement with that filter.
_UNFILTERED_ARGS = {
    "pytest": re.compile(r"^(-x|--exitfirst|--maxfail=\d+|-n|\d+|-p|no:cacheprovider|--tb=\w+)$"),
    "unittest": re.compile(r"^(discover|-s|-t|-q|-v|--quiet|--verbose|[\w./-]+)$"),
    "go test": re.compile(r"^(\./\.\.\.|-race|-v|-json|-count=[1-9]\d*)$"),
    "cargo test": re.compile(r"^(--all|--workspace|--all-features|--release|-q|--quiet)$"),
    "forge test": re.compile(r"^-v+$"),
}


def unfiltered(identity):
    """True when a test identity runs the whole suite (no selector that could match nothing)."""
    if "@" in identity:
        return False  # run from a subdirectory: only part of the suite
    base = identity
    if base.startswith("playwright test"):
        return base == "playwright test"  # paths, --project or --grep select a subset
    for name, ok in _UNFILTERED_ARGS.items():
        if base == name or base.startswith(name + " "):
            rest = base[len(name):].split()
            if name == "unittest":
                # Only `discover` with -s/-t directories (no -p pattern, no module or test names).
                if not rest:
                    return True
                if rest[0] != "discover" or "-p" in rest:
                    return False
                flags = rest[1:]
                return all(t in ("-q", "-v", "--quiet", "--verbose") or flags[i - 1] in ("-s", "-t") or t in ("-s", "-t")
                           for i, t in enumerate(flags))
            return all(ok.match(t) for t in rest)
    return True  # make test/check, npm|pnpm|yarn test, playwright without args: no selector accepted

def recognize(command):
    """-> {'checks': [(name, kind, identity)], 'cd': dir|None} or None (also for background/compound)."""
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

def rel_dir(run_cwd, top):
    """Working directory relative to the repository root ('' for the root itself)."""
    if not (run_cwd and top):
        return ""
    try:
        rel = os.path.relpath(os.path.realpath(run_cwd), os.path.realpath(top))
    except ValueError:
        return ""
    return "" if rel == "." or rel.startswith("..") else rel.replace(os.sep, "/")


def scoped_identity(identity, rel):
    return f"{identity}@{rel}" if rel else identity


def pre_runner(st, key, command, rec, tree_start, common, rel=""):
    st["pending"][key] = {"cmd": command, "checks": rec["checks"], "tree_start": tree_start, "common": common,
                          "dir": rel}


def post_runner(st, key, ok, tree_finish):
    pend = st["pending"].pop(key, None)
    if not pend:
        return []
    started = pend["tree_start"]
    if ok and (not started or started != tree_finish):
        return []  # code changed during the check, or tree undecidable: no evidence
    added, rel = [], pend.get("dir") or ""
    for name, kind, identity in pend["checks"]:
        added.append(add_evidence(st, name, kind, pend["cmd"], ok, started, tree_finish, pend["common"], "runner",
                                  scoped_identity(identity, rel), rel))
    return added


def norm_identity(text):
    return " ".join(str(text).replace("`", "").split())


def add_evidence(st, check, kind, cmd, ok, tree_start, tree_finish, common, source, identity=None, rel=""):
    ev = {"seq": bump(st), "check": check, "kind": kind, "cmd": cmd, "identity": identity or norm_identity(check),
          "dir": rel, "ok": bool(ok), "tree_start": tree_start,
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

def _identity(ev):
    return (ev.get("identity") or norm_identity(ev["check"])).lower()


def _norm_dir(path):
    path = posixpath.normpath(path.strip()) if path.strip() else ""
    return "" if path in (".", "") else path


def parse_requirement(pat):
    """A required-check string -> [(identity, dir, is_runner)], ALL of which must be satisfied. `a && b` / `a; b` are
    compound; `cd X &&` scopes later constituents to X (relative to the repository root). A constituent that parses as
    a recognized runner invocation (is_runner) is satisfied only by runner evidence, never by a declaration."""
    literal = [(norm_identity(pat).lower(), "", False)]
    if "`" in pat or "$(" in pat:
        return literal
    try:
        segs = split_segments(pat)
    except ParseError:
        return literal
    if not segs or any(s.op_after not in ("&&", ";", "") or s.redirects for s in segs):
        return literal
    out, cur = [], ""
    for seg in segs:
        prog, toks = program(seg.tokens)
        if prog == "cd" and len(toks) == 2:
            cur = _norm_dir(toks[1])
            continue
        r = _runner(seg.tokens)
        if r:
            out.append((r[2].lower(), cur, True))
        elif len(segs) == 1:
            return literal
        else:
            out.append((norm_identity(" ".join(seg.tokens)).lower(), cur, False))
    return out or literal


def _ev_ident(ev):
    ident = (ev.get("identity") or norm_identity(ev["check"])).lower()
    rel = ev.get("dir") or ""
    suffix = f"@{rel}".lower()
    return (ident[:-len(suffix)] if rel and ident.endswith(suffix) else ident), rel


def requirement_met(good, pat):
    return all(any(_ev_ident(e)[1] == d and (_ev_ident(e)[0] == p or fnmatch.fnmatchcase(_ev_ident(e)[0], p))
                   and (not runner or e.get("source") == "runner") for e in good)
               for p, d, runner in parse_requirement(pat))


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
        if self.policy.get("invalid"):
            return False, ["invalid verification policy: " + self.policy["invalid"]]
        reasons = []
        evs = self._evidence()
        good = [e for e in evs if e["ok"] and e["tree_start"] and e["tree_start"] == e["tree_finish"]
                and self.eq(e["tree_finish"], tree)]
        mode, pats = self.required()
        if mode == "default":
            if not any(e["kind"] == TEST_KINDS and unfiltered(e.get("identity") or "") for e in good):
                reasons.append("no passing test-runner evidence for this tree (evidence counts only for a recognized "
                               "test runner run as one plain command, e.g. `python3 -m pytest -q`; pipes, `;` and `&&` "
                               "hide its exit status; filtered runs such as `-k`, `-run` or test paths do not count here)")
        else:
            for p in pats:
                if not requirement_met(good, p):
                    reasons.append(f"required check not passed on this tree: {p}")
        for f in evs:
            if not f["ok"] and f["tree_finish"] and self.eq(f["tree_finish"], tree):
                if not any(_identity(g) == _identity(f) and g["seq"] > f["seq"] for g in good):
                    reasons.append(f"unresolved failure: {f.get('identity') or f['check']}")
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
