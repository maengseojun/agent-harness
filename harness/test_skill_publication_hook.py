import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import skill_publication_hook as hook


class PublicationTest(unittest.TestCase):
    def test_change_new_resource_receipt_and_repeated_stop(self):
        with patch.dict(hook.os.environ, {'CODEX_THREAD_ID': 'test'}), tempfile.TemporaryDirectory() as temp:
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
                         {'encoding': 'base64', 'content': base64.b64encode(b'revised').decode()},
                         {'default_branch': 'different/default'}, {'sha': 'commit'}]
            with patch.dict(hook.os.environ, {'CODEX_THREAD_ID': 'test'}), patch.object(hook, 'gh', side_effect=responses):
                receipt = hook.verify(folder, home)
            self.assertEqual(receipt['branch'], 'different/default')
            self.assertNotIn(str(folder), hook.handle(event, home)['reason'])
            bad = responses[:3] + [{'encoding': 'base64', 'content': base64.b64encode(b'wrong').decode()}]
            with patch.object(hook, 'gh', side_effect=bad):
                with self.assertRaisesRegex(ValueError, 'differs'):
                    hook.verify(folder, home)
            submodule = {'tree': tree['tree'] + [{'path': 'skills/demo/extra', 'type': 'commit'}]}
            with patch.object(hook, 'gh', side_effect=responses[:2] + [submodule]):
                with self.assertRaisesRegex(ValueError, 'Unsupported'):
                    hook.verify(folder, home)
            changed_branch = responses[:-1] + [{'sha': 'changed'}]
            with patch.object(hook, 'gh', side_effect=changed_branch):
                with self.assertRaisesRegex(ValueError, 'changed during'):
                    hook.verify(folder, home)
            (folder / 'link').symlink_to(folder / 'SKILL.md')
            self.assertIn('unverified', hook.snapshot(home)[str(folder)])
            hook.handle({'hook_event_name': 'UserPromptSubmit', 'session_id': 'other'}, home)
            (folder / 'SKILL.md').write_text('changed behind link')
            self.assertEqual(hook.handle({'hook_event_name': 'Stop', 'session_id': 'other'}, home)['decision'], 'block')
            (folder / 'SKILL.md').write_text('revised')
            with patch.dict(hook.os.environ, {}, clear=True):
                with self.assertRaisesRegex(ValueError, 'session identity'):
                    hook.verify(folder, home)
            (folder / 'link').unlink()
            (folder / 'reference.md').write_text('new resource')
            self.assertIn(str(folder), hook.handle(event, home)['reason'])
            with patch.object(hook, 'gh', side_effect=responses):
                with self.assertRaisesRegex(ValueError, 'file set'):
                    hook.verify(folder, home)

    def test_alias_verification_and_rejection(self):
        import base64
        with patch.dict(hook.os.environ, {'CODEX_THREAD_ID': 'test'}), tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            alias = home / '.codex/skills/demo'
            alias.parent.mkdir(parents=True)
            source = home / '.local/share/personal-skills/releases/hash/demo'
            source.mkdir(parents=True)
            (source / 'SKILL.md').write_text('published')
            alias.symlink_to(source, target_is_directory=True)
            responses = [{'default_branch': 'main'}, {'sha': 'commit'}, {'tree': [
                {'path': 'skills/demo/SKILL.md', 'sha': 'blob', 'mode': '100644', 'type': 'blob'}]},
                {'encoding': 'base64', 'content': base64.b64encode(b'published').decode()},
                {'default_branch': 'main'}, {'sha': 'commit'}]
            with patch.object(hook, 'gh', side_effect=responses):
                self.assertEqual(hook.verify(alias, home)['source'], str(source.resolve()))
            (source / 'SKILL.md').write_text('modified')
            with patch.object(hook, 'gh', side_effect=responses):
                with self.assertRaisesRegex(ValueError, 'differs'):
                    hook.verify(alias, home)
            (source / 'SKILL.md').write_text('published')
            replacement = home / '.local/share/personal-skills/releases/other/demo'
            replacement.mkdir(parents=True)
            (replacement / 'SKILL.md').write_text('published')
            def read(endpoint):
                value = responses.pop(0)
                if not responses:
                    alias.unlink(); alias.symlink_to(replacement, target_is_directory=True)
                return value
            with patch.object(hook, 'gh', side_effect=read):
                with self.assertRaisesRegex(ValueError, 'changed during'):
                    hook.verify(alias, home)
            outside = home / 'outside/demo'
            outside.mkdir(parents=True); (outside / 'SKILL.md').write_text('published')
            alias.unlink(); alias.symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'matching personal'):
                hook.verify(alias, home)
            alias.unlink(); alias.symlink_to(home / 'missing', target_is_directory=True)
            with self.assertRaises(FileNotFoundError):
                hook.verify(alias, home)
            plain = home / '.agents/skills/demo'
            plain.mkdir(parents=True); (plain / 'SKILL.md').write_text('published')
            alias.unlink(); alias.symlink_to(plain, target_is_directory=True)
            self.assertEqual(hook.source_folder(alias, home), plain.resolve())
            (plain / 'linked-resource').symlink_to(plain / 'SKILL.md')
            with self.assertRaisesRegex(ValueError, 'resources'):
                hook.verify(alias, home)

    def test_install_preserves_existing_and_is_idempotent(self):
        with patch.dict(hook.os.environ, {'CODEX_THREAD_ID': 'test'}), tempfile.TemporaryDirectory() as temp:
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
            plain = home / '.codex/skills/example'
            plain.mkdir(parents=True); (plain / 'SKILL.md').write_text('source')
            alias = home / '.agents/skills/example'; alias.parent.mkdir(parents=True)
            alias.symlink_to(plain, target_is_directory=True)
            self.assertIn(str(plain), hook.snapshot(home))
            self.assertNotIn(str(alias), hook.snapshot(home))
            release = home / '.local/share/personal-skills/releases/hash/managed'
            release.mkdir(parents=True); (release / 'SKILL.md').write_text('installed')
            managed = alias.parent / 'managed'; managed.symlink_to(release, target_is_directory=True)
            self.assertNotIn(str(managed), hook.snapshot(home))


if __name__ == '__main__':
    unittest.main()
