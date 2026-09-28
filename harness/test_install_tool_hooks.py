import json
from pathlib import Path
import shlex
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor

from install import install as package
from install_tool_hooks import EVENTS, install
import test_install


class ToolHookInstallTests(unittest.TestCase):
    def test_record_hooks_preserve_tool_and_entry_handlers(self):
        tools = install(self.release, self.home)
        records = install(self.release, self.home, 'work_records')
        first = self.config.read_bytes()
        self.assertEqual(records, install(self.release, self.home, 'work_records'))
        self.assertEqual(first, self.config.read_bytes())
        config = json.loads(first)
        for event in ('PreToolUse', 'PostToolUse', 'Stop'):
            commands = [h['command'] for e in config['hooks'][event] for h in e['hooks']]
            self.assertEqual(2, len(commands))
            self.assertTrue(any(str(tools) in c for c in commands))
            self.assertTrue(any(str(records) in c for c in commands))
        self.assertIn('UserPromptSubmit', config['hooks'])
        result = subprocess.run([sys.executable, '-B', str(records)], capture_output=True,
                                text=True, check=True, cwd=self.root)
        self.assertEqual('records\n', result.stdout)

    def test_all_replaces_both_managed_launchers_with_one_release(self):
        old = install(self.release, self.home, 'all')
        (self.source / 'harness/ledger.py').write_text('def message(): return "v2"\n')
        upgraded = package(self.source, self.home)
        current = install(upgraded, self.home, 'all')
        self.assertEqual(current, install(upgraded, self.home, 'all'))
        self.assertNotEqual(old, current)
        config = json.loads(self.config.read_text())['hooks']
        for module, events in (('tool_hook', EVENTS), ('work_records',
                                ('UserPromptSubmit', 'PreToolUse', 'PostToolUse', 'Stop'))):
            for event in events:
                commands = [handler['command'] for entry in config[event]
                            for handler in entry['hooks']]
                self.assertEqual(1, sum(str(current[module]) in command for command in commands))
                self.assertFalse(any(str(old[module]) in command for command in commands))

    def setUp(self):
        test_install.InstallTests.setUp(self)
        (self.source / 'harness/run.py').write_text('VALUE = "frozen"\n')
        (self.source / 'harness/tool_hook.py').write_text(
            'import run\nfrom ledger import message\n'
            'def main(): print(run.VALUE + " " + message())\n')
        self.release = package(self.source, self.home)
        self.config = self.home / '.codex/hooks.json'

    def save(self, config):
        self.config.write_text(json.dumps(config))
        return self.config.read_bytes()

    def test_preservation_idempotence_upgrade_and_execution(self):
        foreign = {'type': 'command', 'command': 'old-entry-or-closeout', 'timeout': 7}
        original = {'other': {'keep': True}, 'hooks': {
            event: [{'matcher': 'keep', 'extra': 42, 'hooks': [foreign]}]
            for event in (*EVENTS, 'SessionStart')}}
        before = self.save(original)
        trust = self.home / '.codex/config.toml'
        trust.write_text('user trust settings')
        launcher = install(self.release, self.home)
        first = self.config.read_bytes()
        self.assertEqual(install(self.release, self.home), launcher)
        self.assertEqual(self.config.read_bytes(), first)
        self.assertEqual(list(self.config.parent.glob('hooks.json.backup-*'))[0].read_bytes(), before)
        (self.source / 'harness/ledger.py').write_text('def message(): return "v2"\n')
        upgraded = package(self.source, self.home)
        second = install(upgraded, self.home)
        self.assertNotEqual(launcher, second)
        config = json.loads(self.config.read_text())
        self.assertEqual(config['other'], original['other'])
        self.assertEqual(config['hooks']['SessionStart'], original['hooks']['SessionStart'])
        for event in EVENTS:
            entries = config['hooks'][event]
            self.assertEqual(entries[0], original['hooks'][event][0])
            self.assertEqual(len(entries), 2)
            self.assertNotIn('matcher', entries[1])
            handler = entries[1]['hooks'][0]
            self.assertEqual(handler['timeout'], 10)
            self.assertEqual(shlex.split(handler['command']), [sys.executable, '-B', str(second)])
        self.assertEqual(trust.read_text(), 'user trust settings')
        for path, expected in ((launcher, 'frozen snapshot v1\n'), (second, 'frozen v2\n')):
            result = subprocess.run([sys.executable, '-B', str(path)], capture_output=True,
                                    text=True, check=True, cwd=self.root)
            self.assertEqual(result.stdout, expected)

    def test_shared_entry_keeps_foreign_handler(self):
        launcher = install(self.release, self.home)
        config = json.loads(self.config.read_text())
        foreign = {'type': 'command', 'command': 'closeout'}
        config['hooks']['Stop'][0]['hooks'].append(foreign)
        self.save(config)
        install(self.release, self.home)
        entries = json.loads(self.config.read_text())['hooks']['Stop']
        self.assertEqual(entries[0]['hooks'], [foreign])
        self.assertTrue(launcher.exists())

    def test_malformed_configs_are_untouched(self):
        for value in ('{', '[]', '{"hooks": []}', '{"hooks": {"Stop": {}}}',
                      '{"hooks": {"Stop": [{"hooks": [3]}]}}'):
            with self.subTest(value=value):
                self.config.write_text(value)
                with self.assertRaises(ValueError):
                    install(self.release, self.home)
                self.assertEqual(self.config.read_text(), value)

    def test_symlinks_and_foreign_launcher_conflicts(self):
        outside = self.root / 'outside.json'
        outside.write_text('{}')
        self.config.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'Symlinked'):
            install(self.release, self.home)
        self.assertEqual(outside.read_text(), '{}')
        self.config.unlink()
        launcher = install(self.release, self.home)
        before = self.config.read_bytes()
        launcher.write_text('foreign script')
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            install(self.release, self.home)
        self.assertEqual(self.config.read_bytes(), before)
        launcher.unlink()
        launcher.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'Symlinked'):
            install(self.release, self.home)

    def test_invalid_release_and_relative_release(self):
        with self.assertRaisesRegex(ValueError, 'absolute'):
            install(Path('relative'), self.home)
        (self.release / 'scripts/tool_hook.py').write_text('tampered')
        with self.assertRaisesRegex(ValueError, 'managed release'):
            install(self.release, self.home)
        self.assertFalse(self.config.exists())

    def test_concurrent_install_and_cli(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: install(self.release, self.home), range(8)))
        self.assertEqual(len(set(results)), 1)
        config = json.loads(self.config.read_text())
        self.assertTrue(all(len(config['hooks'][event]) == 1 for event in EVENTS))
        result = subprocess.run([sys.executable, '-B', str(Path(__file__).with_name(
            'install_tool_hooks.py')), '--release', str(self.release), '--home', str(self.home),
                                 '--module', 'tool_hook'],
            capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)['launcher'], str(results[0]))


if __name__ == '__main__':
    unittest.main()
