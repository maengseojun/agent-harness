"""Tree ids and verification-relevant path diffs."""
import fnmatch
import os
import re
import shutil
import tempfile
from pathlib import Path

from .common import git, git_out, read_json

DEFAULT_NON_CODE = ["**/*.md", "docs/**", "**/*.png", "**/*.jpg", "**/*.jpeg", "**/*.gif", "**/*.svg", "**/*.webp"]
ALWAYS_RELEVANT = [
    "requirements*.txt", "constraints*.txt", "CMakeLists.txt", "*.cmake", "package-lock.json", "yarn.lock",
    "pnpm-lock.yaml", "poetry.lock", "Cargo.lock", "go.sum", "uv.lock", "Pipfile.lock", "Gemfile.lock",
    "pyproject.toml", "setup.cfg", "setup.py", "tox.ini", "Makefile", "package.json", "tsconfig*.json",
    "foundry.toml", "Cargo.toml", "go.mod", ".eslintrc*", "ruff.toml", "mypy.ini", "pytest.ini", "Dockerfile",
]


def toplevel(cwd):
    return git_out(cwd, "rev-parse", "--show-toplevel")


def common_dir(cwd):
    return git_out(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")


def glob_regex(pattern):
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"; i += 3
        elif pattern.startswith("**", i):
            out += ".*"; i += 2
        elif pattern[i] == "*":
            out += "[^/]*"; i += 1
        elif pattern[i] == "?":
            out += "[^/]"; i += 1
        elif pattern[i] == "{":
            j = pattern.index("}", i)
            out += "(?:" + "|".join(re.escape(a) for a in pattern[i + 1:j].split(",")) + ")"
            i = j + 1
        else:
            out += re.escape(pattern[i]); i += 1
    return re.compile("^" + out + "$")


def _str_list(value):
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def load_policy(top):
    """`.maeng/verify.json`: non_code_globs, required, protected_branches, formatter.

    A missing file gives the defaults. A file that exists but is unreadable, not JSON, not an object, or has
    wrongly typed fields gives the defaults plus `invalid` (a reason): shipping is denied until it is fixed."""
    policy = {"non_code_globs": DEFAULT_NON_CODE, "required": [], "protected_branches": [], "formatter": None,
              "invalid": None}
    path = Path(top) / ".maeng/verify.json"
    try:
        data = read_json(path, None)
    except (OSError, ValueError) as exc:
        policy["invalid"] = f"{path} is unreadable or not valid JSON ({type(exc).__name__})"
        return policy
    if data is None and not path.exists():
        return policy
    if not isinstance(data, dict):
        policy["invalid"] = f"{path} must contain a JSON object"
        return policy
    bad = [k for k in ("non_code_globs", "required", "protected_branches") if k in data and not _str_list(data[k])]
    if "formatter" in data and data["formatter"] is not None and not _str_list(data["formatter"]):
        bad.append("formatter")
    if bad:
        policy["invalid"] = f"{path}: invalid field(s) " + ", ".join(bad)
        return policy
    for k in ("non_code_globs", "required", "protected_branches", "formatter"):
        if k in data:
            policy[k] = data[k]
    return policy


def is_relevant(path, policy):
    base = os.path.basename(path)
    if any(fnmatch.fnmatch(base, pat) for pat in ALWAYS_RELEVANT):
        return True
    return not any(glob_regex(g).match(path) for g in policy["non_code_globs"])


def dirty_submodules(top):
    rc, out, _ = git(top, "ls-files", "-s")
    dirty, commits = [], {}
    if rc != 0:
        return ["<ls-files failed>"], {}
    for line in out.splitlines():
        meta, _, name = line.partition("\t")
        if not meta.startswith("160000"):
            continue
        sub = Path(top) / name
        if not (sub / ".git").exists():
            continue
        rc2, status, _ = git(sub, "status", "--porcelain")
        if rc2 != 0 or status.strip():
            dirty.append(name)
        commits[name] = git_out(sub, "rev-parse", "HEAD")
    return dirty, commits


def _seed_index(top, idx, env):
    """Copy the repo's index to `idx` so `git add -A` rehashes only changed files (MAE-284: an empty index rehashed
    every file, 7.8s cold). False, with `idx` absent, when there is no readable index or an entry is assume-unchanged
    or skip-worktree: git would not look at those files, so a change could hide from the tree id. copy2 keeps the
    index mtime, which git's racy-clean check compares entries against; a fresh mtime lets a same-size edit pass."""
    real = git_out(top, "rev-parse", "--path-format=absolute", "--git-path", "index")
    try:
        shutil.copy2(real, idx)
    except (TypeError, OSError):
        return False
    rc, out, _ = git(top, "ls-files", "-v", env=env)
    if rc == 0 and not re.search(r"^(?:[a-z]|S) ", out, re.M):
        return True
    os.remove(idx)
    return False


def tree_id(cwd):
    """(tree_sha | None, info). None when not a repo, git fails, or a submodule is dirty."""
    top = toplevel(cwd)
    if not top:
        return None, {"reason": "not a git repo"}
    dirty, commits = dirty_submodules(top)
    if dirty:
        return None, {"reason": "dirty submodule: " + ", ".join(dirty)}
    with tempfile.TemporaryDirectory(prefix="maeng-idx-") as d:
        env = {"GIT_INDEX_FILE": os.path.join(d, "index")}
        seeded = _seed_index(top, env["GIT_INDEX_FILE"], env)
        if not seeded and git(top, "rev-parse", "--verify", "-q", "HEAD")[0] == 0:
            if git(top, "read-tree", "HEAD", env=env)[0] != 0:
                return None, {"reason": "read-tree failed"}
        if git(top, "add", "-A", env=env, timeout=60)[0] != 0:
            return None, {"reason": "git add -A failed"}
        rc, out, _ = git(top, "write-tree", env=env)
    if rc != 0:
        return None, {"reason": "write-tree failed"}
    return out.strip(), {"submodules": commits}


def commit_tree(cwd, rev):
    return git_out(cwd, "rev-parse", "--verify", "-q", rev + "^{tree}")


def changed_paths(top, a, b):
    if a == b:
        return []
    rc, out, _ = git(top, "diff-tree", "-r", "--name-only", "-z", "--no-renames", a, b)
    if rc != 0:
        return None
    return [p for p in out.split("\0") if p]


def relevant_diff(top, a, b, policy=None):
    """Relevant paths that differ between trees; None when undecidable (treat as different)."""
    paths = changed_paths(top, a, b)
    if paths is None:
        return None
    policy = policy or load_policy(top)
    return [p for p in paths if is_relevant(p, policy)]


def relevant_equal(top, a, b, policy=None):
    if not a or not b:
        return False
    return relevant_diff(top, a, b, policy) == []
