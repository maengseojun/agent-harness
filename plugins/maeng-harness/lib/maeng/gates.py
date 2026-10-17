"""PreToolUse gates. G1 code-ship, G2 Notion publish, G3 cross-world (eta)."""
import os
import re
import subprocess
from pathlib import Path

from . import canon, ghcmd, guard, receipts, remotecfg
from . import tree as treelib
from .common import canonical, git, git_out, home_dir, read_json, sha256
from .evidence import Verifier
from .ghcmd import classify_gh, parse_gh  # noqa: F401  (re-exported)
from .shellparse import ENV_ASSIGN, ParseError, RISKY, program, split_segments

SHA_RE = canon.SHA_RE
LEASE_RE = canon.LEASE_RE
_parse_git_globals = canon.parse_git_globals
DEFAULT_BRANCHES = {"main", "master", "trunk"}
WRITE_VERBS = ("get_", "list_", "search_", "read_", "fetch_", "find_", "query_")


class Decision:
    def __init__(self, allow=True, reason="", effects=None):
        self.allow, self.reason, self.effects = allow, reason, effects or []


def deny(reason):
    return Decision(False, reason)


class Ctx:
    def __init__(self, cwd, state, world=guard.PERSONAL, home=None):
        self.cwd, self.state, self.world = cwd, state, world
        self.world_cache = {}

    @property
    def unknown(self):
        return self.world == guard.UNKNOWN


UNKNOWN_REASON = ("maeng guard: cannot classify this checkout (personal vs eta), so mutating code/ship "
                  "operations are denied. Fix the repo config (git config / .claude/settings*.json) or open the "
                  "session in a resolvable directory.")


# ---- helpers -------------------------------------------------------------

def _abs(path, cwd):
    p = Path(os.path.expanduser(path))
    return str(p if p.is_absolute() else Path(cwd) / p)


def is_default_branch(branch, cwd, remote, policy):
    if branch in DEFAULT_BRANCHES or branch in (policy.get("protected_branches") or []):
        return True
    return bool(remote) and remotecfg.default_head(cwd, remote) == branch


def _binding_rev(ctx):
    b = ctx.state.get("binding")
    return (b or {}).get("plan_updated_at")


def verified_commit(ctx, cwd, commit):
    """(ok, reasons) that the commit's tree is ship-verified for the session."""
    tree = treelib.commit_tree(cwd, commit)
    top, common = treelib.toplevel(cwd), treelib.common_dir(cwd)
    if not (tree and top and common):
        return False, ["cannot resolve the commit tree"]
    return Verifier(ctx.state, top, common).ship_verified(tree)


def _verify_or_deny(ctx, cwd, commit, what):
    ok, reasons = verified_commit(ctx, cwd, commit)
    if ok:
        return None
    return deny(f"maeng G1: {what} tree is not ship-verified ({'; '.join(reasons)}). Run the required checks on this "
                f"exact tree (maeng-verify status shows what is missing).")


# ---- G3 local ------------------------------------------------------------

READONLY_PROGS = {"cat", "ls", "head", "tail", "grep", "rg", "find", "wc", "stat", "file", "diff", "less", "more",
                  "echo", "pwd", "which", "test", "[", "du", "df", "tree", "realpath", "dirname", "basename", "cd",
                  "pushd", "popd", "true", "false", "sort", "uniq", "cut", "tr", "printf", "env", "date", "jq",
                  "sha256sum", "shasum", "md5", "readlink"}
READONLY_GIT = {"status", "log", "diff", "show", "rev-parse", "ls-files", "ls-tree", "cat-file", "blame", "describe",
                "grep", "shortlog", "rev-list", "name-rev", "merge-base", "ls-remote", "check-ignore"}


def _target_world(path):
    return guard.classify(path)


def g3_path(path, cwd, ctx, what):
    w = _target_world(_abs(path, cwd))
    if w == guard.ETA:
        return deny(f"maeng G3: {what} targets an eta checkout ({path}); eta is a separate world. "
                    f"Read-only access is allowed; do eta work in an eta session.")
    if w == guard.UNKNOWN:
        return deny(UNKNOWN_REASON)
    return None


