"""Small shared helpers: paths, atomic JSON files, git subprocess wrapper."""
import fcntl
import hashlib
import json
import os
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path


def home_dir():
    return Path(os.environ.get("MAENG_HOME") or Path.home() / ".local/share/maeng-harness")


def cache_dir():
    return Path(os.environ.get("MAENG_CACHE_DIR") or Path.home() / ".cache/maeng-harness")


def vault_dir():
    return Path(os.environ.get("MAENG_VAULT") or Path.home() / "Documents/Obsidian Vault")


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256(text):
    if isinstance(text, str):
        text = text.encode()
    return hashlib.sha256(text).hexdigest()


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_json(path, default=None):
    """Return parsed JSON; `default` when the file is missing. Raises on corrupt files."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return default
    return json.loads(text)


def write_json(path, obj):
    atomic_write(path, json.dumps(obj, indent=2, sort_keys=True) + "\n")


@contextmanager
def locked(path):
    """Exclusive advisory lock on `<path>.lock`."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path) + ".lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def git(cwd, *args, env=None, timeout=20, input_text=None):
    """Run git; returns (returncode, stdout, stderr). Never raises on failure."""
    full_env = dict(os.environ)
    full_env.update({"GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"})
    for var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        full_env.pop(var, None)
    if env:
        full_env.update(env)
    try:
        proc = subprocess.run(["git", *args], cwd=str(cwd), env=full_env, capture_output=True,
                              text=True, timeout=timeout, input=input_text)
    except (OSError, subprocess.SubprocessError) as exc:
        return 255, "", str(exc)
    return proc.returncode, proc.stdout, proc.stderr


def git_out(cwd, *args, **kw):
    rc, out, _ = git(cwd, *args, **kw)
    return out.strip() if rc == 0 else None
