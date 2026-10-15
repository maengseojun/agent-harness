#!/usr/bin/env python3
"""Preview and capture one explicitly selected native Notion or Linear read."""

import argparse
import difflib
import errno
import fcntl
import hashlib
import json
import os
import pty
import re
import select
import stat
import subprocess
import sys
import tempfile
import time
import tty
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import parse_qsl, urlsplit


EXPECTED_VAULT = Path("/Users/maengseojun/Documents/Obsidian Vault")
OBSIDIAN = "/Applications/Obsidian.app/Contents/MacOS/obsidian"
CAPTURE_ROOT = "raw/native-captures"
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
SENSITIVE_KEYS = {
    "authorization", "cookie", "setcookie", "apikey", "xapikey", "access_token",
    "refreshtoken", "clientsecret", "password", "credential", "credentials",
    "authheader", "headers",
}


class SnapshotError(Exception):
    def __init__(self, code, message, partial_files=(), details=None):
        super().__init__(message)
        self.code = code
        self.partial_files = list(partial_files)
        self.details = details


def fail(code, message):
    raise SnapshotError(code, message)


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def json_bytes(value):
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        fail("invalid_json", f"value is not valid JSON: {exc}")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def clean_text(value, label, *, separators=False):
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
        fail("invalid_receipt", f"{label} must be a non-empty string without control characters")
    if separators and ("/" in value or "\\" in value):
        fail("invalid_receipt", f"{label} cannot contain path separators")
    return value


def _sensitive_key(key):
    return re.sub(r"[^a-z0-9]", "", key.lower()) in {
        re.sub(r"[^a-z0-9]", "", item) for item in SENSITIVE_KEYS
    }


def reject_sensitive_fields(value, where="raw_response"):
    if isinstance(value, dict):
        for key, child in value.items():
            if _sensitive_key(str(key)):
                fail("sensitive_receipt", f"{where} contains a credential or transport field: {key}")
            reject_sensitive_fields(child, f"{where}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_sensitive_fields(child, f"{where}[{index}]")


def validate_receipt(value):
    keys = {
        "schema", "service", "source_id", "url", "revision", "fetched_at",
        "coverage", "native_body", "raw_response",
    }
    if not isinstance(value, dict) or set(value) != keys or type(value.get("schema")) is not int or value["schema"] != 1:
        fail("invalid_receipt", "receipt must use schema 1 with exactly the documented fields")
    if value["service"] not in ("notion", "linear"):
        fail("invalid_receipt", "service must be notion or linear")
    identity = {
        "service": value["service"],
        "source_id": clean_text(value["source_id"], "source_id", separators=True),
        "url": clean_text(value["url"], "url"),
    }
    try:
        parsed = urlsplit(identity["url"])
        host = parsed.hostname
        _ = parsed.port
    except ValueError as exc:
        fail("invalid_url", f"source URL is invalid: {exc}")
    if parsed.scheme not in ("http", "https") or not host or parsed.username or parsed.password:
        fail("invalid_url", "source URL must be http(s), include a host, and contain no credentials")
    if any(_sensitive_key(key) for key, _ in parse_qsl(parsed.query, keep_blank_values=True)):
        fail("invalid_url", "source URL query contains a credential field")
    revision = clean_text(value["revision"], "revision")
    fetched_at = clean_text(value["fetched_at"], "fetched_at")
    try:
        timestamp = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
    except ValueError as exc:
        fail("invalid_receipt", f"fetched_at must be an ISO-8601 timestamp: {exc}")
    if timestamp.tzinfo is None:
        fail("invalid_receipt", "fetched_at must include a timezone")
    if not isinstance(value["coverage"], dict) or not value["coverage"]:
        fail("invalid_receipt", "coverage must be a non-empty JSON object")
    if not isinstance(value["native_body"], str) or not value["native_body"].strip():
        fail("invalid_receipt", "native_body must be a non-empty string")
    if "raw_response" not in value:
        fail("invalid_receipt", "raw_response is required and remains separate from native_body")
    reject_sensitive_fields(value["raw_response"])
    json_bytes(value["coverage"])
    raw_response_bytes = json_bytes(value["raw_response"])
    try:
        body_bytes = value["native_body"].encode("utf-8")
    except UnicodeError as exc:
        fail("invalid_receipt", f"native_body must be valid UTF-8 text: {exc}")
    return {
        "receipt": value,
        "identity": identity,
        "revision": revision,
        "fetched_at": fetched_at,
        "coverage": value["coverage"],
        "body": value["native_body"],
        "body_bytes": body_bytes,
        "body_sha256": sha256(body_bytes),
        "raw_response_bytes": raw_response_bytes,
        "raw_response_sha256": sha256(raw_response_bytes),
    }


def load_receipt(value):
    path = Path(value)
    if not path.is_absolute() or path.is_symlink():
        fail("invalid_receipt_path", "receipt path must be absolute and must not be a symlink")
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            fail("invalid_receipt_path", "receipt path must be a regular file")
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys)
    except SnapshotError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        fail("receipt_unavailable", f"cannot read selected receipt: {exc}")
    return validate_receipt(data)


