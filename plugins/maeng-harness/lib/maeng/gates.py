"""PreToolUse gates. Only the irreversible ship steps are blocked: a push to the default branch and a merge
that skips `maeng-ship merge` (review receipt). Everything else (gh, Notion, Linear, eta paths, env) is allowed."""
import os
from pathlib import Path

from . import canon, ghcmd, guard, readonly, receipts, remotecfg
from . import tree as treelib
from .common import cache_dir, git, git_out, home_dir
from .evidence import Verifier
from .shellparse import ParseError, program, split_segments

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

PUSH_VALUE_OPTS = {"--repo", "-o", "--push-option", "--receive-pack", "--exec"}


def push_targets(args, cwd):
    """-> (remote, [destination branch names]) of `git push <args>`; ['*'] for --all/--mirror."""
    pos, skip, every = [], False, False
    for a in args:
        if skip:
            skip = False
        elif a in PUSH_VALUE_OPTS:
            skip = True
        elif a in ("--all", "--mirror", "--branches"):
            every = True
        elif not a.startswith("-"):
            pos.append(a)
    remote, specs = (pos[0], pos[1:]) if pos else ("", [])
    current = git_out(cwd, "symbolic-ref", "--short", "-q", "HEAD") or ""
    if every:
        return remote, ["*"]
    if not specs:
        return remote, [current]
    out = []
    for s in specs:
        dst = s.lstrip("+").rpartition(":")[2] or s.lstrip("+")
        dst = dst.removeprefix("refs/heads/")
        out.append(current if dst == "HEAD" else dst)
    return remote, out


def check_push(toks, cwd, ctx):
    form, _ = canon.parse_canonical_push(toks)
    if form and form["form"] == "lease":  # the maeng-ship merge push
        return check_merge_push(form, cwd, ctx)
    _, args, _, _ = _parse_git_globals(toks)
    remote, dsts = push_targets(args, cwd)
    policy = treelib.load_policy(treelib.toplevel(cwd) or cwd)
    for dst in dsts:
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

def check_bash(command, ctx):
    try:
        segs = split_segments(command.rstrip())
    except ParseError:
        return Decision()  # shortcut: an unparseable command is not inspected; the hook catches mistakes, not attacks
    cwd, effects = ctx.cwd, []
    for seg in segs:
        prog, toks = program(seg.tokens)
        if prog in ("cd", "pushd") and len(toks) > 1:
            cwd = _abs(os.path.expandvars(toks[1]), cwd)
        elif prog == "git":
            sub, _, dirs, _ = _parse_git_globals(toks)
            run_cwd = next((_abs(d, cwd) for kind, d in dirs if kind == "C"), cwd)
            if sub == "push":
                d = check_push(toks, run_cwd, ctx)
                if not d.allow:
                    return d
                effects += d.effects
        elif prog == "gh" and ghcmd.parse_gh(toks)["pos"][:2] == ["pr", "merge"]:
            return deny(f"maeng G1: `gh pr merge` is denied; {MERGE_HINT}")
    return Decision(True, "", effects)


# ---- MCP -----------------------------------------------------------------

def check_mcp_github(tool, tool_input, ctx):
    name = tool.split("__", 2)[-1]
    if name in ("merge_pull_request", "update_pull_request_branch"):
        return deny(f"maeng G1: {name} is denied; {MERGE_HINT}")
    if name in ("push_files", "create_or_update_file") and str(tool_input.get("branch", "")) in DEFAULT_BRANCHES:
        return deny(f"maeng G1: {name} to the default branch is denied; write to a feature branch.")
    return Decision()


def evaluate(tool_name, tool_input, ctx, tool_use_id=""):
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    if tool_name == "Bash" and isinstance(tool_input.get("command"), str):
        return check_bash(tool_input["command"], ctx)
    if tool_name in ("Edit", "Write", "NotebookEdit", "MultiEdit"):
        return check_edit(tool_name, tool_input, ctx)
    if tool_name.startswith("mcp__github__"):
        return check_mcp_github(tool_name, tool_input, ctx)
    return Decision()
