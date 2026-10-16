"""PreToolUse gates. G1 code-ship, G2 Notion publish, G3 cross-world (eta)."""
import os
import re
from pathlib import Path

from . import guard, receipts
from . import tree as treelib
from .common import canonical, git, git_out, home_dir, read_json, sha256
from .evidence import Verifier
from .shellparse import (ENV_ASSIGN, ParseError, RISKY, ROUTE, has_control_structure, program, split_segments,
                         uses_wrapper)

SHA_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
LEASE_RE = re.compile(r"^--force-with-lease=(refs/heads/[^:\s]+):([0-9a-f]{40}(?:[0-9a-f]{24})?)$")
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
    head = git_out(cwd, "symbolic-ref", "-q", f"refs/remotes/{remote}/HEAD") if remote else None
    return bool(head and head.rsplit("/", 1)[-1] == branch)


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
PATHLIKE = ("/", "~", "../", "./")


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

def check_bash(command, ctx):
    try:
        segs = split_segments(command)
    except ParseError:
        return deny("maeng G1: cannot parse this command and it mentions a push/merge/PR route; "
                    "run the simple form directly.") if RISKY.search(command) else Decision()
    payload = uses_wrapper(segs)
    if payload and RISKY.search(payload):
        return deny("maeng G1: shell wrappers (sh -c / bash -c / eval) are not allowed around push/merge/PR "
                    "routes; run the command directly.")
    if has_control_structure(command, segs) and (ROUTE.search(command) or RISKY.search(command)):
        return deny("maeng G1: shell control structures (if/while/for/case, functions, `{ }`, subshells) combined "
                    "with a push/merge/PR/API route are unsupported; run it as a plain command.")
    cwd, effects = ctx.cwd, []
    for seg in segs:
        d, cwd = check_segment(seg, cwd, ctx)
        if not d.allow:
            return d
        effects += d.effects
    return Decision(True, "", effects)


def _cwd_gate(cwd, ctx, prog, mutating):
    """Segments running with cwd inside eta may only read."""
    if not mutating:
        return None
    w = guard.classify(cwd)
    if w == guard.ETA:
        return deny(f"maeng G3: `{prog}` would run inside an eta checkout ({cwd}); only read-only commands are allowed there.")
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


def _arg_paths(toks):
    for t in toks[1:]:
        if "=" in t and not t.startswith("/"):  # --output=/x, of=/x
            t = t.split("=", 1)[1]
        if t and not t.startswith("-") and (t.startswith(PATHLIKE) or "/" in t or t == ".."):
            yield t


def check_segment(seg, cwd, ctx):
    prog, toks = program(seg.tokens)
    for target in seg.redirects:  # every output target, relative to this segment's effective directory
        d = g3_path(target, cwd, ctx, "redirect")
        if d:
            return d, cwd
    if prog in ("cd", "pushd") and len(toks) > 1:
        return Decision(), _abs(toks[1], cwd)
    if prog == "git":
        for t in seg.tokens:
            if not ENV_ASSIGN.match(t):
                break
            if t.startswith(("GIT_CONFIG_COUNT=", "GIT_CONFIG_PARAMETERS=")) and "push" in toks:
                return deny("maeng G1: git config injected through the environment cannot be checked; "
                            "push with an explicit refspec."), cwd
        return check_git(toks, cwd, ctx), cwd
    if prog == "gh":
        return check_gh(toks, cwd, ctx), cwd
    if not prog or (prog in READONLY_PROGS and not mutating_options(prog, toks)):
        return Decision(), cwd
    d = _cwd_gate(cwd, ctx, prog, True)
    if d:
        return d, cwd
    for t in _arg_paths(toks):
        d = g3_path(t, cwd, ctx, f"`{prog}` argument")
        if d:
            return d, cwd
    if prog == "tee":
        for t in toks[1:]:
            if not t.startswith("-"):
                d = g3_path(t, cwd, ctx, "tee target")
                if d:
                    return d, cwd
    return Decision(), cwd