def validate_vault(value):
    path = Path(value)
    expected = EXPECTED_VAULT
    if not path.is_absolute() or str(path) != str(expected) or path.is_symlink():
        fail("wrong_vault", f"vault must be the exact configured path: {expected}")
    try:
        if not path.is_dir() or path.resolve(strict=True) != expected.resolve(strict=True):
            fail("wrong_vault", f"vault path does not resolve to the configured target: {expected}")
    except OSError as exc:
        fail("wrong_vault", f"vault is unavailable: {exc}")
    return path


def validate_relative_path(value):
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        fail("invalid_path", "paths must be non-empty POSIX-relative paths")
    if PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute() or PureWindowsPath(value).drive:
        fail("invalid_path", "absolute and drive-qualified paths are not allowed")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts) or PurePosixPath(value).as_posix() != value:
        fail("invalid_path", "path must be normalized and remain inside the vault")
    if any(ord(char) < 32 for char in value):
        fail("invalid_path", "control characters are not allowed in paths")
    return parts


def validate_impact_path(value):
    parts = validate_relative_path(value)
    if len(parts) < 3 or parts[-1].lower().endswith(".md") is False:
        fail("invalid_impact_path", "impact candidates must be exact Markdown note paths")
    if "/".join(parts[:2]) not in ("wiki/sources", "wiki/concepts", "wiki/answers"):
        fail("invalid_impact_path", "impact candidates must be under wiki/sources, wiki/concepts, or wiki/answers")
    return value


def cli_command(arguments):
    return [OBSIDIAN, f"vault={EXPECTED_VAULT.name}", *arguments]


def remove_record_ending(value):
    if value.endswith("\r\n"):
        return value[:-2]
    if value.endswith("\n") or value.endswith("\r"):
        return value[:-1]
    return value


def invoke_obsidian(arguments):
    master_fd = slave_fd = None
    process = None
    try:
        master_fd, slave_fd = pty.openpty()
        tty.setraw(slave_fd)
        process = subprocess.Popen(
            cli_command(arguments), stdin=slave_fd, stdout=slave_fd,
            stderr=subprocess.PIPE, close_fds=True,
        )
        os.close(slave_fd)
        slave_fd = None
        stderr_fd = process.stderr.fileno()
        open_fds = {master_fd, stderr_fd}
        stdout_bytes = bytearray()
        stderr_bytes = bytearray()
        deadline = time.monotonic() + 30
        while open_fds:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Obsidian CLI timed out after 30 seconds")
            ready, _, _ = select.select(list(open_fds), [], [], min(remaining, 0.1))
            for descriptor in ready:
                try:
                    chunk = os.read(descriptor, 65536)
                except OSError as exc:
                    if descriptor == master_fd and exc.errno == errno.EIO:
                        chunk = b""
                    else:
                        raise
                if not chunk:
                    open_fds.remove(descriptor)
                    continue
                (stdout_bytes if descriptor == master_fd else stderr_bytes).extend(chunk)
        return_code = process.wait(timeout=max(0.1, deadline - time.monotonic()))
    except (OSError, subprocess.SubprocessError, TimeoutError) as exc:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        fail("obsidian_cli_failed", f"Obsidian CLI could not complete: {exc}")
    finally:
        if slave_fd is not None:
            os.close(slave_fd)
        if master_fd is not None:
            os.close(master_fd)
        if process is not None and process.stderr is not None:
            process.stderr.close()
    try:
        stdout = stdout_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        fail("obsidian_cli_invalid_output", f"Obsidian CLI output is not UTF-8: {exc}")
    stderr = stderr_bytes.decode("utf-8", errors="replace")
    if return_code != 0 or stderr:
        detail = remove_record_ending(stderr) or remove_record_ending(stdout) or f"exit code {return_code}"
        fail("obsidian_cli_failed", detail)
    return remove_record_ending(stdout)


