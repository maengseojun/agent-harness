"""Read-only MCPVault stdio access for the user's existing Obsidian vault."""

from __future__ import annotations

import json
import hashlib
import errno
import os
import select
import stat
import subprocess
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath


EXPECTED_VAULT = Path("/Users/maengseojun/Documents/Obsidian Vault")
SERVER_NAME = "obsidian_vault"
PACKAGE_NAME = "@bitbonsai/mcpvault"
PACKAGE_VERSION = "0.16.0"
FULL_NOTE_END_LINE = 2_147_483_647
MAX_REQUEST_BYTES = 2 * 1024 * 1024
MAX_RESPONSE_BYTES = 64 * 1024 * 1024


class MCPVaultError(RuntimeError):
    """A safe, non-content-bearing MCP or vault validation error."""


@dataclass(frozen=True)
class ServerConfig:
    command: str
    args: tuple[str, ...]
    env: dict[str, str] = field(repr=False)


def config_path():
    codex_home = os.environ.get("CODEX_HOME")
    base = Path(codex_home) if codex_home else Path.home() / ".codex"
    return base / "config.toml"


def _valid_note_path(value):
    if (not isinstance(value, str) or not value or "\\" in value or "\x00" in value
            or any(ord(char) < 32 for char in value)):
        raise MCPVaultError("Invalid vault note path")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    parts = value.split("/")
    if (posix.is_absolute() or windows.is_absolute() or windows.drive
            or any(part in ("", ".", "..") for part in parts)
            or posix.as_posix() != value):
        raise MCPVaultError("Invalid vault note path")
    if (parts[0] not in {"wiki", "hubs"} or not value.endswith(".md")
            or any(part.startswith(".") or part.startswith("SYN-") for part in parts)):
        raise MCPVaultError("Note path is outside the QMD source scope")
    return parts


def _valid_directory_path(value):
    if value == "":
        return []
    if (not isinstance(value, str) or "\\" in value or "\x00" in value
            or any(ord(char) < 32 for char in value)):
        raise MCPVaultError("Invalid vault directory path")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    parts = value.split("/")
    if (posix.is_absolute() or windows.is_absolute() or windows.drive
            or any(part in ("", ".", "..") for part in parts)
            or posix.as_posix() != value):
        raise MCPVaultError("Invalid vault directory path")
    if parts[0] not in {"wiki", "hubs"} or any(part.startswith(".") for part in parts):
        raise MCPVaultError("Directory is outside the QMD source scope")
    return parts


def validate_vault_root(path=EXPECTED_VAULT, expected=EXPECTED_VAULT):
    """Require the exact configured folder and reject a symlinked root."""
    path = Path(path)
    expected = Path(expected)
    if not path.is_absolute() or str(path) != str(expected) or path.is_symlink():
        raise MCPVaultError("Vault path does not match the configured exact root")
    try:
        resolved = path.resolve(strict=True)
        if not path.is_dir() or resolved != expected.resolve(strict=True):
            raise MCPVaultError("Configured vault root is unavailable or redirected")
    except OSError as exc:
        raise MCPVaultError("Configured vault root is unavailable") from exc
    return path


