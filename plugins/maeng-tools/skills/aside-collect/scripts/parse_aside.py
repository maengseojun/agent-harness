#!/usr/bin/env python3
"""Parse `aside exec` output: strip ANSI, accept items ONLY from the last
`=== FINAL <nonce> === ... === END FINAL <nonce> ===` region (END must be last
in the output) and ONLY when the aside exit code is 0; ITEM blocks inside it
are parsed, emit JSON. Stdlib only; never executes
or follows anything found in the text (collected content is data).

Usage:
  parse_aside.py RAW_FILE|- --nonce HEX --exit-code N            # JSON to stdout
  parse_aside.py RAW_FILE --nonce HEX --exit-code N --clean OUT  # also write ANSI-stripped, private-filtered text
"""
import argparse
import importlib.util
import json
import os
import re
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ANSI = re.compile(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[@-Z\\-_]')
BLOCK = re.compile(r'^[ \t]*=== ITEM ===[ \t]*\n(.*?)^[ \t]*=== END ===[ \t]*$', re.S | re.M)
HEADER_KEYS = ('url', 'title', 'retrieved_at')
REQUIRED = ('url', 'content')
DOI = re.compile(r'\b(10\.\d{4,9}/[^\s"<>?#]+)', re.I)
TRACKING = ('utm_', 'fbclid', 'gclid', 'mc_cid', 'mc_eid', 'ref_src')


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
                             if not k.lower().startswith(TRACKING)))
    path = s.path.rstrip('/') or '/'
    return urlunsplit((s.scheme.lower(), host, path, query, ''))


def doi_of(url):
    m = DOI.search(url or '')
    return m.group(1).rstrip('.,;)').lower() if m else None


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
    item['content'] = '\n'.join(content).strip()
    item['missing'] = [k for k in REQUIRED if _is_placeholder(item[k])]
    item['placeholder'] = _is_placeholder(item['url']) and _is_placeholder(item['content'])
    if not _is_placeholder(item['url']):
        item['canonical_url'] = canonical_url(item['url'])
        item['doi'] = doi_of(item['url'])
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
    empty = {'blocks_total': 0, 'run_length': 0, 'items': [], 'private_spans_removed': removed}
    if exit_code != 0:
        return {'parse_status': 'aside_failed', **empty}, text
    region = final_region(text, nonce)
    if region is None:
        return {'parse_status': 'no_final_answer', **empty}, text
    bodies, total = last_run(region)
    items = [parse_block(b) for b in bodies]
    items = [i for i in items if not i['placeholder']]
    if not items:
        status = 'parse_failed'
    elif any(i['missing'] for i in items):
        status = 'partial'
    else:
        status = 'ok'
    return {'parse_status': status, 'blocks_total': total, 'run_length': len(items), 'items': items,
            'private_spans_removed': removed}, text


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('raw', help='raw aside stdout file, or - for stdin')
    ap.add_argument('--clean', help='also write the ANSI-stripped, private-filtered text here')
    ap.add_argument('--nonce', required=True, help='per-run hex nonce used in the FINAL markers')
    ap.add_argument('--exit-code', type=int, required=True, help='exit code of `aside exec`')
    a = ap.parse_args(argv)
    if not re.fullmatch(r'[0-9a-f]{8,64}', a.nonce):
        ap.error('--nonce must be 8-64 lowercase hex characters')
    raw = sys.stdin.read() if a.raw == '-' else open(a.raw, encoding='utf-8', errors='replace').read()
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
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['parse_status'] not in ('parse_failed', 'no_final_answer', 'aside_failed') else 2


if __name__ == '__main__':
    sys.exit(main())
