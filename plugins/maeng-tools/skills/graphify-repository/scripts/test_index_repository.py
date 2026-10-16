"""Offline tests: graphify is not installed; the worker is mocked."""
import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import index_repository as ir


def sh(cwd, *args):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True,
                   env={'PATH': '/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin', 'HOME': str(cwd),
                        'GIT_AUTHOR_NAME': 't', 'GIT_AUTHOR_EMAIL': 't@t', 'GIT_COMMITTER_NAME': 't',
                        'GIT_COMMITTER_EMAIL': 't@t'})


class IndexRepository(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name).resolve()
        self.repo = base / 'repo'
        (self.repo / 'src').mkdir(parents=True)
        (self.repo / 'docs').mkdir()
        (self.repo / 'src' / 'a.py').write_text('def a():\n    return 1\n')
        (self.repo / 'docs' / 'notes.md').write_text('x\n')
        sh(self.repo, 'git', 'init', '-q')
        sh(self.repo, 'git', 'add', '-A')
        sh(self.repo, 'git', 'commit', '-q', '-m', 'init')
        self.cache = base / 'cache'
        self.base = base
        self.calls = []

        def fake_worker(python, runtime, out):
            spec = json.loads((out / 'worker-input.json').read_text())
            self.calls.append(spec)
            (out / 'graph.json').write_text(json.dumps({'nodes': [{'id': 'a'}], 'edges': []}))
        p = mock.patch.object(ir, 'run_worker', fake_worker)
        p.start()
        self.addCleanup(p.stop)
        v = mock.patch.object(ir, 'verify_runtime', lambda runtime: ir.PIN_REVISION)
        v.start()
        self.addCleanup(v.stop)

    def run_index(self, out, *extra, include=('src',)):
        argv = ['--repo', str(self.repo), '--out', str(self.base / out), '--python', '/nonexistent/python',
                '--runtime', '/nonexistent/runtime', '--cache-root', str(self.cache)]
        for i in include:
            argv += ['--include', i]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ir.main(argv + list(extra))
        return json.loads(buf.getvalue())

    def test_bad_runtime_refuses_without_extraction_or_output(self):
        with mock.patch.object(ir, 'verify_runtime', side_effect=ValueError('refusing to extract')):
            with self.assertRaisesRegex(ValueError, 'refusing'):
                self.run_index('bad')
        self.assertEqual(self.calls, [])
        self.assertFalse((self.base / 'bad').exists())

    def test_snapshot_records_verified_revision(self):
        with mock.patch.object(ir, 'verify_runtime', lambda runtime: ir.PIN_REVISION) as _:
            self.run_index('ok')
        snap = json.loads((self.base / 'ok' / 'snapshot.json').read_text())
        self.assertEqual(snap['graphify_revision'], ir.PIN_REVISION)

    def test_pin_is_unchanged(self):
        self.assertEqual(ir.PIN_VERSION, '0.9.85')
        self.assertEqual(ir.PIN_REVISION, 'b4e6307bf170f27e0cb888c03f4af9308d531a42')

    def test_default_cache_root_is_persistent_and_per_repo(self):
        a = ir.default_cache_root(self.repo)
        self.assertEqual(a, ir.default_cache_root(self.repo))
        self.assertNotEqual(a, ir.default_cache_root(self.base))
        self.assertEqual(a.parent, ir.CACHE_BASE)
        self.assertIn('.cache/maeng/graphify', a.as_posix())

    def test_cache_root_is_outside_out_and_shared_between_runs(self):
        self.run_index('idx1')
        (self.repo / 'src' / 'a.py').write_text('def a():\n    return 2\n')
        self.run_index('idx2')
        self.assertEqual({c['cache'] for c in self.calls}, {str(self.cache)})
        self.assertTrue(self.cache.is_dir())
        self.assertFalse((self.base / 'idx1' / 'cache').exists())

    def test_reuse_when_unchanged(self):
        first = self.run_index('idx1')
        again = self.run_index('idx2', '--previous', first['snapshot'])
        self.assertTrue(again['reused'])
        self.assertEqual(len(self.calls), 1)
        self.assertFalse((self.base / 'idx2').exists())

    def test_out_dir_inside_repo_does_not_break_reuse(self):
        argv_out = 'repo/.idx1'
        first = self.run_index(argv_out)
        again = self.run_index('idx2', '--previous', first['snapshot'])
        self.assertTrue(again['reused'])

    def test_dirty_change_outside_scope_still_reuses(self):
        first = self.run_index('idx1')
        (self.repo / 'docs' / 'notes.md').write_text('changed\n')
        (self.repo / 'docs' / 'new-untracked.txt').write_text('u\n')
        again = self.run_index('idx2', '--previous', first['snapshot'])
        self.assertTrue(again['reused'])
        self.assertEqual(len(self.calls), 1)

    def test_in_scope_change_rebuilds(self):
        first = self.run_index('idx1')
        (self.repo / 'src' / 'a.py').write_text('def a():\n    return 3\n')
        again = self.run_index('idx2', '--previous', first['snapshot'])
        self.assertFalse(again['reused'])
        self.assertEqual(len(self.calls), 2)

    def test_in_scope_untracked_file_rebuilds(self):
        first = self.run_index('idx1')
        (self.repo / 'src' / 'b.py').write_text('def b():\n    pass\n')
        again = self.run_index('idx2', '--previous', first['snapshot'])
        self.assertFalse(again['reused'])

    def test_scoped_status_honors_excludes(self):
        (self.repo / 'src' / 'gen').mkdir()
        (self.repo / 'src' / 'gen' / 'g.py').write_text('x = 1\n')
        self.assertIn('gen/g.py', ir.scoped_status(self.repo, ['src'], []))
        self.assertEqual(ir.scoped_status(self.repo, ['src'], ['src/gen']), '')

    def test_snapshot_records_scope_and_pin(self):
        snap = json.loads(Path(self.run_index('idx1')['snapshot']).read_text())
        self.assertEqual(snap['graphify_version'], '0.9.85')
        self.assertEqual(snap['repository']['status_scope'], 'in-scope')
        self.assertEqual(snap['cache_root'], str(self.cache))

    def test_select_rejects_traversal_and_symlink(self):
        with self.assertRaises(ValueError):
            ir.select(self.repo, ['../x'], [])
        (self.repo / 'link').symlink_to(self.repo / 'src')
        with self.assertRaises(ValueError):
            ir.select(self.repo, ['link'], [])


