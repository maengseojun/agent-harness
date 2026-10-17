import hashlib, json, os, tempfile, unittest, zipfile
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

    def test_personal_stub_carries_world_personal(self):
        self.note("raw/p.md", "hello\n")
        r = A.cmd_move("raw/p.md", "onedrive", "personal", False)
        self.assertIn("/maeng-archive/personal/", r["destination"])
        self.assertIn("world: personal", (self.vault / "raw/p.md").read_text())

    def test_world_path_mismatch_rejected(self):
        self.note("raw/p.md", "hello\n")
        self.note("eta/n.md", "hello\n")
        for rel, world in (("raw/p.md", "eta"), ("eta/n.md", "personal")):
            for dry in (True, False):
                with self.assertRaisesRegex(A.ArchiveError, "world/path mismatch"):
                    A.cmd_move(rel, "onedrive", world, dry)
        self.assertEqual((self.vault / "raw/p.md").read_text(), "hello\n")
        self.assertEqual((self.vault / "eta/n.md").read_text(), "hello\n")
        self.assertEqual(list(self.od.rglob("*")), [])

    def test_frontmatter_world_mismatch_rejected(self):
        self.note("raw/w.md", "---\nworld: eta\n---\nbody\n")
        with self.assertRaisesRegex(A.ArchiveError, "world mismatch"):
            A.cmd_move("raw/w.md", "onedrive", "personal", False)
        self.assertEqual(list(self.od.rglob("*")), [])

    def test_frontmatter_eta_outside_eta_dir_needs_world_eta(self):
        self.note("raw/w.md", "---\nworld: eta\n---\nbody\n")
        with self.assertRaisesRegex(A.ArchiveError, "world mismatch"):
            A.cmd_move("raw/w.md", "onedrive", "personal", False)
        r = A.cmd_move("raw/w.md", "onedrive", "eta", False)
        self.assertIn("/maeng-archive/eta/", r["destination"])

    def test_world_mismatch_cli_exit_nonzero(self):
        self.note("eta/n.md", "hello\n")
        with mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            self.assertEqual(A.main(["move", "eta/n.md", "--world", "personal"]), 1)
            self.assertEqual(A.main(["move", "eta/n.md", "--world", "eta", "--dry-run"]), 0)


class MovePrivateTests(Base):
    def test_move_refuses_private_note(self):
        p = self.note("raw/p.md", "hello <private>secret</private>\n")
        before = p.read_bytes()
        with self.assertRaises(A.ArchiveError) as cm:
            A.cmd_move("raw/p.md", "onedrive", "personal", False)
        self.assertIn("private", str(cm.exception))
        self.assertEqual(p.read_bytes(), before)
        self.assertFalse(list(self.od.rglob("p.md")))

    def test_move_refuses_private_even_dry_run_and_binary(self):
        b = self.vault / "f.bin"
        b.write_bytes(b"x< Private y")
        with self.assertRaises(A.ArchiveError):
            A.cmd_move("f.bin", "onedrive", "personal", True)
        self.assertTrue(b.exists())


class ExclusiveCopyTests(Base):
    def _src(self, data=b"twenty bytes of data"):
        s = self.home / "src.bin"
        s.write_bytes(data)
        return s

    def test_link_path_used_normally(self):
        d = self.od / "x" / "out.bin"
        self.assertEqual(A.copy_file(self._src(), d, exclusive=True), "link")
        self.assertEqual(d.read_bytes(), b"twenty bytes of data")

    def test_fallback_when_link_fails(self):
        import errno
        for code in (errno.EPERM, errno.ENOTSUP, errno.EXDEV, errno.EOPNOTSUPP):
            d = self.od / f"out{code}.bin"
            with mock.patch.object(A.os, "link", side_effect=OSError(code, "no link")):
                self.assertEqual(A.copy_file(self._src(), d, exclusive=True), "fallback")
            self.assertEqual(d.read_bytes(), b"twenty bytes of data")
            self.assertEqual([x.name for x in self.od.iterdir() if x.name.startswith(".tmp-archive-")], [])

    def test_fallback_never_overwrites(self):
        import errno
        d = self.od / "exists.bin"
        d.write_bytes(b"original")
        with mock.patch.object(A.os, "link", side_effect=OSError(errno.EPERM, "no link")):
            with self.assertRaises(FileExistsError):
                A.copy_file(self._src(), d, exclusive=True)
        self.assertEqual(d.read_bytes(), b"original")

    def test_link_fileexists_still_raised_and_no_fallback(self):
        d = self.od / "exists2.bin"
        d.write_bytes(b"original")
        with self.assertRaises(FileExistsError):
            A.copy_file(self._src(), d, exclusive=True)
        self.assertEqual(d.read_bytes(), b"original")

    def test_fallback_verification_failure_removes_partial(self):
        import errno
        d = self.od / "bad.bin"
        with mock.patch.object(A.os, "link", side_effect=OSError(errno.EPERM, "no link")), \
                mock.patch.object(A, "sha256_file", side_effect=["a", "b"]):
            with self.assertRaises(A.ArchiveError):
                A.copy_file(self._src(), d, exclusive=True)
        self.assertFalse(d.exists())


