"""Focused source-boundary, stale-result and snapshot ownership checks."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import qmd_search as search


class SearchTests(unittest.TestCase):
    def test_note_scope_excludes_raw_config_traversal_and_synthetic(self):
        for path in ['raw/a.md', '.obsidian/private.md', 'templates/a.md', 'wiki/../secret.md', 'wiki/SYN-X.md', '/wiki/x.md']:
            self.assertFalse(search.eligible(path), path)
        self.assertTrue(search.eligible('wiki/sources/언어와 인공지능.md'))

    def test_wrong_cli_vault_stops_before_note_export(self):
        with patch.object(search, 'assert_cli_vault', side_effect=RuntimeError('wrong vault')), patch.object(search, 'evaluate') as evaluate:
            with self.assertRaises(RuntimeError):
                search.export_notes()
            evaluate.assert_not_called()

    def test_changed_source_is_stale_and_collection_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(search, 'RUNTIME', Path(temp)), patch.object(search, 'assert_cli_vault'):
            path = Path(temp) / 'snapshots/course'
            path.mkdir(parents=True)
            (path / 'manifest.json').write_text(json.dumps({'collection': 'course', 'vault': str(search.EXPECTED_VAULT), 'indexed': True, 'exported_at': 'test', 'notes': [{'file': 'n-test.md', 'vault_path': 'wiki/source.md', 'sha256': search.digest(b'old')}]}))
            with patch.object(search, 'qmd', return_value='[{"file":"qmd://course/n-test.md?index=obsidian"}]'), patch.object(search, 'export_notes', return_value=[{'path': 'wiki/source.md', 'body': 'new'}]):
                result = search.search('course', 'question', 'vector')
                self.assertFalse(result[0]['fresh'])
                self.assertEqual(result[0]['vault_path'], 'wiki/source.md')
            with patch.object(search, 'qmd', return_value='[{"file":"qmd://other/n-test.md"}]'):
                with self.assertRaises(RuntimeError):
                    search.search('course', 'question', 'vector')
            with patch.object(search, 'qmd', return_value='[{"file":"qmd://course/n-test.md?index=other"}]'):
                with self.assertRaises(RuntimeError):
                    search.search('course', 'question', 'vector')

    def test_repeated_snapshot_reuses_content_and_detects_external_edits(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(search, 'RUNTIME', Path(temp)), patch.object(search, 'export_notes', return_value=[{'path': 'wiki/source.md', 'body': 'same'}]), patch.object(search, 'qmd', return_value='qmd://wiki/'):
            search.refresh('wiki', None)
            note = next((Path(temp) / 'snapshots/wiki').glob('*.md'))
            timestamp = note.stat().st_mtime_ns
            search.refresh('wiki', None)
            self.assertEqual(note.stat().st_mtime_ns, timestamp)
            note.write_text('edited outside the helper')
            with self.assertRaises(RuntimeError):
                search.refresh('wiki', None)
            self.assertEqual(note.read_text(), 'edited outside the helper')

    def test_symlinked_collection_and_manifest_do_not_change_other_files(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(search, 'RUNTIME', Path(temp)), patch.object(search, 'export_notes', return_value=[]):
            base = Path(temp)
            (base / 'snapshots').mkdir()
            outside = base / 'other'
            outside.mkdir()
            (outside / 'manifest.json').write_text('preserve')
            link = base / 'snapshots/wiki'
            link.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(RuntimeError):
                search.refresh('wiki', None)
            link.unlink()
            link.mkdir()
            (link / 'manifest.json').symlink_to(outside / 'manifest.json')
            with self.assertRaises(RuntimeError):
                search.refresh('wiki', None)
            self.assertEqual((outside / 'manifest.json').read_text(), 'preserve')

    def test_refresh_embeds_changes_and_failed_embedding_stays_unready(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(search, 'RUNTIME', Path(temp)), patch.object(search, 'export_notes', return_value=[{'path': 'wiki/source.md', 'body': 'new'}]):
            calls = []
            def fake_qmd(*args):
                calls.append(args)
                if args[0] == 'embed':
                    raise RuntimeError('embedding failed')
                return 'qmd://wiki/'
            with patch.object(search, 'qmd', side_effect=fake_qmd):
                with self.assertRaises(RuntimeError):
                    search.refresh('wiki', None)
            manifest = json.loads((Path(temp) / 'snapshots/wiki/manifest.json').read_text())
            self.assertFalse(manifest['indexed'])
            self.assertTrue(any(args[0] == 'embed' for args in calls))

    def test_success_exit_with_failed_chunks_is_not_vector_ready(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(search, 'RUNTIME', Path(temp)), patch.object(search, 'export_notes', return_value=[{'path': 'wiki/source.md', 'body': 'new'}]):
            def fake_qmd(*args):
                return '176 chunks still failed after retries' if args[0] == 'embed' else 'qmd://wiki/'
            with patch.object(search, 'qmd', side_effect=fake_qmd):
                with self.assertRaises(RuntimeError):
                    search.refresh('wiki', None)
            self.assertFalse(json.loads((Path(temp) / 'snapshots/wiki/manifest.json').read_text())['indexed'])

    def test_busy_embedding_skip_is_not_vector_ready(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(search, 'RUNTIME', Path(temp)), patch.object(search, 'export_notes', return_value=[{'path': 'wiki/source.md', 'body': 'new'}]):
            def fake_qmd(*args):
                return 'Another embed process is already running. Skipping.' if args[0] == 'embed' else 'qmd://wiki/'
            with patch.object(search, 'qmd', side_effect=fake_qmd):
                with self.assertRaises(RuntimeError):
                    search.refresh('wiki', None)
            self.assertFalse(json.loads((Path(temp) / 'snapshots/wiki/manifest.json').read_text())['indexed'])


if __name__ == '__main__':
    unittest.main()
