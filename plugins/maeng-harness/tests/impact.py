#!/usr/bin/env python3
"""Test impact analysis: pick the tests a change can affect.

  impact.py build            run the suite under coverage (one context per test) and write the map
  impact.py select [REV] [--json]   print the pytest node ids affected by changes since REV (default: the map's base)
  impact.py run [REV] [-- pytest args]   select, then run them with pytest (-n auto when xdist is installed)

`run` and `select` build the map themselves when coverage is installed and the map is missing or was built at a
commit that is no longer an ancestor of HEAD; without a usable map they fall back to the full suite and say so. `run` falls
back to the full suite, and says why on stderr, when the selection is empty, names a file that no longer exists,
cannot be computed, or when pytest collects nothing from it (exit 5) or rejects a node id (exit 4). A genuine test
failure (exit 1) is returned as is: no full rerun hides it. The last stderr line is `impact-summary: {...}` with
mode (narrow | all | fallback), the selected count, the fallback reason, the executed-test count the runner printed
("unavailable" when it printed none) and the exit code. Its runs are working checks, never ship evidence
(MAE-323 AC-7/AC-8): the hook does not recognize `impact.py run` as a runner.

Two layers (MAE-232 D-6):
1. Static graph: Python imports between test files, lib/maeng modules, bin scripts and the hook entry, plus literal
   path references (bin names, schemas/, config/). Proven helper events follow their handler's functions and
   globals; unknown events, raw input, dynamic calls and unresolved inheritance retain the full dispatcher closure.
   Process-boundary tests retain that closure too.
2. Coverage map (built by `build`, refreshed on demand): for every function in lib/bin/hooks, the tests that ran
   one of its lines. A change inside a function selects those tests. A change at module level, or in a function
   the map has no tests for, falls back to the static graph (module code runs once per worker, so the map
   under-counts its readers). The map is keyed by the commit it was built at; changes are diffed against it.

Conservative fallbacks: tests/helpers.py, conftest.py, __init__.py, requirements*, hooks.json, plugin manifests,
anything unknown under plugins/maeng-harness -> every test. A new source file not in the map -> the static graph.
Docs and skills -> the tests that read them (test_plugin, test_docs_sync). A boundary test (the same scenario in a
real process, which the in-process coverage map cannot see) is selected with its in-process twin, and every boundary
test is selected when an entry point (hooks/, bin/) changes.
"""
import ast
import builtins
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# MAENG_IMPACT_PLUGIN: run this selector against another checkout of the plugin (the AC-7 replay runs the current
# selector on historical trees); the map, the tests and lib/ are read from there.
PLUGIN = Path(os.environ.get("MAENG_IMPACT_PLUGIN") or Path(__file__).resolve().parents[1]).resolve()
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))  # this selector's own lib, whichever tree it reads
from maeng.evidence import test_count  # noqa: E402

TESTS = PLUGIN / "tests"
MAP = PLUGIN / ".impact" / "map.json"
ALL = "__all__"
SHARED = {"tests/helpers.py", "tests/conftest.py", "tests/__init__.py", "tests/impact.py"}
BOUNDARY = "tests/test_boundary.py"
DOC_TESTS = ["tests/test_plugin.py", "tests/test_docs_sync.py"]


def sh(*args, cwd=PLUGIN, check=True):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if check and p.returncode != 0:
        raise SystemExit(f"{' '.join(args)} failed: {p.stderr.strip()}")
    return p.stdout


def repo_root():
    return Path(sh("git", "rev-parse", "--show-toplevel").strip())


def rel(path):
    """Path relative to the plugin root (posix)."""
    return Path(path).resolve().relative_to(PLUGIN).as_posix()


# ---- static layer ---------------------------------------------------------

def _source_files():
    out = {}
    for p in sorted((PLUGIN / "lib/maeng").glob("*.py")):
        out[f"maeng.{p.stem}" if p.stem != "__init__" else "maeng"] = rel(p)
    for p in sorted((PLUGIN / "bin").iterdir()):
        if p.is_file():
            out[f"bin:{p.name}"] = rel(p)
    out["hook"] = "hooks/maeng_hooks.py"
    return out


