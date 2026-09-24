"""Focused Stop-hook behavior; no real services or user configuration."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import closeout_hook as hook


class CloseoutHookTest(unittest.TestCase):
    def test_continuation_is_bounded_and_does_not_claim_completion(self):
        pending = ([{'task_id': 'example', 'stage': 'awaiting-closeout',
                     'next_action': 'closeout'}], None)
        with patch.object(hook, 'pending', return_value=pending):
            self.assertEqual(hook.handle({'hook_event_name': 'Stop'})['decision'], 'block')
            self.assertNotIn('decision', hook.handle({'hook_event_name': 'Stop', 'stop_hook_active': True}))
        with patch.object(hook, 'pending', return_value=([], None)):
            self.assertEqual(hook.handle({'hook_event_name': 'Stop'}), {})

    def test_project_and_owner_selection_and_current_state(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            (root / '.harness').mkdir()
            (root / 'nested').mkdir()
            tasks = [
                {'task_id': 'mine', 'owner': 'session', 'request': {'closeout': {'mode': 'managed'}}},
                {'task_id': 'other', 'owner': 'other', 'request': {'closeout': {'mode': 'managed'}}},
                {'task_id': 'legacy', 'owner': 'session', 'request': {}},
                {'task_id': 'blocked', 'owner': 'session', 'request': {'closeout': {'mode': 'managed'}}, 'blocker': {'kind': 'auth'}},
            ]
            with sqlite3.connect(root / '.harness/tasks.sqlite') as db:
                db.execute('CREATE TABLE tasks (state TEXT)')
                db.executemany('INSERT INTO tasks VALUES (?)', [(json.dumps(t),) for t in tasks])
            event = {'cwd': str(root / 'nested'), 'session_id': 'session'}
            result = type('Result', (), {'returncode': 0, 'stdout': json.dumps({'stage': 'awaiting-closeout', 'next_action': 'closeout'})})()
            with patch.object(hook.subprocess, 'run', return_value=result) as run:
                actual, warning = hook.pending(event)
                self.assertEqual([t['task_id'] for t in actual], ['mine'])
                self.assertIsNone(warning)
                self.assertEqual(run.call_count, 1)
                self.assertEqual(json.loads(run.call_args.kwargs['input']), {'task_id': 'mine'})
            result.stdout = json.dumps({'stage': 'done', 'next_action': 'none'})
            with patch.object(hook.subprocess, 'run', return_value=result):
                self.assertEqual(hook.pending(event), ([], None))


if __name__ == '__main__':
    unittest.main()
