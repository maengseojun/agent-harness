#!/usr/bin/env python3
"""Preview or apply an explicit, source-hash-bound Obsidian wiki plan."""

import argparse
import errno
import json
import os
import re
import stat
import tempfile
from pathlib import Path
from pathlib import PurePosixPath
from urllib.parse import unquote

import source_snapshot as snapshot
import mcp_vault


HASH_RE = snapshot.HASH_RE
OPERATION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
TEXT_SUFFIXES = {".body", ".csv", ".html", ".json", ".md", ".text", ".tsv", ".txt", ".xml", ".yaml", ".yml"}
WIKILINK_RE = re.compile(r"!?\[\[([^\]]+)\]\]")
MARKDOWN_LINK_RE = re.compile(r"(?<!!)(?<!\\)\[([^\]\n]*)\]\(\s*(<[^>\n]*>|(?:\\.|[^)\s])+)(?:\s+(['\"])[^\)\n]*?\3)?\s*\)")
FENCED_CODE_RE = re.compile(r"(?ms)^[ \t]*(```+|~~~+)[^\n]*\n.*?^[ \t]*\1[ \t]*$")
INLINE_CODE_RE = re.compile(r"(?<!`)`[^`\n]*`(?!`)")
BACKUP_ROOT = "raw/wiki-compile-versions"


def fail(code, message):
    raise snapshot.SnapshotError(code, message)


def validate_plan(value):
    if not isinstance(value, dict) or set(value) != {"operation_id", "hub", "sources", "notes"}:
        fail("invalid_plan", "plan must contain exactly operation_id, hub, sources, and notes")
    operation_id = value["operation_id"]
    if not isinstance(operation_id, str) or not OPERATION_ID_RE.fullmatch(operation_id) or operation_id in {".", ".."}:
        fail("invalid_plan", "operation_id must be a short path-safe identifier")

    hub = value["hub"]
    parts = snapshot.validate_relative_path(hub)
    if len(parts) < 2 or parts[0] != "hubs" or not hub.lower().endswith(".md"):
        fail("invalid_hub", "hub must be an exact Markdown path under hubs/")

    sources = value["sources"]
    notes = value["notes"]
    if not isinstance(sources, list) or not sources or not isinstance(notes, list) or not notes:
        fail("invalid_plan", "plan needs at least one selected source and one derived note")

    source_paths = set()
    for source in sources:
        if not isinstance(source, dict) or set(source) != {"path", "sha256"}:
            fail("invalid_source", "each source must contain exactly path and sha256")
        path, digest = source["path"], source["sha256"]
        parts = snapshot.validate_relative_path(path)
        allowed = parts[0] == "raw" or (len(parts) >= 3 and parts[:2] == ["wiki", "sources"])
        if not allowed or path.startswith(BACKUP_ROOT + "/") or Path(path).suffix.lower() not in TEXT_SUFFIXES:
            fail("invalid_source", "sources must be selected text files under raw/ or wiki/sources/")
        if path in source_paths:
            fail("duplicate_source", f"duplicate source path: {path}")
        if not isinstance(digest, str) or not HASH_RE.fullmatch(digest):
            fail("invalid_source", f"source sha256 is invalid: {path}")
        source_paths.add(path)

    target_paths = set()
    for note in notes:
        if not isinstance(note, dict) or set(note) != {"path", "expected_sha256", "body"}:
            fail("invalid_note", "each note must contain exactly path, expected_sha256, and body")
        path, expected, body = note["path"], note["expected_sha256"], note["body"]
        parts = snapshot.validate_relative_path(path)
        is_wiki = len(parts) >= 3 and parts[0] == "wiki" and parts[1] in {"answers", "concepts", "entities"}
        is_index_or_log = path in {"wiki/index.md", "log.md"}
        is_selected_hub = path == hub
        if not path.lower().endswith(".md") or not (is_wiki or is_index_or_log or is_selected_hub):
            fail("invalid_target", "targets must be derived wiki notes, wiki/index.md, log.md, or the selected hub")
        if path in target_paths or path in source_paths:
            fail("duplicate_target", f"duplicate or source target path: {path}")
        if expected is not None and (not isinstance(expected, str) or not HASH_RE.fullmatch(expected)):
            fail("invalid_note", f"expected_sha256 must be null or a lowercase SHA-256: {path}")
        if not isinstance(body, str) or not body.strip() or "\x00" in body:
            fail("invalid_note", f"body must be non-empty UTF-8 text: {path}")
        try:
            body.encode("utf-8")
        except UnicodeEncodeError:
            fail("invalid_note", f"body contains invalid UTF-8 text: {path}")
        target_paths.add(path)

    return value