class SafetyTests(Base):
    def test_binary_move_refuses_existing_unrelated_stub(self):
        p = self.vault / "files" / "x.pdf"
        p.parent.mkdir()
        p.write_bytes(b"pdf-bytes")
        other = self.vault / "files" / "x.pdf.archived.md"
        other.write_text("my own note", encoding="utf-8")
        with self.assertRaises(A.ArchiveError):
            A.cmd_move("files/x.pdf", "onedrive", "personal", False)
        self.assertEqual(other.read_text(), "my own note")
        self.assertTrue(p.exists())
        self.assertFalse((self.od / A.ARCHIVE_DIR).exists())

    def test_binary_move_stub_with_same_hash_is_idempotent(self):
        p = self.vault / "files" / "x.pdf"
        p.parent.mkdir()
        p.write_bytes(b"pdf-bytes")
        meta = {"store": "onedrive", "path": "maeng-archive/personal/2026/files/x.pdf",
                "sha256": A.sha256_file(p), "size": 9, "archived_at": "2026-01-01T00:00:00+00:00"}
        (self.vault / "files" / "x.pdf.archived.md").write_text(
            A.build_stub(None, meta, "personal", "files/x.pdf"), encoding="utf-8")
        arch = self.od / meta["path"]
        arch.parent.mkdir(parents=True)
        arch.write_bytes(b"pdf-bytes")
        r = A.cmd_move("files/x.pdf", "onedrive", "personal", False)
        self.assertEqual(r["action"], "archived")
        self.assertFalse(p.exists())

    def test_binary_retry_preserves_populated_stub_byte_for_byte(self):
        p = self.vault / "files" / "x.pdf"
        p.parent.mkdir()
        p.write_bytes(b"pdf-bytes")
        meta = {"store": "onedrive", "path": "maeng-archive/personal/2026/files/x.pdf",
                "sha256": A.sha256_file(p), "size": 9, "archived_at": "2026-01-01T00:00:00+00:00"}
        stub = self.vault / "files" / "x.pdf.archived.md"
        stub.write_text(A.build_stub(None, meta, "personal", "files/x.pdf").replace(
            "<!-- agent: fill a 3-5 line summary of what was here and why it was archived -->",
            "Real summary. See [[other-note]]."), encoding="utf-8")
        before = stub.read_bytes()
        arch = self.od / meta["path"]
        arch.parent.mkdir(parents=True)
        arch.write_bytes(b"pdf-bytes")
        r = A.cmd_move("files/x.pdf", "onedrive", "personal", False)
        self.assertTrue(r["stub_preserved"])
        self.assertEqual(stub.read_bytes(), before)
        self.assertFalse(p.exists())

    def test_binary_retry_rejects_stub_path_outside_archive_root(self):
        p = self.vault / "files" / "x.pdf"
        p.parent.mkdir()
        p.write_bytes(b"pdf-bytes")
        outside = self.od / "elsewhere.bin"  # inside the store, outside maeng-archive/
        outside.write_bytes(b"pdf-bytes")
        meta = {"store": "onedrive", "path": "elsewhere.bin", "sha256": A.sha256_file(p),
                "size": 9, "archived_at": "2026-01-01T00:00:00+00:00"}
        stub = self.vault / "files" / "x.pdf.archived.md"
        stub.write_text(A.build_stub(None, meta, "personal", "files/x.pdf"), encoding="utf-8")
        for bad in ("elsewhere.bin", "maeng-archive/../elsewhere.bin"):
            meta["path"] = bad
            stub.write_text(A.build_stub(None, meta, "personal", "files/x.pdf"), encoding="utf-8")
            with self.assertRaises(A.ArchiveError) as cm:
                A.cmd_move("files/x.pdf", "onedrive", "personal", False)
            self.assertIn("archive root", str(cm.exception))
            self.assertTrue(p.exists())

    def test_md_edit_between_copy_and_stub_aborts(self):
        p = self.note("n.md", "original\n")

        def edit(src):
            src.write_text("original\nedited later\n", encoding="utf-8")

        with mock.patch.object(A, "_before_replace", edit):
            with self.assertRaises(A.ArchiveError) as cm:
                A.cmd_move("n.md", "onedrive", "personal", False)
        self.assertIn("changed during the move", str(cm.exception))
        self.assertEqual(p.read_text(), "original\nedited later\n")
        self.assertIsNone(A.parse_stub(p.read_text()))

    def test_binary_edit_between_copy_and_unlink_aborts(self):
        p = self.vault / "files" / "x.pdf"
        p.parent.mkdir()
        p.write_bytes(b"pdf-bytes")
        with mock.patch.object(A, "_before_replace", lambda src: src.write_bytes(b"pdf-bytes2")):
            with self.assertRaises(A.ArchiveError):
                A.cmd_move("files/x.pdf", "onedrive", "personal", False)
        self.assertEqual(p.read_bytes(), b"pdf-bytes2")
        self.assertFalse((self.vault / "files" / "x.pdf.archived.md").exists())

    def test_non_md_eta_capture_recognised_by_sidecar_world(self):
        raw = self.vault / "raw" / "aside"
        raw.mkdir(parents=True)
        (raw / "run.json").write_text(json.dumps({"nonce": "ab", "world": "eta"}), encoding="utf-8")
        (raw / "run.md").write_text("capture\n", encoding="utf-8")
        with self.assertRaises(A.ArchiveError):  # sidecar says eta: --world personal is a mismatch
            A.cmd_move("raw/aside/run.json", "onedrive", "personal", False)
        r = A.cmd_move("raw/aside/run.json", "onedrive", "eta", False)
        self.assertIn("/maeng-archive/eta/", r["destination"])
        self.assertFalse((raw / "run.json").exists())

    def test_md_capture_without_frontmatter_uses_sidecar_world(self):
        raw = self.vault / "raw" / "aside"
        raw.mkdir(parents=True)
        (raw / "run.json").write_text(json.dumps({"nonce": "ab", "world": "eta"}), encoding="utf-8")
        (raw / "run.md").write_text("capture\n", encoding="utf-8")
        with self.assertRaises(A.ArchiveError):
            A.cmd_move("raw/aside/run.md", "onedrive", "personal", False)
        r = A.cmd_move("raw/aside/run.md", "onedrive", "eta", False)
        self.assertIn("/maeng-archive/eta/", r["destination"])

    def test_retry_capture_finds_the_first_runs_sidecar_by_retry_nonce(self):
        raw = self.vault / "raw" / "aside"
        raw.mkdir(parents=True)
        (raw / "20261018-x-aaaa.json").write_text(json.dumps({"nonce": "bbbb", "world": "eta"}), encoding="utf-8")
        (raw / "20261018-x-bbbb-retry.md").write_text("capture\n", encoding="utf-8")
        with self.assertRaises(A.ArchiveError):
            A.cmd_move("raw/aside/20261018-x-bbbb-retry.md", "onedrive", "personal", False)
        r = A.cmd_move("raw/aside/20261018-x-bbbb-retry.md", "onedrive", "eta", False)
        self.assertIn("/maeng-archive/eta/", r["destination"])

    def test_non_md_without_sidecar_still_needs_eta_dir(self):
        p = self.vault / "files" / "x.pdf"
        p.parent.mkdir()
        p.write_bytes(b"pdf-bytes")
        with self.assertRaises(A.ArchiveError):
            A.cmd_move("files/x.pdf", "onedrive", "eta", False)
        self.assertTrue(p.exists())

    def test_binary_retry_aborts_when_archive_copy_missing_or_different(self):
        p = self.vault / "files" / "x.pdf"
        p.parent.mkdir()
        p.write_bytes(b"pdf-bytes")
        meta = {"store": "onedrive", "path": "maeng-archive/personal/2026/files/x.pdf",
                "sha256": A.sha256_file(p), "size": 9, "archived_at": "2026-01-01T00:00:00+00:00"}
        stub = self.vault / "files" / "x.pdf.archived.md"
        stub.write_text(A.build_stub(None, meta, "personal", "files/x.pdf"), encoding="utf-8")
        before = stub.read_bytes()
        with self.assertRaises(A.ArchiveError):
            A.cmd_move("files/x.pdf", "onedrive", "personal", False)
        arch = self.od / meta["path"]
        arch.parent.mkdir(parents=True)
        arch.write_bytes(b"different")
        with self.assertRaises(A.ArchiveError):
            A.cmd_move("files/x.pdf", "onedrive", "personal", False)
        self.assertTrue(p.exists())
        self.assertEqual(stub.read_bytes(), before)

    def test_move_rejects_symlinked_directory_outside_vault(self):
        outside = Path(self.td.name) / "outside"
        outside.mkdir()
        (outside / "n.md").write_text("external secret", encoding="utf-8")
        (self.vault / "raw").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(A.ArchiveError):
            A.cmd_move("raw/n.md", "onedrive", "personal", False)
        self.assertEqual((outside / "n.md").read_text(), "external secret")
        self.assertFalse((self.od / A.ARCHIVE_DIR).exists())

    def test_move_rejects_symlinked_file(self):
        outside = Path(self.td.name) / "ext.md"
        outside.write_text("ext", encoding="utf-8")
        (self.vault / "link.md").symlink_to(outside)
        with self.assertRaises(A.ArchiveError):
            A.cmd_move("link.md", "onedrive", "personal", False)
        self.assertEqual(outside.read_text(), "ext")

    def test_restore_rejects_symlinked_target_dir(self):
        self.note("wiki/old.md", "body\n")
        A.cmd_move("wiki/old.md", "onedrive", "personal", False)
        outside = Path(self.td.name) / "outside"
        outside.mkdir()
        (self.vault / "wiki").rename(self.vault / "wiki-real")
        (self.vault / "wiki").symlink_to(outside, target_is_directory=True)
        (outside / "old.md").write_text((self.vault / "wiki-real" / "old.md").read_text())
        with self.assertRaises(A.ArchiveError):
            A.cmd_restore("wiki/old.md", True, None)
        self.assertEqual(list(outside.glob("*.restored.md")), [])


