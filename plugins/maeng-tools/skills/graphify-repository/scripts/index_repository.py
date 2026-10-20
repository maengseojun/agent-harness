#!/usr/bin/env python3
"""Explicit, offline AST index. No CLI registration, installation, or semantic pass."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

CODE = {'.py', '.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx', '.go', '.rs',
        '.java', '.c', '.h', '.cpp', '.hpp', '.rb', '.cs', '.kt', '.swift', '.lua', '.sol'}
SKIP = {'.git', '.agents', '.codex', '.aws', '.ssh', '.venv', 'node_modules',
        '__pycache__', 'vendor', 'dist', 'build'}
# TODO(MAE-222): the pin stays at 0.9.85. Bumping to 0.9.91 is a separate task that
# must first re-check the revision gate: new PIN_REVISION commit, reviewed external runtime checkout,
# lockfile, and the extract() signature. Do not edit the two constants alone.
# See references/local-evidence.md "Version bump (not done)".
PIN_VERSION = '0.9.85'
PIN_REVISION = 'b4e6307bf170f27e0cb888c03f4af9308d531a42'
CACHE_BASE = Path.home() / '.cache' / 'maeng' / 'graphify'
WORKER = '''import json, sys, tomllib
from pathlib import Path
sys.path.insert(0, sys.argv[1])
version = tomllib.loads((Path(sys.argv[1])/"pyproject.toml").read_text())["project"]["version"]
if version != sys.argv[4]: raise SystemExit("Graphify version mismatch")
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


# The installed runtime is a plain directory (it sits inside another repository), so git state cannot
# identify it. Pin the reviewed source instead: sha256 over (relative path, file sha256) of every
# graphify/**/*.py plus pyproject.toml, computed from the 0.9.85 runtime at PIN_REVISION on 2026-10-17.
PIN_SOURCE_SHA256 = '942420c60047e05cb41e597ba5c950ef5e1fd419983dcbf3c41910c1a8668ea9'


def runtime_source_digest(runtime):
    runtime = Path(runtime)
    files = sorted([p for p in (runtime / 'graphify').rglob('*.py') if '__pycache__' not in p.parts]
                   + [runtime / 'pyproject.toml'])
    h = hashlib.sha256()
    for p in files:
        h.update(p.relative_to(runtime).as_posix().encode() + b'\0'
                 + hashlib.sha256(p.read_bytes()).hexdigest().encode() + b'\n')
    return h.hexdigest()


def verify_runtime(runtime):
    """Refuse unless the runtime's source matches the pinned manifest digest.

    Returns PIN_REVISION (the revision that digest was taken from). Raises ValueError before any extraction.
    """
    runtime = Path(runtime)
    if not (runtime / 'graphify').is_dir() or not (runtime / 'pyproject.toml').is_file():
        raise ValueError(f'Graphify runtime {runtime} has no graphify/ package or pyproject.toml; refusing to extract')
    try:
        digest = runtime_source_digest(runtime)
    except OSError as e:
        raise ValueError(f'Graphify runtime {runtime} is unreadable; refusing to extract ({e})')
    if digest != PIN_SOURCE_SHA256:
        raise ValueError(f'Graphify runtime source digest {digest[:12]} != pinned {PIN_SOURCE_SHA256[:12]} '
                         f'(modified or different version); refusing to extract')
    return PIN_REVISION


def default_cache_root(root):
    """Persistent per-repository extraction cache, outside the repo and any --out dir."""
    return CACHE_BASE / hashlib.sha256(str(Path(root).resolve()).encode()).hexdigest()[:16]


def scoped_status(root, includes, excludes, ignore=()):
    """git status limited to the indexed scope (includes minus excludes).

    Changes elsewhere in the repository, and the index/cache directories
    themselves, must not invalidate an otherwise unchanged index.
    """
    root = Path(root).resolve()
    spec = [*includes, *(f':(exclude){x}' for x in excludes)]
    out = git(root, 'status', '--porcelain', '--untracked-files=all', '--', *spec)
    prefixes = []
    for p in ignore:
        try:
            prefixes.append(Path(p).resolve().relative_to(root).as_posix() + '/')
        except ValueError:
            pass  # outside the repository: cannot appear in its status
    lines = [l for l in out.split('\n') if l and not any(l[3:].startswith(x) for x in prefixes)]
    return '\n'.join(lines)


def can_reuse(previous, root, revision, status, hashes, includes, excludes):
    """Conservative selected-source freshness check; never semantic validation."""
    return (previous.get('graphify_version') == PIN_VERSION
            and previous.get('graphify_revision') == PIN_REVISION
            and previous['repository'].get('status_scope') == 'in-scope'
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


def run_worker(python, runtime, out):
    """Run the pinned AST extraction in an isolated interpreter (mocked in tests)."""
    with tempfile.TemporaryDirectory(prefix='graphify-home-') as home:
        subprocess.run([str(Path(python).absolute()), '-I', '-B', '-c', WORKER, str(Path(runtime).resolve()),
                        str(out/'worker-input.json'), str(out/'graph.json'), PIN_VERSION],
                       cwd=out, check=True, env={'HOME': home, 'PATH': '/usr/bin:/bin',
                                               'PYTHONHASHSEED': '0', 'PYTHONDONTWRITEBYTECODE': '1'})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    for field in ['repo', 'out', 'python', 'runtime']:
        ap.add_argument('--' + field, required=True)
    ap.add_argument('--include', action='append', required=True)
    ap.add_argument('--exclude', action='append', default=[])
    ap.add_argument('--previous', help='Prior snapshot to reuse if unchanged; otherwise rebuild into --out')
    ap.add_argument('--cache-root', help='Persistent extraction cache (default ~/.cache/maeng/graphify/<repo-hash>)')
    a = ap.parse_args(argv)
    root, out = Path(a.repo).resolve(), Path(a.out).resolve()
    files, omitted = select(root, a.include, a.exclude)
    if not files: raise ValueError('scope contains no admitted code files')
    revision = git(root, 'rev-parse', 'HEAD')
    cache_root = Path(a.cache_root).resolve() if a.cache_root else default_cache_root(root)
    ignore = [out, cache_root]
    status = scoped_status(root, a.include, a.exclude, ignore)
    hashes = {p.relative_to(root).as_posix(): digest(p) for p in files}
    previous_path = Path(a.previous).resolve() if a.previous else None
    if previous_path:
        previous = json.loads(previous_path.read_text())
        if can_reuse(previous, root, revision, status, hashes, a.include, a.exclude):
            print(json.dumps({'snapshot': str(previous_path), 'reused': True,
                              'semantic_truth_verified': False,
                              'resolution_context_fully_fingerprinted': False}))
            return
    runtime_revision = verify_runtime(a.runtime)  # before any extraction or output
    out.mkdir(parents=True, exist_ok=False)
    cache_root.mkdir(parents=True, exist_ok=True)
    spec = {'root': str(root), 'files': [str(p) for p in files], 'cache': str(cache_root)}
    (out/'worker-input.json').write_text(json.dumps(spec))
    run_worker(a.python, a.runtime, out)
    if hashes != {p.relative_to(root).as_posix(): digest(p) for p in files}:
        raise ValueError('source changed during extraction; index is unusable')
    if revision != git(root, 'rev-parse', 'HEAD'):
        raise ValueError('repository revision changed; index is unusable')
    # The index and cache directories are excluded from the scoped status, so a
    # differing post-run status means in-scope files really changed during extraction.
    status_after = scoped_status(root, a.include, a.exclude, ignore)
    graph = json.loads((out/'graph.json').read_text())
    snapshot = {'schema_version': 1, 'graphify_version': PIN_VERSION,
                'graphify_revision': runtime_revision,
                'repository': {'root': str(root), 'revision': revision, 'status_scope': 'in-scope',
                               'dirty': bool(status), 'status': status, 'status_after': status_after},
                'scope': {'include': a.include, 'exclude': a.exclude, 'omitted': omitted,
                          'extensions': sorted(CODE), 'skip_directories': sorted(SKIP),
                          'semantic_analysis': False},
                'files': hashes, 'graph': graph,
                'cache_root': str(cache_root),
                'refresh': {'previous_snapshot': str(previous_path) if previous_path else None,
                            'reused': False, 'resolution_context_fully_fingerprinted': False}}
    (out/'snapshot.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'snapshot': str(out/'snapshot.json'), 'files': len(files),
                      'nodes': len(graph.get('nodes', [])), 'edges': len(graph.get('edges', [])), 'reused': False}))


if __name__ == '__main__':
    main()
