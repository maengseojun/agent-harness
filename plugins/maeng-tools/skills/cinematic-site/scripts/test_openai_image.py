import base64
import email
import email.policy
import json
import os
import shutil
import stat
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCRIPT = Path(__file__).with_name('openai-image.sh')
KEY = 'sk-fake-test-key'
IMAGE = b'\x89PNG fake bytes'
OK = json.dumps({'data': [{'b64_json': base64.b64encode(IMAGE).decode()}]}).encode()


class FakeApi(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers['Content-Length']))
        self.server.requests.append((self.path, dict(self.headers), body))
        self.send_response(self.server.status)
        self.send_header('Content-Length', str(len(self.server.reply)))
        self.end_headers()
        self.wfile.write(self.server.reply)

    def log_message(self, *args):
        pass


def executable(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class OpenAiImageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), FakeApi)
        self.server.requests, self.server.status, self.server.reply = [], 200, OK
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

        bin_dir = self.dir / 'bin'
        bin_dir.mkdir()
        self.security = bin_dir / 'security'
        executable(self.security, f'#!/bin/sh\necho {KEY}\n')
        self.argv_log = self.dir / 'curl-argv'
        executable(bin_dir / 'curl', f'#!/bin/sh\necho "$@" >> "{self.argv_log}"\nexec "{shutil.which("curl")}" "$@"\n')
        self.env = {
            **os.environ,
            'PATH': f'{bin_dir}:{os.environ["PATH"]}',
            'OPENAI_IMAGE_BASE_URL': f'http://127.0.0.1:{self.server.server_port}/v1',
            'NO_PROXY': '*',
            'HOME': str(self.dir),
            'CURL_HOME': str(self.dir),
        }
        (self.dir / '.curlrc').write_text('retry = 2\nretry-all-errors\nretry-delay = 0\nverbose\n')
        self.prompt = self.dir / 'a.prompt.txt'
        self.prompt.write_text('A "quoted" hero\nsecond line\n')
        self.out = self.dir / 'a.png'

    def run_script(self, *refs, out=None):
        return subprocess.run(
            [str(SCRIPT), str(self.prompt), str(out or self.out), '1536x864', 'low', *map(str, refs)],
            env=self.env, capture_output=True, text=True, timeout=30,
        )

    def assert_key_hidden(self, result):
        self.assertNotIn(KEY, result.stdout + result.stderr)
        self.assertNotIn(KEY, self.argv_log.read_text())

    def test_generation_sends_json_and_saves_decoded_image(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.out))
        self.assertEqual(self.out.read_bytes(), IMAGE)
        path, headers, body = self.server.requests[0]
        self.assertEqual(path, '/v1/images/generations')
        self.assertEqual(headers['Authorization'], f'Bearer {KEY}')
        self.assertEqual(json.loads(body), {
            'model': 'gpt-image-2', 'prompt': 'A "quoted" hero\nsecond line\n', 'size': '1536x864', 'quality': 'low',
        })
        self.assert_key_hidden(result)

    def test_references_go_to_edits_as_multipart_in_order(self):
        first, second = self.dir / 'refs 1;x.png', self.dir / 'b.png'
        first.write_bytes(b'first'), second.write_bytes(b'second')
        result = self.run_script(first, second)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.out.read_bytes(), IMAGE)
        path, headers, body = self.server.requests[0]
        self.assertEqual(path, '/v1/images/edits')
        self.assertEqual(headers['Authorization'], f'Bearer {KEY}')
        message = email.message_from_bytes(
            f'Content-Type: {headers["Content-Type"]}\n\n'.encode() + body, policy=email.policy.HTTP)
        parts = [(p.get_param('name', header='content-disposition'), p.get_content()) for p in message.iter_parts()]
        fields = {name: value for name, value in parts if name != 'image[]'}
        self.assertEqual(fields, {
            'model': 'gpt-image-2', 'size': '1536x864', 'quality': 'low', 'prompt': 'A "quoted" hero\nsecond line\n',
        })
        self.assertEqual([value for name, value in parts if name == 'image[]'], [b'first', b'second'])
        self.assert_key_hidden(result)

    def test_api_error_prints_message_and_never_retries(self):
        self.server.status = 429
        self.server.reply = json.dumps({'error': {'message': 'You exceeded your current quota'}}).encode()
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn('HTTP 429: You exceeded your current quota', result.stderr)
        self.assertFalse(self.out.exists())
        self.assertEqual(len(self.server.requests), 1)
        self.assertNotIn(KEY, result.stderr)

    def test_failed_rerun_keeps_the_previous_image(self):
        self.out.write_bytes(b'paid for earlier')
        self.server.status, self.server.reply = 500, b'not json'
        self.assertEqual(self.run_script().returncode, 1)
        self.assertEqual(self.out.read_bytes(), b'paid for earlier')

    def test_ok_reply_without_image_fails_and_writes_nothing(self):
        self.server.reply = b'{"data": [{}]}'
        self.assertNotEqual(self.run_script().returncode, 0)
        self.assertFalse(self.out.exists())

    def test_stops_before_any_request(self):
        executable(self.security, '#!/bin/sh\nexit 44\n')
        self.assertEqual(self.run_script().returncode, 44)
        executable(self.security, f'#!/bin/sh\necho {KEY}\n')
        self.assertEqual(self.run_script(out=self.dir / 'missing' / 'a.png').returncode, 1)
        self.assertNotEqual(self.run_script(self.dir / 'missing.png').returncode, 0)
        self.assertEqual(subprocess.run([str(SCRIPT), str(self.prompt)], env=self.env, capture_output=True).returncode, 2)
        self.prompt.write_text('')
        self.assertEqual(self.run_script().returncode, 1)
        self.assertEqual(self.server.requests, [])


if __name__ == '__main__':
    unittest.main()