def load_plan(value, vault):
    path = Path(value)
    if not path.is_absolute():
        fail("invalid_plan_path", "plan path must be absolute")
    try:
        if path.is_symlink() or not path.is_file():
            fail("invalid_plan_path", "plan must be an existing regular file, not a symlink")
        resolved = path.resolve(strict=True)
        if resolved.is_relative_to(vault.resolve(strict=True)):
            fail("invalid_plan_path", "plan files must stay outside the vault")
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=snapshot.reject_duplicate_keys)
    except snapshot.SnapshotError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        fail("invalid_plan", f"cannot read a unique-key UTF-8 JSON plan: {exc}")
    return validate_plan(value), resolved, snapshot.sha256(raw)


def backup_path(operation_id, target):
    suffix = target[len("wiki/"):] if target.startswith("wiki/") else target
    return f"{BACKUP_ROOT}/{operation_id}/{suffix}.body"


def markdown_targets(body):
    visible = FENCED_CODE_RE.sub("", body)
    visible = INLINE_CODE_RE.sub("", visible)
    for match in MARKDOWN_LINK_RE.finditer(visible):
        raw = match.group(2)
        target = raw[1:-1] if raw.startswith("<") and raw.endswith(">") else raw
        target = re.sub(r"\\([\\`*_{}\[\]()#+\-.!<>| ])", r"\1", target)
        target = unquote(re.split(r"[?#]", target, maxsplit=1)[0])
        if (target and not target.startswith("//") and
                not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target) and
                Path(target).suffix.lower() == ".md"):
            yield target


def extract_links(notes):
    links = []
    seen = set()
    for note in notes:
        for match in WIKILINK_RE.finditer(note["body"]):
            target = match.group(1).split("|", 1)[0].strip().split("#", 1)[0].strip()
            if not target:
                target = note["path"][:-3]
            if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
                continue
            if Path(target).suffix and Path(target).suffix.lower() != ".md":
                continue
            item = (note["path"], target)
            if item not in seen:
                seen.add(item)
                links.append({"source": item[0], "target": item[1]})
        for target in markdown_targets(note["body"]):
            item = (note["path"], target)
            if item not in seen:
                seen.add(item)
                links.append({"source": item[0], "target": item[1]})
    return links


def classify_target(note, state):
    if state["exists"] and state["body"] == note["body"]:
        return "noop"
    expected = note["expected_sha256"]
    if expected is None:
        if state["exists"]:
            fail("target_conflict", f"target exists with different content: {note['path']}")
        return "create"
    if not state["exists"] or snapshot.sha256(state["body"].encode("utf-8")) != expected:
        fail("target_conflict", f"target no longer matches expected_sha256: {note['path']}")
    return "update"


def unique_paths(paths):
    return list(dict.fromkeys(paths))


