#!/usr/bin/env python3
"""Run the existing mutation sample on disposable repositories; retain logs, DB and report.json.

  periodic_checks.py [--root DIR] [--output periodic-results] [--seed mae232]

The sample remains 50 mutants of lib/maeng/gates.py. Survivors are measurements, not runner failures.
"""
import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plugin_checks import REPO, isolated_env, tests_run, tests_skipped  # noqa: E402

IGNORE = {".git", "__pycache__", ".pytest_cache", ".coverage", ".harness"}
FILE = "lib/maeng/gates.py"


def fingerprint(path):
    digest = hashlib.sha256()
    for p in sorted(path.rglob("*")):
        if p.is_file() and not (set(p.relative_to(path).parts) & IGNORE):
            data = p.read_bytes()
            digest.update(p.relative_to(path).as_posix().encode() + b"\0" + str(len(data)).encode() + b"\0" + data)
    return digest.hexdigest()


def run(root, output, seed="mae232"):
    root, output = Path(root).resolve(), Path(output).resolve()
    plugin = root / "plugins/maeng-harness"
    result = {"status": "incomplete", "source_revision": None, "seed": seed, "sample": 50,
              "selected": None, "executed": None, "tests_run": None, "tests_skipped": None,
              "killed": None, "survived": None, "failures": [], "restored": False,
              "checkout_unchanged": False, "cleanup": False, "workspace": None}
    if output.is_relative_to(plugin) or Path(tempfile.gettempdir()).resolve().is_relative_to(root):
        raise ValueError("output and temporary workspace must be outside the source plugin/checkout respectively")
    output.mkdir(parents=True, exist_ok=True)
    for name in ("report.json", "mutants.db", "baseline.log", "mutation.log"):
        (output / name).unlink(missing_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="periodic-checks-"))
    result["workspace"] = str(workspace)
    env = isolated_env(workspace)
    before = None
    original_lib = None
    suite = workspace / "suite/plugins/maeng-harness"
    source = workspace / "source/plugins/maeng-harness"
    db = workspace / "mutants.db"
    try:
        before = fingerprint(plugin)
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, env=env, capture_output=True, text=True,
                                  timeout=30)
        if revision.returncode or not re.fullmatch(r"[0-9a-f]{40}", revision.stdout.strip()):
            raise ValueError("source revision unavailable")
        result["source_revision"] = revision.stdout.strip()
        deps = subprocess.run([sys.executable, "-c", "import mutmut, pytest, xdist"], env=env,
                              capture_output=True, text=True, timeout=30)
        if deps.returncode:
            raise ValueError("missing dependency: mutmut 2.x, pytest or pytest-xdist")
        # Tests read repository siblings and history; a bare plugin copy cannot run their baseline.
        clone = subprocess.run(["git", "clone", "--shared", "--no-hardlinks", "--no-checkout", str(root),
                                str(workspace / "source")], env=env, capture_output=True, text=True, timeout=120)
        if clone.returncode:
            raise ValueError("disposable local clone failed: " + clone.stderr)

        def ignore(directory, names):
            return [n for n in names if n in IGNORE or (Path(directory) / n).resolve() == output]

        shutil.copytree(root, workspace / "source", dirs_exist_ok=True, ignore=ignore)
        shutil.copytree(workspace / "source", workspace / "suite")
        if fingerprint(source) != before:
            raise ValueError("source changed while copying")
        original_lib = fingerprint(source / "lib")
        baseline = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-n", "8", "tests"],
                                  cwd=suite, env=env, capture_output=True, text=True, timeout=900)
        out = baseline.stdout + baseline.stderr
        (output / "baseline.log").write_text(out)
        result["tests_run"], result["tests_skipped"] = tests_run(out), tests_skipped(out)
        if baseline.returncode or not result["tests_run"] or result["tests_skipped"] is None:
            raise ValueError("baseline failed, empty, all-skipped or unknown test counts")
        command = [sys.executable, str(workspace / "source/tools/testperf/mutate.py"), str(db),
                   "--lib", str(source), "--suite", "periodic=" + str(suite), "--file", FILE,
                   "--sample", "50", "--seed", seed]
        mutation = subprocess.run(command, cwd=workspace / "suite", env=env, capture_output=True, text=True,
                                  timeout=10800)
        out = mutation.stdout + mutation.stderr
        (output / "mutation.log").write_text(out)
        samples = re.findall(r"^lib/maeng/gates\.py: \d+ mutants, sampling (\d+)$", out, re.M)
        if len(samples) != 1:
            raise ValueError("unknown selected mutant count")
        result["selected"] = int(samples[0])
        if not db.is_file():
            raise ValueError("missing mutation database")
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as con:
            rows = con.execute("SELECT file,line,idx,suite,killed,rc,n_selected FROM mutants").fetchall()
        result["executed"] = len(rows)
        # rc 2: `pytest -x -n` (xdist) exits 2 when it stops at the first failure, i.e. killed.
        for file, line, idx, name, killed, rc, selected in rows:
            if (file != FILE or name != "periodic" or type(line) is not int or line < 1 or
                    type(idx) is not int or idx < 0 or type(rc) is not int or rc not in (0, 1, 2) or
                    type(killed) is not int or killed != int(rc != 0) or selected != -1):
                raise ValueError("unknown, skipped, timed-out or invalid mutant result")
        if len({r[:4] for r in rows}) != len(rows):
            raise ValueError("duplicate mutant results")
        result["killed"] = sum(r[4] for r in rows)
        result["survived"] = len(rows) - result["killed"]
        if (mutation.returncode or not 0 < result["selected"] <= result["sample"] or
                result["executed"] != result["selected"]):
            raise ValueError("mutation failed, empty or incomplete execution")
    except (OSError, ValueError, sqlite3.Error, subprocess.TimeoutExpired) as exc:
        result["failures"].append(str(exc))
    finally:
        try:
            result["restored"] = (original_lib is not None and (source / "lib").is_dir() and
                                  (suite / "lib").is_dir() and
                                  fingerprint(source / "lib") == fingerprint(suite / "lib") == original_lib)
            result["checkout_unchanged"] = before is not None and fingerprint(plugin) == before
            if db.is_file():
                shutil.copy2(db, output / "mutants.db")
        except OSError as exc:
            result["failures"].append("restoration/result readback: " + str(exc))
        try:
            shutil.rmtree(workspace)
        except OSError as exc:
            result["failures"].append("cleanup: " + str(exc))
        result["cleanup"] = not workspace.exists()
        for field in ("restored", "checkout_unchanged", "cleanup"):
            if not result[field]:
                result["failures"].append(field + " check failed")
    if not result["failures"]:
        result["status"] = "ok"
    (output / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=REPO)
    ap.add_argument("--output", type=Path, default=Path("periodic-results"))
    ap.add_argument("--seed", default="mae232")
    args = ap.parse_args(argv)
    result = run(args.root, args.output, args.seed)
    print(json.dumps(result))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
