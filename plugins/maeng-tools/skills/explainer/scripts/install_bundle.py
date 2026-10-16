#!/usr/bin/env python3
"""Install the two sibling explanation skills with rollback copies and Codex exclusion."""
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

RETIRED = ('references/excalidrawz-setup.md', 'scripts/build_templates.py', 'references/editorial-design.md', 'references/upstream-catalogue.md', 'references/visual-grammar.md', 'references/visual-profiles.md', 'references/representation-selection.md', 'references/structure-catalogue.md', 'references/visual-reference-library.md', 'references/dense-worked-example.md', 'references/blocks-and-arrows-design.md', 'references/diagram-graph-composition.md', 'references/casual.md', 'references/personal-drawio.md', 'references/diagrams-net-setup.md', 'assets/drawio/composition-examples.drawio', 'assets/drawio/dense-library-seats-data.json', 'assets/drawio/dense-library-seats.drawio', 'assets/drawio/mcp-verification.json', 'assets/drawio/korean-layout.graphml', 'assets/drawio/dense-library-cases.png', 'assets/drawio/dense-library-rules.png', 'assets/drawio/structure-templates.drawio', 'assets/drawio/composition-data.json', 'assets/drawio/diagram-explainer.drawio-library.xml', 'assets/drawio/editor-config.json', 'assets/drawio/index.json', 'assets/drawio/casual/provenance.json', 'assets/drawio/casual/approval-flow.png', 'assets/drawio/casual/approval-flow.drawio', 'assets/drawio/profiles/academic-pretendard.json', 'assets/drawio/profiles/balanced-editorial.json', 'assets/drawio/profiles/casual.json')


def install(source: Path, target: Path, backups: Path):
    source, target = source.resolve(), target.resolve()
    if source == target:
        raise ValueError('Source and installation must differ')
    names = ('explainer', 'diagram-explainer')
    for name in names:
        if not (source / name / 'SKILL.md').is_file():
            raise ValueError(f'Missing source skill: {name}')
    backup = backups / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup.mkdir(parents=True)
    target.mkdir(parents=True, exist_ok=True)
    installed = []
    try:
        for name in names:
            live = target / name
            stage = Path(tempfile.mkdtemp(prefix=f'.{name}-', dir=target))
            try:
                if live.is_symlink():
                    raise ValueError(f'Inspect symlinked installation before replacing: {live}')
                if live.exists():
                    shutil.copytree(live, stage, dirs_exist_ok=True)
                shutil.copytree(source / name, stage, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))
                if name == 'diagram-explainer':
                    for relative in RETIRED:
                        (stage / relative).unlink(missing_ok=True)
                if live.exists():
                    live.rename(backup / name)
                installed.append(name)
                stage.rename(live)
            finally:
                if stage.exists():
                    shutil.rmtree(stage)
        files = {}
        for name in names:
            for src in (source / name).rglob('*'):
                if not src.is_file() or '__pycache__' in src.parts:
                    continue
                relative = src.relative_to(source)
                dst = target / relative
                if src.read_bytes() != dst.read_bytes():
                    raise ValueError(f'Installed bytes differ: {relative}')
                files[str(relative)] = hashlib.sha256(dst.read_bytes()).hexdigest()
        (backup / 'installation.json').write_text(json.dumps({'installed': installed, 'restored': False}))
    except Exception:
        restore(target, backup, installed)
        raise
    return {'source': str(source), 'target': str(target), 'backup': str(backup), 'installed': installed, 'files': files}


def restore(target: Path, backup: Path, names):
    for name in reversed(names):
        live = target / name
        if live.exists():
            # Preserve the replaced version too; rollback never discards it.
            live.rename(backup / (name + '.replaced'))
        old = backup / name
        if old.exists():
            old.rename(live)


def codex_request(binary: str, method: str, params):
    process = subprocess.Popen([binary, 'app-server', '--listen', 'stdio://'],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True)
    def request(ident, method, params):
        process.stdin.write(json.dumps({'id': ident, 'method': method, 'params': params}) + '\n')
        process.stdin.flush()
        for line in process.stdout:
            response = json.loads(line)
            if response.get('id') == ident:
                if 'error' in response:
                    raise RuntimeError(response['error'])
                return response['result']
        raise RuntimeError('Codex app-server closed without a response')
    try:
        request(1, 'initialize', {'clientInfo': {'name': 'explainer-installer', 'version': '1'}})
        process.stdin.write('{"method":"initialized"}\n')
        process.stdin.flush()
        return request(2, method, params)
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-skills', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--target', type=Path, default=Path.home() / '.agents/skills')
    parser.add_argument('--backups', type=Path, default=Path.home() / '.codex/skill-backups/explainer')
    parser.add_argument('--codex', help='Verified Codex CLI executable; writes persistent name-based Excalidraw exclusion')
    parser.add_argument('--restore', type=Path, help='Restore the previous pair from this backup; exclusion remains intentional')
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    if args.restore:
        marker = args.restore / 'installation.json'
        previous = json.loads(marker.read_text())
        if previous['restored']:
            raise ValueError('This backup was already restored')
        names = previous['installed']
        restore(args.target, args.restore, names)
        previous['restored'] = True
        marker.write_text(json.dumps(previous))
        result = {'restored': names, 'backup': str(args.restore)}
    else:
        result = None
        try:
            result = install(args.source_skills, args.target, args.backups)
            if args.codex:
                result['exclusion'] = codex_request(args.codex, 'skills/config/write',
                                                   {'name': 'excalidraw-style', 'enabled': False})
                if result['exclusion'].get('effectiveEnabled') is not False:
                    raise RuntimeError('Codex did not confirm the skill is disabled')
                inventory = codex_request(args.codex, 'skills/list', {'cwds': [str(args.target.parent)], 'forceReload': True})
                entries = [skill for scope in inventory['data'] for skill in scope.get('skills', [])
                           if skill.get('name') == 'excalidraw-style']
                if any(skill.get('enabled', True) for skill in entries):
                    raise RuntimeError('Excalidraw remains in the enabled skill inventory')
                result['inventory'] = inventory
            else:
                result['exclusion'] = 'not configured; file-only installation'
            result['status'] = 'installed'
        except Exception as error:
            if result is not None:
                backup = Path(result['backup'])
                restore(args.target, backup, result['installed'])
                marker = backup / 'installation.json'
                previous = json.loads(marker.read_text())
                previous['restored'] = True
                marker.write_text(json.dumps(previous))
                result['installation_rolled_back'] = True
            else:
                result = {}
            result.update(status='failed', error=str(error))
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2))
            raise

    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({'receipt': str(args.receipt), 'backup': result.get('backup'), 'exclusion': result.get('exclusion')}))


if __name__ == '__main__':
    main()
