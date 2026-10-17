#!/usr/bin/env python3
"""Deny-path coverage (MAE-232 AC-6): is every deny return of the gate code executed by at least one test?

  deny_coverage.py PLUGINDIR DB      run the suite under coverage (subprocesses included), then list each deny site

A deny site is a line that produces a denial: a call of `deny(...)`, `deny_out(...)`, `Decision(False, ...)`,
`fail_closed(...)` and `{"decision": "block"...}` in lib/maeng/*.py and hooks/maeng_hooks.py. Multi-line calls count
as covered when their first line ran. Results go to table `deny_sites` (file, line, func, covered, n_tests).
"""
import ast
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

SITE = re.compile(r"\b(deny|deny_out|fail_closed)\(|Decision\(\s*False\b|\"decision\":\s*\"block\"")


def sites(plugin):
    out = []
    for f in sorted([*Path(plugin, "lib/maeng").glob("*.py"), Path(plugin, "hooks/maeng_hooks.py")]):
        src = f.read_text()
        funcs = []
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funcs.append((node.lineno, node.end_lineno, node.name))
        for i, line in enumerate(src.splitlines(), 1):
            if SITE.search(line) and not line.lstrip().startswith("#") and not re.match(r"\s*def ", line):
                inner = [n for s, e, n in funcs if s <= i <= e]
                out.append((f, i, inner[-1] if inner else "<module>", line.strip()))
    return out


def main(plugin, db):
    plugin = Path(plugin).resolve()
    work = Path(tempfile.mkdtemp(prefix="maeng-denycov-"))
    rc = work / "rc"
    rc.write_text(f"[run]\nparallel = true\ndynamic_context = test_function\npatch = subprocess\n"
                  f"data_file = {work / '.coverage'}\nsource =\n    {plugin / 'lib'}\n    {plugin / 'hooks'}\n")
    subprocess.run([sys.executable, "-m", "coverage", "run", f"--rcfile={rc}", "-m", "pytest", "-q", "-n", "auto",
                    "-p", "no:cacheprovider", "tests"], cwd=plugin, check=False)
    subprocess.run([sys.executable, "-m", "coverage", "combine", f"--rcfile={rc}", "-q"], cwd=plugin, check=True)
    import coverage
    data = coverage.CoverageData(basename=str(work / ".coverage"))
    data.read()
    con = sqlite3.connect(db)
    con.executescript("DROP TABLE IF EXISTS deny_sites; CREATE TABLE deny_sites(file TEXT, line INT, func TEXT, "
                      "covered INT, n_tests INT, text TEXT);")
    for f, line, func, text in sites(plugin):
        ctx = (data.contexts_by_lineno(str(f)) or {}).get(line, [])
        tests = {c for c in ctx if c}
        con.execute("INSERT INTO deny_sites VALUES(?,?,?,?,?,?)",
                    (str(f.relative_to(plugin)), line, func, int(bool(tests) or line in (data.lines(str(f)) or [])),
                     len(tests), text[:160]))
    con.commit()
    total, cov = con.execute("SELECT count(*), sum(covered) FROM deny_sites").fetchone()
    print(f"deny sites: {total}, covered: {cov}")
    for row in con.execute("SELECT file, line, func, text FROM deny_sites WHERE covered=0 ORDER BY file, line"):
        print("  UNCOVERED", *row)
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main(*sys.argv[1:3])
