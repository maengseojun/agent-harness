"""Focused tests for the guarded wiki-plan preview/apply workflow."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import source_snapshot
import wiki_compile


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class MemoryMCP:
    def __init__(self, vault, notes, *, missing=(), fail_after=None):
        self.vault = vault
        self.missing = list(missing)
        self.fail_after = fail_after
        self.write_calls = 0
        self.checked_links = []
        self.calls = []
        for path, body in notes.items():
            target = self.vault / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body.encode("utf-8"))

    def assert_vault(self, vault):
        if Path(vault) != self.vault:
            raise AssertionError("wrong test vault")

    def read_notes(self, paths):
        self.calls.append(("read", list(paths)))
        result = {}
        for path in paths:
            target = self.vault / path
            if not target.exists():
                result[path] = {"exists": False, "body": None, "sha256": None}
            else:
                body = target.read_bytes().decode("utf-8")
                result[path] = {"exists": True, "body": body, "sha256": digest(body)}
        return result

    def note_exists(self, path):
        return (self.vault / path).is_file()

    def find_note_paths(self, basename):
        return sorted(path.relative_to(self.vault).as_posix() for path in self.vault.rglob("*.md") if path.is_file() and path.stem.casefold() == basename.removesuffix(".md").casefold())

    def write_note(self, path, body):
        self.calls.append(("write", path))
        self.write_calls += 1
        if self.fail_after is not None and self.write_calls > self.fail_after:
            raise RuntimeError("injected uncertain MCP write")
        target = self.vault / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body.encode("utf-8"))
        return "acknowledged"


class WikiCompileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wiki-compile-test-")
        self.base = Path(self.temp.name)
        self.vault = self.base / "Vault"
        self.vault.mkdir()
        self.vault_patch = mock.patch.object(source_snapshot, "EXPECTED_VAULT", self.vault)
        self.vault_patch.start()
        self.source = "raw/selected.md"
        self.source_body = "Selected source evidence\n"
        self.hub = "hubs/research.md"
        self.initial = {self.source: self.source_body, self.hub: "# Research\n"}
        self.plan = {
            "operation_id": "test-op-1",
            "hub": self.hub,
            "sources": [{"path": self.source, "sha256": digest(self.source_body)}],
            "notes": [{"path": "wiki/concepts/idea.md", "expected_sha256": None,
                       "body": "# Idea\n\nEvidence: [[raw/selected]]\n"}],
        }
        self.plan_path = self.base / "plan.json"
        self.write_plan()

    def tearDown(self):
        self.vault_patch.stop()
        self.temp.cleanup()

    def write_plan(self):
        self.plan_path.write_text(json.dumps(self.plan, ensure_ascii=False), encoding="utf-8")

    def args(self, *, apply=False):
        return SimpleNamespace(vault=str(self.vault), plan=str(self.plan_path), apply=apply)

    def test_create_and_identical_reapply_are_noop(self):
        adapter = MemoryMCP(self.vault, self.initial)
        first = wiki_compile.run(self.args(apply=True), adapter)
        self.assertEqual(first["status"], "applied")
        self.assertEqual(first["observed_changed_paths"], ["wiki/concepts/idea.md"])
        second = wiki_compile.run(self.args(apply=True), adapter)
        self.assertEqual(second["status"], "noop")
        self.assertEqual(second["observed_changed_paths"], [])

    def test_update_keeps_prior_body_and_reapply_is_noop(self):
        old_body = "# Earlier idea\n"
        path = "wiki/concepts/idea.md"
        self.plan["notes"][0]["expected_sha256"] = digest(old_body)
        self.write_plan()
        adapter = MemoryMCP(self.vault, {**self.initial, path: old_body})
        first = wiki_compile.run(self.args(apply=True), adapter)
        prior_path = wiki_compile.backup_path(self.plan["operation_id"], path)
        self.assertEqual(first["status"], "applied")
        self.assertEqual((self.vault / prior_path).read_bytes(), old_body.encode("utf-8"))
        second = wiki_compile.run(self.args(apply=True), adapter)
        self.assertEqual(second["status"], "noop")
        self.assertEqual(second["observed_changed_paths"], [])

    def test_source_change_blocks_apply(self):
        adapter = MemoryMCP(self.vault, {**self.initial, self.source: "new source body\n"})
        with self.assertRaises(source_snapshot.SnapshotError) as caught:
            wiki_compile.run(self.args(apply=True), adapter)
        self.assertEqual(caught.exception.code, "source_changed")
        self.assertFalse(any(call[0] == "write" for call in adapter.calls))

    def test_unexpected_existing_target_conflicts(self):
        adapter = MemoryMCP(self.vault, {**self.initial, "wiki/concepts/idea.md": "someone else's note"})
        with self.assertRaises(source_snapshot.SnapshotError) as caught:
            wiki_compile.run(self.args(apply=True), adapter)
        self.assertEqual(caught.exception.code, "target_conflict")
        self.assertFalse(any(call[0] == "write" for call in adapter.calls))

    def test_desired_body_is_noop_before_stale_expected_hash_check(self):
        desired = self.plan["notes"][0]["body"]
        self.plan["notes"][0]["expected_sha256"] = digest("old prior body")
        self.write_plan()
        adapter = MemoryMCP(self.vault, {**self.initial, "wiki/concepts/idea.md": desired})
        result = wiki_compile.run(self.args(), adapter)
        self.assertEqual(result["status"], "preview")
        self.assertEqual(result["notes"][0]["action"], "noop")

    def test_traversal_and_source_root_targets_are_rejected(self):
        for path in ("raw/../wiki/concepts/unsafe.md", "raw/source.md", "wiki/sources/captured.md"):
            candidate = json.loads(json.dumps(self.plan))
            candidate["notes"][0]["path"] = path
            with self.subTest(path=path), self.assertRaises(source_snapshot.SnapshotError):
                wiki_compile.validate_plan(candidate)

    def test_raw_body_source_is_allowed_but_generated_version_body_is_excluded(self):
        candidate = json.loads(json.dumps(self.plan))
        candidate["sources"] = [{"path": "raw/native-captures/selected.body", "sha256": digest("capture")}]
        self.assertIs(wiki_compile.validate_plan(candidate), candidate)
        candidate["sources"][0]["path"] = "raw/wiki-compile-versions/test-op-1/native-captures/selected.body"
        with self.assertRaises(source_snapshot.SnapshotError):
            wiki_compile.validate_plan(candidate)

    def test_inline_markdown_links_parse_escaped_percent_and_relative_paths(self):
        body = (
            "[ordinary](related.md) [escaped](Folder\\ Name.md) "
            "[angle](<Space Name.md>) [encoded](Encoded%20Note.md) "
            "[relative](../entities/entity.md#details) [external](https://example.com/a.md) "
            "![image](image.md) ` [code](ignored.md) `\n"
            "```md\n[code block](also-ignored.md)\n```\n"
        )
        self.assertEqual(
            list(wiki_compile.markdown_targets(body)),
            ["related.md", "Folder Name.md", "Space Name.md", "Encoded Note.md", "../entities/entity.md"],
        )
        links = wiki_compile.extract_links([{"path": "wiki/concepts/idea.md", "body": body}])
        self.assertEqual([item["target"] for item in links], list(wiki_compile.markdown_targets(body)))

    def test_missing_inline_markdown_link_blocks_preview(self):
        self.plan["notes"][0]["body"] += "\nSee [missing](missing.md).\n"
        self.write_plan()
        adapter = MemoryMCP(self.vault, self.initial)
        with self.assertRaises(source_snapshot.SnapshotError) as caught:
            wiki_compile.run(self.args(), adapter)
        self.assertEqual(caught.exception.code, "missing_link")
        self.assertNotIn(("write", "wiki/concepts/idea.md"), adapter.calls)

    def test_missing_wiki_link_blocks_apply(self):
        self.plan["notes"][0]["body"] += "\nSee [[Missing Concept]].\n"
        self.write_plan()
        adapter = MemoryMCP(self.vault, self.initial)
        with self.assertRaises(source_snapshot.SnapshotError) as caught:
            wiki_compile.run(self.args(apply=True), adapter)
        self.assertEqual(caught.exception.code, "missing_link")
        self.assertFalse(any(call[0] == "write" for call in adapter.calls))

    def test_ambiguous_bare_link_rejects_multiple_planned_or_existing_notes(self):
        self.plan["notes"][0]["body"] = "# Idea\nSee [[idea]].\n"
        self.plan["notes"].append({
            "path": "wiki/answers/nested/idea.md", "expected_sha256": None, "body": "# Other idea\n",
        })
        self.plan["notes"].append({
            "path": "wiki/entities/nested/idea.md", "expected_sha256": None, "body": "# Another idea\n",
        })
        self.plan["notes"][0]["path"] = "wiki/concepts/derived.md"
        self.write_plan()
        adapter = MemoryMCP(self.vault, self.initial)
        with self.assertRaises(source_snapshot.SnapshotError) as caught:
            wiki_compile.run(self.args(), adapter)
        self.assertEqual(caught.exception.code, "ambiguous_link")

        self.plan["notes"] = [
            {"path": "wiki/concepts/derived.md", "expected_sha256": None, "body": "# Idea\nSee [[idea]].\n"},
            {"path": "wiki/answers/nested/idea.md", "expected_sha256": None, "body": "# Other idea\n"},
        ]
        self.write_plan()
        adapter = MemoryMCP(self.vault, {**self.initial, "hubs/idea.md": "# Existing duplicate\n"})
        with self.assertRaises(source_snapshot.SnapshotError) as caught:
            wiki_compile.run(self.args(), adapter)
        self.assertEqual(caught.exception.code, "ambiguous_link")

    def test_partial_failure_reports_observed_and_performed_paths(self):
        self.plan["notes"].append({"path": "wiki/answers/answer.md", "expected_sha256": None,
                                   "body": "# Answer\n"})
        self.write_plan()
        adapter = MemoryMCP(self.vault, self.initial, fail_after=1)
        result = wiki_compile.run(self.args(apply=True), adapter)
        self.assertEqual(result["status"], "uncertain")
        self.assertIn("wiki/concepts/idea.md", result["performed_paths"])
        self.assertEqual(result["observed_changed_paths"], ["wiki/concepts/idea.md"])
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