def g3_edit(tool_name, tool_input, ctx):
    path = tool_input.get("file_path") or tool_input.get("notebook_path") or tool_input.get("path")
    if not path:
        return Decision()
    cwd = ctx.cwd
    return g3_path(path, cwd, ctx, tool_name) or Decision()


# ---- G1/G3 Bash ----------------------------------------------------------

GIT_RETARGET = re.compile(r"^(?:GIT_DIR|GIT_WORK_TREE|GIT_COMMON_DIR)=")


def check_bash(command, ctx):
    """Allowlist gate: a command that mentions a shipping route must be exactly one canonical form."""
    command = command.rstrip()
    try:
        segs = split_segments(command)
    except ParseError:
        return deny(canon.message("it cannot be parsed")) if RISKY.search(command) else Decision()
    if canon.route_mentions(segs, command):
        form, why = canon.canonical_command(command, segs)
        if not form:
            return deny(canon.message(why))
    if any(os.path.basename(t) == "git" for s in segs for t in s.tokens) and \
            any(GIT_RETARGET.match(t) for s in segs for t in s.tokens):
        return deny("maeng G3: GIT_DIR/GIT_WORK_TREE retarget git and cannot be checked; run git without them "
                    "(use `git -C <dir>` for another checkout).")
    cwd, effects = ctx.cwd, []
    for seg in segs:
        d, cwd = check_segment(seg, cwd, ctx)
        if not d.allow:
            return d
        effects += d.effects
    return Decision(True, "", effects)


def _cwd_gate(cwd, ctx, prog, mutating):
    """Mutating segments need a classifiable personal directory: eta may only be read, unknown is denied."""
    if not mutating:
        return None
    if ctx.unknown:
        return deny(UNKNOWN_REASON)
    w = guard.classify(cwd)
    if w == guard.ETA:
        return deny(f"maeng G3: `{prog}` would run inside an eta checkout ({cwd}); only read-only commands are allowed there.")
    if w == guard.UNKNOWN:
        return deny(UNKNOWN_REASON)
    return None


FIND_MUTATING = {"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf", "-fls"}
ALWAYS_MUTATING = {"cp", "mv", "rm", "touch", "mkdir", "ln", "chmod", "chown", "truncate", "dd", "xargs", "tee",
                   "sed", "awk", "gawk", "install", "rmdir", "rsync", "patch"}


def mutating_options(prog, toks):
    """Read-only-looking executables become mutating when they carry write options."""
    args = toks[1:]
    if prog in ALWAYS_MUTATING:
        return True
    if prog == "find":
        return any(t in FIND_MUTATING for t in args)
    if prog == "sort":
        return any(t == "--output" or t.startswith("--output=") or re.match(r"^-[A-Za-z]*o", t) for t in args)
    if prog == "tree":
        return any(t == "-o" or re.match(r"^-[A-Za-z]*o$", t) for t in args)
    if prog == "uniq":
        return len([t for t in args if not t.startswith("-")]) >= 2
    if prog == "date":
        return any(t in ("-s", "--set") or t.startswith("--set=") for t in args)
    return False


def git_readonly(sub, args):
    if sub in READONLY_GIT:
        return not any(a == "--output" or a.startswith("--output=") for a in args)
    if sub == "branch":
        return bool(args) and all(a in ("--list", "-l", "-a", "-r", "--all", "--remotes", "--show-current", "-v", "-vv")
                                  for a in args)
    if sub == "remote":
        return all(a in ("-v", "--verbose") for a in args)
    if sub == "config":
        return bool(args) and (args[0].startswith("--get") or args[0] in ("--list", "-l"))
    return False


# ---- G3 token taint ---------------------------------------------------------
#
# In a personal session every token of every Bash segment (program, options, option values, key=value values,
# redirect targets, bare operands) is resolved against the segment's effective directory, and slugs / github.com
# URLs are classified; a segment with any tainted token is denied unless it is a read-only invocation from the
# closed allowlist (READONLY_PROGS without mutating options, read-only git subcommands, strict read-only gh).