class BackupSafetyTests(Base):
    def seed_old(self):
        old = self.od / A.BACKUP_DIR
        old.mkdir()
        for i in range(3):
            (old / f"maeng-2020010{i}-000000.zip").write_bytes(b"x")
        return old

    def test_missing_vault_errors_without_pruning(self):
        old = self.seed_old()
        with mock.patch.dict(os.environ, {"MAENG_VAULT": str(Path(self.td.name) / "nope")}):
            with self.assertRaises(A.ArchiveError):
                A.cmd_backup(["onedrive"], 1, False)
        self.assertEqual(len(list(old.glob("maeng-*.zip"))), 3)

    def test_empty_vault_errors_without_pruning(self):
        old = self.seed_old()
        with self.assertRaises(A.ArchiveError):
            A.cmd_backup(["onedrive"], 1, False)
        self.assertEqual(len(list(old.glob("maeng-*.zip"))), 3)

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root ignores chmod 000")
    def test_unreadable_directory_aborts_before_write_and_prune(self):
        old = self.seed_old()
        self.note("a.md", "A")
        bad = self.vault / "locked"
        bad.mkdir()
        (bad / "b.md").write_text("B", encoding="utf-8")
        bad.chmod(0)
        try:
            with self.assertRaises(A.ArchiveError):
                A.cmd_backup(["onedrive", "gdrive"], 1, False)
        finally:
            bad.chmod(0o755)
        self.assertEqual(len(list(old.glob("maeng-*.zip"))), 3)
        self.assertEqual(list((self.od / A.BACKUP_DIR).glob("maeng-2026*")), [])
        self.assertFalse((self.gd / A.BACKUP_DIR).exists())

    def test_missing_harness_root_reported_but_ok(self):
        self.note("a.md", "A")
        with mock.patch.dict(os.environ, {"MAENG_HOME": str(Path(self.td.name) / "nohome")}):
            r = A.cmd_backup(["onedrive"], 10, False)
        self.assertEqual(r["stores"]["onedrive"]["status"], "ok")
        self.assertFalse(r["harness_root"]["present"])

    def test_same_second_backups_both_kept(self):
        self.note("a.md", "A")
        fixed = A.now()
        with mock.patch.object(A, "now", return_value=fixed):
            r1 = A.cmd_backup(["onedrive"], 10, False)
            r2 = A.cmd_backup(["onedrive"], 10, False)
        z1, z2 = r1["stores"]["onedrive"]["zip"], r2["stores"]["onedrive"]["zip"]
        self.assertNotEqual(z1, z2)
        self.assertTrue(Path(z1).exists() and Path(z2).exists())

    def test_keep_one_retains_the_newest_same_second_backup(self):
        self.note("a.md", "A")
        fixed = A.now()
        with mock.patch.object(A, "now", return_value=fixed):
            A.cmd_backup(["onedrive"], 1, False)
            r2 = A.cmd_backup(["onedrive"], 1, False)
        newest = Path(r2["stores"]["onedrive"]["zip"])
        self.assertTrue(newest.exists(), "retention deleted the backup it just created")
        self.assertEqual(sorted(p.name for p in newest.parent.glob("maeng-*.zip")), [newest.name])

    def test_exclusive_copy_never_overwrites(self):
        src = Path(self.td.name) / "src.bin"
        src.write_bytes(b"new")
        dst = Path(self.td.name) / "dst.bin"
        dst.write_bytes(b"old")
        with self.assertRaises(FileExistsError):
            A.copy_file(src, dst, exclusive=True)
        self.assertEqual(dst.read_bytes(), b"old")
        self.assertEqual([p for p in dst.parent.iterdir() if p.name.startswith(".tmp-archive-")], [])

    def test_private_files_excluded_from_zip_and_listed(self):
        self.note("ok.md", "fine")
        sec = self.note("secret.md", "x <PRIVATE>hide</private> y")
        (self.home / "h.json").write_text('{"a": "<private>z"}')
        before = sec.read_bytes()
        r = A.cmd_backup(["onedrive"], 10, False)
        with zipfile.ZipFile(r["stores"]["onedrive"]["zip"]) as zf:
            names = zf.namelist()
            man = json.loads(zf.read("manifest.json"))
        self.assertIn("vault/ok.md", names)
        self.assertNotIn("vault/secret.md", names)
        self.assertNotIn("harness/h.json", names)
        self.assertEqual(sorted(man["excluded_private"]), ["harness/h.json", "vault/secret.md"])
        self.assertEqual(sec.read_bytes(), before)


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

    def test_restore_refuses_a_stub_path_outside_the_archive_root(self):
        self.note("n.md", "hello\n")
        A.cmd_move("n.md", "onedrive", "personal", False)
        stub = self.vault / "n.md"
        text = stub.read_text()
        self.assertIn("maeng-archive/", text)
        stub.write_text(text.replace("maeng-archive/", "maeng-archive/../elsewhere/", 1))
        with self.assertRaises(A.ArchiveError) as cm:
            A.cmd_restore(str(stub), True, None)
        self.assertIn("leaves the archive root", str(cm.exception))

    def test_restore_keeps_preexisting_tmp_file(self):
        self.note("n.md", "hello\n")
        A.cmd_move("n.md", "onedrive", "personal", False)
        pre = self.vault / ".tmp-restore-n.md"
        pre.write_bytes(b"precious\x00bytes")
        A.cmd_restore(str(self.vault / "n.md"), True, None)
        self.assertEqual(pre.read_bytes(), b"precious\x00bytes")
        self.assertEqual((self.vault / "n.md").read_text(), "hello\n")
        self.assertEqual(sorted(x.name for x in self.vault.glob(".tmp-restore-*")), [".tmp-restore-n.md"])

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



