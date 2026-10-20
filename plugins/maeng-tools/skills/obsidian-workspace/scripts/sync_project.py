#!/usr/bin/env python3
"""Copy explicitly selected project files into a versioned vault archive."""

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
import tempfile
import sys

import vault_drive


HASH_RE = re.compile(r"^[0-9a-f]{64}$")
PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class SyncError(Exception):
    def __init__(self, code, message, partial_writes=None):
        super().__init__(message)
        self.code = code
        self.partial_writes = list(partial_writes or [])


def fail(code, message):
    raise SyncError(code, message)


def inside(path, parent):
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def absolute_directory(value, label):
    path = Path(value)
    if not path.is_absolute():
        fail("invalid_path", f"{label} must be an absolute path")
    try:
        if path.is_symlink():
            fail("symlink_path", f"{label} must not be a symlink")
        resolved = path.resolve(strict=True)
        if not stat.S_ISDIR(resolved.lstat().st_mode):
            fail("not_directory", f"{label} is not a directory")
    except OSError as exc:
        fail("path_unavailable", f"{label} cannot be accessed: {exc}")
    return resolved


def validate_vault(value):
    vault = absolute_directory(value, "vault")
    markers = (("Home.md", False), ("AGENTS.md", False), ("wiki", True), ("hubs", True))
    for name, want_dir in markers:
        path = vault / name
        try:
            st = path.lstat()
        except OSError:
            fail("wrong_vault", f"vault marker missing: {name}")
        if stat.S_ISLNK(st.st_mode):
            fail("wrong_vault", f"vault marker must not be a symlink: {name}")
        if (want_dir and not stat.S_ISDIR(st.st_mode)) or (not want_dir and not stat.S_ISREG(st.st_mode)):
            fail("wrong_vault", f"vault marker has wrong type: {name}")
        if not inside(path.resolve(strict=True), vault):
            fail("wrong_vault", f"vault marker escapes vault: {name}")
    return vault


def validate_project_id(value):
    if not PROJECT_ID_RE.fullmatch(value):
        fail("invalid_project_id", "project-id must contain only ASCII letters, digits, '_' or '-'")
    return value


def validate_relative_name(value):
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        fail("invalid_source_path", "files must be non-empty POSIX-relative paths")
    if PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute() or PureWindowsPath(value).drive:
        fail("invalid_source_path", "absolute or drive-qualified source paths are not allowed")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts) or PurePosixPath(value).as_posix() != value:
        fail("invalid_source_path", "source path must be normalized and stay inside source-root")
    if any(ord(char) < 32 for char in value):
        fail("invalid_source_path", "control characters are not allowed in source paths")
    return parts


SENSITIVE_DIRS = {
    ".aws", ".azure", ".docker", ".git", ".gnupg", ".kube", ".ssh",
    "credentials", "secrets",
}
SENSITIVE_NAMES = {
    ".env", ".envrc", ".netrc", ".npmrc", ".pypirc", ".git-credentials", ".pgpass", ".htpasswd",
    "authorized_keys", "known_hosts", "id_rsa", "id_dsa", "id_ecdsa",
    "id_ed25519", "id_ecdsa_sk", "credentials", "credentials.json", "secret",
    "secrets", "secrets.json", "token", "tokens", "service-account.json",
    "service_account.json", "client_secret.json", "private_key", "privatekey", "password", "passwords", "passwd",
}
SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".p7b", ".p7c", ".jks", ".keystore"}
SENSITIVE_WORD = re.compile(r"(^|[._-])(api[_-]?key|access[_-]?key|credential|credentials|secret|secrets|token|tokens|private[_-]?key|password|passwd|service[_-]?account)([._-]|$)")


