#!/usr/bin/env python3
"""Linear, Notion and vault records with the Decisions API (MAE-306 / MAE-311, AC-8). Stdlib only.

  records.py related   --task TEXT --candidates FILE [--threshold 0.5]
      Which items should someone doing the task read? One predicate per item; prints the selected
      items by probability, the 3 nearest misses, and the ids that were not judged.
  records.py duplicate --new TEXT --candidates FILE
      Is the new item the same thing as one of the existing items? One choice question (the ids plus
      `none`); names a candidate for Claude to open before deciding. At most 254 candidates.
  records.py cleanup   --candidates FILE [--threshold 0.6]
      Which items look superseded or done? One predicate per item; suggestions only.

FILE is a JSON list of {"id", "title", "text", "source", "path"?, "world"?, "date"?}; `source` is
linear, notion or obsidian (free text such as "linear-maeng" is fine). Claude builds it from search
results. Nothing is written, created, changed or closed: output is stdout only (A-10).

Data rule (A-9). An item is dropped before any request, and its id is printed, when its `world` is
eta, when any segment of its `path` is eta or endix (a vault `eta/` folder, an imported eta Notion
or Linear folder, an eta checkout), or when its `source` names eta ("notion-eta"). If every item is
dropped nothing is sent. Every title and text, and the task or new text, goes through the vault's
strip_private first; each item's text is then cut to --max-item-chars (default 4000). `unknown`
answers (error, timeout, refusal, missing or off-list) are never selected, never named as a
duplicate and never listed as a cleanup suggestion. Pilot name: records.
"""
import argparse
import json
import posixpath
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.append(str(HERE.parent.parent / "obsidian-workspace" / "scripts"))
import decisions_client  # noqa: E402
from private_filter import strip_private  # noqa: E402

DECIDE = decisions_client.decide  # tests replace this
PILOT = "records"
MAX_ITEM_CHARS = 4000
MAX_PREDICATES = 400  # the client's limit per request
MAX_CHOICES = 254  # plus `none`
NONE = "none"
NONE_DESC = "None of the items is the same thing as the new one."

# eta as a word ("notion-eta", "eta_v1", "Eta-2026") or camel-cased ("notionEta"), never "beta" or "meta"
_WORD = re.compile(r"(?<![a-z0-9])(?:eta|endix)(?![a-z0-9])", re.I)
_CAMEL = re.compile(r"(?<=[a-z])(?:Eta|Endix)(?![a-z])")


def _eta_text(s):
    return bool(_WORD.search(s) or _CAMEL.search(s))


def is_eta_path(path):
    """True when any segment of the path is eta or endix. shortcut: stricter than "eta/ at the
    vault root" on purpose (imported eta notes live under wiki/sources/imported/); a false hit only drops."""
    p = posixpath.normpath(str(path or "").replace("\\", "/").strip())
    return any(_eta_text(seg) for seg in p.split("/"))


def refusal(c):
    """Why an item must never be sent, or None."""
    if str(c.get("world") or "").strip().lower() == "eta":
        return "world eta"
    if is_eta_path(c.get("path")):
        return "path in an eta area"
    if _eta_text(str(c.get("source") or "")):
        return "source eta"
    return None


def _clean(s):
    return strip_private(str(s or ""))[0]


def prepare(candidates, max_item_chars=MAX_ITEM_CHARS):
    """-> (items to send, [(id, reason)] dropped). Raises ValueError for a malformed list."""
    if not isinstance(candidates, list) or not all(isinstance(c, dict) for c in candidates):
        raise ValueError("candidates must be a list of objects")
    ids = [str(c.get("id") or "") for c in candidates]
    if not all(ids) or len(set(ids)) != len(ids):
        raise ValueError("every candidate needs a unique non-empty id")
    items, dropped = [], []
    for c, id_ in zip(candidates, ids):
        reason = refusal(c)
        if reason:
            dropped.append((id_, reason))
            continue
        items.append({"id": id_, "title": _clean(c.get("title")), "source": str(c.get("source") or "unknown"),
                      "date": str(c.get("date") or "undated"), "text": _clean(c.get("text"))[:max_item_chars]})
    return items, dropped


