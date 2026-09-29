"""Run: python3 -B -m unittest discover -s harness -p test_notion_body.py."""
import unittest
import ledger


class NotionBodyTests(unittest.TestCase):
    def test_same_notion_page_link_host_is_equivalent(self):
        page = 'a' * 32
        expected = f'[Index](https://www.notion.so/{page})'
        actual = f'[Index](https://app.notion.com/p/{page})'
        self.assertTrue(ledger.notion_body_matches(expected, actual))
        self.assertFalse(ledger.notion_body_matches(expected, actual.replace(page, 'b' * 32)))
        self.assertFalse(ledger.notion_body_matches(f'`{expected}`', f'`{actual}`'))

    def test_approved_notion_link_rendered_as_page_mention(self):
        page = 'a' * 32
        expected = f'[Index](https://app.notion.com/p/{page})'
        actual = f'<mention-page url="https://app.notion.com/p/{page}">Harness</mention-page>'
        self.assertTrue(ledger.notion_body_matches(expected, actual))
        self.assertFalse(ledger.notion_body_matches(expected, actual.replace(page, 'b' * 32)))
        self.assertFalse(ledger.notion_body_matches(expected, actual + '\nExtra'))
        self.assertFalse(ledger.notion_body_matches(f'`{expected}`', f'`{actual}`'))

    def test_added_links_preserve_body_and_existing_links(self):
        source = 'harness/tool_hook.py\nhttps://example.com/result\n[Source](https://example.com/source)\n'
        saved = 'harness/tool_[hook.py](http://hook.py)\n\n[https://example.com/result](https://example.com/result)\n[Source](https://example.com/source)'
        self.assertTrue(ledger.notion_body_matches(source, saved))
        self.assertTrue(ledger.notion_body_matches('See https://example.com/result.',
                        'See [https://example.com/result](https://example.com/result).'))
        for code in ('    hook.py', '````text\n```\nhook.py\n````', '``a` hook.py``'):
            self.assertTrue(ledger.notion_body_matches('hook.py\n' + code,
                            '[hook.py](http://hook.py)\n' + code))
        for changed in (saved.replace('/source)', '/wrong)'), saved.replace('harness/', ''),
                        saved.replace('tool_', 'other_'), saved + '\nExtra text',
                        saved.replace('](https://example.com/result)', '](https://example.com/wrong)')):
            self.assertFalse(ledger.notion_body_matches(source, changed))

    def test_code_and_original_links_are_not_unwrapped(self):
        for source, changed in (
            ('`hook.py`', '`[hook.py](http://hook.py)`'),
            ('```python\nhook.py\n```', '```python\n[hook.py](http://hook.py)\n```'),
            ('[File](https://example.com/a)', '[File](https://example.com/b)'),
            ('[File](https://example.com/a)', 'File'),
            ('https://example.com/report', 'https://[example.com](https://evil.test)/report'),
            ('\\hello', '\\[hello](https://example.com)'),
            ('    hook.py', '    [hook.py](http://hook.py)'),
            ('````text\n```\nhook.py\n````', '````text\n```\n[hook.py](http://hook.py)\n````'),
            ('``a` hook.py``', '``a` [hook.py](http://hook.py)``'),
            ('~~~text\nhook.py', '~~~text\n[hook.py](http://hook.py)'),
            ('```text\nhook.py', '```text\n[hook.py](http://hook.py)'),
            (' \thook.py', ' \t[hook.py](http://hook.py)'),
            ('[Guide][ref]\n[ref]: https://example.com/guide',
             '[[Guide](https://evil.test)][ref]\n[ref]: https://example.com/guide'),
            ('HTTPS://example.com/report', 'HTTPS://[example.com](https://evil.test)/report'),
            ('[Guide](https://example.com/guide)',
             '[[Guide](https://evil.test)](https://example.com/guide)'),
            ('    a\n\n    b', '    a\n    b'),
            ('```text\n```~\nhook.py\n```', '```text\n```~\n[hook.py](http://hook.py)\n```'),
        ):
            self.assertFalse(ledger.notion_body_matches(source, changed))


if __name__ == '__main__':
    unittest.main()
