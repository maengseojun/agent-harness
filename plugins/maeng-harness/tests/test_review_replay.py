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
    monkeypatch.setattr(rr, "_PROMPT", None)
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
    w.err, w.reviewers = None, []
    monkeypatch.setattr(rr, "enrolled_cases", lambda commit, path: w.enrolled)

    def fake(case, prompt, out_schema, cwd, reviewer_override=None):
        w.calls.append(prompt)
        w.reviewers.append(reviewer_override or case["reviewer"])
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


def test_replay_records_enrolled_reviewer_without_override(world):
    rc, res = world.go()
    saved = json.loads((world.tmp / "out/review-replay" / f"{world.case['id']}.json").read_text())
    assert rc == 0 and world.reviewers == [world.case["reviewer"]]
    for row in (saved, res["cases"][0]):
        assert row["reviewer"] == world.case["reviewer"]
        assert row["reviewer_override"] == {"applied": False}


@pytest.mark.parametrize("prompt_from", [None, "a23f430"])
def test_replay_override_only_selected_cases_and_discloses_enrollment(world, prompt_from):
    world.case["reviewer"] = {"model": "claude-fable-5", "effort": "high"}
    other = {**world.case, "id": "abc0000000000002", "reviewer": {"model": "gpt-x", "effort": "high"}}
    world.enrolled.append(other)
    world.man.write_text(json.dumps({"cases": world.enrolled}))
    enrolled_bytes = world.man.read_bytes()
    prompt_args = ["--prompt-from", prompt_from] if prompt_from else []
    world.go(*prompt_args)
    world.reviewers.clear()
    rc, res = world.go(*prompt_args, "--reviewer-override", "claude-opus-5-5/medium", "--only", world.case["id"])
    actual = {"model": "claude-opus-5-5", "effort": "medium"}
    assert rc == 0 and world.reviewers == [actual]
    assert ("V-1 to V-6" in world.calls[-1]) is (prompt_from is None)
    assert world.man.read_bytes() == enrolled_bytes
    for case, row in zip(world.enrolled, res["cases"]):
        saved = json.loads((world.tmp / "out/review-replay" / f"{case['id']}.json").read_text())
        expected_reviewer = actual if case is world.case else case["reviewer"]
        expected_override = ({"applied": True, "enrolled": case["reviewer"]} if case is world.case
                             else {"applied": False})
        for result in (saved, row):
            assert result["reviewer"] == expected_reviewer
            assert result["reviewer_override"] == expected_override


@pytest.mark.parametrize("model", ["claude-opus-5-5", "gpt-x"])
def test_run_reviewer_uses_override_for_provider_dispatch(tmp_path, model):
    case = {"reviewer": {"model": "claude-fable-5", "effort": "high"}}
    override = {"model": model, "effort": "medium"}
    mr = rr.maeng_review()
    result = {"verdict": "pass", "findings": []}
    with mock.patch.object(mr, "run_claude", return_value=(result, None, None)) as claude, \
            mock.patch.object(mr, "codex_attempts", return_value=(result, None)) as codex:
        assert rr.run_reviewer(case, "prompt", {}, str(tmp_path), reviewer_override=override) == (result, None)
    called, unused = (claude, codex) if model.startswith("claude-") else (codex, claude)
    assert called.call_count == 1 and called.call_args.args[:2] == (model, "medium")
    unused.assert_not_called()
    assert case["reviewer"] == {"model": "claude-fable-5", "effort": "high"}


@pytest.mark.parametrize("value", ["claude-opus-5-5", "/medium", "model/", "model//medium", " /medium", "model/ "])
def test_reviewer_override_rejects_malformed_pair(value, capsys):
    with mock.patch.object(rr, "replay") as replay, pytest.raises(SystemExit) as err:
        rr.main(["replay", "--manifest", "unused", "--results", "unused", "--reviewer-override", value])
    assert err.value.code == 2 and "expected MODEL/EFFORT" in capsys.readouterr().err
    replay.assert_not_called()


@pytest.mark.parametrize("change", ["missing", "model", "effort"])
def test_cached_result_from_another_reviewer_is_rerun(world, change):
    world.go()
    path = world.tmp / "out/review-replay" / f"{world.case['id']}.json"
    cached = json.loads(path.read_text())
    if change == "missing":
        cached.pop("reviewer")
    else:
        cached["reviewer"][change] = "different"
    path.write_text(json.dumps(cached))
    rc, res = world.go()
    assert rc == 0 and len(world.calls) == 2
    assert res["cases"][0]["reviewer"] == json.loads(path.read_text())["reviewer"] == world.case["reviewer"]


