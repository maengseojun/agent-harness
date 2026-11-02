import tempfile
import unittest
from pathlib import Path

from check_palette import main


def run(html, *allow, tokens=None):
    with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False) as f:
        f.write(html)
    extra = ['--tokens', tokens] if tokens else []
    try:
        return main([f.name, *extra, *[a for c in allow for a in ('--allow', c)]])
    finally:
        Path(f.name).unlink()


class PaletteTests(unittest.TestCase):
    def test_house_tokens_pass(self):
        self.assertEqual(run(':root{--paper:#f5f5f5;--ink:#2D3142;--rule:rgba(45, 49, 66, 0.12)}'), 0)

    def test_preset_color_fails_until_allowed(self):
        html = ':root{--paper:#f5f5f5;--bg:#0a0f1c}'
        self.assertEqual(run(html), 1)
        self.assertEqual(run(html, '#0a0f1c'), 0)

    def test_named_and_hsl_colors_are_checked(self):
        self.assertEqual(run('<p style="color:red">x</p>'), 1)
        self.assertEqual(run('<rect fill="white"/>'), 1)
        self.assertEqual(run(':root{--bg: hsl(0 100% 50%)}'), 1)

    def test_named_colors_in_shorthands_are_checked(self):
        self.assertEqual(run('<style>.x{text-decoration:underline red}</style>'), 1)
        self.assertEqual(run('<style>.x{column-rule:1px solid red}</style>'), 1)
        self.assertEqual(run('<style>.x{filter:drop-shadow(0 0 2px red)}</style>'), 1)

    def test_allow_and_token_tables_admit_named_colors(self):
        self.assertEqual(run('<p style="color:red">x</p>', 'red'), 0)
        with tempfile.NamedTemporaryFile('w', suffix='.md', delete=False) as f:
            f.write('| `paper` | Page background | `white` | `black` |')
        try:
            self.assertEqual(run('<style>.a{background:white}</style>', tokens=f.name), 0)
        finally:
            Path(f.name).unlink()

    def test_single_quoted_and_unquoted_styles_are_checked(self):
        self.assertEqual(run("<p style='color:red'>x</p>"), 1)
        self.assertEqual(run('<p style=color:red>x</p>'), 1)

    def test_urls_strings_and_identifiers_are_not_colors(self):
        html = ('<style>.x{background-image:url("red.svg");--accent-red:var(--ink);'
                'border-color:var(--rule, var(--ink));quotes:"red"}.y{color:var(--red-ink)}</style>')
        self.assertEqual(run(html), 0)

    def test_rgb_channels_keep_their_boundaries(self):
        with tempfile.NamedTemporaryFile('w', suffix='.md', delete=False) as f:
            f.write('| `paper` | Page background | `rgb(1 23 4)` | `rgb(1 23 4)` |')
        try:
            self.assertEqual(run(':root{--a:rgb(1 23 4)}', tokens=f.name), 0)
            self.assertEqual(run(':root{--a:rgb(12 3 4)}', tokens=f.name), 1)
        finally:
            Path(f.name).unlink()

    def test_short_hex_matches_its_long_form(self):
        self.assertEqual(run(':root{--x:#FFF}'), 0)  # backend fill is #ffffff in the style guide

    def test_tokens_keywords_and_prose_words_pass(self):
        html = ('<style>.a{color:var(--ink);border:1px solid var(--rule);font-family:Tomato,sans-serif}</style>'
                '<rect fill="none"/><p>Note: a red flag</p>')
        self.assertEqual(run(html), 0)

    def test_opt_in_terminal_skin_is_not_an_active_token(self):
        self.assertEqual(run(':root{--paper:#f5f5f5;--accent:#ff5a36}'), 1)

    def test_another_profile_replaces_the_default_set(self):
        with tempfile.NamedTemporaryFile('w', suffix='.md', delete=False) as f:
            f.write('| `paper` | Page background | `#fbf7ef` | `#1b1a17` |')
        try:
            self.assertEqual(run(':root{--paper:#fbf7ef}', tokens=f.name), 0)
            self.assertEqual(run(':root{--paper:#f5f5f5}', tokens=f.name), 1)
        finally:
            Path(f.name).unlink()

    def test_entities_and_anchors_are_not_colors(self):
        self.assertEqual(run('<p>A&#8212;B</p><a href="#focus=api">api</a>'), 0)


if __name__ == '__main__':
    unittest.main()
