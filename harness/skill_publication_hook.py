"""Detect changed personal skills and require GitHub publication before closeout.

Hooks never push or stage files. `verify` records only a byte-verified default-
branch copy. Existing files are baselined, not silently published on installation.
"""
import argparse
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile

REPOSITORY = 'maengseojun/agent-harness'
IGNORED = {'.git', '.harness', '__pycache__', '.DS_Store'}


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(value)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def files(folder):
    if folder.is_symlink():
        raise ValueError('Symlinked skills require explicit source reconciliation')
    result = {}
    for path in sorted(folder.rglob('*')):
        if any(part in IGNORED for part in path.relative_to(folder).parts):
            continue
        if path.is_symlink():
            raise ValueError('Symlinked skill resources are not publication evidence')
        if path.is_file():
            result[path.relative_to(folder).as_posix()] = path.read_bytes()
    return result


def digest(folder):
    values = {name: hashlib.sha256(data).hexdigest() for name, data in files(folder).items()}
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def roots(home):
    repository = home / 'Documents/ChatGPT/Being agents'
    result = [home / '.agents/skills', home / '.codex/skills', repository / 'skills']
    if (repository / '.git').exists():
        listing = subprocess.run(['git', '-C', str(repository), 'worktree', 'list', '--porcelain'],
                                 capture_output=True, text=True, check=True, timeout=3).stdout
        result.extend(Path(line.removeprefix('worktree ')) / 'skills'
                      for line in listing.splitlines() if line.startswith('worktree '))
    return list(dict.fromkeys(result))


def snapshot(home):
    result = {}
    personal_roots = roots(home)
    releases = [home / '.local/share/agent-harness/releases',
                home / '.local/share/personal-skills/releases']
    for root in personal_roots:
        if not root.is_dir():
            continue
        for folder in sorted(root.iterdir()):
            if folder.name.startswith('.'):
                continue
            if folder.is_symlink():
                target = folder.resolve()
                # Aliases of a scanned root and immutable installed releases are not authored copies.
                if (target.parent in [r.resolve() for r in personal_roots]
                        or any(target.is_relative_to(r.resolve()) for r in releases)):
                    continue
                result[str(folder)] = 'unverified: symlinked skill folder'
            elif folder.is_dir() and (folder / 'SKILL.md').is_file():
                try:
                    result[str(folder)] = digest(folder)
                except ValueError as error:
                    result[str(folder)] = 'unverified: ' + str(error)
    return result


def state_dir(home):
    return home / '.local/share/agent-harness/skill-publication'