SLUG_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?(?:\.git)?$")
SCP_RE = re.compile(r"^[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+:[A-Za-z0-9_.~/-]+$")
GLOB_CUT = re.compile(r"[*?\[{]")


def _variants(tok):
    """The token itself plus the path-like values hidden inside it: `--dir=X`, `key=value`, `-DX`, `a:b`."""
    out = [tok]
    if "=" in tok:
        out.append(tok.split("=", 1)[1])
    m = re.match(r"^-[A-Za-z]([^=].*)$", tok)
    if m:
        out.append(m.group(1))
    for v in list(out):
        if ":" in v and "://" not in v:
            out += [part for part in v.split(":") if part]
    return out


def _resolvable(path):
    return bool(path) and "\n" not in path and "\0" not in path and len(path) < 4096 and \
        all(len(c) < 255 for c in path.split("/"))


def world_of_path(path, cwd, ctx):
    """World of a path-like token resolved against `cwd` (memoized by nearest existing directory)."""
    expanded = os.path.expandvars(path)
    m = GLOB_CUT.search(expanded)
    if m:
        expanded = expanded[:m.start()] or "."
    if not _resolvable(expanded):
        return guard.PERSONAL
    absolute = _abs(expanded, cwd)
    parts = absolute.split("/")
    if ".git" in parts:  # a path inside a .git directory belongs to the repository that owns it
        absolute = "/".join(parts[:parts.index(".git")]) or "/"
    try:
        near = guard._nearest_dir(absolute)
    except (OSError, ValueError):
        near = None
    key = str(near) if near is not None else absolute
    cache = ctx.world_cache
    if key not in cache:
        cache[key] = guard.classify(absolute if near is None else str(near))
    return cache[key]


def token_taint(seg, cwd, ctx):
    """-> the first reason a token of this segment is eta/unknown tainted, or None."""
    for tok in seg.tokens:
        for v in _variants(tok):
            if not v or v == "-":
                continue
            # (b) repository identity: owner/repo slugs, github.com URLs, API paths
            m = ghcmd.URL_REPO.search(v) or ghcmd.API_REPO.match(v)
            if m and guard.spec_is_eta(f"{m.group(1)}/{m.group(2)}"):
                return f"`{tok}` names an eta repository"
            if (SLUG_RE.match(v) or SCP_RE.match(v)) and guard.spec_is_eta(v):
                return f"`{tok}` names an eta repository"
            if v.startswith("-"):
                continue
            # (a) filesystem path relative to the effective directory
            w = world_of_path(v, cwd, ctx)
            if w == guard.ETA:
                return f"`{tok}` resolves into an eta checkout"
            if w == guard.UNKNOWN:
                return f"`{tok}` resolves somewhere whose world cannot be determined"
    return None


def readonly_invocation(prog, toks):
    """True only for the closed read-only allowlist."""
    if not prog or prog in ("cd", "pushd", "popd"):
        return True
    if prog == "git":
        sub, args, _, _ = _parse_git_globals(toks)
        return sub is None or git_readonly(sub, args)
    if prog == "gh":
        return ghcmd.readonly_strict(toks)
    return prog in READONLY_PROGS and not mutating_options(prog, toks)


def check_taint(seg, prog, toks, cwd, ctx):
    """The G3 authority: deny a non-read-only segment that is tainted or runs in an eta/unknown directory."""
    if readonly_invocation(prog, toks):
        return None
    if ctx.unknown:
        return deny(UNKNOWN_REASON)
    w = world_of_path(".", cwd, ctx)
    if w == guard.ETA:
        return deny(f"maeng G3: `{prog}` would run inside an eta checkout ({cwd}); only read-only commands are allowed there.")
    if w == guard.UNKNOWN:
        return deny(UNKNOWN_REASON)
    why = token_taint(seg, cwd, ctx)
    if why:
        return deny(f"maeng G3: `{prog}` is not a read-only command and {why}; eta is a separate world "
                    f"(read-only access is allowed; do eta work in an eta session).")
    return None