def _open_raw_file(vault, relative, *, create_parents=False, create_file=False, allow_note_bytes=False):
    parts = snapshot.validate_relative_path(relative)
    allowed_selected_source = len(parts) >= 3 and parts[:2] == ["wiki", "sources"]
    allowed_derived_note = (
        relative in {"wiki/index.md", "log.md"}
        or len(parts) >= 2 and parts[0] == "hubs"
        or len(parts) >= 3 and parts[0] == "wiki" and parts[1] in {"answers", "concepts", "entities"}
    )
    allowed = bool(parts) and (parts[0] == "raw" or allowed_selected_source or (allow_note_bytes and allowed_derived_note))
    if (not allowed
            or any(part.startswith(".") or part.lower() in {".git", ".obsidian", "node_modules"} for part in parts)):
        fail("unsafe_storage_path", "filesystem read is outside the selected artifact or derived-note scope")
    root = snapshot.validate_vault(vault)
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(root, directory_flags)
    try:
        for part in parts[:-1]:
            try:
                child = os.open(part, directory_flags, dir_fd=descriptor)
            except FileNotFoundError:
                if not create_parents:
                    os.close(descriptor)
                    return None, None
                os.mkdir(part, mode=0o700, dir_fd=descriptor)
                child = os.open(part, directory_flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        if create_file:
            try:
                file_descriptor = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=descriptor)
            except FileExistsError:
                return descriptor, None
        else:
            try:
                file_descriptor = os.open(parts[-1], os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0), dir_fd=descriptor)
            except FileNotFoundError:
                return descriptor, None
        if not stat.S_ISREG(os.fstat(file_descriptor).st_mode):
            os.close(file_descriptor)
            fail("unsafe_storage_path", "selected raw artifact is not a regular file")
        return descriptor, file_descriptor
    except (OSError, snapshot.SnapshotError):
        os.close(descriptor)
        raise


def read_raw_bytes(vault, relative, *, allow_note_bytes=False):
    parent = descriptor = None
    try:
        parent, descriptor = _open_raw_file(vault, relative, allow_note_bytes=allow_note_bytes)
        if descriptor is None:
            return None
        chunks = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
    except snapshot.SnapshotError:
        raise
    except OSError as exc:
        fail("source_unavailable", f"cannot read selected raw artifact {relative}: {exc}")
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if parent is not None:
            os.close(parent)


def read_note_bytes(vault, relative):
    if not relative.lower().endswith(".md"):
        fail("unsafe_storage_path", "byte reads for backups require a selected Markdown target")
    return read_raw_bytes(vault, relative, allow_note_bytes=True)


