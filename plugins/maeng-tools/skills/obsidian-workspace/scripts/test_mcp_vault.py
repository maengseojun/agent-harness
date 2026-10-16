"""Protocol, root, path and raw-text checks for the read-only and helper clients."""

import errno
import hashlib
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import mcp_vault


SERVER = r'''#!/usr/bin/env python3
import json, os, pathlib, sys, time
MODE = __MODE__
VAULT = pathlib.Path(sys.argv[1])
for raw in sys.stdin.buffer:
    message = json.loads(raw)
    method = message.get("method")
    if method == "notifications/initialized":
        continue
    if method == "initialize":
        protocol = "2024-11-05" if MODE == "wrong_protocol" else "2025-03-26"
        result = {"protocolVersion": protocol, "capabilities": {}, "serverInfo": {"name": "test", "version": "0.16.0"}}
    elif method == "tools/call":
        name = message["params"]["name"]
        if MODE == "timeout":
            time.sleep(0.4)
        if MODE == "rpc_error":
            print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "error": {"code": -1, "message": "fixture"}}), flush=True)
            continue
        if MODE == "partial":
            sys.stdout.write('{"jsonrpc":"2.0","id":')
            sys.stdout.flush()
            break
        if MODE == "tool_error":
            result = {"content": [{"type": "text", "text": "Error: fixture"}], "isError": True}
        elif name == "list_directory":
            directory = VAULT / message["params"]["arguments"].get("path", "")
            result = {"content": [{"type": "text", "text": json.dumps({"dirs": sorted(p.name for p in directory.iterdir() if p.is_dir()), "files": sorted(p.name for p in directory.iterdir() if p.is_file())})}]}
        elif name == "read_note_lines":
            args = message["params"]["arguments"]
            body = (VAULT / args["path"]).read_bytes().decode("utf-8")
            if MODE == "truncated":
                body = body[:max(1, len(body) // 2)]
            lines = body.split("\n")
            result = {"content": [{"type": "text", "text": "\n".join(lines[args["startLine"] - 1:args["endLine"]])}]}
        elif name == "write_note":
            args = message["params"]["arguments"]
            target = VAULT / args["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(args["content"].encode("utf-8"))
            result = {"content": [{"type": "text", "text": "ack"}]}
        else:
            result = {"content": [{"type": "text", "text": "Unexpected tool"}], "isError": True}
    else:
        continue
    if "id" in message:
        print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}), flush=True)
'''


class MCPVaultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.node = self.base / 'bin' / 'node'
        self.node.parent.mkdir()
        self.node.write_text('#!/usr/bin/env python3\nimport os,sys\nos.execv(sys.executable, [sys.executable, *sys.argv[1:]])\n', encoding='utf-8')
        self.node.chmod(0o755)
        self.vault = self.base / 'vault'
        (self.vault / 'wiki').mkdir(parents=True)
        (self.vault / 'wiki' / 'source.md').write_bytes(b'---\ntitle: original yaml\n---\n# Heading\nBody\n')
        package = self.base / 'node_modules' / '@bitbonsai' / 'mcpvault'
        (package / 'dist').mkdir(parents=True)
        self.server = package / 'dist' / 'server.js'
        (package / 'package.json').write_text(json.dumps({'name': '@bitbonsai/mcpvault', 'version': '0.16.0'}), encoding='utf-8')
        self.settings = self.base / 'config.toml'

    def tearDown(self):
        self.temp.cleanup()

    def write_server(self, mode='normal'):
        code = SERVER.replace('__MODE__', json.dumps(mode))
        self.server.write_text(code, encoding='utf-8')

    def write_config(self, *, root=None, version='0.16.0', enabled=None, command=None):
        if version != '0.16.0':
            package_file = self.server.parent.parent / 'package.json'
            package_file.write_text(json.dumps({'name': '@bitbonsai/mcpvault', 'version': version}), encoding='utf-8')
        server_args = [str(self.server), str(root or self.vault)]
        self.settings.write_text(
            '[mcp_servers.obsidian_vault]\n'
            f'command = {json.dumps(str(command or self.node))}\n'
            f'args = {json.dumps(server_args)}\n',
            encoding='utf-8',
        )
        if enabled is not None:
            with self.settings.open('a', encoding='utf-8') as stream:
                stream.write(f'enabled = {json.dumps(enabled)}\n')

    def client(self, mode='normal', timeout=3):
        self.write_server(mode)
        self.write_config()
        return mcp_vault.MCPVault(expected_vault=self.vault, settings_path=self.settings, timeout=timeout)

    def helper(self, mode='normal', timeout=3):
        self.write_server(mode)
        self.write_config()
        return mcp_vault.MCPVaultHelpers(expected_vault=self.vault, settings_path=self.settings, timeout=timeout)

    def test_exact_root_and_pinned_server_configuration(self):
        self.write_server()
        self.write_config()
        config = mcp_vault.load_server_config(self.settings, self.vault)
        self.assertEqual(config.args[1], str(self.vault))
        self.assertEqual(Path(config.args[0]), self.server)
        with self.assertRaises(mcp_vault.MCPVaultError):
            mcp_vault.load_server_config(self.settings, self.base / 'other')
        with self.assertRaises(mcp_vault.MCPVaultError):
            self.write_config(version='0.15.0')
            mcp_vault.load_server_config(self.settings, self.vault)

    def test_wrong_root_fails_before_process_launch(self):
        self.write_server()
        self.write_config(root=self.base / 'other')
        with patch.object(mcp_vault.subprocess, 'Popen') as popen:
            with self.assertRaises(mcp_vault.MCPVaultError):
                with mcp_vault.MCPVault(expected_vault=self.vault, settings_path=self.settings):
                    pass
        popen.assert_not_called()

    def test_disabled_server_fails_before_process_launch(self):
        self.write_server()
        self.write_config(enabled=False)
        with patch.object(mcp_vault.subprocess, 'Popen') as popen:
            with self.assertRaisesRegex(mcp_vault.MCPVaultError, 'disabled'):
                with mcp_vault.MCPVault(expected_vault=self.vault, settings_path=self.settings):
                    pass
        popen.assert_not_called()

    def test_non_node_command_fails_before_process_launch(self):
        self.write_server()
        self.write_config(command=Path('/bin/sh'))
        with patch.object(mcp_vault.subprocess, 'Popen') as popen:
            with self.assertRaisesRegex(mcp_vault.MCPVaultError, 'Node.js'):
                with mcp_vault.MCPVault(expected_vault=self.vault, settings_path=self.settings):
                    pass
        popen.assert_not_called()

    def test_symlinked_root_and_note_are_rejected(self):
        alias = self.base / 'vault-alias'
        alias.symlink_to(self.vault, target_is_directory=True)
        with self.assertRaises(mcp_vault.MCPVaultError):
            mcp_vault.validate_vault_root(alias, alias)
        outside = self.base / 'outside.md'
        outside.write_text('outside', encoding='utf-8')
        link = self.vault / 'wiki' / 'linked.md'
        link.symlink_to(outside)
        with self.assertRaises(mcp_vault.MCPVaultError):
            mcp_vault.hash_vault_note('wiki/linked.md', self.vault)

    def test_note_path_guard_rejects_traversal_hidden_and_other_scopes(self):
        for path in ('/wiki/a.md', 'wiki/../secret.md', 'wiki/.private.md', 'wiki/SYN-X.md', 'raw/source.md', 'wiki\\escape.md'):
            with self.subTest(path=path), self.assertRaises(mcp_vault.MCPVaultError):
                mcp_vault._valid_note_path(path)

    def test_read_note_lines_preserves_original_markdown_and_uses_full_range(self):
        expected = '---\ntitle: original yaml\n---\n# Heading\nBody\n'
        with self.client() as vault:
            body = vault.read_note_lines('wiki/source.md')
            listing = vault.list_directory('wiki')
        self.assertEqual(body, expected)
        self.assertEqual(listing, {'dirs': [], 'files': ['source.md']})
        self.assertEqual(mcp_vault.hash_vault_note('wiki/source.md', self.vault), hashlib.sha256(expected.encode('utf-8')).hexdigest())

    def test_helper_preserves_raw_yaml_crlf_and_writes_complete_markdown(self):
        source = '---\r\ntitle: old: [serialization]\r\ncomment: "keep"\r\n---\r\n# Heading\r\nBody\r\n'
        (self.vault / 'wiki' / 'source.md').write_bytes(source.encode('utf-8'))
        desired = '---\r\ntitle: complete prepared note\r\n---\r\n# New\r\nBody\r\n'
        with self.helper() as vault:
            state = vault.read_notes(['wiki/source.md'])['wiki/source.md']
            vault.write_note('wiki/concepts/new.md', desired)
            saved = vault.read_notes(['wiki/concepts/new.md'])['wiki/concepts/new.md']
        self.assertEqual(state['body'], source)
        self.assertEqual(state['sha256'], hashlib.sha256(source.encode('utf-8')).hexdigest())
        self.assertEqual(saved['body'], desired)
        self.assertEqual((self.vault / 'wiki' / 'concepts' / 'new.md').read_bytes(), desired.encode('utf-8'))

    def test_helper_rejects_truncated_mcp_text_and_terminal_symlink(self):
        with self.helper(mode='truncated') as vault:
            with self.assertRaisesRegex(mcp_vault.MCPVaultError, 'hash'):
                vault.read_note_lines('wiki/source.md')
        outside = self.base / 'outside.md'
        outside.write_text('outside', encoding='utf-8')
        target = self.vault / 'wiki' / 'concepts' / 'linked.md'
        target.parent.mkdir(parents=True)
        target.symlink_to(outside)
        with self.helper() as vault:
            with self.assertRaises(mcp_vault.MCPVaultError):
                vault.write_note('wiki/concepts/linked.md', '# unsafe\n')
        self.assertEqual(outside.read_text(encoding='utf-8'), 'outside')

    def test_helper_metadata_link_scan_rejects_symlinks_and_reports_all_matches(self):
        first = self.vault / 'wiki' / 'one' / 'Same.md'
        second = self.vault / 'hubs' / 'Same.md'
        first.parent.mkdir(parents=True)
        second.parent.mkdir(parents=True)
        first.write_text('one', encoding='utf-8')
        second.write_text('two', encoding='utf-8')
        linked = self.vault / 'wiki' / 'one' / 'Linked.md'
        linked.symlink_to(first)
        with self.helper() as vault:
            matches = vault.find_note_paths('same')
        self.assertEqual(matches, ['hubs/Same.md', 'wiki/one/Same.md'])
        self.assertNotIn('wiki/one/Linked.md', matches)

    def test_nonregular_note_is_rejected_without_blocking(self):
        if not hasattr(os, 'mkfifo'):
            self.skipTest('FIFO is unavailable on this platform')
        target = self.vault / 'wiki' / 'fifo.md'
        os.mkfifo(target)
        with self.helper() as vault:
            with self.assertRaises(mcp_vault.MCPVaultError):
                vault.read_notes(['wiki/fifo.md'])

    def test_only_read_only_tools_can_be_called(self):
        vault = self.client()
        with self.assertRaises(mcp_vault.MCPVaultError):
            vault._call_tool('write_note', {'path': 'wiki/source.md', 'content': 'x'})
        self.assertIsNone(vault.process)

    def test_read_only_qmd_client_still_rejects_writes(self):
        with self.assertRaises(mcp_vault.MCPVaultError):
            self.client()._call_tool('write_note', {'path': 'wiki/source.md', 'content': 'x'})

    def test_protocol_and_tool_errors_are_reported_without_echoing_payload(self):
        for mode in ('rpc_error', 'tool_error'):
            with self.subTest(mode=mode), self.client(mode=mode) as vault:
                with self.assertRaises(mcp_vault.MCPVaultError):
                    vault.list_directory('wiki')

    def test_unsupported_protocol_negotiation_fails_closed(self):
        with self.assertRaises(mcp_vault.MCPVaultError):
            with self.client(mode='wrong_protocol'):
                pass

    def test_timeout_and_truncated_response_fail_closed(self):
        with self.client(mode='timeout', timeout=1) as vault:
            vault.timeout = 0.1
            with self.assertRaises(TimeoutError):
                vault.list_directory('wiki')
        with self.client(mode='partial', timeout=1) as vault:
            with self.assertRaises(mcp_vault.MCPVaultError):
                vault.list_directory('wiki')


if __name__ == '__main__':
    unittest.main()
