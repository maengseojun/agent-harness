#!/usr/bin/env python3
"""Reviewed small subgraph to Archify architecture JSON + lossless evidence sidecar."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess


def source_ref(item):
    path, loc = item.get('source_file'), item.get('source_location')
    if not isinstance(path, str) or not path:
        return None
    parts = PurePosixPath(path)
    if parts.is_absolute() or '..' in parts.parts or '\\' in path:
        raise ValueError('source path must be repository-relative')
    ref = {'path': path}
    m = re.fullmatch(r'L(\d+)(?:[-:]L?(\d+))?', str(loc))
    if m:
        ref['line'] = int(m[1])
        if m[2]: ref['end_line'] = int(m[2])
    return ref


def status(item):
    value = item.get('confidence')
    return value if value in {'EXTRACTED', 'INFERRED'} else 'UNVERIFIED'


def convert(snapshot, selection, repo):
    graph = snapshot['graph']
    ids = selection['nodes']
    if not ids or len(ids) != len(set(ids)):
        raise ValueError('select unique nodes for a focused subgraph')
    for field in ['question', 'assumptions', 'example', 'check_question', 'answer', 'scope', 'excluded']:
        if field not in selection:
            raise ValueError(f'missing teaching/scope field: {field}')
    nodes = {n['id']: n for n in graph['nodes']}
    if not set(ids).issubset(nodes): raise ValueError('unknown selected node')
    if repo.resolve() != Path(snapshot['repository']['root']).resolve():
        raise ValueError('wrong source repository')
    head = subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'], check=True,
                          capture_output=True, text=True).stdout.strip()
    if head != snapshot['repository']['revision']:
        raise ValueError('repository revision changed; rebuild the index')
    # Check current working source against indexed fingerprints. This checks
    # freshness and location; it cannot establish semantic truth.
    for path, expected in snapshot['files'].items():
        ref = source_ref({'source_file': path})
        p = (repo/ref['path']).resolve()
        if not p.is_relative_to(repo.resolve()) or not p.is_file():
            raise ValueError('source missing or outside repository')
        if hashlib.sha256(p.read_bytes()).hexdigest() != expected:
            raise ValueError(f'stale index: {path}')
    mapped = {nid: f'n{i+1}' for i, nid in enumerate(ids)}
    components, evidence_nodes = [], []
    for i, nid in enumerate(ids):
        n = nodes[nid]
        ref = source_ref(n)
        component = {'id': mapped[nid], 'type': 'backend', 'label': selection.get('labels', {}).get(nid, n.get('label', nid)),
                     'sublabel': n.get('type', 'symbol'), 'tag': status(n),
                     'pos': [80+(i%3)*340, 140+(i//3)*210], 'size': [210, 84]}
        # Archify sources require immutable repository metadata. Working-tree
        # lines are retained in provenance/cards, never linked falsely to HEAD.
        components.append(component)
        evidence_nodes.append({'id': mapped[nid], 'graphify_id': nid, 'raw': n, 'source': ref,
                               'evidence_status': status(n)})
    edges = graph.get('edges', graph.get('links', []))
    connections, evidence_edges = [], []
    seen = set()
    for selected in selection.get('edges', []):
        index = selected['index']
        if type(index) is not int or index < 0 or index >= len(edges) or index in seen:
            raise ValueError('invalid or duplicate edge index')
        seen.add(index)
        e = edges[index]
        if ('_src' in e) != ('_tgt' in e): raise ValueError('partial direction markers')
        if '_src' in e:
            src, tgt, basis = e['_src'], e['_tgt'], '_src/_tgt'
        elif graph.get('directed') is False:
            if not selected.get('direction_note'):
                raise ValueError('directed:false needs explicit reviewed direction')
            src, tgt, basis = selected.get('from'), selected.get('to'), 'source-reviewed override'
            if {src, tgt} != {e['source'], e['target']}:
                raise ValueError('override must preserve edge endpoints')
        else:
            src, tgt, basis = e['source'], e['target'], 'raw extraction arc order'
        if src not in mapped or tgt not in mapped:
            raise ValueError('selected edge endpoint is outside selected nodes')
        if selected.get('from', src) != src or selected.get('to', tgt) != tgt:
            raise ValueError('review conflicts with stored direction')
        review = selected.get('review', {})
        if review.get('status') not in {'source-confirmed', 'unverified'}:
            raise ValueError('edge requires explicit source-confirmed or unverified review')
        if not review.get('note'): raise ValueError('edge review needs a reason')
        refs = review.get('sources', [])
        if review['status'] == 'source-confirmed' and not refs:
            raise ValueError('source-confirmed review needs source lines')
        for ref in refs:
            path, line = ref['path'], ref.get('line')
            source_ref({'source_file': path})
            if path not in snapshot['files'] or type(line) is not int or line < 1:
                raise ValueError('review source must be an indexed file and positive line')
            if line > len((repo/path).read_text().splitlines()): raise ValueError('source line out of range')
        relation = e.get('relation', e.get('type', 'relation'))
        effective = status(e) if review['status'] == 'source-confirmed' else 'UNVERIFIED'
        connections.append({'id': f'e{index}', 'from': mapped[src], 'to': mapped[tgt],
                            'label': f'{relation} · {effective}',
                            'variant': 'default' if effective == 'EXTRACTED' else 'dashed'})
        evidence_edges.append({'id': f'e{index}', 'index': index, 'raw': e, 'from': src, 'to': tgt,
                               'direction_basis': basis, 'selection': selected,
                               'extraction_status': status(e), 'display_status': effective,
                               'extracted_source': source_ref(e)})
    cards = [
        {'dot': 'cyan', 'title': '학습 질문', 'items': [selection['question']]},
        {'dot': 'amber', 'title': '전제와 범위', 'items': selection['assumptions'] + [selection['scope'], '제외: '+', '.join(selection['excluded'])]},
        {'dot': 'emerald', 'title': '예시와 확인', 'items': [selection['example'], selection['check_question'], selection['answer']]},
        {'dot': 'slate', 'title': '근거의 한계', 'items': ['실선: 확인한 추출 관계. 점선: 추론 또는 미확인 관계.',
         '인용 위치 검사는 해석의 진실성을 증명하지 않습니다. JSON과 provenance를 함께 확인하세요.',
         '작업 트리 dirty: '+str(snapshot['repository']['dirty'])]},
    ]
    reference_lines = [f"{ref['path']}:{ref['line']} · {edge['selection']['review']['note']}"
                       for edge in evidence_edges for ref in edge['selection']['review'].get('sources', [])]
    if reference_lines:
        cards.append({'dot': 'violet', 'title': '작업 원문 근거', 'items': reference_lines})
    candidate = {'schema_version': 1, 'diagram_type': 'architecture',
                 'meta': {'title': selection.get('title', selection['question']),
                          'subtitle': snapshot['repository']['revision'][:12]+' · working-source evidence',
                          'locale': 'ko', 'output': selection['output'],
                          'animation': 'none', 'quality_profile': 'standard'},
                 'components': components, 'connections': connections, 'cards': cards}
    provenance = {'schema_version': 1, 'adapter': 'being-agents-minimal-v1',
                  'repository': snapshot['repository'], 'scope': snapshot['scope'], 'files': snapshot['files'],
                  'selection': selection, 'nodes': evidence_nodes, 'edges': evidence_edges,
                  'omitted_nodes': len(nodes)-len(ids), 'omitted_edges': len(edges)-len(evidence_edges),
                  'graph_directed': graph.get('directed'), 'semantic_truth_verified_by_adapter': False}
    return candidate, provenance


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ['snapshot', 'selection', 'repo', 'out']:
        p.add_argument('--'+arg, required=True)
    a = p.parse_args()
    snapshot_path = Path(a.snapshot)
    candidate, provenance = convert(json.loads(snapshot_path.read_text()),
                                    json.loads(Path(a.selection).read_text()), Path(a.repo))
    provenance['snapshot_sha256'] = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
    out = Path(a.out)
    if out.exists() or out.with_suffix('.provenance.json').exists():
        raise ValueError('output exists; use a new candidate path')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(candidate, ensure_ascii=False, indent=2)+'\n')
    out.with_suffix('.provenance.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2)+'\n')


if __name__ == '__main__': main()
