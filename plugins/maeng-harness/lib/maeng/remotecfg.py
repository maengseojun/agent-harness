"""Plain-remote checks: a push or a repository binding is only trusted when the remote configuration is
unambiguous (one effective URL, no mirror/refspec/followTags expansion, known default branch)."""
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
    if for_push:
        rc, out, _ = git(cwd, "config", "--get-all", f"remote.{remote}.push")
        if rc != 1:
            return None, (f"maeng G1: remote.{remote}.push is configured; configured push refspecs expand the push. "
                          f"Unset it and push with an explicit refspec.")
        follow, err = _bool(cwd, "push.followTags")
        if err or follow:
            return None, "maeng G1: push.followTags is enabled; it pushes tags alongside the branch. Unset it."
        if default_head(cwd, remote) is None:
            return None, (f"maeng G1: the default branch of remote `{remote}` is unknown "
                          f"(refs/remotes/{remote}/HEAD missing); run `git remote set-head {remote} --auto`.")
    return effective, None
