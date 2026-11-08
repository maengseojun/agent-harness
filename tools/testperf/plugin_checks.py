#!/usr/bin/env python3
"""Runs every plugin test suite listed in a checked inventory (lanes.json) and prints one aggregate (MAE-323 S7).

  plugin_checks.py --lane gate|periodic [--isolated] [--require-complete] [--json OUT] [--lanes FILE] [--root DIR]
                   [--print-pip] [--timeout SEC]

Inventory parity: every directory under plugins/ and harness/ that holds test_*.py must be covered by some suite of
some lane, and every `covers` entry must exist. A suite whose declared deps are missing is `unavailable` when
required and `skipped` (with its declared reason) when optional. The aggregate is ok only when parity holds, every
required suite is ok and every optional one is ok or skipped; --require-complete also forbids skipped gate suites.
Exit code 1 when the aggregate is not ok.
"""
import argparse
import json
import os
import re
import shutil
import site
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "plugins" / "maeng-harness" / "lib"))
from maeng.evidence import ran_zero_tests  # noqa: E402

SKIP_DIRS = {"archive", "node_modules", ".claude", "__pycache__"}
PYTEST_LINE = re.compile(r"^\W*((?:\d+ [a-z]+(?:, )?)+) in [\d.]+s", re.M)
PYTEST_COUNTED = {"passed", "failed", "error", "errors", "xfailed", "xpassed"}


def discover(root):
    found = set()
    for top in ("plugins", "harness"):
        for dirpath, dirs, files in os.walk(Path(root) / top):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            if any(f.startswith("test_") and f.endswith(".py") for f in files):
                found.add(Path(dirpath).relative_to(root).as_posix())
    return found


def parity(root, lanes):
    covered = {c for suites in lanes.values() for s in suites for c in s["covers"]}
    found = discover(root)
    nonexistent = sorted(c for c in covered if not (Path(root) / c).is_dir())
    no_tests = sorted(c for c in covered - found if c not in nonexistent)
    missing = sorted(found - covered)
    return {"ok": not (missing or nonexistent or no_tests), "missing_lane": missing, "nonexistent": nonexistent,
            "no_tests": no_tests}


def tests_run(output):
    m = None
    for m in PYTEST_LINE.finditer(output):
        pass
    if m:
        return sum(int(n) for n, w in re.findall(r"(\d+) ([a-z]+)", m.group(1)) if w in PYTEST_COUNTED)
    if re.search(r"\bno tests ran\b", output):
        return 0
    ran = re.findall(r"^Ran (\d+) tests?\b", output, re.M)
    if ran:
        skipped = re.findall(r"^(?:OK|FAILED) \(.*?skipped=(\d+)", output, re.M)
        return int(ran[-1]) - (int(skipped[-1]) if skipped else 0)
    return None


def tests_skipped(output):
    m = None
    for m in PYTEST_LINE.finditer(output):
        pass
    if m:
        return sum(int(n) for n, w in re.findall(r"(\d+) ([a-z]+)", m.group(1)) if w == "skipped")
    skipped = re.findall(r"^(?:OK|FAILED) \(.*?skipped=(\d+)", output, re.M)
    return int(skipped[-1]) if skipped else (0 if tests_run(output) is not None else None)


