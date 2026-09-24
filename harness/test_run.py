"""Isolated CLI/ledger regression tests, not claims of live agent execution."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from ledger import LedgerError, plain_summary, sha
from run import execute
from install import FILES, install


class ProjectRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / "문서 project"
        self.project.mkdir()
        self.skill = self.root / "specialist" / "SKILL.md"
        self.skill.parent.mkdir()
        self.skill.write_text("Use only supplied meeting facts.\n")
        self.request = {"task_id": "same-id", "owner": "fixture-coordinator", "kind": "doc",
                        "description": "Summarize supplied notes", "acceptance": ["Grounded actions"],
                        "authorization_scope": ["isolated temporary project"],
                        "publication_required": False, "skill_paths": [str(self.skill)],
                        "closeout": {"mode": "local-only", "reason": "isolated local fixture"}}

    def call(self, action, **extra):
        data = {"task_id": "same-id", **extra}
        if action != "status":
            data.setdefault("owner", "fixture-coordinator")
        return execute(self.project, action, data)

    def ready(self, complete=True, artifact="summary.md"):
        execute(self.project, "start", self.request)
        (self.project / artifact).write_text("A grounded action\n")
        (self.project / "check.txt").write_text("fixture check passed\n")
        (self.project / "review.txt").write_text("fixture independent review\n")
        digest = self.call("artifact", path=artifact, worker_id="fixture-worker")["artifact"]["sha256"]
        self.call("check", artifact_sha256=digest, evidence_path="check.txt", check_id="fixture",
                  agent_id="fixture-worker", exit_code=0)
        self.call("review", artifact_sha256=digest, evidence_path="review.txt",
                  agent_id="fixture-reviewer", verdict="approved", covered_conditions=[0])
        return self.call("complete") if complete else self.call("status")

    def test_managed_closeout_requires_separate_notion_body_readback(self):
        self.request["closeout"] = {"mode": "managed", "github_paths": []}
        state = self.ready(complete=False, artifact="report.md")
        self.assertEqual("awaiting-closeout", state["stage"])
        with self.assertRaisesRegex(LedgerError, "closeout evidence"):
            self.call("complete")
        (self.project / "summary.md").write_text("Decision\n\nNext action\n")
        (self.project / "notion.md").write_text("Decision\nNext action\n")
        fields = {"service": "notion", "target": "https://app.notion.com/p/12345678901234567890123456789012",
                  "summary_path": "summary.md", "readback_path": "notion.md", "receipt_ref": "host:page-fetch"}
        self.call("closeout", **fields)
        self.assertEqual("done", self.call("complete")["stage"])
        self.assertEqual(state["artifact"]["sha256"], self.call("status")["closeouts"]["notion"]["artifact_sha256"])
        (self.project / "notion.md").write_text("Different body\n")
        self.assertEqual("awaiting-closeout", self.call("status")["stage"])
        with self.assertRaisesRegex(LedgerError, "mismatch"):
            self.call("closeout", **fields)
        (self.project / "notion.md").write_text("Decision\nNext action\n")
        self.call("closeout", **fields)
        self.assertEqual("done", self.call("complete")["stage"])

    def test_github_exact_revision_paths_and_drift(self):
        self.request["closeout"] = {"mode": "managed", "github_paths": ["managed/SKILL.md"]}
        self.request["kind"] = "code"
        source = self.project / "managed/SKILL.md"
        source.parent.mkdir()
        source.write_text("Executable rule v1\n")
        checked = self.ready(complete=False, artifact="report.md")
        self.assertEqual(checked["check"]["sources"], checked["review"]["sources"])
        self.assertEqual(sha(source.read_bytes()), checked["review"]["sources"]["managed/SKILL.md"]["sha256"])
        (self.project / "summary.md").write_text("Decision\n")
        (self.project / "notion.md").write_text("Decision\n")
        self.call("closeout", service="notion", target="https://www.notion.so/fixture-12345678901234567890123456789012",
                  summary_path="summary.md", readback_path="notion.md", receipt_ref="host:page-fetch")
        self.assertEqual("awaiting-closeout", self.call("status")["stage"])
        (self.project / "github-readback.md").write_bytes(source.read_bytes())
        fields = {"service": "github", "repository": "example/private", "commit": "a" * 40,
                  "files": [{"path": "managed/SKILL.md", "readback_path": "github-readback.md"}],
                  "receipt_ref": "host:commit-fetch"}
        with self.assertRaisesRegex(LedgerError, "declared paths"):
            self.call("closeout", **{**fields, "files": []})
        with self.assertRaisesRegex(LedgerError, "Git commit"):
            self.call("closeout", **{**fields, "commit": "main"})
        (self.project / "github-readback.md").write_text("wrong bytes\n")
        with self.assertRaisesRegex(LedgerError, "mismatch"):
            self.call("closeout", **fields)
        (self.project / "github-readback.md").write_bytes(source.read_bytes())
        result = self.call("closeout", **fields)
        self.assertIn("/blob/" + "a" * 40 + "/managed/SKILL.md", result["closeouts"]["github"]["files"][0]["url"])
        self.assertEqual("done", self.call("complete")["stage"])
        source.write_text("Executable rule v2\n")
        stale = self.call("status")
        self.assertEqual("repair-required", stale["stage"])
        self.assertIsNone(stale["check"])
        self.assertIsNone(stale["review"])
        self.assertEqual({}, stale["closeouts"])
        (self.project / "github-readback.md").write_bytes(source.read_bytes())
        with self.assertRaisesRegex(LedgerError, "independently reviewed"):
            self.call("closeout", **{**fields, "commit": "b" * 40})
        with self.assertRaisesRegex(LedgerError, "independently reviewed"):
            self.call("complete")
        self.call("repair", reason_ref="fixture:source-change")
        digest = self.call("artifact", path="report.md", worker_id="fixture-worker")["artifact"]["sha256"]
        self.call("check", artifact_sha256=digest, evidence_path="check.txt", check_id="fixture-rerun",
                  agent_id="fixture-worker", exit_code=0)
        self.call("review", artifact_sha256=digest, evidence_path="review.txt",
                  agent_id="fixture-reviewer", verdict="approved", covered_conditions=[0])
        self.call("closeout", service="notion", target="https://www.notion.so/fixture-12345678901234567890123456789012",
                  summary_path="summary.md", readback_path="notion.md", receipt_ref="host:page-refetch")
        self.call("closeout", **{**fields, "commit": "b" * 40})
        self.assertEqual("done", self.call("complete")["stage"])

    def test_managed_code_requires_paths_or_explicit_exception(self):
        self.request["kind"] = "code"
        for policy in (None, {"mode": "managed", "github_paths": []}):
            request = {k: v for k, v in self.request.items() if k != "closeout"}
            if policy is not None:
                request["closeout"] = policy
            with self.subTest(policy=policy), self.assertRaisesRegex(LedgerError, "managed code requires"):
                execute(self.project, "start", request)
        self.assertEqual("done", self.ready()["stage"])

    def test_postreview_source_change_before_first_closeout_requires_repair(self):
        self.request["kind"] = "code"
        self.request["closeout"] = {"mode": "managed", "github_paths": ["source.py"]}
        source = self.project / "source.py"
        source.write_text("old checked code\n")
        checked = self.ready(complete=False, artifact="report.md")
        source.write_text("unreviewed replacement code\n")
        (self.project / "remote.py").write_bytes(source.read_bytes())
        with self.assertRaisesRegex(LedgerError, "independently reviewed"):
            self.call("closeout", service="github", repository="example/private", commit="a" * 40,
                      files=[{"path": "source.py", "readback_path": "remote.py"}], receipt_ref="host:fetch")
        with self.assertRaisesRegex(LedgerError, "repair required"):
            self.call("check", artifact_sha256=checked["artifact"]["sha256"], evidence_path="check.txt",
                      check_id="fixture", agent_id="fixture-worker", exit_code=0)
        self.assertEqual("repair-required", self.call("status")["stage"])

    def test_source_change_between_check_and_review_requires_repair(self):
        self.request["closeout"] = {"mode": "managed", "github_paths": ["source.py"]}
        source = self.project / "source.py"
        source.write_text("checked source\n")
        execute(self.project, "start", self.request)
        for name in ("report.md", "check.txt", "review.txt"):
            (self.project / name).write_text("fixture evidence\n")
        digest = self.call("artifact", path="report.md", worker_id="fixture-worker")["artifact"]["sha256"]
        self.call("check", artifact_sha256=digest, evidence_path="check.txt", check_id="fixture",
                  agent_id="fixture-worker", exit_code=0)
        source.write_text("changed after check\n")
        with self.assertRaisesRegex(LedgerError, "mechanical check"):
            self.call("review", artifact_sha256=digest, evidence_path="review.txt",
                      agent_id="fixture-reviewer", verdict="approved", covered_conditions=[0])
        self.assertEqual("repair-required", self.call("status")["stage"])

    def test_runner_default_and_legacy_ledger_policy(self):
        request = {key: value for key, value in self.request.items() if key != "closeout"}
        state = execute(self.project, "start", request)
        self.assertEqual({"mode": "managed", "github_paths": []}, state["request"]["closeout"])
        with self.assertRaisesRegex(LedgerError, "different request"):
            execute(self.project, "start", {**request,
                    "closeout": {"mode": "managed", "github_paths": ["managed/SKILL.md"]}})

    def test_read_only_exception_requires_reason(self):
        self.request["closeout"] = {"mode": "read-only", "reason": "source inspection only"}
        self.assertEqual("done", self.ready()["stage"])
        other = {**self.request, "task_id": "missing-reason", "closeout": {"mode": "local-only"}}
        with self.assertRaisesRegex(LedgerError, "exception"):
            execute(self.project, "start", other)

    def test_summary_normalization_preserves_code_and_math_blank_lines(self):
        self.assertEqual(plain_summary(b"First\n\nSecond\n"), plain_summary(b"First\nSecond\n"))
        self.assertNotEqual(plain_summary(b"```python\na\n\nb\n```\n"),
                            plain_summary(b"```python\na\nb\n```\n"))
        self.assertNotEqual(plain_summary(b"$$\na\n\nb\n$$\n"),
                            plain_summary(b"$$\na\nb\n$$\n"))

    def test_projects_are_isolated_and_start_is_idempotent(self):
        first = execute(self.project, "start", self.request)
        again = execute(self.project, "start", self.request)
        other = self.root / "code project"
        other.mkdir()
        second = execute(other, "start", {**self.request, "description": "Another task"})
        self.assertEqual(first["run_id"], again["run_id"])
        self.assertNotEqual(first["database"], second["database"])
        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertEqual("*\n", (self.project / ".harness/.gitignore").read_text())

    def test_local_skill_text_is_frozen_without_fabricated_provenance(self):
        result = execute(self.project, "start", self.request)
        pin = result["context"]["skills"][1]
        self.assertEqual("local", pin["source"])
        self.assertNotIn("repository", pin)
        self.assertEqual(sha(self.skill.read_bytes()), pin["sha256"])
        self.skill.write_text("A later revision\n")
        self.assertEqual(pin, self.call("context")["context"]["skills"][1])
        with self.assertRaisesRegex(LedgerError, "frozen"):
            execute(self.project, "start", self.request)

    def test_user_and_project_relative_skill_paths(self):
        expanduser = Path.expanduser
        with patch.object(Path, "expanduser", lambda path:
                          self.root / str(path)[2:] if str(path).startswith("~/") else expanduser(path)):
            result = execute(self.project, "start", {**self.request,
                             "skill_paths": ["~/specialist/SKILL.md"]})
        self.assertEqual(str(self.skill), result["skills"][1]["path"])
        result = execute(self.project, "start", {**self.request, "task_id": "relative-skill",
                         "skill_paths": ["../specialist/SKILL.md"]})
        self.assertEqual(str(self.skill), result["skills"][1]["path"])
        relative = [{**pin, "path": "../specialist/SKILL.md"} if pin["name"] == "specialist"
                    else pin for pin in result["skills"]]
        repeated = execute(self.project, "route", {"task_id": "relative-skill",
                           "owner": self.request["owner"], "skills": relative})
        self.assertEqual(result["skills"], repeated["skills"])

    def test_resume_does_not_repeat_completed_work_and_tamper_invalidates(self):
        ready = self.ready()
        before = (self.project / "summary.md").stat().st_mtime_ns
        self.call("pause")
        resumed = self.call("resume", owner="fixture-new-coordinator")
        self.assertEqual("done", resumed["stage"])
        self.assertEqual(ready["artifact"], resumed["artifact"])
        self.assertEqual(before, (self.project / "summary.md").stat().st_mtime_ns)
        (self.project / "summary.md").write_text("Changed after review\n")
        stale = self.call("status")
        self.assertEqual("repair-required", stale["stage"])
        self.assertIsNone(stale["review"])
        self.assertEqual("repair", stale["next_action"])

    def test_project_escape_symlink_and_self_review_are_rejected(self):
        execute(self.project, "start", self.request)
        outside = self.root / "outside.md"
        outside.write_text("user content")
        (self.project / "linked.md").symlink_to(outside)
        for path in ("../outside.md", "linked.md", str(outside)):
            with self.subTest(path=path), self.assertRaisesRegex(LedgerError, "escapes"):
                self.call("artifact", path=path, worker_id="fixture-worker")
        self.ready()
        state = self.call("status")
        with self.assertRaisesRegex(LedgerError, "independent"):
            self.call("review", artifact_sha256=state["artifact"]["sha256"], evidence_path="review.txt",
                      agent_id="fixture-worker", verdict="approved", covered_conditions=[0])
        other = self.root / "symlink project"
        other.mkdir()
        (other / ".harness").symlink_to(self.project / ".harness", target_is_directory=True)
        with self.assertRaisesRegex(LedgerError, "symlink"):
            execute(other, "doctor", None)

    def test_cli_from_another_cwd_and_read_only_discovery(self):
        cli = str(Path(__file__).with_name("run.py"))
        cmd = [sys.executable, "-B", cli, "--project", str(self.project)]
        doctor = subprocess.run([*cmd, "doctor"], cwd=self.root, capture_output=True, text=True, check=True)
        self.assertFalse(json.loads(doctor.stdout)["ledger_exists"])
        self.assertFalse((self.project / ".harness").exists())
        started = subprocess.run([*cmd, "start"], input=json.dumps(self.request), cwd=self.root,
                                 capture_output=True, text=True, check=True)
        self.assertEqual("working", json.loads(started.stdout)["stage"])
        listing = subprocess.run([*cmd, "list"], cwd=self.root, capture_output=True, text=True, check=True)
        self.assertEqual("same-id", json.loads(listing.stdout)["tasks"][0]["task_id"])

    def test_internal_artifact_and_evidence_aliases_are_rejected(self):
        ready = self.ready()
        link = self.project / "deliverable.md"
        link.symlink_to(self.project / "summary.md")
        with self.assertRaisesRegex(LedgerError, "symlink"):
            self.call("artifact", path="deliverable.md", worker_id="fixture-worker")
        link.unlink()
        link.symlink_to(self.project / "check.txt")
        with self.assertRaisesRegex(LedgerError, "symlink"):
            self.call("check", artifact_sha256=ready["artifact"]["sha256"],
                      evidence_path="deliverable.md", check_id="fixture",
                      agent_id="fixture-worker", exit_code=0)
        self.assertEqual("done", self.call("status")["stage"])

    def test_symlink_cannot_be_hidden_by_parent_traversal(self):
        execute(self.project, "start", self.request)
        (self.project / "first").mkdir()
        (self.project / "nested/second").mkdir(parents=True)
        (self.project / "output.md").write_text("reviewable output")
        (self.project / "nested/output.md").write_text("unreviewed output")
        alias = self.project / "alias"
        alias.symlink_to(self.project / "first", target_is_directory=True)
        for target in ("first", "nested/second"):
            alias.unlink()
            alias.symlink_to(self.project / target, target_is_directory=True)
            with self.subTest(target=target), self.assertRaisesRegex(LedgerError, "symlink"):
                self.call("artifact", path="alias/../output.md", worker_id="fixture-worker")
        self.assertIsNone(self.call("status")["artifact"])
        regular = self.call("artifact", path="first/../output.md", worker_id="fixture-worker")
        self.assertEqual(str(self.project / "output.md"), regular["artifact"]["path"])

    def test_real_installed_runtime_survives_removed_source_and_checks_manifest(self):
        repository = Path(__file__).resolve().parents[1]
        source = self.root / "temporary checkout"
        for relative in FILES.values():
            destination = source / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repository / relative, destination)
        home = self.root / "temporary user"
        release = install(source, home)
        shutil.rmtree(source)
        cmd = [sys.executable, "-B", str(home / ".agents/skills/harness-run/scripts/run.py"),
               "--project", str(self.project)]
        result = subprocess.run([*cmd, "start"], input=json.dumps(self.request), cwd=self.root,
                                capture_output=True, text=True, check=True)
        self.assertEqual("user", json.loads(result.stdout)["installation"])
        self.assertEqual("working", json.loads(result.stdout)["stage"])
        manifest = release / "manifest.json"
        original = manifest.read_bytes()
        manifest.write_text('{"files": {}, "release_id": "invalid"}')
        bad = subprocess.run([*cmd, "doctor"], capture_output=True, text=True)
        self.assertEqual(2, bad.returncode)
        self.assertIn("invalid install manifest", bad.stderr)
        manifest.write_bytes(original)
        (release / "references/README.md").write_text("Unexpected local edit")
        bad = subprocess.run([*cmd, "doctor"], capture_output=True, text=True)
        self.assertEqual(2, bad.returncode)
        self.assertIn("installed files changed", bad.stderr)


if __name__ == "__main__":
    unittest.main()
