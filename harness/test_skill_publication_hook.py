import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import skill_publication_hook as hook


class PublicationTest(unittest.TestCase):
    def test_change_new_resource_receipt_and_repeated_stop(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            folder = home / '.agents/skills/demo'
            folder.mkdir(parents=True)
            (folder / 'SKILL.md').write_text('original')
            event = {'session_id': 'test', 'hook_event_name': 'UserPromptSubmit'}
            self.assertEqual(hook.handle(event, home), {})
            event['hook_event_name'] = 'Stop'
            self.assertEqual(hook.handle(event, home), {})
            (folder / 'SKILL.md').write_text('revised')
            self.assertEqual(hook.handle(event, home)['decision'], 'block')
            self.assertNotIn('decision', hook.handle({**event, 'stop_hook_active': True}, home))
            new = home / '.agents/skills/new-skill'
            new.mkdir(); (new / 'SKILL.md').write_text('new')
            self.assertIn(str(new), hook.handle(event, home)['reason'])
            tree = {'tree': [{'path': 'skills/demo/SKILL.md', 'sha': 'blob', 'mode': '100644', 'type': 'blob'}]}
            import base64
            responses = [{'default_branch': 'different/default'}, {'sha': 'commit'}, tree,
                         {'encoding': 'base64', 'content': base64.b64encode(b'revised').decode()}]
            with patch.object(hook, 'gh', side_effect=responses):
                receipt = hook.verify(folder, home)
            self.assertEqual(receipt['branch'], 'different/default')
            self.assertNotIn(str(folder), hook.handle(event, home)['reason'])
            bad = responses[:-1] + [{'encoding': 'base64', 'content': base64.b64encode(b'wrong').decode()}]
            with patch.object(hook, 'gh', side_effect=bad):
                with self.assertRaisesRegex(ValueError, 'differs'):
                    hook.verify(folder, home)
            (folder / 'reference.md').write_text('new resource')
            self.assertIn(str(folder), hook.handle(event, home)['reason'])
            with patch.object(hook, 'gh', side_effect=responses):
                with self.assertRaisesRegex(ValueError, 'file set'):
                    hook.verify(folder, home)

    def test_install_preserves_existing_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp); config = home / '.codex/hooks.json'; config.parent.mkdir()
            old = {'hooks': {'Stop': [{'hooks': [{'type': 'command', 'command': 'existing'}]}]}}
            config.write_text(json.dumps(old))
            hook.install(home); once = config.read_bytes(); hook.install(home)
            self.assertEqual(once, config.read_bytes())
            self.assertEqual(json.loads(once)['hooks']['Stop'][0], old['hooks']['Stop'][0])
            self.assertTrue(list(config.parent.glob('hooks.json.backup-*')))
            import hashlib
            old_script = b'"""Detect changed personal skills old release"""'
            old_path = config.parent / 'hooks' / ('skill-publication-' + hashlib.sha256(old_script).hexdigest() + '.py')
            old_path.write_bytes(old_script)
            cfg = json.loads(once)
            cfg['hooks']['Stop'].append({'hooks': [{'type': 'command', 'command': f'/usr/bin/python3 -B {old_path}'}]})
            config.write_text(json.dumps(cfg))
            hook.install(home)
            self.assertEqual(len(json.loads(config.read_text())['hooks']['Stop']), 2)
            with self.assertRaises(ValueError):
                hook.verify(home / 'outside/demo', home)


if __name__ == '__main__':
    unittest.main()