# shortcut: path names are a candidate filter; use a reviewed content scanner if automatic discovery is added.
def is_sensitive(parts):
    lowered = [part.casefold() for part in parts]
    for part in lowered:
        if part in SENSITIVE_DIRS or part in SENSITIVE_NAMES:
            return True
        if part.startswith(".env.") or part.startswith(".env-"):
            return True
    name = lowered[-1]
    if Path(name).suffix in SENSITIVE_SUFFIXES or SENSITIVE_WORD.search(name):
        return True
    if any(lowered[i:i + 2] in ([".config", "gcloud"], [".config", "gh"]) for i in range(len(lowered) - 1)):
        return True
    return False


def read_regular_file(path, label, unsafe_code="unsafe_source"):
    try:
        before_path = path.lstat()
    except OSError as exc:
        fail("source_unavailable", f"{label} cannot be accessed: {exc}")
    if stat.S_ISLNK(before_path.st_mode) or not stat.S_ISREG(before_path.st_mode):
        fail(unsafe_code, f"{label} must be a real regular file, not a symlink or directory")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        fail("source_unavailable", f"{label} cannot be opened safely: {exc}")
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (before_path.st_dev, before_path.st_ino):
            fail("source_changed", f"{label} changed while being opened")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read()
        after = os.fstat(fd)
        after_path = path.lstat()
        if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            fail("source_changed", f"{label} changed while being read")
        if stat.S_ISLNK(after_path.st_mode) or (after_path.st_dev, after_path.st_ino) != (after.st_dev, after.st_ino):
            fail("source_changed", f"{label} path changed while being read")
        return data
    except OSError as exc:
        fail("source_unavailable", f"{label} could not be read safely: {exc}")
    finally:
        os.close(fd)


def checked_path(root, parts, label, missing_code, symlink_code, unsafe_code):
    path = root
    for index, part in enumerate(parts):
        path = path / part
        try:
            st = path.lstat()
        except OSError as exc:
            fail(missing_code, f"{label} is unavailable: {exc}")
        if stat.S_ISLNK(st.st_mode):
            fail(symlink_code, f"{label} path contains a symlink")
        if index < len(parts) - 1 and not stat.S_ISDIR(st.st_mode):
            fail(unsafe_code, f"{label} parent is not a directory")
    return path


def capture_sources(source_root, vault, names):
    captured = []
    seen = set()
    for name in names:
        parts = validate_relative_name(name)
        rel = PurePosixPath(name).as_posix()
        if rel in seen:
            fail("duplicate_source", f"source path was selected more than once: {rel}")
        seen.add(rel)
        if is_sensitive(parts):
            fail("sensitive_candidate", f"known sensitive path candidate rejected: {rel}")
        if vault_drive.is_binary(rel):
            fail("binary_to_drive", f"binaries are kept on Drive, not in the vault; store it with vault_drive.py and link the file:// URL: {rel}")
        path = checked_path(source_root, parts, f"source {rel}", "source_unavailable", "symlink_source", "unsafe_source")
        try:
            real = path.resolve(strict=True)
        except OSError as exc:
            fail("source_unavailable", f"source file is unavailable ({rel}): {exc}")
        if not inside(real, source_root):
            fail("source_escape", f"source path escapes source-root: {rel}")
        if inside(real, vault):
            fail("source_inside_vault", f"source files must not be inside the target vault: {rel}")
        data = read_regular_file(path, rel)
        captured.append({
            "relative": rel,
            "source_path": str(source_root / Path(*parts)),
            "data": data,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data),
        })
    return captured


