#!/usr/bin/env python3
"""Store one binary at Drive vault-offload/<vault-relative path> instead of the vault; print its file:// URL.

Usage: vault_drive.py <vault-relative path> <source file> [--drive <root>]
Same steps as ~/Documents/maeng-harness/vault-maint/offload.py: copy, sha256 check, manifest-<stamp>.json.
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath
from urllib.parse import quote

DRIVE_ROOT = Path.home() / "Library/CloudStorage/GoogleDrive-2025131619@korea.ac.kr/내 드라이브/maeng-archive/vault-offload"
# Same set as offload.py's BINARY, so the weekly sweep and this helper agree.
BINARY = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".gz", ".xz", ".tar",
          ".mp4", ".mov", ".pptx", ".docx", ".xlsx", ".hwp"}


def is_binary(name):
    return PurePosixPath(name).suffix.lower() in BINARY


def file_url(path):
    return "file://" + quote(str(path))


def store(relative, data, drive=DRIVE_ROOT):
    """Write data to <drive>/<relative> (immutable), verify sha256, write a manifest; return the file:// URL."""
    rel = PurePosixPath(relative)
    if rel.is_absolute() or not rel.parts or any(p in ("", ".", "..") for p in rel.parts):
        raise ValueError(f"vault-relative path required: {relative}")
    drive = Path(drive).resolve()  # a file:// URL needs an absolute path
    if not drive.is_dir():
        raise FileNotFoundError(f"Drive vault-offload is not available, nothing written: {drive}")
    digest = hashlib.sha256(data).hexdigest()
    dst = drive / Path(*rel.parts)
    # Check every existing component before mkdir, so a symlink cannot make us create folders outside Drive.
    if any((drive / Path(*rel.parts[:i])).is_symlink() for i in range(1, len(rel.parts) + 1)):
        raise ValueError(f"destination leaves the Drive root through a symlink: {relative}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if hashlib.sha256(dst.read_bytes()).hexdigest() != digest:
            raise FileExistsError(f"refusing to replace a different Drive file: {dst}")
    else:
        fd, tmp = tempfile.mkstemp(prefix=".vault-drive-", dir=dst.parent)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.link(tmp, dst)
        finally:
            os.unlink(tmp)
        if hashlib.sha256(dst.read_bytes()).hexdigest() != digest:
            raise OSError(f"hash mismatch after copy: {dst}")
    entry = [{"path": rel.as_posix(), "sha256": digest, "bytes": len(data), "drive": str(dst)}]
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = hashlib.sha256(f"{rel.as_posix()}\0{digest}".encode()).hexdigest()[:12]
    try:
        with open(drive / f"manifest-{stamp}-{name}.json", "x", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False, indent=1)
    except FileExistsError:
        pass  # same path and bytes already recorded this second
    return file_url(dst)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("relative")
    parser.add_argument("source")
    parser.add_argument("--drive", default=str(DRIVE_ROOT))
    args = parser.parse_args()
    try:
        print(store(args.relative, Path(args.source).read_bytes(), args.drive))
    except (OSError, ValueError) as exc:
        print(f"vault_drive: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
