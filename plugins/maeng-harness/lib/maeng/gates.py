"""PreToolUse gates. Only the irreversible ship steps are blocked: a push to the default branch and a merge
that skips `maeng-ship merge` (review receipt). Everything else (gh, Notion, Linear, eta paths, env) is allowed."""
import os
import re
import shlex
from pathlib import Path

from . import canon, ghcmd, guard, readonly, receipts, remotecfg
from . import tree as treelib
from .common import cache_dir, git, git_out, home_dir
from .evidence import Verifier
from .shellparse import SHELLS, ParseError, program, split_segments

_parse_git_globals = canon.parse_git_globals
DEFAULT_BRANCHES = {"main", "master", "trunk"}
READONLY_PROGS = readonly.PROGS
READONLY_GIT = {"status", "log", "diff", "show", "rev-parse", "ls-files", "ls-tree", "cat-file", "blame", "describe",
                "grep", "shortlog", "rev-list", "name-rev", "merge-base", "ls-remote", "check-ignore"}
# handlers.post_mcp records these Notion calls in the session journal
NOTION_STRUCTURAL = {"notion-delete-pages": "delete", "notion-delete-databases": "delete", "notion-move-pages": "move",
                     "notion-create-database": "create", "notion-update-data-source": "update"}
MERGE_HINT = "merge only through `maeng-ship merge <PR>` (needs a review receipt)."


class Decision:
    def __init__(self, allow=True, reason="", effects=None):
        self.allow, self.reason, self.effects = allow, reason, effects or []


def deny(reason):
    return Decision(False, reason)


class Ctx:
    def __init__(self, cwd, state, world=guard.PERSONAL, home=None):
        self.cwd, self.state, self.world = cwd, state, world


def _abs(path, cwd):
    p = Path(os.path.expanduser(path))
    return str(p if p.is_absolute() else Path(cwd) / p)