def validate_storage_dirs(vault, project_id):
    assets = vault / "assets"
    deliverables = assets / "deliverables"
    project_dir = deliverables / project_id
    files_dir = project_dir / "files"
    for path, label in ((assets, "assets"), (deliverables, "assets/deliverables"), (project_dir, f"project {project_id}"), (files_dir, "managed files")):
        try:
            st = path.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            fail("storage_path_error", f"cannot inspect {label}: {exc}")
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
            fail("unsafe_storage_path", f"{label} must be a real directory")
    catalog_path = project_dir / "catalog.json"
    if os.path.lexists(catalog_path):
        try:
            st = catalog_path.lstat()
        except OSError as exc:
            fail("catalog_error", f"catalog cannot be inspected: {exc}")
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
            fail("catalog_error", "catalog.json must be a real regular file")
    return project_dir, catalog_path


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def valid_timestamp(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.utcoffset() == dt.timedelta(0)


def validate_catalog(project_dir, catalog_path, source_root, project_id):
    if not os.path.lexists(catalog_path):
        files_dir = project_dir / "files"
        if os.path.lexists(files_dir):
            try:
                if not stat.S_ISDIR(files_dir.lstat().st_mode) or any(files_dir.iterdir()):
                    fail("unmanaged_storage", "files/ exists without a catalog; inspect it before syncing")
            except OSError as exc:
                fail("storage_path_error", f"cannot inspect files/: {exc}")
        return None, None, set(), {}
    raw = read_regular_file(catalog_path, "catalog.json")
    try:
        catalog = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        fail("invalid_catalog", f"catalog.json is not valid unambiguous JSON: {exc}")
    if not isinstance(catalog, dict) or set(catalog) != {"schema", "project_id", "source_root", "files"}:
        fail("invalid_catalog", "catalog.json has an unexpected structure")
    if type(catalog["schema"]) is not int or catalog["schema"] != 1:
        fail("invalid_catalog", "unsupported catalog schema")
    if catalog["project_id"] != project_id:
        fail("project_id_mismatch", "catalog project_id does not match --project-id")
    if catalog["source_root"] != str(source_root):
        fail("source_root_mismatch", "this project-id is already bound to a different source-root")
    if not isinstance(catalog["files"], dict):
        fail("invalid_catalog", "catalog files must be an object")

    owned_paths = set()
    timestamps = {}
    for relative, entry in catalog["files"].items():
        parts = validate_relative_name(relative)
        if is_sensitive(parts):
            fail("invalid_catalog", f"catalog contains a known sensitive source path: {relative}")
        if not isinstance(entry, dict) or set(entry) != {"source_path", "current_sha256", "versions"}:
            fail("invalid_catalog", f"invalid catalog entry: {relative}")
        expected_source = str(source_root / Path(*parts))
        if entry["source_path"] != expected_source:
            fail("invalid_catalog", f"catalog source path does not match its key: {relative}")
        current = entry["current_sha256"]
        versions = entry["versions"]
        if not isinstance(current, str) or not HASH_RE.fullmatch(current) or not isinstance(versions, list) or not versions:
            fail("invalid_catalog", f"invalid current hash or versions for: {relative}")
        hashes = set()
        for version in versions:
            if not isinstance(version, dict) or set(version) != {"sha256", "path", "size", "captured_at"}:
                fail("invalid_catalog", f"invalid version metadata for: {relative}")
            digest = version["sha256"]
            size = version["size"]
            path_value = version["path"]
            if not isinstance(digest, str) or not HASH_RE.fullmatch(digest) or digest in hashes:
                fail("invalid_catalog", f"invalid or duplicate version hash for: {relative}")
            if isinstance(size, bool) or not isinstance(size, int) or size < 0:
                fail("invalid_catalog", f"invalid version size for: {relative}")
            expected_path = f"files/{digest}/{PurePosixPath(relative).name}"
            if path_value != expected_path or not valid_timestamp(version["captured_at"]):
                fail("invalid_catalog", f"invalid version path or timestamp for: {relative}")
            saved = checked_path(
                project_dir, ["files", digest, PurePosixPath(relative).name],
                f"managed copy {path_value}", "catalog_copy_missing", "catalog_copy_unsafe", "catalog_copy_unsafe",
            )
            data = read_regular_file(saved, f"managed copy {path_value}", "catalog_copy_unsafe")
            if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
                fail("catalog_copy_tampered", f"managed copy does not match catalog: {path_value}")
            hashes.add(digest)
            owned_paths.add(path_value)
            timestamps.setdefault(path_value, version["captured_at"])
        if current not in hashes:
            fail("invalid_catalog", f"current hash has no preserved version: {relative}")
    return catalog, raw, owned_paths, timestamps


def make_plan(captured, catalog, owned_paths, project_dir):
    existing_files = catalog["files"] if catalog else {}
    planned_paths = set()
    plan = []
    catalog_changed = catalog is None
    for item in captured:
        relative = item["relative"]
        digest = item["sha256"]
        saved_relative = f"files/{digest}/{PurePosixPath(relative).name}"
        entry = existing_files.get(relative)
        old_current = entry["current_sha256"] if entry else None
        versions = entry["versions"] if entry else []
        has_version = any(version["sha256"] == digest for version in versions)
        needs_version = not has_version
        target_exists = os.path.lexists(project_dir / saved_relative)
        is_owned = saved_relative in owned_paths
        if target_exists and not is_owned and saved_relative not in planned_paths:
            fail("unmanaged_destination", f"destination already exists but is not cataloged: {saved_relative}")
        create_copy = needs_version and not is_owned and saved_relative not in planned_paths
        if create_copy:
            planned_paths.add(saved_relative)
        if not entry or old_current != digest or needs_version:
            catalog_changed = True
        plan.append({
            "relative": relative,
            "source_path": item["source_path"],
            "sha256": digest,
            "size": item["size"],
            "saved_relative": saved_relative,
            "saved_path": str(project_dir / saved_relative),
            "old_current": old_current,
            "catalog_entry_added": entry is None,
            "needs_version": needs_version,
            "create_copy": create_copy,
            "action": "create" if create_copy else "reuse",
        })
    return plan, catalog_changed


def ensure_directory(path, partial):
    try:
        st = path.lstat()
    except FileNotFoundError:
        try:
            path.mkdir()
            partial.append(str(path))
        except FileExistsError:
            pass
        except OSError as exc:
            fail("storage_write_failed", f"cannot create directory {path}: {exc}", partial)
        try:
            st = path.lstat()
        except OSError as exc:
            fail("storage_write_failed", f"cannot verify directory {path}: {exc}", partial)
    except OSError as exc:
        fail("storage_path_error", f"cannot inspect directory {path}: {exc}", partial)
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
        fail("unsafe_storage_path", f"destination must be a real directory: {path}", partial)


def write_immutable(path, data, partial):
    parent = path.parent
    tmp = None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=".sync-", dir=parent)
        tmp = Path(tmp_name)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(tmp, path)
        partial.append(str(path))
        tmp.unlink()
        tmp = None
        saved = read_regular_file(path, f"saved copy {path}")
        if saved != data:
            fail("readback_failed", f"saved copy differs from source: {path}", partial)
    except FileExistsError:
        fail("unmanaged_destination", f"refusing to overwrite existing destination: {path}", partial)
    except SyncError:
        raise
    except OSError as exc:
        fail("storage_write_failed", f"cannot save immutable copy {path}: {exc}", partial)
    finally:
        if tmp is not None:
            try:
                tmp.unlink()
            except OSError:
                pass


