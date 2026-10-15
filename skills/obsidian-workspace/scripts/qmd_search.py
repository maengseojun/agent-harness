"""CLI-derived, rebuildable local QMD search snapshots; the vault remains authoritative."""
import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from source_snapshot import EXPECTED_VAULT, assert_cli_vault, invoke_obsidian

RUNTIME = Path('/Users/maengseojun/Documents/ChatGPT/Being agents/outputs/obsidian-mae166/qmd-runtime')
QMD = RUNTIME / 'node_modules/.bin/qmd'
EMBED_MODEL = 'hf:Qwen/Qwen3-Embedding-0.6B-GGUF/Qwen3-Embedding-0.6B-Q8_0.gguf'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def eligible(path):
    parts = path.split('/')
    return (parts[0] in {'wiki', 'hubs'} and path.endswith('.md')
            and not any(p in {'', '.', '..'} or '\\' in p for p in parts)
            and not any(p.startswith('SYN-') for p in parts))


def evaluate(code):
    value = invoke_obsidian(['eval', 'code=' + code])
    if not value.startswith('=> '):
        raise RuntimeError('Missing Obsidian CLI result')
    return json.loads(value[3:])


def export_notes(paths=None):
    assert_cli_vault(EXPECTED_VAULT)
    if paths is not None and (not paths or any(not eligible(p) for p in paths)):
        raise ValueError('Select real Markdown paths under wiki/ or hubs/ only')
    code = '(async()=>{if(app.vault.adapter.getBasePath()!==' + json.dumps(str(EXPECTED_VAULT)) + ')throw new Error("wrong vault");const paths=' + json.dumps(paths) + ';const files=paths?paths.map(p=>app.vault.getAbstractFileByPath(p)):app.vault.getMarkdownFiles();const out=[];for(const f of files){if(!f||f.extension!=="md")throw new Error("selected note missing");if(!/^(wiki|hubs)\\//.test(f.path)||f.path.split("/").some(p=>p.startsWith("SYN-")))continue;out.push({path:f.path,body:await app.vault.read(f)});}return JSON.stringify(out);})()'
    result = evaluate(code)
    return [r for r in result if eligible(r['path'])]


def qmd(*arguments):
    env = dict(os.environ)
    for key in ['INDEX_PATH', 'QMD_CONFIG_DIR', 'XDG_CACHE_HOME', 'QMD_EMBED_MODEL', 'QMD_RERANK_MODEL', 'QMD_QUERY_MODEL', 'QMD_GENERATE_MODEL', 'QMD_TRUST_LOCAL_CONFIG', 'QMD_TRUST_UPDATE_HOOKS']:
        env.pop(key, None)
    env.update(QMD_CONFIG_DIR=str(RUNTIME / 'config'), XDG_CACHE_HOME=str(RUNTIME / 'cache'), QMD_EMBED_MODEL=EMBED_MODEL)
    result = subprocess.run([str(QMD), '--index', 'obsidian', *arguments], env=env, cwd=RUNTIME,
                            text=True, capture_output=True, check=True)
    return result.stdout


def snapshot_directory(collection):
    directory = RUNTIME / 'snapshots' / collection
    if any(p.is_symlink() for p in [RUNTIME, RUNTIME / 'snapshots', directory, directory / 'manifest.json']):
        raise RuntimeError('Symlinked managed search path')
    if not directory.resolve().is_relative_to(RUNTIME.resolve()):
        raise RuntimeError('Search path escapes managed runtime')
    return directory


def refresh(collection, paths):
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
        data = row['body'].encode()
        name = 'n-' + digest(row['path'].encode()) + '.md'
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


def search(collection, query, mode):
    assert_cli_vault(EXPECTED_VAULT)
    manifest = json.loads((snapshot_directory(collection) / 'manifest.json').read_text())
    if manifest.get('vault') != str(EXPECTED_VAULT) or manifest.get('collection') != collection or not manifest.get('indexed'):
        raise RuntimeError('Missing or unfinished managed search snapshot')
    if mode == 'keyword':
        output = qmd('search', query, '-c', collection, '--format', 'json', '-n', '5')
    else:
        typed = 'vec: ' + query if mode == 'vector' else 'lex: ' + query + '\nvec: ' + query
        output = qmd('query', typed, '--no-rerank', '-c', collection, '--format', 'json', '-n', '5')
    results = json.loads(output)
    mapping = {r['file']: r for r in manifest['notes']}
    for result in results:
        uri = urlsplit(result['file'])
        index = parse_qs(uri.query, keep_blank_values=True)
        if uri.scheme != 'qmd' or uri.netloc != collection or uri.fragment or index not in ({}, {'index': ['obsidian']}):
            raise RuntimeError('QMD returned a result outside the requested collection')
        name = uri.path.removeprefix('/')
        if name not in mapping:
            raise RuntimeError('QMD result has no managed source mapping')
        result.update({k: v for k, v in mapping[name].items() if k != 'file'})
        result['snapshot_exported_at'] = manifest['exported_at']
    current = {r['path']: digest(r['body'].encode()) for r in export_notes(list({r['vault_path'] for r in results}))} if results else {}
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
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', args.collection):
        parser.error('Invalid collection name')
    if args.operation == 'search' and (not args.query or '\n' in args.query or '\r' in args.query or args.paths):
        parser.error('Search needs one plain-text query and no --paths')
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
