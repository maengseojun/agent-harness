import copy
import json
from pathlib import Path
import unittest

from sync_skills import LOCK, validate


class PinBoundaryTests(unittest.TestCase):
    def test_only_pinned_trusted_cache_paths(self):
        entry = json.loads(LOCK.read_text())['skills'][0]
        self.assertEqual(validate(entry).name, 'SKILL.md')
        for key, value in [('repository', 'untrusted/skills'), ('commit', 'main'),
                           ('sha256', '0'), ('source_path', '../auth.json'),
                           ('path', '/tmp/unapproved-skill')]:
            changed = copy.deepcopy(entry)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate(changed)


if __name__ == '__main__':
    unittest.main()
