"""Hosting CLI observations and out-of-hook compatibility verification (AC-2)."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from .helpers import HarnessCase, ROOT
from maeng import handlers, state

REPO = ROOT.parents[1]


class SessionCli(HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.plugin = self.tmp / "plugin"
        (self.plugin / "policy").mkdir(parents=True)
        (self.plugin / ".claude-plugin").mkdir()
        (self.plugin / ".claude-plugin/plugin.json").write_text('{"version": "test"}')
        self.policy = self.plugin / "policy/cli-compatibility.json"
        self.policy.write_text(json.dumps({"verified": {"cli_version": "2.1.314"}}))
        patcher = mock.patch.object(handlers, "PLUGIN_ROOT", self.plugin)
        patcher.start()
        self.addCleanup(patcher.stop)

    def host(self, version="9.9.9"):
        exe = self.tmp / "embedded-claude"
        exe.write_text(f"#!{sys.executable}\nprint({(version + ' (Claude Code)')!r})\n")
        exe.chmod(0o755)
        self.env["CLAUDE_CODE_EXECPATH"] = str(exe)
        return exe

    def start_cli(self, **fields):
        rc, out, err = self.hook("SessionStart", self.repo, source="resume", **fields)
        self.assertEqual(rc, 0, err)
        self.assertEqual(err, "")
        return out, self.load_state()["cli_compatibility"]

    def test_matching_host_records_observation_without_notice_or_pending(self):
        self.host("2.1.314")
        out, observed = self.start_cli()
        self.assertNotIn("systemMessage", out)
        self.assertEqual(observed["observed_version"], "2.1.314")
        self.assertFalse(observed["pending"])

    def test_mismatch_notifies_once_per_session_version_and_keeps_pending(self):
        exe = self.host()
        out, observed = self.start_cli()
        self.assertEqual(len(out["systemMessage"].splitlines()), 1)
        self.assertIn("9.9.9", out["systemMessage"])
        self.assertTrue(observed["pending"])
        self.assertEqual(observed["source"], "CLAUDE_CODE_EXECPATH --version")
        self.assertEqual(observed["executable"], str(exe))
        self.assertTrue(observed["observed_at"])
        self.assertNotIn("systemMessage", self.start_cli()[0])
        self.host("9.9.8")
        self.assertIn("systemMessage", self.start_cli()[0])
        self.host()
        self.assertNotIn("systemMessage", self.start_cli()[0])
        self.sid += "-other"
        self.assertIn("systemMessage", self.start_cli()[0])

    def test_missing_host_never_uses_path_payload_or_old_transcript_version(self):
        self.env["CLAUDE_CODE_VERSION"] = "2.1.314"
        transcript = self.tmp / "session.jsonl"
        transcript.write_text(json.dumps({"sessionId": self.sid, "version": "2.1.314"}) + "\n")
        with mock.patch.object(handlers.subprocess, "run", wraps=subprocess.run) as run:
            out, observed = self.start_cli(version="2.1.314", transcript_path=str(transcript))
        self.assertFalse(any(c.args[0][-1:] == ["--version"] for c in run.call_args_list))
        self.assertIn("version unknown", out["systemMessage"])
        self.assertIsNone(observed["observed_version"])
        self.assertTrue(observed["pending"])
        self.assertNotIn("systemMessage", self.start_cli()[0])

    def test_relative_executable_is_unknown(self):
        self.env["CLAUDE_CODE_EXECPATH"] = "claude"
        self.assertIsNone(self.start_cli()[1]["observed_version"])

    def test_failed_or_malformed_host_probe_is_unknown(self):
        self.host()
        real_run = subprocess.run
        for result in (subprocess.CompletedProcess([], 1, "9.9.9 (Claude Code)\n", ""),
                       subprocess.CompletedProcess([], 0, "not a Claude version\n", ""),
                       OSError("unavailable"), subprocess.TimeoutExpired([], 1)):
            def probe(cmd, **kw):
                if cmd[-1:] == ["--version"]:
                    self.assertLessEqual(kw["timeout"], 1)
                    if isinstance(result, Exception):
                        raise result
                    return result
                return real_run(cmd, **kw)
            with self.subTest(result=result), mock.patch.object(handlers.subprocess, "run", side_effect=probe):
                observed = self.start_cli()[1]
                self.assertIsNone(observed["observed_version"])
                self.assertTrue(observed["pending"])

    def test_absent_or_corrupt_policy_is_unverified(self):
        self.host()
        for content in (None, "{", "[]"):
            if content is None:
                self.policy.unlink()
            else:
                self.policy.write_text(content)
            out, observed = self.start_cli()
            self.assertTrue(observed["pending"])
            self.assertIsNone(observed["verified_version"])

    def test_process_hook_records_embedded_host_without_running_tests(self):
        self.PROCESS = True
        self.host()
        out, observed = self.start_cli()
        self.assertEqual(observed["observed_version"], "9.9.9")
        self.assertTrue(observed["pending"])
        self.assertEqual(len(out["systemMessage"].splitlines()), 1)


@pytest.fixture
def runner(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("cli_compat", REPO / "tools/testperf/cli_compat.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setenv("MAENG_HOME", str(tmp_path / "home"))
    mod.REPO = tmp_path
    mod.PLUGIN = tmp_path / "plugins/maeng-harness"
    mod.POLICY = mod.PLUGIN / "policy/cli-compatibility.json"
    mod.POLICY.parent.mkdir(parents=True)
    mod.POLICY.write_text(json.dumps({"verified": {"cli_version": "2.1.314"}}))
    (mod.PLUGIN / "source.py").write_text("# checked source\n")
    observation = {"observed_version": "9.9.9", "verified_version": "2.1.314", "pending": True,
                   "source": "CLAUDE_CODE_EXECPATH --version", "executable": "/embedded/claude",
                   "observed_at": "2026-11-08T10:00:00+0000", "notified_versions": ["9.9.9"]}
    state.update("s2", lambda s: s.update(cli_compatibility=observation))
    return mod


def test_verify_runs_smoke_then_full_and_binds_evidence(runner, monkeypatch):
    calls = []
    def run(command, **kw):
        calls.append(command)
        assert kw["cwd"] == runner.REPO
        assert kw["env"]["PYTEST_ADDOPTS"] == ""
        assert state.load("s2")["cli_compatibility"]["pending"]
        return subprocess.CompletedProcess(command, 0, "7 passed, 2 skipped in 0.1s\n", "")
    monkeypatch.setattr(runner.subprocess, "run", run)
    assert runner.main(["verify", "--session", "s2"]) == 0
    assert calls == [runner.SMOKE, runner.FULL]
    assert calls[0] == ["python3", "-m", "pytest", "-q", "plugins/maeng-harness/tests/test_boundary.py"]
    assert calls[1] == ["python3", "-m", "pytest", "-q", "-n", "8"]
    verified = json.loads(runner.POLICY.read_text())["verified"]
    assert verified["cli_version"] == "9.9.9"
    assert verified["observed_at"] == state.load("s2")["cli_compatibility"]["observed_at"]
    assert verified["source"] == "CLAUDE_CODE_EXECPATH --version"
    assert verified["plugin_revision"] == runner.plugin_revision()
    assert verified["checked_at"]
    assert set(verified["checks"]) == {"hook_smoke", "full_suite"}
    assert all(r["tests_run"] == 7 and r["returncode"] == 0 for r in verified["checks"].values())
    assert not state.load("s2")["cli_compatibility"]["pending"]


@pytest.mark.parametrize("stage", [0, 1], ids=["smoke", "full"])
@pytest.mark.parametrize("result", [
    subprocess.CompletedProcess([], 1, "1 failed in 0.1s", ""),
    subprocess.CompletedProcess([], 0, "4 skipped in 0.1s", ""),
    subprocess.CompletedProcess([], 0, "no tests ran in 0.1s", ""),
    subprocess.CompletedProcess([], 0, "ok", ""),
    OSError("runner unavailable"), subprocess.TimeoutExpired([], 900),
], ids=["failed", "all-skipped", "zero", "unknown-count", "missing-runner", "timeout"])
def test_failed_checks_preserve_verified_bytes_and_pending(runner, monkeypatch, stage, result):
    before = runner.POLICY.read_bytes()
    calls = []
    def run(command, **kw):
        calls.append(command)
        r = result if len(calls) == stage + 1 else subprocess.CompletedProcess(command, 0, "3 passed in 0.1s", "")
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(runner.subprocess, "run", run)
    assert runner.main(["verify", "--session", "s2"]) == 1
    assert len(calls) == stage + 1
    assert runner.POLICY.read_bytes() == before
    assert state.load("s2")["cli_compatibility"]["pending"]


@pytest.mark.parametrize("observation", [None, {"observed_version": None},
    {"observed_version": "unknown"}, {"observed_version": "2.1.314", "source": "PATH"}])
def test_unknown_or_unbound_host_cannot_start_verification(runner, monkeypatch, observation):
    state.update("s2", lambda s: s.update(cli_compatibility=observation))
    before = runner.POLICY.read_bytes()
    with mock.patch.object(runner.subprocess, "run") as run:
        assert runner.main(["verify", "--session", "s2"]) == 1
        run.assert_not_called()
    assert runner.POLICY.read_bytes() == before


@pytest.mark.parametrize("changed", ["source", "session"])
def test_changed_inputs_cannot_publish_success(runner, monkeypatch, changed):
    before = runner.POLICY.read_bytes()
    def run(command, **kw):
        if command == runner.FULL:
            if changed == "source":
                (runner.PLUGIN / "source.py").write_text("# changed while testing\n")
            else:
                state.update("s2", lambda s: s["cli_compatibility"].update(observed_version="9.9.8"))
        return subprocess.CompletedProcess(command, 0, "3 passed in 0.1s", "")
    monkeypatch.setattr(runner.subprocess, "run", run)
    assert runner.main(["verify", "--session", "s2"]) == 1
    assert runner.POLICY.read_bytes() == before
    assert state.load("s2")["cli_compatibility"]["pending"]


def test_missing_session_starts_no_tests(runner):
    with mock.patch.object(runner.subprocess, "run") as run:
        assert runner.main(["verify", "--session", ""]) == 1
        run.assert_not_called()


def test_policy_has_seed_or_successful_check_evidence():
    record = json.loads((ROOT / "policy/cli-compatibility.json").read_text())
    verified = record["verified"]
    if verified["checks"] is None:
        assert verified["cli_version"] == "2.1.314"
        evidence = REPO / verified["seed_evidence"]
        assert json.loads(evidence.read_text())["cli_version"] == "2.1.314"
    else:
        assert verified["plugin_revision"] and verified["checked_at"]
        assert set(verified["checks"]) == {"hook_smoke", "full_suite"}
        assert all(c["tests_run"] > 0 and c["returncode"] == 0 for c in verified["checks"].values())
