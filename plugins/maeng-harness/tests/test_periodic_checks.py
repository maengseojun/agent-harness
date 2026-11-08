"""Offline periodic and observation contracts; mutation execution is stubbed."""
import copy
import importlib.util
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[3]


def load(name):
    spec = importlib.util.spec_from_file_location(name, REPO / "tools/testperf" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


periodic = load("periodic_checks")
observation = load("ci_observation")


@pytest.fixture
def mutation(tmp_path, monkeypatch):
    root = tmp_path / "checkout"
    plugin = root / "plugins/maeng-harness"
    (plugin / "lib/maeng").mkdir(parents=True)
    (plugin / "lib/maeng/gates.py").write_text("VALUE = 1\n")
    (plugin / "tests").mkdir()
    (plugin / "tests/test_example.py").write_text("def test_example(): assert True\n")
    calls = []
    settings = {"baseline": "3 passed in 0.1s", "baseline_rc": 0, "selected": 2, "rows": 2,
                "rc": 0, "restore": True, "row_rc": 1, "killed": 1, "dependency_rc": 0}

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        out, rc = "", 0
        if argv[0] == "git":
            out = settings.get("revision", "a" * 40 + "\n")
            rc = settings.get("clone_rc", 0) if "clone" in argv else settings.get("revision_rc", 0)
        elif "-c" in argv:
            rc = settings["dependency_rc"]
        elif "pytest" in argv:
            out, rc = settings["baseline"], settings["baseline_rc"]
        else:
            assert argv[1].endswith("/tools/testperf/mutate.py")
            db = Path(argv[2])
            lib = Path(argv[argv.index("--lib") + 1])
            suite = Path(argv[argv.index("--suite") + 1].split("=", 1)[1])
            assert not lib.is_relative_to(root) and not suite.is_relative_to(root)
            assert not db.exists(), "every run needs a fresh database"
            assert "--file" in argv and argv[argv.index("--sample") + 1] == "50"
            assert argv[argv.index("--seed") + 1] == "mae232"
            assert "KEY" not in " ".join(kwargs["env"])
            assert Path(kwargs["env"]["HOME"]).is_relative_to(db.parent)
            assert (suite / "lib/maeng/gates.py").read_text() == "VALUE = 1\n"
            (suite / "lib/maeng/gates.py").write_text("VALUE = 2\n")
            if settings["restore"]:
                (suite / "lib/maeng/gates.py").write_text("VALUE = 1\n")
            if settings.get("no_db"):
                return SimpleNamespace(returncode=0, stdout="lib/maeng/gates.py: 10 mutants, sampling 2\n", stderr="")
            con = sqlite3.connect(db)
            con.execute("CREATE TABLE mutants(file, line, idx, source_line, mutated_line, suite, killed, rc, duration_s, n_selected)")
            for i in range(settings["rows"]):
                con.execute("INSERT INTO mutants VALUES(?,?,?,?,?,?,?,?,?,?)",
                            ("lib/maeng/gates.py", i + 1, 0, "VALUE = 1", "VALUE = 2", "periodic",
                             settings["killed"], settings["row_rc"], 0.1, -1))
            con.commit()
            con.close()
            out = settings.get("mutation_output", f"lib/maeng/gates.py: 10 mutants, sampling {settings['selected']}\n")
            rc = settings["rc"]
        if settings.get("timeout") and "mutate.py" in " ".join(argv):
            raise subprocess.TimeoutExpired(argv, 1, output=b"partial")
        return SimpleNamespace(returncode=rc, stdout=out, stderr="")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture")
    monkeypatch.setattr(periodic.subprocess, "run", run)
    return root, plugin, tmp_path / "results", settings, calls


def execute(mutation):
    root, plugin, output, settings, calls = mutation
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    result = periodic.run(root, output)
    assert {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before
    assert result["checkout_unchanged"] is True
    assert result["cleanup"] is True
    assert not Path(result["workspace"]).exists()
    assert json.loads((output / "report.json").read_text()) == result
    return result


def test_disposable_contract_retains_results_without_changing_checkout(mutation):
    result = execute(mutation)
    assert result["status"] == "ok"
    assert (result["selected"], result["executed"], result["tests_run"]) == (2, 2, 3)
    assert result["source_revision"] == "a" * 40 and result["seed"] == "mae232"
    assert result["killed"] == 2 and result["survived"] == 0 and not result["failures"]
    for name in ("mutants.db", "baseline.log", "mutation.log"):
        assert (mutation[2] / name).is_file()


@pytest.mark.parametrize("change", [
    {"selected": 0, "rows": 0}, {"rows": 0}, {"rows": 1}, {"rc": 1}, {"restore": False},
    {"baseline": "3 skipped in 0.1s"}, {"baseline": "unknown counts"},
    {"baseline_rc": 1}, {"dependency_rc": 1}, {"timeout": True},
    {"row_rc": 5}, {"row_rc": -9}, {"killed": None}, {"killed": 0, "row_rc": 1}, {"killed": 0, "row_rc": 2}, {"row_rc": 3},
    {"clone_rc": 1}, {"revision_rc": 1}, {"revision": "unknown"},
    {"mutation_output": "unknown selection"}, {"no_db": True}, {"selected": 51, "rows": 51},
])
def test_empty_skipped_unknown_missing_failed_or_unrestored_is_incomplete(mutation, change):
    mutation[3].update(change)
    result = execute(mutation)
    assert result["status"] == "incomplete" and result["failures"]


def test_xdist_stop_after_first_failure_counts_as_killed(mutation):
    mutation[3].update(row_rc=2)
    result = execute(mutation)
    assert result["status"] == "ok" and result["killed"] == 2


def test_survivors_are_measurements_not_runner_failures(mutation):
    mutation[3].update(row_rc=0, killed=0)
    result = execute(mutation)
    assert result["status"] == "ok" and result["survived"] == 2


def test_cleanup_failure_is_incomplete(mutation, monkeypatch):
    remove = periodic.shutil.rmtree
    monkeypatch.setattr(periodic.shutil, "rmtree", lambda path: None)
    result = periodic.run(mutation[0], mutation[2])
    assert result["status"] == "incomplete" and result["cleanup"] is False
    remove(result["workspace"])


def test_cleanup_exception_and_stale_artifacts_are_not_success(mutation, monkeypatch):
    output = mutation[2]
    output.mkdir()
    for name in ("mutants.db", "baseline.log", "mutation.log"):
        (output / name).write_text("stale")
    mutation[3]["dependency_rc"] = 1
    remove = periodic.shutil.rmtree

    def refuse(path):
        raise OSError("cleanup fixture")

    monkeypatch.setattr(periodic.shutil, "rmtree", refuse)
    result = periodic.run(mutation[0], output)
    assert result["status"] == "incomplete" and result["cleanup"] is False
    assert not (output / "mutants.db").exists()
    remove(result["workspace"])


def test_wrapper_cli_exit_status_and_unsafe_output(mutation, monkeypatch):
    with pytest.raises(ValueError):
        periodic.run(mutation[0], mutation[1] / "results")
    for status, rc in (("ok", 0), ("incomplete", 1)):
        monkeypatch.setattr(periodic, "run", lambda *args: {"status": status})
        assert periodic.main(["--root", str(mutation[0]), "--output", str(mutation[2])]) == rc


def test_checkout_change_is_detected(mutation, monkeypatch):
    fingerprint = periodic.fingerprint
    reads = 0

    def changed(path):
        nonlocal reads
        value = fingerprint(path)
        if path == mutation[1]:
            reads += 1
            if reads > 1:
                return "changed"
        return value

    monkeypatch.setattr(periodic, "fingerprint", changed)
    result = periodic.run(mutation[0], mutation[2])
    assert result["checkout_unchanged"] is False and result["status"] == "incomplete"


def pending():
    return {"version": 1, "state": "pending", "judgment": "pending", "decision": "D-14 Later small PR",
            "window_start": "2026-11-08T00:00:00Z", "window_end": "2026-11-22T00:00:00Z",
            "window_start_source": "first plugin-suites run", "earliest_judgment": "2026-11-21",
            "follow_up": {"pr": "S7 CI aggregate read", "earliest": "2026-11-21",
                          "scope": "Exact-head gate aggregate before receipt reservation after user judgment"},
            "runs": [], "note": "Lead fills observations from gh run list; no enforcement judgment yet."}


def observed(run_id=1, attempt=1, outcome="success", lane="gate"):
    return {"run_id": run_id, "attempt": attempt, "event": "push" if lane == "gate" else "workflow_dispatch", "head_sha": "a" * 40,
            "check_name": "Plugin suites (informational: ship does not read it)" if lane == "gate"
                          else "Plugin periodic (informational: separate from gate)",
            "lane": lane, "outcome": outcome,
            "suite_counts": {"total": 1, "ok": int(outcome == "success"), "failed": int(outcome != "success"),
                             "skipped": 0, "unavailable": 0, "tests_run": 3},
            "failure_cause": None if outcome == "success" else "test-regression"}


def test_pending_empty_record_reports_no_observations(tmp_path):
    report = pending()
    assert observation.validate(report)["attempts"] == 0
    path = tmp_path / "observation.json"
    path.write_text(json.dumps(report))
    p = subprocess.run([sys.executable, str(REPO / "tools/testperf/ci_observation.py"), "--report", str(path)],
                       capture_output=True, text=True)
    assert p.returncode == 0 and p.stdout.strip() == "pending, no observations"


def test_counts_runs_attempts_causes_and_same_head_reruns_without_erasing_failure():
    report = pending()
    report["runs"] = [observed(outcome="failure"), observed(attempt=2), observed(run_id=2, lane="periodic")]
    original = copy.deepcopy(report)
    summary = observation.validate(report)
    assert summary["runs"] == 2 and summary["attempts"] == 3
    assert summary["failures_by_cause"] == {"test-regression": 1}
    assert summary["flaky_same_head_reruns"] == 1 and summary["unresolved_failures"] == 0
    assert summary["gate_attempts"] == 2 and summary["periodic_attempts"] == 1
    assert report == original and summary["state"] == "pending"
    report["runs"] = [observed(outcome="failure"), observed(run_id=2, lane="periodic")]
    assert observation.validate(report)["unresolved_failures"] == 1


@pytest.mark.parametrize("field,value", [
    ("state", "stable"), ("state", "required"), ("judgment", "approved"), ("decision", "Wait"),
    ("earliest_judgment", "2026-11-20"), ("window_end", "2026-11-21T00:00:00Z"),
    ("window_start", "unknown"), ("runs", None), ("unexpected", True), ("note", ""),
])
def test_deferral_rejects_unknown_or_early_approval(field, value):
    report = pending()
    report[field] = value
    with pytest.raises(ValueError):
        observation.validate(report)


@pytest.mark.parametrize("field,value", [
    ("run_id", None), ("attempt", 0), ("attempt", True), ("event", "unknown"),
    ("head_sha", "stale"), ("check_name", "plugin-suites"), ("lane", "unknown"),
    ("outcome", "unknown"), ("failure_cause", "unknown"), ("suite_counts", {}),
])
def test_observation_unknown_fields_fail(field, value):
    report = pending()
    entry = observed()
    entry[field] = value
    report["runs"] = [entry]
    with pytest.raises(ValueError):
        observation.validate(report)


def test_incomplete_attempt_history_invalid_counts_and_deferral_fail():
    for edit in (lambda r: r["runs"].append(observed(attempt=2)),
                 lambda r: r["runs"].extend([observed(), observed()]),
                 lambda r: r["runs"].append({**observed(), "suite_counts": {**observed()["suite_counts"], "tests_run": 0}}),
                 lambda r: r["follow_up"].update(earliest="2026-11-20"),
                 lambda r: r["follow_up"].update(scope="")):
        report = pending()
        edit(report)
        with pytest.raises(ValueError):
            observation.validate(report)


def test_seed_record_is_pending_and_defers_enforcement():
    report = json.loads((REPO / "docs/design/MAE-323-b3-ci-observation.json").read_text())
    assert observation.validate(report)["state"] == "pending"
    assert report["runs"] == [] and "gh run list" in report["note"]