def assert_cli_vault(vault):
    output = invoke_obsidian(["vault", "info=path"])
    if output != str(vault):
        fail("wrong_vault", f"Obsidian CLI resolved a different or empty vault path: {output!r}")


def read_impact_notes(paths):
    if not paths:
        return []
    code = (
        "(async()=>{const paths=" + json.dumps(paths, ensure_ascii=False) +
        ";const notes=[];for(const path of paths){const file=app.vault.getAbstractFileByPath(path);"
        "if(!file||file.path!==path||file.extension!=='md'){notes.push({path,ok:false,error:'missing_or_not_markdown'});continue;}"
        "try{notes.push({path,ok:true,body:await app.vault.read(file)});}"
        "catch(error){notes.push({path,ok:false,error:String(error)});}}"
        "return JSON.stringify({notes});})()"
    )
    output = invoke_obsidian(["eval", f"code={code}"])
    if not output.startswith("=> "):
        fail("obsidian_cli_invalid_output", f"Obsidian eval returned no JSON result: {output[:200]!r}")
    try:
        payload = json.loads(output[3:])
    except json.JSONDecodeError as exc:
        fail("obsidian_cli_invalid_output", f"Obsidian eval returned invalid JSON: {exc}")
    if not isinstance(payload, dict) or not isinstance(payload.get("notes"), list):
        fail("obsidian_cli_invalid_output", "Obsidian eval result is missing notes")
    if len(payload["notes"]) != len(paths):
        fail("obsidian_cli_invalid_output", "Obsidian eval returned a different number of notes")
    result = []
    for expected, item in zip(paths, payload["notes"]):
        if not isinstance(item, dict) or item.get("path") != expected or item.get("ok") is not True:
            detail = item.get("error", "invalid note result") if isinstance(item, dict) else "invalid note result"
            fail("impact_note_unavailable", f"cannot read selected impact note {expected}: {detail}")
        body = item.get("body")
        if not isinstance(body, str):
            fail("obsidian_cli_invalid_output", f"Obsidian eval returned no text body for {expected}")
        result.append({"path": expected, "sha256": sha256(body.encode("utf-8")), "body": body})
    return result


def identity_key(identity):
    return sha256(json_bytes([identity["service"], identity["source_id"], identity["url"]]))


def revision_key(revision):
    return sha256(revision.encode("utf-8"))


def version_key(revision, body_hash):
    return f"{revision_key(revision)}:{body_hash}"


def body_relative(identity_hash, revision_hash, body_hash):
    return f"{CAPTURE_ROOT}/{identity_hash}/{revision_hash}-{body_hash}.body"


def response_relative(identity_hash, response_hash):
    return f"{CAPTURE_ROOT}/{identity_hash}/responses/{response_hash}.json"


def receipt_hash(receipt, body_hash, response_hash):
    return sha256(json_bytes({
        "identity": {key: receipt["identity"][key] for key in ("service", "source_id", "url")},
        "revision": receipt["revision"],
        "fetched_at": receipt["fetched_at"],
        "coverage": receipt["coverage"],
        "native_body_sha256": body_hash,
        "raw_response_sha256": response_hash,
    }))


def storage_path(vault, relative, *, create_parents=False):
    parts = validate_relative_path(relative)
    if len(parts) < 2 or "/".join(parts[:2]) != CAPTURE_ROOT or parts[-1].lower().endswith(".md"):
        fail("invalid_storage_path", "capture metadata and attachment paths must stay under raw/native-captures and cannot be notes")
    current = vault
    root = vault.resolve(strict=True)
    for index, part in enumerate(parts):
        current = current / part
        if current.is_symlink():
            fail("unsafe_storage_path", f"capture path contains a symlink: {current}")
        if current.exists():
            if index < len(parts) - 1 and not current.is_dir():
                fail("unsafe_storage_path", f"capture path parent is not a directory: {current}")
            if os.path.commonpath((str(root), str(current.resolve(strict=True)))) != str(root):
                fail("unsafe_storage_path", f"capture path escapes the vault: {current}")
        elif create_parents and index < len(parts) - 1:
            current.mkdir()
    return current


