import unittest

import private_filter as pf


class PrivateFilter(unittest.TestCase):
    def test_private_span_removed(self):
        out, s = pf.apply('a <private>secret\nline</private> b')
        self.assertEqual(out, 'a [private omitted] b')
        self.assertEqual(s['private_spans'], 1)

    def test_unclosed_private_fails_safe(self):
        out, _ = pf.apply('keep <private>oops never closed')
        self.assertNotIn('oops', out)
        self.assertTrue(out.startswith('keep '))

    def test_redaction_is_opt_in(self):
        text = 'key sk-ABCDEFGHIJKLMNOPQRSTUV end'
        self.assertEqual(pf.apply(text)[0], text)
        out, s = pf.apply(text, [{'name': 'api-key', 'pattern': r'sk-[A-Za-z0-9]{20,}'}])
        self.assertEqual(out, 'key [redacted:api-key] end')
        self.assertEqual(s['redacted'], {'api-key': 1})


if __name__ == '__main__':
    unittest.main()
