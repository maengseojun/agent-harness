#!/usr/bin/env python3
"""Explicit, offline AST index. No CLI registration, installation, or semantic pass."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

CODE = {'.py', '.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx', '.go', '.rs',
        '.java', '.c', '.h', '.cpp', '.hpp', '.rb', '.cs', '.kt', '.swift', '.lua'}
SKIP = {'.git', '.agents', '.codex', '.aws', '.ssh', '.venv', 'node_modules',
        '__pycache__', 'vendor', 'dist', 'build'}
WORKER = '''import json, sys, tomllib
from pathlib import Path
sys.path.insert(0, sys.argv[1])
version = tomllib.loads((Path(sys.argv[1])/"pyproject.toml").read_text())["project"]["version"]
if version != "0.9.85": raise SystemExit("Graphify version mismatch")
from graphify.extract import extract
spec = json.loads(Path(sys.argv[2]).read_text())
result = extract([Path(p) for p in spec["files"]], root=Path(spec["root"]),
                 cache_root=Path(spec["cache"]), parallel=False)
Path(sys.argv[3]).write_text(json.dumps(result, ensure_ascii=False, indent=2))
'''


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def git(root, *args):
    r = subprocess.run(['git', '-C', str(root), *args], capture_output=True,
                       text=True, check=True)
    return r.stdout.strip()


def can_reuse(previous, root, revision, status, hashes, includes, excludes):
    """Conservative selected-source freshness check; never semantic validation."""
    return (previous.get('graphify_version') == '0.9.85'
            and previous.get('graphify_revision') == 'b4e6307bf170f27e0cb888c03f4af9308d531a42'
            and Path(previous['repository']['root']).resolve() == root.resolve()
            and previous['repository']['revision'] == revision
            and previous['repository'].get('status_after', previous['repository'].get('status')) == status
            and previous['files'] == hashes
            and previous['scope']['include'] == includes
            and previous['scope']['exclude'] == excludes
            and previous['scope'].get('semantic_analysis') is False
            and previous['scope'].get('extensions') == sorted(CODE)
            and previous['scope'].get('skip_directories') == sorted(SKIP)
            and not previous['graph'].get('failed_sources'))


def select(root, includes, excludes):
    root = root.resolve()
    files = set()
    omitted = []
    for entry in includes:
        part = Path(entry)
        if part.is_absolute() or '..' in part.parts:
            raise ValueError('include must be repo-relative without traversal')
        start = root / part
        if not start.exists():
            raise ValueError(f'missing include: {entry}')
        # Reject symlinks at any selected ancestor, including a directory scope.
        if any((root / Path(*part.parts[:i])).is_symlink() for i in range(1, len(part.parts)+1)):
            raise ValueError('symlink scope is not supported')
        candidates = [start] if start.is_file() else start.rglob('*')
        for p in candidates:
            rel = p.relative_to(root).as_posix()
            if any(rel == x or rel.startswith(x.rstrip('/') + '/') for x in excludes):
                if p.is_file(): omitted.append(rel)
                continue
            if SKIP.intersection(p.relative_to(root).parts) or p.is_symlink():
                continue
            if p.is_file() and p.suffix.lower() in CODE and not p.name.startswith('.'):
                if not p.resolve().is_relative_to(root):
                    raise ValueError('source outside repository')
                files.add(p)
    return sorted(files), sorted(set(omitted))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for field in ['repo', 'out', 'python', 'runtime']:
        ap.add_argument('--' + field, required=True)
    ap.add_argument('--include', action='append', required=True)
    ap.add_argument('--exclude', action='append', default=[])
    ap.add_argument('--previous', help='Prior snapshot to reuse if unchanged; otherwise rebuild into --out')
    a = ap.parse_args()
    root, out = Path(a.repo).resolve(), Path(a.out).resolve()
    files, omitted = select(root, a.include, a.exclude)
    if not files: raise ValueError('scope contains no admitted code files')
    revision = git(root, 'rev-parse', 'HEAD')
    status = git(root, 'status', '--porcelain', '--untracked-files=all')
    hashes = {p.relative_to(root).as_posix(): digest(p) for p in files}
    previous_path = Path(a.previous).resolve() if a.previous else None
    if previous_path:
        previous = json.loads(previous_path.read_text())
        if can_reuse(previous, root, revision, status, hashes, a.include, a.exclude):
            print(json.dumps({'snapshot': str(previous_path), 'reused': True,
                              'semantic_truth_verified': False,
                              'resolution_context_fully_fingerprinted': False}))
            return
    out.mkdir(parents=True, exist_ok=False)
    spec = {'root': str(root), 'files': [str(p) for p in files], 'cache': str(out)}
    (out/'worker-input.json').write_text(json.dumps(spec))
    with tempfile.TemporaryDirectory(prefix='graphify-home-') as home:
        subprocess.run([str(Path(a.python).absolute()), '-I', '-B', '-c', WORKER, str(Path(a.runtime).resolve()),
                        str(out/'worker-input.json'), str(out/'graph.json')],
                       cwd=out, check=True, env={'HOME': home, 'PATH': '/usr/bin:/bin',
                                               'PYTHONHASHSEED': '0', 'PYTHONDONTWRITEBYTECODE': '1'})
    if hashes != {p.relative_to(root).as_posix(): digest(p) for p in files}:
        raise ValueError('source changed during extraction; index is unusable')
    if revision != git(root, 'rev-parse', 'HEAD'):
        raise ValueError('repository revision changed; index is unusable')
    if status != git(root, 'status', '--porcelain', '--untracked-files=all'):
        # New index under the repository contributes untracked output. Source
        # fingerprints remain authoritative; report post-run status separately.
        status_after = git(root, 'status', '--porcelain', '--untracked-files=all')
    else: status_after = status
    graph = json.loads((out/'graph.json').read_text())
    snapshot = {'schema_version': 1, 'graphify_version': '0.9.85',
                'graphify_revision': 'b4e6307bf170f27e0cb888c03f4af9308d531a42',
                'repository': {'root': str(root), 'revision': revision,
                               'dirty': bool(status), 'status': status, 'status_after': status_after},
                'scope': {'include': a.include, 'exclude': a.exclude, 'omitted': omitted,
                          'extensions': sorted(CODE), 'skip_directories': sorted(SKIP),
                          'semantic_analysis': False},
                'files': hashes, 'graph': graph,
                'refresh': {'previous_snapshot': str(previous_path) if previous_path else None,
                            'reused': False, 'resolution_context_fully_fingerprinted': False}}
    (out/'snapshot.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2)+'\n')
    # Include this index's own new files in the final status so the first reuse
    # check does not invalidate an otherwise unchanged index inside the repo.
    snapshot['repository']['status_after'] = git(root, 'status', '--porcelain', '--untracked-files=all')
    (out/'snapshot.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'snapshot': str(out/'snapshot.json'), 'files': len(files),
                      'nodes': len(graph.get('nodes', [])), 'edges': len(graph.get('edges', [])), 'reused': False}))


if __name__ == '__main__':
    main()