def check_segment(seg, cwd, ctx):
    prog, toks = program(seg.tokens)
    for target in seg.redirects:  # every output target, relative to this segment's effective directory
        d = g3_path(target, cwd, ctx, "redirect")
        if d:
            return d, cwd
    if prog in ("cd", "pushd") and len(toks) > 1:
        return Decision(), _abs(toks[1], cwd)
    blocked = check_taint(seg, prog, toks, cwd, ctx)
    if blocked:
        return blocked, cwd
    if prog == "git":
        return check_git(toks, cwd, ctx), cwd
    if prog == "gh":
        return check_gh(toks, cwd, ctx), cwd
    if prog == "maeng-ship":
        return check_ship_cmd(toks, cwd, ctx), cwd
    return Decision(), cwd


def check_git(toks, cwd, ctx):
    sub, args, dirs, cfg = _parse_git_globals(toks)
    ro = git_readonly(sub, args)
    for kind, d in dirs:  # -C / --git-dir / --work-tree: resolve the target; eta or unknown cannot be mutated
        path = _abs(d, cwd)
        if kind == "C":
            cwd = path
        if not ro:
            if not os.path.exists(path):
                return deny(f"maeng G3: git {'-C' if kind == 'C' else '--' + kind} target {path} does not exist, so its "
                            f"world cannot be determined; denied.")
            probe = os.path.dirname(path) if kind == "git-dir" and os.path.basename(path.rstrip("/")) == ".git" else path
            blocked = g3_path(probe, cwd, ctx, f"git {'-C' if kind == 'C' else '--' + kind}")
            if blocked:
                return blocked
    if sub is None:
        return Decision()
    if not ro:
        blocked = _cwd_gate(cwd, ctx, "git " + sub, True)
        if blocked:
            return blocked
    if sub == "push":
        return check_push(toks, cwd, ctx)
    return Decision()


# ---- git push (canonical forms only) --------------------------------------

def _current_branch(cwd):
    return git_out(cwd, "symbolic-ref", "--short", "-q", "HEAD")


def check_push(toks, cwd, ctx):
    form, why = canon.parse_canonical_push(toks)
    if not form:
        return deny(canon.message(why))
    if form["form"] == "lease":
        return check_merge_push(form, cwd, ctx)
    remote, branch = form["remote"], form["branch"]
    url, err = remotecfg.plain_remote(cwd, remote)
    if err:
        return deny(err)
    policy = treelib.load_policy(treelib.toplevel(cwd) or cwd)
    if is_default_branch(branch, cwd, remote, policy):
        return deny(f"maeng G1: pushing to the default branch `{branch}` is denied. Open a PR and use "
                    f"`maeng-ship merge <PR>` (needs a matching review receipt).")
    src = form["src"]
    spec = src if form["src_kind"] == "sha" else "refs/heads/" + src
    commit = git_out(cwd, "rev-parse", "--verify", "-q", spec + "^{commit}")
    if not commit:
        return deny(f"maeng G1: cannot resolve source `{src}` to a commit.")
    d = _verify_or_deny(ctx, cwd, commit, f"pushed commit {commit[:8]} ({src} -> {branch})")
    return d or Decision()


def check_merge_push(lease, cwd, ctx):
    """The exact maeng-ship lease form: only with matching receipts covering the change, for this repository,
    and a verified head tree."""
    rev = _binding_rev(ctx)
    url, err = remotecfg.plain_remote(cwd, lease["remote"])
    if err:
        return deny(err)
    repo = guard.normalize_repo(url)
    recs, problem = receipts.find_code(cwd, repo, lease["base"], lease["head"], lease["ref"], rev)
    if not recs:
        return deny(f"maeng G1: merge push denied: {problem}. Use `maeng-review` then `maeng-ship merge <PR>`.")
    if git(cwd, "merge-base", "--is-ancestor", lease["base"], lease["head"])[0] != 0:
        return deny("maeng G1: merge push denied: base is not an ancestor of head (BEHIND). Update, re-verify, re-review.")
    d = _verify_or_deny(ctx, cwd, lease["head"], "reviewed head")
    if d:
        return d
    intent = {k: lease[k] for k in ("remote", "ref")}
    intent.update(base_sha=lease["base"], head_sha=lease["head"], repo=repo)
    return Decision(True, "", [("receipt_pending", rec["key"], intent) for rec in recs])


