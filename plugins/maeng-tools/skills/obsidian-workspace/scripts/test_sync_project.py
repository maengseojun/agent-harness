"""Isolated behavioral tests for sync_project.py; every vault lives in a temp directory."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("sync_project.py")


class SyncProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sync-project-test-")
        self.base = Path(self.temp.name)
        self.vault = self.base / "vault"
        self.source = self.base / "source"
        self.vault.mkdir()
        self.source.mkdir()
        (self.vault / "Home.md").write_text("# Home\n", encoding="utf-8")
        (self.vault / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
        (self.vault / "wiki").mkdir()
        (self.vault / "hubs").mkdir()
        self.project_id = "MAE_177-test"

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, files, *, source=None, vault=None, project_id=None, apply=False):
        args = [
            sys.executable, "-B", str(SCRIPT),
            "--vault", str(vault or self.vault),
            "--project-id", project_id or self.project_id,
            "--source-root", str(source or self.source),
            "--files", *files,
        ]
        if apply:
            args.append("--apply")
        process = subprocess.run(args, text=True, capture_output=True, check=False)
        try:
            payload = json.loads(process.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"CLI did not return JSON: {exc}; stdout={process.stdout!r}; stderr={process.stderr!r}")
        return process, payload

    def assert_error(self, files, code, **kwargs):
        process, payload = self.run_cli(files, **kwargs)
        self.assertNotEqual(process.returncode, 0)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], code)
        return payload

    def catalog(self):
        return self.vault / "assets" / "deliverables" / self.project_id / "catalog.json"

    def test_dry_run_does_not_change_files_or_create_directories(self):
        source = self.source / "report.md"
        source.write_text("proposal v1\n", encoding="utf-8")
        before = self.snapshot_tree(self.base)
        process, payload = self.run_cli(["report.md"])
        after = self.snapshot_tree(self.base)
        self.assertEqual(process.returncode, 0)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["applied"])
        self.assertEqual(payload["items"][0]["action"], "would_create")
        self.assertEqual(before, after)
        self.assertFalse((self.vault / "assets").exists())
        self.assertEqual(source.read_text(encoding="utf-8"), "proposal v1\n")

    def test_initial_apply_then_identical_apply_keeps_catalog_bytes_and_mtime(self):
        source = self.source / "report.md"
        original = b"same bytes\n"
        source.write_bytes(original)
        first, first_result = self.run_cli(["report.md"], apply=True)
        self.assertEqual(first.returncode, 0, first.stdout)
        self.assertTrue(first_result["catalog_changed"])
        saved = Path(first_result["items"][0]["saved_path"])
        self.assertEqual(saved.read_bytes(), original)
        data = json.loads(self.catalog().read_text(encoding="utf-8"))
        record = data["files"]["report.md"]
        version = record["versions"][0]
        self.assertEqual(data["schema"], 1)
        self.assertEqual(data["project_id"], self.project_id)
        self.assertEqual(data["source_root"], str(self.source.resolve()))
        self.assertEqual(record["source_path"], str(source.resolve()))
        self.assertEqual(record["current_sha256"], hashlib.sha256(original).hexdigest())
        self.assertEqual(version["size"], len(original))
        self.assertTrue(version["captured_at"].endswith("Z"))
        catalog = self.catalog()
        content_before = catalog.read_bytes()
        mtime_before = catalog.stat().st_mtime_ns

        second, second_result = self.run_cli(["report.md"], apply=True)
        self.assertEqual(second.returncode, 0, second.stdout)
        self.assertTrue(second_result["applied"])
        self.assertFalse(second_result["catalog_changed"])
        self.assertEqual(second_result["items"][0]["action"], "reused")
        self.assertEqual(catalog.read_bytes(), content_before)
        self.assertEqual(catalog.stat().st_mtime_ns, mtime_before)
        self.assertEqual(source.read_bytes(), original)

    def test_new_version_and_revert_preserve_each_unique_copy(self):
        source = self.source / "report.md"
        v1, v2 = b"version one\n", b"version two\n"
        source.write_bytes(v1)
        first, _ = self.run_cli(["report.md"], apply=True)
        self.assertEqual(first.returncode, 0, first.stdout)
        initial = json.loads(self.catalog().read_text(encoding="utf-8"))["files"]["report.md"]
        v1_sha = hashlib.sha256(v1).hexdigest()
        v1_path = self.catalog().parent / next(v["path"] for v in initial["versions"] if v["sha256"] == v1_sha)

        source.write_bytes(v2)
        second, second_result = self.run_cli(["report.md"], apply=True)
        self.assertEqual(second.returncode, 0, second.stdout)
        v2_sha = hashlib.sha256(v2).hexdigest()
        self.assertEqual(second_result["items"][0]["changed_from_sha256"], v1_sha)
        self.assertEqual(v1_path.read_bytes(), v1)

        source.write_bytes(v1)
        third, third_result = self.run_cli(["report.md"], apply=True)
        self.assertEqual(third.returncode, 0, third.stdout)
        self.assertEqual(third_result["items"][0]["changed_from_sha256"], v2_sha)
        record = json.loads(self.catalog().read_text(encoding="utf-8"))["files"]["report.md"]
        self.assertEqual(record["current_sha256"], v1_sha)
        self.assertEqual(len(record["versions"]), 2)
        saved = {v["sha256"]: (self.catalog().parent / v["path"]).read_bytes() for v in record["versions"]}
        self.assertEqual(saved, {v1_sha: v1, v2_sha: v2})
        self.assertEqual(source.read_bytes(), v1)

    def test_modified_managed_copy_is_rejected_without_rewriting_catalog(self):
        source = self.source / "report.md"
        source.write_bytes(b"original\n")
        first, _ = self.run_cli(["report.md"], apply=True)
        self.assertEqual(first.returncode, 0, first.stdout)
        catalog_bytes = self.catalog().read_bytes()
        record = json.loads(catalog_bytes)["files"]["report.md"]
        saved = self.catalog().parent / record["versions"][0]["path"]
        saved.write_bytes(b"tampered\n")

        payload = self.assert_error(["report.md"], "catalog_copy_tampered", apply=True)
        self.assertEqual(payload["partial_writes"], [])
        self.assertEqual(self.catalog().read_bytes(), catalog_bytes)
        self.assertEqual(source.read_bytes(), b"original\n")

    def test_modified_catalog_metadata_is_rejected(self):
        source = self.source / "report.md"
        source.write_bytes(b"original\n")
        first, _ = self.run_cli(["report.md"], apply=True)
        self.assertEqual(first.returncode, 0, first.stdout)
        catalog = self.catalog()
        data = json.loads(catalog.read_text(encoding="utf-8"))
        data["files"]["report.md"]["current_sha256"] = "0" * 64
        catalog.write_text(json.dumps(data), encoding="utf-8")
        tampered = catalog.read_bytes()

        self.assert_error(["report.md"], "invalid_catalog", apply=True)
        self.assertEqual(catalog.read_bytes(), tampered)
        self.assertEqual(source.read_bytes(), b"original\n")

    def test_different_source_root_cannot_reuse_project_id(self):
        source = self.source / "report.md"
        source.write_bytes(b"same\n")
        first, _ = self.run_cli(["report.md"], apply=True)
        self.assertEqual(first.returncode, 0, first.stdout)
        other = self.base / "other-source"
        other.mkdir()
        (other / "report.md").write_bytes(b"same\n")
        self.assert_error(["report.md"], "source_root_mismatch", source=other, apply=True)
        self.assertEqual(source.read_bytes(), b"same\n")
        self.assertEqual((other / "report.md").read_bytes(), b"same\n")

    def test_binary_is_refused_before_any_vault_write(self):
        (self.source / "figure.PNG").write_bytes(b"\x89PNG\r\n")
        self.assert_error(["figure.PNG"], "binary_to_drive", apply=True)
        self.assertFalse((self.vault / "assets").exists())

    def test_wrong_vault_escape_symlink_and_sensitive_candidates_are_rejected(self):
        outside = self.base / "outside.txt"
        outside.write_text("outside\n", encoding="utf-8")
        self.assert_error(["report.md"], "source_unavailable")
        wrong_vault = self.base / "wrong-vault"
        wrong_vault.mkdir()
        self.assert_error(["report.md"], "wrong_vault", vault=wrong_vault)
        self.assert_error(["../outside.txt"], "invalid_source_path")
        self.assert_error([".env"], "sensitive_candidate")
        (self.source / ".env").write_text("not read\n", encoding="utf-8")
        self.assert_error([".env"], "sensitive_candidate")
        (self.source / "credentials.json").write_text("not read\n", encoding="utf-8")
        self.assert_error(["credentials.json"], "sensitive_candidate")
        (self.source / "folder").mkdir()
        self.assert_error(["folder"], "unsafe_source")
        (self.vault / "private.md").write_text("must not be ingested\n", encoding="utf-8")
        self.assert_error(["vault/private.md"], "source_inside_vault", source=self.base)
        self.assert_error(["private.md"], "source_inside_vault", source=self.vault)
        try:
            (self.source / "linked.md").symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("filesystem does not support symlinks")
        self.assert_error(["linked.md"], "symlink_source")

    def test_invalid_project_id_and_duplicate_file_selection_are_rejected(self):
        (self.source / "report.md").write_text("x\n", encoding="utf-8")
        self.assert_error(["report.md"], "invalid_project_id", project_id="../bad")
        self.assert_error(["report.md", "report.md"], "duplicate_source")

    @staticmethod
    def snapshot_tree(root):
        result = {}
        for path in sorted(root.rglob("*")):
            relative = str(path.relative_to(root))
            if path.is_dir():
                result[relative] = ("dir", path.stat().st_mtime_ns)
            else:
                result[relative] = ("file", path.read_bytes(), path.stat().st_mtime_ns)
        return result


if __name__ == "__main__":
    unittest.main()
