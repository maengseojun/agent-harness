#!/usr/bin/env python3
"""Check this explanation bundle's required source revisions and optional examples."""
import argparse
import hashlib
import json
from pathlib import Path


def check(skill: Path, mode: str):
    manifest = json.loads((skill / 'references/reference-map.json').read_text())
    results = []
    for item in manifest['references']:
        if mode not in item['modes']:
            continue
        path = (skill / item['path']).resolve()
        if not path.is_file():
            state = 'required_missing' if item['required'] else 'optional_missing'
        elif item.get('sha256') and hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            state = 'revision_conflict'
        else:
            state = 'current'
        results.append({'id': item['id'], 'path': str(path), 'state': state})
    blocked = any(x['state'] in ('required_missing', 'revision_conflict') for x in results)
    return {'mode': mode, 'revision': manifest['revision'], 'blocked': blocked, 'references': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('text', 'diagram'), default='text')
    parser.add_argument('--skill-dir', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        result = check(args.skill_dir, args.mode)
    except (OSError, ValueError, KeyError) as error:
        print(json.dumps({'blocked': True, 'error': str(error)}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(result['blocked'])


if __name__ == '__main__':
    raise SystemExit(main())