def read_regular_file(path, label):
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            fail("unsafe_storage_path", f"{label} must be a regular file")
        return path.read_bytes()
    except SnapshotError:
        raise
    except OSError as exc:
        fail("storage_read_failed", f"cannot read {label}: {exc}")


def validate_catalog(catalog):
    if not isinstance(catalog, dict) or set(catalog) != {"schema", "sources"} or catalog["schema"] != 1 or not isinstance(catalog["sources"], dict):
        fail("catalog_invalid", "capture catalog must use schema 1")
    for key, source in catalog["sources"].items():
        if not isinstance(key, str) or not HASH_RE.fullmatch(key) or not isinstance(source, dict) or set(source) != {"identity", "current_version", "versions"}:
            fail("catalog_invalid", "capture catalog has an invalid source entry")
        identity = source["identity"]
        if not isinstance(identity, dict) or set(identity) != {"service", "source_id", "url"} or identity_key(identity) != key:
            fail("catalog_invalid", "capture catalog source identity does not match its key")
        versions = source["versions"]
        if not isinstance(versions, dict) or not isinstance(source["current_version"], str) or source["current_version"] not in versions:
            fail("catalog_invalid", "capture catalog has no valid current version")
        for key_value, version in versions.items():
            if not isinstance(version, dict) or set(version) != {"revision", "native_body_sha256", "body_path", "observations"}:
                fail("catalog_invalid", "capture catalog has an invalid version")
            if not isinstance(version["revision"], str) or not isinstance(version["native_body_sha256"], str) or not HASH_RE.fullmatch(version["native_body_sha256"]):
                fail("catalog_invalid", "capture catalog version hash or revision is invalid")
            expected_key = version_key(version["revision"], version["native_body_sha256"])
            if key_value != expected_key or version["body_path"] != body_relative(key, revision_key(version["revision"]), version["native_body_sha256"]):
                fail("catalog_invalid", "capture catalog version path does not match its identity")
            if not isinstance(version["observations"], list):
                fail("catalog_invalid", "capture catalog observations must be a list")
            seen = set()
            for observation in version["observations"]:
                fields = {"receipt_sha256", "fetched_at", "coverage", "raw_response_sha256", "raw_response_path"}
                if not isinstance(observation, dict) or set(observation) != fields:
                    fail("catalog_invalid", "capture catalog has an invalid receipt observation")
                if not isinstance(observation["receipt_sha256"], str) or not isinstance(observation["raw_response_sha256"], str) or not HASH_RE.fullmatch(observation["receipt_sha256"]) or not HASH_RE.fullmatch(observation["raw_response_sha256"]):
                    fail("catalog_invalid", "capture catalog observation hash is invalid")
                if observation["receipt_sha256"] in seen or not isinstance(observation["coverage"], dict):
                    fail("catalog_invalid", "capture catalog observation is duplicated or has invalid coverage")
                seen.add(observation["receipt_sha256"])
                if observation["raw_response_path"] != response_relative(key, observation["raw_response_sha256"]):
                    fail("catalog_invalid", "capture catalog raw response path does not match its hash")
    return catalog


def load_catalog(vault):
    path = storage_path(vault, f"{CAPTURE_ROOT}/catalog.json")
    if not os.path.lexists(path):
        return {"schema": 1, "sources": {}}, None
    raw = read_regular_file(path, "capture catalog")
    try:
        catalog = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicate_keys)
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        fail("catalog_invalid", f"capture catalog is not valid JSON: {exc}")
    return validate_catalog(catalog), raw


def read_capture_body(vault, version):
    path = storage_path(vault, version["body_path"])
    body_bytes = read_regular_file(path, "current native body capture")
    if sha256(body_bytes) != version["native_body_sha256"]:
        fail("capture_changed", "stored native body hash does not match catalog metadata")
    try:
        return body_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        fail("capture_changed", f"stored native body is not UTF-8: {exc}")