def load_candidates(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _render(items):
    return "\n\n".join(f"[{i['id']}] {i['title']} ({i['source']}, {i['date']})\n{i['text']}" for i in items)


def _name(n, id_):
    return f"i{n}_" + re.sub(r"[^A-Za-z0-9_-]", "_", id_)[:40]  # the index keeps it unique


def _probability(a):
    p = a.get("probability") if isinstance(a, dict) and a.get("status") == "ok" else None
    return p if isinstance(p, (int, float)) and not isinstance(p, bool) and 0 <= p <= 1 else None


def _predicates(items, text, instruction, decide, pilot):
    """One predicate per item -> (scored [(item, p)] by p descending, [unknown ids], [unknown reasons])."""
    if len(items) > MAX_PREDICATES:
        raise ValueError(f"at most {MAX_PREDICATES} candidates per request, got {len(items)}; split the file")
    qs = [{"type": "predicate", "name": _name(n, i["id"]), "instructions": instruction.format(id=i["id"])}
          for n, i in enumerate(items, 1)]
    got = {a.get("name"): a for a in (decide or DECIDE)(text, qs, pilot) if isinstance(a, dict)}
    scored, unknown, reasons = [], [], []
    for i, q in zip(items, qs):
        a = got.get(q["name"])
        p = _probability(a)
        if p is None:
            unknown.append(i["id"])
            reasons.append((a or {}).get("reason") or "no verdict")
        else:
            scored.append((i, p))
    return sorted(scored, key=lambda x: -x[1]), unknown, sorted(set(reasons))


def related(task, candidates, threshold=0.5, *, decide=None, max_item_chars=MAX_ITEM_CHARS, pilot=PILOT):
    items, dropped = prepare(candidates, max_item_chars)
    out = {"sent": bool(items), "selected": [], "near": [], "unknown": [], "reasons": [], "dropped": dropped}
    if items:
        text = f"Task:\n{_clean(task)}\n\nItems:\n{_render(items)}"
        scored, out["unknown"], out["reasons"] = _predicates(
            items, text, "Is item [{id}] relevant to the task above, so that someone doing the task should read it?", decide, pilot)
        out["selected"] = [(i, p) for i, p in scored if p >= threshold]
        out["near"] = [(i, p) for i, p in scored if p < threshold][:3]
    return out


def cleanup(candidates, threshold=0.6, *, decide=None, max_item_chars=MAX_ITEM_CHARS, pilot=PILOT):
    items, dropped = prepare(candidates, max_item_chars)
    out = {"sent": bool(items), "suggested": [], "unknown": [], "reasons": [], "dropped": dropped}
    if items:
        scored, out["unknown"], out["reasons"] = _predicates(
            items, f"Items:\n{_render(items)}",
            "According to its own text and the other items listed, is item [{id}] superseded by a newer item "
            "or already done, so it can be archived or closed?", decide, pilot)
        out["suggested"] = [(i, p) for i, p in scored if p >= threshold]
    return out


def duplicate(new, candidates, *, decide=None, max_item_chars=MAX_ITEM_CHARS, pilot=PILOT):
    """-> {"status": "not_sent" | "unknown" | "ok", "chosen": id | "none" | None, "p", "runner_up": (id, p) | None,
    "dropped", "items"}. Raises ValueError for more than 254 candidates or a candidate with the id `none`."""
    items, dropped = prepare(candidates, max_item_chars)
    if len(items) > MAX_CHOICES:
        raise ValueError(f"at most {MAX_CHOICES} candidates for a duplicate check, got {len(items)}; narrow the search")
    if any(i["id"] == NONE for i in items):
        raise ValueError(f"the candidate id {NONE!r} is reserved for the no-duplicate choice")
    out = {"status": "not_sent", "chosen": None, "p": None, "runner_up": None, "dropped": dropped, "items": items}
    if not items:
        return out
    valid = {i["id"] for i in items} | {NONE}
    q = {"type": "choice", "name": "duplicate_of", "instructions":
         "Is the new item described above the same thing as one of the existing items "
         "(a duplicate that should be updated instead of created)?",
         "choices": [{"value": i["id"], "description": i["title"] or i["id"]} for i in items]
         + [{"value": NONE, "description": NONE_DESC}]}
    text = f"New item:\n{_clean(new)}\n\nExisting items:\n{_render(items)}"
    got = {a.get("name"): a for a in (decide or DECIDE)(text, [q], pilot) if isinstance(a, dict)}
    a = got.get("duplicate_of")
    if not (isinstance(a, dict) and a.get("status") == "ok" and a.get("choice") in valid):
        out["status"] = "unknown"
        return out
    probs = {x.get("value"): x.get("probability") for x in (a.get("probabilities") or []) if isinstance(x, dict)}
    num = lambda v: v if isinstance(v, (int, float)) and not isinstance(v, bool) else None
    out.update(status="ok", chosen=a["choice"], p=num(probs.get(a["choice"])))
    rest = [(v, num(p)) for v, p in probs.items() if v in valid and v != a["choice"] and num(p) is not None]
    out["runner_up"] = max(rest, key=lambda x: x[1]) if rest else None
    return out


def _p(p):
    return "-" if p is None else f"{p:.2f}"


def _line(i, p):
    return f"  {_p(p)} [{i['id']}] {i['title']} ({i['source']}, {i['date']})"


def _show_dropped(dropped):
    for id_, why in dropped:
        print(f"dropped, not sent: {id_} ({why})")


def _show_unknown(res):
    if res["unknown"]:
        print("unknown, not judged: " + ", ".join(res["unknown"]))
        print("records: unknown answers: " + ", ".join(res["reasons"]), file=sys.stderr)


def cmd_related(a, cands):
    r = related(a.task, cands, a.threshold, max_item_chars=a.max_item_chars)
    _show_dropped(r["dropped"])
    if not r["sent"]:
        return print("nothing was sent: no candidate left")
    print(f"selected (probability >= {a.threshold:g}), read these:")
    print("\n".join(_line(i, p) for i, p in r["selected"]) or "  none")
    if r["near"]:
        print("near misses (below the threshold):\n" + "\n".join(_line(i, p) for i, p in r["near"]))
    _show_unknown(r)


def cmd_cleanup(a, cands):
    r = cleanup(cands, a.threshold, max_item_chars=a.max_item_chars)
    _show_dropped(r["dropped"])
    if not r["sent"]:
        return print("nothing was sent: no candidate left")
    print(f"cleanup suggestions (probability >= {a.threshold:g}); suggestions only, nothing is archived or closed:")
    print("\n".join(_line(i, p) for i, p in r["suggested"]) or "  none")
    _show_unknown(r)


def cmd_duplicate(a, cands):
    r = duplicate(a.new, cands, max_item_chars=a.max_item_chars)
    _show_dropped(r["dropped"])
    title = {i["id"]: i["title"] for i in r["items"]}
    named = lambda v, p: f"none (probability {_p(p)})" if v == NONE else f"[{v}] {title[v]} (probability {_p(p)})"
    if r["status"] == "not_sent":
        print("nothing was sent: no candidate left")
    elif r["status"] == "unknown":
        print("no judgment (unknown)")
    else:
        c = r["chosen"]
        print(f"{'no duplicate named' if c == NONE else 'duplicate candidate'}: {named(c, r['p'])}")
        print("runner-up: " + (named(*r["runner_up"]) if r["runner_up"] else "none listed"))
        if c != NONE:
            print("open it before deciding")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="records.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--candidates", required=True, metavar="FILE")
    common.add_argument("--max-item-chars", type=int, default=MAX_ITEM_CHARS)
    p = sub.add_parser("related", parents=[common], help="pick the items worth reading for a task")
    p.add_argument("--task", required=True)
    p.add_argument("--threshold", type=float, default=0.5)
    p.set_defaults(run=cmd_related)
    p = sub.add_parser("duplicate", parents=[common], help="is the new item a duplicate of an existing one")
    p.add_argument("--new", required=True)
    p.set_defaults(run=cmd_duplicate)
    p = sub.add_parser("cleanup", parents=[common], help="list items that look superseded or done")
    p.add_argument("--threshold", type=float, default=0.6)
    p.set_defaults(run=cmd_cleanup)
    a = ap.parse_args(argv)
    if a.max_item_chars < 1:
        ap.error("--max-item-chars must be >= 1")
    if not 0 <= getattr(a, "threshold", 0) <= 1:
        ap.error("--threshold must be between 0 and 1")
    try:
        a.run(a, load_candidates(a.candidates))
    except (OSError, ValueError) as e:
        ap.error(str(e))
    return 0


if __name__ == "__main__":
    sys.exit(main())
