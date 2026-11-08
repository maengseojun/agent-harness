"""review_replay.py on a temporary receipts directory with two hand-written receipts."""
import json
import os
import re
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


# ---- replay subcommand: temp git repo, injected reviewer and enrolled-cases loader ----
import importlib.util  # noqa: E402
import tempfile  # noqa: E402
import unittest  # noqa: E402
from unittest import mock  # noqa: E402

import pytest  # noqa: E402

_spec = importlib.util.spec_from_file_location("review_replay_tool", SCRIPT)
rr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rr)

PLAN = "# Plan\n\nRequirements -> acceptance:\n- **AC-1** the app greets\n\nVerification:\n- AC-1 `pytest`\n"


def _g(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@x", *args],
                          capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("MAENG_HOME", str(tmp_path / "home"))
    repo = tmp_path / "repo"
    repo.mkdir()
    _g(repo, "init", "-q", "-b", "main")
    (repo / "app.py").write_text("print('a')\n")
    _g(repo, "add", "."), _g(repo, "commit", "-qm", "c0")
    c0 = _g(repo, "rev-parse", "HEAD")
    (repo / "app.py").write_text("print('b')\n")
    _g(repo, "commit", "-qam", "c1")
    c1 = _g(repo, "rev-parse", "HEAD")
    (repo / "app.py").write_text("print('c')\n")
    (repo / "docs/design").mkdir(parents=True)
    (repo / "docs/design/MAE-9-plan.md").write_text(PLAN)
    _g(repo, "add", "."), _g(repo, "commit", "-qm", "c2")
    c2 = _g(repo, "rev-parse", "HEAD")
    exp = [{"severity": "high", "title": "Missing validation of input", "file": "app.py", "line": 10,
            "expected_blocking": True},
           {"severity": "critical", "title": "Race condition in cache refresh handler", "file": "lib.py",
            "line": 100, "expected_blocking": True}]
    case = {"id": "abc0000000000001", "repo": "r/x", "pr": 1, "base": c1, "head": c2, "base_ref": "refs/heads/main",
            "plan_path": None, "criteria_rev": "old", "reviewer": {"model": "gpt-x", "effort": "high"},
            "verdict": "fail", "reconstructable": True, "findings": exp}
    man = tmp_path / "cases.json"
    man.write_text(json.dumps({"cases": [case]}))
    w = type("W", (), {})()
    w.repo, w.case, w.exp, w.man, w.tmp, w.c0, w.c1, w.c2, w.calls = repo, case, exp, man, tmp_path, c0, c1, c2, []
    w.enrolled = [case]
    w.found = [{"severity": "high", "title": "Totally different words", "body": "b", "file": "app.py", "line": 15}]
    w.err = None
    monkeypatch.setattr(rr, "enrolled_cases", lambda commit, path: w.enrolled)

    def fake(case, prompt, out_schema, cwd):
        w.calls.append(prompt)
        if w.err:
            return None, w.err
        return {"verdict": "fail", "findings": w.found}, None

    monkeypatch.setattr(rr, "run_reviewer", fake)

    def go(*extra):
        res = tmp_path / "out" / "results.json"
        rc = rr.main(["replay", "--manifest", str(man), "--results", str(res), "--repo", str(repo), *extra])
        return rc, (json.loads(res.read_text()) if res.exists() else None)

    w.go = go
    return w


def test_integrity_mismatch_runs_nothing(world, capsys):
    world.enrolled = []
    rc, res = world.go()
    assert rc == 1 and res is None and world.calls == []
    assert "manifest changed since enrollment" in capsys.readouterr().out


def test_lost_blocker_threshold(world):
    rc, res = world.go("--max-lost-blockers", "0")
    assert rc == 1 and [x["title"] for x in res["lost_blockers"]] == [world.exp[1]["title"]]
    assert res["cases"][0]["expected"][0]["matched"]["line"] == 15
    rc, res = world.go("--max-lost-blockers", "1", "--force")
    assert rc == 0 and res["cases_run"] == 1 and res["verdicts"] == {"fail": 1}


def test_title_similarity_and_severity(world):
    world.found.append({"severity": "high", "title": "Race condition in the cache refresh handler", "body": "b",
                        "file": "other.py", "line": 1})
    rc, res = world.go("--max-lost-blockers", "0")
    assert rc == 0 and res["lost_blockers"] == []
    world.found[1]["severity"] = "medium"
    rc, res = world.go("--max-lost-blockers", "0", "--force")
    assert rc == 1 and len(res["lost_blockers"]) == 1


def test_reviewer_error_fails_require_complete(world):
    world.err = "boom"
    rc, res = world.go("--require-complete")
    assert rc == 1 and res["cases"][0]["status"] == "error" and res["lost_blockers"] == []
    rc, _ = world.go("--max-lost-blockers", "0", "--force")
    assert rc == 0


def test_expected_verbatim_and_no_rerun(world):
    rc, res = world.go()
    assert res["expected"] == {world.case["id"]: world.exp}
    assert len(world.calls) == 1
    world.go()
    assert len(world.calls) == 1
    world.go("--force")
    assert len(world.calls) == 2


@pytest.mark.parametrize("cached_hash", [None, "different-prompt"])
def test_cached_result_from_another_prompt_is_rerun(world, cached_hash):
    world.go()
    f = world.tmp / "out" / "review-replay" / f"{world.case['id']}.json"
    cached = json.loads(f.read_text())
    prompt_sha256 = cached.pop("prompt_sha256")
    if cached_hash is not None:
        cached["prompt_sha256"] = cached_hash
    f.write_text(json.dumps(cached))
    with mock.patch.object(rr, "run_case", wraps=rr.run_case) as run_case:
        rc, res = world.go()
    assert rc == 0 and run_case.call_count == 1 and len(world.calls) == 2
    assert json.loads(f.read_text())["prompt_sha256"] == prompt_sha256 == res["prompt_sha256"]


def test_aggregate_does_not_relabel_an_unselected_case_from_another_prompt(world):
    world.go()
    f = world.tmp / "out" / "review-replay" / f"{world.case['id']}.json"
    cached = json.loads(f.read_text())
    cached["prompt_sha256"] = "different-prompt"
    f.write_text(json.dumps(cached))
    rc, res = world.go("--only", "another-case")
    assert rc == 0 and res["cases_run"] == 0 and res["cases"][0]["status"] == "no_result"
    assert len(world.calls) == 1


def test_plan_resolution(world):
    b, path, how = rr.reconstruct(world.repo, world.case)
    assert (path, how) == ("docs/design/MAE-9-plan.md", "changed-single")
    assert re.fullmatch(r"[0-9a-f]{64}", b["criteria_rev"]) and b["criteria"] == ["AC-1"]
    assert b["files_reviewed"] == ["app.py", "docs/design/MAE-9-plan.md"] and b["changed_files"]["app.py"] == "print('c')"
    b, path, how = rr.reconstruct(world.repo, dict(world.case, base=world.c0, head=world.c1))
    assert (path, how, b["criteria"], b["plan_text"], b["criteria_rev"]) == (None, "none", None, None, None)


def test_too_large(world):
    rc, res = world.go("--max-bytes", "10", "--require-complete")
    assert rc == 1 and res["cases"][0]["status"] == "too_large" and world.calls == []


class Compare(unittest.TestCase):
    """`compare`: blockers the baseline prompt kept and the new prompt lost, on the same bundles."""

    def run_compare(self, base_cases, new_cases, max_lost=None):
        import io
        from contextlib import redirect_stdout, redirect_stderr
        with tempfile.TemporaryDirectory() as d:
            b, n = Path(d, "b.json"), Path(d, "n.json")
            expected = {"c1": [{"title": "t1"}, {"title": "t2"}]}
            b.write_text(json.dumps({"expected": expected, "prompt_from": "old", "cases": base_cases}))
            n.write_text(json.dumps({"expected": expected, "prompt_from": "new", "cases": new_cases}))
            out, err = io.StringIO(), io.StringIO()
            argv = ["compare", "--baseline", str(b), "--results", str(n)]
            if max_lost is not None:
                argv += ["--max-lost", str(max_lost)]
            with redirect_stdout(out), redirect_stderr(err):
                rc = rr.main(argv)
        return rc, json.loads(out.getvalue()) if out.getvalue().startswith("{") else out.getvalue(), err.getvalue()

    def case(self, m1, m2, status="ok"):
        return {"id": "c1", "status": status, "expected": [{"title": "t1", "matched": m1}, {"title": "t2", "matched": m2}]}

    def test_lost_is_kept_by_baseline_and_not_by_new(self):
        rc, out, err = self.run_compare([self.case({"x": 1}, None)], [self.case(None, {"y": 1})], max_lost=0)
        self.assertEqual(rc, 1)
        self.assertEqual([l["title"] for l in out["lost_vs_baseline"]], ["t1"])
        self.assertEqual([g["title"] for g in out["gained_vs_baseline"]], ["t2"])
        self.assertEqual((out["kept_baseline"], out["kept_new"], out["lost_by_both"]), (1, 1, 0))
        self.assertIn("lost by the new prompt", err)

    def test_lost_by_both_is_not_charged_to_the_new_prompt(self):
        rc, out, _ = self.run_compare([self.case(None, None)], [self.case(None, None)], max_lost=0)
        self.assertEqual((rc, out["lost_vs_baseline"], out["lost_by_both"]), (0, [], 2))

    def test_a_case_missing_or_not_ok_in_one_run_is_not_compared(self):
        rc, out, err = self.run_compare([self.case({"x": 1}, {"x": 1}, status="error")], [self.case(None, None)], max_lost=3)
        self.assertEqual((rc, out["cases_compared"], out["cases_not_in_both"]), (1, 0, ["c1"]))
        self.assertIn("FAIL: empty comparison denominator", err)
        self.assertIn("cases_not_in_both=1", err)

    def test_empty_cases_or_expectations_fail_even_with_a_loss_allowance(self):
        empty = {**self.case(None, None), "expected": []}
        for cases in ([], [empty]):
            rc, _, err = self.run_compare(cases, cases, max_lost=3)
            self.assertEqual(rc, 1)
            self.assertIn("FAIL: empty comparison denominator", err)

    def test_runs_with_different_expectations_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            b, n = Path(d, "b.json"), Path(d, "n.json")
            b.write_text(json.dumps({"expected": {"c1": [{"title": "t1"}]}, "cases": []}))
            n.write_text(json.dumps({"expected": {"c1": [{"title": "t2"}]}, "cases": []}))
            import io
            from contextlib import redirect_stdout
            with redirect_stdout(io.StringIO()):
                self.assertEqual(rr.main(["compare", "--baseline", str(b), "--results", str(n)]), 1)

    def test_prompt_from_reads_the_literal_at_a_commit(self):
        import argparse
        rr._PROMPT = None
        try:
            old = rr.review_prompt(argparse.Namespace(prompt_from="a23f430"))
        finally:
            rr._PROMPT = None
        self.assertTrue(old.startswith("You are an independent, adversarial reviewer"))
        self.assertNotIn("V-1 to V-6", old)
        self.assertIn("V-1 to V-6", rr.review_prompt(argparse.Namespace(prompt_from=None)))
        rr._PROMPT = None


def test_pinned_plan_path_wins_and_the_cap_counts_utf8_bytes(world):
    """Codex findings on PR #104: a manifest plan_path is honoured at head before any heuristic; prompt_bytes is the
    UTF-8 length, so a non-ASCII bundle cannot slip under --max-bytes by code-point count."""
    repo = world.repo
    case = dict(world.case, plan_path="docs/design/MAE-9-plan.md")
    path, how = rr.resolve_plan(repo, case)
    assert (path, how) == ("docs/design/MAE-9-plan.md", "pinned")
    path, how = rr.resolve_plan(repo, dict(case, plan_path="docs/design/absent-plan.md"))
    assert how != "pinned"
    assert len("한글".encode("utf-8")) == 6 and len("한글") == 2  # the unit the cap must use