def test_reviewer_override_cache_follows_effective_reviewer(world):
    for effort in ("medium", "high"):
        for _ in range(2):
            assert world.go("--reviewer-override", f"claude-opus-5-5/{effort}")[0] == 0
    assert world.reviewers == [{"model": "claude-opus-5-5", "effort": e} for e in ("medium", "high")]
    world.go()
    assert world.reviewers[-1] == world.case["reviewer"] and len(world.calls) == 3


def test_reviewer_override_disclosure_on_cache_reuse(world):
    world.go()
    path = world.tmp / "out/review-replay" / f"{world.case['id']}.json"
    cached = json.loads(path.read_text())
    cached.pop("reviewer_override", None)  # a cache from before disclosure was added
    path.write_text(json.dumps(cached))
    _, res = world.go()
    assert len(world.calls) == 1
    assert res["cases"][0]["reviewer_override"] == {"applied": False}
    _, res = world.go("--reviewer-override", "gpt-x/high")
    assert len(world.calls) == 1
    assert res["cases"][0]["reviewer_override"] == {"applied": True, "enrolled": world.case["reviewer"]}
    assert json.loads(path.read_text())["reviewer_override"] == res["cases"][0]["reviewer_override"]


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


@pytest.mark.parametrize("cached_hash", [None, "different-bundle"])
def test_cached_result_from_another_bundle_is_rerun(world, cached_hash):
    world.go()
    f = world.tmp / "out" / "review-replay" / f"{world.case['id']}.json"
    cached = json.loads(f.read_text())
    digest = cached.pop("bundle_sha256")
    if cached_hash is not None:
        cached["bundle_sha256"] = cached_hash
    f.write_text(json.dumps(cached))
    rc, res = world.go()
    assert rc == 0 and len(world.calls) == 2
    result = json.loads(f.read_text())
    bundle, _, _ = rr.reconstruct(world.repo, world.case)
    assert result["bundle_sha256"] == digest == rr.bundle_sha256(bundle)
    for key in ("bundle_sha256", "bundle_bytes", "criteria_rev", "plan_path", "plan_resolution"):
        assert res["cases"][0][key] == result[key]


def test_cache_reconstructs_mutable_stored_scope(world):
    world.go()
    scope = {"files": ["app.py"], "excluded_files": ["docs/design/MAE-9-plan.md"],
             "delegated_files": [], "exclusion_reason": "review code only"}
    with mock.patch.object(rr, "stored_scope", return_value=scope):
        world.go()
        world.go()
    assert len(world.calls) == 2
    assert json.loads(world.calls[-1].split(rr.review_prompt(None), 1)[1])["files_reviewed"] == ["app.py"]


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
        return {"id": "c1", "status": status, "criteria_rev": "rev1", "plan_path": "docs/design/MAE-9-plan.md",
                "plan_resolution": "pinned", "expected": [{"title": "t1", "matched": m1}, {"title": "t2", "matched": m2}]}

    def test_different_bundle_bindings_fail(self):
        base = self.case({"x": 1}, None)
        for key in ("criteria_rev", "plan_path", "plan_resolution"):
            with self.subTest(key=key):
                rc, out, err = self.run_compare([base], [{**base, key: "different"}])
                self.assertEqual((rc, out["bundle_mismatch"]), (1, ["c1"]))
                self.assertIn("FAIL: bundle mismatch", err)
        base = {**base, "bundle_sha256": "digest"}
        for new in (self.case({"x": 1}, None), {**base, "bundle_sha256": "different"}):
            for before, after in ((base, new), (new, base)):
                with self.subTest(before=before, after=after):
                    rc, out, _ = self.run_compare([before], [after])
                    self.assertEqual((rc, out["bundle_mismatch"]), (1, ["c1"]))

    def test_binding_reports_digest_or_legacy_criteria_and_plan(self):
        for digest, binding in ((None, "criteria_rev+plan"), ("digest", "bundle_sha256")):
            with self.subTest(digest=digest):
                case = self.case({"x": 1}, None)
                if digest:
                    case["bundle_sha256"] = digest
                rc, out, _ = self.run_compare([case], [case])
                self.assertEqual((rc, out["binding"], out["bundle_mismatch"]), (0, binding, []))

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

    def test_new_prompt_error_counts_baseline_kept_blockers_as_lost(self):
        base = self.case({"x": 1}, {"y": 1})
        for status in ("error", "too_large", "no_result"):
            with self.subTest(status=status):
                new = [] if status == "no_result" else [self.case(None, None, status=status)]
                rc, out, err = self.run_compare([base], new, max_lost=1)
                self.assertEqual((rc, out["cases_compared"], out["expected"], out["kept_baseline"]), (1, 1, 2, 2))
                self.assertEqual(out["lost_vs_baseline"], [
                    {"id": "c1", "title": title, "reason": status} for title in ("t1", "t2")])
                self.assertEqual(out["excluded"], [])
                self.assertIn("lost by the new prompt", err)
        rc, out, _ = self.run_compare([{**base, "bundle_sha256": "digest"}],
                                      [self.case(None, None, status="error")], max_lost=1)
        self.assertEqual((rc, out["expected"], len(out["lost_vs_baseline"]), out["bundle_mismatch"]), (1, 2, 2, ["c1"]))

    def test_a_case_not_ok_in_baseline_is_excluded(self):
        rc, out, err = self.run_compare([self.case({"x": 1}, {"x": 1}, status="error")], [self.case(None, None)], max_lost=3)
        self.assertEqual((rc, out["cases_compared"], out["cases_not_in_both"]), (1, 0, ["c1"]))
        self.assertEqual(out["excluded"], [{"id": "c1", "baseline_status": "error", "new_status": "ok",
                                            "reason": "baseline is not ok"}])
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


