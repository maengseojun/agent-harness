#!/usr/bin/env python3
"""maeng-archive: cold-storage archive, backup and restore for the Obsidian vault.

Stdlib only (Python 3.11+). Nothing is deleted before a hash-verified copy exists.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import secrets
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

STORES = ("onedrive", "gdrive")
DEFAULT_GDRIVE = "GoogleDrive-2025131619@korea.ac.kr"  # all Drive use stays on the school account for now (MAE-257); MAENG_ARCHIVE_GDRIVE switches it
ARCHIVE_DIR = "maeng-archive"
BACKUP_DIR = "maeng-backup"
EXCLUDE_DIRS = {".trash", ".cache", "__pycache__", "cache", "Cache", ".git"}


class ArchiveError(Exception):
    pass


# ---------- configuration ----------
def vault_root() -> Path:
    return Path(os.environ.get("MAENG_VAULT") or Path.home() / "Documents" / "Obsidian Vault").expanduser()


def maeng_home() -> Path:
    return Path(os.environ.get("MAENG_HOME") or Path.home() / ".local" / "share" / "maeng-harness").expanduser()


def store_root(name: str) -> Path | None:
    if name not in STORES:
        raise ArchiveError(f"unknown store: {name}")
    if name == "onedrive":
        env = os.environ.get("MAENG_ARCHIVE_ONEDRIVE")
        if env:
            p = Path(env).expanduser()
            return p if p.is_dir() else None
        base = Path.home() / "Library" / "CloudStorage"
        default = base / "OneDrive-고려대학교"
        if default.is_dir():
            return default
        found = sorted(glob.glob(str(base / "OneDrive-*")))
        return Path(found[0]) if found else None
    env = os.environ.get("MAENG_ARCHIVE_GDRIVE")
    if env:
        p = Path(env).expanduser()
        return p if p.is_dir() else None
    base = Path.home() / "Library" / "CloudStorage"
    for sub in ("My Drive", "내 드라이브"):
        if (base / DEFAULT_GDRIVE / sub).is_dir():
            return base / DEFAULT_GDRIVE / sub
    for pat in ("GoogleDrive-*/My Drive", "GoogleDrive-*/내 드라이브"):
        found = sorted(glob.glob(str(base / pat)))
        if found:
            return Path(found[0])
    return None


# ---------- file helpers ----------
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _exclusive_publish(tmp: str, dst: Path) -> str:
    """Create dst from the fsynced temp file without ever replacing an existing dst.

    Returns "link" or "fallback". Fast path is link() (atomic, raises FileExistsError). Cloud File Provider
    mounts (OneDrive/Google Drive) may reject link(); then create dst with O_CREAT|O_EXCL, copy the bytes,
    fsync and verify size+sha256. A failed fallback removes only the file it created."""
    try:
        os.link(tmp, dst)  # raises FileExistsError instead of overwriting
        return "link"
    except FileExistsError:
        raise
    except OSError:
        pass  # EPERM/ENOTSUP/EXDEV/EOPNOTSUPP or any other link failure: use the portable path
    fd = os.open(dst, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)  # FileExistsError if present
    try:
        with os.fdopen(fd, "wb") as out, open(tmp, "rb") as inp:
            shutil.copyfileobj(inp, out, 1 << 20)
            out.flush()
            os.fsync(out.fileno())
        if os.path.getsize(dst) != os.path.getsize(tmp) or sha256_file(Path(dst)) != sha256_file(Path(tmp)):
            raise ArchiveError(f"exclusive fallback copy verification failed: {dst}")
    except BaseException:
        try:
            os.unlink(dst)
        except OSError:
            pass
        raise
    return "fallback"


def copy_file(src: Path, dst: Path, exclusive: bool = False) -> str:
    """Copy via temp file in the destination directory, fsync, then atomic rename.

    exclusive=True never replaces an existing destination: link() when supported, else an O_EXCL
    create-and-verify fallback. Returns the path used ("replace", "link" or "fallback")."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dst.parent, prefix=".tmp-archive-")
    try:
        with os.fdopen(fd, "wb") as out, open(src, "rb") as inp:
            shutil.copyfileobj(inp, out, 1 << 20)
            out.flush()
            os.fsync(out.fileno())
        if exclusive:
            how = _exclusive_publish(tmp, dst)
            os.unlink(tmp)
        else:
            os.replace(tmp, dst)
            how = "replace"
        return how
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def write_text_atomic(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-stub-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def now() -> dt.datetime:
    return dt.datetime.now().astimezone()


# ---------- frontmatter ----------
def split_frontmatter(text: str) -> tuple[list[str], str]:
    if text.startswith("---\n"):
        end = text.find("\n---\n", 3)
        if end != -1:
            return text[4:end].split("\n"), text[end + 5:]
        if text.endswith("\n---"):
            return text[4:-4].split("\n"), ""
    return [], text


def parse_stub(text: str) -> dict | None:
    lines, _ = split_frontmatter(text)
    status = any(l.strip() == "status: archived" for l in lines)
    meta: dict = {}
    in_block = False
    for l in lines:
        if l.startswith("archive:"):
            in_block = True
            continue
        if in_block:
            if l.startswith("  ") and ":" in l:
                k, v = l.strip().split(":", 1)
                v = v.strip()
                try:
                    v = json.loads(v)
                except ValueError:
                    pass
                meta[k] = v
            else:
                in_block = False
    if status and meta.get("sha256"):
        return meta
    return None


def build_stub(original_text: str | None, meta: dict, world: str, rel: str) -> str:
    fm: list[str] = []
    if original_text is not None:
        fm, _ = split_frontmatter(original_text)
    fm = [l for l in fm if not l.startswith("status:")]
    # drop any previous archive block
    cleaned, skip = [], False
    for l in fm:
        if l.startswith("archive:"):
            skip = True
            continue
        if skip and l.startswith("  "):
            continue
        skip = False
        cleaned.append(l)
    fm = [l for l in cleaned if l.strip() != ""] if not cleaned else cleaned
    if not any(l.startswith("world:") for l in fm):
        fm.append(f"world: {world}")
    fm.append("archive:")
    for k in ("store", "path", "sha256", "size", "archived_at", "original", "stub_kind"):
        if k not in meta and k in ("original", "stub_kind"):
            continue  # only callers building legacy-form stubs omit these
        fm.append(f"  {k}: {json.dumps(meta[k], ensure_ascii=False)}")
    fm.append("status: archived")
    return (
        "---\n" + "\n".join(fm) + "\n---\n\n"
        "## Summary\n"
        "<!-- agent: fill a 3-5 line summary of what was here and why it was archived -->\n\n"
        f"Archived original: `{meta['store']}:{meta['path']}` (sha256 `{meta['sha256'][:12]}`)\n"
    )


# ---------- containment ----------
def resolved_vault() -> Path:
    try:
        return vault_root().resolve(strict=True)
    except (FileNotFoundError, OSError):
        raise ArchiveError(f"vault not found: {vault_root()}")


def ensure_inside_vault(vault: Path, path: Path, must_exist: bool = True) -> Path:
    """Reject paths that leave the resolved vault, or that reach it through a symlink
    (any ancestor between vault and the file, or the file itself)."""
    vault = vault.resolve(strict=True)
    p = path if path.is_absolute() else vault / path
    try:  # rebase a lexical (unresolved) vault prefix onto the resolved vault
        p = vault / p.relative_to(vault_root())
    except ValueError:
        pass
    try:
        parts = p.relative_to(vault).parts
    except ValueError:
        # path may be spelled via an unresolved vault prefix; compare resolved parent
        try:
            parts = p.parent.resolve(strict=False).relative_to(vault).parts + (p.name,)
        except ValueError:
            raise ArchiveError(f"path is outside the vault: {path}")
    cur = vault
    for comp in parts:
        cur = cur / comp
        if cur.is_symlink():
            raise ArchiveError(f"symlink in path (refusing): {cur}")
        if not cur.exists():
            break
    if must_exist:
        try:
            real = (vault / Path(*parts)).resolve(strict=True)
        except (FileNotFoundError, OSError):
            raise ArchiveError(f"not found: {path}")
        if real != vault and vault not in real.parents:
            raise ArchiveError(f"path resolves outside the vault: {path}")
        return real
    return vault / Path(*parts)


# ---------- move ----------
def _before_replace(src: Path) -> None:
    """Hook point between the verified copy and replacing the source (tests simulate a racing edit here)."""


def sidecar_world(src: Path) -> str | None:
    """`world` from the aside-collect JSON sidecar of a capture (<name>.json next to <name>.md, or the
    sidecar file itself). None when there is no readable sidecar or it has no string `world`."""
    stem = src.stem
    names = [src.name] if src.suffix.lower() == ".json" else []
    names += [stem + ".json"]
    if stem.endswith("-retry"):
        names.append(stem[: -len("-retry")] + ".json")
    for n in names:
        sc = src.with_name(n)
        if sc.is_file() and not sc.is_symlink():
            try:
                data = json.loads(sc.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            w = data.get("world") if isinstance(data, dict) else None
            if isinstance(w, str):
                return w
    if stem.endswith("-retry"):
        # aside-collect step 7 updates the FIRST run's sidecar (<STAMP>-<slug>-<nonce>.json), which then records the
        # retry nonce; the retry capture is <STAMP>-<slug>-<RNONCE>-retry.md
        prefix, _, rnonce = stem[: -len("-retry")].rpartition("-")
        for sc in sorted(src.parent.glob(prefix + "-*.json")):
            if sc.is_symlink():
                continue
            try:
                data = json.loads(sc.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and data.get("nonce") == rnonce and isinstance(data.get("world"), str):
                return data["world"]
    return None


def cmd_move(rel: str, store: str, world: str, dry_run: bool) -> dict:
    if Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise ArchiveError("path must be vault-relative without '..'")
    in_eta = Path(rel).parts[:1] == ("eta",)
    mismatch = (
        f"world/path mismatch: --world {world} with {rel}; eta material (under eta/ or with world: eta "
        "frontmatter) needs --world eta, everything else needs --world personal. Nothing changed")
    if in_eta and world != "eta":
        raise ArchiveError(mismatch)
    vault = resolved_vault()
    src = vault / rel
    ensure_inside_vault(vault, src, must_exist=False)
    is_md = src.suffix.lower() == ".md"
    if not is_md:
        # Non-markdown eta material is recognised by the folder or by the aside sidecar's `world`.
        sc_world = sidecar_world(src) if not in_eta else None
        if sc_world is not None and sc_world != world:
            raise ArchiveError(f"world mismatch: {rel} has sidecar world: {sc_world} but --world {world}. Nothing changed")
        if world == "eta" and not in_eta and sc_world != "eta":
            raise ArchiveError(mismatch)
    stub_path = src if is_md else src.with_name(src.name + ".archived.md")
    if is_md and src.is_file():
        text = src.read_text(encoding="utf-8", errors="replace")
        existing = parse_stub(text)
        if existing:
            return {"action": "already-archived", "stub": str(stub_path), "archive": existing}
    if not is_md and not src.exists() and stub_path.is_file():
        existing = parse_stub(stub_path.read_text(encoding="utf-8", errors="replace"))
        if existing:
            return {"action": "already-archived", "stub": str(stub_path), "archive": existing}
    if not src.is_file():
        raise ArchiveError(f"not a file in vault: {src}")
    ensure_inside_vault(vault, src, must_exist=True)
    if is_md:
        fm_world = [l.partition(":")[2].strip().strip("'\"") for l in
                    split_frontmatter(src.read_text(encoding="utf-8", errors="replace"))[0] if l.startswith("world:")]
        if not fm_world and not in_eta:  # aside raw captures carry the world only in their JSON sidecar
            fm_world = [w for w in [sidecar_world(src)] if w]
        if world == "eta" and not in_eta and fm_world[:1] != ["eta"]:
            raise ArchiveError(mismatch)
        if fm_world and fm_world[0] != world:
            raise ArchiveError(f"world mismatch: {rel} has world: {fm_world[0]} but --world {world}. Nothing changed")
    if _has_private(src):
        raise ArchiveError(
            f"refusing to move {rel}: it contains a <private> span, and <private> content never leaves "
            "the vault; remove or relocate the private text first. Nothing changed")
    root = store_root(store)
    if root is None:
        raise ArchiveError(f"store '{store}' not found; nothing changed")
    stamp = now()
    rel_posix = Path(rel).as_posix()
    arch_rel = f"{ARCHIVE_DIR}/{world}/{stamp.year}/{rel_posix}"
    dest = root / arch_rel
    src_hash = sha256_file(src)
    size = src.stat().st_size
    if not is_md and stub_path.exists():
        prior = parse_stub(stub_path.read_text(encoding="utf-8", errors="replace")) if stub_path.is_file() else None
        if not prior or prior.get("sha256") != src_hash:
            raise ArchiveError(f"refusing to overwrite existing {stub_path.name}: not a stub for this file")
        # Retry of an interrupted move: the stub is already written and is NOT disposable.
        # Verify its archived copy, remove only the binary, leave the stub byte-identical.
        prior_root = store_root(str(prior.get("store", "")))
        prior_copy = prior_root / str(prior.get("path", "")) if prior_root is not None else None
        if prior_copy is not None:  # the stub is vault data: its path must stay inside the archive root
            arch_root = (prior_root / ARCHIVE_DIR).resolve()
            real = prior_copy.resolve()
            if real != arch_root and arch_root not in real.parents:
                raise ArchiveError(
                    f"existing stub {stub_path.name} archive.path leaves the archive root; nothing changed")
        if prior_copy is None or not prior_copy.is_file() or sha256_file(prior_copy) != src_hash:
            raise ArchiveError(
                f"existing stub {stub_path.name} has no verified archive copy with the same sha256; "
                "nothing changed")
        if dry_run:
            return {"action": "dry-run", "resume_binary_removal": True, "source": str(src),
                    "destination": str(prior_copy), "sha256": src_hash, "stub": str(stub_path)}
        src.unlink()
        return {"action": "archived", "stub_preserved": True, "archive": prior, "source": str(src),
                "destination": str(prior_copy), "sha256": src_hash, "size": size, "stub": str(stub_path)}
    plan = {"source": str(src), "destination": str(dest), "sha256": src_hash, "size": size, "stub": str(stub_path)}
    reuse = False
    if dest.exists():
        if sha256_file(dest) != src_hash:
            raise ArchiveError(f"destination exists with different hash: {dest}")
        reuse = True
    if dry_run:
        return {"action": "dry-run", "reuse_existing": reuse, **plan}
    if not reuse:
        copy_file(src, dest)
    if sha256_file(dest) != src_hash:
        try:
            if not reuse:
                dest.unlink()
        finally:
            raise ArchiveError("hash mismatch after copy; vault unchanged")
    meta = {"store": store, "path": arch_rel, "sha256": src_hash, "size": size,
            "archived_at": stamp.isoformat(timespec="seconds"),
            "original": rel_posix, "stub_kind": "inplace" if is_md else "sibling"}
    _before_replace(src)
    original_bytes = src.read_bytes()
    if hashlib.sha256(original_bytes).hexdigest() != src_hash:
        if not reuse:
            dest.unlink()
        raise ArchiveError(f"{rel} changed during the move (edit after copy); original left untouched, nothing archived")
    # universal newlines, as read_text gives: split_frontmatter expects "---\n", so a CRLF note would lose its frontmatter
    original_text = (original_bytes.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
                     if is_md else None)
    stub = build_stub(original_text, meta, world, rel_posix)
    write_text_atomic(stub_path, stub)
    if not is_md:
        src.unlink()
    return {"action": "archived", "archive": meta, **plan}


# ---------- backup ----------
def _excluded(rel: Path) -> bool:
    parts = rel.parts
    if any(p in EXCLUDE_DIRS for p in parts[:-1]):
        return True
    name = parts[-1]
    if name == ".DS_Store":
        return True
    if parts[0] == ".obsidian" and len(parts) == 2 and name.startswith("workspace") and name.endswith(".json"):
        return True
    return False


def _walk(base: Path):
    def _onerror(err):
        raise ArchiveError(f"cannot read {getattr(err, 'filename', base)}: {err}; backup aborted, nothing written or pruned")

    for dirpath, dirnames, filenames in os.walk(base, onerror=_onerror):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            p = Path(dirpath) / fn
            if p.is_symlink():
                continue
            rel = p.relative_to(base)
            if not _excluded(rel):
                yield p, rel


_PRIVATE_BYTES = re.compile(rb"<\s*private", re.I)


def _has_private_bytes(data: bytes) -> bool:
    return bool(_PRIVATE_BYTES.search(data))


def _has_private(p: Path) -> bool:
    return _has_private_bytes(p.read_bytes())


def build_backup_zip(zip_path: Path, stamp: str) -> dict:
    files, excluded = [], []
    walked = md_count = 0
    vault, harness = vault_root(), maeng_home()
    present = {"vault": vault.is_dir(), "harness": harness.is_dir()}
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for label, base in (("vault", vault), ("harness", harness)):
            if not present[label]:
                continue
            for p, rel in _walk(base):
                walked += 1
                arc = f"{label}/{rel.as_posix()}"
                if label == "vault" and p.suffix.lower() == ".md":
                    md_count += 1
                # Single read: privacy scan, hash, size and archived bytes all come from `data`.
                data = p.read_bytes()
                if _has_private_bytes(data):
                    excluded.append(arc)
                    continue
                files.append({"path": arc, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})
                zi = zipfile.ZipInfo.from_file(p, arc)
                zi.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(zi, data)
        manifest = {"created": stamp, "file_count": len(files), "files": files,
                    "excluded_private": excluded, "walked": walked, "vault_md_count": md_count,
                    "roots_present": present}
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
    return manifest


def verify_backup(zip_path: Path, manifest: dict) -> None:
    if not manifest["roots_present"]["vault"]:
        raise ArchiveError(f"vault root missing: {vault_root()}")
    if manifest["vault_md_count"] < 1:
        raise ArchiveError(f"vault has no .md files: {vault_root()}")
    if manifest["file_count"] + len(manifest["excluded_private"]) != manifest["walked"]:
        raise ArchiveError("manifest count does not match files walked")
    with zipfile.ZipFile(zip_path) as zf:
        bad = zf.testzip()
        if bad:
            raise ArchiveError(f"corrupt zip member: {bad}")
        if len(zf.namelist()) != manifest["file_count"] + 1:
            raise ArchiveError("zip member count does not match manifest")
        names = set(zf.namelist())
        for entry in manifest["files"]:
            if entry["path"] not in names:
                raise ArchiveError(f"zip member missing: {entry['path']}")
            h = hashlib.sha256()
            with zf.open(entry["path"]) as m:
                for chunk in iter(lambda: m.read(1 << 20), b""):
                    h.update(chunk)
            if h.hexdigest() != entry["sha256"]:
                raise ArchiveError(f"archived bytes differ from manifest sha256: {entry['path']}")


def cmd_backup(targets: list[str], keep: int, dry_run: bool) -> dict:
    # Unique identity per run: two backups in the same second must never share a name.
    # The stamp is only an identity (microseconds + random suffix keep names unique). Retention does NOT
    # sort by name: _prune orders by (st_mtime_ns, name), so pruning depends on the store preserving
    # mtime; a cloud rehydration that resets mtimes would reorder which backups get pruned.
    stamp = now().strftime("%Y%m%d-%H%M%S-%f") + "-" + secrets.token_hex(3)
    name = f"maeng-{stamp}"
    result: dict = {"name": name, "stores": {}}
    vault = vault_root()
    if not vault.is_dir():
        raise ArchiveError(f"vault root missing: {vault}; nothing backed up, nothing pruned")
    if not any(p.suffix.lower() == ".md" for p, _ in _walk(vault)):
        raise ArchiveError(f"vault has no .md files: {vault}; nothing backed up, nothing pruned")
    result["harness_root"] = {"path": str(maeng_home()), "present": maeng_home().is_dir()}
    avail = {}
    for t in targets:
        root = store_root(t)
        if root is None:
            result["stores"][t] = {"status": "skipped", "reason": f"{t} store not found"}
        else:
            avail[t] = root
    if dry_run:
        count = sum(1 for b in (vault, maeng_home()) if b.is_dir() for _ in _walk(b))
        for t, root in avail.items():
            result["stores"][t] = {"status": "dry-run", "would_write": str(root / BACKUP_DIR / f"{name}.zip"), "file_count": count}
        return result
    if not avail:
        return result
    with tempfile.TemporaryDirectory(prefix="maeng-backup-") as td:
        tmp_zip = Path(td) / f"{name}.zip"
        manifest = build_backup_zip(tmp_zip, stamp)
        verify_backup(tmp_zip, manifest)  # raises before any copy or prune
        if manifest["excluded_private"]:
            result["excluded_private"] = manifest["excluded_private"]
            print(f"warning: {len(manifest['excluded_private'])} file(s) containing <private> excluded from backup: "
                  + ", ".join(manifest["excluded_private"]), file=sys.stderr)
        local_hash = sha256_file(tmp_zip)
        manifest_text = json.dumps({**manifest, "zip_sha256": local_hash}, ensure_ascii=False, indent=1)
        tmp_manifest = Path(td) / f"{name}.manifest.json"
        tmp_manifest.write_text(manifest_text, encoding="utf-8")
        for t, root in avail.items():
            bdir = root / BACKUP_DIR
            dest = bdir / f"{name}.zip"
            try:
                copy_file(tmp_zip, dest, exclusive=True)
                if sha256_file(dest) != local_hash:
                    dest.unlink()
                    raise ArchiveError("copied zip hash mismatch")
                with zipfile.ZipFile(dest) as zf:
                    bad = zf.testzip()
                if bad:
                    dest.unlink()
                    raise ArchiveError(f"corrupt zip member: {bad}")
                copy_file(tmp_manifest, bdir / f"{name}.manifest.json", exclusive=True)
            except (ArchiveError, OSError, zipfile.BadZipFile) as e:
                result["stores"][t] = {"status": "failed", "reason": str(e)}
                continue
            pruned = _prune(bdir, keep)  # only reached after verification
            result["stores"][t] = {"status": "ok", "zip": str(dest), "files": manifest["file_count"], "pruned": pruned}
    return result


def _prune(bdir: Path, keep: int) -> list[str]:
    zips = sorted(bdir.glob("maeng-*.zip"), key=lambda p: (p.stat().st_mtime_ns, p.name))  # oldest first
    old = zips[:-keep] if keep > 0 and len(zips) > keep else []
    gone = []
    for z in old:
        z.unlink()
        m = z.with_suffix(".manifest.json")
        if m.exists():
            m.unlink()
        gone.append(z.name)
    return gone


# ---------- restore ----------
def _original_of_stub(vault: Path, stub: Path, meta: dict) -> Path:
    """Original path of a stub. Uses explicit archive.original/stub_kind; legacy stubs are
    inferred from the archive path and refused when ambiguous. Never trusts the filename alone."""
    try:
        stub_rel = stub.relative_to(vault).as_posix()
    except ValueError:
        raise ArchiveError("stub is outside the vault")
    kind, original = meta.get("stub_kind"), meta.get("original")
    if kind is not None or original is not None:
        if kind not in ("inplace", "sibling") or not isinstance(original, str) or not original:
            raise ArchiveError("stub has invalid archive.original / archive.stub_kind; refusing")
        op = Path(original)
        if op.is_absolute() or ".." in op.parts:
            raise ArchiveError("stub archive.original must be vault-relative without '..'; refusing")
        expected = original if kind == "inplace" else original + ".archived.md"
        if stub_rel != expected:
            raise ArchiveError(f"stub location {stub_rel} does not match archive.original ({original}, {kind}); refusing")
        if not str(meta.get("path", "")).endswith("/" + op.as_posix()):
            raise ArchiveError("stub archive.path does not match archive.original; refusing")
        return vault / op
    # legacy stub (no explicit fields)
    if not stub_rel.endswith(".archived.md"):
        return stub
    sibling = stub_rel[: -len(".archived.md")]
    apath = "/" + str(meta.get("path", ""))
    is_inplace = apath.endswith("/" + stub_rel)
    is_sibling = apath.endswith("/" + sibling) and not sibling.lower().endswith(".md")
    if is_inplace == is_sibling:
        raise ArchiveError(f"legacy stub {stub.name} is ambiguous (markdown file or sibling stub); "
                           "refusing, restore manually from the archive path in the stub")
    return stub if is_inplace else vault / sibling


def cmd_restore(path: str, apply: bool, target: str | None) -> dict:
    p = Path(path).expanduser()
    if p.suffix == ".zip":
        return _restore_zip(p, apply, target)
    vault = resolved_vault()
    if not p.is_absolute():
        p = vault / p  # vault-relative, never CWD-relative (same form `move` accepts)
    # Resolve ONCE; every later read, copy and rename uses this absolute vault path.
    p = ensure_inside_vault(vault, p, must_exist=True)
    if not p.is_file():
        raise ArchiveError(f"not found: {p}")
    meta = parse_stub(p.read_text(encoding="utf-8", errors="replace"))
    if not meta:
        raise ArchiveError("not an archive stub (no status: archived / archive.sha256)")
    root = store_root(meta["store"])
    if root is None:
        raise ArchiveError(f"store '{meta['store']}' not found")
    arch = root / meta["path"]
    arch_root = (root / ARCHIVE_DIR).resolve()  # the stub is vault data: its path must stay inside the archive root
    if arch_root not in arch.resolve().parents:
        raise ArchiveError(f"stub archive.path leaves the archive root: {meta['path']}; refusing")
    if not arch.is_file():
        raise ArchiveError(f"archived file missing: {arch}")
    if sha256_file(arch) != meta["sha256"]:
        raise ArchiveError("archived file hash differs from stub; refusing")
    orig = _original_of_stub(vault, p, meta)
    orig = ensure_inside_vault(vault, orig, must_exist=False)
    kept = p.with_name(p.stem + ".restored.md")
    plan = {"archive": str(arch), "restore_to": str(orig), "stub_renamed_to": str(kept)}
    if orig != p and orig.exists():
        raise ArchiveError(f"original path already exists: {orig}")
    if kept.exists():
        raise ArchiveError(f"{kept} already exists")
    if not apply:
        return {"action": "dry-run", **plan}
    orig.parent.mkdir(parents=True, exist_ok=True)
    # Unique temp path allocated by mkstemp (O_EXCL): never a fixed name, so a
    # pre-existing file can never be overwritten or moved. Only this temp is cleaned.
    fd, tmp = tempfile.mkstemp(dir=orig.parent, prefix=".tmp-restore-")
    try:
        with os.fdopen(fd, "wb") as out, open(arch, "rb") as inp:
            shutil.copyfileobj(inp, out, 1 << 20)
            out.flush()
            os.fsync(out.fileno())
        if sha256_file(Path(tmp)) != meta["sha256"]:
            raise ArchiveError("hash mismatch after restore copy; nothing changed")
        os.replace(p, kept)
        os.replace(tmp, orig)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return {"action": "restored", **plan}


def _restore_zip(z: Path, apply: bool, target: str | None) -> dict:
    if not z.is_file():
        raise ArchiveError(f"not found: {z}")
    with zipfile.ZipFile(z) as zf:
        bad = zf.testzip()
        if bad:
            raise ArchiveError(f"corrupt zip member: {bad}")
        names = [n for n in zf.namelist() if not n.endswith("/") and n != "manifest.json"]
        if not apply:
            return {"action": "dry-run", "zip": str(z), "file_count": len(names), "sample": names[:20]}
        if not target:
            raise ArchiveError("--target is required with --apply")
        tdir = Path(target).expanduser().resolve()
        live = vault_root().resolve()
        if tdir == live or live in tdir.parents or tdir in live.parents:
            raise ArchiveError("target must not be, contain, or live inside the live vault")
        for n in names:
            dest = (tdir / n).resolve()
            if tdir not in dest.parents:
                raise ArchiveError(f"unsafe path in zip: {n}")
            if dest.exists():
                raise ArchiveError(f"would overwrite existing file: {dest}")
        for n in names:
            dest = tdir / n
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(n) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)
    return {"action": "restored", "zip": str(z), "target": str(tdir), "file_count": len(names)}


# ---------- status ----------
def last_backup(root: Path) -> str | None:
    zips = sorted((root / BACKUP_DIR).glob("maeng-*.zip")) if (root / BACKUP_DIR).is_dir() else []
    return zips[-1].name if zips else None


def cmd_status() -> dict:
    out = {"vault": {"path": str(vault_root()), "found": vault_root().is_dir()}, "stores": {}}
    for s in STORES:
        root = store_root(s)
        if root is None:
            out["stores"][s] = {"found": False}
        else:
            out["stores"][s] = {"found": True, "root": str(root),
                                "free_bytes": shutil.disk_usage(root).free, "last_backup": last_backup(root)}
    return out


def print_status(st: dict) -> None:
    print(f"vault: {st['vault']['path']} ({'found' if st['vault']['found'] else 'missing'})")
    for s, v in st["stores"].items():
        if not v["found"]:
            print(f"{s}: missing")
        else:
            print(f"{s}: found {v['root']}  free={v['free_bytes'] / 1e9:.1f} GB  last_backup={v['last_backup'] or 'none'}")


# ---------- CLI ----------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="archive.py", description=__doc__)
    ap.add_argument("--json", action="store_true", help="JSON output")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    m = sub.add_parser("move")
    m.add_argument("path")
    m.add_argument("--store", choices=STORES, default="onedrive")
    m.add_argument("--world", choices=("personal", "eta"), default="personal")
    m.add_argument("--dry-run", action="store_true")
    b = sub.add_parser("backup")
    b.add_argument("--to", default="onedrive,gdrive")
    b.add_argument("--keep", type=int, default=10)
    b.add_argument("--dry-run", action="store_true")
    r = sub.add_parser("restore")
    r.add_argument("path")
    r.add_argument("--apply", action="store_true")
    r.add_argument("--target")
    for sp in sub.choices.values():
        sp.add_argument("--json", action="store_true", dest="json2")
    a = ap.parse_args(argv)
    as_json = a.json or getattr(a, "json2", False)
    try:
        if a.cmd == "status":
            res = cmd_status()
            if not as_json:
                print_status(res)
                return 0
        elif a.cmd == "move":
            res = cmd_move(a.path, a.store, a.world, a.dry_run)
        elif a.cmd == "backup":
            targets = [t.strip() for t in a.to.split(",") if t.strip()]
            for t in targets:
                if t not in STORES:
                    raise ArchiveError(f"unknown store: {t}")
            res = cmd_backup(targets, a.keep, a.dry_run)
        else:
            res = cmd_restore(a.path, a.apply, a.target)
    except (ArchiveError, OSError) as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False) if as_json else f"error: {e}", file=sys.stderr)
        return 1
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if a.cmd == "backup" and not a.dry_run:
        stores = res.get("stores", {}).values()
        failed = any(v.get("status") == "failed" for v in stores)
        if failed or not any(v.get("status") == "ok" for v in stores):
            print("error: backup incomplete: a requested store failed or no store succeeded", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
