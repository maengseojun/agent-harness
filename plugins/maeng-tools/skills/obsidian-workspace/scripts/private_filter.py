#!/usr/bin/env python3
"""Pre-write filter for vault notes: drop <private>...</private> spans and apply
opt-in regex redaction. Stdlib only; reads stdin or a file, writes stdout.

  private_filter.py [FILE] [--patterns patterns.json]

patterns.json: [{"name": "api-key", "pattern": "sk-[A-Za-z0-9]{20,}"}, ...]
Redaction runs only when --patterns is given (opt-in). An unclosed <private>
removes everything after it (fail safe). A JSON summary goes to stderr.
"""
import argparse
import json
import re
import sys

PRIVATE = re.compile(r'<private>.*?</private>', re.S | re.I)
OPEN = re.compile(r'<private>', re.I)


def strip_private(text):
    text, n = PRIVATE.subn('[private omitted]', text)
    m = OPEN.search(text)
    if m:
        text, n = text[:m.start()] + '[private omitted]', n + 1
    return text, n


def redact(text, patterns):
    counts = {}
    for p in patterns:
        rx = re.compile(p['pattern'])
        text, c = rx.subn(f"[redacted:{p['name']}]", text)
        if c:
            counts[p['name']] = c
    return text, counts


def apply(text, patterns=None):
    text, private = strip_private(text)
    counts = {}
    if patterns:
        text, counts = redact(text, patterns)
    return text, {'private_spans': private, 'redacted': counts}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file', nargs='?', default='-')
    ap.add_argument('--patterns')
    a = ap.parse_args(argv)
    text = sys.stdin.read() if a.file == '-' else open(a.file, encoding='utf-8').read()
    patterns = json.load(open(a.patterns, encoding='utf-8')) if a.patterns else None
    out, summary = apply(text, patterns)
    sys.stdout.write(out)
    print(json.dumps(summary), file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