class BackupConsistencyTests(Base):
    def test_file_changing_after_read_stays_consistent(self):
        target = self.note("a.md", "original\n")
        self.note("b.md", "other\n")
        real = Path.read_bytes

        def racing(self_):
            data = real(self_)
            if self_ == target:
                target.write_text("changed after read\n")  # concurrent editor/sync
            return data
        with mock.patch.object(Path, "read_bytes", racing):
            r = A.cmd_backup(["onedrive"], 10, False)
        self.assertEqual(r["stores"]["onedrive"]["status"], "ok")
        with zipfile.ZipFile(r["stores"]["onedrive"]["zip"]) as zf:
            man = json.loads(zf.read("manifest.json"))
            entry = next(f for f in man["files"] if f["path"] == "vault/a.md")
            self.assertEqual(zf.read("vault/a.md"), b"original\n")
            self.assertEqual(entry["sha256"], hashlib.sha256(b"original\n").hexdigest())
            self.assertEqual(entry["size"], len(b"original\n"))
            self.assertEqual(zf.getinfo("vault/a.md").date_time[0] >= 1980, True)

    def test_verify_catches_corrupted_manifest_no_copy_no_prune(self):
        self.note("a.md", "hello\n")
        old = self.od / A.BACKUP_DIR
        old.mkdir()
        for i in range(3):
            (old / f"maeng-2020010{i}-000000.zip").write_bytes(b"x")
        real_build = A.build_backup_zip

        def bad_build(zp, stamp):
            m = real_build(zp, stamp)
            m["files"][0]["sha256"] = "0" * 64
            return m
        with mock.patch.object(A, "build_backup_zip", bad_build):
            with self.assertRaises(A.ArchiveError) as cm:
                A.cmd_backup(["onedrive"], 1, False)
        self.assertIn("differ from manifest", str(cm.exception))
        self.assertEqual(len(list(old.glob("maeng-*.zip"))), 3)  # not copied, not pruned
        self.assertEqual(len(list(old.glob("*.manifest.json"))), 0)

    def test_verify_catches_zip_member_tampered(self):
        self.note("a.md", "hello\n")
        with tempfile.TemporaryDirectory() as td:
            zp = Path(td) / "t.zip"
            m = A.build_backup_zip(zp, "s")
            A.verify_backup(zp, m)
            m["files"][0]["sha256"] = hashlib.sha256(b"different").hexdigest()
            with self.assertRaises(A.ArchiveError):
                A.verify_backup(zp, m)


