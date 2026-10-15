"""Focused MCP source-boundary, cache ownership and freshness checks."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import qmd_search as search


class FakeVault:
    def __init__(self, root, *, fail_read=None):
        self.expected_vault = Path(root)
        self.calls = []
        self.fail_read = fail_read

    def __enter__(self):
        self.calls.append(('connect',))
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.calls.append(('close',))

    def list_directory(self, path=''):
        self.calls.append(('list_directory', path))
        target = self.expected_vault / path if path else self.expected_vault
        dirs = sorted(p.name for p in target.iterdir() if p.is_dir())
        files = sorted(p.name for p in target.iterdir() if not p.is_dir())
        return {'dirs': dirs, 'files': files}

    def read_note_lines(self, path):
        self.calls.append(('read_note_lines', path, 1, 2_147_483_647))
        if path == self.fail_read:
            raise RuntimeError('fixture source read failed')
        return (self.expected_vault / path).read_bytes().decode('utf-8')


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'vault'
        (self.root / 'wiki' / 'sources').mkdir(parents=True)
        (self.root / 'hubs' / 'courses').mkdir(parents=True)
        self.source = self.root / 'wiki' / 'sources' / 'course.md'
        self.body = '---\ntitle: Original\ncomment: keep this YAML order\n---\n# Course\nEvidence\n'
        self.source.write_bytes(self.body.encode('utf-8'))
        self.hub = self.root / 'hubs' / 'courses' / 'course.md'
        self.hub.write_bytes(b'# Course hub\n')
        self.fake = FakeVault(self.root)
        self.patches = [
            patch.object(search, 'EXPECTED_VAULT', self.root),
            patch.object(search, 'MCPVault', lambda **kwargs: self.fake),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def tearDown(self):
        self.temp.cleanup()

    def isolated_runtime(self):
        import tempfile
        return Path(tempfile.mkdtemp(dir=self.temp.name))

    def test_scope_excludes_hidden_synthetic_config_traversal_and_non_markdown(self):
        for path in ['raw/a.md', '.obsidian/private.md', 'templates/a.md', 'wiki/../secret.md',
                     'wiki/SYN-X.md', 'wiki/.hidden.md', '/wiki/x.md', 'wiki/a.markdown']:
            self.assertFalse(search.eligible(path), path)
        self.assertTrue(search.eligible('wiki/sources/언어와 인공지능.md'))

    def test_export_reads_raw_markdown_and_hashes_exact_source_bytes(self):
        rows = search.export_notes(['wiki/sources/course.md'])
        self.assertEqual(rows, [{'path': 'wiki/sources/course.md', 'body': self.body}])
        self.assertIn(('read_note_lines', 'wiki/sources/course.md', 1, 2_147_483_647), self.fake.calls)
        self.assertNotIn(('read_note', 'wiki/sources/course.md'), self.fake.calls)
        self.assertEqual(self.source.read_bytes(), self.body.encode('utf-8'))

    def test_enumeration_is_bounded_and_omits_hidden_synthetic_and_out_of_scope_paths(self):
        (self.root / 'wiki' / 'sources' / 'SYN-sample.md').write_text('synthetic')
        (self.root / 'wiki' / 'sources' / '.hidden.md').write_text('hidden')
        (self.root / 'wiki' / 'sources' / 'notes.txt').write_text('not a note')
        (self.root / 'raw').mkdir()
        (self.root / 'raw' / 'input.md').write_text('raw')
        rows = search.export_notes()
        self.assertEqual({row['path'] for row in rows}, {'wiki/sources/course.md', 'hubs/courses/course.md'})
        self.assertFalse(any('raw/' in call[1] for call in self.fake.calls if call[0] == 'list_directory'))
        self.assertFalse(any('.hidden' in call[1] or 'SYN-' in call[1] for call in self.fake.calls if call[0] == 'read_note_lines'))

    def test_bad_selected_path_and_symlinked_note_are_rejected(self):
        with self.assertRaises(ValueError):
            search.export_notes(['wiki/../outside.md'])
        outside = Path(self.temp.name) / 'outside.md'
        outside.write_text('outside')
        link = self.root / 'wiki' / 'sources' / 'linked.md'
        link.symlink_to(outside)
        with self.assertRaises(Exception):
            search.export_notes(['wiki/sources/linked.md'])
        self.assertEqual(outside.read_text(), 'outside')

    def test_mcp_failure_stops_before_cache_mutation_or_qmd(self):
        broken = FakeVault(self.root, fail_read='wiki/sources/course.md')
        with patch.object(search, 'MCPVault', lambda **kwargs: broken), patch.object(search, 'RUNTIME', self.isolated_runtime()), patch.object(search, 'qmd') as qmd:
            original = self.source.read_bytes()
            with self.assertRaises(RuntimeError):
                search.refresh('course', ['wiki/sources/course.md'])
            qmd.assert_not_called()
            self.assertEqual(self.source.read_bytes(), original)
            self.assertFalse((Path(search.RUNTIME) / 'snapshots' / 'course').exists())

    def test_partial_mcp_read_failure_preserves_the_previous_snapshot(self):
        second = self.root / 'wiki' / 'sources' / 'second.md'
        second.write_text('# second\n', encoding='utf-8')
        broken = FakeVault(self.root, fail_read='wiki/sources/second.md')
        runtime = self.isolated_runtime()
        directory = runtime / 'snapshots' / 'course'
        directory.mkdir(parents=True)
        previous_body = b'previous managed snapshot\n'
        previous_file = 'n-' + search.digest(b'wiki/sources/course.md') + '.md'
        (directory / previous_file).write_bytes(previous_body)
        previous_manifest = {
            'collection': 'course', 'vault': str(self.root), 'indexed': True,
            'exported_at': 'before',
            'notes': [{'file': previous_file, 'vault_path': 'wiki/sources/course.md', 'sha256': search.digest(previous_body)}],
        }
        manifest_path = directory / 'manifest.json'
        manifest_path.write_text(json.dumps(previous_manifest), encoding='utf-8')
        with patch.object(search, 'MCPVault', lambda **kwargs: broken), patch.object(search, 'RUNTIME', runtime), patch.object(search, 'qmd') as qmd:
            with self.assertRaises(RuntimeError):
                search.refresh('course', ['wiki/sources/course.md', 'wiki/sources/second.md'])
            qmd.assert_not_called()
        self.assertEqual((directory / previous_file).read_bytes(), previous_body)
        self.assertEqual(json.loads(manifest_path.read_text()), previous_manifest)
        self.assertEqual(self.source.read_bytes(), self.body.encode('utf-8'))

    def test_changed_source_is_stale_and_collection_escape_is_rejected(self):
        runtime = self.isolated_runtime()
        directory = runtime / 'snapshots' / 'course'
        directory.mkdir(parents=True)
        old_hash = search.digest(b'old')
        (directory / 'manifest.json').write_text(json.dumps({
            'collection': 'course', 'vault': str(self.root), 'indexed': True,
            'exported_at': 'test', 'notes': [{'file': 'n-test.md', 'vault_path': 'wiki/sources/course.md', 'sha256': old_hash}],
        }))
        with patch.object(search, 'RUNTIME', runtime), patch.object(search, 'validate_vault_root'):
            with patch.object(search, 'qmd', return_value='[{"file":"qmd://course/n-test.md?index=obsidian"}]'):
                result = search.search('course', 'question', 'vector')
            self.assertFalse(result[0]['fresh'])
            self.assertEqual(result[0]['vault_path'], 'wiki/sources/course.md')
            with patch.object(search, 'qmd', return_value='[{"file":"qmd://other/n-test.md"}]'):
                with self.assertRaises(RuntimeError):
                    search.search('course', 'question', 'vector')
            with patch.object(search, 'qmd', return_value='[{"file":"qmd://course/n-test.md?index=other"}]'):
                with self.assertRaises(RuntimeError):
                    search.search('course', 'question', 'vector')
            with self.assertRaises(ValueError):
                search.snapshot_directory('../escape')

    def test_repeated_refresh_reuses_snapshot_and_detects_external_cache_edits(self):
        runtime = self.isolated_runtime()
        with patch.object(search, 'RUNTIME', runtime), patch.object(search, 'qmd', return_value='qmd://wiki/'):
            search.refresh('wiki', ['wiki/sources/course.md'])
            note = next((runtime / 'snapshots/wiki').glob('*.md'))
            timestamp = note.stat().st_mtime_ns
            search.refresh('wiki', ['wiki/sources/course.md'])
            self.assertEqual(note.stat().st_mtime_ns, timestamp)
            note.write_text('edited outside the helper', encoding='utf-8')
            with self.assertRaises(RuntimeError):
                search.refresh('wiki', ['wiki/sources/course.md'])
            self.assertEqual(note.read_text(), 'edited outside the helper')
            self.assertEqual(self.source.read_bytes(), self.body.encode('utf-8'))

    def test_symlinked_collection_and_manifest_do_not_change_outside_files(self):
        runtime = self.isolated_runtime()
        (runtime / 'snapshots').mkdir()
        outside = runtime / 'other'
        outside.mkdir()
        (outside / 'manifest.json').write_text('preserve')
        link = runtime / 'snapshots/wiki'
        link.symlink_to(outside, target_is_directory=True)
        with patch.object(search, 'RUNTIME', runtime):
            with self.assertRaises(RuntimeError):
                search.refresh('wiki', ['wiki/sources/course.md'])
            link.unlink()
            link.mkdir()
            (link / 'manifest.json').symlink_to(outside / 'manifest.json')
            with self.assertRaises(RuntimeError):
                search.refresh('wiki', ['wiki/sources/course.md'])
        self.assertEqual((outside / 'manifest.json').read_text(), 'preserve')

    def test_failed_or_partial_embedding_stays_unready(self):
        for embedding in ('embedding failed', '176 chunks still failed after retries', 'Another embed process is already running. Skipping.'):
            with self.subTest(embedding=embedding):
                runtime = self.isolated_runtime()
                def fake_qmd(*args):
                    if args[0] == 'embed':
                        if embedding == 'embedding failed':
                            raise RuntimeError(embedding)
                        return embedding
                    return 'qmd://wiki/'
                with patch.object(search, 'RUNTIME', runtime), patch.object(search, 'qmd', side_effect=fake_qmd):
                    with self.assertRaises(RuntimeError):
                        search.refresh('wiki', ['wiki/sources/course.md'])
                manifest = json.loads((runtime / 'snapshots/wiki/manifest.json').read_text())
                self.assertFalse(manifest['indexed'])
                self.assertEqual(self.source.read_bytes(), self.body.encode('utf-8'))

    def test_qmd_process_route_is_local_and_obsidian_cli_is_not_a_dependency(self):
        module = Path(search.__file__).read_text(encoding='utf-8')
        for forbidden in ('source_snapshot', 'assert_cli_vault', 'invoke_obsidian', 'Obsidian.app', "'eval'"):
            self.assertNotIn(forbidden, module)
        class Result:
            stdout = 'ok'
        with patch.object(search.qmd_subprocess, 'run', return_value=Result()) as run:
            self.assertEqual(search.qmd('search', 'question'), 'ok')
        command = run.call_args.args[0]
        self.assertEqual(command[0], str(search.QMD))
        self.assertEqual(command[0], str(search.QMD))
        self.assertFalse(any(str(arg).startswith('/Applications/Obsidian.app') for arg in command))


if __name__ == '__main__':
    unittest.main()