@pytest.fixture
def strict_runs():
    """Fresh synthetic results; historical outputs supply membership, never fabricated result hashes."""
    frozen = json.loads((rr.ROOT / "docs/design/MAE-323-b2-review-replay-compare.json").read_text())
    cases = json.loads((rr.ROOT / "docs/design/MAE-323-b2-review-cases.json").read_text())["cases"]
    expected = {c["id"]: c["findings"] for c in cases}
    rows = [{"id": c["id"], "status": "no_result" if c["id"] in frozen["cases_not_in_both"] else "ok",
             "bundle_sha256": "test-bundle-" + c["id"],
             "reviewer": c["reviewer"], "reviewer_override": {"applied": False},
             "expected": [{**e, "matched": None} for e in c["findings"]]} for c in cases]
    base = {"expected": expected, "cases": rows}
    return base, json.loads(json.dumps(base))


def strict_compare(tmp_path, base, new, *, cli=False):
    import argparse
    import io
    from contextlib import redirect_stdout, redirect_stderr
    b, n = tmp_path / "baseline.json", tmp_path / "new.json"
    b.write_text(json.dumps(base))
    n.write_text(json.dumps(new))
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        if cli:
            rc = rr.main(["compare", "--baseline", str(b), "--results", str(n), "--require-bundle-sha256"])
        else:
            # Call compare directly so pre-change failures exercise logic, not an unrecognised CLI flag.
            rc = rr.compare(argparse.Namespace(baseline=str(b), results=str(n), max_lost=1000,
                                               require_bundle_sha256=True))
    return rc, json.loads(out.getvalue()), err.getvalue()


def test_strict_compare_cli_accepts_frozen_membership(tmp_path, strict_runs):
    rc, out, _ = strict_compare(tmp_path, *strict_runs, cli=True)
    assert (rc, out["binding"], out["cases_compared"], out["expected"]) == (0, "bundle_sha256", 41, 97)
    assert len(out["excluded"]) == 8


@pytest.mark.parametrize("change", ["model", "effort", "missing"])
def test_strict_compare_rejects_reviewer_mismatch(tmp_path, strict_runs, change):
    base, new = strict_runs
    row = new["cases"][0]
    if change == "missing":
        row.pop("reviewer")
    else:
        row["reviewer"][change] = "different"
    rc, out, err = strict_compare(tmp_path, base, new)
    assert rc == 1 and out["reviewer_mismatch"] == [row["id"]]
    assert (out["cases_compared"], out["expected"]) == (41, 97)
    assert "FAIL: reviewer mismatch" in err


