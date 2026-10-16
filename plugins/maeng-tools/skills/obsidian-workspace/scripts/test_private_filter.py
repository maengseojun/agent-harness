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

    def test_nested_private_does_not_leak(self):
        out, s = pf.apply('a <private>outer <private>inner</private>SECRET</private> b')
        self.assertEqual(out, 'a [private omitted] b')
        self.assertNotIn('SECRET', out)
        self.assertEqual(s['private_spans'], 1)

    def test_unclosed_nested_excludes_to_end(self):
        out, _ = pf.apply('k <PRIVATE x="1"> a <private>b</private> LEAK')
        self.assertEqual(out, 'k [private omitted]')

    def test_multiple_spans(self):
        out, s = pf.apply('1<private>x</private>2< Private >y</ private >3')
        self.assertEqual(out, '1[private omitted]2[private omitted]3')
        self.assertEqual(s['private_spans'], 2)

    def test_stray_close_is_text_and_exposes_nothing(self):
        out, _ = pf.apply('pre </private> mid <private>s</private> post')
        self.assertEqual(out, 'pre </private> mid [private omitted] post')
        out, _ = pf.apply('<private>s</private></private>tail')
        self.assertEqual(out, '[private omitted]</private>tail')

    def test_redaction_is_opt_in(self):
        text = 'key sk-ABCDEFGHIJKLMNOPQRSTUV end'
        self.assertEqual(pf.apply(text)[0], text)
        out, s = pf.apply(text, [{'name': 'api-key', 'pattern': r'sk-[A-Za-z0-9]{20,}'}])
        self.assertEqual(out, 'key [redacted:api-key] end')
        self.assertEqual(s['redacted'], {'api-key': 1})


if __name__ == '__main__':
    unittest.main()