class RestoreCwdTests(Base):
    def test_same_named_file_in_cwd_untouched(self):
        self.note("n.md", "hello\n")
        A.cmd_move("n.md", "onedrive", "personal", False)
        with tempfile.TemporaryDirectory() as cwd:
            decoy = Path(cwd) / "n.md"
            decoy.write_text("DECOY")
            (Path(cwd) / "n.restored.md").write_text("DECOY2")
            old = os.getcwd()
            os.chdir(cwd)
            try:
                r = A.cmd_restore("n.md", True, None)
            finally:
                os.chdir(old)
            self.assertEqual(decoy.read_text(), "DECOY")
            self.assertEqual((Path(cwd) / "n.restored.md").read_text(), "DECOY2")
            self.assertEqual(sorted(os.listdir(cwd)), ["n.md", "n.restored.md"])
        self.assertEqual(r["action"], "restored")
        self.assertEqual((self.vault / "n.md").read_text(), "hello\n")
        self.assertTrue((self.vault / "n.restored.md").exists())

    def test_relative_cwd_file_not_in_vault_not_found(self):
        with tempfile.TemporaryDirectory() as cwd:
            (Path(cwd) / "only-here.md").write_text("x")
            old = os.getcwd()
            os.chdir(cwd)
            try:
                with self.assertRaises(A.ArchiveError):
                    A.cmd_restore("only-here.md", False, None)
            finally:
                os.chdir(old)

    def test_absolute_path_outside_vault_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "n.md"
            f.write_text("x")
            with self.assertRaises(A.ArchiveError):
                A.cmd_restore(str(f), True, None)
            self.assertEqual(f.read_text(), "x")


