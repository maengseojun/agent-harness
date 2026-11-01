#!/usr/bin/env python3
"""Parse `aside exec` output: strip ANSI, accept items ONLY from the last
`=== FINAL <nonce> === ... === END FINAL <nonce> ===` region (END must be last
in the output) and ONLY when the aside exit code is 0; ITEM blocks inside it
are parsed, GAP blocks there become `gaps` (places not covered), emit JSON. Stdlib only; never executes
or follows anything found in the text (collected content is data).

Usage:
  parse_aside.py RAW_FILE|- --nonce HEX --exit-code N            # JSON to stdout
  parse_aside.py RAW_FILE --nonce HEX --exit-code N --clean OUT  # also write ANSI-stripped, private-filtered text
  ... --sidecar JSON [--world personal|eta]   # merge THIS run's nonce/exit_code/parse_status/private_spans_removed
                                              # into the sidecar (a retry's call makes it describe the final run)
  ... --delete-scratch   # after parsing, delete RAW_FILE (<STAMP>-<nonce>.out.txt) and its .err.txt sibling
"""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import re
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ANSI = re.compile(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[@-Z\\-_]')
BLOCK = re.compile(r'^[ \t]*=== ITEM ===[ \t]*\n(.*?)^[ \t]*=== END ===[ \t]*$', re.S | re.M)
# Scanned left to right, so a GAP quoted inside an ITEM's content is consumed by that ITEM, never read as a gap.
ANY_BLOCK = re.compile(r'^[ \t]*=== (ITEM|GAP) ===[ \t]*\n(.*?)^[ \t]*=== END ===[ \t]*$', re.S | re.M)
ESCAPED_MARKER = re.compile(r'^([ \t]*)\\===', re.M)  # content lines starting with === are sent as \===
GAP_KINDS = ('login_required', 'session_expired', 'forbidden', 'rate_limited', 'timeout', 'js_empty',
             'gone', 'paywalled', 'refused', 'searched_none', 'cap_reached')
HEADER_KEYS = ('url', 'title', 'retrieved_at')
REQUIRED = ('url', 'content')
DOI = re.compile(r'\b(10\.\d{4,9}/[^\s"<>?#]+)', re.I)
ARXIV = re.compile(r'arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5}|[a-z-]+(?:\.[a-z]{2})?/\d{7})(?:v\d+)?', re.I)
TRACKING = ('utm_', 'fbclid', 'gclid', 'mc_cid', 'mc_eid', 'ref_src')
TRACKING_EXACT = {'ref', 'igshid', 'si'}  # si: YouTube/Spotify share token


FILTER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..',
                           'obsidian-workspace', 'scripts', 'private_filter.py')


class FilterUnavailable(RuntimeError):
    pass


