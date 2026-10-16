"""World classification: personal | eta | unknown (fail closed)."""
import json
import os
import re
from pathlib import Path

from .common import cache_dir, git, read_json, write_json

PERSONAL, ETA, UNKNOWN = "personal", "eta", "unknown"
ETA_SLUGS = {"maengseojun/eta_v1"}
ETA_ORGS = {"endix-foundation-v1"}
ETA_PLUGIN = "eta-rules@eta"

_URL_PATTERNS = (
    re.compile(r"^(?:https?|ssh|git)://(?:[^@/]+@)?[^/]+/([^/]+)/([^/]+?)(?:\.git)?/?$"),
    re.compile(r"^(?:[^@/]+@)?[^:/]+:([^/]+)/([^/]+?)(?:\.git)?/?$"),
    re.compile(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?$"),
)


def eta_root():
    return Path(os.environ.get("MAENG_ETA_ROOT") or Path.home() / "Documents/Project/eta_v1")


def parse_remote(url):
    """Return (owner, name) for a GitHub-style URL or owner/name slug, else None."""
    url = (url or "").strip()
    for pat in _URL_PATTERNS:
        m = pat.match(url)
        if m:
            return m.group(1), m.group(2)
    return None


def normalize_repo(url):
    """Canonical repository identity: `host/owner/name` for network URLs, a resolved path for local ones."""
    url = (url or "").strip()
    if not url:
        return None
    if url.startswith(("/", "~", "file://", ".")):
        try:
            return str(Path(url.replace("file://", "", 1)).expanduser().resolve())
        except OSError:
            return url
    m = (re.match(r"^(?:https?|ssh|git)://(?:[^@/]+@)?([^/:]+)(?::\d+)?/(.+?)(?:\.git)?/?$", url)
         or re.match(r"^(?:[^@/]+@)?([^:/]+):(.+?)(?:\.git)?/?$", url))
    if m:
        return f"{m.group(1).lower()}/{m.group(2).lower()}"
    if re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?(?:\.git)?$", url):
        return "github.com/" + re.sub(r"\.git$", "", url).lower()
    return url


def remote_is_eta(url):
    if url and (url.startswith(("/", "~")) or url.startswith("file://")):
        try:
            return _under(Path(url.replace("file://", "")).expanduser().resolve(), eta_root())
        except OSError:
            return False
    parsed = parse_remote(url)
    if not parsed:
        return False
    owner, name = (parsed[0].lower(), parsed[1].lower())
    return owner in ETA_ORGS or f"{owner}/{name}" in ETA_SLUGS


def _under(path, root):
    try:
        path.relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _nearest_dir(path):
    p = Path(path).expanduser()
    p = p if p.is_absolute() else Path.cwd() / p
    while not p.exists():
        if p.parent == p:
            return None
        p = p.parent
    p = p.resolve()
    return p if p.is_dir() else p.parent


def _settings_files(top):
    d = Path(top) / ".claude"
    if not d.is_dir():
        return []
    files = sorted(d.glob("settings*.json"), key=lambda f: (f.name == "settings.local.json", f.name))
    return files


def _settings_say_eta(top):
    enabled = {}
    for f in _settings_files(top):
        data = json.loads(f.read_text(encoding="utf-8"))
        plugins = data.get("enabledPlugins", {}) if isinstance(data, dict) else {}
        if not isinstance(plugins, dict):
            raise ValueError("enabledPlugins must be an object")
        enabled.update(plugins)
    return enabled.get(ETA_PLUGIN) is True


def _stamp(files):
    out = []
    for f in files:
        try:
            st = Path(f).stat()
            out.append([str(f), st.st_mtime_ns, st.st_size])
        except OSError:
            pass
    return out


def _repo_paths(p):
    rc, out, err = git(p, "rev-parse", "--path-format=absolute", "--git-common-dir", "--git-dir", "--show-toplevel")
    if rc != 0:
        if "not a git repository" in err:
            return None
        raise RuntimeError(err.strip() or "git rev-parse failed")
    lines = out.split("\n")
    return lines[0], lines[1], lines[2]


def _origin_url(p):
    rc, out, err = git(p, "config", "--get", "remote.origin.url")
    if rc == 0:
        return out.strip()
    if rc == 1:
        return ""
    raise RuntimeError(err.strip() or "git config failed")


def _cache_load():
    try:
        return read_json(cache_dir() / "guard.json", {}) or {}
    except (ValueError, OSError):
        return {}


def _cache_save(cache):
    try:
        write_json(cache_dir() / "guard.json", cache)
    except OSError:
        pass


def _classify_repo(p, paths):
    common, gitdir, top = paths
    files = [Path(common) / "config", Path(gitdir) / "config.worktree", *_settings_files(top)]
    key = _stamp(files)
    cache = _cache_load()
    hit = cache.get(top)
    if hit and hit.get("key") == key:
        return hit["result"]
    result = ETA if remote_is_eta(_origin_url(p)) or _settings_say_eta(top) else PERSONAL
    cache[top] = {"key": key, "result": result}
    _cache_save(cache)
    return result


def _classify(path):
    p = _nearest_dir(path)
    if p is None:
        return UNKNOWN
    if _under(p, eta_root()):
        return ETA
    paths = _repo_paths(p)
    if paths is None:
        for parent in [p, *p.parents]:
            if _settings_files(parent) and _settings_say_eta(parent):
                return ETA
        return PERSONAL
    return _classify_repo(p, paths)


def classify(path):
    """Never raises: any failure to decide is `unknown`."""
    try:
        return _classify(path)
    except Exception:
        return UNKNOWN


def eta_checkouts():
    """eta root, its linked worktrees, and dev/contracts, dev/web."""
    root = eta_root()
    found = []
    if not root.exists():
        return found
    found.append(root)
    rc, out, _ = git(root, "worktree", "list", "--porcelain")
    if rc == 0:
        found += [Path(l[9:]) for l in out.splitlines() if l.startswith("worktree ")]
    found += [root / "dev/contracts", root / "dev/web"]
    seen, result = set(), []
    for p in found:
        if p.exists() and str(p.resolve()) not in seen:
            seen.add(str(p.resolve()))
            result.append(p)
    return result


ISOLATION_KEYS = ("maeng-harness@maeng", "linear@synced", "commit-commands@claude-plugins-official")


def isolation_missing(checkout):
    try:
        data = read_json(Path(checkout) / ".claude/settings.local.json", {}) or {}
        plugins = data.get("enabledPlugins", {})
        return any(plugins.get(k) is not False for k in ISOLATION_KEYS)
    except (ValueError, AttributeError):
        return True
