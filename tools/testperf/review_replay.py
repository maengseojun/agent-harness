#!/usr/bin/env python3
"""Enroll historical review verdicts that carried critical/high findings (AC-13 corpus), and validate the file.

  review_replay.py build --out FILE       write the case manifest from the stored reviews
  review_replay.py check --manifest FILE  validate the schema, print counts; non-zero when empty

Sources: <home>/receipts (pass receipts only) and <home>/reviews (every review run incl. fail/blocked, where the
blocking findings live). They overlap; a verdict is counted once. Finding bodies are never copied (public repo).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins/maeng-harness/lib"))
from maeng import receipts  # noqa: E402
from maeng.common import canonical, home_dir, sha256  # noqa: E402

BLOCKING = ("critical", "high")
CASE_KEYS = {"id", "repo", "pr", "base", "head", "base_ref", "plan_path", "criteria_rev", "reviewer", "verdict",
             "reconstructable", "findings"}
FINDING_KEYS = {"severity", "title", "file", "line", "expected_blocking"}


def _verdicts():
    """-> ({id: verdict}, [receipt timestamps]). id = first 16 hex of the verdict hash (the reviews/ file name)."""
    found, stamps = {}, []
    rdir = receipts.receipts_dir()
    for p in sorted(rdir.glob("*.json")) if rdir.is_dir() else []:
        rec = receipts.load(p.stem)
        if isinstance(rec, dict) and "verdict" in rec:
            found.setdefault(sha256(canonical(rec["verdict"]))[:16], rec["verdict"])
            stamps += [h["at"] for h in rec.get("history", []) if h.get("at")]
    vdir = home_dir() / "reviews"
    for p in sorted(vdir.glob("*.json")) if vdir.is_dir() else []:
        try:
            v = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(v, dict) and "subject" in v:
            found.setdefault(sha256(canonical(v))[:16], v)
    return found, stamps


def _has_commit(sha):
    return bool(sha) and subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{sha}^{{commit}}"],
                                        capture_output=True).returncode == 0


def build_manifest():
    found, stamps = _verdicts()
    scanned, cases = 0, []
    for vid, v in sorted(found.items()):
        s = v.get("subject") or {}
        if s.get("kind") not in ("code", "parent"):
            continue
        scanned += 1
        hi = [f for f in v.get("findings", []) if f.get("severity") in BLOCKING]
        if not hi:
            continue
        rv = v.get("reviewer") or {}
        cases.append({
            "id": vid, "repo": s.get("repo"), "pr": s.get("pr"), "base": s.get("base"), "head": s.get("head"),
            "base_ref": s.get("destination"), "plan_path": s.get("plan_path"), "criteria_rev": s.get("criteria_rev"),
            "reviewer": {"model": rv.get("model"), "effort": rv.get("effort")}, "verdict": v.get("verdict"),
            "reconstructable": _has_commit(s.get("base")) and _has_commit(s.get("head")),
            "findings": [{"severity": f["severity"], "title": f.get("title"), "file": f.get("file"),
                          "line": f.get("line"), "expected_blocking": True} for f in hi]})
    return {"built_at": max(stamps) if stamps else None, "receipts_scanned": scanned, "cases_enrolled": len(cases),
            "cases_reconstructable": sum(c["reconstructable"] for c in cases), "cases": cases}


def counts(m):
    return (f"scanned={m.get('receipts_scanned')} enrolled={m.get('cases_enrolled')} "
            f"reconstructable={m.get('cases_reconstructable')} "
            f"blockers={sum(len(c.get('findings', [])) for c in m.get('cases') or [])}")


def check(m):
    cases = m.get("cases")
    if not isinstance(cases, list) or not cases:
        return ["empty case list"]
    errs = []
    for c in cases:
        if set(c) != CASE_KEYS:
            errs.append(f"case {c.get('id')}: keys differ from schema")
            continue
        if not c["findings"]:
            errs.append(f"case {c['id']}: no findings")
        for f in c["findings"]:
            if set(f) != FINDING_KEYS or f["severity"] not in BLOCKING or f["expected_blocking"] is not True:
                errs.append(f"case {c['id']}: bad finding")
    if not any(c.get("findings") for c in cases):
        errs.append("empty blocker denominator")
    if m.get("cases_enrolled") != len(cases) or m.get("cases_reconstructable") != sum(
            bool(c.get("reconstructable")) for c in cases):
        errs.append("counts do not match cases")
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build").add_argument("--out", required=True)
    sub.add_parser("check").add_argument("--manifest", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "build":
        m = build_manifest()
        Path(a.out).write_text(json.dumps(m, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(counts(m))
        return 0
    m = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    errs = check(m)
    print(counts(m))
    for e in errs:
        print("FAIL: " + e, file=sys.stderr)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
