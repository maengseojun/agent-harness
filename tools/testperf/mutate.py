#!/usr/bin/env python3
"""Mutation comparison of two test suites over the same mutants (MAE-232 D-7), using mutmut 2.x mutation operators.

  mutate.py DB --lib LIBDIR --suite NAME=PLUGINDIR [--suite ...] --file lib/maeng/gates.py [--file ...]
            [--sample N] [--seed S] [--impact GITPLUGINDIR] [--jobs J] [--timeout-factor F]

Each PLUGINDIR is a full copy of plugins/maeng-harness (its own tests/); LIBDIR's lib/ is copied over every suite
copy first, so all suites run against byte-identical source. For every sampled mutant the mutated file is written
into each suite copy (in place, so hook/CLI child processes see it too), the suite runs with `pytest -x -n J`, and
the file is restored. Results go to table `mutants` (killed = the suite failed or timed out).

--impact GITPLUGINDIR also runs, in the suite named `new`, only the tests that GITPLUGINDIR/tests/impact.py (a git
checkout whose impact map was built at the same source) selects for the mutated line (suite name `new-impact`).
"""
import argparse
import random
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import mutmut

SCHEMA = """CREATE TABLE IF NOT EXISTS mutants(file TEXT, line INT, idx INT, source_line TEXT, mutated_line TEXT,
suite TEXT, killed INT, rc INT, duration_s REAL, n_selected INT, PRIMARY KEY(file, line, idx, suite));"""


def mutants_of(path):
    ctx = mutmut.Context(filename=str(path))
    return mutmut.list_mutations(ctx)


def mutated_source(path, mid):
    ctx = mutmut.Context(filename=str(path), mutation_id=mid)
    src, n = mutmut.mutate(ctx)
    assert n == 1, (path, mid)
    return src


def run_suite(plugin, jobs, timeout, targets=("tests",)):
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "-n", str(jobs),
                            *targets], cwd=plugin, capture_output=True, text=True, timeout=timeout)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        rc = -9
    return rc, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("db")
    ap.add_argument("--lib", required=True)
    ap.add_argument("--suite", action="append", required=True)
    ap.add_argument("--file", action="append", required=True)
    ap.add_argument("--sample", type=int, default=50)
    ap.add_argument("--seed", default="mae232")
    ap.add_argument("--impact")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--timeout-factor", type=float, default=3.0)
    a = ap.parse_args()
    suites = dict(s.split("=", 1) for s in a.suite)
    for plugin in suites.values():
        shutil.rmtree(Path(plugin) / "lib", ignore_errors=True)
        shutil.copytree(Path(a.lib) / "lib", Path(plugin) / "lib", ignore=shutil.ignore_patterns("__pycache__"))
    con = sqlite3.connect(a.db)
    con.executescript(SCHEMA)
    # unmutated baseline: every suite must pass, and its time sets the timeout
    budget = {}
    for name, plugin in suites.items():
        rc, dur = run_suite(plugin, a.jobs, None)
        if rc != 0:
            raise SystemExit(f"suite {name} fails without mutation (rc {rc}); fix that first")
        budget[name] = max(60.0, dur * a.timeout_factor)
        print(f"baseline {name}: {dur:.1f}s", flush=True)
    rng = random.Random(a.seed)
    if a.impact:
        sys.path.insert(0, str(Path(a.impact) / "tests"))
        import impact  # noqa: E402  (the new suite's selector)
    for rel in a.file:
        src_path = Path(a.lib) / rel
        mids = mutants_of(src_path)
        pick = sorted(rng.sample(range(len(mids)), min(a.sample, len(mids))))
        print(f"{rel}: {len(mids)} mutants, sampling {len(pick)}", flush=True)
        for k in pick:
            mid = mids[k]
            line_no = mid.line_number + 1
            done = {r[0] for r in con.execute("SELECT suite FROM mutants WHERE file=? AND line=? AND idx=?",
                                               (rel, line_no, mid.index))}
            text = mutated_source(src_path, mid)
            mline = text.split("\n")[mid.line_number] if mid.line_number < len(text.split("\n")) else ""
            runs = [(n, p, ("tests",)) for n, p in suites.items()]
            if a.impact:
                ids, _ = impact.select(changes={rel: {line_no}})
                runs.append(("new-impact", suites["new"], ("tests",) if ids == [impact.ALL] else tuple(ids)))
            for name, plugin, targets in runs:
                if name in done:
                    continue
                target = Path(plugin) / rel
                original = target.read_text()
                target.write_text(text)
                try:
                    if not targets:
                        rc, dur = 0, 0.0  # nothing selected: the mutant survives selection
                    else:
                        rc, dur = run_suite(plugin, a.jobs, budget.get(name, budget.get("new")), targets)
                finally:
                    target.write_text(original)
                con.execute("INSERT OR REPLACE INTO mutants VALUES(?,?,?,?,?,?,?,?,?,?)",
                            (rel, line_no, mid.index, mid.line.strip(), mline.strip(), name, int(rc != 0), rc, dur,
                             len(targets) if targets != ("tests",) else -1))
                con.commit()
                print(f"  {rel}:{line_no}#{mid.index} {name}: {'killed' if rc else 'SURVIVED'} ({dur:.1f}s)",
                      flush=True)


if __name__ == "__main__":
    main()