def _parse_git_globals(toks):
    """-> (subcommand, args_after, cwd_dirs, config_overrides)"""
    i, dirs, cfg = 1, [], {}
    while i < len(toks):
        t = toks[i]
        if t == "-C" and i + 1 < len(toks):
            dirs.append(toks[i + 1]); i += 2
        elif t == "-c" and i + 1 < len(toks):
            k, _, v = toks[i + 1].partition("=")
            cfg.setdefault(k.lower(), []).append(v); i += 2
        elif t.startswith("--git-dir=") or t.startswith("--work-tree="):
            dirs.append(t.split("=", 1)[1]); i += 1
        elif t in ("--git-dir", "--work-tree", "--namespace") and i + 1 < len(toks):
            i += 2
        elif t.startswith("-"):
            i += 1
        else:
            return t, toks[i + 1:], dirs, cfg
    return None, [], dirs, cfg


def check_git(toks, cwd, ctx):
    sub, args, dirs, cfg = _parse_git_globals(toks)
    ro = git_readonly(sub, args)
    for d in dirs:
        cwd = _abs(d, cwd)
        if not ro:
            blocked = g3_path(cwd, cwd, ctx, "git -C")
            if blocked:
                return blocked
    if sub is None:
        return Decision()
    if not ro:
        blocked = _cwd_gate(cwd, ctx, "git " + sub, True)
        if blocked:
            return blocked
    for p_ in _arg_paths(["git", *args]) if sub in READONLY_GIT and not ro else ():
        blocked = g3_path(p_, cwd, ctx, "git output")
        if blocked:
            return blocked
    if sub == "push":
        return deny(UNKNOWN_REASON) if ctx.unknown else check_push(args, cwd, cfg, ctx)
    return Decision()


# ---- git push ------------------------------------------------------------

def _cfg(cwd, cfg, key):
    if key.lower() in cfg:
        return cfg[key.lower()][-1]
    return git_out(cwd, "config", "--get", key)


def _push_config_specs(cwd, cfg, remote):
    """Effective `remote.<name>.push` values: config files then `git -c` overrides (an empty value resets).
    -> (specs, error)"""
    rc, out, _ = git(cwd, "config", "--get-all", f"remote.{remote}.push")
    if rc not in (0, 1):
        return [], f"cannot read remote.{remote}.push; push with an explicit refspec."
    specs = out.splitlines() if rc == 0 else []
    for v in cfg.get(f"remote.{remote}.push".lower(), []):
        specs = [] if v == "" else specs + [v]
    return specs, None


def _parse_push(args):
    o = {"force": False, "mirror": False, "all": False, "tags": False, "delete": False, "dry": False,
         "repo": None, "pos": []}
    i = 0
    takes_value = {"--push-option", "--receive-pack", "--exec", "-o"}
    while i < len(args):
        t = args[i]
        if t == "--":
            o["pos"] += args[i + 1:]
            break
        if t.startswith("--"):
            name, eq, val = t.partition("=")
            if name in ("--force", "--force-with-lease", "--force-if-includes"):
                o["force"] = True
            elif name == "--mirror":
                o["mirror"] = True
            elif name in ("--all", "--branches"):
                o["all"] = True
            elif name in ("--tags", "--follow-tags"):
                o["tags"] = True
            elif name == "--delete":
                o["delete"] = True
            elif name in ("--dry-run",):
                o["dry"] = True
            elif name == "--repo":
                o["repo"] = val if eq else (args[i + 1] if i + 1 < len(args) else None)
                i += 0 if eq else 1
            elif name in takes_value and not eq:
                i += 1
        elif t.startswith("-") and len(t) > 1:
            cluster = t[1:]
            if "f" in cluster:
                o["force"] = True
            if "d" in cluster:
                o["delete"] = True
            if "n" in cluster:
                o["dry"] = True
            if cluster.endswith("o") and i + 1 < len(args):
                i += 1
        else:
            o["pos"].append(t)
        i += 1
    return o


