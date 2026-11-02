#!/usr/bin/env python3
"""Report colors in an output file that are not in the effective token set (default: diagram-explainer's style guide)."""
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
COLOR_DECL = re.compile(r'(?:--[\w-]+|[a-z-]*(?:color|background|border|outline|fill|stroke|shadow)[a-z-]*)\s*:\s*([^;{}"<>]+)', re.I)
PAINT_ATTR = re.compile(r'\b(?:fill|stroke|stop-color|flood-color|lighting-color|color)\s*=\s*["\']([^"\']*)["\']', re.I)


def colors(text):
    found = {re.sub(r'\s+', '', c.lower()) for c in COLOR.findall(text)}
    values = COLOR_DECL.findall(text) + PAINT_ATTR.findall(text)
    return found | {w for v in values for w in re.findall(r'[a-z]+', v.lower()) if w in NAMED}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file')
    parser.add_argument('--allow', action='append', default=[], help='a deliberately borrowed color')
    parser.add_argument('--tokens', type=Path, default=STYLE, help='the effective style guide or profile (default: %(default)s)')
    args = parser.parse_args(argv)
    allowed = colors('\n'.join(TOKEN_ROW.findall(args.tokens.read_text()))) | colors(' '.join(args.allow))
    off = sorted(colors(Path(args.file).read_text()) - allowed)
    for color in off:
        print(f'off-palette: {color}')
    if not off:
        print('palette: house tokens only')
    return 1 if off else 0


if __name__ == '__main__':
    sys.exit(main())