def prepare_preview(vault, receipt, impact_paths, catalog, catalog_raw):
    identity = receipt["identity"]
    identity_hash = identity_key(identity)
    revision_hash = revision_key(receipt["revision"])
    candidate_key = version_key(receipt["revision"], receipt["body_sha256"])
    body_path = body_relative(identity_hash, revision_hash, receipt["body_sha256"])
    raw_path = response_relative(identity_hash, receipt["raw_response_sha256"])
    source = catalog["sources"].get(identity_hash)
    if source is not None and source["identity"] != identity:
        fail("identity_conflict", "capture catalog identity hash collision")
    current = None
    old_body = ""
    if source:
        current = source["versions"][source["current_version"]]
        old_body = read_capture_body(vault, current)
    matching_revision = next((v for v in source["versions"].values() if v["revision"] == receipt["revision"]), None) if source else None
    changed = {
        "revision": current is None or current["revision"] != receipt["revision"],
        "body": current is None or current["native_body_sha256"] != receipt["body_sha256"],
        "diff": "".join(difflib.unified_diff(
            old_body.splitlines(keepends=True), receipt["body"].splitlines(keepends=True),
            fromfile="current" if current else "/dev/null", tofile="candidate",
        )),
    }
    if matching_revision and matching_revision["native_body_sha256"] != receipt["body_sha256"]:
        details = {
            "ok": False, "applied": False, "action": "conflict", "changed": changed,
            "impact_notes": read_impact_notes(impact_paths),
        }
        raise SnapshotError("version_conflict", "the same native revision has a different body", details=details)
    version_exists = source is not None and candidate_key in source["versions"]
    current_metadata = None if current is None else {
        "revision": current["revision"],
        "native_body_sha256": current["native_body_sha256"],
        "body_path": current["body_path"],
    }
    candidate = {
        "revision": receipt["revision"],
        "fetched_at": receipt["fetched_at"],
        "coverage": receipt["coverage"],
        "native_body_sha256": receipt["body_sha256"],
        "raw_response_sha256": receipt["raw_response_sha256"],
        "body_path": body_path,
        "raw_response_path": raw_path,
    }
    return {
        "ok": True,
        "applied": False,
        "action": "reused" if version_exists else ("would_create" if current is None else "would_create_version"),
        "identity": identity,
        "current": current_metadata,
        "candidate": candidate,
        "changed": changed,
        "impact_notes": read_impact_notes(impact_paths),
        "writes": {"note_files": 0, "attachments": [], "metadata_changed": False},
    }, candidate_key, catalog_raw


@contextmanager
def catalog_lock(vault):
    path = storage_path(vault, f"{CAPTURE_ROOT}/.source_snapshot.lock", create_parents=True)
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        fail("catalog_lock_failed", f"cannot lock capture catalog: {exc}")
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
    except OSError as exc:
        os.close(descriptor)
        fail("catalog_lock_failed", f"cannot lock capture catalog: {exc}")
    try:
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def write_immutable(vault, relative, data, partial):
    path = storage_path(vault, relative, create_parents=True)
    if os.path.lexists(path):
        existing = read_regular_file(path, "immutable capture")
        if existing != data:
            fail("immutable_conflict", f"refusing to replace existing capture: {relative}")
        return False
    temp_path = None
    try:
        descriptor, temp_name = tempfile.mkstemp(prefix=".source-snapshot-", dir=path.parent)
        temp_path = Path(temp_name)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temp_path, path)
        partial.append(relative)
        temp_path.unlink()
        temp_path = None
        if read_regular_file(path, "new immutable capture") != data:
            fail("readback_failed", f"capture readback differs: {relative}")
        return True
    except SnapshotError:
        raise
    except FileExistsError:
        existing = read_regular_file(path, "concurrent immutable capture")
        if existing != data:
            fail("immutable_conflict", f"refusing to replace existing capture: {relative}")
        return False
    except OSError as exc:
        fail("storage_write_failed", f"cannot write immutable capture {relative}: {exc}")
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass


def write_catalog(vault, data, previous_bytes, partial):
    path = storage_path(vault, f"{CAPTURE_ROOT}/catalog.json", create_parents=True)
    if os.path.lexists(path):
        if previous_bytes is None or read_regular_file(path, "capture catalog") != previous_bytes:
            fail("catalog_changed", "capture catalog changed during apply; reconcile before retrying")
    elif previous_bytes is not None:
        fail("catalog_changed", "capture catalog disappeared during apply; reconcile before retrying")
    temp_path = None
    try:
        descriptor, temp_name = tempfile.mkstemp(prefix=".source-catalog-", dir=path.parent)
        temp_path = Path(temp_name)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if previous_bytes is None:
            os.link(temp_path, path)
            partial.append(f"{CAPTURE_ROOT}/catalog.json")
            temp_path.unlink()
            temp_path = None
        else:
            os.replace(temp_path, path)
            partial.append(f"{CAPTURE_ROOT}/catalog.json")
            temp_path = None
        if read_regular_file(path, "capture catalog readback") != data:
            fail("readback_failed", "capture catalog readback differs")
    except SnapshotError:
        raise
    except FileExistsError:
        fail("catalog_changed", "capture catalog appeared during apply; reconcile before retrying")
    except OSError as exc:
        fail("catalog_write_failed", f"cannot update capture catalog: {exc}")
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass


