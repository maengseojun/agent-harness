#!/usr/bin/env python3
"""Load test-suite timing runs into SQLite (MAE-232).

  perfdb.py load DB LABEL RUNDIR    RUNDIR holds wall.txt (one line per repeat: label i t0 t1 rc load1 load5 load15)
                                    and junit-<i>.xml; rows go to tables `runs` and `cases`
  perfdb.py stats DB                median / p95 / spread of every label (wall seconds)

Percentiles use the nearest-rank method on the repeats of one label.
"""
import math
import sqlite3
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs(label TEXT, rep INT, t0 REAL, t1 REAL, wall_s REAL, rc INT, load1 REAL, load5 REAL,
                                load15 REAL, n_tests INT, n_fail INT, PRIMARY KEY(label, rep));
CREATE TABLE IF NOT EXISTS cases(label TEXT, rep INT, file TEXT, cls TEXT, name TEXT, time_s REAL, outcome TEXT,
                                 size TEXT);
"""


def load(db, label, rundir):
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    con.execute("DELETE FROM runs WHERE label=?", (label,))
    con.execute("DELETE FROM cases WHERE label=?", (label,))
    for line in Path(rundir, "wall.txt").read_text().splitlines():
        f = line.split()
        rep, t0, t1, rc = int(f[1]), float(f[2]), float(f[3]), int(f[4])
        loads = [float(x.rstrip(",")) for x in f[5:8]] + [None] * (3 - len(f[5:8]))
        junit = Path(rundir, f"junit-{rep}.xml")
        n = nf = 0
        if junit.exists():
            for case in ET.parse(junit).getroot().iter("testcase"):
                outcome = "failed" if case.find("failure") is not None or case.find("error") is not None else \
                    "skipped" if case.find("skipped") is not None else "passed"
                props = {p.get("name"): p.get("value") for p in case.iter("property")}
                n += 1
                nf += outcome == "failed"
                cls = case.get("classname", "")
                con.execute("INSERT INTO cases VALUES(?,?,?,?,?,?,?,?)",
                            (label, rep, case.get("file") or cls.rsplit(".", 1)[0], cls, case.get("name"),
                             float(case.get("time") or 0), outcome, props.get("size")))
        con.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?,?)", (label, rep, t0, t1, t1 - t0, rc, *loads, n, nf))
    con.commit()


def pct(xs, p):
    xs = sorted(xs)
    return xs[max(0, math.ceil(p / 100 * len(xs)) - 1)]


def stats(db):
    con = sqlite3.connect(db)
    print(f"{'label':28} {'n':>3} {'median':>8} {'p95':>8} {'min':>8} {'max':>8} {'tests':>6} {'fail':>5} {'load1':>6}")
    for (label,) in con.execute("SELECT DISTINCT label FROM runs ORDER BY min(t0) OVER (PARTITION BY label)"):
        rows = con.execute("SELECT wall_s, n_tests, n_fail, load1 FROM runs WHERE label=?", (label,)).fetchall()
        w = [r[0] for r in rows]
        print(f"{label:28} {len(w):3d} {pct(w, 50):8.2f} {pct(w, 95):8.2f} {min(w):8.2f} {max(w):8.2f} "
              f"{rows[0][1]:6d} {sum(r[2] for r in rows):5d} {sum(r[3] or 0 for r in rows) / len(rows):6.2f}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["load"]:
        load(*sys.argv[2:5])
    elif sys.argv[1:2] == ["stats"]:
        stats(sys.argv[2])
    else:
        print(__doc__)
        sys.exit(2)