def _package_version(server_script):
    script = Path(server_script)
    if (not script.is_absolute() or script.name != "server.js"
            or script.parent.name != "dist" or script.is_symlink() or not script.is_file()):
        raise MCPVaultError("Configured MCPVault entry point is not the pinned server")
    package_file = script.parent.parent / "package.json"
    if package_file.is_symlink() or not package_file.is_file():
        raise MCPVaultError("Configured MCPVault package metadata is unavailable")
    try:
        package = json.loads(package_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MCPVaultError("Configured MCPVault package metadata is invalid") from exc
    if package.get("name") != PACKAGE_NAME or package.get("version") != PACKAGE_VERSION:
        raise MCPVaultError("Configured MCPVault package is not the approved pinned version")
    return script


def load_server_config(path=None, expected_vault=EXPECTED_VAULT):
    """Read only the configured stdio command; never include settings in errors."""
    expected = Path(expected_vault)
    validate_vault_root(expected, expected)
    path = Path(path) if path is not None else config_path()
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise MCPVaultError("Configured MCP settings file is unavailable")
    try:
        settings = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise MCPVaultError("Configured MCP settings file is invalid") from exc
    servers = settings.get("mcp_servers")
    server = servers.get(SERVER_NAME) if isinstance(servers, dict) else None
    if not isinstance(server, dict):
        raise MCPVaultError("The configured Obsidian MCP server is unavailable")
    enabled = server.get("enabled", True)
    if type(enabled) is not bool:
        raise MCPVaultError("Configured Obsidian MCP enabled flag is invalid")
    if not enabled:
        raise MCPVaultError("Configured Obsidian MCP server is disabled")
    if server.get("type", "stdio") != "stdio":
        raise MCPVaultError("Configured Obsidian MCP server is not a stdio server")
    command = server.get("command")
    args = server.get("args")
    env = server.get("env", {})
    if (not isinstance(command, str) or Path(command).name.lower() not in {"node", "node.exe"}
            or not Path(command).is_absolute()
            or not Path(command).is_file() or not os.access(command, os.X_OK)):
        raise MCPVaultError("Configured Node.js MCP executable is unavailable")
    if (not isinstance(args, list) or len(args) != 2
            or any(not isinstance(arg, str) or "\x00" in arg for arg in args)):
        raise MCPVaultError("Configured MCP arguments do not match the approved server")
    _package_version(args[0])
    if args[1] != str(expected):
        raise MCPVaultError("Configured MCP server targets a different vault")
    if not isinstance(env, dict) or any(
        not isinstance(key, str) or not isinstance(value, str) for key, value in env.items()
    ):
        raise MCPVaultError("Configured MCP environment is invalid")
    return ServerConfig(command=command, args=tuple(args), env=dict(env))


def _one_text(result, context):
    if not isinstance(result, dict) or result.get("isError") is True:
        raise MCPVaultError(f"MCP {context} failed")
    content = result.get("content")
    if not isinstance(content, list) or len(content) != 1:
        raise MCPVaultError(f"MCP {context} returned an unexpected response")
    block = content[0]
    if not isinstance(block, dict) or block.get("type") != "text" or not isinstance(block.get("text"), str):
        raise MCPVaultError(f"MCP {context} returned non-text content")
    return block["text"]


def _safe_listing_name(name):
    if (not isinstance(name, str) or not name or name in {".", ".."}
            or "/" in name or "\\" in name or "\x00" in name
            or any(ord(char) < 32 for char in name)):
        raise MCPVaultError("MCP directory listing contains an invalid path entry")
    return name


class MCPVault:
    """Short-lived read-only MCP stdio client for list/read operations."""

    def __init__(self, *, expected_vault=EXPECTED_VAULT, settings_path=None, timeout=30):
        self.expected_vault = Path(expected_vault)
        self.settings_path = settings_path
        self.timeout = timeout
        self.process = None
        self.buffer = bytearray()
        self.next_id = 0
        self.client_name = "obsidian-workspace-qmd"

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def connect(self):
        if self.process is not None:
            return self
        validate_vault_root(self.expected_vault, self.expected_vault)
        config = load_server_config(self.settings_path, self.expected_vault)
        environment = os.environ.copy()
        environment.update(config.env)
        try:
            self.process = subprocess.Popen(
                [config.command, *config.args], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, bufsize=0, env=environment,
            )
            initialized = self._request("initialize", {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": self.client_name, "version": "1.0"},
            })
            if initialized.get("protocolVersion") != "2025-03-26":
                raise MCPVaultError("MCP server negotiated an unsupported protocol version")
            self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        except Exception:
            self.close()
            raise
        return self

    def close(self):
        process, self.process = self.process, None
        self.buffer.clear()
        if process is None:
            return
        try:
            if process.stdin and not process.stdin.closed:
                try:
                    process.stdin.close()
                except OSError:
                    pass
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=2)
        finally:
            if process.stdout:
                process.stdout.close()

    def _send(self, value):
        if self.process is None or self.process.poll() is not None:
            raise MCPVaultError("MCP server stopped before responding")
        try:
            data = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        except (TypeError, ValueError, UnicodeError) as exc:
            raise MCPVaultError("MCP request could not be encoded") from exc
        if len(data) > MAX_REQUEST_BYTES:
            raise MCPVaultError("MCP request exceeds the client limit")
        try:
            self.process.stdin.write(data)
            self.process.stdin.flush()
        except (OSError, BrokenPipeError) as exc:
            raise MCPVaultError("MCP request could not be sent") from exc

    def _read_line(self, deadline):
        while True:
            newline = self.buffer.find(b"\n")
            if newline >= 0:
                if newline > MAX_RESPONSE_BYTES:
                    raise MCPVaultError("MCP response exceeds the client limit")
                line = bytes(self.buffer[:newline])
                del self.buffer[:newline + 1]
                if not line.strip():
                    continue
                try:
                    value = json.loads(line.decode("utf-8"))
                except (UnicodeError, json.JSONDecodeError) as exc:
                    raise MCPVaultError("MCP server returned invalid JSON") from exc
                if not isinstance(value, dict):
                    raise MCPVaultError("MCP server returned an invalid message")
                return value
            if len(self.buffer) > MAX_RESPONSE_BYTES:
                raise MCPVaultError("MCP response exceeds the client limit")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("MCP request timed out")
            if self.process is None or self.process.poll() is not None:
                raise MCPVaultError("MCP server stopped before completing a response")
            ready, _, _ = select.select([self.process.stdout], [], [], min(remaining, 0.2))
            if not ready:
                continue
            try:
                chunk = os.read(self.process.stdout.fileno(), 65536)
            except OSError as exc:
                raise MCPVaultError("MCP response could not be read") from exc
            if not chunk:
                raise MCPVaultError("MCP server closed stdout before responding")
            self.buffer.extend(chunk)

    def _request(self, method, params=None):
        self.next_id += 1
        request_id = self.next_id
        request = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            request["params"] = params
        self._send(request)
        deadline = time.monotonic() + self.timeout
        while True:
            message = self._read_line(deadline)
            if "method" in message and "id" not in message:
                continue
            if "method" in message and "id" in message:
                raise MCPVaultError("MCP server requested an unsupported client operation")
            if type(message.get("id")) is not int or message.get("id") != request_id:
                raise MCPVaultError("MCP server returned an unmatched response")
            if "error" in message:
                raise MCPVaultError(f"MCP protocol request failed: {method}")
            result = message.get("result")
            if not isinstance(result, dict):
                raise MCPVaultError(f"MCP protocol response is invalid: {method}")
            return result

    def _call_tool(self, name, arguments):
        if name not in {"list_directory", "read_note_lines"}:
            raise MCPVaultError("Only read-only MCP tools are allowed by this client")
        return self._request("tools/call", {"name": name, "arguments": arguments})

    def list_directory(self, path=""):
        parts = _valid_directory_path(path)
        _assert_vault_directory(self.expected_vault, parts)
        text = _one_text(self._call_tool("list_directory", {"path": path}), "directory listing")
        try:
            listing = json.loads(text)
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise MCPVaultError("MCP directory listing is not valid JSON") from exc
        if (not isinstance(listing, dict) or set(listing) != {"dirs", "files"}
                or not isinstance(listing["dirs"], list) or not isinstance(listing["files"], list)):
            raise MCPVaultError("MCP directory listing has an unexpected shape")
        dirs = [_safe_listing_name(name) for name in listing["dirs"]]
        files = [_safe_listing_name(name) for name in listing["files"]]
        if len(set(dirs)) != len(dirs) or len(set(files)) != len(files):
            raise MCPVaultError("MCP directory listing contains duplicate entries")
        return {"dirs": dirs, "files": files}

    def read_note_lines(self, path):
        parts = _valid_note_path(path)
        _assert_vault_file(self.expected_vault, parts)
        result = self._call_tool("read_note_lines", {
            "path": path,
            "startLine": 1,
            "endLine": FULL_NOTE_END_LINE,
        })
        # read_note_lines returns the original Markdown as plain text. Do not JSON-parse it.
        return _one_text(result, "raw note read")