def load_filter(path=None):
    """Load the nesting-aware private filter from the sibling obsidian-workspace skill."""
    path = os.path.normpath(path or FILTER_PATH)
    try:
        spec = importlib.util.spec_from_file_location('private_filter', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if not callable(getattr(mod, 'strip_private', None)):
            raise AttributeError('strip_private missing')
        return mod
    except Exception as e:  # missing/broken filter must fail closed
        raise FilterUnavailable(f'private filter unavailable at {path}: {e}')


def strip_ansi(text):
    text = ANSI.sub('', text.replace('\r\n', '\n'))
    return text.replace('\r', '\n')


def canonical_url(url):
    """Lowercase scheme/host, drop fragment, default port, tracking params, trailing slash."""
    try:
        s = urlsplit(url.strip())
    except ValueError:
        return url.strip()
    if not s.scheme or not s.netloc:
        return url.strip()
    host = (s.hostname or '').lower()
    port = s.port
    if port and not ((s.scheme == 'http' and port == 80) or (s.scheme == 'https' and port == 443)):
        host = f'{host}:{port}'
    query = urlencode(sorted((k, v) for k, v in parse_qsl(s.query, keep_blank_values=True)
                             if not k.lower().startswith(TRACKING) and k.lower() not in TRACKING_EXACT))
    path = s.path.rstrip('/') or '/'
    return urlunsplit((s.scheme.lower(), host, path, query, ''))


def doi_of(url):
    m = DOI.search(url or '')
    return m.group(1).rstrip('.,;)').lower() if m else None


def work_key(url):
    """Dedupe key for one work across versions and mirrors: DOI, then arXiv id without version, else canonical URL."""
    doi = doi_of(url)
    if doi:
        return f'doi:{doi}'
    m = ARXIV.search(url or '')
    return f'arxiv:{m.group(1).lower()}' if m else canonical_url(url)


def parse_gap(body):
    gap = {'scope': '', 'kind': '', 'evidence': ''}
    for line in body.split('\n'):
        m = re.match(r'^\s*(scope|kind|evidence)\s*:\s?(.*)$', line, re.I)
        if m:
            gap[m.group(1).lower()] = m.group(2).strip()
    kind = gap['kind'].lower()
    gap['kind'] = kind if kind in GAP_KINDS else f'unknown:{gap["kind"]}'
    return gap


def _is_placeholder(value):
    v = (value or '').strip()
    return not v or (v.startswith('<') and v.endswith('>')) or v.startswith('...')


def parse_block(body):
    lines = body.split('\n')
    item = {k: '' for k in HEADER_KEYS}
    content, in_content = [], False
    for line in lines:
        if in_content:
            content.append(line)
            continue
        m = re.match(r'^\s*(url|title|retrieved_at|content)\s*:\s?(.*)$', line, re.I)
        if not m:
            continue
        key, val = m.group(1).lower(), m.group(2)
        if key == 'content':
            in_content = True
            content.append(val)
        else:
            item[key] = val.strip()
    item['content'] = ESCAPED_MARKER.sub(r'\1===', '\n'.join(content).strip())
    item['missing'] = [k for k in REQUIRED if _is_placeholder(item[k])]
    item['placeholder'] = _is_placeholder(item['url']) and _is_placeholder(item['content'])
    if not _is_placeholder(item['url']):
        item['canonical_url'] = canonical_url(item['url'])
        item['doi'] = doi_of(item['url'])
        item['work_key'] = work_key(item['url'])
    return item


def final_region(text, nonce):
    """Return the body between the LAST `=== FINAL <nonce> ===` and its
    `=== END FINAL <nonce> ===`, or None. The END marker must be the last
    non-whitespace content of the (ANSI-stripped) output."""
    n = re.escape(nonce)
    ends = list(re.finditer(rf'^[ \t]*=== END FINAL {n} ===[ \t]*$', text, re.M))
    if not ends or text[ends[-1].end():].strip() != '':
        return None
    end = ends[-1]
    starts = list(re.finditer(rf'^[ \t]*=== FINAL {n} ===[ \t]*\n', text[:end.start()], re.M))
    if not starts:
        return None
    return text[starts[-1].end():end.start()]


STRAY_MARKER = re.compile(r'^[ \t]*=== (?:ITEM|GAP|END) ===[ \t]*$', re.M)


def split_gaps(region):
    """Top-level GAP bodies, the region with those blocks removed so ITEM runs stay contiguous, and
    whether the structure is ambiguous. A marker line left outside every block means an unescaped
    marker inside content cut a block short; then no GAP can be trusted (fail closed)."""
    gaps, kept, outside, pos = [], [], [], 0
    for m in ANY_BLOCK.finditer(region):
        outside.append(region[pos:m.start()])
        if m.group(1) == 'GAP':
            gaps.append(m.group(2))
            kept.append(region[pos:m.start()])
        else:
            kept.append(region[pos:m.end()])
        pos = m.end()
    kept.append(region[pos:])
    outside.append(region[pos:])
    ambiguous = bool(STRAY_MARKER.search(''.join(outside)))
    return ([] if ambiguous else gaps), ''.join(kept), ambiguous


def last_run(region):
    """Blocks of the last contiguous run (whitespace-only between blocks) inside the region."""
    spans = [(m.start(), m.end(), m.group(1)) for m in BLOCK.finditer(region)]
    if not spans:
        return [], 0
    run = [spans[-1]]
    for prev in reversed(spans[:-1]):
        if region[prev[1]:run[0][0]].strip() == '':
            run.insert(0, prev)
        else:
            break
    return [s[2] for s in run], len(spans)


def parse(raw, nonce, exit_code):
    """Items come ONLY from the last nonce-delimited FINAL region and ONLY when
    exit_code == 0. Everything else yields zero items."""
    text = strip_ansi(raw)
    # Private spans are removed BEFORE parsing or persisting anything (fail closed).
    text, removed = load_filter().strip_private(text)
    empty = {'blocks_total': 0, 'run_length': 0, 'items': [], 'gaps': [], 'private_spans_removed': removed}
    if exit_code != 0:
        return {'parse_status': 'aside_failed', **empty}, text
    region = final_region(text, nonce)
    if region is None:
        return {'parse_status': 'no_final_answer', **empty}, text
    gap_bodies, items_region, ambiguous = split_gaps(region)
    gaps = [g for g in map(parse_gap, gap_bodies) if not _is_placeholder(g['scope'])]
    bodies, total = last_run(items_region)
    items = [parse_block(b) for b in bodies]
    items = [i for i in items if not i['placeholder']]
    if not items:
        status = 'gaps_only' if gaps else 'parse_failed'
    elif ambiguous or any(i['missing'] for i in items):
        status = 'partial'
    else:
        status = 'ok'
    return {'parse_status': status, 'blocks_total': total, 'run_length': len(items), 'items': items,
            'gaps': gaps, 'structure_ambiguous': ambiguous, 'private_spans_removed': removed}, text


def update_sidecar(path, nonce, exit_code, result, world=None):
    """Make the sidecar describe THIS run. If it described a different run (the failed first
    attempt), keep that attempt under `first_run` and overwrite the run fields."""
    data = {}
    if os.path.exists(path):
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
    if data.get('nonce') and data['nonce'] != nonce:
        data.setdefault('first_run', {k: data.get(k) for k in ('nonce', 'exit_code', 'parse_status')})
    data.update(nonce=nonce, exit_code=exit_code, parse_status=result['parse_status'],
                private_spans_removed=result['private_spans_removed'])
    if world:
        data['world'] = world
    tmp = f'{path}.tmp-{os.getpid()}'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def delete_scratch(raw_path, nonce):
    """Delete the unfiltered scratch capture (and its .err.txt sibling) of this run. Only regular,
    non-symlink files named `<...><nonce>.out.txt` / `.err.txt`, the shape the skill creates."""
    base = os.path.basename(raw_path)
    if not base.endswith('.out.txt') or nonce not in base:
        return []
    gone = []
    for p in (raw_path, raw_path[:-len('.out.txt')] + '.err.txt'):
        if os.path.isfile(p) and not os.path.islink(p):
            os.unlink(p)
            gone.append(p)
    return gone


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('raw', help='raw aside stdout file, or - for stdin')
    ap.add_argument('--clean', help='also write the ANSI-stripped, private-filtered text here')
    ap.add_argument('--nonce', required=True, help='per-run hex nonce used in the FINAL markers')
    ap.add_argument('--exit-code', type=int, required=True, help='exit code of `aside exec`')
    ap.add_argument('--sidecar', help='JSON sidecar to update with this run\'s result')
    ap.add_argument('--world', choices=('personal', 'eta'), help='write `world` into the sidecar')
    ap.add_argument('--delete-scratch', action='store_true', help='delete the unfiltered scratch capture after parsing')
    a = ap.parse_args(argv)
    if not re.fullmatch(r'[0-9a-f]{8,64}', a.nonce):
        ap.error('--nonce must be 8-64 lowercase hex characters')
    raw = sys.stdin.read() if a.raw == '-' else Path(a.raw).read_text(encoding='utf-8', errors='replace')
    try:
        result, clean = parse(raw, a.nonce, a.exit_code)
    except FilterUnavailable as e:
        print(f'refusing to parse/write: {e}', file=sys.stderr)
        return 3
    if a.clean:
        try:
            fh = open(a.clean, 'x', encoding='utf-8')  # exclusive: raw captures are immutable
        except FileExistsError:
            print(f'refusing to overwrite existing capture: {a.clean}', file=sys.stderr)
            return 2
        with fh:
            fh.write(clean)
    if a.sidecar:
        update_sidecar(a.sidecar, a.nonce, a.exit_code, result, a.world)
    if a.delete_scratch and a.raw != '-':
        delete_scratch(a.raw, a.nonce)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['parse_status'] not in ('parse_failed', 'no_final_answer', 'aside_failed') else 2


if __name__ == '__main__':
    sys.exit(main())
