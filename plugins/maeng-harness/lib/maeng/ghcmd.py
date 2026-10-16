"""`gh` command parsing/classification and the canonical `gh pr create` form."""
import re

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
READ_ACTIONS = {"view", "list", "diff", "checks", "status", "watch", "set-default", "token", "get", "check",
                "search", "browse"}
# Remote reads that also write files into the local working directory / a destination operand.
LOCAL_WRITES = {("pr", "checkout"), ("repo", "clone"), ("release", "download"), ("run", "download"),
                ("gist", "clone")}
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
GH_VALUE_FLAGS = {"-X", "--method", "-H", "--header", "-f", "-F", "--field", "--raw-field", "-q", "--jq", "-t",
                  "--template", "--hostname", "--cache", "--input", "-B", "--base", "-H", "--head", "-t", "--title",
                  "-b", "--body", "-F", "--body-file", "-a", "--assignee", "-l", "--label", "-m", "--milestone",
                  "-r", "--reviewer", "-p", "--project", "--jq", "-D", "--dir", "-O", "--output", "-A", "--archive",
                  "--pattern", "-n", "--name"}
URL_REPO = re.compile(r"(?:https?://)?(?:www\.)?(?:api\.)?github\.com/(?:repos/)?([^/\s]+)/([^/\s#?]+)", re.I)
API_REPO = re.compile(r"^/?repos/([^/]+)/([^/]+)")

PR_CREATE_VALUE = {"--base": "base", "-B": "base", "--head": "head", "-H": "head", "--title": "title", "-t": "title",
                   "--body": "body", "-b": "body", "--body-file": "body_file", "-F": "body_file", "--repo": "repo",
                   "-R": "repo"}
PR_CREATE_BOOL = {"--draft", "-d"}


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
    m = API_REPO.match(endpoint or "") or URL_REPO.search(endpoint or "")
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
    if (group, action) in LOCAL_WRITES:
        return "local", "", repo, info
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


def target_repos(info):
    """Every repository a gh call names: -R/--repo, GitHub URL positionals, API endpoint paths."""
    out = []
    if info["repo"]:
        out.append(info["repo"])
    for p in info["pos"]:
        m = URL_REPO.search(p) or API_REPO.match(p)
        if m:
            out.append(f"{m.group(1)}/{m.group(2)}")
    return out


def local_destinations(info):
    """Paths a local-write gh command writes to beyond the working directory: --dir/-D, --output/-O and the
    clone destination operand."""
    out = []
    for flag in ("-D", "--dir", "-O", "--output"):
        v = info["flags"].get(flag)
        if isinstance(v, str) and v:
            out.append(v)
    pos = info["pos"]
    if len(pos) > 3 and pos[1] == "clone":
        out.append(pos[3])
    return out


def parse_pr_create(toks):
    """Canonical `gh pr create` -> ({base, head, title, body, body_file, repo, draft}, why)."""
    if toks[1:3] != ["pr", "create"]:
        return None, "`gh pr create` must be written exactly like that (no global flags before `pr create`)"
    out = {"base": None, "head": None, "title": None, "body": None, "body_file": None, "repo": None, "draft": False}
    args, i = toks[3:], 0
    while i < len(args):
        t = args[i]
        name, eq, val = t.partition("=")
        if t in PR_CREATE_BOOL:
            out["draft"] = True
        elif name in PR_CREATE_VALUE and name.startswith("--") and eq:
            out[PR_CREATE_VALUE[name]] = val
        elif t in PR_CREATE_VALUE:
            if i + 1 >= len(args):
                return None, f"`{t}` needs a value"
            out[PR_CREATE_VALUE[t]] = args[i + 1]
            i += 1
        else:
            return None, f"`gh pr create` flag/argument `{t}` is not allowed (only --base --head --title --body " \
                         f"--body-file --draft --repo)"
        i += 1
    return out, ""


def canonical_gh(toks):
    """-> ({'form': 'gh-pr-create'|'gh-write', ...} | None, why) for a single plain gh command."""
    kind, reason, _, info = classify_gh(toks)
    if kind == "create":
        parsed, why = parse_pr_create(toks)
        if parsed and not (parsed["repo"] and REPO_RE.match(parsed["repo"])):
            return None, "`gh pr create` needs an explicit `--repo <owner/repo>` equal to origin"
        return ({"form": "gh-pr-create", **parsed} if parsed else None), why
    if kind == "write" and info["pos"][0] != "api":
        if not (info["repo"] and REPO_RE.match(info["repo"])):
            return None, (f"`gh {' '.join(info['pos'][:2])}` writes need an explicit `-R <owner/repo>` "
                          f"(gh would otherwise pick the repository from GH_REPO or its configured default)")
        return {"form": "gh-write", "repos": target_repos(info)}, ""
    if kind == "local":
        return {"form": "gh-local", "repos": target_repos(info)}, ""
    if kind == "read":
        return {"form": "gh-read", "repos": target_repos(info)}, ""
    return None, reason or "this gh command is not on the G1 allowlist"
