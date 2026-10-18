"""git argument parsing for the G1 push check, and maeng-ship's exact lease push form."""
import re

SHA_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
LEASE_RE = re.compile(r"^--force-with-lease=(refs/heads/[^:\s]+):([0-9a-f]{40}(?:[0-9a-f]{24})?)$")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


# ---- git ------------------------------------------------------------------

def parse_git_globals(toks):
    """-> (subcommand, args_after, dirs, config_overrides); dirs = [(kind, path)] kind in C|git-dir|work-tree."""
    i, dirs, cfg = 1, [], {}
    while i < len(toks):
        t = toks[i]
        if t == "-C" and i + 1 < len(toks):
            dirs.append(("C", toks[i + 1])); i += 2
        elif t == "-c" and i + 1 < len(toks):
            k, sep, v = toks[i + 1].partition("=")
            cfg.setdefault(k.lower(), []).append(v if sep else None); i += 2  # None: value-less `-c k` (git: true)
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
