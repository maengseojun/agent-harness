"""Allowlist of canonical shipping forms (G1).

Any Bash command whose tokens mention a shipping route is allowed ONLY when the whole command is exactly one plain
segment matching a canonical form. Everything else is denied by design; the gate does not try to understand
disguised variants (wrappers, compound commands, `git -c`, ...)."""
import os
import re

from . import ghcmd
from .shellparse import ENV_ASSIGN, RISKY, SHELLS, program

SHA_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
LEASE_RE = re.compile(r"^--force-with-lease=(refs/heads/[^:\s]+):([0-9a-f]{40}(?:[0-9a-f]{24})?)$")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
NON_EXEC = {"echo", "printf", "grep", "egrep", "fgrep", "rg", "man", "which", "type", "whereis", "ls", "cat", "head",
            "tail", "wc", "less", "more", "stat", "file"}

FORMS = (
    "git push [-u] <remote> <branch>",
    "git push [-u] <remote> <local-branch>:<name|refs/heads/name>",
    "git push [-u] <remote> <full-commit-sha>:refs/heads/<name> (a SHA source needs the full refs/heads/ destination)",
    "git push --force-with-lease=refs/heads/<base>:<sha> <remote> <sha>:refs/heads/<base> (maeng-ship's exact lease)",
    "gh pr create --repo|-R <owner/repo of origin> [--base B] [--head H] [--title T] [--body B | --body-file F] [--draft]",
    "maeng-ship merge <N> [--remote R] [--session S]",
    "read-only gh commands; gh pr comment|edit|review|ready|close and gh issue * ONLY with -R <owner/repo>; "
    "gh pr checkout / repo clone / release download / run download / gist clone in a personal directory",
)


def message(why=""):
    text = ("maeng G1: only canonical shipping forms are allowed: " + "; ".join(FORMS) +
            "; run it as a plain single command (no ; && || | & newline, $(), backticks, redirects, subshells, "
            "env assignments, wrappers like env/command/sudo/xargs/sh -c, or git -c/-C/--git-dir/--work-tree).")
    return text + (f" Not canonical because: {why}." if why else "")


def unquoted_metachars(command):
    """Shell metacharacters that make a command more than one plain segment."""
    found, quote, i, n = set(), None, 0, len(command)
    while i < n:
        c = command[i]
        if quote == "'":
            if c == "'":
                quote = None
        elif quote == '"':
            if c == "\\":
                i += 1
            elif c == '"':
                quote = None
            elif c in "$`":
                found.add(c)
        elif c == "\\":
            i += 1
        elif c in "'\"":
            quote = c
        elif c in ";&|<>(){}\n`$":
            found.add(c)
        i += 1
    return found


# ---- git ------------------------------------------------------------------

def parse_git_globals(toks):
    """-> (subcommand, args_after, dirs, config_overrides); dirs = [(kind, path)] kind in C|git-dir|work-tree."""
    i, dirs, cfg = 1, [], {}
    while i < len(toks):
        t = toks[i]
        if t == "-C" and i + 1 < len(toks):
            dirs.append(("C", toks[i + 1])); i += 2
        elif t == "-c" and i + 1 < len(toks):
            k, _, v = toks[i + 1].partition("=")
            cfg.setdefault(k.lower(), []).append(v); i += 2
        elif t.startswith("--git-dir=") or t.startswith("--work-tree="):
            kind, _, v = t[2:].partition("=")
            dirs.append((kind, v)); i += 1
        elif t in ("--git-dir", "--work-tree") and i + 1 < len(toks):
            dirs.append((t[2:], toks[i + 1])); i += 2
        elif t in ("--namespace", "--super-prefix", "--exec-path", "--config-env") and i + 1 < len(toks):
            if t == "--config-env":
                cfg.setdefault(toks[i + 1].partition("=")[0].lower(), []).append("<env>")
            i += 2
        elif t.startswith("--config-env="):
            cfg.setdefault(t.split("=", 1)[1].partition("=")[0].lower(), []).append("<env>"); i += 1
        elif t.startswith("-"):
            i += 1
        else:
            return t, toks[i + 1:], dirs, cfg
    return None, [], dirs, cfg


