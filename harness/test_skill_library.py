"""Check the independently installable personal skill folders."""

from pathlib import Path
import re
import unittest

from install import FILES


LIBRARY = Path(__file__).resolve().parents[1] / 'skills'


class SkillLibraryTests(unittest.TestCase):
    def test_each_folder_has_matching_metadata_and_local_references(self):
        folders = sorted(path for path in LIBRARY.iterdir() if path.is_dir())
        self.assertTrue(folders)
        for folder in folders:
            with self.subTest(skill=folder.name):
                body = (folder / 'SKILL.md').read_text()
                front = body.split('---', 2)
                self.assertEqual(len(front), 3)
                self.assertRegex(front[1], rf'(?m)^name: {re.escape(folder.name)}$')
                self.assertRegex(front[1], r'(?m)^description: \S.+$')
                for path in folder.rglob('*'):
                    self.assertFalse(path.is_symlink())
                for reference in re.findall(r'\]\((references/[^)#]+)(?:#[^)]+)?\)', body):
                    self.assertTrue((folder / reference).is_file(), reference)

    def test_relative_guide_links_survive_installation(self):
        guide = (LIBRARY.parent / 'harness/README.md').read_text()
        for reference in re.findall(r'\]\((?!https?://|#)([^)#]+)(?:#[^)]+)?\)', guide):
            with self.subTest(reference=reference):
                self.assertIn(f'references/{reference}', FILES)


if __name__ == '__main__':
    unittest.main()