@pytest.mark.parametrize("side", ["baseline", "new", "both"])
@pytest.mark.parametrize("excluded", [False, True])
def test_strict_compare_discloses_overrides_without_failing(tmp_path, strict_runs, side, excluded):
    base, new = strict_runs
    before = next(c for c in base["cases"] if (c["status"] != "ok") == excluded)
    after = next(c for c in new["cases"] if c["id"] == before["id"])
    enrolled = dict(before["reviewer"])
    for label, row in (("baseline", before), ("new", after)):
        row["reviewer"] = {"model": "claude-opus-5-5", "effort": "medium"}
        if side in (label, "both"):
            row["reviewer_override"] = {"applied": True, "enrolled": enrolled}
    rc, out, _ = strict_compare(tmp_path, base, new)
    assert rc == 0 and out["reviewer_mismatch"] == []
    assert out["reviewer_overrides"] == [{
        "id": before["id"],
        "baseline": {k: before[k] for k in ("reviewer", "reviewer_override")},
        "new": {k: after[k] for k in ("reviewer", "reviewer_override")}}]


def test_strict_compare_rejects_changed_frozen_counts(tmp_path, strict_runs, monkeypatch):
    design = tmp_path / "docs/design"
    design.mkdir(parents=True)
    for name in ("MAE-323-b2-review-cases.json", "MAE-323-b2-review-replay-compare.json"):
        data = json.loads((rr.ROOT / "docs/design" / name).read_text())
        if name.endswith("compare.json"):
            data["expected"] -= 1
        (design / name).write_text(json.dumps(data))
    monkeypatch.setattr(rr, "ROOT", tmp_path)
    rc, _, err = strict_compare(tmp_path, *strict_runs)
    assert rc == 1 and "FAIL: frozen comparison membership" in err


@pytest.mark.parametrize("side", ["baseline", "new", "both"])
@pytest.mark.parametrize("digest", [None, "", " ", "different"])
def test_strict_compare_rejects_missing_or_changed_hashes(tmp_path, strict_runs, side, digest):
    base, new = strict_runs
    for run in ([base, new] if side == "both" else [base if side == "baseline" else new]):
        run["cases"][0]["bundle_sha256"] = digest
    if side == "both" and digest == "different":
        new["cases"][0]["bundle_sha256"] = "another"
    rc, out, err = strict_compare(tmp_path, base, new)
    assert rc == 1 and out["bundle_mismatch"] == [base["cases"][0]["id"]]
    assert (out["binding"], out["cases_compared"], out["expected"]) == ("bundle_sha256", 41, 97)
    assert "FAIL: bundle mismatch" in err


@pytest.mark.parametrize("change", ["remove", "replace", "duplicate", "waiver", "baseline_error",
                                    "enrolled_expectation", "row_expectation", "reorder_expectations"])
def test_strict_compare_rejects_membership_changes(tmp_path, strict_runs, change):
    base, new = strict_runs
    for run in (base, new):
        if change == "remove":
            run["cases"].pop(0)
        elif change == "replace":
            run["cases"][0]["id"] = "unexpected-case"
        elif change == "duplicate":
            run["cases"].append(run["cases"][0])
        elif change == "waiver":
            next(c for c in run["cases"] if c["status"] != "ok")["status"] = "ok"
        elif change == "baseline_error":
            run["cases"][0]["status"] = "error"
        elif change == "enrolled_expectation":
            run["expected"][run["cases"][0]["id"]][0]["title"] = "changed enrollment"
        elif change == "row_expectation":
            run["cases"][0]["expected"].pop()
        else:
            run["cases"][0]["expected"].reverse()
    rc, _, err = strict_compare(tmp_path, base, new)
    assert rc == 1 and "FAIL: frozen comparison membership" in err


@pytest.mark.parametrize("status", ["error", "too_large", "would_run", "no_result", "absent"])
def test_strict_compare_lists_failed_new_cases_without_shrinking_denominator(tmp_path, strict_runs, status):
    base, new = strict_runs
    case = new["cases"][0]
    if status == "absent":
        new["cases"].pop(0)
    else:
        case["status"] = status
    rc, out, _ = strict_compare(tmp_path, base, new)
    assert (rc, out["cases_compared"], out["expected"]) == (1, 41, 97)
    assert out["cases_not_run"] == [{"id": case["id"], "status": "no_result" if status == "absent" else status}]
    assert len(out["excluded"]) == 8