def _remote_url(cwd, remote):
    url = git_out(cwd, "remote", "get-url", "--push", remote)
    if url:
        return url
    if "/" in remote or ":" in remote or remote.startswith("."):
        return remote
    return None


def _current_branch(cwd):
    return git_out(cwd, "symbolic-ref", "--short", "-q", "HEAD")


def _resolve_remote(opts, cwd, cfg, cur):
    pos = opts["pos"]
    if opts["repo"]:
        return opts["repo"], pos
    if pos:
        return pos[0], pos[1:]
    for key in (f"branch.{cur}.pushRemote" if cur else None, "remote.pushDefault",
                f"branch.{cur}.remote" if cur else None):
        v = key and _cfg(cwd, cfg, key)
        if v:
            return v, pos
    return "origin", pos


def _branch_of(ref):
    return ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref


def _exact_lease(args):
    if len(args) != 3:
        return None
    m = LEASE_RE.match(args[0])
    if not m:
        return None
    ref, base = m.group(1), m.group(2)
    head, _, dst = args[2].partition(":")
    if SHA_RE.match(head) and dst == ref:
        return {"ref": ref, "base": base, "head": head, "remote": args[1]}
    return None


def check_push(args, cwd, cfg, ctx):
    lease = _exact_lease(args)
    if lease:
        return check_merge_push(lease, cwd, ctx)
    o = _parse_push(args)
    if o["dry"]:
        return Decision()
    if o["force"] or any(p.startswith("+") for p in o["pos"]):
        return deny("maeng G1: force pushes are denied (-f, --force, --force-with-lease, +refspec). "
                    "Merging goes through `maeng-ship merge <PR>`.")
    if o["mirror"]:
        return deny("maeng G1: `git push --mirror` is denied.")
    if o["all"]:
        return deny("maeng G1: `git push --all/--branches` is denied; push the feature branch explicitly.")
    if o["tags"] or "tag" in o["pos"][1:2]:
        return deny("maeng G1: tag pushes are denied.")
    cur = _current_branch(cwd)
    remote, refspecs = _resolve_remote(o, cwd, cfg, cur)
    url = _remote_url(cwd, remote)
    if not url:
        return deny(f"maeng G1: cannot resolve push remote `{remote}`.")
    if guard.remote_is_eta(url):
        return deny(f"maeng G3: push target {url} is an eta repository; eta is a separate world.")
    policy = treelib.load_policy(treelib.toplevel(cwd) or cwd)
    pairs, err = _resolve_refspecs(refspecs, cwd, cfg, cur, o["delete"], remote)
    if err:
        return deny("maeng G1: " + err)
    for src, dst in pairs:
        ref = dst if dst.startswith("refs/") else "refs/heads/" + dst
        if ref.startswith("refs/tags/"):
            return deny("maeng G1: tag pushes are denied.")
        if not ref.startswith("refs/heads/"):
            return deny(f"maeng G1: pushing to non-branch ref {ref} is denied.")
        branch = _branch_of(ref)
        if is_default_branch(branch, cwd, remote, policy):
            return deny(f"maeng G1: pushing to the default branch `{branch}` is denied. Open a PR and use "
                        f"`maeng-ship merge <PR>` (needs a matching review receipt).")
        if src is None:
            continue  # deleting a non-default branch
        commit = git_out(cwd, "rev-parse", "--verify", "-q", src + "^{commit}")
        if not commit:
            return deny(f"maeng G1: cannot resolve source `{src}` to a commit.")
        d = _verify_or_deny(ctx, cwd, commit, f"pushed commit {commit[:8]} ({src} -> {branch})")
        if d:
            return d
    return Decision()


