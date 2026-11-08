#!/usr/bin/env python3
"""Verify the hosting CLI observed by SessionStart; never run this from a hook.

  python3 tools/testperf/cli_compat.py verify --session SESSION_ID [--timeout 900]

Only successful, nonempty process-hook and full-suite runs replace the verified record.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins/maeng-harness"
POLICY = PLUGIN / "policy/cli-compatibility.json"
sys.path.insert(0, str(PLUGIN / "lib"))
from maeng import state  # noqa: E402
from maeng.common import now_iso, sha256, write_json  # noqa: E402
from maeng.evidence import test_count  # noqa: E402

SMOKE = ["python3", "-m", "pytest", "-q", "plugins/maeng-harness/tests/test_boundary.py"]
FULL = ["python3", "-m", "pytest", "-q", "-n", "8"]
IDENTITY = ("observed_version", "source", "executable", "observed_at")


def plugin_revision():
    """Content revision includes dirty/new plugin files and this runner, without changing a git index."""
    digest = hashlib.sha256()
    paths = [p for p in PLUGIN.rglob("*") if p.is_file() and p != POLICY
             and not {"__pycache__", ".pytest_cache"}.intersection(p.parts)]
    paths.append(Path(__file__).resolve())
    for p in sorted(paths):
        name = p.relative_to(REPO).as_posix() if p.is_relative_to(REPO) else "tools/testperf/cli_compat.py"
        digest.update(name.encode() + b"\0" + p.read_bytes() + b"\0")
    return digest.hexdigest()


def run_check(command, timeout):
    started = time.monotonic()
    # Ambient selection flags must not turn the required full suite into a subset.
    env = {**os.environ, "PYTEST_ADDOPTS": ""}
    proc = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True, timeout=timeout)
    output = proc.stdout + proc.stderr
    count = test_count(output)
    result = {"command": command, "returncode": proc.returncode, "tests_run": count,
              "checked_at": now_iso(), "duration_s": round(time.monotonic() - started, 3),
              "output_sha256": sha256(output)}
    if proc.returncode or count is None or count <= 0:
        raise ValueError(f"check failed or executed-test count unavailable/zero: {result}")
    return result


def verify(session_id, timeout):
    if not session_id:
        raise ValueError("a SessionStart session ID is required")
    observation = state.load(session_id).get("cli_compatibility")
    if (not isinstance(observation, dict)
            or not re.fullmatch(r"\d+\.\d+\.\d+(?:-[\w.-]+)?", observation.get("observed_version") or "")
            or observation.get("source") != "CLAUDE_CODE_EXECPATH --version"
            or not Path(observation.get("executable") or "").is_absolute()
            or not observation.get("observed_at")):
        raise ValueError("hosting CLI version unknown/unbound; restart with a host-provided executable first")
    identity = {k: observation[k] for k in IDENTITY}
    state.update(session_id, lambda st: st["cli_compatibility"].update(pending=True))
    revision = plugin_revision()
    checks = {}
    for name, command in (("hook_smoke", SMOKE), ("full_suite", FULL)):
        checks[name] = run_check(command, timeout)
        print(f"{name}: {checks[name]['tests_run']} executed tests passed")
    if plugin_revision() != revision:
        raise ValueError("plugin changed during checks; compatibility remains pending")

    def finish(st):
        current = st.get("cli_compatibility") or {}
        if any(current.get(k) != v for k, v in identity.items()):
            raise ValueError("host observation changed during checks; compatibility remains pending")
        write_json(POLICY, {"verified": {"cli_version": identity["observed_version"],
                   "source": identity["source"], "observed_at": identity["observed_at"],
                   "plugin_revision": revision, "checked_at": now_iso(), "checks": checks}})
        current.update(pending=False, verified_version=identity["observed_version"])
    state.update(session_id, finish)
    print(f"verified hosting CLI {identity['observed_version']} at plugin revision {revision}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("verify")
    check.add_argument("--session", default=os.environ.get("MAENG_SESSION_ID"))
    check.add_argument("--timeout", type=int, default=900, help="seconds per check (outside SessionStart)")
    args = parser.parse_args(argv)
    try:
        if args.timeout <= 0:
            raise ValueError("timeout must be positive")
        verify(args.session, args.timeout)
    except (OSError, ValueError, subprocess.TimeoutExpired, state.StateCorrupt) as exc:
        print(f"cli compatibility: {exc}; prior verified record retained", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
