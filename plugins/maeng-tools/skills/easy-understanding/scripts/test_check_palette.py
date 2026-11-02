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