class StubIdentityTests(Base):
    def test_markdown_named_archived_md_roundtrips(self):
        self.note("other.md", "see [[report.archived]]\n")
        self.note("report.archived.md", "---\nid: R\n---\nbody\n")
        A.cmd_move("report.archived.md", "onedrive", "personal", False)
        stub = self.vault / "report.archived.md"
        txt = stub.read_text()
        self.assertIn('stub_kind: "inplace"', txt)
        self.assertIn('original: "report.archived.md"', txt)
        r = A.cmd_restore("report.archived.md", True, None)
        self.assertEqual(Path(r["restore_to"]), (self.vault / "report.archived.md").resolve())
        self.assertIn("body", stub.read_text())
        self.assertFalse((self.vault / "report").exists())
        self.assertEqual((self.vault / "other.md").read_text(), "see [[report.archived]]\n")

    def test_sibling_metadata_and_restore(self):
        (self.vault / "d").mkdir()
        (self.vault / "d" / "x.bin").write_bytes(b"\x00")
        A.cmd_move("d/x.bin", "onedrive", "personal", False)
        txt = (self.vault / "d" / "x.bin.archived.md").read_text()
        self.assertIn('stub_kind: "sibling"', txt)
        self.assertIn('original: "d/x.bin"', txt)
        A.cmd_restore("d/x.bin.archived.md", True, None)
        self.assertEqual((self.vault / "d" / "x.bin").read_bytes(), b"\x00")

    def test_explicit_fields_must_match_location(self):
        self.note("a.md", "x\n")
        A.cmd_move("a.md", "onedrive", "personal", False)
        (self.vault / "a.md").rename(self.vault / "b.md")
        with self.assertRaises(A.ArchiveError):
            A.cmd_restore("b.md", True, None)

    def _legacy(self, rel, arch_rel):
        # write a stub without original/stub_kind pointing at a real archived copy
        data = b"legacy\n"
        dest = self.od / arch_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        meta = {"store": "onedrive", "path": arch_rel, "sha256": hashlib.sha256(data).hexdigest(),
                "size": len(data), "archived_at": "2026-01-01T00:00:00+00:00"}
        stub = A.build_stub(None, {**meta, "original": "", "stub_kind": ""}, "personal", rel)
        stub = stub.replace('  original: ""\n', "").replace('  stub_kind: ""\n', "")
        self.note(rel, stub)

    def test_legacy_inplace_md_named_archived_md_infers_inplace(self):
        self._legacy("report.archived.md", "maeng-archive/personal/2026/report.archived.md")
        r = A.cmd_restore("report.archived.md", False, None)
        self.assertEqual(Path(r["restore_to"]).name, "report.archived.md")

    def test_legacy_sibling_infers_sibling(self):
        self._legacy("x.bin.archived.md", "maeng-archive/personal/2026/x.bin")
        r = A.cmd_restore("x.bin.archived.md", False, None)
        self.assertEqual(Path(r["restore_to"]).name, "x.bin")

    def test_legacy_ambiguous_refused(self):
        self._legacy("report.archived.md", "maeng-archive/personal/2026/elsewhere.md")
        with self.assertRaises(A.ArchiveError):
            A.cmd_restore("report.archived.md", False, None)


