#!/usr/bin/env python3
"""Validate the saved D-14 deferral offline. This command only reports pending judgment."""
import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import re
import sys

CHECKS = {"gate": "Plugin suites (informational: ship does not read it)",
          "periodic": "Plugin periodic (informational: separate from gate)"}
CAUSES = {"test-regression", "flaky-same-head-rerun", "dependency-runner-environment", "inventory-collection",
          "timeout", "cancellation", "unavailable-unknown-data"}


def fields(value, names, label):
    if not isinstance(value, dict) or set(value) != set(names.split()):
        raise ValueError(label + ": missing or unknown fields")


def text(value):
    return isinstance(value, str) and bool(value.strip())


def timestamp(value):
    if not text(value):
        raise ValueError("unknown observation window timestamp")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("observation timestamps need a timezone")
    return stamp


def validate(report):
    fields(report, "version state judgment decision window_start window_end window_start_source earliest_judgment "
           "follow_up runs note", "report")
    if (type(report["version"]) is not int or report["version"] != 1 or report["state"] != "pending" or
            report["judgment"] != "pending" or report["decision"] != "D-14 Later small PR"):
        raise ValueError("only explicit pending judgment with D-14 Later small PR is supported")
    if not text(report["note"]) or report["window_start_source"] != "first plugin-suites run":
        raise ValueError("record the first plugin-suites run as the window source and explain pending work")
    earliest = date.fromisoformat(report["earliest_judgment"])
    follow_up = report["follow_up"]
    fields(follow_up, "pr earliest scope", "follow-up PR")
    if (earliest < date(2026, 11, 21) or date.fromisoformat(follow_up["earliest"]) < earliest or
            not text(follow_up["pr"]) or not text(follow_up["scope"])):
        raise ValueError("name the follow-up PR and scope, no earlier than 2026-11-21 and user judgment")
    runs = report["runs"]
    if not isinstance(runs, list):
        raise ValueError("runs must be an explicit list")
    # The initial empty pending record has no service readback; it establishes no observation window.
    if not runs and report["window_start"] is None and report["window_end"] is None:
        start = None
    else:
        start, end = timestamp(report["window_start"]), timestamp(report["window_end"])
        if end - start < timedelta(days=14):
            raise ValueError("the observation window must cover at least 14 days from the first run")
    seen, history = set(), defaultdict(list)
    failures = Counter()
    for run in runs:
        fields(run, "run_id attempt event head_sha check_name lane outcome suite_counts failure_cause", "run")
        if any(type(run[k]) is not int or run[k] < 1 for k in ("run_id", "attempt")):
            raise ValueError("run id and attempt must be positive integers")
        lane = run["lane"]
        if (not isinstance(lane, str) or lane not in CHECKS or run["check_name"] != CHECKS[lane] or
                run["event"] not in ({"push", "pull_request"} if lane == "gate" else {"schedule", "workflow_dispatch"})):
            raise ValueError("unknown check, lane or trigger")
        if not isinstance(run["head_sha"], str) or not re.fullmatch(r"[0-9a-f]{40}", run["head_sha"]):
            raise ValueError("unknown head sha")
        outcome, cause = run["outcome"], run["failure_cause"]
        if outcome not in ("success", "failure", "cancelled", "timed_out", "skipped"):
            raise ValueError("unknown outcome")
        if ((outcome == "success" and cause is not None) or
                (outcome != "success" and (not isinstance(cause, str) or cause not in CAUSES)) or
                (outcome == "cancelled" and cause != "cancellation") or
                (outcome == "timed_out" and cause != "timeout")):
            raise ValueError("unknown or inconsistent failure cause")
        counts = run["suite_counts"]
        fields(counts, "total ok failed skipped unavailable tests_run", "suite counts")
        if (any(type(n) is not int or n < 0 for n in counts.values()) or counts["total"] < 1 or
                counts["total"] != sum(counts[k] for k in ("ok", "failed", "skipped", "unavailable")) or
                (outcome == "success" and (counts["ok"] != counts["total"] or counts["tests_run"] < 1))):
            raise ValueError("unknown, empty or inconsistent suite counts")
        key = (run["run_id"], run["attempt"], lane)
        if key in seen:
            raise ValueError("duplicate run attempt")
        seen.add(key)
        history[run["run_id"]].append(run)
        if cause is not None:
            failures[cause] += 1
    for attempts in history.values():
        if (sorted(r["attempt"] for r in attempts) != list(range(1, max(r["attempt"] for r in attempts) + 1)) or
                len({(r["head_sha"], r["event"], r["lane"]) for r in attempts}) != 1):
            raise ValueError("missing first attempts or inconsistent rerun identity")
    flaky, unresolved = 0, 0
    for i, run in enumerate(runs):
        if run["outcome"] != "success":
            recovered = any(later["outcome"] == "success" and
                            (later["head_sha"], later["lane"]) == (run["head_sha"], run["lane"])
                            for later in runs[i + 1:])
            flaky += int(recovered)
            unresolved += int(not recovered)
    return {"state": "pending", "runs": len(history), "attempts": len(seen), "failures_by_cause": dict(failures),
            "flaky_same_head_reruns": flaky, "unresolved_failures": unresolved,
            "gate_attempts": sum(r["lane"] == "gate" for r in runs),
            "periodic_attempts": sum(r["lane"] == "periodic" for r in runs)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", required=True, type=Path)
    args = ap.parse_args(argv)
    try:
        summary = validate(json.loads(args.report.read_text()))
    except (OSError, ValueError, TypeError) as exc:
        print("invalid observation record: " + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(summary) if summary["attempts"] else "pending, no observations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
