"""Stdlib frontmatter parsing for skill name and description byte counts."""
import json
import re


def _frontmatter(text):
    lines = text.split("\n")
    if lines[0] != "---":
        raise ValueError("no opening ---")
    end = lines.index("---", 1)
    return lines[1:end]


def _value(first, cont):
    """The value of one top-level key: `first` is the text after `key:`, `cont` the indented lines under it."""
    if first[:1] in (">", "|"):
        lines = [c.strip() for c in cont]
        if first[0] == "|":
            return "\n".join(lines).strip("\n")
        paragraphs, cur = [], []
        for line in lines + [""]:
            if line:
                cur.append(line)
            elif cur:
                paragraphs.append(" ".join(cur))
                cur = []
        return "\n".join(paragraphs)
    raw = " ".join([first] + [c.strip() for c in cont]).strip()
    if raw.startswith('"'):
        return json.loads(raw)
    if raw.startswith("'"):
        return raw[1:-1].replace("''", "'")
    return raw


def _fields(block):
    """Top-level `name` and `description` values of a frontmatter block."""
    out = {}
    i = 0
    while i < len(block):
        m = re.match(r"^([A-Za-z_][\w-]*):(?:[ \t]+(.*))?$", block[i])
        i += 1
        if not m:
            continue
        cont = []
        while i < len(block) and (block[i][:1] in (" ", "\t") or not block[i].strip()):
            cont.append(block[i])
            i += 1
        while cont and not cont[-1].strip():
            cont.pop()
        if m.group(1) in ("name", "description"):
            out[m.group(1)] = _value((m.group(2) or "").rstrip(), cont)
    return out