def atomic_catalog_write(path, data, previous_bytes, partial):
    tmp = None
    try:
        if os.path.lexists(path):
            current = read_regular_file(path, "catalog.json")
            if previous_bytes is None or current != previous_bytes:
                fail("catalog_changed", "catalog changed outside this helper; reconcile before retrying", partial)
        elif previous_bytes is not None:
            fail("catalog_changed", "catalog disappeared outside this helper; reconcile before retrying", partial)
        fd, tmp_name = tempfile.mkstemp(prefix=".catalog-", dir=path.parent)
        tmp = Path(tmp_name)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if previous_bytes is None:
            os.link(tmp, path)
            partial.append(str(path))
            tmp.unlink()
            tmp = None
        else:
            os.replace(tmp, path)
            partial.append(str(path))
            tmp = None
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
        readback = read_regular_file(path, "catalog.json")
        if readback != data:
            fail("readback_failed", "catalog readback differs from the new catalog", partial)
    except SyncError:
        raise
    except OSError as exc:
        fail("catalog_write_failed", f"cannot atomically write catalog.json: {exc}", partial)
    finally:
        if tmp is not None:
            try:
                tmp.unlink()
            except OSError:
                pass


def acquire_lock(project_dir):
    # shortcut: lock coordinates this helper only; use vault-wide transactions if concurrent editors must be supported.
    lock = project_dir / ".sync_project.lock"
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        fail("lock_busy", "another sync helper holds the project lock; inspect stale locks before retrying")
    except OSError as exc:
        fail("lock_failed", f"cannot acquire project lock: {exc}")
    try:
        os.write(fd, f"pid={os.getpid()}\n".encode("ascii"))
        os.fsync(fd)
    except OSError as exc:
        os.close(fd)
        try:
            lock.unlink()
        except OSError:
            pass
        fail("lock_failed", f"cannot initialize project lock: {exc}")
    return lock, fd


