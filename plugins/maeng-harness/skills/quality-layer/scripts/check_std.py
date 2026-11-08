#!/usr/bin/env python3
"""Validate genre-standard conditions and their locally stored source quotes."""
import argparse
from datetime import date
from pathlib import Path
import re


def normalized(text):
    return " ".join(text.split())


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
    for number, line in enumerate(text.splitlines(), 1):
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if heading and len(heading[1]) <= 2:
            section = len(heading[1]) == 2 and heading[2] in ("Conditions", "조건")
            found |= section
        elif section and line.startswith("- "):
            conditions.append((number, [field.strip() for field in line[2:].split(" | ")]))
    if not found:
        out.append((1, "no Conditions section"))
    if not conditions:
        out.append((1, "zero conditions"))
    if len(conditions) > 7:
        out.append((conditions[7][0], "more than 7 conditions"))

    quotes = 0
    for number, fields in conditions:
        if len(fields) < 4:
            out.append((number, "missing condition fields or tag"))
            continue
        identifier, stamp, status, tag = fields[:4]
        if not re.fullmatch(r"S[1-9][0-9]*", identifier):
            out.append((number, "bad condition id"))
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
                original = (path.parent / filename).read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
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
