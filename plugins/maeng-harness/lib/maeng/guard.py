"""World classification: personal | eta | unknown (fail closed)."""
import json
import os
import re
from pathlib import Path

from .common import cache_dir, git, read_json, write_json

PERSONAL, ETA, UNKNOWN = "personal", "eta", "unknown"
ETA_SLUGS = {"maengseojun/eta_v1"}
# Single source of truth for the eta world: every checkout of a repo under these orgs (or slugs) is eta.
ETA_ORGS = {"endix-foundation-v1", "endix-labs-v1"}
ETA_PLUGIN = "eta-rules@eta"
ETA_PLUGINS = ("eta-rules@eta", "eta-craft@eta")

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


def spec_is_eta(text):
    """Generous eta test for any repo spec (slug, URL, host/owner/name, API path): deny on any eta mention."""
    low = (text or "").lower()
    if any(org in low for org in ETA_ORGS) or any(slug in low for slug in ETA_SLUGS):
        return True
    return remote_is_eta(text)


def _under(path, root):
    try:
        path.relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _nearest_dir(path):
    p = Path(path).expanduser()
    p = p if p.is_absolute() else Path.cwd() / p
    p = Path(os.path.realpath(p))  # follow symlinks (also dangling ones) before classifying
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


SKIP_DIRS = {"_to_delete", "node_modules", ".git", ".venv", "__pycache__"}
SETTINGS_REL = ".claude/settings.local.json"
ISOLATION_KEYS = ("maeng-harness@maeng", "linear@synced", "commit-commands@claude-plugins-official")
DESIRED_PLUGINS = {**{k: False for k in ISOLATION_KEYS}, **{k: True for k in ETA_PLUGINS}}


def _walk_checkouts(root, max_depth=None):
    """Yield directories under `root` that hold a `.git` entry (repos, linked worktrees, submodules)."""
    root = Path(root)
    base = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        depth = len(Path(dirpath).parts) - base
        if ".git" in dirnames or ".git" in filenames:
            yield Path(dirpath)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not os.path.islink(os.path.join(dirpath, d))]
        if max_depth is not None and depth >= max_depth:
            dirnames[:] = []


def _is_submodule(p):
    rc, out, _ = git(p, "rev-parse", "--show-superproject-working-tree")
    return rc == 0 and bool(out.strip())


def _worktrees(p):
    if (Path(p) / ".git").is_file():      # a linked worktree (or submodule): its main repo lists it
        return []
    rc, out, _ = git(p, "worktree", "list", "--porcelain")
    if rc != 0:
        return []
    return [Path(l[9:]) for l in out.splitlines() if l.startswith("worktree ")]


def checkout_origin_is_eta(p):
    try:
        return remote_is_eta(_origin_url(p))
    except Exception:
        return False


def discover_checkouts(scan_roots=(), root=None):
    """Every eta checkout: the eta_v1 folder, each git repo and linked worktree under it (walk, skipping
    _to_delete/node_modules/.git/submodules), plus checkouts under `scan_roots` (depth <= 4) whose origin org is eta.
    -> list of Path, de-duplicated."""
    root = Path(root) if root else eta_root()
    found = []
    if root.is_dir():
        found.append(root)
        for co in _walk_checkouts(root):
            if not _is_submodule(co):
                found.append(co)
                found += _worktrees(co)
    for sr in scan_roots:
        sr = Path(sr).expanduser()
        if not sr.is_dir():
            continue
        for co in _walk_checkouts(sr, max_depth=4):
            if _is_submodule(co) or not checkout_origin_is_eta(co):
                continue
            found.append(co)
            found += _worktrees(co)
    seen, result = set(), []
    for p in found:
        if p.exists() and str(p.resolve()) not in seen:
            seen.add(str(p.resolve()))
            result.append(p)
    return result


def eta_checkouts():
    return discover_checkouts()


def project_root(path):
    """The directory Claude uses as project root for `path`: git toplevel, else the eta folder, else the dir itself."""
    p = _nearest_dir(path)
    if p is None:
        return None
    paths = _repo_paths(p)
    if paths:
        return Path(paths[2])
    return eta_root() if _under(p, eta_root()) else p


def isolation_missing(checkout):
    """True when the checkout's local settings lack the maeng-harness disables or the eta enables."""
    try:
        data = read_json(Path(checkout) / SETTINGS_REL, {}) or {}
        plugins = data.get("enabledPlugins", {})
        return any(plugins.get(k) is not v for k, v in DESIRED_PLUGINS.items())
    except (ValueError, AttributeError):
        return True