def _imports(path):
    """lib modules a Python file imports (maeng.x names)."""
    try:
        tree = ast.parse(Path(path).read_text())
    except (SyntaxError, UnicodeDecodeError):
        return set()
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level and Path(path).parent.name == "maeng":  # relative import inside lib/maeng
                base = "maeng" + ("." + base if base else "")
            if base == "maeng":
                mods |= {f"maeng.{a.name}" for a in node.names}
            elif base.startswith("maeng."):
                mods.add(base)
        elif isinstance(node, ast.Import):
            mods |= {a.name for a in node.names if a.name.startswith("maeng")}
    return mods


def _event_imports(path):
    """Event -> handler imports, following local functions and globals. None means unresolved dispatch."""
    try:
        tree = ast.parse(Path(path).read_text())
    except (OSError, SyntaxError, UnicodeDecodeError):
        return {}
    symbols, imports, module_code, routes = {}, {}, [], None
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name == "*":
                    return {}
                if isinstance(node, ast.Import) and alias.name.startswith("maeng.") and not alias.asname:
                    return {}  # the bound package can expose modules beyond this import
                base = (node.module or "") if isinstance(node, ast.ImportFrom) else ""
                if isinstance(node, ast.ImportFrom) and node.level:
                    base = "maeng" + ("." + base if base else "")
                mod = f"{base}.{alias.name}" if base == "maeng" else base or alias.name
                name = alias.asname or alias.name.split(".")[0]
                if name in imports and imports[name] != mod:
                    return {}  # a repeated package/alias binding is not a proven event dependency
                imports[name] = mod
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols[node.name] = node
            module_code += [*node.decorator_list, node.args, *([node.returns] if node.returns else [])]
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    return {}
                symbols[target.id] = node.value
                if target.id == "HANDLERS":
                    routes = node.value
            if not any(isinstance(t, ast.Name) and t.id == "HANDLERS" for t in node.targets):
                module_code.append(node.value)
        else:
            module_code.append(node)
    if not isinstance(routes, ast.Dict) or any(not isinstance(k, ast.Constant) or not isinstance(k.value, str)
                                               for k in routes.keys):
        return {}
    data_methods = {n for cls in (dict, list, set, tuple, str) for n in dir(cls) if not n.startswith("_")}
    out = {}
    for key, entry in zip(routes.keys, routes.values):
        seen, deps, todo = set(), set(), [entry, *module_code]
        dynamic = not (isinstance(entry, ast.Lambda) or isinstance(entry, ast.Name) and
                       isinstance(symbols.get(entry.id), (ast.FunctionDef, ast.AsyncFunctionDef)))
        while todo:
            node = todo.pop()
            functions = {n.name for n in ast.walk(node) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            for ref in ast.walk(node):
                if isinstance(ref, (ast.FunctionDef, ast.AsyncFunctionDef)) and ref.decorator_list:
                    dynamic = True
                if isinstance(ref, (ast.Import, ast.ImportFrom)):
                    dynamic = True  # a local import is outside the proven module bindings
                if isinstance(ref, ast.Call):
                    if isinstance(ref.func, ast.Attribute):
                        root = ref.func.value
                        while isinstance(root, ast.Attribute):
                            root = root.value
                        known = (isinstance(root, ast.Name) and root.id in imports.keys() | symbols.keys() or
                                 isinstance(root, ast.Constant) or isinstance(root, ast.Call) and
                                 isinstance(root.func, ast.Name) and root.func.id in imports.keys() | vars(builtins).keys())
                        if not known and ref.func.attr not in data_methods:
                            dynamic = True
                    elif isinstance(ref.func, ast.Name):
                        name = ref.func.id
                        if name in ("getattr", "globals", "locals", "eval", "exec", "__import__") or not (
                                name in imports or name in functions or name in vars(builtins) or
                                isinstance(symbols.get(name), (ast.FunctionDef, ast.AsyncFunctionDef))):
                            dynamic = True
                    elif not isinstance(ref.func, (ast.Attribute, ast.Lambda)):
                        dynamic = True
                if isinstance(ref, ast.Name) and isinstance(ref.ctx, ast.Load):
                    name = ref.id
                    if name in imports and imports[name].startswith("maeng"):
                        deps.add(imports[name])
                    if name in symbols and name not in seen:
                        seen.add(name)
                        todo.append(symbols[name])
        out[key.value] = None if dynamic else deps
    return out


def _test_events(text, helper_tree, events):
    """Prove literal events through self calls; unresolved inheritance, aliases or raw input keep the full hook."""
    if helper_tree is None:
        return None
    helpers = {n.name: n for cls in helper_tree.body if isinstance(cls, ast.ClassDef) and cls.name == "HarnessCase"
               for n in cls.body if isinstance(n, ast.FunctionDef)}
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    local = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    execution_modules = {"subprocess", "runpy", "importlib", "os", "pickle", "marshal", "ctypes", "code", "codeop",
                         "builtins", "types", "operator"}
    bindings = []
    for source in (tree, helper_tree):
        imported, trusted, unknown, foreign = set(), set(), set(), set()
        for node in ast.walk(source):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    imported.add(name)
                    module = (node.module or "") if isinstance(node, ast.ImportFrom) else alias.name
                    if getattr(node, "level", 0) or module.split(".")[0] not in sys.stdlib_module_names | {"maeng"}:
                        foreign.add(name)
                    if not getattr(node, "level", 0) and module.split(".")[0] in (sys.stdlib_module_names - execution_modules) | {"maeng"}:
                        trusted.add(name)
                    else:
                        unknown.add(name)
        if source is helper_tree and foreign:
            return None
        bindings.append((imported, trusted - unknown))
    fixture_imports = [(n, a) for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
                       for a in n.names if (a.asname or a.name.split(".")[0]) == "HarnessCase"]
    fixture_import = bool(fixture_imports) and all(isinstance(n, ast.ImportFrom) and n.level == 1 and
                         n.module == "helpers" and a.name == "HarnessCase" and a.asname is None
                         for n, a in fixture_imports)
    if bindings[0][0] - bindings[0][1] - ({"HarnessCase"} if fixture_import else set()):
        return None  # an external function can also be passed to a callback-taking builtin
    trusted = ({"self", "HarnessCase"} | local | vars(builtins).keys() | bindings[0][1]) - (bindings[0][0] - bindings[0][1])
    for node in ast.walk(tree):
        if isinstance(node, ast.arg) and node.arg != "self":
            return None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.decorator_list:
            return None
        if isinstance(node, ast.Call):
            root = node.func
            while isinstance(root, (ast.Attribute, ast.Call)):
                root = root.value if isinstance(root, ast.Attribute) else root.func
            if not (isinstance(root, ast.Name) and root.id in trusted or isinstance(root, ast.Constant)):
                return None  # an external driver or unknown receiver can dispatch outside this tree
        if isinstance(node, ast.ImportFrom) and any(a.name in ("HOOK", "call_hook", "call_cli", "*") for a in node.names):
            return None
        if isinstance(node, ast.Call) and any(isinstance(a, ast.Name) and a.id == "self" for a in node.args):
            return None
        if isinstance(node, ast.ClassDef) and node.keywords:
            return None
        if isinstance(node, ast.ClassDef) and any(not (isinstance(b, ast.Name) and b.id in local | {"HarnessCase"} or
                isinstance(b, ast.Attribute) and isinstance(b.value, ast.Name) and
                b.value.id == "unittest" and b.attr == "TestCase") for b in node.bases):
            return None
    todo = [tree, *(helpers[n] for n in ("setUp", "tearDown", "setUpClass", "tearDownClass") if n in helpers)]
    calls = {id(n.func): n for root in todo for n in ast.walk(root) if isinstance(n, ast.Call)}
    seen, found = set(), set()
    while todo:
        node = todo.pop()
        if isinstance(node, ast.FunctionDef) and node.decorator_list:
            return None
        for ref in ast.walk(node):
            if node is not tree and isinstance(ref, ast.Call):
                root = ref.func
                while isinstance(root, (ast.Attribute, ast.Call)):
                    root = root.value if isinstance(root, ast.Attribute) else root.func
                if isinstance(root, ast.Name) and root.id in bindings[1][0] - bindings[1][1]:
                    return None
                # These current fixture functions have inspected targets; test-level aliases remain unknown.
                known = {"git": {"run"}, "cli": {"run", "call_cli"}, "make_repo": {"_template_root"},
                         "run_check": {"between"}}.get(node.name, set())
                if isinstance(ref.func, ast.Name) and ref.func.id not in vars(builtins).keys() | bindings[1][1] | known:
                    return None
            if (isinstance(ref, ast.Call) and isinstance(ref.func, ast.Attribute) and node is tree and
                    isinstance(ref.func.value, ast.Name) and ref.func.value.id == "self" and ref.func.attr in helpers):
                if any(isinstance(a, ast.Starred) for a in ref.args) or any(
                        k.arg is None or k.arg == "hook_event_name" for k in ref.keywords):
                    return None
            if isinstance(ref, (ast.Assign, ast.NamedExpr)) and isinstance(ref.value, ast.Name) and ref.value.id == "self":
                return None
            if isinstance(ref, ast.Name) and ref.id in ("HOOK", "call_hook", "call_cli", "getattr", "globals", "locals",
                                                       "eval", "exec", "compile", "__import__"):
                if not (ref.id == "call_cli" and isinstance(node, ast.FunctionDef) and node.name == "cli"):
                    return None
            if not isinstance(ref, ast.Attribute):
                continue
            if ref.attr in ("HOOK", "call_hook", "call_cli"):
                return None
            if not (isinstance(ref.value, ast.Name) and ref.value.id == "self"):
                if ref.attr in ("hook", "pre", "bash_pre", "run_check", "verify_tree", "run_hook_text"):
                    return None
                continue
            name = ref.attr
            if name == "run_hook_text" or name in helpers and id(ref) not in calls:
                return None
            if id(ref) not in calls:
                continue
            if name in helpers and name in local:
                return None  # an override can alter the wrapper's dispatch
            if name == "cli":
                call = calls[id(ref)]
                command = call.args[0].value if call.args and isinstance(call.args[0], ast.Constant) else None
                if command not in {b.name for b in (PLUGIN / "bin").iterdir() if b.is_file()} or command not in text:
                    return None
            if name == "run_check":
                call = calls[id(ref)]
                callbacks = [k.value for k in call.keywords if k.arg == "between"] + call.args[3:4]
                if any(not isinstance(v, ast.Constant) or v.value is not None for v in callbacks):
                    return None  # the between callback can drive any event
            if name == "hook":
                call = calls[id(ref)]
                event = call.args[0].value if call.args and isinstance(call.args[0], ast.Constant) else None
                if event not in events:
                    return None
                found.add(event)
            elif name in helpers:
                if name not in seen:
                    seen.add(name)
                    helper = helpers[name]
                    calls.update({id(n.func): n for n in ast.walk(helper) if isinstance(n, ast.Call)})
                    todo.append(helper)
            elif name not in local and not name.startswith("assert") and name not in ("addCleanup", "subTest", "skipTest"):
                return None
    return found


def static_graph():
    """{test file: set of source files it can reach}."""
    srcs = _source_files()
    edges = {k: _imports(PLUGIN / v) for k, v in srcs.items()}
    edges["hook"] |= {"maeng.handlers", "maeng.state"}
    event_imports = _event_imports(PLUGIN / srcs["maeng.handlers"])
    if not event_imports:
        edges["maeng.handlers"] |= {n for n in srcs if n.startswith("maeng")}
    for event, deps in event_imports.items():
        key, handler = "hook:" + event, "handler:" + event
        srcs[key], srcs[handler] = srcs["hook"], srcs["maeng.handlers"]
        edges[key] = (edges["hook"] - {"maeng.handlers"}) | {handler}
        edges[handler] = edges["maeng.handlers"] if deps is None else deps

    def closure(start):
        seen, todo = set(), list(start)
        while todo:
            n = todo.pop()
            if n in seen or n not in srcs:
                continue
            seen.add(n)
            todo += edges.get(n, ())
        return {srcs[n] for n in seen}

    helpers_text = (TESTS / "helpers.py").read_text()
    try:
        helper_tree = ast.parse(helpers_text)
    except SyntaxError:
        helper_tree = None
    uses_hook = re.compile(r"\bself\.(hook|pre|bash_pre|start|run_check|verify_tree|run_hook_text)\(|\bHOOK\b")
    graph = {}
    for t in sorted(TESTS.glob("test_*.py")):
        text = t.read_text()
        start = _imports(t)
        if uses_hook.search(text) or "HarnessCase" in text or rel(t) == BOUNDARY:
            events = None if rel(t) == BOUNDARY else _test_events(text, helper_tree, event_imports)
            start |= {"hook"} if events is None else {"hook:" + e for e in events}
            start.add("maeng.state")
        start |= {f"bin:{b.name}" for b in (PLUGIN / "bin").iterdir() if b.name in text}
        reach = closure(start)
        for d in ("schemas", "config"):
            if f"{d}/" in text or (d == "schemas" and "verdict.schema" in text):
                reach |= {rel(p) for p in (PLUGIN / d).glob("*")}
        if "lib/maeng/schema.py" in reach:
            reach.add("schemas/verdict.schema.json")
        if "lib/maeng/gates.py" in reach:
            reach.add("config/notion-databases.json")
        graph[rel(t)] = reach
    return graph


# ---- coverage layer ---------------------------------------------------------

def _functions(source):
    """[(start, end, qualname)] for every def/class body, innermost last."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    out = []

    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = f"{prefix}{child.name}"
                start = min([child.lineno] + [d.lineno for d in child.decorator_list])
                if not isinstance(child, ast.ClassDef):
                    out.append((start, child.end_lineno, name))
                visit(child, name + ".")
    visit(tree, "")
    return out


def _scope(funcs, line):
    """Innermost function holding `line`, or None (module level)."""
    best = None
    for s, e, name in funcs:
        if s <= line <= e and (best is None or s >= best[0]):
            best = (s, e, name)
    return best[2] if best else None


def _nodeid(context):
    """coverage test_function context 'tests.test_x.Class.test_y' -> 'tests/test_x.py::Class::test_y'.
    A class built inside a function (`tests.test_x._cases.<locals>.Class.test_y`) is addressed by the module-level
    name it is bound to: the maker and `<locals>` are dropped (pytest exit 5 on three such ids was the rc-5 defect)."""
    parts = [p for p in context.split(".") if p]
    if "<locals>" in parts:
        i = parts.index("<locals>")
        parts = parts[:i - 1] + parts[i + 1:]
    for i in range(len(parts), 0, -1):
        f = PLUGIN / Path(*parts[:i]).with_suffix(".py")
        if f.is_file() and f.name.startswith("test_"):
            return "::".join([rel(f), *parts[i:]])
    return None


def build():
    try:
        import coverage  # noqa: F401
    except ImportError:
        raise SystemExit("impact build needs coverage (pip install -r requirements-dev.txt)")
    base = sh("git", "rev-parse", "HEAD").strip()
    work = Path(tempfile.mkdtemp(prefix="maeng-impact-"))
    rc = work / "rc"
    rc.write_text("[run]\nparallel = true\ndynamic_context = test_function\npatch = subprocess\n"
                  f"data_file = {work / '.coverage'}\nsource =\n    {PLUGIN / 'lib'}\n    {PLUGIN / 'bin'}\n"
                  f"    {PLUGIN / 'hooks'}\n")
    args = [sys.executable, "-m", "coverage", "run", f"--rcfile={rc}", "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "tests"]
    if _have_xdist():
        args += ["-n", "auto"]
    p = subprocess.run(args, cwd=PLUGIN)
    if p.returncode != 0:
        raise SystemExit("impact build: the suite failed; the map is only built from a passing run")
    sh(sys.executable, "-m", "coverage", "combine", f"--rcfile={rc}", "-q")
    import coverage
    data = coverage.CoverageData(basename=str(work / ".coverage"))
    data.read()
    files = {}
    for measured in data.measured_files():
        try:
            key = rel(measured)
        except ValueError:
            continue
        funcs = _functions(Path(measured).read_text())
        by_scope = {}
        for line, ctxs in (data.contexts_by_lineno(measured) or {}).items():
            tests = {n for n in map(_nodeid, ctxs) if n}
            if tests:
                by_scope.setdefault(_scope(funcs, line) or "<module>", set()).update(tests)
        files[key] = {k: sorted(v) for k, v in by_scope.items()}
    MAP.parent.mkdir(exist_ok=True)
    MAP.write_text(json.dumps({"base": base, "files": files}, indent=0, sort_keys=True) + "\n")
    shutil.rmtree(work, ignore_errors=True)
    n = len({t for f in files.values() for ts in f.values() for t in ts})
    print(f"impact map: {len(files)} source files, {n} tests, base {base[:12]} -> {rel(MAP)}")


# ---- selection --------------------------------------------------------------

def changed(base):
    """{plugin-relative path: set of old-side line numbers touched (None = whole file / unknown)}."""
    top = repo_root()
    prefix = PLUGIN.relative_to(top).as_posix() + "/"
    out = {}
    names = sh("git", "diff", "--name-only", "--no-renames", base, "--", ".", cwd=PLUGIN).split()
    names += sh("git", "ls-files", "--others", "--exclude-standard", "--", ".", cwd=PLUGIN).split()
    for n in names:
        path = n[len(prefix):] if n.startswith(prefix) else n
        out[path] = None
    for path in list(out):
        if not path.endswith(".py") and not path.startswith("bin/"):
            continue
        diff = sh("git", "diff", "-U0", "--no-renames", base, "--", path, cwd=PLUGIN, check=False)
        lines = set()
        for m in re.finditer(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@", diff, re.M):
            start, count = int(m.group(1)), int(m.group(2) or 1)
            lines |= set(range(start, start + count)) if count else {start, start + 1}  # pure insert: neighbours
        out[path] = lines or None
    return out


def load_map():
    """-> (map dict or None, note). A missing or unreadable map is a note, never a crash."""
    if not MAP.exists():
        return None, "no coverage map"
    try:
        cov = json.loads(MAP.read_text())
        if not isinstance(cov.get("files"), dict) or not cov.get("base"):
            raise ValueError("missing base/files")
        if subprocess.run(["git", "merge-base", "--is-ancestor", cov["base"], "HEAD"], cwd=PLUGIN,
                          capture_output=True).returncode != 0:
            return None, f"coverage map base {cov['base'][:12]} is not an ancestor of HEAD"
        return cov, None
    except (ValueError, OSError) as exc:
        return None, f"coverage map unreadable ({exc})"


def _have_coverage():
    try:
        import coverage  # noqa: F401
        return True
    except ImportError:
        return False


def ensure_map():
    """Build or refresh the map when coverage is installed and the map is missing or built off-history -> note."""
    cov, note = load_map()
    if cov is not None:
        return None
    if not _have_coverage():
        return f"{note}; coverage not installed (pip install -r requirements-dev.txt)"
    try:
        build()
    except SystemExit as exc:
        raise SystemExit(f"{note}; map not rebuilt ({exc})") from exc
    return f"{note}; map rebuilt"


def select(base=None, changes=None):
    """-> (sorted node ids or [ALL], reasons). `changes` ({path: old-side lines}) replaces the git diff."""
    cov, note = load_map()
    if cov is None:
        return [ALL], [note]
    base = base or (cov or {}).get("base") or "HEAD"
    graph = static_graph()
    picked, why = set(), [note] if note else []
    for path, lines in sorted((changes if changes is not None else changed(base)).items()):
        if path in SHARED or re.match(r"requirements.*\.txt$|hooks/hooks\.json$|\.claude-plugin/", path):
            return [ALL], [f"{path}: shared test/plugin input -> all"]
        if path.startswith("tests/test_") and path.endswith(".py"):
            picked.add(path); why.append(f"{path}: test file itself")
            continue
        if path.endswith(".md") or path.startswith("skills/"):
            picked |= set(DOC_TESTS); why.append(f"{path}: doc/skill -> doc tests")
            continue
        if path.startswith(("lib/", "bin/", "hooks/")):
            if path.startswith(("bin/", "hooks/")):
                picked.add(BOUNDARY)
            entry = (cov or {}).get("files", {}).get(path)
            if entry is not None and lines is not None:
                funcs = _functions(_old_text(base, path))
                scopes = {_scope(funcs, ln) or "<module>" for ln in lines}
                tests = {t for s in scopes for t in entry.get(s, [])}
                # module-level code (constants, imports) runs once per worker, so the map under-counts its readers;
                # an uncovered function (or one only child processes ran) has no tests in the map at all
                if "<module>" not in scopes and tests:
                    picked |= tests; why.append(f"{path}: {', '.join(sorted(scopes))} -> {len(tests)} tests")
                    continue
            users = {t for t, reach in graph.items() if path in reach}
            if not users:
                return [ALL], [f"{path}: no static user -> all"]
            picked |= users; why.append(f"{path}: static graph -> {len(users)} test files")
            continue
        if path.startswith(("schemas/", "config/")):
            users = {t for t, reach in graph.items() if path in reach}
            picked |= users or {ALL}; why.append(f"{path}: static graph -> {len(users) or 'all'}")
            continue
        if path.startswith((".impact/",)):
            continue
        return [ALL], [f"{path}: unknown input -> all"]
    if ALL in picked:
        return [ALL], why
    twins = boundary_twins(picked)
    if twins:
        why.append(f"boundary twins of selected tests: {len(twins)}")
    picked |= twins
    files = {p for p in picked if "::" not in p}  # a whole file already runs its node ids: pytest would run them twice
    return sorted(p for p in picked if "::" not in p or p.split("::")[0] not in files), why


def boundary_twins(picked):
    """Node ids in test_boundary.py whose in-process scenario is among `picked`."""
    if BOUNDARY in picked:
        return set()
    sys.path.insert(0, str(PLUGIN))
    try:
        from tests import test_boundary
    finally:
        sys.path.pop(0)
    out = set()
    for name, cls in vars(test_boundary).items():
        if not (isinstance(cls, type) and getattr(cls, "PROCESS", False)):
            continue
        base = cls.__mro__[1]
        base_file = rel(sys.modules[base.__module__].__file__)
        for attr in dir(cls):
            if attr.startswith("test") and callable(getattr(cls, attr)) and \
                    f"{base_file}::{base.__name__}::{attr}" in picked:
                out.add(f"{BOUNDARY}::{name}::{attr}")
    return out


def _old_text(base, path):
    top = repo_root()
    full = (PLUGIN / path).resolve().relative_to(top).as_posix()
    p = subprocess.run(["git", "show", f"{base}:{full}"], cwd=top, capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else ""


def _have_xdist():
    try:
        import xdist  # noqa: F401
        return True
    except ImportError:
        return False


NO_TESTS_COLLECTED, USAGE_ERROR = 5, 4  # pytest exit codes that mean "the selection itself was unusable"


def pytest_args(targets, extra):
    args = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *extra, *targets]
    if _have_xdist() and (targets == ["tests"] or len(targets) > 40) and "-n" not in extra:
        args[4:4] = ["-n", "auto"]
    return args


def run_pytest(args):
    """Stream pytest's output and return (rc, executed-test count or None)."""
    p = subprocess.Popen(args, cwd=PLUGIN, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    tail = []
    for line in p.stdout:
        sys.stdout.write(line)
        tail.append(line)
        del tail[:-60]
    return p.wait(), test_count("".join(tail))


def run_selected(ids, extra, runner=None, fallback=None):
    """Run the selected tests, or the full suite with a stated reason -> (rc, summary dict).
    A failure of the selected tests (rc 1) is final; only an unusable selection falls back."""
    runner = runner or run_pytest  # looked up at call time, so a test can replace the module's runner
    count, rc = None, None
    if ids == [ALL]:
        mode, targets = "all", ["tests"]
    elif not ids:
        fallback, targets = "empty selection", ["tests"]
    else:
        missing = sorted({i.split("::")[0] for i in ids if not (PLUGIN / i.split("::")[0]).exists()})
        if missing:
            fallback, targets = "selected files missing: " + ", ".join(missing), ["tests"]
        else:
            mode, targets = "narrow", ids
    if not fallback:
        rc, count = runner(pytest_args(targets, extra))
        if rc in (NO_TESTS_COLLECTED, USAGE_ERROR) and targets != ["tests"]:
            fallback = f"pytest exit {rc} on the selection (nothing collected or a bad node id)"
    if fallback:
        print("# fallback to the full suite: " + fallback, file=sys.stderr)
        rc, count = runner(pytest_args(["tests"], extra))
        mode = "fallback"
    return rc, {"mode": mode, "selected": None if ids == [ALL] else len(ids), "fallback": fallback,
                "tests_run": count if isinstance(count, int) else "unavailable", "rc": rc}


def main(argv):
    if not argv or argv[0] not in ("build", "select", "run"):
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    extra = []
    if "--" in rest:
        i = rest.index("--")
        rest, extra = rest[:i], rest[i + 1:]
    as_json = "--json" in rest
    rest = [r for r in rest if r != "--json"]
    if cmd == "build":
        build()
        return 0
    try:
        note = ensure_map()
    except SystemExit as exc:
        error = f"coverage map build failed: {exc}"
        print("# " + error, file=sys.stderr)
        if cmd == "run":
            print("impact-summary: " + json.dumps({"mode": "fallback", "selected": None, "fallback": error,
                                                   "tests_run": "unavailable", "rc": 1}), file=sys.stderr)
        elif as_json:
            print(json.dumps({"ids": [ALL], "all": True, "reasons": [error], "error": error, "map_note": error}))
        return 1
    if note:
        print("# " + note, file=sys.stderr)
    try:
        ids, why = select(rest[0] if rest else None)
        error = None
    except (SystemExit, ValueError, OSError, KeyError) as exc:
        ids, why, error = [], [], f"selector error: {exc}"
    for w in why:
        print("# " + w, file=sys.stderr)
    if cmd == "select":
        if as_json:
            print(json.dumps({"ids": ids, "all": ids == [ALL], "reasons": why, "error": error, "map_note": note}))
            return 1 if error else 0
        if error:
            print("# " + error, file=sys.stderr)
            return 1
        print("\n".join(ids))
        return 0
    if error:
        print("# " + error, file=sys.stderr)
        rc, summary = run_selected([], extra)
        summary["fallback"] = error
    else:
        fallback = "; ".join(why) if ids == [ALL] and load_map()[0] is None else None
        rc, summary = run_selected(ids, extra, fallback=fallback)
    print("impact-summary: " + json.dumps(summary), file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
