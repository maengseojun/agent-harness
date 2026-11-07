"""review_replay.py on a temporary receipts directory with two hand-written receipts."""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "tools" / "testperf" / "review_replay.py"
REAL_HEAD = subprocess.run(["git", "-C", str(SCRIPT.parent), "rev-parse", "HEAD"], capture_output=True,
                           text=True).stdout.strip()
FAKE = "f" * 40


def receipt(pr, head, findings):
    s = {"kind": "code", "repo": "r/x", "pr": pr, "base": REAL_HEAD, "head": head, "destination": "refs/heads/main",
         "criteria_rev": "rev1"}
    v = {"verdict": "fail", "reviewer": {"model": "m", "effort": "high", "provenance": "review-run"}, "subject": s,
         "findings": findings}
    return {"key": "code-" + str(pr), "status": "unconsumed", "verdict": v, "history": [{"at": "2026-11-01T10:00:00Z"}]}


def run(home, *args):
    env = dict(os.environ, MAENG_HOME=str(home))
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env)


def test_build_and_check(tmp_path):
    rd = tmp_path / "receipts"
    rd.mkdir()
    hi = {"severity": "high", "title": "T", "file": "a.py", "line": 3, "body": "SECRET BODY"}
    (rd / "code-1.json").write_text(json.dumps(receipt(1, FAKE, [hi])))
    (rd / "code-2.json").write_text(json.dumps(receipt(2, REAL_HEAD, [dict(hi, severity="medium")])))
    out = tmp_path / "cases.json"
    assert run(tmp_path, "build", "--out", str(out)).returncode == 0
    m = json.loads(out.read_text())
    assert (m["receipts_scanned"], m["cases_enrolled"], m["cases_reconstructable"]) == (2, 1, 0)
    assert m["built_at"] == "2026-11-01T10:00:00Z"
    c = m["cases"][0]
    assert (c["pr"], c["reconstructable"], c["findings"]) == (1, False, [
        {"severity": "high", "title": "T", "file": "a.py", "line": 3, "expected_blocking": True}])
    assert "SECRET BODY" not in out.read_text()
    assert run(tmp_path, "check", "--manifest", str(out)).returncode == 0
    out2 = tmp_path / "again.json"
    run(tmp_path, "build", "--out", str(out2))
    assert out.read_bytes() == out2.read_bytes()


def test_check_fails_on_empty(tmp_path):
    f = tmp_path / "e.json"
    f.write_text(json.dumps({"receipts_scanned": 3, "cases_enrolled": 0, "cases_reconstructable": 0, "cases": []}))
    assert run(tmp_path, "check", "--manifest", str(f)).returncode == 1