def isolated_env(tmp):
    t = str(tmp)
    # PYTHONUSERBASE keeps the parent's user-site packages importable (read-only) while HOME is the temp dir
    return {"PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "HOME": t, "TMPDIR": t,
            "PYTHONUSERBASE": os.environ.get("PYTHONUSERBASE") or site.USER_BASE,
            "XDG_CONFIG_HOME": t + "/config", "XDG_CACHE_HOME": t + "/cache", "XDG_DATA_HOME": t + "/data",
            "PYTHONDONTWRITEBYTECODE": "1", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": t + "/gitconfig",
            "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}


def run_suite(suite, root, isolated, timeout):
    res = {"id": suite["id"], "status": "missing", "rc": None, "duration_s": 0.0, "tests_run": None,
           "tests_skipped": None, "output_tail": ""}
    tmp = tempfile.mkdtemp(prefix="plugin-checks-")
    env = isolated_env(os.path.realpath(tmp)) if isolated else dict(os.environ)
    start = time.monotonic()
    try:
        cwd = Path(root) / suite["cwd"]
        if suite.get("manual"):  # a periodic job someone prepares by hand (copies, a database): never launched here
            res["status"], res["output_tail"] = "skipped", "manual: " + suite["manual"]
            return res
        absent = [d for d in suite["deps"]
                  if subprocess.run(["python3", "-c", "import " + d], cwd=cwd, env=env,
                                    capture_output=True).returncode != 0] if cwd.is_dir() else []
        if absent:
            res["status"] = "unavailable" if suite["required"] else "skipped"
            res["output_tail"] = ("missing modules: " + ", ".join(absent) +
                                  ("" if suite["required"] else "; " + suite.get("reason", "")))
            return res
        try:
            p = subprocess.run(suite["command"], cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout,
                               errors="replace")
            out, res["rc"] = p.stdout + p.stderr, p.returncode
        except (FileNotFoundError, NotADirectoryError) as e:
            res["output_tail"] = str(e)
            return res
        except subprocess.TimeoutExpired as e:
            res["status"] = "timeout"
            out = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            res["output_tail"] = "\n".join(out.splitlines()[-40:])
            return res
        res["tests_run"] = tests_run(out)
        res["tests_skipped"] = tests_skipped(out)
        res["output_tail"] = "\n".join(out.splitlines()[-40:])
        if res["rc"] != 0:
            res["status"] = "failed"
        elif (res["tests_skipped"] or 0) > suite.get("skips_allowed", 0):
            res["status"] = "skipped-tests"
        elif res["tests_run"] == 0 or ran_zero_tests(out):
            res["status"] = "empty"
        else:
            res["status"] = "ok"
        return res
    finally:
        res["duration_s"] = round(time.monotonic() - start, 2)
        shutil.rmtree(tmp, ignore_errors=True)


def suite_passes(suite, res):
    return res["status"] == "ok" or (res["status"] == "skipped" and not suite["required"])


def table(results):
    rows = [("id", "status", "rc", "tests", "skipped", "secs")]
    rows += [(r["id"], r["status"], str(r["rc"]), str(r["tests_run"]), str(r["tests_skipped"]),
              str(r["duration_s"])) for r in results]
    w = [max(len(r[i]) for r in rows) for i in range(6)]
    return "\n".join("  ".join(c.ljust(w[i]) for i, c in enumerate(r)) for r in rows)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", required=True, choices=["gate", "periodic"])
    ap.add_argument("--isolated", action="store_true")
    ap.add_argument("--require-complete", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--root", default=str(REPO))
    ap.add_argument("--lanes")
    ap.add_argument("--print-pip", action="store_true")
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args(argv)
    root = Path(a.root)
    lanes = json.loads(Path(a.lanes or root / "plugins/maeng-harness/tests/lanes.json").read_text())["lanes"]
    for lane in lanes.values():
        for s in lane:
            if "skips_allowed" in s:
                if type(s["skips_allowed"]) is not int or s["skips_allowed"] < 0:
                    ap.error(f"{s['id']}: skips_allowed must be a nonnegative integer")
                if not isinstance(s.get("skips_reason"), str) or not s["skips_reason"].strip():
                    ap.error(f"{s['id']}: skips_reason is required with skips_allowed")
    suites = lanes[a.lane]
    if a.print_pip:
        print("\n".join(sorted({p for s in suites for p in s["pip"]})))
        return 0
    par = parity(root, lanes)
    results = [run_suite(s, root, a.isolated, a.timeout) for s in suites]
    ok = par["ok"] and all(suite_passes(s, r) for s, r in zip(suites, results))
    if a.require_complete and a.lane == "gate" and any(r["status"] == "skipped" for r in results):
        ok = False
    print(table(results))
    print("parity: " + ("ok" if par["ok"] else "FAILED " + json.dumps({k: v for k, v in par.items() if k != "ok" and v})))
    print("aggregate: " + ("ok" if ok else "NOT ok"))
    data = {"lane": a.lane, "isolated": a.isolated, "require_complete": a.require_complete, "aggregate_ok": ok,
            "parity": par, "suites": results, "generated_at": datetime.now(timezone.utc).isoformat()}
    if a.json:
        Path(a.json).write_text(json.dumps(data, indent=2) + "\n")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        md = ["### Plugin suites (%s lane): %s" % (a.lane, "ok" if ok else "NOT ok"), "",
              "| suite | status | rc | tests | skipped | secs |", "|---|---|---|---|---|---|"]
        md += ["| %s | %s | %s | %s | %s | %s |" % (r["id"], r["status"], r["rc"], r["tests_run"],
                                                   r["tests_skipped"], r["duration_s"])
               for r in results]
        md.append("\nparity: " + ("ok" if par["ok"] else "FAILED " + json.dumps(par)))
        with open(summary, "a") as f:
            f.write("\n".join(md) + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
