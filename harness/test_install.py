from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import hashlib
import json
import multiprocessing
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from install import install


FIXTURE = {
    'SKILL.md': ('.agents/skills/harness-run/SKILL.md', b'Use scripts/run.py.\n'),
    'agents/openai.yaml': ('.agents/skills/harness-run/agents/openai.yaml', b'interface: {}\n'),
    'scripts/ledger.py': ('harness/ledger.py', b'def message(): return "snapshot v1"\n'),
    'scripts/run.py': ('harness/run.py', b'from ledger import message\nprint(message())\n'),
    'scripts/tool_hook.py': ('harness/tool_hook.py', b'from ledger import message\nimport run\ndef main(): print(message())\n'),
    'references/README.md': ('harness/README.md', b'Local harness reference.\n'),
    'references/NOTION-WORKSPACE.md': ('harness/NOTION-WORKSPACE.md', b'Canonical personal locators.\n'),
}


def preserved_metadata(path):
    state = path.lstat()
    # Reading a symlink can advance atime; retain all other tuple fields and ns precision.
    return (*state[:7], state.st_mtime_ns, state.st_ctime_ns)


class InstallTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / 'source'
        self.home = self.root / 'home'
        for source, data in FIXTURE.values():
            path = self.source / source
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    def links(self, home=None):
        return [(home or self.home) / name / 'skills/harness-run'
                for name in ('.agents', '.codex')]

    def assert_links(self, release, home=None):
        for link in self.links(home):
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(strict=True), release)

    def test_snapshot_manifest_and_idempotency(self):
        release = install(self.source, self.home)
        expected = {name: data for name, (_, data) in FIXTURE.items()}
        manifest = json.loads((release / 'manifest.json').read_text())
        self.assertEqual(manifest['files'], {
            name: hashlib.sha256(data).hexdigest() for name, data in expected.items()})
        self.assertEqual(manifest['release_id'], release.parent.name)
        self.assertEqual(release.parent.parent, self.home / '.local/share/agent-harness/releases')
        self.assert_links(release)
        for name, data in expected.items():
            self.assertFalse((release / name).is_symlink())
            self.assertEqual((release / name).read_bytes(), data)
        before = [preserved_metadata(path) for path in [release, *self.links()]]
        self.assertEqual(install(self.source, self.home), release)
        self.assertEqual([preserved_metadata(path) for path in [release, *self.links()]], before)
        other_home = self.root / 'other-home'
        self.assertEqual(install(self.source, other_home).parent.name, release.parent.name)

    def test_upgrade_preserves_old_release(self):
        old = install(self.source, self.home)
        before = {str(path.relative_to(old)): path.read_bytes()
                  for path in old.rglob('*') if path.is_file()}
        (self.source / 'harness/run.py').write_text('print("snapshot v2")\n')
        new = install(self.source, self.home)
        self.assertNotEqual(old, new)
        self.assert_links(new)
        self.assertEqual((new / 'scripts/run.py').read_text(), 'print("snapshot v2")\n')
        self.assertEqual({str(path.relative_to(old)): path.read_bytes()
                          for path in old.rglob('*') if path.is_file()}, before)

    def test_upgrade_accepts_previous_five_and_six_file_releases(self):
        from install import FILES
        for count in (5, 6):
            with self.subTest(count=count):
                home = self.root / f'previous-{count}'
                omitted = ['scripts/tool_hook.py']
                if count == 5:
                    omitted.append('references/NOTION-WORKSPACE.md')
                removed = {name: FILES.pop(name) for name in omitted}
                try:
                    prior = install(self.source, home)
                finally:
                    FILES.update(removed)
                upgraded = install(self.source, home)
                self.assertNotEqual(prior, upgraded)
                self.assert_links(upgraded, home)
                self.assertEqual(len(json.loads((prior / 'manifest.json').read_text())['files']), count)

    def test_conflicts_leave_both_entrypoints_untouched(self):
        outside = self.root / 'user-skill'
        outside.mkdir()
        (outside / 'note').write_text('user data')
        for index in (0, 1):
            for kind in ('file', 'directory', 'symlink', 'dangling'):
                with self.subTest(index=index, kind=kind):
                    home = self.root / f'home-{index}-{kind}'
                    old = install(self.source, home)
                    links = self.links(home)
                    conflict = links[index]
                    conflict.unlink()
                    if kind == 'file':
                        conflict.write_text('user data')
                    elif kind == 'directory':
                        conflict.mkdir()
                        (conflict / 'note').write_text('user data')
                    else:
                        conflict.symlink_to(outside if kind == 'symlink' else self.root / 'missing')
                    before = [preserved_metadata(link) for link in links]
                    runner = self.source / 'harness/run.py'
                    runner.write_bytes(runner.read_bytes() + b'# changed\n')
                    with self.assertRaisesRegex(ValueError, 'Unmanaged'):
                        install(self.source, home)
                    self.assertEqual([preserved_metadata(link) for link in links], before)
                    self.assertEqual(links[1 - index].resolve(), old)
                    if kind == 'file':
                        self.assertEqual(conflict.read_text(), 'user data')
                    elif kind == 'directory':
                        self.assertEqual((conflict / 'note').read_text(), 'user data')
                    else:
                        self.assertEqual(conflict.readlink(), outside if kind == 'symlink'
                                         else self.root / 'missing')
        self.assertEqual((outside / 'note').read_text(), 'user data')

    def test_changed_current_release_blocks_upgrade(self):
        release = install(self.source, self.home)
        (release / 'scripts/ledger.py').write_text('tampered')
        (self.source / 'harness/run.py').write_text('print("upgrade")\n')
        before = [preserved_metadata(link) for link in self.links()]
        with self.assertRaisesRegex(ValueError, 'managed release'):
            install(self.source, self.home)
        self.assertEqual([preserved_metadata(link) for link in self.links()], before)
        self.assertEqual((release / 'scripts/ledger.py').read_text(), 'tampered')

    def test_corrupt_unlinked_release_is_not_reused(self):
        release = install(self.source, self.home)
        for link in self.links():
            link.unlink()
        (release / 'manifest.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'managed release'):
            install(self.source, self.home)
        self.assertTrue(all(not link.exists() and not link.is_symlink() for link in self.links()))
        self.assertEqual((release / 'manifest.json').read_text(), '{}')

    def test_release_payload_symlink_is_rejected_even_with_matching_bytes(self):
        release = install(self.source, self.home)
        payload = release / 'scripts/run.py'
        payload.unlink()
        payload.symlink_to(self.source / 'harness/run.py')
        with self.assertRaisesRegex(ValueError, 'managed release'):
            install(self.source, self.home)
        self.assert_links(release)

    def test_package_survives_source_removal(self):
        release = install(self.source, self.home)
        renamed = self.source.with_name('renamed-source')
        self.source.rename(renamed)
        shutil.rmtree(renamed)
        for name, (_, data) in FIXTURE.items():
            self.assertEqual((release / name).read_bytes(), data)
        for link in self.links():
            result = subprocess.run([sys.executable, '-B', str(link / 'scripts/run.py')],
                                    cwd=self.home, capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout, 'snapshot v1\n')

    def test_missing_source_does_not_modify_entrypoints(self):
        old = install(self.source, self.home)
        (self.source / 'harness/run.py').unlink()
        with self.assertRaises(FileNotFoundError):
            install(self.source, self.home)
        self.assert_links(old)

    def test_concurrent_threads_and_processes(self):
        other_source = self.root / 'other-source'
        shutil.copytree(self.source, other_source)
        (other_source / 'harness/run.py').write_text('print("other snapshot")\n')
        sources = [self.source, other_source] * 4
        for kind in ('threads', 'processes'):
            with self.subTest(kind=kind):
                home = self.root / kind
                if kind == 'threads':
                    pool = ThreadPoolExecutor(max_workers=4)
                else:
                    pool = ProcessPoolExecutor(max_workers=4,
                                               mp_context=multiprocessing.get_context('spawn'))
                with pool:
                    jobs = [pool.submit(install, source, home) for source in sources]
                    releases = {job.result(timeout=30) for job in jobs}
                self.assertEqual(len(releases), 2)
                self.assertIn(self.links(home)[0].resolve(), releases)
                self.assert_links(self.links(home)[0].resolve(), home)
                for source in (self.source, other_source):
                    self.assertIn(install(source, home), releases)
                store = home / '.local/share/agent-harness/releases'
                self.assertEqual(set(store.iterdir()), {release.parent for release in releases})

    def test_cli_explicit_home(self):
        result = subprocess.run([
            sys.executable, '-B', str(Path(__file__).with_name('install.py')),
            '--source-root', str(self.source), '--home', str(self.home),
        ], cwd=self.root, capture_output=True, text=True, check=True)
        response = json.loads(result.stdout)
        self.assert_links(Path(response['path']))
        self.assertEqual(Path(response['path']).parent.name, response['release_id'])


if __name__ == '__main__':
    unittest.main()
