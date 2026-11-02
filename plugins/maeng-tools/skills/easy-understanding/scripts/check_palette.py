#!/usr/bin/env python3
"""Report colors in an output file that are not in the effective token set (default: diagram-explainer's style guide).

shortcut: a regex lint, not a CSS parser. Colors set from <script>, CSS escapes and external stylesheets are not
seen; the rendered look in review.md stays the final check. Upgrade to a real CSS tokenizer if leaks get past it.
"""
import argparse
import re
import sys
from pathlib import Path

STYLE = Path(__file__).resolve().parents[2] / 'diagram-explainer/references/style-guide.md'
COLOR = re.compile(r'(?<![&\w])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b|(?:rgb|hsl)a?\([^)]*\)', re.I)
# Only token-table rows (| `role` | ...) count; prose mentions and the opt-in terminal skin are not active tokens.
TOKEN_ROW = re.compile(r'^\|\s*`(?!terminal-)[a-z][a-z0-9-]*`\s*\|.*$', re.M)
# CSS named colors, looked for only in color-bearing declarations and SVG paint attributes so prose words pass.
NAMED = frozenset('''aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue blueviolet
brown burlywood cadetblue chartreuse chocolate coral cornflowerblue cornsilk crimson cyan darkblue darkcyan
darkgoldenrod darkgray darkgreen darkgrey darkkhaki darkmagenta darkolivegreen darkorange darkorchid darkred
darksalmon darkseagreen darkslateblue darkslategray darkslategrey darkturquoise darkviolet deeppink deepskyblue
dimgray dimgrey dodgerblue firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite gold goldenrod gray
green greenyellow grey honeydew hotpink indianred indigo ivory khaki lavender lavenderblush lawngreen
lemonchiffon lightblue lightcoral lightcyan lightgoldenrodyellow lightgray lightgreen lightgrey lightpink
lightsalmon lightseagreen lightskyblue lightslategray lightslategrey lightsteelblue lightyellow lime limegreen
linen magenta maroon mediumaquamarine mediumblue mediumorchid mediumpurple mediumseagreen mediumslateblue
mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream mistyrose moccasin navajowhite navy
oldlace olive olivedrab orange orangered orchid palegoldenrod palegreen paleturquoise palevioletred papayawhip
peachpuff peru pink plum powderblue purple rebeccapurple red rosybrown royalblue saddlebrown salmon sandybrown
seagreen seashell sienna silver skyblue slateblue slategray slategrey snow springgreen steelblue tan teal
thistle tomato turquoise violet wheat white whitesmoke yellow yellowgreen'''.split())
CSS_SOURCE = re.compile(r'<style[^>]*>(.*?)</style>|\bstyle\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))', re.I | re.S)
# Parts of a value that are never colors: url(...), quoted strings and --custom-property names.
NOT_A_COLOR_PART = re.compile(r'url\([^)]*\)|"[^"]*"|\'[^\']*\'|--[\w-]+', re.I)
WORD = re.compile(r'(?<![\w-])[a-z]+(?![\w-])')
DECL = re.compile(r'([-\w]+)\s*:\s*([^;{}]+)')
# Every declaration is checked (shorthands like text-decoration or column-rule carry colors) except these.
NOT_COLOR = frozenset('''font font-family content quotes animation animation-name transition transition-property
will-change grid-area grid-template-areas counter-reset counter-increment'''.split())
PAINT_ATTR = re.compile(r'\b(?:fill|stroke|stop-color|flood-color|lighting-color|color)\s*=\s*["\']([^"\']*)["\']', re.I)


def literals(text):
    out = set()
    for c in COLOR.findall(text):
        # Keep channel boundaries: rgb(1 23 4) and rgb(12 3 4) stay different; spaces around , ( ) / go.
        c = re.sub(r'\s*([,()/])\s*', r'\1', re.sub(r'\s+', ' ', c.lower().strip()))
        if c.startswith('#') and len(c) in (4, 5):
            c = '#' + ''.join(ch * 2 for ch in c[1:])
        out.add(c)
    return out


def names(text):
    return {w for w in WORD.findall(NOT_A_COLOR_PART.sub(' ', text.lower())) if w in NAMED}


def used(text, whole_css=False):
    """Colors an output uses: literals anywhere; named colors only in CSS declarations and SVG paint attributes."""
    css = text if whole_css else '\n'.join(''.join(groups) for groups in CSS_SOURCE.findall(text))
    values = [v for p, v in DECL.findall(css) if p.lower() not in NOT_COLOR] + PAINT_ATTR.findall(text)
    return literals(text) | {n for v in values for n in names(v)}


def allowed(tokens_text, allow):
    """Token-table rows give literals and backticked named colors; --allow values count as written."""
    rows = '\n'.join(TOKEN_ROW.findall(tokens_text))
    named_cells = {w.lower() for w in re.findall(r'`([A-Za-z]+)`', rows) if w.lower() in NAMED}
    return literals(rows) | named_cells | literals(' '.join(allow)) | names(' '.join(allow))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file')
    parser.add_argument('--allow', action='append', default=[], help='a deliberately borrowed color')
    parser.add_argument('--tokens', type=Path, default=STYLE, help='the effective style guide or profile (default: %(default)s)')
    args = parser.parse_args(argv)
    path = Path(args.file)
    off = sorted(used(path.read_text(), path.suffix == '.css') - allowed(args.tokens.read_text(), args.allow))
    for color in off:
        print(f'off-palette: {color}')
    if not off:
        print('palette: house tokens only')
    return 1 if off else 0


if __name__ == '__main__':
    sys.exit(main())