def release_lock(lock, fd, partial):
    os.close(fd)
    try:
        lock.unlink()
    except OSError as exc:
        fail("lock_cleanup_failed", f"could not remove cooperative lock {lock}: {exc}", [*partial, str(lock)])


def build_catalog(project_id, source_root, old_catalog, plan, timestamps):
    catalog = old_catalog if old_catalog is not None else {
        "schema": 1,
        "project_id": project_id,
        "source_root": str(source_root),
        "files": {},
    }
    for item in plan:
        if not item["catalog_entry_added"] and not item["needs_version"] and item["old_current"] == item["sha256"]:
            continue
        entry = catalog["files"].get(item["relative"])
        if entry is None:
            entry = {
                "source_path": item["source_path"],
                "current_sha256": item["sha256"],
                "versions": [],
            }
            catalog["files"][item["relative"]] = entry
        if item["needs_version"]:
            entry["versions"].append({
                "sha256": item["sha256"],
                "path": item["saved_relative"],
                "size": item["size"],
                "captured_at": timestamps[item["saved_relative"]],
            })
        entry["current_sha256"] = item["sha256"]
    return catalog


def result_payload(vault, project_id, source_root, project_dir, catalog_path, plan, catalog_changed, applied):
    created = sum(item["action"] == "create" for item in plan)
    items = []
    for item in plan:
        action = item["action"]
        items.append({
            "source": item["relative"],
            "source_path": item["source_path"],
            "sha256": item["sha256"],
            "size": item["size"],
            "saved_path": item["saved_path"],
            "catalog_path": item["saved_relative"],
            "action": ("created" if action == "create" else "reused") if applied else ("would_create" if action == "create" else "would_reuse"),
            **({"changed_from_sha256": item["old_current"]} if item["old_current"] and item["old_current"] != item["sha256"] else {}),
        })
    return {
        "ok": True,
        "project_id": project_id,
        "vault": str(vault),
        "project_path": str(project_dir),
        "catalog_path": str(catalog_path),
        "source_root": str(source_root),
        "applied": applied,
        "catalog_changed": catalog_changed,
        "items": items,
        "counts": {
            "selected": len(plan),
            "new_copies": created,
            "reused_copies": len(plan) - created,
            "catalog_entries_added": sum(item["catalog_entry_added"] for item in plan),
            "current_hash_changes": sum(bool(item["old_current"] and item["old_current"] != item["sha256"]) for item in plan),
        },
    }


