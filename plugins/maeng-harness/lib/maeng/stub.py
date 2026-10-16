"""Obsidian session stub: unique id, atomic write, readback."""
import time

from .common import atomic_write, git_out, now_iso, vault_dir


def _stub_name(st):
    issue = (st.get("binding") or {}).get("issue") or "none"
    return f"SESSION-{issue}-{time.strftime('%Y%m%d-%H%M')}-{str(st['session_id'])[:8]}"


def _body(st, status, notes):
    lines = [f"# Session {st['session_id'][:8]}", "", f"Status: {status}", ""]
    ev = st.get("evidence", [])
    lines.append("## Evidence")
    lines += [f"- {'ok' if e['ok'] else 'FAIL'} `{e['check']}` tree {str(e['tree_finish'])[:8]}" for e in ev[-20:]] or ["- none"]
    if st.get("skips"):
        lines += ["", "## Skips"] + [f"- {s['reason']}" for s in st["skips"]]
    if st.get("decisions"):
        lines += ["", "## Decisions"] + [f"- {d['text']}" for d in st["decisions"]]
    if notes:
        lines += ["", "## Open"] + [f"- {n}" for n in notes]
    return "\n".join(lines) + "\n"


def write(st, status="in-progress", notes=(), ended=False):
    """Create or refresh the stub. Returns the path, or None when no vault exists."""
    vault = vault_dir()
    if not vault.is_dir():
        return None
    meta = st.get("stub") or {}
    name = meta.get("id")
    if not name:
        name = _stub_name(st)
        base, n = name, 1
        while (vault / "wiki/sessions" / (name + ".md")).exists():
            n += 1
            name = f"{base}-{n}"
        meta = {"id": name, "started": now_iso()}
    issue = (st.get("binding") or {}).get("issue")
    head = git_out(st.get("cwd") or ".", "rev-parse", "--short", "HEAD") if st.get("cwd") else None
    fm = ["---", f"id: {name}", "type: session", "world: personal", f"session: {st['session_id']}",
          f"linear: [{issue}]" if issue else "linear: []", f"commit: {head or ''}", f"started: {meta['started']}",
          f"updated: {now_iso()}"]
    if ended:
        fm.append(f"ended: {now_iso()}")
        # SessionEnd carries no obligations of its own: keep the last Stop's open items.
        notes = notes or meta.get("open", [])
        if meta.get("last_status") not in (None, "ok"):
            status = f"ended ({meta['last_status']})"
    else:
        meta["open"], meta["last_status"] = list(notes), status
    fm.append("---")
    text = "\n".join(fm) + "\n\n" + _body(st, status, notes)
    path = vault / "wiki/sessions" / (name + ".md")
    atomic_write(path, text)
    if path.read_text(encoding="utf-8") != text:
        raise OSError("session stub readback mismatch")
    st["stub"] = meta
    return path
