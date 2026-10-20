# PR 60 Spec/Plan: gdrive store defaults to the school Drive (MAE-257)

Goal: user decision 2026-10-21. All Drive use stays on the school account 2025131619@korea.ac.kr for now; move to the personal Drive later in one go. Drop the googledrive-maeng/googledrive-school MCP plan.

AC-1: with no MAENG_ARCHIVE_GDRIVE, store_root("gdrive") returns GoogleDrive-2025131619@korea.ac.kr/<My Drive|내 드라이브> when it exists, even when another GoogleDrive-* sorts first; without it the first sorted GoogleDrive-* is used; MAENG_ARCHIVE_GDRIVE overrides. Check: `python3 -m pytest -q plugins/maeng-tools/skills/maeng-archive/scripts/test_archive.py` passes.
AC-2: maeng-archive/SKILL.md and work-records/SKILL.md name the school Drive as the gdrive store and the claude.ai connector (school) as the read path; no googledrive-maeng/googledrive-school references remain. Check: `grep -rn 'googledrive-maeng\|googledrive-school' plugins` returns nothing.
AC-3: full suite passes. Check: `python3 -m pytest -q`.