def parse_canonical_push(toks):
    """-> (form, why). form = {'form': 'push'|'lease', 'remote', 'src', 'src_kind', 'branch'} """
    if toks[1:2] != ["push"]:
        return None, "git global options (-c/-C/--git-dir/--work-tree/...) precede the subcommand"
    lease, rest, upstream = None, [], False
    for a in toks[2:]:
        if a in ("-u", "--set-upstream"):
            upstream = True
        elif LEASE_RE.match(a) and not lease:
            lease = LEASE_RE.match(a)
        elif a.startswith("-"):
            forced = a in ("-f", "--force", "--force-if-includes") or a.startswith(("--force", "--mirror")) or \
                re.match(r"^-[A-Za-z]*f", a)
            return None, ("force pushes are denied (" + a + ")") if forced else f"git push flag `{a}` is not allowed"
        else:
            rest.append(a)
    if len(rest) != 2:
        return None, "git push needs exactly `<remote> <refspec>`"
    remote, spec = rest
    if not NAME_RE.match(remote):
        return None, "the remote must be a configured remote name"
    if lease:
        head, _, dst = spec.partition(":")
        if upstream or not (SHA_RE.match(head) and dst == lease.group(1)):
            return None, "the lease form is only `--force-with-lease=refs/heads/<base>:<sha> <remote> <sha>:refs/heads/<base>`"
        return {"form": "lease", "ref": lease.group(1), "base": lease.group(2), "head": head, "remote": remote}, ""
    src, colon, dst = spec.partition(":")
    if not colon:
        dst = src
    if "HEAD" in (src, dst) or src.endswith("_HEAD") or dst.endswith("_HEAD"):
        return None, "HEAD is not a branch name; name the branch explicitly"
    src_kind = "sha" if SHA_RE.match(src) else ("branch" if BRANCH_RE.match(src) and ".." not in src else None)
    if not src_kind or src.endswith(("/", ".lock")):
        return None, f"source `{src}` must be a local branch name or a full commit SHA"
    bare = not dst.startswith("refs/")
    if dst.startswith("refs/heads/"):
        name = dst[len("refs/heads/"):]
    elif bare:
        name = dst
    else:
        return None, f"destination `{dst}` must be refs/heads/<name> or <name>"
    if not BRANCH_RE.match(name) or ".." in name or name.endswith(("/", ".lock")) or "//" in name or \
            name.startswith("refs/"):
        return None, f"destination branch `{name}` is not a plain branch name"
    if src_kind == "sha" and bare:
        return None, "a commit SHA source needs destination refs/heads/<name>"
    return {"form": "push", "remote": remote, "src": src, "src_kind": src_kind, "branch": name}, ""


# ---- maeng-ship -----------------------------------------------------------

def parse_canonical_ship(toks):
    opts, pos, i = {}, [], 1
    while i < len(toks):
        t = toks[i]
        name, eq, val = t.partition("=")
        if name in ("--remote", "--session"):
            if not eq:
                if i + 1 >= len(toks):
                    return None, f"`{name}` needs a value"
                val = toks[i + 1]; i += 1
            opts[name[2:]] = val
        elif t.startswith("-"):
            return None, f"maeng-ship flag `{t}` is not allowed"
        else:
            pos.append(t)
        i += 1
    if len(pos) != 2 or pos[0] != "merge" or not pos[1].isdigit():
        return None, "maeng-ship is only allowed as `maeng-ship merge <N>`"
    remote = opts.get("remote", "origin")
    if not NAME_RE.match(remote) or not re.match(r"^[A-Za-z0-9_.-]*$", opts.get("session", "")):
        return None, "unsupported --remote/--session value"
    return {"form": "ship", "pr": pos[1], "remote": remote}, ""


# ---- route detection ------------------------------------------------------

def _github_write(toks):
    """curl/wget that writes to GitHub: a mutating method or a request body, aimed at github.com."""
    if not any("github.com" in t for t in toks):
        return False
    for i, t in enumerate(toks):
        name, _, val = t.partition("=")
        nxt = toks[i + 1] if i + 1 < len(toks) else ""
        if name in ("-X", "--request", "--method") and (val or nxt).upper() in ("POST", "PUT", "PATCH", "DELETE"):
            return True
        if re.match(r"^-X(POST|PUT|PATCH|DELETE)$", t, re.I):
            return True
        if name in ("-d", "--data", "--data-binary", "--data-raw", "--data-urlencode", "-F", "--form", "-T",
                    "--upload-file", "--json", "--post-data", "--post-file", "--body-data", "--body-file"):
            return True
    return False


def route_mentions(segs, command):
    """Why-strings for every shipping route the command's tokens mention (empty list: none)."""
    found = []
    for seg in segs:
        toks = list(seg.tokens)
        prog, _ = program(toks)
        if prog in NON_EXEC:
            continue
        if (prog in SHELLS or prog in ("eval", "source", ".")) and RISKY.search(command):
            found.append("shell wrapper around a shipping route")
        for i, t in enumerate(toks):
            base = os.path.basename(t)
            if base == "git":
                sub, _, _, cfg = parse_git_globals(toks[i:])
                if sub == "push" or any(k.startswith("alias.") for k in cfg):
                    found.append("git push")
            elif base == "gh":
                if ghcmd.classify_gh(toks[i:])[0] not in ("read", "local"):
                    found.append("gh write/ship route")
            elif base == "maeng-ship" and "merge" in toks[i + 1:]:
                found.append("maeng-ship merge")
            elif base in ("curl", "wget") and _github_write(toks[i:]):
                found.append("direct GitHub API write")
    return found


def canonical_command(command, segs):
    """-> (form dict | None, why) for a command that mentions a shipping route."""
    if len(segs) != 1:
        return None, "it is compound (several segments, a substitution, or a control structure)"
    seg = segs[0]
    if seg.redirects:
        return None, "it has redirects"
    meta = unquoted_metachars(command)
    if meta:
        return None, "it uses shell syntax " + " ".join(sorted(repr(m) for m in meta))
    toks = seg.tokens
    if not toks or ENV_ASSIGN.match(toks[0]):
        return None, "it starts with an environment assignment"
    head = toks[0]
    base = os.path.basename(head)
    if head != base and not os.path.isabs(head):
        return None, "the program must be a bare name or an absolute path"
    if base == "git":
        return parse_canonical_push(toks)
    if base == "gh":
        return ghcmd.canonical_gh(toks)
    if base == "maeng-ship":
        return parse_canonical_ship(toks)
    return None, f"`{head}` is a wrapper or an unsupported program in front of a shipping route"