def check_ship_cmd(toks, cwd, ctx):
    form, _ = canon.parse_canonical_ship(toks)
    if not form:
        return Decision()  # no `merge`: nothing to ship (check_bash already enforced the canonical form)
    if ctx.unknown:
        return deny(UNKNOWN_REASON)
    _, err = remotecfg.plain_remote(cwd, form["remote"])
    return deny(err) if err else Decision()


def _ls_remote_sha(cwd, url, branch):
    """-> (sha | None, why). MAENG_GIT overrides the git binary (tests)."""
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")}
    env.update({"GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"})
    ref = f"refs/heads/{branch}"
    try:
        proc = subprocess.run([os.environ.get("MAENG_GIT", "git"), "ls-remote", url, ref], cwd=str(cwd), env=env,
                              capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)
    if proc.returncode != 0:
        return None, proc.stderr.strip()[:200] or f"ls-remote exited {proc.returncode}"
    for line in proc.stdout.splitlines():
        sha, _, name = line.partition("\t")
        if name.strip() == ref:
            return sha.strip(), ""
    return None, f"{ref} does not exist on the remote"


def check_pr_head(ctx, cwd, head, repo_spec, must_be_origin=False):
    """PR creation: the repository's REMOTE head must be a ship-verified commit (never a local branch by name)."""
    head = (head or "").strip() or _current_branch(cwd) or ""
    if not head:
        return deny("maeng G1: PR creation needs a resolvable head branch.")
    if ":" in head:
        return deny(f"maeng G1: cross-repository PR head `{head}` is not supported; push a branch of the target "
                    f"repository and open the PR from it.")
    if not canon.BRANCH_RE.match(head):
        return deny(f"maeng G1: `{head}` is not a plain branch name.")
    origin_url, err = remotecfg.plain_remote(cwd, "origin", for_push=False)
    if must_be_origin:
        if err:
            return deny(err)
        rid = guard.normalize_repo(repo_spec)
        _, raw, _ = git(cwd, "config", "--get", "remote.origin.url")
        if rid not in (guard.normalize_repo(origin_url), guard.normalize_repo(raw.strip())):
            return deny(f"maeng G1: `gh pr create --repo {repo_spec}` must name origin's repository "
                        f"({guard.normalize_repo(origin_url)}); the PR head is verified on origin only.")
        url = origin_url
    elif repo_spec:
        rid = guard.normalize_repo(repo_spec)
        url = origin_url if origin_url and guard.normalize_repo(origin_url) == rid else f"https://{rid}.git"
    elif err:
        return deny(err)
    else:
        url = origin_url
    sha, why = _ls_remote_sha(cwd, url, head)
    if not sha:
        return deny(f"maeng G1: cannot establish the remote head of `{head}` ({why}); push the verified branch "
                    f"first with a canonical `git push`.")
    d = _verify_or_deny(ctx, cwd, sha, f"remote PR head {sha[:8]} of `{head}`")
    return d or Decision()


# ---- gh ------------------------------------------------------------------

def check_gh(toks, cwd, ctx):
    kind, reason, repo, info = classify_gh(toks)
    if kind == "read":
        return Decision()
    if ctx.unknown:
        return deny(UNKNOWN_REASON)
    if kind == "deny":
        return deny(canon.message(reason))
    if kind == "local":  # reads from the remote but writes files locally: G3 on every local destination
        blocked = _cwd_gate(cwd, ctx, "gh " + " ".join(info["pos"][:2]), True)
        if blocked:
            return blocked
        for dest in ghcmd.local_destinations(info):
            blocked = g3_path(dest, cwd, ctx, f"`gh {' '.join(info['pos'][:2])}` destination")
            if blocked:
                return blocked
        return Decision()
    targets = ghcmd.target_repos(info)
    for t in targets:
        if guard.spec_is_eta(t):
            return deny(f"maeng G3: gh write targets eta repo `{t}`; eta is a separate world.")
    if not targets:
        blocked = _cwd_gate(cwd, ctx, "gh", True)
        if blocked:
            return blocked
    if kind == "create":
        parsed, why = ghcmd.parse_pr_create(toks)
        if not parsed:
            return deny(canon.message(why))
        if not (parsed["repo"] and ghcmd.REPO_RE.match(parsed["repo"])):
            return deny(canon.message("`gh pr create` needs an explicit `--repo <owner/repo>` equal to origin"))
        return check_pr_head(ctx, cwd, parsed["head"], parsed["repo"], must_be_origin=True)
    if info["pos"][:1] != ["api"] and not (info["repo"] and ghcmd.REPO_RE.match(info["repo"])):
        return deny(canon.message("gh writes need an explicit `-R <owner/repo>`"))
    return Decision()