def _strings(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _strings(v)
    elif obj is not None:
        yield str(obj)


def is_default_branch(branch, cwd, remote, policy):
    if branch in DEFAULT_BRANCHES or branch in (policy.get("protected_branches") or []):
        return True
    return bool(remote) and remotecfg.default_head(cwd, remote) == branch


# ---- harness state -------------------------------------------------------

STATE_REASON = ("maeng: {what} writes into the harness state directory ({root}); harness state (receipts, "
                "session state, caches) is written only by the maeng CLIs and hooks.")


def harness_state_root(path, cwd):
    """-> the harness state root (MAENG_HOME / MAENG_CACHE_DIR) the path resolves into, symlinks followed, or ''."""
    target = os.path.realpath(_abs(path, cwd))
    for root in (home_dir(), cache_dir()):
        r = os.path.realpath(str(root))
        if target == r or target.startswith(r.rstrip("/") + "/"):
            return r
    return ""


def check_edit(tool_name, tool_input, ctx):
    path = tool_input.get("file_path") or tool_input.get("notebook_path") or tool_input.get("path")
    root = harness_state_root(path, ctx.cwd) if isinstance(path, str) and path else ""
    return deny(STATE_REASON.format(what=tool_name, root=root)) if root else Decision()


# ---- git push ------------------------------------------------------------

PUSH_VALUE_OPTS = {"--repo", "-o", "--push-option", "--receive-pack", "--exec", "--recurse-submodules"}


def _config(cwd, key, cfg=None, multi=False, boolean=False):
    """-> git's effective value(s) of a config key, with the command's `-c` overrides applied by git itself
    (last value wins for single-valued keys; -c values are appended to multi-valued ones)."""
    overrides = [a for k, vals in (cfg or {}).items() for v in vals for a in ("-c", k if v is None else f"{k}={v}")]
    rc, out, _ = git(cwd, *overrides, "config", *(["--type=bool"] if boolean else []),
                     "--get-all" if multi else "--get", key)
    return (out.splitlines() if multi else [out.strip()]) if rc == 0 and out.strip() else []  # values may hold spaces (aliases)


def push_targets(args, cwd, cfg=None):
    """-> (remote, [destination branch names]) of `git push <args>`; ['*'] for --all/--mirror, [''] when an
    implicit destination cannot be determined (detached HEAD, unknown directory)."""
    pos, skip, every, repo = [], None, False, None
    for a in args:
        if skip:
            repo = a if skip == "--repo" else repo
            skip = None
        elif a in PUSH_VALUE_OPTS:
            skip = a
        elif a.startswith("--repo="):
            repo = a[7:]
        elif a in ("--all", "--mirror", "--branches"):
            every = True
        elif not a.startswith("-"):
            pos.append(a)
    current = git_out(cwd, "symbolic-ref", "--short", "-q", "HEAD") or ""
    remote, specs = (pos[0], pos[1:]) if pos else (repo, []) if repo else \
        ((_config(cwd, f"branch.{current}.pushRemote", cfg) or _config(cwd, "remote.pushDefault", cfg)
          or _config(cwd, f"branch.{current}.remote", cfg) or ["origin"])[0], [])
    rc, urls, _ = git(cwd, "config", "--get-regexp", r"^remote\..*\.url$")
    remote = next((k[7:-4] for k, _, u in (ln.partition(" ") for ln in urls.splitlines() if rc == 0)
                   if u == remote), remote)  # a URL operand that is a configured remote's URL is that remote
    if every or _config(cwd, f"remote.{remote}.mirror", cfg, boolean=True) == ["true"]:
        return remote, ["*"]
    if not specs:  # implicit: the current branch, its upstream, and any configured remote.<r>.push refspecs
        if _config(cwd, "push.default", cfg) == ["matching"]:
            return remote, ["*"]
        upstream = [m.removeprefix("refs/heads/") for m in _config(cwd, f"branch.{current}.merge", cfg, multi=True)]
        specs = [current, *upstream, *_config(cwd, f"remote.{remote}.push", cfg, multi=True)]
    out = []
    for s in specs:
        spec = s.lstrip("+")
        src, _, dst = spec.rpartition(":") if ":" in spec else ("", "", spec)
        dst = (dst or src).removeprefix("refs/heads/")  # `main:` pushes main
        # `:` pushes every matching branch; a glob may match the default branch
        out.append("*" if spec == ":" or "*" in dst else current if dst in ("HEAD", "@") else dst)
    return remote, out


def check_push(toks, cwd, ctx):
    form, _ = canon.parse_canonical_push(toks)
    policy = treelib.load_policy(treelib.toplevel(cwd) or cwd)
    if policy.get("invalid"):
        return deny(f"maeng G1: {policy['invalid']}; protected branches cannot be read, so pushes are denied until "
                    f"it is fixed.")
    if form and form["form"] == "lease" and \
            is_default_branch(form["ref"].removeprefix("refs/heads/"), cwd, form["remote"], policy):
        return check_merge_push(form, cwd, ctx)  # the maeng-ship merge push; a feature-branch lease is a plain push
    _, args, _, cfg = _parse_git_globals(toks)
    remote, dsts = push_targets(args, cwd, cfg)
    for dst in dsts:
        if not dst or "$" in dst or "$" in remote:  # the parser keeps `$var` unexpanded
            return deny("maeng G1: cannot tell where this push goes (no current branch, or a shell variable); name "
                        "the remote and branch literally.")
        if dst == "*" or is_default_branch(dst, cwd, remote, policy):
            return deny(f"maeng G1: pushing to the default branch (`{dst}`) is denied; push a feature branch and "
                        f"{MERGE_HINT}")
    return Decision()


def check_merge_push(lease, cwd, ctx):
    """The exact maeng-ship lease form: only with matching receipts covering the change, for this repository,
    and a verified head tree."""
    rev = (ctx.state.get("binding") or {}).get("plan_updated_at")
    url, err = remotecfg.plain_remote(cwd, lease["remote"])
    if err:
        return deny(err)
    repo = guard.normalize_repo(url)
    recs, problem = receipts.find_code(cwd, repo, lease["base"], lease["head"], lease["ref"], rev,
                                      issue=(ctx.state.get("binding") or {}).get("issue"))
    if not recs:
        return deny(f"maeng G1: merge push denied: {problem}. Use `maeng-review` then `maeng-ship merge <PR>`.")
    if git(cwd, "merge-base", "--is-ancestor", lease["base"], lease["head"])[0] != 0:
        return deny("maeng G1: merge push denied: base is not an ancestor of head (BEHIND). Update, re-verify, re-review.")
    tree = treelib.commit_tree(cwd, lease["head"])
    top, common = treelib.toplevel(cwd), treelib.common_dir(cwd)
    ok, reasons = Verifier(ctx.state, top, common).ship_verified(tree) if tree and top and common \
        else (False, ["cannot resolve the commit tree"])
    if not ok:
        return deny(f"maeng G1: reviewed head tree is not ship-verified ({'; '.join(reasons)}).")
    intent = {k: lease[k] for k in ("remote", "ref")}
    intent.update(base_sha=lease["base"], head_sha=lease["head"], repo=repo)
    return Decision(True, "", [("receipt_pending", rec["key"], intent) for rec in recs])


# ---- Bash ----------------------------------------------------------------

# Test switches and binary/state overrides retarget maeng-ship's own checks (fixture receipts, fake git/gh); other
# MAENG_* prefixes (MAENG_REVIEW_BACKEND, ...) stay allowed.
# shortcut: a text match, not a shell parse; catches assignment/export/unset/env -u, not quoting tricks.
SWITCHES = r"MAENG_(?:TEST_FIXTURES|GIT|GH|HOME|CACHE_DIR)\b"
SWITCH_SET = re.compile(rf"\b{SWITCHES}\+?=|\b(?:export|unset|declare|typeset|readonly|local|read|env)\b[^;&|\n]*\b{SWITCHES}")
SHIP_TEXT = re.compile(r"\bgit\b.*\bpush\b|\bgh\b.*\b(?:pr|api|alias|repo)\b|--force-with-lease|maeng-ship", re.S)
SHELL_KEYWORDS = {"if", "then", "elif", "else", "while", "until", "do", "!", "{"}
GH_API_MERGE = re.compile(r"/pulls/[^/\s]+/(?:merge|update-branch)\b|/merges\b|/merge-upstream\b|/git/refs\b")
GH_GRAPHQL_MERGE = re.compile(r"mergePullRequest|updatePullRequestBranch|mergeBranch|updateRefs?\b|createRef\b|"
                              r"enablePullRequestAutoMerge|enqueuePullRequest|createCommitOnBranch", re.I)


def check_gh(toks, cwd, expands=False):
    """expands: the raw command has a `$` outside single quotes, so a `$` in a value may be a shell expansion."""
    info = ghcmd.parse_gh(toks)
    pos = info["pos"]
    if pos[:2] in (["pr", "merge"], ["pr", "update-branch"], ["repo", "sync"]):
        return deny(f"maeng G1: `gh {' '.join(pos[:2])}` is denied; {MERGE_HINT}")
    if pos[:2] in (["pr", "create"], ["pr", "new"]) and not ({"-H", "--head"} & {t.partition("=")[0] for t in toks}) and \
            is_default_branch(git_out(cwd, "symbolic-ref", "--short", "-q", "HEAD") or "", cwd, "origin",
                              treelib.load_policy(treelib.toplevel(cwd) or cwd)):
        return deny("maeng G1: `gh pr create` on the default branch can push it; create the PR from a feature branch "
                    "or pass --head.")
    if pos[:1] and pos[0] in ghcmd.gh_aliases():
        return deny(f"maeng G1: `gh {pos[0]}` is a gh alias, which can hide a merge; run the underlying command.")
    if pos[:1] == ["api"]:
        text = " ".join(toks)
        writes = info["method"] not in (None, "GET") or (info["method"] is None and (info["fields"] or info["input"]))
        if (writes and GH_API_MERGE.search(text)) or GH_GRAPHQL_MERGE.search(text):
            return deny(f"maeng G1: this `gh api` call merges or moves a branch ref; {MERGE_HINT}")
        branches = [f[7:].removeprefix("refs/heads/") for f in info["fields"] if f.startswith("branch=")]
        if any(b.startswith("@") or "{" in b or "$" in b for b in branches):  # gh expands these; the gate cannot see the value
            return deny("maeng G1: a contents-API `branch=` from a file, a {placeholder} or a variable cannot be checked; name the "
                        "feature branch literally.")
        policy = treelib.load_policy(treelib.toplevel(cwd) or cwd)
        if writes and "/contents/" in text and (info["input"] or not branches or any(
                is_default_branch(b, cwd, "origin", policy) for b in branches)):
            return deny("maeng G1: a contents-API write without a literal feature `branch=` field (or with --input) can commit to the default branch.")
        query = [f for f in info["fields"] if f.startswith("query=")]
        if pos[1:2] == ["graphql"] and (info["input"] or not query or any(f.startswith("$") for f in info["fields"]) or any(f[6:].startswith(("@", "$")) or "$(" in f or "`" in f or (expands and "$" in f)
            or (f in info["typed"] and re.search(r"\{(?:owner|repo|branch)\}", f))
                                                             for f in query)):
            return deny("maeng G1: a `gh api graphql` query from a file, --input or a variable cannot be checked for "
                        "a merge mutation; pass the query as a literal -f query='...'.")
    return Decision()


def check_git(toks, cwd, ctx):
    sub, args, dirs, cfg = _parse_git_globals(toks)
    for kind, d in dirs:  # git applies -C cumulatively
        if kind == "C":
            cwd = _abs(d, cwd)
    alias = [v for k, vals in cfg.items() if sub and k == f"alias.{sub.lower()}" for v in vals if v] or (_config(cwd, f"alias.{sub}") if sub else [])
    if any(re.search(r"\bpush\b|\bmerge\b|\bupdate-branch\b|\brepo\s+sync\b", a) for a in alias):
        return deny(f"maeng G1: `git {sub}` is an alias that pushes or merges; run the underlying command.")
    for a in alias:  # a `!` alias runs a shell command: check it like Bash (a self-recursive alias fails closed)
        d = check_bash(" ".join([a[1:], *map(shlex.quote, args)]), Ctx(cwd, ctx.state, ctx.world)) \
            if a.startswith("!") else Decision()  # git appends the invocation's arguments
        if not d.allow:
            return d
    if sub == "push" and any(kind != "C" for kind, _ in dirs):
        return deny("maeng G1: a push with --git-dir/--work-tree is not checked; use `git -C <dir> push ...`.")
    return check_push(toks, cwd, ctx) if sub == "push" else Decision()


def check_bash(command, ctx, moved=False):
    if SWITCH_SET.search(command):
        return deny("maeng G1: setting MAENG_TEST_FIXTURES / MAENG_GIT / MAENG_GH / MAENG_HOME / MAENG_CACHE_DIR from "
                    "Bash is denied; they switch maeng-ship to test fixtures or fake binaries.")
    try:
        segs = split_segments(command.rstrip())
    except ParseError:
        if SHIP_TEXT.search(command):
            return deny("maeng G1: cannot parse this command and it mentions a push or merge; run that step as a "
                        "simpler command.")
        return Decision()
    cwd, effects = ctx.cwd, []
    expands = bool(re.search(r"\$[A-Za-z_{]", re.sub(r"'[^']*'", "", command)))
    for seg in segs:
        words = list(seg.tokens)
        while words and words[0] in SHELL_KEYWORDS:  # `if git push ...; then` runs the condition too
            words.pop(0)
        prog, toks = program(words)
        payload = " ".join(toks[1:]) if prog == "eval" else \
            next((toks[i + 1] for i, t in enumerate(toks[1:4], 1)
                  if re.fullmatch(r"-[a-zA-Z]*c[a-zA-Z]*", t) and i + 1 < len(toks)), None) if prog in SHELLS else None
        if payload:  # `sh -c '...'` / `eval '...'`: check the wrapped command too
            d = check_bash(payload, Ctx(cwd, ctx.state, ctx.world), moved)
            if not d.allow:
                return d
            effects += d.effects
            moved = moved or bool(re.search(r"\bgit\b.*\b(?:checkout|switch|config)\b", payload))
        if prog in ("cd", "pushd") and len(toks) > 1:
            cwd = _abs(os.path.expandvars(toks[1]), cwd)
        elif moved and ((prog == "git" and _parse_git_globals(toks)[0] == "push") or (
                prog == "gh" and ghcmd.parse_gh(toks)["pos"][:2] in (["pr", "create"], ["pr", "new"])
                and not ({"-H", "--head"} & {t.partition("=")[0] for t in toks}))):
            return deny("maeng G1: this push follows a checkout/switch/config change in the same command, so its "
                        "destination cannot be checked beforehand; run the push as its own command.")
        elif prog in ("git", "gh"):
            moved = moved or _parse_git_globals(toks)[0] in ("checkout", "switch", "config") \
                if prog == "git" else moved
            d = check_git(toks, cwd, ctx) if prog == "git" else check_gh(toks, cwd, expands)
            if not d.allow:
                return d
            effects += d.effects
    return Decision(True, "", effects)


# ---- MCP -----------------------------------------------------------------

GITHUB_MCP_GATED = re.compile(r"__(?:merge_pull_request|update_pull_request_branch|push_files|create_or_update_file|"
                              r"delete_file)$")


def check_mcp_github(tool, tool_input, ctx):
    name = tool.split("__", 2)[-1]
    if name in ("merge_pull_request", "update_pull_request_branch"):
        return deny(f"maeng G1: {name} is denied; {MERGE_HINT}")
    if name in ("push_files", "create_or_update_file", "delete_file"):
        branch = str(tool_input.get("branch") or "").removeprefix("refs/heads/")
        policy = treelib.load_policy(treelib.toplevel(ctx.cwd) or ctx.cwd)
        if not branch or is_default_branch(branch, ctx.cwd, "origin", policy):
            return deny(f"maeng G1: {name} to the default branch (or with no branch) is denied; write to a feature "
                        f"branch.")
    return Decision()


def evaluate(tool_name, tool_input, ctx, tool_use_id=""):
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    if tool_name == "Bash":
        if not isinstance(tool_input.get("command"), str):
            return deny("maeng gate: the Bash command is missing or not a string; denied because it cannot be read.")
        return check_bash(tool_input["command"], ctx)
    if tool_name in ("Edit", "Write", "NotebookEdit", "MultiEdit"):
        return check_edit(tool_name, tool_input, ctx)
    if tool_name.startswith("mcp__") and GITHUB_MCP_GATED.search(tool_name):  # any server name (plugin, connector)
        return check_mcp_github(tool_name, tool_input, ctx)
    return Decision()
