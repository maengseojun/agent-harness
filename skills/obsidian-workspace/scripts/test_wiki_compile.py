"""Focused tests for the guarded wiki-plan preview/apply workflow."""

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import source_snapshot
import wiki_compile


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class MemoryCLI:
    def __init__(self, vault, notes, *, missing=(), fail_after=None):
        self.vault = vault
        self.notes = dict(notes)
        self.missing = list(missing)
        self.fail_after = fail_after
        self.apply_calls = 0
        self.checked_links = []

    def assert_vault(self, vault):
        if Path(vault) != self.vault:
            raise AssertionError("wrong test vault")

    def read_notes(self, paths):
        result = {}
        for path in paths:
            body = self.notes.get(path)
            result[path] = ({"exists": True, "body": body, "sha256": digest(body)} if body is not None
                            else {"exists": False, "body": None, "sha256": None})
        return result

    def check_links(self, links, planned_paths):
        self.checked_links = list(links)
        return self.missing

    def apply(self, plan_path, plan_hash, operation_id):
        self.apply_calls += 1
        plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
        performed = []
        for index, note in enumerate(plan["notes"]):
            current = self.notes.get(note["path"])
            if current == note["body"]:
                continue
            if current is not None:
                self.notes[wiki_compile.backup_path(operation_id, note["path"])] = current
                performed.append(wiki_compile.backup_path(operation_id, note["path"]))
            self.notes[note["path"]] = note["body"]
            performed.append(note["path"])
            if self.fail_after == index + 1:
                return {"operation_id": operation_id, "status": "partial_failure", "performed_paths": performed,
                        "error": {"code": "injected_failure", "path": note["path"], "message": "test interruption"}}
        return {"operation_id": operation_id, "status": "applied" if performed else "noop", "performed_paths": performed}


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
        adapter = MemoryCLI(self.vault, self.initial)
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
        adapter = MemoryCLI(self.vault, {**self.initial, path: old_body})
        first = wiki_compile.run(self.args(apply=True), adapter)
        prior_path = wiki_compile.backup_path(self.plan["operation_id"], path)
        self.assertEqual(first["status"], "applied")
        self.assertEqual(adapter.notes[prior_path], old_body)
        second = wiki_compile.run(self.args(apply=True), adapter)
        self.assertEqual(second["status"], "noop")
        self.assertEqual(second["observed_changed_paths"], [])

    def test_source_change_blocks_apply(self):
        adapter = MemoryCLI(self.vault, {**self.initial, self.source: "new source body\n"})
        with self.assertRaises(source_snapshot.SnapshotError) as caught:
            wiki_compile.run(self.args(apply=True), adapter)
        self.assertEqual(caught.exception.code, "source_changed")
        self.assertEqual(adapter.apply_calls, 0)

    def test_unexpected_existing_target_conflicts(self):
        adapter = MemoryCLI(self.vault, {**self.initial, "wiki/concepts/idea.md": "someone else's note"})
        with self.assertRaises(source_snapshot.SnapshotError) as caught:
            wiki_compile.run(self.args(apply=True), adapter)
        self.assertEqual(caught.exception.code, "target_conflict")
        self.assertEqual(adapter.apply_calls, 0)

    def test_desired_body_is_noop_before_stale_expected_hash_check(self):
        desired = self.plan["notes"][0]["body"]
        self.plan["notes"][0]["expected_sha256"] = digest("old prior body")
        self.write_plan()
        adapter = MemoryCLI(self.vault, {**self.initial, "wiki/concepts/idea.md": desired})
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
        adapter = MemoryCLI(self.vault, self.initial, missing=[
            {"source": "wiki/concepts/idea.md", "target": "missing.md"},
        ])
        with self.assertRaises(source_snapshot.SnapshotError) as caught:
            wiki_compile.run(self.args(), adapter)
        self.assertEqual(caught.exception.code, "missing_link")
        self.assertIn({"source": "wiki/concepts/idea.md", "target": "missing.md"}, adapter.checked_links)

    def test_missing_wiki_link_blocks_apply(self):
        self.plan["notes"][0]["body"] += "\nSee [[Missing Concept]].\n"
        self.write_plan()
        adapter = MemoryCLI(self.vault, self.initial, missing=[{"source": "wiki/concepts/idea.md", "target": "Missing Concept"}])
        with self.assertRaises(source_snapshot.SnapshotError) as caught:
            wiki_compile.run(self.args(apply=True), adapter)
        self.assertEqual(caught.exception.code, "missing_link")
        self.assertEqual(adapter.apply_calls, 0)

    def test_partial_failure_reports_observed_and_performed_paths(self):
        self.plan["notes"].append({"path": "wiki/answers/answer.md", "expected_sha256": None,
                                   "body": "# Answer\n"})
        self.write_plan()
        adapter = MemoryCLI(self.vault, self.initial, fail_after=1)
        result = wiki_compile.run(self.args(apply=True), adapter)
        self.assertEqual(result["status"], "partial_failure")
        self.assertEqual(result["performed_paths"], ["wiki/concepts/idea.md"])
        self.assertEqual(result["observed_changed_paths"], ["wiki/concepts/idea.md"])
        self.assertFalse(result["ok"])

    def test_generated_apply_executes_with_fake_app_and_staged_source(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is required to execute generated Obsidian eval code")
        source_body = "The staged source body.\n"
        self.source = "raw/native-captures/selected.body"
        note_path = "wiki/concepts/idea.md"
        first_body = (
            "# Idea\n\n" +
            "Links: [hub](../../hubs/research.md), [escaped](Folder\\ Name.md), " +
            "[angle](<Space Note.md>), [encoded](Encoded%20Note.md), " +
            "[relative](../entities/entity.md).\n" +
            "Code: `[ignored](not-present.md)`\n\n```md\n[also ignored](not-present.md)\n```\n"
        )
        second_body = first_body + "\nUpdated from selected evidence.\n"
        bodies = {
            self.source: source_body,
            self.hub: "# Research\n",
            "wiki/concepts/Folder Name.md": "# Folder target\n",
            "wiki/concepts/Space Note.md": "# Angle-bracket target\n",
            "wiki/concepts/Encoded Note.md": "# Encoded target\n",
            "wiki/entities/entity.md": "# Entity target\n",
        }
        staged_plans = []

        def stage(plan):
            path = self.base / f"generated-{len(staged_plans)}.json"
            path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            staged_plans.append(path)
            plan_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            return wiki_compile.VaultCLI.apply_code(path, plan_hash)

        common = {
            "operation_id": "generated-test",
            "hub": self.hub,
            "sources": [{"path": self.source, "sha256": digest(source_body)}],
        }
        create_plan = {**common, "notes": [{"path": note_path, "expected_sha256": None, "body": first_body}]}
        update_plan = {**common, "notes": [{"path": note_path, "expected_sha256": digest(first_body), "body": second_body}]}
        broken_plan = {**common, "notes": [{"path": "wiki/concepts/broken.md", "expected_sha256": None,
                                               "body": "See [missing](not-present.md).\n"}]}
        codes = [stage(create_plan), stage(update_plan), stage(update_plan), stage(broken_plan)]
        app_fixture = f'''globalThis.app = (() => {{
  const bodies = new Map(Object.entries({json.dumps(bodies)}));
  const files = new Map();
  const folders = new Map();
  const writes = [];
  const addFolder = path => {{ if(!folders.has(path)) folders.set(path, {{path, children:[]}}); }};
  for (const [path, body] of bodies) {{
    const parts=path.split("/"); parts.pop(); let parent="";
    for(const part of parts){{parent=parent?parent+"/"+part:part;addFolder(parent);}}
    files.set(path, {{path, extension:path.split(".").pop()}});
  }}
  return {{
    writes,
    bodies,
    vault: {{
      adapter: {{getBasePath: () => {json.dumps(str(self.vault))}}},
      getAbstractFileByPath: path => files.get(path) || folders.get(path) || null,
      read: async file => bodies.get(file.path),
      createFolder: async path => {{if(files.has(path))throw new Error("folder conflict");addFolder(path);writes.push(["folder",path]);}},
      create: async (path, body) => {{if(files.has(path))throw new Error("file exists");const file={{path,extension:path.split(".").pop()}};files.set(path,file);bodies.set(path,body);writes.push(["create",path]);return file;}},
      modify: async (file, body) => {{bodies.set(file.path,body);writes.push(["modify",file.path]);}}
    }},
    metadataCache: {{getFirstLinkpathDest: () => null}}
  }};
}})();'''
        eval_calls = ",".join(f"JSON.parse(await eval({json.dumps(code)}))" for code in codes)
        wrapper = (
            "(async()=>{" + app_fixture +
            f"const receipts=[{eval_calls}];" +
            "const versionPath='raw/wiki-compile-versions/generated-test/concepts/idea.md.body';" +
            "process.stdout.write(JSON.stringify({receipts,writes:app.writes,version:app.bodies.get(versionPath),current:app.bodies.get('wiki/concepts/idea.md')}));" +
            "})().catch(error=>{console.error(String(error));process.exitCode=1;});"
        )
        completed = subprocess.run([node, "-e", wrapper], text=True, capture_output=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        create_receipt, update_receipt, repeat_receipt, broken_receipt = result["receipts"]
        self.assertEqual(create_receipt["status"], "applied")
        self.assertIn(note_path, create_receipt["performed_paths"])
        self.assertEqual(update_receipt["status"], "applied")
        version_path = "raw/wiki-compile-versions/generated-test/concepts/idea.md.body"
        self.assertIn(version_path, update_receipt["performed_paths"])
        self.assertEqual(result["version"], first_body)
        self.assertEqual(result["current"], second_body)
        self.assertEqual(repeat_receipt["status"], "noop")
        self.assertEqual(repeat_receipt["performed_paths"], [])
        self.assertEqual(broken_receipt["status"], "rejected")
        self.assertEqual(broken_receipt["error"]["code"], "missing_links")
        self.assertEqual(broken_receipt["performed_paths"], [])
        self.assertNotIn(["create", "wiki/concepts/broken.md"], result["writes"])


if __name__ == "__main__":
    unittest.main()
