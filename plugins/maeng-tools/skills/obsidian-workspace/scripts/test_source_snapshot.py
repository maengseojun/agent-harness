"""Focused behavioral tests for selected native source snapshots."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import source_snapshot


class MemoryMCP:
    def __init__(self, vault, notes=None, *, error=None, reported_hash=None):
        self.vault = vault
        self.notes = dict(notes or {})
        self.error = error
        self.reported_hash = reported_hash
        self.calls = []

    def assert_vault(self, vault):
        if Path(vault) != self.vault:
            raise AssertionError("wrong test vault")

    def read_notes(self, paths):
        self.calls.append(list(paths))
        if self.error:
            raise self.error
        result = {}
        for path in paths:
            body = self.notes.get(path)
            if body is None:
                result[path] = {"exists": False, "body": None, "sha256": None}
            else:
                digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
                result[path] = {"exists": True, "body": body, "sha256": self.reported_hash or digest}
        return result


class SourceSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="source-snapshot-test-")
        self.base = Path(self.temp.name)
        self.vault = self.base / "Obsidian Vault"
        self.vault.mkdir()
        self.notes = {}
        self.expected_patch = mock.patch.object(source_snapshot, "EXPECTED_VAULT", self.vault)
        self.expected_patch.start()
        self.adapter = MemoryMCP(self.vault, self.notes)
        self.adapter.notes = self.notes

    def tearDown(self):
        self.expected_patch.stop()
        self.temp.cleanup()

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
            source_snapshot.run(self.args(receipt, impacts=impacts, apply=apply, vault=vault), self.adapter)
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

    def test_wrong_vault_stops_before_capture_or_note_read(self):
        receipt = self.write_receipt(self.make_receipt())
        before = self.snapshot()
        self.assert_snapshot_error(receipt, "wrong_vault", apply=True, vault=self.base / "different vault")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.adapter.calls, [])

    def test_preview_reads_selected_raw_markdown_through_mcp_and_writes_nothing(self):
        receipt = self.write_receipt(self.make_receipt())
        note_path = "wiki/sources/P-MAE166.md"
        original = "---\r\ntitle: legacy: [raw]\r\ncomment: \"keep me\"\r\n---\r\n# Existing source\r\nreview this claim\r\n"
        self.notes[note_path] = original
        before = self.snapshot()
        payload = source_snapshot.run(self.args(receipt, impacts=[note_path]), self.adapter)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(payload["action"], "would_create")
        self.assertTrue(payload["changed"]["body"])
        self.assertIn("first native body", payload["changed"]["diff"])
        self.assertEqual(payload["impact_notes"], [{
            "path": note_path,
            "sha256": hashlib.sha256(original.encode("utf-8")).hexdigest(),
            "body": original,
        }])
        self.assertEqual(self.adapter.calls, [[note_path]])
        self.assertNotIn("first native body", str(self.adapter.calls))

    def test_large_native_body_stays_in_receipt_not_mcp_arguments(self):
        body = "selected native body\n" + ("long line\n" * 35_000)
        receipt = self.write_receipt(self.make_receipt(body=body), "large-receipt.json")
        note_path = "wiki/sources/P-MAE166.md"
        self.adapter.notes[note_path] = "selected impact note\n"
        payload = source_snapshot.run(self.args(receipt, impacts=[note_path]), self.adapter)
        self.assertEqual(payload["candidate"]["native_body_sha256"], hashlib.sha256(body.encode()).hexdigest())
        self.assertTrue(payload["changed"]["diff"].endswith("+long line\n"))
        self.assertEqual(self.adapter.calls, [[note_path]])
        self.assertNotIn(body, str(self.adapter.calls))

    def test_missing_and_unavailable_impact_notes_are_distinct(self):
        receipt = self.write_receipt(self.make_receipt())
        note_path = "wiki/sources/S-LING-002.md"
        with self.assertRaises(source_snapshot.SnapshotError) as missing:
            source_snapshot.run(self.args(receipt, impacts=[note_path]), self.adapter)
        self.assertEqual(missing.exception.code, "impact_note_missing")
        self.adapter.error = RuntimeError("fixture access failure")
        with self.assertRaises(source_snapshot.SnapshotError) as unavailable:
            source_snapshot.run(self.args(receipt, impacts=[note_path]), self.adapter)
        self.assertEqual(unavailable.exception.code, "impact_note_unavailable")

    def test_mismatched_raw_readback_hash_is_rejected(self):
        receipt = self.write_receipt(self.make_receipt())
        note_path = "wiki/sources/S-LING-002.md"
        self.adapter.notes[note_path] = "---\r\ntitle: keep raw\r\n---\r\nbody\r\n"
        self.adapter.reported_hash = "0" * 64
        with self.assertRaises(source_snapshot.SnapshotError) as caught:
            source_snapshot.run(self.args(receipt, impacts=[note_path]), self.adapter)
        self.assertEqual(caught.exception.code, "impact_note_changed")

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