class VerifyRuntime(unittest.TestCase):
    def make_runtime(self, extra=b''):
        d = Path(tempfile.mkdtemp())
        (d / 'graphify').mkdir()
        (d / 'graphify' / 'extract.py').write_bytes(b'print(1)\n' + extra)
        (d / 'pyproject.toml').write_text('[project]\nversion = "0.9.85"\n')
        return d

    def test_matching_source_manifest_ok(self):
        d = self.make_runtime()
        with mock.patch.object(ir, 'PIN_SOURCE_SHA256', ir.runtime_source_digest(d)):
            self.assertEqual(ir.verify_runtime(d), ir.PIN_REVISION)

    def test_modified_source_refused(self):
        d = self.make_runtime()
        pinned = ir.runtime_source_digest(d)
        (d / 'graphify' / 'extract.py').write_bytes(b'print(2)\n')
        with mock.patch.object(ir, 'PIN_SOURCE_SHA256', pinned):
            with self.assertRaisesRegex(ValueError, 'source digest'):
                ir.verify_runtime(d)

    def test_added_module_refused(self):
        d = self.make_runtime()
        pinned = ir.runtime_source_digest(d)
        (d / 'graphify' / 'extra.py').write_text('x = 1\n')
        with mock.patch.object(ir, 'PIN_SOURCE_SHA256', pinned):
            with self.assertRaisesRegex(ValueError, 'source digest'):
                ir.verify_runtime(d)

    def test_missing_package_refused(self):
        d = Path(tempfile.mkdtemp())
        with self.assertRaisesRegex(ValueError, 'no graphify'):
            ir.verify_runtime(d)

    def test_pycache_is_ignored(self):
        d = self.make_runtime()
        pinned = ir.runtime_source_digest(d)
        (d / 'graphify' / '__pycache__').mkdir()
        (d / 'graphify' / '__pycache__' / 'x.cpython-312.pyc').write_bytes(b'\0')
        with mock.patch.object(ir, 'PIN_SOURCE_SHA256', pinned):
            self.assertEqual(ir.verify_runtime(d), ir.PIN_REVISION)


if __name__ == '__main__':
    unittest.main()
