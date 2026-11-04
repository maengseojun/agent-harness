"""Merge-quiz truth: patch ids, a throwaway clone, execution-backed items and keyed grading."""
from .common import git


def patch_id(cwd, base, head):
    """The stable patch id of base...head, equal across a rebase that keeps the diff; None when it cannot be read."""
    rc, diff, _ = git(cwd, "diff", "--no-ext-diff", "--no-textconv", "--no-renames", f"{base}...{head}")
    if rc != 0 or not diff:
        return None
    rc, out, _ = git(cwd, "patch-id", "--stable", input_text=diff)
    return out.split()[0] if rc == 0 and out.split() else None
