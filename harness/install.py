"""Install a fixed harness snapshot and register both user-level skill paths.

Uses a local POSIX filesystem and cooperative installers. Each link replacement
is atomic; an interrupted pair of replacements can be completed by reinstalling.
"""
import argparse
from contextlib import ExitStack
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile


FILES = {
    'SKILL.md': '.agents/skills/harness-run/SKILL.md',
    'agents/openai.yaml': '.agents/skills/harness-run/agents/openai.yaml',
    'scripts/ledger.py': 'harness/ledger.py',
    'scripts/run.py': 'harness/run.py',
    'references/README.md': 'harness/README.md',
    'references/NOTION-WORKSPACE.md': 'harness/NOTION-WORKSPACE.md',
}
PREVIOUS_FILES = set(FILES) - {'references/NOTION-WORKSPACE.md'}


def _manifest(payload):
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in payload.items()}
    canonical = json.dumps(hashes, sort_keys=True, separators=(',', ':')).encode()
    release_id = hashlib.sha256(canonical).hexdigest()
    manifest = {'release_id': release_id, 'files': hashes}
    return release_id, (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode()


def _verify(release):
    """Never repair or overwrite an existing release, including a dangling link."""
    error = f'Changed or invalid managed release: {release}'
    directories = [release.parent, release] + [release / name for name in
                                               ('agents', 'scripts', 'references')]
    if any(path.is_symlink() or not path.is_dir() for path in directories):
        raise ValueError(error)
    try:
        saved = json.loads((release / 'manifest.json').read_text())
    except (OSError, ValueError, TypeError):
        raise ValueError(error) from None
    if (not isinstance(saved, dict) or set(saved) != {'files', 'release_id'}
            or not isinstance(saved['files'], dict)
            or set(saved['files']) not in (PREVIOUS_FILES, set(FILES))):
        raise ValueError(error)
    paths = [release / name for name in (*saved['files'], 'manifest.json')]
    if any(path.is_symlink() or not path.is_file() for path in paths):
        raise ValueError(error)
    release_id, manifest = _manifest({name: (release / name).read_bytes() for name in saved['files']})
    if release.parent.name != release_id or (release / 'manifest.json').read_bytes() != manifest:
        raise ValueError(error)


def _entrypoint(link, releases):
    if link.is_symlink():
        target = Path(os.path.abspath(link.parent / link.readlink()))
        if target.name == 'harness-run' and target.parent.parent == releases:
            _verify(target)
            return
    elif not link.exists():
        return
    raise ValueError(f'Unmanaged skill entrypoint: {link}')


def install(source_root, home):
    """Return the installed release's skill directory; never delete old releases."""
    source_root, home = Path(source_root), Path(home).expanduser().resolve()
    payload = {name: (source_root / source).read_bytes() for name, source in FILES.items()}
    release_id, manifest = _manifest(payload)
    store = home / '.local/share/agent-harness'
    releases = store / 'releases'
    release = releases / release_id / 'harness-run'
    links = [home / name / 'skills/harness-run' for name in ('.agents', '.codex')]
    store.mkdir(parents=True, exist_ok=True)
    # One per-home lock serializes threads and processes through both switches.
    with (store / 'install.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for link in links:
            _entrypoint(link, releases)
        if release.parent.exists() or release.parent.is_symlink():
            _verify(release)
        else:
            releases.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.stage-', dir=releases) as stage:
                skill = Path(stage) / 'harness-run'
                for name, data in {**payload, 'manifest.json': manifest}.items():
                    destination = skill / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(data)
                Path(stage).rename(release.parent)
        # Prepare both links before replacing either; keep temporaries on the
        # corresponding filesystem so replace remains atomic.
        with ExitStack() as cleanup:
            pending = []
            for link in links:
                if link.is_symlink() and link.readlink() == release:
                    continue
                link.parent.mkdir(parents=True, exist_ok=True)
                stage = cleanup.enter_context(tempfile.TemporaryDirectory(
                    prefix='.harness-run-', dir=link.parent))
                temporary = Path(stage) / 'harness-run'
                temporary.symlink_to(release, target_is_directory=True)
                pending.append((temporary, link))
            for temporary, link in pending:
                temporary.replace(link)
    return release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--home', type=Path, default=Path.home(), help='Override the user home')
    args = parser.parse_args()
    try:
        release = install(args.source_root, args.home)
    except (OSError, ValueError) as error:
        parser.exit(1, f'{error}\n')
    print(json.dumps({'release_id': release.parent.name, 'path': str(release)}))


if __name__ == '__main__':
    main()
