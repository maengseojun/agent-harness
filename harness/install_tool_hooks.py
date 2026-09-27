"""Register four local harness hooks without changing Codex trust approvals."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile

from install import _verify

EVENTS = ('PreToolUse', 'PostToolUse', 'SubagentStop', 'Stop')


def _launcher(release):
    return (f'# harness-tools-release: {json.dumps(str(release))}\n'
            'import sys\n'
            f'sys.path.insert(0, {str(release / "scripts")!r})\n'
            'import tool_hook\n'
            'tool_hook.main()\n').encode()


def _plain(path):
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError(f'Symlinked managed path: {path}')


def _atomic(path, data):
    descriptor, temporary = tempfile.mkstemp(prefix='.harness-tools-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _owned(handler, hooks_dir):
    if handler.get('type') != 'command' or not isinstance(handler.get('command'), str):
        return False
    try:
        parts = shlex.split(handler['command'])
        if len(parts) != 3 or parts[1] != '-B' or not Path(parts[0]).is_absolute():
            return False
        path = Path(parts[2])
        if path.parent != hooks_dir or not path.name.startswith('harness-tools-'):
            return False
        _plain(path)
        data = path.read_bytes()
        release = Path(json.loads(data.splitlines()[0].decode().removeprefix(
            '# harness-tools-release: ')))
        return (release.is_absolute() and data == _launcher(release)
                and path.name == f'harness-tools-{hashlib.sha256(data).hexdigest()}.py')
    except (OSError, ValueError, TypeError, IndexError):
        return False


def _config(data):
    config = json.loads(data)
    if not isinstance(config, dict) or not isinstance(config.get('hooks', {}), dict):
        raise ValueError('Invalid hooks configuration')
    for entries in config.get('hooks', {}).values():
        if not isinstance(entries, list):
            raise ValueError('Invalid hook event entries')
        for entry in entries:
            if (not isinstance(entry, dict) or not isinstance(entry.get('hooks'), list)
                    or any(not isinstance(handler, dict) for handler in entry['hooks'])):
                raise ValueError('Invalid hook handlers')
    return config


def install(release, home):
    release = Path(release)
    if not release.is_absolute():
        raise ValueError('--release must be absolute')
    _plain(release)
    _verify(release)
    if not (release / 'scripts/tool_hook.py').is_file():
        raise ValueError('Release does not include tool_hook.py')
    home = Path(os.path.abspath(Path(home).expanduser()))
    hooks_dir = home / '.codex/hooks'
    config_path = home / '.codex/hooks.json'
    lock_path = hooks_dir / 'harness-tools.lock'
    for path in (hooks_dir, config_path, lock_path):
        _plain(path)
    hooks_dir.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _plain(config_path)
        old = config_path.read_bytes() if config_path.exists() else None
        config = _config(old) if old is not None else {}
        data = _launcher(release)
        launcher = hooks_dir / f'harness-tools-{hashlib.sha256(data).hexdigest()}.py'
        _plain(launcher)
        if launcher.exists():
            if not launcher.is_file() or launcher.read_bytes() != data:
                raise ValueError(f'Conflicting managed launcher: {launcher}')
        else:
            _atomic(launcher, data)
        handler = {'type': 'command', 'command': shlex.join([sys.executable, '-B', str(launcher)]),
                   'timeout': 10}
        hooks = config.setdefault('hooks', {})
        for event in EVENTS:
            entries = hooks.setdefault(event, [])
            retained = []
            for entry in entries:
                remaining = [item for item in entry['hooks'] if not _owned(item, hooks_dir)]
                if remaining or not entry['hooks']:
                    retained.append({**entry, 'hooks': remaining})
            retained.append({'hooks': [handler.copy()]})
            hooks[event] = retained
        updated = (json.dumps(config, indent=2) + '\n').encode()
        if old != updated:
            if old is not None:
                backup = config_path.with_name(f'hooks.json.backup-{hashlib.sha256(old).hexdigest()}')
                _plain(backup)
                if backup.exists():
                    if backup.read_bytes() != old:
                        raise ValueError(f'Conflicting configuration backup: {backup}')
                else:
                    _atomic(backup, old)
            _atomic(config_path, updated)
    return launcher


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', required=True, type=Path)
    parser.add_argument('--home', type=Path, default=Path.home())
    args = parser.parse_args()
    try:
        launcher = install(args.release, args.home)
    except (OSError, ValueError) as error:
        parser.exit(1, f'{error}\n')
    print(json.dumps({'launcher': str(launcher)}))


if __name__ == '__main__':
    main()