def write_backup(vault, relative, expected_bytes):
    if not relative.startswith(BACKUP_ROOT + "/") or not relative.endswith(".body"):
        fail("unsafe_storage_path", "version backups must remain under raw/wiki-compile-versions/")
    parent = descriptor = None
    try:
        parent, descriptor = _open_raw_file(vault, relative, create_parents=True, create_file=True)
        if descriptor is None:
            existing = read_raw_bytes(vault, relative)
            if existing != expected_bytes:
                fail("backup_conflict", f"version path already contains different bytes: {relative}")
            return False
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = None
            stream.write(expected_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        os.close(parent)
        parent = None
        if read_raw_bytes(vault, relative) != expected_bytes:
            fail("readback_failed", f"backup readback differs: {relative}")
        return True
    except snapshot.SnapshotError:
        raise
    except OSError as exc:
        fail("backup_write_failed", f"cannot save byte backup {relative}: {exc}")
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if parent is not None:
            os.close(parent)


def read_source_states(plan, adapter, vault):
    markdown_paths = [source["path"] for source in plan["sources"] if Path(source["path"]).suffix.lower() == ".md"]
    markdown = adapter.read_notes(markdown_paths)
    result = {}
    for source in plan["sources"]:
        path = source["path"]
        if Path(path).suffix.lower() == ".md":
            result[path] = markdown[path]
            continue
        raw = read_raw_bytes(vault, path)
        if raw is None:
            result[path] = {"exists": False, "body": None, "sha256": None}
            continue
        try:
            body = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            fail("source_unavailable", f"selected text source is not UTF-8: {path}: {exc}")
        result[path] = {"exists": True, "body": body, "sha256": snapshot.sha256(raw)}
    return result


def _normalized_candidates(target, source):
    value = (target or "").split("|", 1)[0].split("#", 1)[0].strip()
    if not value:
        value = source[:-3] if source.lower().endswith(".md") else source

    def normalized(parts):
        result = []
        for part in parts:
            if part in ("", "."):
                continue
            if part == "..":
                if not result:
                    return None
                result.pop()
            else:
                result.append(part)
        return "/".join(result) if result else None

    rooted = value.startswith("/")
    raw = value[1:] if rooted else value
    root_path = normalized(raw.split("/"))
    relative_path = None if rooted else normalized(source.split("/")[:-1] + raw.split("/"))
    candidates = []
    for candidate in (root_path, relative_path):
        if candidate:
            candidates.append(candidate if candidate.lower().endswith(".md") else candidate + ".md")
    return list(dict.fromkeys(candidates))


def check_links(notes, planned_paths, adapter):
    planned = set(planned_paths)
    missing = []
    for link in extract_links(notes):
        candidates = _normalized_candidates(link["target"], link["source"])
        resolved = set(candidate for candidate in candidates if candidate in planned)
        for candidate in candidates:
            if candidate in planned:
                continue
            try:
                if adapter.note_exists(candidate):
                    resolved.add(candidate)
            except mcp_vault.MCPVaultError:
                continue
        if len(resolved) > 1:
            fail("ambiguous_link", f"note link resolves to multiple exact paths: {link['target']}")
        found = len(resolved) == 1
        target = link["target"].split("|", 1)[0].split("#", 1)[0].strip()
        if not found and target and "/" not in target:
            base = target[:-3] if target.lower().endswith(".md") else target
            matches = {path for path in planned if PurePosixPath(path).name[:-3].casefold() == base.casefold()}
            matches.update(adapter.find_note_paths(target))
            if len(matches) > 1:
                fail("ambiguous_link", f"note link resolves to multiple existing notes: {target}")
            found = len(matches) == 1
        if not found:
            missing.append(link)
    return missing


def backup_state(vault, path):
    data = read_raw_bytes(vault, path)
    return {"exists": data is not None, "bytes": data, "sha256": snapshot.sha256(data) if data is not None else None}


def _verify_sources(plan, adapter, vault):
    states = read_source_states(plan, adapter, vault)
    for source in plan["sources"]:
        current = states[source["path"]]
        if not current["exists"]:
            fail("source_missing", f"selected source is missing: {source['path']}")
        if current["sha256"] != source["sha256"]:
            fail("source_changed", f"selected source hash changed: {source['path']}")
    return states


def preflight(plan, adapter, vault):
    sources = plan["sources"]
    notes = plan["notes"]
    target_paths = [note["path"] for note in notes]
    source_states = _verify_sources(plan, adapter, vault)
    states = adapter.read_notes(unique_paths([plan["hub"]] + target_paths))

    source_rows = [{"path": source["path"], "sha256": source["sha256"], "verified": True} for source in sources]
    if plan["hub"] not in target_paths and not states[plan["hub"]]["exists"]:
        fail("missing_hub", f"selected hub is missing: {plan['hub']}")

    changes = []
    backup_targets = []
    for note in notes:
        current = states[note["path"]]
        action = classify_target(note, current)
        path = backup_path(plan["operation_id"], note["path"])
        item = {
            "path": note["path"], "action": action,
            "expected_sha256": note["expected_sha256"], "current_sha256": current["sha256"],
            "backup_path": path,
        }
        changes.append(item)
        backup_targets.append((note, current, path, action, item))
        mcp_vault._validate_helper_parent_chain(note["path"], vault)

    backup_states = {}
    for note, current, path, action, item in backup_targets:
        prior = backup_state(vault, path)
        backup_states[path] = prior
        if action == "create" and prior["exists"]:
            fail("backup_conflict", f"version path already exists for a new target: {path}")
        if action == "update" and prior["exists"]:
            current_bytes = read_note_bytes(vault, note["path"])
            if current_bytes is None or snapshot.sha256(current_bytes) != current["sha256"]:
                fail("target_changed", f"target changed during backup preflight: {note['path']}")
            if prior["bytes"] != current_bytes:
                fail("backup_conflict", f"version path already contains different bytes: {path}")
            item["backup_reused"] = True
        elif action == "update":
            item["backup_reused"] = False

    missing = check_links(notes, target_paths, adapter)
    if missing:
        first = missing[0]
        fail("missing_link", f"note link from {first.get('source')} does not resolve: {first.get('target')}")

    return {
        "sources": source_rows, "changes": changes, "links_checked": len(extract_links(notes)),
        "states": states, "backup_states": backup_states, "source_states": source_states,
    }


def _plan_hash_matches(plan_path, expected_hash):
    descriptor = None
    try:
        descriptor = os.open(plan_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return False
        hasher = __import__("hashlib").sha256()
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                return hasher.hexdigest() == expected_hash
            hasher.update(chunk)
    except OSError:
        return False
    finally:
        if descriptor is not None:
            os.close(descriptor)


def apply_plan(plan, plan_path, plan_hash, adapter, vault):
    performed = []
    uncertain = False
    try:
        for note in plan["notes"]:
            if not _plan_hash_matches(plan_path, plan_hash):
                fail("plan_changed", "staged plan changed during apply; reconcile before retrying")
            _verify_sources(plan, adapter, vault)
            current = adapter.read_notes([note["path"]])[note["path"]]
            action = classify_target(note, current)
            if action == "noop":
                continue
            backup = backup_path(plan["operation_id"], note["path"])
            if action == "update":
                current_bytes = read_note_bytes(vault, note["path"])
                if current_bytes is None or snapshot.sha256(current_bytes) != current["sha256"]:
                    fail("target_changed", f"target changed before its byte backup: {note['path']}")
                prior = read_raw_bytes(vault, backup)
                if prior is None:
                    if write_backup(vault, backup, current_bytes):
                        performed.append(backup)
                elif prior != current_bytes:
                    fail("backup_conflict", f"version path changed before update: {backup}")
            elif read_raw_bytes(vault, backup) is not None:
                fail("backup_conflict", f"version path appeared before create: {backup}")

            if not _plan_hash_matches(plan_path, plan_hash):
                fail("plan_changed", "staged plan changed before note write; reconcile before retrying")
            _verify_sources(plan, adapter, vault)
            current = adapter.read_notes([note["path"]])[note["path"]]
            second_action = classify_target(note, current)
            if second_action == "noop":
                continue
            if second_action != action:
                fail("target_changed", f"target changed before note write: {note['path']}")
            mcp_vault._validate_helper_parent_chain(note["path"], vault)
            uncertain = True
            adapter.write_note(note["path"], note["body"])
            performed.append(note["path"])
            readback = adapter.read_notes([note["path"]])[note["path"]]
            if not readback["exists"] or readback["body"] != note["body"]:
                fail("readback_failed", f"written note did not match its separate MCP readback: {note['path']}")
            uncertain = False
        status = "applied" if any(path in {note["path"] for note in plan["notes"]} for path in performed) else "noop"
        return {"operation_id": plan["operation_id"], "status": status, "performed_paths": performed, "error": None}
    except Exception as exc:
        code = getattr(exc, "code", "mcp_write_failed" if uncertain else "apply_failed")
        status = "uncertain" if uncertain else ("partial_failure" if performed else "rejected")
        return {
            "operation_id": plan["operation_id"], "status": status, "performed_paths": performed,
            "error": {"code": code, "message": str(exc)},
        }


def _effect_states(plan, vault, adapter):
    note_paths = [note["path"] for note in plan["notes"]]
    notes = adapter.read_notes(note_paths)
    backups = {backup_path(plan["operation_id"], path): None for path in note_paths}
    for path in backups:
        backups[path] = backup_state(vault, path)
    return notes, backups


def apply_result(plan, plan_path, plan_hash, adapter, vault, before):
    receipt = apply_plan(plan, plan_path, plan_hash, adapter, vault)
    try:
        after_notes, after_backups = _effect_states(plan, vault, adapter)
    except Exception as exc:
        return {
            "ok": False, "status": "uncertain", "operation_id": plan["operation_id"],
            "performed_paths": receipt["performed_paths"], "observed_changed_paths": [], "readback": [],
            "error": receipt.get("error") or {"code": "readback_failed", "message": str(exc)},
            "readback_error": str(exc),
        }

    after = dict(after_notes)
    for path, state in after_backups.items():
        after[path] = {"exists": state["exists"], "sha256": state["sha256"], "bytes": state["bytes"]}
    changed = []
    readback = []
    note_by_path = {note["path"]: note for note in plan["notes"]}
    for path, current in after.items():
        old = before.get(path, {"exists": False, "sha256": None})
        if old["exists"] != current["exists"] or old["sha256"] != current["sha256"]:
            changed.append(path)
        if path in note_by_path:
            readback.append({
                "path": path, "exists": current["exists"], "sha256": current["sha256"],
                "desired_match": current["exists"] and current["body"] == note_by_path[path]["body"],
            })
        elif current["exists"]:
            readback.append({"path": path, "exists": True, "sha256": current["sha256"], "desired_match": None})

    all_desired = all(after_notes[note["path"]]["exists"] and after_notes[note["path"]]["body"] == note["body"] for note in plan["notes"])
    status = receipt["status"]
    if status == "uncertain":
        ok = False
    elif status == "partial_failure":
        ok = False
    elif status == "rejected":
        status = "partial_failure" if changed else "rejected"
        ok = False
    elif not all_desired:
        status, ok = ("partial_failure", False) if changed else ("uncertain", False)
    elif changed:
        status, ok = "applied", True
    else:
        status, ok = "noop", True
    return {
        "ok": ok, "status": status, "operation_id": plan["operation_id"],
        "performed_paths": receipt["performed_paths"], "observed_changed_paths": changed,
        "readback": readback, "error": receipt.get("error"),
    }


def _run(args, vault, plan, plan_path, plan_hash, adapter):
    adapter.assert_vault(vault)
    checked = preflight(plan, adapter, vault)
    if not args.apply:
        return {
            "ok": True, "status": "preview", "applied": False,
            "operation_id": plan["operation_id"], "hub": plan["hub"],
            "sources": checked["sources"], "notes": checked["changes"],
            "links_checked": checked["links_checked"],
        }
    before = dict(checked["states"])
    for path, state in checked["backup_states"].items():
        before[path] = {"exists": state["exists"], "sha256": state["sha256"]}
    for note in plan["notes"]:
        before.setdefault(backup_path(plan["operation_id"], note["path"]), {"exists": False, "sha256": None})
    return apply_result(plan, plan_path, plan_hash, adapter, vault, before)


def run(args, adapter=None):
    vault = snapshot.validate_vault(args.vault)
    plan, plan_path, plan_hash = load_plan(args.plan, vault)
    if adapter is not None:
        return _run(args, vault, plan, plan_path, plan_hash, adapter)
    with mcp_vault.MCPVaultHelpers(expected_vault=vault) as client:
        return _run(args, vault, plan, plan_path, plan_hash, client)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True, help="exact configured vault folder")
    parser.add_argument("--plan", required=True, help="absolute path to a private UTF-8 JSON plan")
    parser.add_argument("--apply", action="store_true", help="apply the explicitly reviewed plan; default is preview")
    args = parser.parse_args(argv)
    try:
        result = run(args)
    except snapshot.SnapshotError as exc:
        result = {"ok": False, "status": "rejected", "error": {"code": exc.code, "message": str(exc)}}
    except Exception as exc:
        result = {"ok": False, "status": "rejected", "error": {"code": "compile_failed", "message": str(exc)}}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
