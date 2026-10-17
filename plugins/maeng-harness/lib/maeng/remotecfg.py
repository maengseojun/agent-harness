"""Plain-remote checks: a push or a repository binding is only trusted when the remote configuration is
unambiguous (one effective URL, no mirror/refspec/followTags expansion, known default branch)."""
import os
import re
import subprocess

from . import guard
from .canon import NAME_RE
from .common import git


def _bool(cwd, key):
    """-> (True|False, error)."""
    rc, out, _ = git(cwd, "config", "--type=bool", "--get", key)
    if rc == 1:
        return False, None
    if rc != 0:
        return False, f"cannot read {key}"
    return out.strip() == "true", None


def default_head(cwd, remote):
    """The remote's default branch from refs/remotes/<remote>/HEAD, or None when unknown."""
    rc, out, _ = git(cwd, "symbolic-ref", "-q", f"refs/remotes/{remote}/HEAD")
    prefix = f"refs/remotes/{remote}/"
    out = out.strip()
    return out[len(prefix):] if rc == 0 and out.startswith(prefix) else None


def _symref_head(cwd, url):
    """-> (branch | None, why): the destination's own default branch via `git ls-remote --symref <url> HEAD`.
    MAENG_GIT overrides the git binary (tests)."""
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")}
    env.update({"GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"})
    try:
        proc = subprocess.run([os.environ.get("MAENG_GIT", "git"), "ls-remote", "--symref", url, "HEAD"],
                              cwd=str(cwd), env=env, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)
    if proc.returncode != 0:
        return None, proc.stderr.strip()[:200] or f"ls-remote exited {proc.returncode}"
    for line in proc.stdout.splitlines():
        m = re.match(r"^ref:\s+refs/heads/(\S+)\s+HEAD$", line.strip())
        if m:
            return m.group(1), ""
    return None, "the remote did not report a symbolic HEAD"


def established_default_head(cwd, remote, url):
    """-> (branch | None, error). The default branch must be established from the effective remote and agree with
    refs/remotes/<remote>/HEAD; otherwise the caller denies."""
    hint = f"run `git remote set-head {remote} --auto`"
    local = default_head(cwd, remote)
    if local is None:
        return None, (f"maeng G1: the default branch of remote `{remote}` is unknown "
                      f"(refs/remotes/{remote}/HEAD missing); {hint}.")
    live, why = _symref_head(cwd, url)
    if live is None:
        return None, (f"maeng G1: cannot establish the default branch of remote `{remote}` from the remote "
                      f"itself ({why}); denied.")
    if live != local:
        return None, (f"maeng G1: remote `{remote}` default branch is `{live}` but refs/remotes/{remote}/HEAD says "
                      f"`{local}` (stale); {hint}, then retry.")
    return live, None


def plain_remote(cwd, remote, for_push=True):
    """-> (effective_url | None, error | None). `for_push` adds the push-only checks."""
    if not NAME_RE.match(remote or ""):
        return None, f"maeng G1: `{remote}` is not a configured remote name; use a named remote."
    rc, out, _ = git(cwd, "config", "--get-all", f"remote.{remote}.url")
    urls = out.splitlines() if rc == 0 else []
    if len(urls) != 1:
        return None, (f"maeng G1: remote `{remote}` must have exactly one url (found {len(urls)}); "
                      f"fix remote.{remote}.url.")
    rc, out, _ = git(cwd, "config", "--get-all", f"remote.{remote}.pushurl")
    if rc not in (0, 1):
        return None, f"maeng G1: cannot read remote.{remote}.pushurl."
    pushurls = out.splitlines() if rc == 0 else []
    if pushurls and (len(pushurls) != 1 or pushurls[0] != urls[0]):
        return None, (f"maeng G1: remote.{remote}.pushurl must be unset or equal to remote.{remote}.url "
                      f"(it names another push destination).")
    mirror, err = _bool(cwd, f"remote.{remote}.mirror")
    if err or mirror:
        return None, f"maeng G1: remote.{remote}.mirror is set; mirror remotes push every ref and are denied."
    rc, out, _ = git(cwd, "remote", "get-url", "--push", remote)
    effective = out.strip() if rc == 0 else ""
    if not effective:
        return None, f"maeng G1: cannot resolve the push url of remote `{remote}`."
    for u in (effective, urls[0]):
        if guard.remote_is_eta(u) or guard.spec_is_eta(u):
            return None, f"maeng G3: remote `{remote}` ({u}) is an eta repository; eta is a separate world."
    rc, out, _ = git(cwd, "remote", "get-url", remote)
    fetch_effective = out.strip() if rc == 0 else ""
    if not fetch_effective:
        return None, f"maeng G1: cannot resolve the fetch url of remote `{remote}`."
    if effective != urls[0] or fetch_effective != urls[0]:
        return None, (f"maeng G1: a url.<base>.insteadOf / pushInsteadOf rewrite applies to remote `{remote}` "
                      f"(configured {urls[0]}, fetch {fetch_effective}, push {effective}); fetch, push and PR-head "
                      f"verification would not use one URL. Remove the rewrite.")
    if for_push:
        rc, out, _ = git(cwd, "config", "--get-all", f"remote.{remote}.push")
        if rc != 1:
            return None, (f"maeng G1: remote.{remote}.push is configured; configured push refspecs expand the push. "
                          f"Unset it and push with an explicit refspec.")
        follow, err = _bool(cwd, "push.followTags")
        if err or follow:
            return None, "maeng G1: push.followTags is enabled; it pushes tags alongside the branch. Unset it."
        rc, out, _ = git(cwd, "config", "--get", "push.recurseSubmodules")
        if rc == 0 and out.strip().lower() in ("on-demand", "only"):
            return None, (f"maeng G1: push.recurseSubmodules={out.strip()} also pushes submodule commits to "
                          f"their own remotes, which are not verified. Unset it.")
        rec, err = _bool(cwd, "submodule.recurse")
        if err or rec:
            return None, ("maeng G1: submodule.recurse is enabled; a push would recurse into submodule remotes "
                          "that are not verified. Unset it.")
        _, err = established_default_head(cwd, remote, effective)
        if err:
            return None, err
    return effective, None