def run_sync(args):
    project_id = validate_project_id(args.project_id)
    vault = validate_vault(args.vault)
    source_root = absolute_directory(args.source_root, "source-root")
    if inside(source_root, vault):
        fail("source_inside_vault", "source-root must be outside the target vault")
    initial = capture_sources(source_root, vault, args.files)
    project_dir, catalog_path = validate_storage_dirs(vault, project_id)
    catalog, catalog_bytes, owned, timestamps = validate_catalog(project_dir, catalog_path, source_root, project_id)
    plan, catalog_changed = make_plan(initial, catalog, owned, project_dir)
    if not args.apply:
        return result_payload(vault, project_id, source_root, project_dir, catalog_path, plan, catalog_changed, False)

    partial = []
    for directory in (vault / "assets", vault / "assets" / "deliverables", project_dir, project_dir / "files"):
        ensure_directory(directory, partial)
    try:
        lock, lock_fd = acquire_lock(project_dir)
    except SyncError as exc:
        exc.partial_writes.extend(path for path in partial if path not in exc.partial_writes)
        raise
    try:
        latest = capture_sources(source_root, vault, args.files)
        if latest != initial:
            fail("source_changed", "selected source bytes changed after planning; rerun after review", partial)
        current_catalog, current_bytes, current_owned, current_timestamps = validate_catalog(project_dir, catalog_path, source_root, project_id)
        current_plan, current_changed = make_plan(latest, current_catalog, current_owned, project_dir)
        if not current_changed:
            return result_payload(vault, project_id, source_root, project_dir, catalog_path, current_plan, False, True)

        path_timestamps = dict(current_timestamps)
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
        for item in current_plan:
            if item["needs_version"]:
                path_timestamps.setdefault(item["saved_relative"], now)
        for item, source in zip(current_plan, latest):
            if item["create_copy"]:
                destination = project_dir / item["saved_relative"]
                ensure_directory(destination.parent, partial)
                write_immutable(destination, source["data"], partial)
        final_sources = capture_sources(source_root, vault, args.files)
        if final_sources != latest:
            fail("source_changed", "selected source bytes changed during storage; catalog was not updated", partial)
        new_catalog = build_catalog(project_id, source_root, current_catalog, current_plan, path_timestamps)
        new_bytes = (json.dumps(new_catalog, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        atomic_catalog_write(catalog_path, new_bytes, current_bytes, partial)
        checked, readback, _paths, _times = validate_catalog(project_dir, catalog_path, source_root, project_id)
        if checked != new_catalog or readback != new_bytes:
            fail("readback_failed", "catalog verification after write failed", partial)
        return result_payload(vault, project_id, source_root, project_dir, catalog_path, current_plan, True, True)
    except SyncError as exc:
        exc.partial_writes.extend(path for path in partial if path not in exc.partial_writes)
        raise
    finally:
        release_lock(lock, lock_fd, partial)


def parser_for_cli():
    class JsonArgumentParser(argparse.ArgumentParser):
        def error(self, message):
            raise SyncError("usage_error", message)

    parser = JsonArgumentParser(description="Archive explicitly selected local project files into a versioned Obsidian vault folder.")
    parser.add_argument("--vault", required=True, help="absolute path to the target vault")
    parser.add_argument("--project-id", required=True, help="stable ASCII project ID")
    parser.add_argument("--source-root", required=True, help="absolute path to the source root")
    parser.add_argument("--files", nargs="+", required=True, metavar="RELATIVE_PATH", help="explicit source-root-relative files; no recursive collection")
    parser.add_argument("--apply", action="store_true", help="write immutable copies and update the version catalog; default is dry run")
    parser.epilog = "Sensitive basename/path denylist is limited and is not a complete secret scanner. Dry run creates no files, folders, or locks."
    return parser


def main(argv=None):
    applied = "--apply" in (argv if argv is not None else sys.argv[1:])
    try:
        args = parser_for_cli().parse_args(argv)
        payload = run_sync(args)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0
    except SyncError as exc:
        print(json.dumps({
            "ok": False,
            "applied": applied,
            "error": {"code": exc.code, "message": str(exc)},
            "partial_writes": exc.partial_writes,
        }, ensure_ascii=False, sort_keys=True))
        return 2
    except Exception as exc:
        print(json.dumps({
            "ok": False,
            "applied": applied,
            "error": {"code": "internal_error", "message": f"{type(exc).__name__}: {exc}"},
            "partial_writes": [],
        }, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
