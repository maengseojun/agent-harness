import contextlib
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ask  # noqa: E402

OK = {"choices": [{"message": {"content": "답변"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 5, "completion_tokens": 2}}


class AskTests(unittest.TestCase):
    def run_main(self, argv, post=None, key="KEY", stdin=""):
        calls = []

        def fake(url, body, headers, timeout):
            calls.append((url, body, headers))
            return post(body) if post else OK
        out, err, code = io.StringIO(), io.StringIO(), None
        piped = io.StringIO(stdin)
        piped.isatty = lambda: not stdin
        with mock.patch.object(ask.decisions_client, "_post", fake), \
                mock.patch.object(ask.decisions_client, "_keychain_key", lambda s: key if s == "baze-api-key" else None), \
                mock.patch.object(sys, "stdin", piped), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ask.main(argv)
        return code, out.getvalue(), err.getvalue(), calls

    def test_request_and_output(self):
        code, out, err, calls = self.run_main(["--system", "S", "--max-tokens", "9", "다듬어줘"])
        self.assertEqual((code, out), (0, "답변\n"))
        self.assertIn("gemini-4-argon, 5 in, 2 out", err)
        url, body, headers = calls[0]
        self.assertEqual(url, "https://api.baze.co/v1/gateway/chat/completions/")
        self.assertEqual(headers["Authorization"], "Bearer KEY")
        self.assertEqual(body, {"model": "gemini-4-argon", "max_tokens": 9, "messages": [
            {"role": "system", "content": "S"}, {"role": "user", "content": "다듬어줘"}]})

    def test_prompt_and_file_join_in_order_and_model_changes(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d, "a.md")
            f.write_text("파일", encoding="utf-8")
            _, _, _, calls = self.run_main(["--model", "solar-pro4", "--file", str(f), "앞"])
        self.assertEqual(calls[0][1]["model"], "solar-pro4")
        self.assertEqual(calls[0][1]["messages"], [{"role": "user", "content": "앞\n\n파일"}])

    def test_stdin_is_the_prompt_only_when_nothing_else_is_given(self):
        self.assertEqual(self.run_main([], stdin="입력")[3][0][1]["messages"], [{"role": "user", "content": "입력"}])
        self.assertEqual(self.run_main(["인자"], stdin="입력")[3][0][1]["messages"], [{"role": "user", "content": "인자"}])

    def test_a_secret_format_is_masked_and_prose_is_kept(self):
        token = "gh" "p_abcdefghijklmnop1234"
        _, _, _, calls = self.run_main([f"key: value stays, {token} goes"])
        sent = json.dumps(calls[0][1])
        self.assertNotIn("abcdefghijklmnop1234", sent)
        self.assertIn("key: value stays", sent)

    def test_no_key_sends_nothing(self):
        code, _, err, calls = self.run_main(["hi"], key=None)
        self.assertEqual((code, calls), (1, []))
        self.assertIn("baze-api-key", err)

    def test_http_error_is_reported_without_a_traceback(self):
        def post(body):
            raise urllib.error.HTTPError("u", 403, "no", {}, io.BytesIO(b'{"detail": "model off"}'))
        code, out, err, _ = self.run_main(["hi"], post)
        self.assertEqual((code, out), (1, ""))
        self.assertIn("http 403", err)
        self.assertIn("model off", err)

    def test_an_empty_answer_is_a_failure(self):
        for resp in ({"choices": []}, {"choices": [{"message": {"content": ""}}]}, {"choices": [{"message": {"content": None}}]}, {}):
            with self.subTest(resp):
                self.assertEqual(self.run_main(["hi"], lambda b: resp)[0], 1)

    def test_a_cut_answer_says_so(self):
        cut = {"choices": [{"message": {"content": "일부"}, "finish_reason": "length"}], "usage": {}}
        self.assertIn("cut off", self.run_main(["hi"], lambda b: cut)[2])

    def test_no_prompt_is_an_argument_error(self):
        with self.assertRaises(SystemExit) as e:
            self.run_main([])
        self.assertEqual(e.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