# ---- MCP -----------------------------------------------------------------

def _is_read_tool(name):
    return name.startswith(WRITE_VERBS)


def check_mcp_github(tool, tool_input, ctx):
    name = tool.split("__", 2)[-1]
    if _is_read_tool(name):
        return Decision()
    if ctx.unknown:
        return deny(UNKNOWN_REASON)
    slug = f"{tool_input.get('owner', '')}/{tool_input.get('repo', '')}"
    if guard.spec_is_eta(slug):
        return deny(f"maeng G3: {name} targets eta repo `{slug}`; eta is a separate world.")
    if name in ("push_files", "create_or_update_file"):
        return deny(f"maeng G1: {name} is denied; its contents are never tied to the verified tree. Publish only "
                    f"through a verified `git commit` + `git push` of a feature branch.")
    if name in ("merge_pull_request", "update_pull_request_branch"):
        return deny(f"maeng G1: {name} is denied; merge only through `maeng-ship merge <PR>`.")
    cwd = ctx.cwd
    if name == "create_pull_request":
        return check_pr_head(ctx, cwd, str(tool_input.get("head", "")), slug)
    return Decision()


def check_mcp_eta_linear(tool, tool_input, ctx):
    name = tool.split("__", 2)[-1]
    if _is_read_tool(name):
        return Decision()
    return deny(f"maeng G3: `{name}` writes to eta Linear; eta records belong to the eta session.")


# ---- G2 Notion -----------------------------------------------------------

class NotionConfigError(Exception):
    pass


NOTION_ID_RE = re.compile(r"^[0-9a-f]{32}$")
NOTION_CONFIG_REASON = ("maeng G2: invalid Notion gate configuration ({why}); Notion create/update writes are denied "
                        "until MAENG_NOTION_DBS / $MAENG_HOME/config.json notion_databases / the shipped "
                        "config/notion-databases.json is a non-empty list of 32-hex Notion ids.")


def _nid(value):
    return receipts.nid(value)


def _valid_dbs(ids, source):
    if not isinstance(ids, list) or not ids:
        raise NotionConfigError(f"{source}: notion_databases must be a non-empty list")
    out = set()
    for i in ids:
        n = _nid(i) if isinstance(i, str) else ""
        if not NOTION_ID_RE.match(n):
            raise NotionConfigError(f"{source}: `{i}` is not a 32-hex Notion id")
        out.add(n)
    return out


def notion_dbs():
    """-> set of normalized protected database ids. Raises NotionConfigError when the chosen source is invalid or
    the shipped default is unreadable (the caller must deny)."""
    env = os.environ.get("MAENG_NOTION_DBS")
    if env:
        return _valid_dbs([p.strip() for p in env.split(",") if p.strip()], "MAENG_NOTION_DBS")
    user = home_dir() / "config.json"
    if user.exists():
        try:
            data = read_json(user, {})
        except (ValueError, OSError) as exc:
            raise NotionConfigError(f"{user}: unreadable ({exc})")
        if not isinstance(data, dict):
            raise NotionConfigError(f"{user}: must be a JSON object")
        if "notion_databases" in data:
            return _valid_dbs(data["notion_databases"], str(user))
    shipped = Path(__file__).resolve().parents[2] / "config" / "notion-databases.json"
    try:
        data = read_json(shipped, None)
    except (ValueError, OSError) as exc:
        raise NotionConfigError(f"shipped default unreadable ({exc})")
    if not isinstance(data, dict):
        raise NotionConfigError("shipped default missing or malformed")
    return _valid_dbs(data.get("notion_databases"), "shipped default")


