"""`gh` command parsing/classification and the canonical `gh pr create` form."""
import os
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
# Destructive remote operations, denied everywhere even where the group is otherwise open (`gh issue *`).
DENIED_ACTIONS = {"issue": {"delete"}, "repo": {"delete", "archive", "unarchive", "rename", "edit"},
                  "release": {"delete", "delete-asset", "create", "edit", "upload"}}
READ_ACTIONS = {"view", "list", "diff", "checks", "status", "watch", "token", "get", "check",
                "search", "browse"}
# Remote reads that also write files into the local working directory / a destination operand.
LOCAL_WRITES = {("pr", "checkout"), ("repo", "clone"), ("repo", "set-default"), ("release", "download"), ("run", "download"),
                ("gist", "clone")}
# The closed known surface, derived from GH_ALLOWED and pinned by equality in the tests: GH_OPEN_GROUPS take any
# action (`issue` writes everything except DENIED_ACTIONS; the others only read), GH_WRITES are the known remote
# writes of the closed groups (`pr create` is GH_GATED), LOCAL_WRITES write files locally, GH_READS is the rest.
# Anything else (repo create, gist create, variable set, label create, project, codespace, auth login, ...) is denied.
GH_OPEN_GROUPS = frozenset(g for g, acts in GH_ALLOWED.items() if acts is None)
WRITE_ACTIONS = ("comment", "edit", "review", "ready", "close")
GH_WRITES = frozenset((g, a) for g, acts in GH_ALLOWED.items() for a in acts or () if a in WRITE_ACTIONS)
GH_GATED = frozenset({("pr", "create")})
GH_READS = frozenset((g, a) for g, acts in GH_ALLOWED.items() for a in acts or ()) - GH_WRITES - LOCAL_WRITES
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
GH_VALUE_FLAGS = {"--preview", "-X", "--method", "-H", "--header", "-f", "-F", "--field", "--raw-field", "-q", "--jq", "-t",
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


def gh_aliases():
    """Names of the aliases in the user's gh config (`aliases:` mapping of config.yml), else an empty set."""
    base = os.environ.get("GH_CONFIG_DIR") or (os.path.join(os.environ["XDG_CONFIG_HOME"], "gh")
                                               if os.environ.get("XDG_CONFIG_HOME")
                                               else os.path.join(os.path.expanduser("~"), ".config", "gh"))
    names, inside = set(), False
    try:
        with open(os.path.join(base, "config.yml"), encoding="utf-8") as f:
            for line in f:
                if re.match(r"^aliases:\s*$", line):
                    inside = True
                elif inside and re.match(r"^\S", line):
                    inside = False
                elif inside:
                    m = re.match(r"^\s+['\"]?([^:'\"\s]+)['\"]?\s*:", line)
                    if m:
                        names.add(m.group(1))
    except OSError:
        pass
    return names


def parse_gh(toks):
    args = toks[1:]
    info = {"repo": None, "pos": [], "flags": {}, "method": None, "fields": [], "raw": [], "typed": [],
            "input": False}
    i = 0
    while i < len(args):
        t = args[i]
        name, eq, val = t.partition("=")
        if t in ("-R", "--repo") or name == "--repo":
            info["repo"] = val if eq else (args[i + 1] if i + 1 < len(args) else None)
            i += 0 if eq else 1
        elif re.match(r"^-X=?[A-Za-z]+$", t):
            info["method"] = t[2:].lstrip("=").upper()
        elif t in ("-X", "--method") or name == "--method":
            v = val if eq else (args[i + 1] if i + 1 < len(args) else "")
            info["method"] = v.upper(); i += 0 if eq else 1
        elif t in ("-f", "-F", "--field", "--raw-field") or name in ("--field", "--raw-field"):
            v = val if eq else (args[i + 1] if i + 1 < len(args) else "")
            info["fields"].append(v)
            info["raw" if t in ("-f", "--raw-field") or name == "--raw-field" else "typed"].append(v)
            i += 0 if eq else 1
        elif t.startswith(("-f", "-F")) and len(t) > 2 and t[2] != "-":
            v = t[2:].removeprefix("=")  # pflag accepts -Fk=v and -F=k=v
            info["fields"].append(v)
            info["raw" if t.startswith("-f") else "typed"].append(v)
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
    if group == "pr" and action == "close" and (info["flags"].get("--delete-branch") or info["flags"].get("-d")):
        return "deny", "`gh pr close --delete-branch` deletes the remote head branch and is denied.", repo, info
    if group in DENIED_ACTIONS and action in DENIED_ACTIONS[group]:
        return "deny", f"`gh {group} {action}` is a destructive remote operation and is denied.", repo, info
    if group not in GH_ALLOWED:
        if group in gh_aliases():
            return "deny", (f"`gh {group}` is a user-defined gh alias (it can expand to `pr merge` or any other "
                            f"route); gh aliases are not allowed, run the underlying command."), repo, info
        return "deny", f"`gh {group}` is not a known gh command (fail closed; not on the G1 allowlist).", repo, info
    if group == "alias" and action != "list":
        return "deny", f"`gh alias {action or ''}` is denied: gh aliases can hide merge/push routes.", repo, info
    allowed = GH_ALLOWED[group]
    if allowed is not None and action not in allowed:
        return "deny", f"`gh {group} {action or ''}` is not on the G1 allowlist " \
                       f"(merge/sync/release/repo-edit routes go through maeng-ship or are denied).", repo, info
    if (group, action) in LOCAL_WRITES:
        return "local", "", repo, info
    if group in ("issue",) or (group, action) in GH_WRITES:
        return ("read" if action in READ_ACTIONS else "write"), "", repo, info
    return "read", "", repo, info


_SUBST = re.compile(r"\$\(|`")
_WHOLE_VAR = re.compile(r"^\$\{?\w+\}?$")


def _graphql_uninspectable(info):
    """-> why this GraphQL call's content cannot be read from the command line, else ''."""
    if info["input"]:
        return "--input hides the request body"
    raw = {f.partition("=")[0]: f.partition("=")[2] for f in info["raw"]}
    if "query" not in raw:
        return "the query is not a literal -f/--raw-field query=<text>"
    for v in info["fields"]:
        if v.partition("=")[2].startswith("@") or _SUBST.search(v) or _WHOLE_VAR.match(v.partition("=")[2]):
            return "a field value comes from a file or a substitution"
    if any(f.partition("=")[0] == "query" for f in info["typed"]):
        return "the query is passed with -F/--field"
    if re.search(r"\bmutation\b|createCommitOnBranch|mergePullRequest", raw["query"], re.I):
        return "GraphQL mutations (createCommitOnBranch, mergePullRequest, ...) are denied"
    return ""


def _classify_api(info):
    pos = info["pos"]
    endpoint = pos[1] if len(pos) > 1 else ""
    repo = info["repo"] or _api_repo(endpoint)
    if endpoint == "graphql":
        why = _graphql_uninspectable(info)
        if why:
            return "deny", (f"`gh api graphql` is denied: {why}. Only an inspectable literal "
                            f"`-f query='query {{ ... }}'` (no mutation, no @file, no --input, no substitution) is "
                            f"allowed."), repo, info
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


STRICT_READ = {"pr": {"view", "list", "diff", "checks", "status"}, "issue": {"view", "list", "status"},
               "repo": {"view"}, "run": {"view", "list"}, "release": {"view", "list"},
               "workflow": {"view", "list"}}


def readonly_strict(toks):
    """The closed read-only gh allowlist used under G3 taint: pr/issue view|list|diff|checks|status, repo view and
    `gh api` GET without -f/-F/--input/-X non-GET, plus run/release/workflow view|list. Anything else is not read-only."""
    from .readonly import gh_options_ok
    info = parse_gh(toks)
    pos = info["pos"]
    if not pos or not gh_options_ok(info):
        return False
    if pos[0] == "api":
        if len(pos) > 1 and pos[1] == "graphql":  # an inspectable literal query only reads
            return not _graphql_uninspectable(info)
        if info["fields"] or info["input"]:
            return False
        if info["method"] not in (None, "GET"):
            return False
        return len(pos) > 1 and pos[1] != "graphql"
    return len(pos) > 1 and pos[1] in STRICT_READ.get(pos[0], ())
