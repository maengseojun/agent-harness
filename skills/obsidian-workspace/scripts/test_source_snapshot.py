"""Focused behavioral tests for selected native source snapshots."""

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import source_snapshot


class SourceSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="source-snapshot-test-")
        self.base = Path(self.temp.name)
        self.vault = self.base / "Obsidian Vault"
        self.vault.mkdir()
        self.cli_vault = self.vault
        self.notes = {}
        self.calls = []
        self.expected_patch = mock.patch.object(source_snapshot, "EXPECTED_VAULT", self.vault)
        self.obsidian_patch = mock.patch.object(source_snapshot, "OBSIDIAN", "/fake/obsidian")
        self.invoke_patch = mock.patch.object(source_snapshot, "invoke_obsidian", side_effect=self.fake_cli)
        self.expected_patch.start()
        self.obsidian_patch.start()
        self.invoke_patch.start()

    def tearDown(self):
        self.invoke_patch.stop()
        self.obsidian_patch.stop()
        self.expected_patch.stop()
        self.temp.cleanup()

    def fake_cli(self, command):
        self.calls.append(list(command))
        if command == ["vault", "info=path"]:
            return str(self.cli_vault)
        if len(command) == 2 and command[0] == "eval" and command[1].startswith("code="):
            code = command[1][5:]
            literal = code.split("const paths=", 1)[1].split(";const notes", 1)[0]
            paths = json.loads(literal)
            items = [
                {"path": path, "ok": path in self.notes, "body": self.notes.get(path, ""), "error": "missing"}
                for path in paths
            ]
            return "=> " + json.dumps({"notes": items}, ensure_ascii=False)
        raise AssertionError(f"unexpected command: {command!r}")

    def make_receipt(self, *, body="first native body\n", revision="rev-1", fetched_at="2026-10-14T09:00:00+09:00", raw_response=None):
        if raw_response is None:
            raw_response = {"page": {"id": "page-123", "last_edited_at": revision}}
        return {
            "schema": 1,
            "service": "notion",
            "source_id": "page-123",
            "url": "https://www.notion.so/example/page-123",
            "revision": revision,
            "fetched_at": fetched_at,
            "coverage": {"scope": "selected native body", "unknown_block_count": True, "truncated": None},
            "native_body": body,
            "raw_response": raw_response,
        }

    def write_receipt(self, value, name="receipt.json"):
        path = self.base / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def args(self, receipt, *, impacts=(), apply=False, vault=None):
        return SimpleNamespace(
            vault=str(vault or self.vault),
            receipt=str(receipt),
            impact_note=list(impacts),
            apply=apply,
        )

    def snapshot(self):
        return {
            path.relative_to(self.vault).as_posix(): path.read_bytes()
            for path in sorted(self.vault.rglob("*")) if path.is_file()
        }

    def assert_snapshot_error(self, receipt, code, *, impacts=(), apply=False, vault=None):
        with self.assertRaises(source_snapshot.SnapshotError) as caught:
            source_snapshot.run(self.args(receipt, impacts=impacts, apply=apply, vault=vault))
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_receipt_identity_url_and_impact_traversal_are_validated(self):
        value = self.make_receipt()
        value.pop("source_id")
        with self.assertRaises(source_snapshot.SnapshotError) as caught:
            source_snapshot.validate_receipt(value)
        self.assertEqual(caught.exception.code, "invalid_receipt")

        value = self.make_receipt()
        value["url"] = "file:///tmp/private"
        with self.assertRaises(source_snapshot.SnapshotError) as caught:
            source_snapshot.validate_receipt(value)
        self.assertEqual(caught.exception.code, "invalid_url")

        for path in ("wiki/sources/../Home.md", "wiki/answers/../../outside.md", "/wiki/sources/a.md"):
            with self.assertRaises(source_snapshot.SnapshotError) as caught:
                source_snapshot.validate_impact_path(path)
            self.assertEqual(caught.exception.code, "invalid_path")

    def test_wrong_cli_target_stops_before_capture_or_note_read(self):
        receipt = self.write_receipt(self.make_receipt())
        self.cli_vault = self.base / "different vault"
        before = self.snapshot()
        self.assert_snapshot_error(receipt, "wrong_vault", apply=True)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.calls, [["vault", "info=path"]])

    def test_preview_reads_selected_notes_through_cli_and_writes_nothing(self):
        receipt = self.write_receipt(self.make_receipt())
        note_path = "wiki/sources/P-MAE166.md"
        self.notes[note_path] = "# Existing source\nreview this claim\n"
        before = self.snapshot()
        payload = source_snapshot.run(self.args(receipt, impacts=[note_path]))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(payload["action"], "would_create")
        self.assertTrue(payload["changed"]["body"])
        self.assertIn("first native body", payload["changed"]["diff"])
        self.assertEqual(payload["impact_notes"], [{
            "path": note_path,
            "sha256": hashlib.sha256(self.notes[note_path].encode("utf-8")).hexdigest(),
            "body": self.notes[note_path],
        }])
        self.assertFalse((self.vault / note_path).exists())
        self.assertEqual([call[0] for call in self.calls], ["vault", "eval"])
        self.assertIn(note_path, self.calls[1][1])
        self.assertNotIn("first native body", self.calls[1][1])

    def test_large_native_body_is_loaded_from_receipt_not_cli_arguments(self):
        body = "selected native body\n" + ("long line\n" * 35_000)
        receipt = self.write_receipt(self.make_receipt(body=body), "large-receipt.json")
        note_path = "wiki/sources/P-MAE166.md"
        self.notes[note_path] = "selected impact note\n"
        payload = source_snapshot.run(self.args(receipt, impacts=[note_path]))
        self.assertEqual(payload["candidate"]["native_body_sha256"], hashlib.sha256(body.encode()).hexdigest())
        self.assertTrue(payload["changed"]["diff"].endswith("+long line\n"))
        self.assertLess(len(self.calls[1][1]), 1000)
        self.assertTrue(all(body not in " ".join(call) for call in self.calls))

    def test_pty_eval_preserves_note_carriage_returns_exactly(self):
        executable = self.base / "fake-obsidian"
        payload_path = self.base / "eval-result.json"
        log_path = self.base / "cli-log.json"
        note_path = "wiki/sources/S-LING-002.md"
        expected_body = "first line\r\nsecond line\rfinal carriage return\r"
        payload_path.write_text(json.dumps({"notes": [{
            "path": note_path, "ok": True, "body": expected_body,
        }]}), encoding="utf-8")
        executable.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "with open(os.environ['FAKE_OBSIDIAN_PAYLOAD'], encoding='utf-8') as stream:\n"
            "    payload = json.load(stream)\n"
            "with open(os.environ['FAKE_OBSIDIAN_LOG'], 'w', encoding='utf-8') as stream:\n"
            "    json.dump({'executable': sys.argv[0], 'argv': sys.argv[1:], 'stdout_isatty': sys.stdout.isatty()}, stream)\n"
            "sys.stdout.write('=> ' + json.dumps(payload, ensure_ascii=False) + '\\r\\n')\n",
            encoding="utf-8",
        )
        executable.chmod(0o755)
        self.invoke_patch.stop()
        try:
            with mock.patch.object(source_snapshot, "OBSIDIAN", str(executable)), mock.patch.dict(
                os.environ,
                {"FAKE_OBSIDIAN_PAYLOAD": str(payload_path), "FAKE_OBSIDIAN_LOG": str(log_path)},
            ):
                notes = source_snapshot.read_impact_notes([note_path])
        finally:
            self.invoke_patch.start()

        self.assertEqual(notes[0]["body"], expected_body)
        self.assertEqual(notes[0]["sha256"], hashlib.sha256(expected_body.encode("utf-8")).hexdigest())
        log = json.loads(log_path.read_text(encoding="utf-8"))
        self.assertEqual(log["executable"], str(executable))
        self.assertTrue(log["stdout_isatty"])
        self.assertEqual(log["argv"][:2], ["vault=Obsidian Vault", "eval"])
        self.assertIn(note_path, log["argv"][2])

    def test_apply_reuses_identical_version_and_keeps_prior_bytes(self):
        first_receipt = self.write_receipt(self.make_receipt())
        first = source_snapshot.run(self.args(first_receipt, apply=True))
        first_body_path = self.vault / first["candidate"]["body_path"]
        first_response_path = self.vault / first["candidate"]["raw_response_path"]
        first_body = first_body_path.read_bytes()
        self.assertEqual(first_body, b"first native body\n")
        self.assertEqual(
            first_response_path.read_bytes(),
            source_snapshot.json_bytes(self.make_receipt()["raw_response"]),
        )
        first_tree = self.snapshot()

        repeated = source_snapshot.run(self.args(first_receipt, apply=True))
        self.assertEqual(repeated["action"], "reused")
        self.assertEqual(self.snapshot(), first_tree)

        second_receipt = self.write_receipt(
            self.make_receipt(body="second native body\n", revision="rev-2", fetched_at="2026-10-14T10:00:00+09:00"),
            "receipt-v2.json",
        )
        second = source_snapshot.run(self.args(second_receipt, apply=True))
        self.assertEqual(second["action"], "captured")
        self.assertEqual(first_body_path.read_bytes(), first_body)
        self.assertNotEqual(first["candidate"]["body_path"], second["candidate"]["body_path"])
        catalog = json.loads((self.vault / "raw/native-captures/catalog.json").read_text(encoding="utf-8"))
        source = catalog["sources"][source_snapshot.identity_key(first["identity"])]
        self.assertEqual(len(source["versions"]), 2)

    def test_same_revision_with_different_body_is_rejected(self):
        original = self.write_receipt(self.make_receipt())
        source_snapshot.run(self.args(original, apply=True))
        before = self.snapshot()
        conflicting = self.write_receipt(self.make_receipt(body="changed under same revision\n"), "conflict.json")
        error = self.assert_snapshot_error(conflicting, "version_conflict", apply=True)
        self.assertEqual(error.details["action"], "conflict")
        self.assertEqual(self.snapshot(), before)

    def test_invalid_timestamp_or_secret_transport_metadata_is_rejected(self):
        value = self.make_receipt()
        value["fetched_at"] = "2026-10-14T09:00:00"
        with self.assertRaises(source_snapshot.SnapshotError) as caught:
            source_snapshot.validate_receipt(value)
        self.assertEqual(caught.exception.code, "invalid_receipt")

        value = self.make_receipt(raw_response={"page": {}, "headers": {"x-api-key": "secret"}})
        with self.assertRaises(source_snapshot.SnapshotError) as caught:
            source_snapshot.validate_receipt(value)
        self.assertEqual(caught.exception.code, "sensitive_receipt")


if __name__ == "__main__":
    unittest.main()