def apply_capture(vault, receipt, payload, candidate_key, catalog, catalog_raw):
    identity = receipt["identity"]
    identity_hash = identity_key(identity)
    revision_hash = revision_key(receipt["revision"])
    body_path = payload["candidate"]["body_path"]
    raw_path = payload["candidate"]["raw_response_path"]
    partial = []
    try:
        write_immutable(vault, body_path, receipt["body_bytes"], partial)
        write_immutable(vault, raw_path, receipt["raw_response_bytes"], partial)
        source = catalog["sources"].setdefault(identity_hash, {
            "identity": identity,
            "current_version": candidate_key,
            "versions": {},
        })
        version = source["versions"].setdefault(candidate_key, {
            "revision": receipt["revision"],
            "native_body_sha256": receipt["body_sha256"],
            "body_path": body_path,
            "observations": [],
        })
        observation_hash = receipt_hash(receipt, receipt["body_sha256"], receipt["raw_response_sha256"])
        if not any(item["receipt_sha256"] == observation_hash for item in version["observations"]):
            version["observations"].append({
                "receipt_sha256": observation_hash,
                "fetched_at": receipt["fetched_at"],
                "coverage": receipt["coverage"],
                "raw_response_sha256": receipt["raw_response_sha256"],
                "raw_response_path": raw_path,
            })
        source["current_version"] = candidate_key
        new_bytes = json_bytes(catalog)
        metadata_changed = new_bytes != catalog_raw
        if metadata_changed:
            write_catalog(vault, new_bytes, catalog_raw, partial)
        payload["ok"] = True
        payload["applied"] = True
        payload["action"] = "reused" if not metadata_changed and not partial else "captured"
        payload["writes"] = {
            "note_files": 0,
            "attachments": [path for path in partial if path != f"{CAPTURE_ROOT}/catalog.json"],
            "metadata_changed": metadata_changed,
        }
        return payload
    except SnapshotError as exc:
        exc.partial_files = partial + exc.partial_files
        raise


def run(args):
    receipt = load_receipt(args.receipt)
    impact_paths = [validate_impact_path(path) for path in (args.impact_note or [])]
    if len(impact_paths) != len(set(impact_paths)):
        fail("duplicate_impact_path", "each impact note must be selected once")
    vault = validate_vault(args.vault)
    assert_cli_vault(vault)
    if args.apply:
        with catalog_lock(vault):
            catalog, catalog_raw = load_catalog(vault)
            payload, candidate_key, catalog_raw = prepare_preview(
                vault, receipt, impact_paths, catalog, catalog_raw
            )
            return apply_capture(vault, receipt, payload, candidate_key, catalog, catalog_raw)
    catalog, catalog_raw = load_catalog(vault)
    payload, _, _ = prepare_preview(vault, receipt, impact_paths, catalog, catalog_raw)
    return payload


def parser_for_cli():
    parser = argparse.ArgumentParser(description="Preview or immutably capture one selected Notion/Linear receipt.")
    parser.add_argument("--vault", required=True, help="Exact configured Obsidian vault path")
    parser.add_argument("--receipt", required=True, help="Absolute path to one selected receipt JSON file")
    parser.add_argument("--impact-note", action="append", default=[], help="Exact note path under wiki/sources, wiki/concepts, or wiki/answers; repeat as needed")
    parser.add_argument("--apply", action="store_true", help="Save immutable body/raw response attachments and update the current-version catalog")
    return parser


def main(argv=None):
    applied = "--apply" in (argv if argv is not None else sys.argv[1:])
    try:
        payload = run(parser_for_cli().parse_args(argv))
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0
    except SnapshotError as exc:
        print(json.dumps({
            "ok": False,
            "applied": applied,
            "error": {"code": exc.code, "message": str(exc)},
            "partial_files": exc.partial_files,
            "details": exc.details,
        }, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
