"""Fetch only hash-pinned files from the approved GitHub skill source."""
import argparse
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'harness/skills.lock.json'


def validate(entry):
    if entry['repository'] != 'openai/skills':
        raise ValueError('Repository is not approved; review a new source explicitly')
    if not re.fullmatch(r'[0-9a-f]{40}', entry['commit']):
        raise ValueError('Require an immutable commit, not a branch')
    if not re.fullmatch(r'[0-9a-f]{64}', entry['sha256']):
        raise ValueError('Invalid file digest')
    source = PurePosixPath(entry['source_path'])
    prefixes = ('skills/.system/skill-creator/', 'skills/.curated/notion-knowledge-capture/',
                'skills/.curated/cli-creator/')
    if source.is_absolute() or '..' in source.parts or not str(source).startswith(prefixes):
        raise ValueError('Unexpected skill source path')
    target = ROOT / entry['path']
    cache = ROOT / '.harness/skills'
    if not target.resolve().is_relative_to(cache.resolve()) or target.is_symlink():
        raise ValueError('Cache path escapes the approved directory')
    return target


def sync(check=False):
    lock = json.loads(LOCK.read_text())
    entries = lock['skills'] + lock.get('resources', [])
    for entry in entries:
        target = validate(entry)
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == entry['sha256']:
            continue
        if check:
            raise ValueError(f"Missing or changed skill resource: {entry['path']}")
        response = subprocess.run(
            ['gh', 'api', f"repos/{entry['repository']}/contents/{entry['source_path']}?ref={entry['commit']}"],
            check=True, capture_output=True, text=True, timeout=45)
        data = base64.b64decode(json.loads(response.stdout)['content'])
        if hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('GitHub content differs from approved digest; cache unchanged')
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as tmp:
            tmp.write(data)
            temp = Path(tmp.name)
        temp.replace(target)
    return {'verified_files': len(entries), 'commit': lock['skills'][0]['commit']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify cached files without network calls')
    args = parser.parse_args()
    print(json.dumps(sync(args.check)))
