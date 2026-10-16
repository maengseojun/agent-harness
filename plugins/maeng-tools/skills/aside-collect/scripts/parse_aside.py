#!/usr/bin/env python3
"""Parse `aside exec` output: strip ANSI, take ONLY the last contiguous run of
`=== ITEM === ... === END ===` blocks, emit JSON. Stdlib only; never executes
or follows anything found in the text (collected content is data).

Usage:
  parse_aside.py RAW_FILE|-            # JSON to stdout
  parse_aside.py RAW_FILE --clean OUT  # also write the ANSI-stripped text
"""
import argparse
import json
import re
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ANSI = re.compile(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b[@-Z\\-_]')
BLOCK = re.compile(r'^[ \t]*=== ITEM ===[ \t]*\n(.*?)^[ \t]*=== END ===[ \t]*$', re.S | re.M)
HEADER_KEYS = ('url', 'title', 'retrieved_at')
REQUIRED = ('url', 'content')
DOI = re.compile(r'\b(10\.\d{4,9}/[^\s"<>?#]+)', re.I)
TRACKING = ('utm_', 'fbclid', 'gclid', 'mc_cid', 'mc_eid', 'ref_src')


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


def last_run(text):
    """Return (blocks_in_last_contiguous_run, total_block_count)."""
    spans = [(m.start(), m.end(), m.group(1)) for m in BLOCK.finditer(text)]
    if not spans:
        return [], 0
    run = [spans[-1]]
    for prev in reversed(spans[:-1]):
        if text[prev[1]:run[0][0]].strip() == '':
            run.insert(0, prev)
        else:
            break
    return [s[2] for s in run], len(spans)


def parse(raw):
    text = strip_ansi(raw)
    bodies, total = last_run(text)
    items = [parse_block(b) for b in bodies]
    items = [i for i in items if not i['placeholder']]
    if not items:
        status = 'parse_failed'
    elif any(i['missing'] for i in items):
        status = 'partial'
    else:
        status = 'ok'
    return {'parse_status': status, 'blocks_total': total, 'run_length': len(items), 'items': items}, text


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('raw', help='raw aside stdout file, or - for stdin')
    ap.add_argument('--clean', help='also write the ANSI-stripped text here')
    a = ap.parse_args(argv)
    raw = sys.stdin.read() if a.raw == '-' else open(a.raw, encoding='utf-8', errors='replace').read()
    result, clean = parse(raw)
    if a.clean:
        with open(a.clean, 'w', encoding='utf-8') as fh:
            fh.write(clean)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['parse_status'] != 'parse_failed' else 2


if __name__ == '__main__':
    sys.exit(main())