def _open_vault_entry(root, parts, *, directory):
    root = validate_vault_root(root, root)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    directory_flags = flags | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(root, directory_flags)
    try:
        for index, part in enumerate(parts):
            final = index == len(parts) - 1
            open_flags = directory_flags if (not final or directory) else flags
            next_descriptor = os.open(part, open_flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        metadata = os.fstat(descriptor)
        expected_mode = stat.S_ISDIR if directory else stat.S_ISREG
        if not expected_mode(metadata.st_mode):
            raise MCPVaultError("Vault entry is not the expected regular file or directory")
        return descriptor
    except OSError as exc:
        os.close(descriptor)
        raise MCPVaultError("Vault entry is missing, symlinked, or unreadable") from exc
    except Exception:
        os.close(descriptor)
        raise


def _assert_vault_directory(root, parts):
    if parts:
        _valid_directory_path("/".join(parts))
    descriptor = _open_vault_entry(root, parts, directory=True)
    os.close(descriptor)


def _assert_vault_file(root, parts):
    descriptor = _open_vault_entry(root, parts, directory=False)
    os.close(descriptor)


def hash_vault_note(path, root=EXPECTED_VAULT):
    """Hash complete source bytes through a no-follow file descriptor."""
    parts = _valid_note_path(path)
    descriptor = _open_vault_entry(root, parts, directory=False)
    try:
        import hashlib

        hasher = hashlib.sha256()
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                return hasher.hexdigest()
            hasher.update(chunk)
    finally:
        os.close(descriptor)


def _valid_helper_note_path(value, *, write=False):
    """Validate an explicitly selected helper Markdown path, separate from QMD scope."""
    if (not isinstance(value, str) or not value or "\\" in value or "\x00" in value
            or any(ord(char) < 32 for char in value)):
        raise MCPVaultError("Invalid helper note path")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    parts = value.split("/")
    if (posix.is_absolute() or windows.is_absolute() or windows.drive
            or any(part in ("", ".", "..") for part in parts)
            or posix.as_posix() != value or not value.lower().endswith(".md")
            or any(part.startswith(".") or part.lower() in {".git", ".obsidian", "node_modules"} for part in parts)):
        raise MCPVaultError("Invalid or restricted helper Markdown path")
    if write:
        allowed = (
            value == "log.md" or value == "wiki/index.md"
            or (len(parts) >= 2 and parts[0] == "hubs")
            or (len(parts) >= 3 and parts[0] == "wiki" and parts[1] in {"answers", "concepts", "entities"})
        )
        if not allowed:
            raise MCPVaultError("Helper write path is outside the derived-note scope")
    return parts


def _helper_file_hash(path, root=EXPECTED_VAULT):
    parts = _valid_helper_note_path(path)
    descriptor = _open_vault_entry(root, parts, directory=False)
    try:
        hasher = hashlib.sha256()
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                return hasher.hexdigest()
            hasher.update(chunk)
    finally:
        os.close(descriptor)


def _helper_file_exists(path, root=EXPECTED_VAULT):
    parts = _valid_helper_note_path(path)
    try:
        descriptor = _open_vault_entry(root, parts, directory=False)
    except MCPVaultError as exc:
        cause = exc.__cause__
        if isinstance(cause, OSError) and cause.errno == errno.ENOENT:
            return False
        raise
    os.close(descriptor)
    return True


def _validate_helper_parent_chain(path, root=EXPECTED_VAULT):
    parts = _valid_helper_note_path(path)
    root = validate_vault_root(root, root)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(root, flags)
    try:
        for part in parts[:-1]:
            try:
                next_descriptor = os.open(part, flags, dir_fd=descriptor)
            except FileNotFoundError:
                return
            except OSError as exc:
                raise MCPVaultError("Helper note parent is symlinked or unavailable") from exc
            os.close(descriptor)
            descriptor = next_descriptor
    finally:
        os.close(descriptor)


class MCPVaultHelpers(MCPVault):
    """Selected-note client for source snapshots and explicit wiki plans.

    The base MCPVault client remains read-only for QMD. This separate client
    adds only full-note writes to the permitted derived-note destinations.
    """

    client_name = "obsidian-workspace-helper"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client_name = type(self).client_name

    def _call_tool(self, name, arguments):
        if name not in {"list_directory", "read_note_lines", "write_note"}:
            raise MCPVaultError("Helper MCP client permits selected reads and derived-note writes only")
        return self._request("tools/call", {"name": name, "arguments": arguments})

    def assert_vault(self, vault):
        validate_vault_root(vault, self.expected_vault)

    def note_exists(self, path):
        return _helper_file_exists(path, self.expected_vault)

    def read_note_lines(self, path):
        _valid_helper_note_path(path)
        _assert_vault_file(self.expected_vault, _valid_helper_note_path(path))
        result = self._call_tool("read_note_lines", {
            "path": path,
            "startLine": 1,
            "endLine": FULL_NOTE_END_LINE,
        })
        text = _one_text(result, "raw helper note read")
        try:
            returned_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            disk_hash = _helper_file_hash(path, self.expected_vault)
        except UnicodeError as exc:
            raise MCPVaultError("MCP note read is not valid UTF-8") from exc
        if returned_hash != disk_hash:
            raise MCPVaultError("MCP note read differs from the complete no-follow file hash")
        return text

    def read_notes(self, paths):
        result = {}
        for path in paths:
            _valid_helper_note_path(path)
            if not self.note_exists(path):
                result[path] = {"exists": False, "body": None, "sha256": None}
                continue
            body = self.read_note_lines(path)
            result[path] = {
                "exists": True,
                "body": body,
                "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            }
        return result

    def write_note(self, path, content):
        _valid_helper_note_path(path, write=True)
        if not isinstance(content, str) or "\x00" in content:
            raise MCPVaultError("Helper note content must be UTF-8 text")
        try:
            content.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise MCPVaultError("Helper note content is not valid UTF-8") from exc
        _validate_helper_parent_chain(path, self.expected_vault)
        # Reject a terminal symlink or non-file even for direct client callers.
        self.note_exists(path)
        # Omit frontmatter: content is the complete prepared raw Markdown string.
        return _one_text(self._call_tool("write_note", {"path": path, "content": content}), "derived-note write")

    def find_note_paths(self, basename):
        """Find same-basename Markdown files by safe filesystem metadata only."""
        if not isinstance(basename, str) or not basename or "/" in basename or "\\" in basename:
            raise MCPVaultError("Invalid note basename")
        wanted = basename[:-3] if basename.lower().endswith(".md") else basename
        root = validate_vault_root(self.expected_vault, self.expected_vault)
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        root_fd = os.open(root, flags)
        matches = []

        def visit(directory_fd, prefix):
            try:
                names = os.listdir(directory_fd)
            except OSError as exc:
                raise MCPVaultError("Vault note metadata is unavailable") from exc
            for name in names:
                if (not name or name.startswith(".") or name.lower() in {".git", ".obsidian", "node_modules"}
                        or "/" in name or "\\" in name or any(ord(char) < 32 for char in name)):
                    continue
                relative = f"{prefix}/{name}" if prefix else name
                try:
                    metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                except OSError as exc:
                    raise MCPVaultError("Vault note metadata is unavailable") from exc
                if stat.S_ISLNK(metadata.st_mode):
                    continue
                if stat.S_ISDIR(metadata.st_mode):
                    try:
                        child_fd = os.open(name, flags, dir_fd=directory_fd)
                    except OSError as exc:
                        if exc.errno == errno.ENOENT:
                            continue
                        raise MCPVaultError("Vault note metadata is unavailable") from exc
                    try:
                        visit(child_fd, relative)
                    finally:
                        os.close(child_fd)
                elif stat.S_ISREG(metadata.st_mode) and name.lower().endswith(".md") and name[:-3].casefold() == wanted.casefold():
                    matches.append(relative)

        try:
            visit(root_fd, "")
        finally:
            os.close(root_fd)
        return sorted(matches)
