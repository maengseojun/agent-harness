#!/usr/bin/env python3
"""Refresh and search local QMD snapshots exported through read-only MCPVault."""

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess as qmd_subprocess
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from mcp_vault import EXPECTED_VAULT, MCPVault, hash_vault_note, load_server_config, validate_vault_root


RUNTIME = Path('/Users/maengseojun/Documents/ChatGPT/Being agents/outputs/obsidian-mae166/qmd-runtime')
QMD = RUNTIME / 'node_modules/.bin/qmd'
EMBED_MODEL = 'hf:Qwen/Qwen3-Embedding-0.6B-GGUF/Qwen3-Embedding-0.6B-Q8_0.gguf'
COLLECTION_RE = re.compile(r'[a-z][a-z0-9-]{0,63}')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def eligible(path):
    if not isinstance(path, str):
        return False
    parts = path.split('/')
    return (len(parts) >= 2 and parts[0] in {'wiki', 'hubs'} and path.endswith('.md')
            and not any(p in {'', '.', '..'} or '\\' in p for p in parts)
            and not any(p.startswith('.') or p.startswith('SYN-') for p in parts))


def validate_collection(collection):
    if not isinstance(collection, str) or not COLLECTION_RE.fullmatch(collection):
        raise ValueError('Invalid collection name')
    return collection


def qmd(*arguments):
    env = dict(os.environ)
    for key in ['INDEX_PATH', 'QMD_CONFIG_DIR', 'XDG_CACHE_HOME', 'QMD_EMBED_MODEL', 'QMD_RERANK_MODEL', 'QMD_QUERY_MODEL', 'QMD_GENERATE_MODEL', 'QMD_TRUST_LOCAL_CONFIG', 'QMD_TRUST_UPDATE_HOOKS']:
        env.pop(key, None)
    env.update(QMD_CONFIG_DIR=str(RUNTIME / 'config'), XDG_CACHE_HOME=str(RUNTIME / 'cache'), QMD_EMBED_MODEL=EMBED_MODEL)
    result = qmd_subprocess.run([str(QMD), '--index', 'obsidian', *arguments], env=env, cwd=RUNTIME,
                                text=True, capture_output=True, check=True)
    return result.stdout


def snapshot_directory(collection):
    validate_collection(collection)
    directory = RUNTIME / 'snapshots' / collection
    candidates = [RUNTIME, RUNTIME / 'snapshots', directory, directory / 'manifest.json']
    if any(path.is_symlink() for path in candidates):
        raise RuntimeError('Symlinked managed search path')
    if not directory.resolve().is_relative_to(RUNTIME.resolve()):
        raise RuntimeError('Search path escapes managed runtime')
    return directory


def _enumerate_note_paths(vault):
    root_listing = vault.list_directory('')
    roots = [name for name in ('wiki', 'hubs') if name in root_listing['dirs']]
    if not roots:
        raise RuntimeError('Configured vault has no wiki/ or hubs/ source folders')
    pending = deque(roots)
    found = []
    while pending:
        directory = pending.popleft()
        listing = vault.list_directory(directory)
        for name in listing['dirs']:
            if name.startswith('.') or name.startswith('SYN-'):
                continue
            pending.append(directory + '/' + name)
        for name in listing['files']:
            path = directory + '/' + name
            if eligible(path):
                found.append(path)
    if len(set(found)) != len(found):
        raise RuntimeError('MCP directory listing returned duplicate source paths')
    return sorted(found)


def _read_exported_notes(paths, vault):
    rows = []
    for path in paths:
        if not eligible(path):
            raise ValueError('Select real Markdown paths under wiki/ or hubs/ only')
        body = vault.read_note_lines(path)
        try:
            body_bytes = body.encode('utf-8')
        except UnicodeError as exc:
            raise RuntimeError('MCP returned note text that is not valid UTF-8') from exc
        source_root = getattr(vault, 'expected_vault', EXPECTED_VAULT)
        if digest(body_bytes) != hash_vault_note(path, source_root):
            raise RuntimeError('MCP raw note read does not match the complete vault file hash')
        rows.append({'path': path, 'body': body})
    return rows


def export_notes(paths=None, *, vault=None):
    """Read exact original Markdown through MCP and verify it against file bytes."""
    if paths is not None:
        if (not paths or any(not eligible(path) for path in paths)
                or len(set(paths)) != len(paths)):
            raise ValueError('Select unique real Markdown paths under wiki/ or hubs/ only')
        selected = list(paths)
    if vault is not None:
        if paths is None:
            selected = _enumerate_note_paths(vault)
        return _read_exported_notes(selected, vault)
    with MCPVault(expected_vault=EXPECTED_VAULT) as connected:
        if paths is None:
            selected = _enumerate_note_paths(connected)
        return _read_exported_notes(selected, connected)