def _resolve_refspecs(refspecs, cwd, cfg, cur, delete_flag, remote=None):
    """-> ([(src|None, dst)], error)"""
    if refspecs and refspecs[0] == "tag":
        return [], "tag pushes are denied."
    pairs = []
    for spec in refspecs:
        if "*" in spec:
            return [], f"glob refspec `{spec}` cannot be checked; push with an explicit refspec."
        src, colon, dst = spec.partition(":")
        if delete_flag and not colon:
            pairs.append((None, src)); continue
        if colon and not src:
            pairs.append((None, dst)); continue
        if not colon:
            if src == "HEAD":
                if not cur:
                    return [], "detached HEAD needs an explicit destination."
                dst = cur
            else:
                dst = src
        elif not dst:
            return [], f"refspec `{spec}` has no destination."
        pairs.append((src, dst))
    if pairs:
        return pairs, None
    if remote and not remote.startswith(("/", ".", "~")) and "://" not in remote:
        specs, err = _push_config_specs(cwd, cfg, remote)
        if err:
            return [], err
        if specs:  # git uses remote.<name>.push instead of push.default
            if any(sp.startswith("+") for sp in specs):
                return [], "force refspec configured in remote.%s.push; push with an explicit refspec." % remote
            return _resolve_refspecs(specs, cwd, cfg, cur, delete_flag, None)
    if not cur:
        return [], "detached HEAD push without a refspec cannot be checked."
    mode = (_cfg(cwd, cfg, "push.default") or "simple").lower()
    upstream = _cfg(cwd, cfg, f"branch.{cur}.merge")
    up_name = _branch_of(upstream) if upstream else None
    if mode == "current":
        dst = cur
    elif mode in ("upstream", "tracking"):
        if not up_name:
            return [], "push.default=upstream but the branch has no upstream."
        dst = up_name
    elif mode == "simple":
        if up_name and up_name != cur:
            return [], f"push.default=simple with upstream `{up_name}` != `{cur}`; push with an explicit refspec."
        dst = cur
    else:
        return [], f"push.default={mode} cannot be checked; push with an explicit refspec."
    return [(cur, dst)], None


def check_merge_push(lease, cwd, ctx):
    """The exact maeng-ship lease form: only with matching receipts covering the change, for this repository,
    and a verified head tree."""
    rev = _binding_rev(ctx)
    url = _remote_url(cwd, lease["remote"])
    if not url:
        return deny(f"maeng G1: merge push denied: cannot resolve push remote `{lease['remote']}`.")
    if guard.remote_is_eta(url):
        return deny(f"maeng G3: merge push target {url} is an eta repository; eta is a separate world.")
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


# ---- gh ------------------------------------------------------------------

GH_ALLOWED = {
    "pr": {"view", "list", "diff", "checks", "status", "checkout", "comment", "edit", "review", "ready", "close"},
    "issue": None,  # everything
    "repo": {"view", "list", "clone", "set-default"},
    "run": {"view", "list", "watch", "download"},
    "workflow": {"view", "list"},
    "release": {"view", "list", "download"},
    "search": None, "status": None, "browse": None, "completion": None, "help": None, "version": None,
    "auth": {"status", "token"}, "label": {"list"}, "gist": {"view", "list", "clone"}, "cache": {"list"},
    "ruleset": {"view", "list", "check"}, "secret": {"list"}, "variable": {"list", "get"},
    "ssh-key": {"list"}, "gpg-key": {"list"}, "extension": {"list", "search", "browse"},
    "alias": {"list"}, "config": {"get", "list"},
}
READ_ACTIONS = {"view", "list", "diff", "checks", "status", "checkout", "watch", "download", "clone", "set-default",
                "token", "get", "check", "search", "browse"}
GH_VALUE_FLAGS = {"-X", "--method", "-H", "--header", "-f", "-F", "--field", "--raw-field", "-q", "--jq", "-t",
                  "--template", "--hostname", "--cache", "--input", "-B", "--base", "-H", "--head", "-t", "--title",
                  "-b", "--body", "-F", "--body-file", "-a", "--assignee", "-l", "--label", "-m", "--milestone",
                  "-r", "--reviewer", "-p", "--project", "--jq"}


