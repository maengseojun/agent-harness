#!/usr/bin/env python3
"""Wall time of impact-selected test runs (MAE-232 AC-2).

  impact_timing.py PLUGINDIR DB REPEATS FILE:FUNC [FILE:FUNC ...]

For each function, the selection tests/impact.py makes for a one-line change inside it is run REPEATS times
(the same command `impact.py run` uses: serial for <=40 tests, else -n auto). Rows go to table `impact_runs`.
"""
import sqlite3
import subprocess
import sys
import time
from pathlib import Path


def main(plugin, db, repeats, *targets):
    plugin = Path(plugin).resolve()
    sys.path.insert(0, str(plugin / "tests"))
    import impact
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE IF NOT EXISTS impact_runs(file TEXT, func TEXT, n_selected INT, rep INT, wall_s REAL, "
                "rc INT, workers TEXT)")
    for t in targets:
        f, func = t.split(":")
        start = [s for s, e, n in impact._functions((plugin / f).read_text()) if n == func][0]
        ids, _ = impact.select(changes={f: {start + 1}})
        targets_ = ["tests"] if ids == [impact.ALL] else ids
        par = len(targets_) > 40 or targets_ == ["tests"]
        cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *(["-n", "auto"] if par else []),
               *targets_]
        con.execute("DELETE FROM impact_runs WHERE file=? AND func=?", (f, func))
        for rep in range(1, int(repeats) + 1):
            t0 = time.time()
            rc = subprocess.run(cmd, cwd=plugin, capture_output=True).returncode
            con.execute("INSERT INTO impact_runs VALUES(?,?,?,?,?,?,?)",
                        (f, func, len(ids), rep, time.time() - t0, rc, "auto" if par else "1"))
            con.commit()
        print(f"{t}: {len(ids)} tests", flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
