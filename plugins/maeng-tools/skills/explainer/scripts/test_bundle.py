import importlib.util
import json
import shutil
import tempfile
import unittest
from unittest import mock
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, BASE / 'scripts' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


checker, installer = module('check_references'), module('install_bundle')


class BundleChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        for name in ('explainer', 'diagram-explainer'):
            shutil.copytree(BASE.parent / name, self.source / name, ignore=shutil.ignore_patterns('__pycache__'))

    def tearDown(self):
        self.temp.cleanup()

    def test_reference_failures_do_not_become_success(self):
        skill = self.source / 'explainer'
        self.assertFalse(checker.check(skill, 'text')['blocked'])
        required = skill / 'references/explanation-design.md'
        content = required.read_bytes()
        required.unlink()
        self.assertTrue(checker.check(skill, 'text')['blocked'])
        required.write_bytes(content + b'\nChanged outside reviewed revision\n')
        self.assertTrue(checker.check(skill, 'text')['blocked'])
        required.write_bytes(content)
        optional = self.source / 'diagram-explainer/assets/example-timeline.html'
        optional.unlink()
        result = checker.check(skill, 'diagram')
        self.assertFalse(result['blocked'])
        self.assertTrue(any(x['state'] == 'optional_missing' for x in result['references']))

    def test_original_design_and_personal_delivery_are_required(self):
        skill = self.source / 'explainer'
        for relative in (
            'references/style-guide.md', 'references/output-spec.md',
            'references/personal-additions.md', 'references/delivery-storage.md',
            'LICENSE.txt',
        ):
            path = self.source / 'diagram-explainer' / relative
            content = path.read_bytes()
            path.unlink()
            self.assertTrue(checker.check(skill, 'diagram')['blocked'], relative)
            self.assertFalse(checker.check(skill, 'text')['blocked'])
            path.write_bytes(content + b'\nUnreviewed change\n')
            self.assertTrue(checker.check(skill, 'diagram')['blocked'], relative)
            path.write_bytes(content)
        self.assertFalse(checker.check(skill, 'diagram')['blocked'])

    def test_reinstall_preserves_user_files_and_restores_previous_pair(self):
        target, backups = self.root / 'installed', self.root / 'backups'
        for name in ('explainer', 'diagram-explainer'):
            (target / name).mkdir(parents=True)
            (target / name / 'SKILL.md').write_text('previous ' + name)
            (target / name / 'personal-note.txt').write_text('keep my note')
        retired = target / 'diagram-explainer/references/casual.md'
        retired.parent.mkdir()
        retired.write_text('legacy generator')
        first = installer.install(self.source, target, backups)
        self.assertEqual((target / 'explainer/personal-note.txt').read_text(), 'keep my note')
        self.assertFalse(retired.exists())
        self.assertFalse(checker.check(target / 'explainer', 'diagram')['blocked'])
        second = installer.install(self.source, target, backups)
        self.assertFalse(checker.check(target / 'explainer', 'text')['blocked'])
        installer.restore(target, Path(second['backup']), second['installed'])
        self.assertFalse(checker.check(target / 'explainer', 'diagram')['blocked'])
        installer.restore(target, Path(first['backup']), first['installed'])
        self.assertEqual((target / 'explainer/SKILL.md').read_text(), 'previous explainer')
        self.assertEqual(retired.read_text(), 'legacy generator')

    def test_invalid_source_and_symlink_do_not_destroy_live_data(self):
        target, backups = self.root / 'live', self.root / 'backups'
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'SKILL.md').write_text('external user file')
        target.mkdir()
        (target / 'explainer').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            installer.install(self.source, target, backups)
        self.assertEqual((outside / 'SKILL.md').read_text(), 'external user file')
        (self.source / 'explainer/SKILL.md').unlink()
        with self.assertRaises(ValueError):
            installer.install(self.source, target, backups)
        self.assertTrue((target / 'explainer').is_symlink())

    def test_post_swap_verification_failure_rolls_back_both_folders(self):
        target, backups = self.root / 'live', self.root / 'backups'
        for name in ('explainer', 'diagram-explainer'):
            (target / name).mkdir(parents=True)
            (target / name / 'SKILL.md').write_text('previous ' + name)
        rename = Path.rename
        def corrupt_after_swap(path, destination):
            result = rename(path, destination)
            if path.name.startswith('.diagram-explainer-'):
                (Path(destination) / 'SKILL.md').write_text('corrupted after swap')
            return result
        with mock.patch.object(Path, 'rename', corrupt_after_swap):
            with self.assertRaises(ValueError):
                installer.install(self.source, target, backups)
        for name in ('explainer', 'diagram-explainer'):
            self.assertEqual((target / name / 'SKILL.md').read_text(), 'previous ' + name)

    def test_config_failure_or_wrong_effective_state_has_receipt_and_rollback(self):
        target, backups = self.root / 'live', self.root / 'backups'
        for name in ('explainer', 'diagram-explainer'):
            (target / name).mkdir(parents=True)
            (target / name / 'SKILL.md').write_text('previous ' + name)
        for responses in ([{'effectiveEnabled': True}],
                          [{'effectiveEnabled': False}, RuntimeError('inventory unavailable')]):
            receipt = self.root / 'failure.json'
            args = ['install_bundle.py', '--source-skills', str(self.source), '--target', str(target),
                    '--backups', str(backups), '--codex', 'mocked', '--receipt', str(receipt)]
            with mock.patch('sys.argv', args), mock.patch.object(installer, 'codex_request', side_effect=responses):
                with self.assertRaises(RuntimeError):
                    installer.main()
            result = json.loads(receipt.read_text())
            self.assertEqual(result['status'], 'failed')
            self.assertTrue(result['installation_rolled_back'])
            for name in ('explainer', 'diagram-explainer'):
                self.assertEqual((target / name / 'SKILL.md').read_text(), 'previous ' + name)


if __name__ == '__main__':
    unittest.main()
