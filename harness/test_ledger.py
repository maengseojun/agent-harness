"""Isolated local ledger tests; fixtures do not claim native-agent/remote execution."""

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from ledger import Ledger, LedgerError, sha


CLI = str(Path(__file__).with_name("ledger.py").resolve())


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="harness-ledger-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.db = self.root / "state.sqlite"
        self.ledger = Ledger(self.db)
        self.owner = "coordinator"
        self.artifact = self.write("artifact.txt", "version one\n")
        self.check_file = self.write("check.txt", "isolated mechanical check fixture\n")
        self.review_file = self.write("review.txt", "isolated independent review fixture\n")
        self.skill = self.write("SKILL.md", "---\nname: fixture\n---\nRead the bounded request.\n")
        self.pin = {"name": "fixture", "path": str(self.skill), "sha256": sha(self.skill.read_bytes()),
                    "repository": "example/skills", "commit": "a" * 40,
                    "source_path": "skills/fixture/SKILL.md",
                    "url": "https://github.com/example/skills/blob/" + "a" * 40 + "/skills/fixture/SKILL.md"}

    def write(self, name, value):
        path = self.root / name
        path.write_text(value, encoding="utf-8")
        return path

    def data(self, action, **extra):
        data = {"task_id": "pilot", **extra}
        if action not in {"create", "status"}:
            data.setdefault("owner", self.owner)
        return data

    def call(self, action, **extra):
        return self.ledger.dispatch(action, self.data(action, **extra))

    def cli(self, action, *, env=None, **extra):
        return subprocess.run([sys.executable, "-B", CLI, "--db", str(self.db), action],
                              input=json.dumps(self.data(action, **extra)), text=True,
                              capture_output=True, timeout=15, env=env)

    def create(self, required=True):
        return self.call("create", kind="doc", description="Bounded local test request",
                         acceptance=["Content matches the bounded request"],
                         authorization_scope=["local temporary directory only"],
                         publication_required=required, refs=["fixture:request-v1"])

    def start(self, required=True):
        self.create(required)
        self.call("claim")
        routed = self.call("route", skills=[self.pin])
        self.call("configure-hooks", output_owner="personal", destinations=[], write_paths=[], requirements=[])
        return routed

    def record(self):
        return self.call("artifact", path=str(self.artifact), worker_id="worker")["artifact"]["sha256"]

    def check(self, digest, **extra):
        return self.call("check", **{"artifact_sha256": digest, "evidence_path": str(self.check_file),
                                    "check_id": "fixture-unittest", "agent_id": "worker", "exit_code": 0, **extra})

    def review(self, digest, **extra):
        return self.call("review", **{"artifact_sha256": digest, "evidence_path": str(self.review_file),
                                     "agent_id": "verifier", "verdict": "approved", "covered_conditions": [0], **extra})

    def ready(self, required=True):
        self.start(required)
        digest = self.record()
        self.check(digest)
        self.review(digest)
        return digest

    def queue(self, digest, target=None, publication_id="output", adapter="local", approve=True):
        target = target or str(self.root / "published.txt")
        self.call("enqueue", publication_id=publication_id, adapter=adapter,
                  target=target, artifact_sha256=digest)
        if approve:
            self.call("approve", publication_id=publication_id, target=target,
                      artifact_sha256=digest, approved_by="user", approval_ref="approval:fixture")
        return target

    def test_same_request_replay_and_payload_conflict(self):
        original = self.create()
        self.call("claim")
        replay = self.create()
        self.assertEqual(original["run_id"], replay["run_id"])
        self.assertEqual("coordinator", replay["owner"])
        with self.assertRaisesRegex(LedgerError, "different request"):
            self.call("create", **{**original["request"], "description": "Changed request"})
        with sqlite3.connect(self.db) as db:
            self.assertEqual(1, db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0])

    def test_real_file_routing_freezes_text_and_metadata(self):
        routed = self.start()
        self.assertEqual(self.skill.read_text(), routed["context"]["skills"][0]["text"])
        self.assertNotIn("text", routed["skills"][0])
        original = routed["context"]
        self.skill.write_text("later unapproved changes")
        self.assertEqual(original, self.call("context")["context"])
        self.assertEqual(original, self.call("route", skills=[self.pin])["context"])
        changed = {**self.pin, "sha256": sha(self.skill.read_bytes())}
        with self.assertRaisesRegex(LedgerError, "frozen"):
            self.call("route", skills=[changed])

    def test_route_rejects_hash_mutable_ref_and_mismatched_url(self):
        self.create()
        self.call("claim")
        bad_pins = [{**self.pin, "sha256": "0" * 64}, {**self.pin, "commit": "main"},
                    {**self.pin, "repository": "https://other.example/skills"},
                    {**self.pin, "url": self.pin["url"].replace("/blob/", "/tree/")},
                    {**self.pin, "source_path": "../SKILL.md"},
                    {**self.pin, "name": ""}, {**self.pin, "path": "relative.md"}]
        for pin in bad_pins:
            with self.subTest(pin=pin), self.assertRaises(LedgerError):
                self.call("route", skills=[pin])
        self.assertEqual([], self.call("status")["skills"])

    def test_owner_conflict_requires_pause_before_takeover(self):
        self.start()
        original = self.call("status")
        for op in ("claim", "pause", "resume", "context"):
            with self.subTest(op=op), self.assertRaisesRegex(LedgerError, "owner conflict"):
                self.call(op, owner="other")
        self.call("pause")
        with self.assertRaisesRegex(LedgerError, "paused"):
            self.record()
        self.owner = "other"
        resumed = self.call("resume")
        self.assertNotEqual(original["run_id"], resumed["run_id"])
        self.assertEqual(["coordinator", "other"], resumed["owners"])
        self.assertEqual(original["skills"], resumed["skills"])
        with self.assertRaisesRegex(LedgerError, "owner conflict"):
            self.call("pause", owner="coordinator")

    def test_completion_needs_check_independent_review_and_approval(self):
        self.start()
        digest = self.record()
        with self.assertRaises(LedgerError):
            self.call("complete")
        with self.assertRaisesRegex(LedgerError, "mechanical"):
            self.review(digest)
        self.check(digest)
        for identity in ("worker", "coordinator"):
            with self.subTest(identity=identity), self.assertRaisesRegex(LedgerError, "independent"):
                self.review(digest, agent_id=identity)
        with self.assertRaisesRegex(LedgerError, "every acceptance"):
            self.review(digest, covered_conditions=[])
        self.review(digest)
        self.assertEqual("awaiting-approval", self.call("complete")["stage"])
        self.queue(digest, approve=False)
        with self.assertRaisesRegex(LedgerError, "approval required"):
            self.call("publish", publication_id="output")
        self.assertFalse((self.root / "published.txt").exists())
        self.assertEqual("awaiting-approval", self.call("complete")["stage"])

    def test_work_without_publication_can_finish(self):
        self.ready(required=False)
        finished = self.call("complete")
        self.assertEqual("done", finished["stage"])
        self.assertEqual("verified", finished["work_status"])
        self.assertTrue(finished["stages"])

    def test_approval_must_match_target_and_hash(self):
        digest = self.ready()
        target = self.queue(digest, approve=False)
        for wrong_target, wrong_hash in ((target + ".other", digest), (target, "0" * 64)):
            with self.subTest(target=wrong_target), self.assertRaisesRegex(LedgerError, "mismatch"):
                self.call("approve", publication_id="output", target=wrong_target, artifact_sha256=wrong_hash,
                          approved_by="user", approval_ref="approval:fixture")
        state = self.call("status")
        self.assertIsNone(state["publications"][0]["approval"])
        self.assertEqual("awaiting-approval", state["stage"])

    def test_publication_idempotency_and_replay(self):
        digest = self.ready()
        target = self.queue(digest)
        self.queue(digest)
        self.call("enqueue", publication_id="alias", adapter="local", target=target, artifact_sha256=digest)
        self.assertEqual(1, len(self.call("status")["publications"]))
        with self.assertRaisesRegex(LedgerError, "different request"):
            self.call("enqueue", publication_id="output", adapter="local", target=target + ".other", artifact_sha256=digest)
        self.call("publish", publication_id="output")
        inode = Path(target).stat().st_ino
        replay = self.call("publish", publication_id="output")
        self.assertEqual(1, replay["publications"][0]["attempts"])
        self.assertEqual(inode, Path(target).stat().st_ino)
        self.assertEqual("done", self.call("complete")["stage"])

    def test_real_subprocess_crash_after_save_resumes_without_duplication(self):
        digest = self.ready()
        target = self.queue(digest)
        before = self.call("status")
        env = {**os.environ, "HARNESS_LEDGER_TEST_CRASH_ROOT": str(self.root),
               "HARNESS_LEDGER_TEST_CRASH_AFTER_SAVE": "1"}
        crash = self.cli("publish", publication_id="output", env=env)
        self.assertEqual(91, crash.returncode, crash.stderr)
        self.assertEqual(digest, sha(Path(target).read_bytes()))
        inode = Path(target).stat().st_ino
        with sqlite3.connect(self.db) as db:
            saved = json.loads(db.execute("SELECT state FROM outbox").fetchone()[0])
        self.assertEqual("pending", saved["status"])
        self.assertIsNone(saved["receipt"])
        self.assertEqual(1, saved["attempts"])
        self.call("pause")
        self.owner = "recovery-coordinator"
        self.call("resume")
        resumed = self.cli("publish", publication_id="output")
        self.assertEqual(0, resumed.returncode, resumed.stderr)
        after = json.loads(resumed.stdout)
        self.assertEqual("verified", after["publications"][0]["status"])
        self.assertEqual(2, after["publications"][0]["attempts"])
        for field in ("artifact", "artifact_history", "check", "review", "retry_count"):
            self.assertEqual(before[field], after[field], field)
        self.assertEqual(inode, Path(target).stat().st_ino)
        self.assertEqual([], list(self.root.glob(".ledger-*")))
        self.assertEqual("done", self.call("complete")["stage"])

    def test_record_only_retry_preserves_completed_work(self):
        digest = self.ready()
        target = self.queue(digest, target=str(self.root / "missing-dir" / "output.txt"))
        before = self.call("status")
        failed = self.call("publish", publication_id="output")
        self.assertEqual("blocked", failed["stage"])
        self.assertEqual("verified", failed["work_status"])
        self.assertEqual("io", failed["publications"][0]["blocker"]["kind"])
        Path(target).parent.mkdir()
        retried = self.call("publish", publication_id="output")
        self.assertEqual("verified", retried["publications"][0]["status"])
        self.assertEqual(2, retried["publications"][0]["attempts"])
        for field in ("artifact_history", "check", "review", "retry_count", "run_id"):
            self.assertEqual(before[field], retried[field], field)

    def test_user_modified_target_is_never_overwritten(self):
        digest = self.ready()
        target = self.queue(digest)
        Path(target).write_text("user modification")
        inode = Path(target).stat().st_ino
        for _ in range(2):
            blocked = self.call("publish", publication_id="output")
            self.assertEqual("conflict", blocked["publications"][0]["status"])
            self.assertEqual("blocked", self.call("complete")["stage"])
            self.assertEqual("user modification", Path(target).read_text())
            self.assertEqual(inode, Path(target).stat().st_ino)

    def test_target_modified_after_verification_blocks_completion(self):
        digest = self.ready()
        target = self.queue(digest)
        self.call("publish", publication_id="output")
        self.assertEqual("done", self.call("complete")["stage"])
        Path(target).write_text("later user change")
        self.assertEqual("blocked", self.call("status")["stage"])
        self.assertEqual("blocked", self.call("complete")["stage"])
        self.assertEqual("later user change", Path(target).read_text())

    def test_changed_artifact_invalidates_evidence_and_old_publication(self):
        digest = self.ready()
        self.queue(digest)
        self.call("publish", publication_id="output")
        self.call("complete")
        self.artifact.write_text("version two\n")
        invalidated = self.call("status")
        self.assertEqual("repair-required", invalidated["stage"])
        self.assertIsNone(invalidated["check"])
        self.assertIsNone(invalidated["review"])
        self.assertEqual(digest, invalidated["artifact"]["sha256"])
        with self.assertRaises(LedgerError):
            self.call("complete")
        with self.assertRaisesRegex(LedgerError, "bounded repair"):
            self.record()
        self.call("repair", reason_ref="feedback:revision")
        new_hash = self.record()
        self.assertNotEqual(digest, new_hash)
        with self.assertRaisesRegex(LedgerError, "not current"):
            self.check(digest)
        self.check(new_hash)
        self.review(new_hash)
        state = self.call("complete")
        self.assertEqual("superseded", state["publications"][0]["status"])
        self.assertEqual("awaiting-approval", state["stage"])
        with self.assertRaisesRegex(LedgerError, "superseded"):
            self.call("publish", publication_id="output")
        self.queue(new_hash, target=str(self.root / "published-v2.txt"), publication_id="revision")
        self.call("publish", publication_id="revision")
        self.assertEqual("done", self.call("complete")["stage"])

    def test_changed_check_or_review_evidence_invalidates_completion(self):
        self.ready(required=False)
        self.call("complete")
        self.review_file.write_text("altered review")
        with self.assertRaises(LedgerError):
            self.call("complete")
        self.assertIsNone(self.call("status")["review"])
        self.call("repair", reason_ref="feedback:evidence")
        digest = self.record()
        self.check(digest)
        self.review(digest)
        self.check_file.write_text("altered check")
        with self.assertRaises(LedgerError):
            self.call("complete")
        self.assertIsNone(self.call("status")["check"])

    def test_auth_error_is_a_persisted_blocker_not_success(self):
        self.start(required=False)
        digest = self.record()
        blocked = self.check(digest, exit_code=1, failure_kind="auth")
        self.assertEqual("blocked", blocked["stage"])
        self.assertEqual("auth", Ledger(self.db).dispatch("status", {"task_id": "pilot"})["blocker"]["kind"])
        with self.assertRaisesRegex(LedgerError, "blocked"):
            self.call("complete")
        self.call("clear-blocker", resolution_ref="reauth:verified")
        with self.assertRaisesRegex(LedgerError, "repair required"):
            self.check(digest)
        self.call("repair", reason_ref="reauth:retry")
        digest = self.record()
        with self.assertRaisesRegex(LedgerError, "cannot be successes"):
            self.check(digest, failure_kind="access", exit_code=0)

    def test_explicit_access_blocker_survives_pause_and_resume(self):
        self.ready(required=False)
        self.call("block", kind="access", reason_ref="source:permission-denied")
        self.call("pause")
        self.call("resume")
        state = self.call("status")
        self.assertEqual("blocked", state["stage"])
        self.assertEqual("access", state["blocker"]["kind"])
        self.assertEqual("verified", state["work_status"])

    def test_unreadable_work_sets_access_blocker_and_missing_evidence_sets_io_blocker(self):
        self.ready(required=False)
        with patch("ledger.read_file", side_effect=PermissionError):
            with self.assertRaisesRegex(LedgerError, "blocked"):
                self.call("complete")
        self.assertEqual("access", self.call("status")["blocker"]["kind"])
        self.call("clear-blocker", resolution_ref="local:access-restored")
        self.call("repair", reason_ref="local:access-restored")
        digest = self.record()
        self.check(digest)
        self.review(digest)
        self.review_file.unlink()
        with self.assertRaisesRegex(LedgerError, "blocked"):
            self.call("complete")
        self.assertEqual("io", self.call("status")["blocker"]["kind"])

    def test_recovery_owner_cannot_inherit_its_own_review(self):
        self.ready(required=False)
        self.call("complete")
        self.call("pause")
        self.owner = "verifier"
        state = self.call("resume")
        self.assertIsNone(state["review"])
        self.assertEqual("repair-required", state["stage"])
        with self.assertRaises(LedgerError):
            self.call("complete")

    def test_return_to_previous_hash_reconciles_the_same_output(self):
        digest = self.ready()
        target = self.queue(digest)
        self.call("publish", publication_id="output")
        inode = Path(target).stat().st_ino
        for content in ("temporary revision", "version one\n"):
            self.call("repair", reason_ref="feedback:revision")
            self.artifact.write_text(content)
            revision = self.record()
            self.check(revision)
            self.review(revision)
        self.assertEqual(digest, revision)
        self.queue(digest)
        self.call("publish", publication_id="output")
        self.assertEqual(inode, Path(target).stat().st_ino)
        self.assertEqual(1, len(self.call("status")["publications"]))
        self.assertEqual("done", self.call("complete")["stage"])

    def test_repair_loops_are_capped_at_three(self):
        self.start(required=False)
        digest = self.record()
        self.check(digest, exit_code=1)
        for i in range(3):
            repaired = self.call("repair", reason_ref="check:failure")
            self.assertEqual(i + 1, repaired["retry_count"])
            digest = self.record()
            self.check(digest, exit_code=1)
        with self.assertRaisesRegex(LedgerError, "limit reached"):
            self.call("repair", reason_ref="check:failure")
        state = self.call("status")
        self.assertEqual(3, state["retry_count"])
        self.assertEqual("retry-limit", state["blocker"]["kind"])
        self.assertEqual("blocked", state["stage"])
        with self.assertRaisesRegex(LedgerError, "cannot be cleared"):
            self.call("clear-blocker", resolution_ref="not-an-authorization")

    def test_remote_intent_needs_matching_readback_receipt(self):
        digest = self.ready()
        target = self.queue(digest, target="https://example.invalid/document/123", adapter="remote")
        pending = self.call("publish", publication_id="output")
        self.assertEqual("reconciliation-required", pending["publications"][0]["status"])
        self.assertEqual("publishing", self.call("complete")["stage"])
        self.call("publication-error", publication_id="output", kind="uncertain", reason_ref="remote:response-lost")
        self.assertEqual("reconciliation-required", self.call("publish", publication_id="output")["publications"][0]["status"])
        readback = self.write("readback.txt", "incorrect remote content")
        with self.assertRaisesRegex(LedgerError, "hash mismatch"):
            self.call("receipt", publication_id="output", target=target, artifact_sha256=digest,
                      readback_path=str(readback), receipt_ref="remote:readback-1")
        readback.write_bytes(self.artifact.read_bytes())
        with self.assertRaisesRegex(LedgerError, "target or hash mismatch"):
            self.call("receipt", publication_id="output", target=target + "4", artifact_sha256=digest,
                      readback_path=str(readback), receipt_ref="remote:readback-1")
        self.call("receipt", publication_id="output", target=target, artifact_sha256=digest,
                  readback_path=str(readback), receipt_ref="remote:readback-1")
        self.assertEqual("done", self.call("complete")["stage"])
        before = self.call("status")
        database_bytes = self.db.read_bytes()
        readback.write_text("altered readback evidence")
        stale = self.call("status")
        self.assertEqual("publishing", stale["stage"])
        self.assertEqual("publish-or-reconcile", stale["next_action"])
        self.assertEqual("verified", stale["work_status"])
        self.assertEqual("reconciliation-required", stale["publications"][0]["status"])
        self.assertEqual(database_bytes, self.db.read_bytes())
        for key in ("artifact", "check", "review", "retry_count"):
            self.assertEqual(before[key], stale[key])

    def test_publication_auth_error_does_not_retry_or_rerun_work(self):
        digest = self.ready()
        target = self.queue(digest, target="https://example.invalid/document/123", adapter="remote")
        self.call("publication-error", publication_id="output", kind="auth", reason_ref="remote:expired-session")
        with self.assertRaisesRegex(LedgerError, "explicit resolution"):
            self.call("publish", publication_id="output")
        before = self.call("status")
        self.assertEqual("blocked", before["stage"])
        self.assertEqual("verified", before["work_status"])
        self.call("clear-blocker", publication_id="output", resolution_ref="remote:session-restored")
        self.call("receipt", publication_id="output", target=target, artifact_sha256=digest,
                  readback_path=str(self.artifact), receipt_ref="remote:readback-attestation")
        self.assertEqual(before["artifact_history"], self.call("status")["artifact_history"])

    def test_feedback_classification_cannot_edit_policy(self):
        self.start()
        before = self.call("status")["request"]
        for category in ("task", "skill", "code", "policy"):
            self.call("feedback", category=category, reference="feedback:" + category)
        self.call("feedback", category="policy", reference="feedback:policy")
        state = self.call("status")
        self.assertEqual(4, len(state["feedback"]))
        self.assertEqual(before, state["request"])
        self.assertEqual(self.skill.read_text(), self.call("context")["context"]["skills"][0]["text"])

    def test_concurrent_claim_has_one_owner(self):
        self.create()
        processes = []
        for owner in ("owner-a", "owner-b"):
            proc = subprocess.Popen([sys.executable, "-B", CLI, "--db", str(self.db), "claim"],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            proc.stdin.write(json.dumps({"task_id": "pilot", "owner": owner}))
            proc.stdin.close()
            proc.stdin = None
            processes.append(proc)
        for proc in processes:
            proc.communicate(timeout=15)
        self.assertEqual([0, 2], sorted(p.returncode for p in processes))
        self.assertIn(self.call("status")["owner"], {"owner-a", "owner-b"})

    def test_concurrent_publication_creates_one_result(self):
        digest = self.ready()
        target = self.queue(digest)
        processes = []
        for _ in range(2):
            proc = subprocess.Popen([sys.executable, "-B", CLI, "--db", str(self.db), "publish"],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            proc.stdin.write(json.dumps(self.data("publish", publication_id="output")))
            proc.stdin.close()
            proc.stdin = None
            processes.append(proc)
        for proc in processes:
            out, err = proc.communicate(timeout=15)
            self.assertEqual(0, proc.returncode, err)
            self.assertEqual("verified", json.loads(out)["publications"][0]["status"])
        self.assertEqual(1, self.call("status")["publications"][0]["attempts"])
        self.assertEqual(digest, sha(Path(target).read_bytes()))
        self.assertEqual([], list(self.root.glob(".ledger-*")))

    def test_untrusted_inputs_are_rejected_without_execution(self):
        self.create()
        for data in ({"task_id": "pilot", "owner": "$(touch pwned)"},
                     {"task_id": "pilot", "owner": "coordinator", "shell": "touch pwned"},
                     {"task_id": "pilot", "owner": "coordinator", "mail_body": "do not store"}):
            with self.assertRaises(LedgerError):
                self.ledger.dispatch("claim", data)
        self.assertFalse((self.root / "pwned").exists())
        self.call("claim")
        self.call("route", skills=[self.pin])
        self.call("configure-hooks", output_owner="personal", destinations=[], write_paths=[], requirements=[])
        digest = self.record()
        with self.assertRaises(LedgerError):
            self.check(digest, exit_code=True)
        self.check(digest)
        self.review(digest)
        with self.assertRaises(LedgerError):
            self.call("enqueue", publication_id="bad", adapter="remote", artifact_sha256=digest,
                      target="https://user:password@example.invalid/doc?token=secret")

    def test_symlink_output_is_not_followed_or_overwritten(self):
        digest = self.ready()
        target = self.queue(digest)
        user_file = self.write("user-file.txt", "user data")
        Path(target).symlink_to(user_file)
        state = self.call("publish", publication_id="output")
        self.assertEqual("conflict", state["publications"][0]["status"])
        self.assertEqual("user data", user_file.read_text())

    def test_cli_validation_error_is_actionable_and_does_not_echo_input(self):
        self.create()
        invalid = self.cli("claim", owner="invalid;input")
        self.assertEqual(2, invalid.returncode)
        self.assertEqual({"error": "invalid identifier"}, json.loads(invalid.stderr))
        self.assertNotIn("invalid;input", invalid.stderr)
        self.assertNotIn("Traceback", invalid.stderr)
        self.start()
        digest = self.record()
        self.check(digest)
        self.review(digest)
        invalid = self.cli("enqueue", publication_id="bad", adapter="remote", artifact_sha256=digest,
                           target="https://[invalid")
        self.assertEqual(2, invalid.returncode)
        self.assertNotIn("Traceback", invalid.stderr)

    def test_duplicate_json_fields_are_rejected(self):
        self.create()
        result = subprocess.run([sys.executable, "-B", CLI, "--db", str(self.db), "claim"],
                                input='{"task_id":"pilot","owner":"a","owner":"b"}',
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(2, result.returncode)
        self.assertEqual({"error": "duplicate JSON fields"}, json.loads(result.stderr))
        self.assertIsNone(self.call("status")["owner"])


if __name__ == "__main__":
    unittest.main()
