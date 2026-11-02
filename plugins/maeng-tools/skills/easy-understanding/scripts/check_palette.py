#!/usr/bin/env python3
"""Report colors in an output file that are not in the effective token set (default: diagram-explainer's style guide)."""
import argparse
import re
import sys
from pathlib import Path

STYLE = Path(__file__).resolve().parents[2] / 'diagram-explainer/references/style-guide.md'
# shortcut: hex and rgb()/rgba() only; named colors and hsl() pass unchecked, add them if a leak shows up
COLOR = re.compile(r'(?<![&\w])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b|rgba?\([^)]*\)')


def colors(text):
    return {re.sub(r'\s+', '', c.lower()) for c in COLOR.findall(text)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file')
    parser.add_argument('--allow', action='append', default=[], help='a deliberately borrowed color')
    parser.add_argument('--tokens', type=Path, default=STYLE, help='the effective style guide or profile (default: %(default)s)')
    args = parser.parse_args(argv)
    allowed = colors(args.tokens.read_text()) | colors(' '.join(args.allow))
    off = sorted(colors(Path(args.file).read_text()) - allowed)
    for color in off:
        print(f'off-palette: {color}')
    if not off:
        print('palette: house tokens only')
    return 1 if off else 0


if __name__ == '__main__':
    sys.exit(main())
