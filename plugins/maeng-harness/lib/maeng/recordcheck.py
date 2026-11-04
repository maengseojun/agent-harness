"""Decisions checks on records work (MAE-320). records.py needs candidates from searches only the agent has, so a hook
cannot run it: the hook denies the create until the agent ran it. A run counts whatever Decisions answered."""
import os
import re
import time
from pathlib import Path

from .common import vault_dir

WINDOW = 1800  # shortcut: one check covers every create for 30 minutes, tighten if duplicates slip through
GENERATED = ("wiki/sessions/", "wiki/reviews/", "wiki/sources/", "raw/")  # machine-made notes
SCRIPT = "python3 <decisions skill>/scripts/records.py"
_RUN = re.compile(r"records\.py['\"]?\s+(related|duplicate)\b")


def off():
    return os.environ.get("MAENG_DECISIONS", "").strip().lower() == "off"


def ran(command):
    """-> "related" or "duplicate" when this Bash command runs that check, else None."""
    m = _RUN.search(command)
    return m[1] if m else None


def mark(st, check):
    st.setdefault("records_checks", {})[check] = time.time()


def _new_vault_note(path):
    vault = vault_dir().resolve()
    p = (vault / path).resolve()  # an absolute path replaces the vault part
    if p.suffix != ".md" or not p.is_relative_to(vault) or p.exists():
        return False
    return not p.relative_to(vault).as_posix().startswith(GENERATED)


def creates(tool, tin):
    """Does this call create a new Linear issue, Notion page or vault note?"""
    if tool.endswith("__save_issue"):
        return not tin.get("id")
    if tool.endswith("__notion-create-pages"):
        return True
    if tool == "mcp__obsidian_vault__write_note":
        return bool(tin.get("path")) and _new_vault_note(str(tin["path"]))
    if tool == "Write":
        p = str(tin.get("file_path") or "")
        return p.startswith("/") and _new_vault_note(p)
    return False


def duplicate_gate(tool, tin, st):
    """-> the deny reason, or None."""
    if off() or not isinstance(tool, str) or not isinstance(tin, dict) or not creates(tool, tin):
        return None
    if time.time() - (st.get("records_checks") or {}).get("duplicate", 0) <= WINDOW:
        return None
    return (f"maeng: run the duplicate check first: search for this item, then `{SCRIPT} duplicate --new \"<title and "
            f"one-line summary>\" --candidates <file>`. An empty candidate list is fine when the search found nothing.")


def related_missing(st):
    if off() or (st.get("records_checks") or {}).get("related"):
        return None
    return (f"maeng: run the related check first: search Linear, Notion and the vault for this task, then `{SCRIPT} "
            f"related --task \"<what you are about to do>\" --candidates <file>`. An empty candidate list is fine when "
            f"the search found nothing.")
