#!/usr/bin/env python3
"""MAE-323 AC-7: replay the impact selector over pinned recent code commits.

  impact_replay.py --manifest M --record [--commits 16] [--cache DIR] [--worktree DIR]   # pin and run, write M
  impact_replay.py --manifest M --require-cases 16 --max-median 100                     # judge a recorded run

`--record` pins the newest N commits that change plugins/maeng-harness code (lib, bin, hooks, tests, schemas,
config, policy, plugin manifest; docs excluded), then for each commit C with parent P: a throwaway worktree is put
at P, the coverage map is built there with the CURRENT tests/impact.py (cached per parent under --cache), the
worktree moves to C, and `impact.py run P` executes the selection the way a working check would. The selector's
own `impact-summary:` line is recorded as is: mode (narrow | all | fallback), selected count, fallback reason,
executed tests, exit code. Fallbacks are reported separately and never counted as a narrow selection.

The judgement reads only the manifest: every case must have completed (a summary line and exit 0 or 1; exit 1 is a
genuine test failure at that commit, which selection must not hide), no case may carry a selector error, and the
median of executed tests over all completed cases (full-suite counts for `all` and `fallback` cases, so a fallback
raises the median) must be at most --max-median. Stdlib only.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_REL = "plugins/maeng-harness"
IMPACT = ROOT / PLUGIN_REL / "tests/impact.py"
CODE = re.compile(r"^plugins/maeng-harness/(lib/|bin/|hooks/|tests/|schemas/|config/|policy/|requirements|\.claude-plugin/)")
SUMMARY = "impact-summary: "


def git(*args, cwd=ROOT, check=True):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and p.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {p.stderr.strip()}")
    return p.stdout


def code_commits(n):
    """The newest n commits whose diff against their first parent touches plugin code (merges skipped)."""
    out = []
    for line in git("log", "--no-merges", "--format=%H %P", "-n", "400", "--", PLUGIN_REL).splitlines():
        sha, *parents = line.split()
        if not parents:
            continue
        files = git("diff", "--name-only", "--no-renames", f"{parents[0]}..{sha}").split()
        code = sorted(f for f in files if CODE.match(f))
        if code:
            out.append({"sha": sha, "parent": parents[0], "subject": git("log", "-1", "--format=%s", sha).strip(),
                        "code_files": code})
        if len(out) == n:
            break
    return out


def worktree(path):
    path = Path(path).resolve()
    if not (path / ".git").exists():
        git("worktree", "add", "--detach", "-q", str(path), "HEAD")
    return path


def run_impact(plugin_dir, *args):
    env = {**os.environ, "MAENG_IMPACT_PLUGIN": str(plugin_dir)}
    t0 = time.monotonic()
    p = subprocess.run([sys.executable, str(IMPACT), *args], cwd=plugin_dir, env=env, capture_output=True, text=True)
    return p, round(time.monotonic() - t0, 1)


def record_case(case, wt, cache):
    plugin = wt / PLUGIN_REL
    res = {**case, "map": None, "select": None, "summary": None, "rc": None, "selector_error": None, "duration_s": None}
    git("checkout", "-q", "--detach", case["parent"], cwd=wt)
    git("clean", "-fdq", cwd=wt)                      # untracked only: the ignored .impact/ map survives
    cached = cache / f"{case['parent']}.json"
    mapfile = plugin / ".impact" / "map.json"
    mapfile.parent.mkdir(exist_ok=True)
    if cached.exists():
        shutil.copy(cached, mapfile)
        res["map"] = "cached"
    else:
        mapfile.unlink(missing_ok=True)
        p, secs = run_impact(plugin, "build")
        if p.returncode == 0 and mapfile.exists():
            shutil.copy(mapfile, cached)
            res["map"] = f"built in {secs}s"
        else:
            res["map"] = "unbuilt: " + (p.stderr.strip().splitlines() or ["?"])[-1][:300]
    git("checkout", "-q", "--detach", case["sha"], cwd=wt)
    p, _ = run_impact(plugin, "select", case["parent"], "--json")
    try:
        sel = json.loads(p.stdout.strip().splitlines()[-1])
        res["select"] = {"count": None if sel["all"] else len(sel["ids"]), "all": sel["all"],
                         "reasons": sel["reasons"], "error": sel["error"]}
        res["selector_error"] = sel["error"]
    except (ValueError, IndexError, KeyError):
        res["selector_error"] = "select --json produced no result: " + p.stderr[-300:]
    p, secs = run_impact(plugin, "run", case["parent"])
    res["rc"], res["duration_s"] = p.returncode, secs
    lines = [ln for ln in p.stderr.splitlines() if ln.startswith(SUMMARY)]
    if lines:
        res["summary"] = json.loads(lines[-1][len(SUMMARY):])
        if res["summary"]["fallback"] and res["summary"]["fallback"].startswith("selector error"):
            res["selector_error"] = res["summary"]["fallback"]
    else:
        res["selector_error"] = res["selector_error"] or "no impact-summary line: " + p.stderr[-300:]
    return res


def record(a):
    cache = Path(a.cache).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    wt = worktree(a.worktree)
    cases = code_commits(a.commits)
    done = []
    for i, c in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {c['sha'][:12]} {c['subject'][:70]}", file=sys.stderr, flush=True)
        r = record_case(c, wt, cache)
        s = r["summary"] or {}
        print(f"    map={r['map']} mode={s.get('mode')} selected={s.get('selected')} tests_run={s.get('tests_run')} "
              f"rc={r['rc']} fallback={s.get('fallback')} error={r['selector_error']}", file=sys.stderr, flush=True)
        done.append(r)
        write(a.manifest, cases=done, partial=i < len(cases))
    git("worktree", "remove", "--force", str(wt))


def write(path, cases, partial):
    m = {"recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "partial": partial,
         "impact_sha256": hashlib.sha256(IMPACT.read_bytes()).hexdigest(),
         "commits_selected_by": "newest commits whose diff against the first parent touches " + CODE.pattern,
         "cases": cases, "summary": judge(cases)}
    Path(path).write_text(json.dumps(m, indent=1) + "\n", encoding="utf-8")


def judge(cases):
    completed = [c for c in cases if c.get("summary") and c.get("rc") in (0, 1) and not c.get("selector_error")]
    counts = [c["summary"]["tests_run"] for c in completed if isinstance(c["summary"]["tests_run"], int)]
    narrow = [c["summary"]["tests_run"] for c in completed if c["summary"]["mode"] == "narrow"
              and isinstance(c["summary"]["tests_run"], int)]
    return {"cases": len(cases), "completed": len(completed),
            "selector_errors": [c["sha"][:12] + ": " + str(c["selector_error"]) for c in cases if c.get("selector_error")],
            "fallbacks": [{"sha": c["sha"][:12], "reason": c["summary"]["fallback"]} for c in completed
                          if c["summary"]["mode"] == "fallback"],
            "all_by_rule": [c["sha"][:12] for c in completed if c["summary"]["mode"] == "all"],
            "test_failures": [c["sha"][:12] for c in completed if c["rc"] == 1],
            "count_unavailable": [c["sha"][:12] for c in completed if not isinstance(c["summary"]["tests_run"], int)],
            "median_tests_run": _median(counts), "median_tests_run_narrow_only": _median(narrow)}


def _median(values):
    if not values:
        return None
    m = statistics.median(values)
    return int(m) if float(m).is_integer() else m


def check(a):
    m = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    s = judge(m.get("cases") or [])
    print(json.dumps(s, indent=1))
    errs = []
    if m.get("partial"):
        errs.append("the recording is partial")
    if s["completed"] < a.require_cases:
        errs.append(f"completed cases {s['completed']} < {a.require_cases}")
    if s["selector_errors"]:
        errs.append(f"{len(s['selector_errors'])} selector errors")
    if s["count_unavailable"]:
        errs.append("executed-test count unavailable for " + ", ".join(s["count_unavailable"]))
    if s["median_tests_run"] is None or s["median_tests_run"] > a.max_median:
        errs.append(f"median executed tests {s['median_tests_run']} > {a.max_median}")
    if hashlib.sha256(IMPACT.read_bytes()).hexdigest() != m.get("impact_sha256"):
        errs.append("tests/impact.py changed since the recording")
    for e in errs:
        print("FAIL: " + e, file=sys.stderr)
    return 1 if errs else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--commits", type=int, default=16)
    ap.add_argument("--cache", default=str(Path.home() / ".cache/maeng-harness/impact-replay"))
    ap.add_argument("--worktree", default=str(ROOT.parent / "agent-harness-impact-replay"))
    ap.add_argument("--require-cases", type=int, default=16)
    ap.add_argument("--max-median", type=int, default=100)
    a = ap.parse_args(argv)
    if a.record:
        record(a)
    return check(a)


if __name__ == "__main__":
    sys.exit(main())