def notion_scope(tool, tool_input):
    """-> (op, destination) when this call is G2-gated, else None."""
    name = tool.split("__", 2)[-1]
    if name not in ("notion-create-pages", "notion-update-page", "notion-update-data-source"):
        return None
    dbs = notion_dbs()  # may raise NotionConfigError: check_mcp_notion turns it into a deny
    if name == "notion-create-pages":
        parent = tool_input.get("parent") or {}
        dest = _nid(next((v for k, v in parent.items() if k.endswith("_id")), ""))
        return ("create", dest) if dest in dbs else None
    if name == "notion-update-page":
        pid = _nid(tool_input.get("page_id"))
        journaled = {_nid(i) for e in receipts.read_journal() for i in e["page_ids"]}
        return ("update", pid) if pid in receipts.registry_ids() | journaled else None
    if name == "notion-update-data-source":
        did = _nid(tool_input.get("data_source_id"))
        return ("update", did) if did in dbs else None
    return None


NOTION_WRITE = re.compile(r"^notion-(create|update|delete|move|duplicate|restore|upload|set-|send-|spawn|stop|convert)")


def check_mcp_notion(tool, tool_input, ctx, tool_use_id=""):
    if ctx.unknown and NOTION_WRITE.match(tool.split("__", 2)[-1]):
        return deny(UNKNOWN_REASON)
    try:
        scope = notion_scope(tool, tool_input)
    except NotionConfigError as exc:
        return deny(NOTION_CONFIG_REASON.format(why=exc))
    if not scope:
        return Decision()
    op, dest = scope
    stuck = receipts.unresolved_entries()
    if stuck:
        return deny("maeng G2: an earlier Notion write has no confirmed readback "
                    f"(journal {stuck[0]['id']}); run `maeng-review reconcile --notion` first.")
    digest = sha256(canonical(tool_input))
    rec, problem = receipts.find_notion(digest, dest, op)
    if not rec:
        return deny(f"maeng G2: Notion {op} denied: {problem}. Get a Sol pass for this exact payload first.")
    entry = {"id": tool_use_id or digest[:16], "tool_use_id": tool_use_id, "digest": digest, "op": op,
             "destination": dest, "key": rec["key"]}
    return Decision(True, "", [("journal_pending", entry), ("receipt_pending", rec["key"], {"entry": entry["id"]})])


# ---- dispatcher entry ----------------------------------------------------

def malformed(tool_name, tool_input):
    """-> a reason when the operation fields the gate relies on are missing or of the wrong type, else ''."""
    if not isinstance(tool_name, str) or not tool_name.strip():
        return "tool_name is missing or not a string"
    if tool_name == "Bash":
        cmd = tool_input.get("command")
        if not isinstance(cmd, str) or not cmd.strip():
            return "Bash command is missing, not a string, or empty"
    elif tool_name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        keys = ("file_path", "notebook_path") if tool_name == "NotebookEdit" else ("file_path",)
        if not any(isinstance(tool_input.get(k), str) and tool_input[k].strip() for k in keys):
            return f"{tool_name} file_path is missing or not a string"
    return ""


def evaluate(tool_name, tool_input, ctx, tool_use_id=""):
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    bad = malformed(tool_name, tool_input)
    if bad:
        return deny(f"maeng gate: malformed operation ({bad}); denied because the gate cannot determine what the "
                    f"call does.")
    if tool_name == "Bash":
        return check_bash(tool_input["command"], ctx)
    if tool_name in ("Edit", "Write", "NotebookEdit", "MultiEdit"):
        if ctx.unknown:
            return deny(UNKNOWN_REASON)
        return g3_edit(tool_name, tool_input, ctx)
    if tool_name.startswith("mcp__github__"):
        return check_mcp_github(tool_name, tool_input, ctx)
    if tool_name.startswith("mcp__linear-endix__"):
        d = check_mcp_eta_linear(tool_name, tool_input, ctx)
        return d
    if tool_name.startswith("mcp__claude_ai_Notion__"):
        return check_mcp_notion(tool_name, tool_input, ctx, tool_use_id)
    return Decision()
