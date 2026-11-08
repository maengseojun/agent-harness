#!/usr/bin/env python3
"""Validate genre-standard conditions and their locally stored source quotes.

Relative sources must resolve within the standard directory's parent (e.g. the
wiki root), allowing sibling drafts but rejecting escapes, including symlinks.
"""
import argparse
from datetime import date
from pathlib import Path
import re


def normalized(text):
    return " ".join(text.split())


def unfenced_lines(text):
    """Yield original line numbers and text outside backtick or tilde fences."""
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            if (marker and marker[1][0] == fence[0]
                    and len(marker[1]) >= len(fence) and not marker[2].strip()):
                fence = None
            continue
        if marker and (marker[1][0] == "~" or "`" not in marker[2]):
            fence = marker[1]
            continue
        yield number, line


def problems(path):
    """Return (line number, problem) pairs for one Markdown standard."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [(1, f"cannot read standard: {exc}")]
    if not text.strip():
        return [(1, "empty standard")]

    out = []
    section = False
    found = False
    conditions = []
    for number, line in unfenced_lines(text):
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if heading and len(heading[1]) <= 2:
            section = len(heading[1]) == 2 and heading[2] in ("Conditions", "조건")
            found |= section
        elif section and line.startswith("- "):
            conditions.append((number, [field.strip() for field in line[2:].split(" | ", 4)]))
    if not found:
        out.append((1, "no Conditions section"))
    if not conditions:
        out.append((1, "zero conditions"))
    if len(conditions) > 7:
        out.append((conditions[7][0], "more than 7 conditions"))

    quotes = 0
    identifiers = set()
    for number, fields in conditions:
        if len(fields) < 4:
            out.append((number, "missing condition fields or tag"))
            continue
        identifier, stamp, status, tag = fields[:4]
        if not re.fullmatch(r"S[1-9][0-9]*", identifier):
            out.append((number, "bad condition id"))
        if identifier in identifiers:
            out.append((number, "duplicate condition id"))
        identifiers.add(identifier)
        try:
            if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", stamp):
                raise ValueError
            date.fromisoformat(stamp)
        except ValueError:
            out.append((number, "bad condition date"))
        if status not in ("current", "stale"):
            out.append((number, "bad condition status"))

        source = tag.startswith("source:")
        if tag not in ("user", "author") and not source:
            out.append((number, f"unknown condition tag: {tag or '(empty)'}"))
            continue
        expected = 5 if tag == "author" else 6
        if len(fields) == 5:
            tail = fields[4].split(" | ") if tag == "author" else fields[4].rsplit(" | ", 1)
            fields = fields[:4] + [field.strip() for field in tail]
        if len(fields) != expected:
            out.append((number, f"expected {expected} fields for {tag}"))
            continue
        if not fields[-1]:
            out.append((number, "empty condition sentence"))
        if tag == "author":
            continue
        quoted = fields[4]
        if len(quoted) < 3 or not quoted.startswith('"') or not quoted.endswith('"') or not quoted[1:-1].strip():
            out.append((number, "missing or empty quoted text"))
            continue
        quotes += 1
        if source:
            filename = tag[len("source:"):].strip()
            if not tag.startswith("source: ") or not filename or Path(filename).is_absolute():
                out.append((number, "source path must be relative to the standard directory"))
                continue
            try:
                directory = path.parent.resolve()
                source_path = (directory / filename).resolve()
                if not source_path.is_relative_to(directory.parent):
                    out.append((number, "source path escapes the standard directory's parent"))
                    continue
                original = source_path.read_text(encoding="utf-8")
            except (OSError, UnicodeError, RuntimeError) as exc:
                out.append((number, f"cannot read source: {exc}"))
                continue
            if normalized(quoted[1:-1]) not in normalized(original):
                out.append((number, "quote absent from source"))
    if not quotes:
        out.append((1, "zero source or user quotes"))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()
    failed = False
    for path in args.files:
        for line, problem in problems(path):
            print(f"{path}:{line}: {problem}")
            failed = True
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