def parse_gh(toks):
    args = toks[1:]
    info = {"repo": None, "pos": [], "flags": {}, "method": None, "fields": [], "input": False}
    i = 0
    while i < len(args):
        t = args[i]
        name, eq, val = t.partition("=")
        if t in ("-R", "--repo") or name == "--repo":
            info["repo"] = val if eq else (args[i + 1] if i + 1 < len(args) else None)
            i += 0 if eq else 1
        elif re.match(r"^-X[A-Za-z]+$", t):
            info["method"] = t[2:].upper()
        elif t in ("-X", "--method") or name == "--method":
            v = val if eq else (args[i + 1] if i + 1 < len(args) else "")
            info["method"] = v.upper(); i += 0 if eq else 1
        elif t in ("-f", "-F", "--field", "--raw-field") or name in ("--field", "--raw-field"):
            v = val if eq else (args[i + 1] if i + 1 < len(args) else "")
            info["fields"].append(v); i += 0 if eq else 1
        elif t.startswith(("-f", "-F")) and len(t) > 2 and t[2] != "-":
            info["fields"].append(t[2:])
        elif name == "--input" or t == "--input":
            info["input"] = True; i += 0 if eq else 1
        elif t.startswith("-"):
            if name in GH_VALUE_FLAGS and not eq:
                info["flags"][name] = args[i + 1] if i + 1 < len(args) else ""
                i += 1
            else:
                info["flags"][name] = val if eq else True
        else:
            info["pos"].append(t)
        i += 1
    return info


def _api_repo(endpoint):
    m = re.match(r"^/?repos/([^/]+)/([^/]+)", endpoint or "")
    return f"{m.group(1)}/{m.group(2)}" if m else None


def classify_gh(toks):
    """-> (kind, reason, repo, info) kind: read | write | create | deny"""
    info = parse_gh(toks)
    pos = info["pos"]
    repo = info["repo"]
    if not pos:
        return "read", "", repo, info
    group, action = pos[0], (pos[1] if len(pos) > 1 else None)
    if group == "api":
        return _classify_api(info)
    if group == "pr" and action == "merge":
        return "deny", "`gh pr merge` is denied in every mode; use `maeng-ship merge <PR>`.", repo, info
    if group == "pr" and action == "create":
        return "create", "", repo, info
    if group not in GH_ALLOWED:
        return "deny", f"`gh {group}` is not on the G1 allowlist.", repo, info
    allowed = GH_ALLOWED[group]
    if allowed is not None and action not in allowed:
        return "deny", f"`gh {group} {action or ''}` is not on the G1 allowlist " \
                       f"(merge/sync/release/repo-edit routes go through maeng-ship or are denied).", repo, info
    if group in ("issue",) or action in ("comment", "edit", "review", "ready", "close"):
        return ("read" if action in READ_ACTIONS else "write"), "", repo, info
    return "read", "", repo, info


def _classify_api(info):
    pos = info["pos"]
    endpoint = pos[1] if len(pos) > 1 else ""
    repo = info["repo"] or _api_repo(endpoint)
    if endpoint == "graphql":
        text = " ".join(info["fields"])
        if info["input"] or re.search(r"\bmutation\b|createCommitOnBranch|mergePullRequest", text, re.I):
            return "deny", "GraphQL mutations (createCommitOnBranch, mergePullRequest, ...) are denied.", repo, info
        return "read", "", repo, info
    method = info["method"] or ("POST" if (info["fields"] or info["input"]) else "GET")
    if method in ("GET", "HEAD"):
        return "read", "", repo, info
    clean = endpoint.lstrip("/")
    if re.match(r"^repos/[^/]+/[^/]+/(issues|pulls/\d+/(comments|reviews))(/|$)", clean) and "/merge" not in clean:
        return "write", "", repo, info
    return "deny", (f"`gh api -X {method} {endpoint}` is denied (merge, ref/contents writes and other mutations "
                    f"go through maeng-ship or are not allowed)."), repo, info


