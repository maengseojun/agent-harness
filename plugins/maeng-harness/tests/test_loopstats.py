"""loopstats.py on small hand-written transcripts. Expected numbers are worked out by hand in the comments."""
import json
import re
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "tools" / "testperf" / "loopstats.py"
ROLES = {"grades": {"quick": {"agent": "maeng-tools:quick", "ceiling": "high"}}}


def line(rid, secs, agent, ver, effort, attributed=None):
    """One assistant line of a subagent transcript; one request per line, `secs` after 2026-11-02T06:00:00Z."""
    h, rest = divmod(secs, 3600)
    o = {"type": "assistant", "timestamp": "2026-11-02T%02d:%02d:%02dZ" % (6 + h, rest // 60, rest % 60),
         "requestId": rid, "agentId": agent, "isSidechain": True, "version": ver, "effort": effort,
         "perTurnEffort": effort, "uuid": "u-" + rid, "gitBranch": "feat/x",
         "message": {"model": "claude-test", "content": [], "usage": {"output_tokens": 1}}}
    if attributed:
        o["attributionAgent"] = attributed
    return json.dumps(o, separators=(",", ":"))


def write_subagent(root, name, lines):
    d = root / "-proj" / "sess" / "subagents"
    d.mkdir(parents=True, exist_ok=True)
    (d / ("agent-%s.jsonl" % name)).write_text("\n".join(lines) + "\n")


def fixture(tmp_path):
    root = tmp_path / "projects"
    # A: xhigh, requests at 0, 100, 200 s -> active time 100 + 100 + 0 = 200 s
    write_subagent(root, "A", [line("a1", 0, "A", "2.1.309", "xhigh", "maeng-tools:quick"),
                               line("a2", 100, "A", "2.1.309", "xhigh", "maeng-tools:quick"),
                               line("a3", 200, "A", "2.1.309", "xhigh", "maeng-tools:quick")])
    # B: high, same shape -> 200 s
    write_subagent(root, "B", [line("b1", 0, "B", "2.1.309", "high", "maeng-tools:quick"),
                               line("b2", 100, "B", "2.1.309", "high", "maeng-tools:quick"),
                               line("b3", 200, "B", "2.1.309", "high", "maeng-tools:quick")])
    # C: xhigh, 0 and 100 s -> 100 s; D: high, 0 and 600 s -> gap capped at 300 s
    write_subagent(root, "C", [line("c1", 0, "C", "2.1.317", "xhigh"), line("c2", 100, "C", "2.1.317", "xhigh")])
    write_subagent(root, "D", [line("d1", 0, "D", "2.1.317", "high"), line("d2", 600, "D", "2.1.317", "high")])
    return root


def run(root, tmp_path, *extra, until="2026-11-05"):
    return subprocess.run([sys.executable, str(SCRIPT), "--projects", str(root), "--state", str(tmp_path / "state"),
                           "--until", until, "--days", "7", *extra], capture_output=True, text=True)


def test_effort_share_is_split_by_cli_version(tmp_path):
    p = run(fixture(tmp_path), tmp_path)
    assert p.returncode == 0, p.stderr
    # before 2.1.317: A and B, xhigh 200 s of 400 s = 50.0%; from 2.1.317: C 100 s xhigh of 100 + 300 s = 25.0%
    assert re.search(r"before 2\.1\.317\s+subagents\s+2\s+50\.0%", p.stdout)
    assert re.search(r"2\.1\.317 and later\s+subagents\s+2\s+25\.0%", p.stdout)
    assert re.search(r"version not recorded\s+subagents\s+0\s+no data", p.stdout)


def test_an_unparsable_file_is_counted_not_dropped(tmp_path):
    root = fixture(tmp_path)
    write_subagent(root, "bad", ['{"type":"assistant","timestamp":"2026-11-02T06:00:00Z"'])  # cut off mid-line
    p = run(root, tmp_path)
    assert p.returncode == 0, p.stderr
    assert "files that could not be parsed: 1 (transcripts 1, review files 0)" in p.stdout
    assert re.search(r"before 2\.1\.317\s+subagents\s+2\s+50\.0%", p.stdout)  # the good files still count


def test_a_window_without_transcripts_is_an_error_and_prints_no_table(tmp_path):
    p = run(fixture(tmp_path), tmp_path, until="2020-01-01")
    assert p.returncode != 0
    assert "no transcript in the window" in p.stderr
    assert p.stdout == ""


def test_requests_above_the_grade_ceiling_need_roles(tmp_path):
    root = fixture(tmp_path)
    assert "requests above the grade ceiling: 미측정 (needs --roles)" in run(root, tmp_path).stdout
    roles = tmp_path / "roles.json"
    roles.write_text(json.dumps(ROLES))
    # A and B ran as `quick` (ceiling high): A's 3 xhigh requests are above it, B's 3 high requests are not
    p = run(root, tmp_path, "--roles", str(roles))
    assert "requests above the grade ceiling: 3 of 6 checked subagent requests" in p.stdout
