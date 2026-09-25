"""Bounded Codex Stop reminder for managed personal tasks in the current project.

The runner owns the completion invariant. This hook requests one continuation;
it neither writes to services nor prevents a human from stopping a task.
"""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time


RUNNER = Path.home() / '.codex/skills/harness-run/scripts/run.py'


def pending(event):
    session = event.get('session_id')
    cwd = event.get('cwd')
    if not isinstance(session, str) or not isinstance(cwd, str):
        return [], 'No project/session identity; closeout was not checked.'
    directory = Path(cwd).resolve()
    project = next((p for p in (directory, *directory.parents)
                    if (p / '.harness/tasks.sqlite').is_file()), None)
    if project is None:
        return [], None
    db = project / '.harness/tasks.sqlite'
    if db.is_symlink() or db.parent.is_symlink():
        raise ValueError('Refusing a symlinked task ledger')
    with sqlite3.connect(db.as_uri() + '?mode=ro', uri=True, timeout=1) as connection:
        tasks = [json.loads(row[0]) for row in connection.execute('SELECT state FROM tasks')]
    tasks = [t for t in tasks if t.get('owner') == session
             and t.get('request', {}).get('closeout', {}).get('mode') == 'managed'
             and not t.get('paused') and not t.get('blocker')
             and not (t.get('stage') == 'done' and t.get('completion_requested') is True)]
    deadline = time.monotonic() + 6
    remaining = []
    for task in tasks:
        # Recheck artifact/readback freshness through the installed runner.
        timeout = deadline - time.monotonic()
        if timeout <= 0:
            return remaining, 'Closeout inspection timed out; remaining tasks were not checked.'
        result = subprocess.run([sys.executable, '-B', str(RUNNER.resolve()),
                                 '--project', str(project), 'status'],
                                input=json.dumps({'task_id': task['task_id']}),
                                text=True, capture_output=True, timeout=timeout)
        if result.returncode not in (0, 1):
            raise ValueError('Installed runner could not inspect closeout')
        status = json.loads(result.stdout)
        if status['stage'] not in ('done', 'blocked', 'paused'):
            remaining.append({'task_id': task['task_id'], 'stage': status['stage'],
                              'next_action': status['next_action']})
    return remaining, None


def handle(event):
    if event.get('hook_event_name') != 'Stop':
        return {}
    tasks, warning = pending(event)
    if not tasks:
        return {'systemMessage': warning} if warning else {}
    reason = ('Managed personal work still has pending closeout: ' + json.dumps(tasks)
              + '. Resume the existing task and verify its Notion record and required '
              'GitHub delivery before claiming completion. Use the existing authorization; '
              'do not force-push or include unrelated files. If access or scope blocks '
              'delivery, record the blocker and report the unfinished item. Do not create '
              'a duplicate task or weaken its closeout requirement.')
    if warning:
        reason += ' ' + warning
    # ponytail: one continuation avoids loops during an outage; the runner still
    # refuses Done. This reminder only covers the current project/session.
    if event.get('stop_hook_active'):
        return {'systemMessage': reason}
    return {'decision': 'block', 'reason': reason}


if __name__ == '__main__':
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            raise ValueError('Expected hook event object')
        print(json.dumps(handle(event)))
    except (OSError, ValueError, KeyError, sqlite3.Error, subprocess.TimeoutExpired):
        print(json.dumps({'systemMessage': 'Personal closeout check unavailable. '
                          'Do not treat this as verified delivery; inspect the existing task.'}))