class CliExitCodes(unittest.TestCase):
    def _env(self, t):
        return dict(os.environ, MAENG_VAULT=str(Path(t, "vault")), MAENG_ARCHIVE_ONEDRIVE=str(Path(t, "od")),
                    MAENG_ARCHIVE_GDRIVE=str(Path(t, "none")), MAENG_HOME=str(Path(t, "home")))

    def _run(self, env, *a):
        import subprocess, sys
        return subprocess.run([sys.executable, str(Path(__file__).with_name("archive.py")), *a],
                              env=env, capture_output=True, text=True)

    def test_backup_nonzero_when_store_copy_fails_but_prints_json(self):
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            Path(t, "vault").mkdir(); Path(t, "od").mkdir()
            Path(t, "vault", "n.md").write_text("hi\n")
            Path(t, "od", "maeng-backup").write_text("a file, so mkdir of the backup dir fails")
            r = self._run(self._env(t), "backup", "--to", "onedrive")
            self.assertEqual(r.returncode, 1)
            self.assertEqual(json.loads(r.stdout)["stores"]["onedrive"]["status"], "failed")

    def test_backup_nonzero_when_no_store_available(self):
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            Path(t, "vault").mkdir()
            Path(t, "vault", "n.md").write_text("hi\n")
            r = self._run(self._env(t), "backup", "--to", "gdrive")
            self.assertEqual(r.returncode, 1)
            self.assertIn("skipped", r.stdout)

    def test_move_and_restore_nonzero_on_error(self):
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            Path(t, "vault").mkdir(); Path(t, "od").mkdir()
            env = self._env(t)
            self.assertEqual(self._run(env, "move", "missing.md").returncode, 1)
            self.assertEqual(self._run(env, "restore", "missing.md").returncode, 1)


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


if __name__ == "__main__":
    unittest.main()
