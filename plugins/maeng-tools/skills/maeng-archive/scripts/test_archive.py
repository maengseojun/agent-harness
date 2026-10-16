import json, os, tempfile, unittest, zipfile
from pathlib import Path
from unittest import mock

import archive as A


class Base(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        t = Path(self.td.name)
        self.vault, self.od, self.gd, self.home = t / "vault", t / "od", t / "gd", t / "home"
        for d in (self.vault, self.od, self.gd, self.home):
            d.mkdir()
        self.env = mock.patch.dict(os.environ, {
            "MAENG_VAULT": str(self.vault), "MAENG_ARCHIVE_ONEDRIVE": str(self.od),
            "MAENG_ARCHIVE_GDRIVE": str(self.gd), "MAENG_HOME": str(self.home)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.td.cleanup()

    def note(self, rel, text):
        p = self.vault / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p


class MoveTests(Base):
    def test_move_md_and_frontmatter_preserved(self):
        p = self.note("raw/a.md", "---\ntitle: A\ntags: [x]\nstatus: draft\n---\nbody text\n")
        orig = p.read_bytes()
        r = A.cmd_move("raw/a.md", "onedrive", "personal", False)
        self.assertEqual(r["action"], "archived")
        dest = Path(r["destination"])
        self.assertEqual(dest.read_bytes(), orig)
        stub = p.read_text(encoding="utf-8")
        self.assertIn("title: A", stub)
        self.assertIn("tags: [x]", stub)
        self.assertNotIn("status: draft", stub)
        self.assertIn("status: archived", stub)
        self.assertIn("## Summary", stub)
        meta = A.parse_stub(stub)
        self.assertEqual(meta["sha256"], A.sha256_file(dest))
        self.assertIn("maeng-archive/personal/", meta["path"])

    def test_move_non_md(self):
        p = self.vault / "files" / "x.pdf"
        p.parent.mkdir()
        p.write_bytes(b"%PDF data")
        A.cmd_move("files/x.pdf", "onedrive", "personal", False)
        self.assertFalse(p.exists())
        stub = self.vault / "files" / "x.pdf.archived.md"
        self.assertTrue(stub.exists())
        self.assertIsNotNone(A.parse_stub(stub.read_text(encoding="utf-8")))

    def test_hash_mismatch_aborts(self):
        p = self.note("n.md", "hello\n")
        before = p.read_bytes()
        def bad_copy(src, dst):
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(b"corrupt")
        with mock.patch.object(A, "copy_file", bad_copy):
            with self.assertRaises(A.ArchiveError):
                A.cmd_move("n.md", "onedrive", "personal", False)
        self.assertEqual(p.read_bytes(), before)

    def test_missing_store(self):
        p = self.note("n.md", "hello\n")
        with mock.patch.dict(os.environ, {"MAENG_ARCHIVE_GDRIVE": str(self.od / "nope")}):
            with self.assertRaises(A.ArchiveError):
                A.cmd_move("n.md", "gdrive", "personal", False)
        self.assertEqual(p.read_text(), "hello\n")

    def test_idempotent(self):
        self.note("n.md", "hello\n")
        A.cmd_move("n.md", "onedrive", "personal", False)
        stub1 = (self.vault / "n.md").read_text(encoding="utf-8")
        r = A.cmd_move("n.md", "onedrive", "personal", False)
        self.assertEqual(r["action"], "already-archived")
        self.assertEqual((self.vault / "n.md").read_text(encoding="utf-8"), stub1)

    def test_existing_dest_same_hash_ok_diff_hash_aborts(self):
        p = self.note("n.md", "hello\n")
        r = A.cmd_move("n.md", "onedrive", "personal", True)
        dest = Path(r["destination"])
        dest.parent.mkdir(parents=True)
        dest.write_text("other")
        with self.assertRaises(A.ArchiveError):
            A.cmd_move("n.md", "onedrive", "personal", False)
        self.assertEqual(p.read_text(), "hello\n")
        dest.write_text("hello\n")
        self.assertEqual(A.cmd_move("n.md", "onedrive", "personal", False)["action"], "archived")

    def test_dry_run_no_changes(self):
        p = self.note("n.md", "hello\n")
        r = A.cmd_move("n.md", "onedrive", "personal", True)
        self.assertEqual(r["action"], "dry-run")
        self.assertEqual(p.read_text(), "hello\n")
        self.assertEqual(list(self.od.rglob("*")), [])

    def test_eta_world(self):
        self.note("eta/n.md", "hello\n")
        r = A.cmd_move("eta/n.md", "onedrive", "eta", False)
        self.assertIn("/maeng-archive/eta/", r["destination"])
        self.assertIn("world: eta", (self.vault / "eta/n.md").read_text())


class BackupTests(Base):
    def test_backup_manifest_exclusions_and_prune(self):
        self.note("a.md", "A")
        self.note(".obsidian/workspace.json", "{}")
        self.note(".obsidian/app.json", "{}")
        self.note(".trash/t.md", "t")
        self.note("sub/.DS_Store", "x")
        (self.home / "state.json").write_text("{}")
        old = self.od / A.BACKUP_DIR
        old.mkdir()
        for i in range(3):
            (old / f"maeng-2020010{i}-000000.zip").write_bytes(b"x")
            (old / f"maeng-2020010{i}-000000.manifest.json").write_text("{}")
        r = A.cmd_backup(["onedrive", "gdrive"], 2, False)
        self.assertEqual(r["stores"]["onedrive"]["status"], "ok")
        z = Path(r["stores"]["onedrive"]["zip"])
        with zipfile.ZipFile(z) as zf:
            names = set(zf.namelist())
            self.assertIn("vault/a.md", names)
            self.assertIn("vault/.obsidian/app.json", names)
            self.assertIn("harness/state.json", names)
            self.assertNotIn("vault/.obsidian/workspace.json", names)
            self.assertFalse(any(".trash" in n or ".DS_Store" in n for n in names))
            man = json.loads(zf.read("manifest.json"))
        self.assertEqual(man["file_count"], len(man["files"]))
        self.assertTrue((z.with_suffix(".manifest.json")).exists())
        self.assertEqual(len(list(old.glob("maeng-*.zip"))), 2)
        self.assertEqual(len(list(old.glob("maeng-*.manifest.json"))), 2)
        self.assertEqual(r["stores"]["gdrive"]["status"], "ok")

    def test_missing_gdrive_reported(self):
        self.note("a.md", "A")
        with mock.patch.dict(os.environ, {"MAENG_ARCHIVE_GDRIVE": str(self.od / "nope")}):
            r = A.cmd_backup(["onedrive", "gdrive"], 10, False)
        self.assertEqual(r["stores"]["gdrive"]["status"], "skipped")
        self.assertEqual(r["stores"]["onedrive"]["status"], "ok")

    def test_backup_dry_run(self):
        self.note("a.md", "A")
        r = A.cmd_backup(["onedrive"], 10, True)
        self.assertEqual(r["stores"]["onedrive"]["status"], "dry-run")
        self.assertFalse((self.od / A.BACKUP_DIR).exists())

    def test_status(self):
        with mock.patch.dict(os.environ, {"MAENG_ARCHIVE_GDRIVE": str(self.od / "nope")}):
            st = A.cmd_status()
        self.assertTrue(st["stores"]["onedrive"]["found"])
        self.assertFalse(st["stores"]["gdrive"]["found"])


class RestoreTests(Base):
    def test_restore_stub_dry_then_apply(self):
        self.note("n.md", "hello\n")
        A.cmd_move("n.md", "onedrive", "personal", False)
        stub = self.vault / "n.md"
        r = A.cmd_restore(str(stub), False, None)
        self.assertEqual(r["action"], "dry-run")
        self.assertIn("status: archived", stub.read_text())
        r = A.cmd_restore(str(stub), True, None)
        self.assertEqual(r["action"], "restored")
        self.assertEqual(stub.read_text(), "hello\n")
        self.assertTrue((self.vault / "n.restored.md").exists())

    def test_restore_non_md_stub(self):
        (self.vault / "x.bin").write_bytes(b"\x00\x01")
        A.cmd_move("x.bin", "onedrive", "personal", False)
        A.cmd_restore(str(self.vault / "x.bin.archived.md"), True, None)
        self.assertEqual((self.vault / "x.bin").read_bytes(), b"\x00\x01")

    def test_restore_zip(self):
        self.note("a.md", "A")
        r = A.cmd_backup(["onedrive"], 10, False)
        z = r["stores"]["onedrive"]["zip"]
        d = A.cmd_restore(z, False, None)
        self.assertEqual(d["action"], "dry-run")
        with self.assertRaises(A.ArchiveError):
            A.cmd_restore(z, True, None)
        with self.assertRaises(A.ArchiveError):
            A.cmd_restore(z, True, str(self.vault / "sub"))
        tgt = Path(self.td.name) / "target"
        A.cmd_restore(z, True, str(tgt))
        self.assertEqual((tgt / "vault/a.md").read_text(), "A")


if __name__ == "__main__":
    unittest.main()


class CliRoundTrip(unittest.TestCase):
    """Drives the real CLI (main) so argument wiring is covered, not only cmd_* functions."""

    def test_move_then_restore_with_vault_relative_paths(self):
        import os, subprocess, sys, tempfile
        script = str(Path(__file__).with_name("archive.py"))
        with tempfile.TemporaryDirectory() as t:
            vault, od = Path(t, "vault"), Path(t, "od")
            (vault / "wiki").mkdir(parents=True)
            od.mkdir()
            note = vault / "wiki" / "old.md"
            note.write_text("---\nid: X\n---\nbody\n", encoding="utf-8")
            env = dict(os.environ, MAENG_VAULT=str(vault), MAENG_ARCHIVE_ONEDRIVE=str(od),
                       MAENG_ARCHIVE_GDRIVE=str(Path(t, "none")), MAENG_HOME=str(Path(t, "home")))
            run = lambda *a: subprocess.run([sys.executable, script, *a], env=env, capture_output=True, text=True)
            self.assertEqual(run("move", "wiki/old.md").returncode, 0)
            self.assertIn("status: archived", note.read_text(encoding="utf-8"))
            dry = run("restore", "wiki/old.md")
            self.assertEqual(dry.returncode, 0, dry.stderr)
            self.assertIn("dry-run", dry.stdout)
            self.assertEqual(run("restore", "wiki/old.md", "--apply").returncode, 0)
            self.assertIn("body", note.read_text(encoding="utf-8"))
            self.assertEqual(run("backup", "--to", "onedrive,gdrive").returncode, 0)
            self.assertTrue(list((od / "maeng-backup").glob("maeng-*.zip")))