def refresh(collection, paths):
    validate_collection(collection)
    directory = snapshot_directory(collection)
    rows = export_notes(paths)
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / 'manifest.json'
    prior = json.loads(manifest_path.read_text()) if manifest_path.exists() else {'notes': []}
    if manifest_path.exists() and (prior.get('vault') != str(EXPECTED_VAULT) or prior.get('collection') != collection):
        raise RuntimeError('Managed snapshot identity differs')
    previous = {r['file']: r for r in prior['notes']}
    # Only our hash-verified derived copies may be replaced or removed.
    for name, row in previous.items():
        if (directory / name).is_symlink() or not re.fullmatch(r'n-[a-f0-9]{64}\.md', name):
            raise RuntimeError('Unsafe managed snapshot path')
        if not (directory / name).exists() or digest((directory / name).read_bytes()) != row['sha256']:
            raise RuntimeError('Search snapshot was edited; reconcile before refresh')
    notes = []
    for row in rows:
        data = row['body'].encode('utf-8')
        name = 'n-' + digest(row['path'].encode('utf-8')) + '.md'
        target = directory / name
        if target.is_symlink() or (target.exists() and name not in previous):
            raise RuntimeError('Unmanaged search destination')
        if not target.exists() or target.read_bytes() != data:
            stage = directory / (name + '.tmp')
            with stage.open('xb') as stream:
                stream.write(data)
            os.replace(stage, target)
        notes.append({'file': name, 'vault_path': row['path'], 'sha256': digest(data)})
    names = {r['file'] for r in notes}
    for name in previous.keys() - names:
        (directory / name).unlink()
    manifest = {'collection': collection, 'vault': str(EXPECTED_VAULT), 'exported_at': datetime.now(timezone.utc).isoformat(), 'notes': notes, 'indexed': False}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    listing = qmd('collection', 'list')
    if 'qmd://' + collection + '/' not in listing:
        qmd('collection', 'add', str(directory), '--name', collection, '--mask', 'n-*.md')
    qmd('update')
    embedding = qmd('embed', '-c', collection, '--timeout', '60', '--max-docs-per-batch', '16', '--max-batch-mb', '32')
    if re.search(r'\b\d+ chunks still failed\b|Another embed process is already running', embedding):
        raise RuntimeError('QMD reported failed chunks; vector coverage is incomplete')
    manifest['indexed'] = True
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return {'collection': collection, 'notes': len(notes), 'exported_at': manifest['exported_at'], 'snapshot_only': True}


def _read_search_results(collection, query, mode):
    if mode == 'keyword':
        output = qmd('search', query, '-c', collection, '--format', 'json', '-n', '5')
    else:
        typed = 'vec: ' + query if mode == 'vector' else 'lex: ' + query + '\nvec: ' + query
        output = qmd('query', typed, '--no-rerank', '-c', collection, '--format', 'json', '-n', '5')
    results = json.loads(output)
    if not isinstance(results, list):
        raise RuntimeError('QMD returned an invalid result list')
    return results


def search(collection, query, mode):
    validate_collection(collection)
    validate_vault_root(EXPECTED_VAULT, EXPECTED_VAULT)
    manifest = json.loads((snapshot_directory(collection) / 'manifest.json').read_text())
    if manifest.get('vault') != str(EXPECTED_VAULT) or manifest.get('collection') != collection or not manifest.get('indexed'):
        raise RuntimeError('Missing or unfinished managed search snapshot')
    if mode not in {'keyword', 'vector', 'hybrid'}:
        raise ValueError('Unsupported QMD search mode')
    with MCPVault(expected_vault=EXPECTED_VAULT) as vault:
        results = _read_search_results(collection, query, mode)
        mapping = {r['file']: r for r in manifest['notes']}
        for result in results:
            if not isinstance(result, dict) or not isinstance(result.get('file'), str):
                raise RuntimeError('QMD returned a result without a valid collection URI')
            uri = urlsplit(result['file'])
            index = parse_qs(uri.query, keep_blank_values=True)
            if uri.scheme != 'qmd' or uri.netloc != collection or uri.fragment or index not in ({}, {'index': ['obsidian']}):
                raise RuntimeError('QMD returned a result outside the requested collection')
            name = uri.path.removeprefix('/')
            if name not in mapping:
                raise RuntimeError('QMD result has no managed source mapping')
            result.update({k: v for k, v in mapping[name].items() if k != 'file'})
            result['snapshot_exported_at'] = manifest['exported_at']
        paths = list(dict.fromkeys(result['vault_path'] for result in results))
        current_rows = _read_exported_notes(paths, vault) if paths else []
        current = {r['path']: digest(r['body'].encode('utf-8')) for r in current_rows}
    for result in results:
        result['fresh'] = current.get(result['vault_path']) == result['sha256']
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['refresh', 'search'])
    parser.add_argument('--collection', default='wiki')
    parser.add_argument('--paths', nargs='+')
    parser.add_argument('--query')
    parser.add_argument('--mode', choices=['keyword', 'vector', 'hybrid'], default='hybrid')
    args = parser.parse_args()
    if not COLLECTION_RE.fullmatch(args.collection):
        parser.error('Invalid collection name')
    if args.operation == 'search' and (not args.query or '\n' in args.query or '\r' in args.query or args.paths):
        parser.error('Search needs one plain-text query and no --paths')
    if args.operation == 'refresh' and args.query:
        parser.error('Refresh does not accept --query')
    try:
        validate_vault_root(EXPECTED_VAULT, EXPECTED_VAULT)
        load_server_config(expected_vault=EXPECTED_VAULT)
    except RuntimeError as exc:
        parser.error(str(exc))
    RUNTIME.mkdir(parents=True, exist_ok=True)
    snapshot_directory(args.collection)
    if (RUNTIME / 'snapshot.lock').is_symlink():
        parser.error('Symlinked snapshot lock')
    with (RUNTIME / 'snapshot.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        result = refresh(args.collection, args.paths) if args.operation == 'refresh' else search(args.collection, args.query, args.mode)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