def load(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def handle(event, home=Path.home()):
    kind = event.get('hook_event_name')
    session = event.get('session_id')
    if kind not in {'UserPromptSubmit', 'Stop'} or not isinstance(session, str) or not session:
        return {}
    directory = state_dir(home)
    directory.mkdir(parents=True, exist_ok=True)
    state_path = directory / (hashlib.sha256(session.encode()).hexdigest() + '.json')
    # ponytail: one process-wide local lock; split by session if hook contention matters.
    with (directory / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = snapshot(home)
        if not state_path.exists() and kind == 'Stop':
            return {'systemMessage': 'Skill publication baseline is missing; change detection is '
                    'unverified. Start a new turn to establish a baseline; inspect skills changed '
                    'in this turn manually before claiming publication.'}
        state = load(state_path, {'baseline': current})
        receipts = load(directory / 'verified.json', {})
        pending = {path: value for path, value in current.items()
                   if (state['baseline'].get(path) != value or value.startswith('unverified:'))
                   and not (receipts.get(path, {}).get('digest') == value
                            and receipts.get(path, {}).get('session') == session)}
        # Deletion never authorizes removing a skill from GitHub.
        removed = sorted(set(state['baseline']) - set(current))
        atomic(state_path, json.dumps(state, sort_keys=True).encode())
    if kind != 'Stop' or not (pending or removed):
        return {}
    reason = ('Personal skill publication is pending. Changed skills: '
              + json.dumps(sorted(pending), ensure_ascii=False)
              + '; locally removed skills: ' + json.dumps(removed, ensure_ascii=False)
              + '. Inspect the user-authorized changes, validate the skill, publish only reviewed '
              'personal skill files to the live default branch of ' + REPOSITORY
              + ', read back the immutable remote files and reconcile the installed copy. '
              'Then run ' + shlex.join([sys.executable, '-B', str(Path(__file__).resolve()),
                                      'verify', '--skill', '<absolute-skill-folder>'])
              + ' for each changed installed/source folder. Do not publish unrelated changes, '
              'third-party acquisitions or private task examples without authorization. '
              'Do not force-push. A local removal needs explicit user authorization; report it '
              'instead of deleting remote files. On access/conflict failure, preserve the draft '
              'and report the blocker; do not claim synchronization.')
    if event.get('stop_hook_active'):
        return {'systemMessage': reason}
    return {'decision': 'block', 'reason': reason}


def gh(endpoint):
    result = subprocess.run(['gh', 'api', endpoint], capture_output=True, text=True,
                            check=True, timeout=45)
    return json.loads(result.stdout)


def source_folder(folder, home):
    """Resolve installed aliases without accepting arbitrary linked directories."""
    if not folder.is_symlink():
        return folder
    target = folder.resolve(strict=True)
    personal_roots = [root.resolve() for root in roots(home)]
    releases = [home / '.local/share/agent-harness/releases',
                home / '.local/share/personal-skills/releases']
    if target.name != folder.name or not (
            target.parent in personal_roots
            or any(target.is_relative_to(root.resolve()) for root in releases)):
        raise ValueError('Skill alias must resolve to a matching personal source or installed release')
    return target


def verify(folder, home=Path.home()):
    session = os.environ.get('CODEX_THREAD_ID')
    if not isinstance(session, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', session):
        raise ValueError('CODEX_THREAD_ID session identity is required for a publication receipt')
    folder = Path(os.path.abspath(folder))
    if folder.parent not in roots(home) or not re.fullmatch(r'[a-z0-9][a-z0-9-]*', folder.name):
        raise ValueError('Only a direct personal skill folder is supported')
    source = source_folder(folder, home)
    local = files(source)
    if 'SKILL.md' not in local:
        raise ValueError('Missing SKILL.md')
    branch = gh(f'repos/{REPOSITORY}')['default_branch']
    from urllib.parse import quote
    sha = gh(f'repos/{REPOSITORY}/commits/{quote(branch, safe="")}')['sha']
    tree = gh(f'repos/{REPOSITORY}/git/trees/{sha}?recursive=1')
    if tree.get('truncated'):
        raise ValueError('Remote tree is truncated; cannot verify complete skill')
    prefix = f'skills/{folder.name}/'
    if any(entry['type'] not in {'blob', 'tree'} for entry in tree['tree']
           if entry['path'].startswith(prefix)):
        raise ValueError('Unsupported remote skill entry (for example a submodule)')
    remote = {entry['path'][len(prefix):]: entry for entry in tree['tree']
              if entry['path'].startswith(prefix) and entry['type'] == 'blob'}
    if set(remote) != set(local):
        raise ValueError('Remote skill file set differs from local skill')
    for name, entry in remote.items():
        if entry['mode'] == '120000':
            raise ValueError('Remote symlink is not a skill resource')
        blob = gh(f'repos/{REPOSITORY}/git/blobs/{entry["sha"]}')
        if blob.get('encoding') != 'base64' or base64.b64decode(blob['content']) != local[name]:
            raise ValueError(f'Remote file differs: {name}')
    if (gh(f'repos/{REPOSITORY}')['default_branch'] != branch
            or gh(f'repos/{REPOSITORY}/commits/{quote(branch, safe="")}')['sha'] != sha):
        raise ValueError('Default branch changed during verification; repeat readback')
    # Bind the receipt to the bytes inspected, not a second read after the network calls.
    values = {name: hashlib.sha256(data).hexdigest() for name, data in local.items()}
    inspected = hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
    if source_folder(folder, home) != source or digest(source) != inspected:
        raise ValueError('Skill changed during verification; no receipt saved')
    directory = state_dir(home)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = directory / 'verified.json'
        receipt = {'digest': inspected, 'repository': REPOSITORY, 'branch': branch, 'commit': sha,
                   'session': session, 'source': str(source)}
        if receipt['session']:
            session_path = directory / (hashlib.sha256(receipt['session'].encode()).hexdigest() + '.json')
            if session_path.exists():
                state = load(session_path, {})
                state['baseline'][str(folder)] = inspected
                atomic(session_path, json.dumps(state, sort_keys=True).encode())
        receipts = load(path, {})
        receipts[str(folder)] = receipt
        atomic(path, json.dumps(receipts, sort_keys=True).encode())
    return receipt


def owned(handler, home):
    try:
        parts = shlex.split(handler.get('command', ''))
        path = Path(parts[2]) if len(parts) == 3 and parts[1] == '-B' else Path()
        if path.parent != home / '.codex/hooks' or path.is_symlink() or not path.is_file():
            return False
        data = path.read_bytes()
        return (handler.get('type') == 'command'
                and path.name == 'skill-publication-' + hashlib.sha256(data).hexdigest() + '.py'
                and data.startswith(b'"""Detect changed personal skills'))
    except (OSError, ValueError):
        return False


def _install(home):
    content = Path(__file__).read_bytes()
    target = home / '.codex/hooks' / ('skill-publication-' + hashlib.sha256(content).hexdigest() + '.py')
    config_path = home / '.codex/hooks.json'
    old = config_path.read_bytes() if config_path.exists() else b'{}'
    config = json.loads(old)
    handler = {'type': 'command', 'command': shlex.join([sys.executable, '-B', str(target)]),
               'timeout': 10, 'statusMessage': 'Checking personal skill publication'}
    for event in ('UserPromptSubmit', 'Stop'):
        entries = config.setdefault('hooks', {}).setdefault(event, [])
        retained = []
        for entry in entries:
            remaining = [item for item in entry['hooks'] if not owned(item, home)]
            if remaining or not entry['hooks']:
                retained.append({**entry, 'hooks': remaining})
        retained.append({'hooks': [handler.copy()]})
        config['hooks'][event] = retained
    updated = (json.dumps(config, indent=2) + '\n').encode()
    atomic(target, content)
    if (config_path.read_bytes() if config_path.exists() else b'{}') != old:
        raise ValueError('Hook configuration changed during installation; retry from current state')
    if old != updated:
        atomic(config_path.with_name('hooks.json.backup-' + hashlib.sha256(old).hexdigest()), old)
        atomic(config_path, updated)
    return {'hook': str(target), 'events': ['UserPromptSubmit', 'Stop']}


def install(home=Path.home()):
    directory = home / '.codex/hooks'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'harness-tools.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _install(home)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', choices=['verify', 'install'])
    parser.add_argument('--skill', type=Path)
    args = parser.parse_args()
    try:
        if args.action == 'install':
            output = install()
        elif args.action == 'verify':
            if args.skill is None:
                raise ValueError('--skill is required')
            output = verify(args.skill)
        else:
            output = handle(json.load(sys.stdin))
        print(json.dumps(output))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        if args.action:
            parser.exit(1, f'{error}\n')
        print(json.dumps({'systemMessage': 'Skill publication check unavailable; synchronization '
                          'is unverified. Inspect the local hook: ' + str(error)}))


if __name__ == '__main__':
    main()