def check_gh(toks, cwd, ctx):
    kind, reason, repo, info = classify_gh(toks)
    if kind == "read":
        return Decision()
    if ctx.unknown:
        return deny(UNKNOWN_REASON)
    if kind == "deny":
        return deny("maeng G1: " + reason)
    if repo and guard.remote_is_eta(repo):
        return deny(f"maeng G3: gh write targets eta repo `{repo}`; eta is a separate world.")
    if not repo:
        blocked = _cwd_gate(cwd, ctx, "gh", True)
        if blocked:
            return blocked
    if kind == "create":
        head = info["flags"].get("--head") or info["flags"].get("-H") or _current_branch(cwd)
        if not head:
            return deny("maeng G1: `gh pr create` needs a resolvable head branch.")
        commit = git_out(cwd, "rev-parse", "--verify", "-q", head.split(":")[-1] + "^{commit}")
        if not commit:
            return deny(f"maeng G1: cannot resolve PR head `{head}` locally.")
        return _verify_or_deny(ctx, cwd, commit, f"PR head {commit[:8]}") or Decision()
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
    if guard.remote_is_eta(slug):
        return deny(f"maeng G3: {name} targets eta repo `{slug}`; eta is a separate world.")
    if name in ("push_files", "create_or_update_file"):
        return deny(f"maeng G1: {name} is denied; its contents are never tied to the verified tree. Publish only "
                    f"through a verified `git commit` + `git push` of a feature branch.")
    if name in ("merge_pull_request", "update_pull_request_branch"):
        return deny(f"maeng G1: {name} is denied; merge only through `maeng-ship merge <PR>`.")
    cwd = ctx.cwd
    if name == "create_pull_request":
        head = str(tool_input.get("head", ""))
        commit = git_out(cwd, "rev-parse", "--verify", "-q", head.split(":")[-1] + "^{commit}") if head else None
        if not commit:
            return deny(f"maeng G1: cannot resolve PR head `{head}` locally.")
        return _verify_or_deny(ctx, cwd, commit, f"PR head {commit[:8]}") or Decision()
    return Decision()


def check_mcp_eta_linear(tool, tool_input, ctx):
    name = tool.split("__", 2)[-1]
    if _is_read_tool(name):
        return Decision()
    return deny(f"maeng G3: `{name}` writes to eta Linear; eta records belong to the eta session.")


# ---- G2 Notion -----------------------------------------------------------

def notion_dbs():
    env = os.environ.get("MAENG_NOTION_DBS")
    if env:
        ids = env.split(",")
    else:
        ids = (read_json(home_dir() / "config.json", {}) or {}).get("notion_databases")
        if not ids:  # shipped defaults: never leave the outcome databases ungated
            shipped = Path(__file__).resolve().parents[2] / "config" / "notion-databases.json"
            ids = (read_json(shipped, {}) or {}).get("notion_databases", [])
    return {i.replace("-", "").strip() for i in ids if i}


def _nid(value):
    return str(value or "").replace("-", "").strip()


def notion_scope(tool, tool_input):
    """-> (op, destination) when this call is G2-gated, else None."""
    name = tool.split("__", 2)[-1]
    dbs = notion_dbs()
    if name == "notion-create-pages":
        parent = tool_input.get("parent") or {}
        dest = _nid(next((v for k, v in parent.items() if k.endswith("_id")), ""))
        return ("create", dest) if dest in dbs else None
    if name == "notion-update-page":
        pid = _nid(tool_input.get("page_id"))
        journaled = {i for e in receipts.read_journal() for i in e["page_ids"]}
        return ("update", pid) if pid in receipts.registry_ids() | journaled else None
    if name == "notion-update-data-source":
        did = _nid(tool_input.get("data_source_id"))
        return ("update", did) if did in dbs else None
    return None


def check_mcp_notion(tool, tool_input, ctx, tool_use_id=""):
    scope = notion_scope(tool, tool_input)
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

def evaluate(tool_name, tool_input, ctx, tool_use_id=""):
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    if tool_name == "Bash":
        return check_bash(str(tool_input.get("command", "")), ctx)
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
