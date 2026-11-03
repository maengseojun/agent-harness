#!/usr/bin/env python3
"""Advisory pre-flight before a review round (MAE-306). Stdlib only.

  preflight.py ac --plan PLAN.md [--base REF] [--head REF] [--evidence FILE ...] [--max-diff-chars N]
      One Decisions request: for each AC-n of the plan, met / unmet / unclear, judged from the plan,
      the git diff and the verification output.
  preflight.py triage --findings review.json [--previous review.json ...] [--base REF] [--head REF]
      One Decisions request: for each finding of a maeng-review result, new or repeat of an earlier
      round, and caused by this diff / pre-existing / a bypass of a gate.

Advisory only: prints Markdown tables, never edits a file, never gates anything, and exits 0 unless
its own arguments are wrong (2). Pilot name: review_preflight. decisions_client sends nothing under
MAENG_DECISIONS=off or in an eta checkout (every answer is then `unknown`) and redacts secrets.
"""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import decisions_client  # noqa: E402

DECIDE = decisions_client.decide  # tests replace this
PILOT = "review_preflight"
BASE, HEAD, MAX_DIFF = "origin/feat/harness-v1", "HEAD", 300000
NO_EVIDENCE = "No verification output was supplied."


def _choices(*pairs):
    return [{"value": v, "description": d} for v, d in pairs]


AC_CHOICES = _choices(
    ("met", "The diff and the verification output show this criterion is satisfied."),
    ("unmet", "The diff or the verification output shows it is not satisfied, or something it requires is missing."),
    ("unclear", "The material above is not enough to tell."))
REPEAT_CHOICES = _choices(
    ("new", "Not raised in any previous round."),
    ("repeat", "The same problem was raised in a previous round, even if worded differently."))
CAUSE_CHOICES = _choices(
    ("this_change", "Caused by lines this diff adds or changes."),
    ("pre_existing", "The problem exists in code this diff does not change."),
    ("bypass", "A way around an approval, review or ship gate."))

# `- **AC-1** text`, `* AC-1 text`, `AC-1: text`, `**AC-1:** text`; bare prose "AC-1 is ..." is not a criterion
_AC = re.compile(r"^(\s*)([-*+]\s+)?(\*\*)?AC-(\d+)(\*\*)?[ \t]*(:)?(\*\*)?[ \t]*(.*)$")
_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")
_VERIF = re.compile(r"^\s*(?:#{1,6}\s*)?\**Verification\**\s*:?\**\s*$", re.I)


def parse_acs(plan):
    """-> [(AC-n, text)] in first-seen order. Lines under a Verification heading are commands, not
    criteria; a repeated id keeps its first definition. shortcut: a wrapped line must be indented
    deeper than its bullet to belong to it."""
    acs, cur, in_verif = {}, None, False
    for line in plan.splitlines() + [""]:
        m = _AC.match(line)
        if m and not (m[2] or m[3] or m[6]):
            m = None
        indent = len(line) - len(line.lstrip())
        if cur and line.strip() and not m and indent > cur[1]:
            cur[2].append(line.strip())
            continue
        if cur:
            acs.setdefault(cur[0], " ".join(p for p in cur[2] if p))
            cur = None
        if _VERIF.match(line):
            in_verif = True
        elif in_verif and line.strip() and not m and not _BULLET.match(line) and indent == 0:
            in_verif = False
        if m and not in_verif:
            cur = (f"AC-{m[4]}", len(m[1]), [m[8].strip()])
    return list(acs.items())


def _git_diff(base, head):
    r = subprocess.run(["git", "diff", "--no-ext-diff", "--no-color", f"{base}...{head}"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[:300] or f"git exited {r.returncode}")
    return r.stdout


def _diff_section(base, head, limit):
    # redact before cutting, so a cut cannot leave the unredacted start of a secret
    diff = decisions_client.redact(_git_diff(base, head))
    note = ""
    if len(diff) > limit:
        note = f"[diff truncated: the first {limit} of {len(diff)} characters are shown]\n"
        diff = diff[:limit]
    return f"=== DIFF (git diff {base}...{head}) ===\n{note}{diff or '(empty diff)'}"


def _verdict(a, allowed):
    ok = isinstance(a, dict) and a.get("status") == "ok" and a.get("choice") in allowed
    return a["choice"] if ok else "unknown"


def _prob(a, value):
    ps = a.get("probabilities") if isinstance(a, dict) else None
    return next((x.get("probability") for x in ps if isinstance(x, dict) and x.get("value") == value), None) \
        if isinstance(ps, list) else None


def _num(x):
    return f"{x:.2f}" if isinstance(x, (int, float)) and not isinstance(x, bool) else "-"


def _cell(s):
    return str(s).replace("|", "\\|").replace("\n", " ").strip()


def _ask(text, questions):
    return {a.get("name"): a for a in DECIDE(text, questions, PILOT) if isinstance(a, dict)}


def _note_unknown(answers):
    reasons = sorted({(a or {}).get("reason") or "no verdict" for a in answers})
    if reasons:
        print("preflight: unknown answers: " + ", ".join(reasons), file=sys.stderr)


def _read(ap, path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        ap.error(f"cannot read {path}: {e.strerror}")


def _diff_or_none(args, limit):
    try:
        return _diff_section(args.base, args.head, limit)
    except (OSError, RuntimeError, subprocess.SubprocessError) as e:
        print(f"preflight: no diff, so nothing was sent ({e})", file=sys.stderr)


def cmd_ac(ap, args):
    plan = _read(ap, args.plan)
    acs = parse_acs(plan)
    if not acs:
        print(f"preflight: no acceptance criteria (AC-n) found in {args.plan}")
        return
    evidence = [(p, _read(ap, p)) for p in args.evidence]
    diff = _diff_or_none(args, args.max_diff_chars)
    if diff is None:
        return
    ev = "\n\n".join(f"--- {p} ---\n{t}" for p, t in evidence) or NO_EVIDENCE
    text = f"=== PLAN ({args.plan}) ===\n{plan}\n\n{diff}\n\n=== VERIFICATION OUTPUT ===\n{ev}"
    questions = [{"type": "choice", "name": n, "choices": AC_CHOICES,
                  "instructions": f"Criterion {n}: {t}\nJudge only from the plan, diff and verification output above."}
                 for n, t in acs]
    answers = _ask(text, questions)
    rows, counts, unknown = [], Counter(), []
    for n, _ in acs:
        a = answers.get(n)
        v = _verdict(a, ("met", "unmet", "unclear"))
        counts[v] += 1
        if v == "unknown":
            unknown.append(a)
        known = v != "unknown"
        rows.append(f"| {n} | {v} | {_num(_prob(a, 'met') if known else None)} | "
                    f"{_num(_prob(a, 'unmet') if known else None)} | {_num(a.get('confidence') if known else None)} |")
    print("| AC | verdict | p(met) | p(unmet) | confidence |\n|---|---|---|---|---|\n" + "\n".join(rows))
    print(f"\nadvisory only: {counts['unmet']} unmet, {counts['unclear']} unclear, {counts['unknown']} unknown")
    _note_unknown(unknown)


def load_findings(ap, path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        ap.error(f"cannot read findings from {path}: {getattr(e, 'strerror', None) or e}")
    items = data.get("findings") if isinstance(data, dict) else data
    return [f for f in items if isinstance(f, dict)] if isinstance(items, list) else []


def _where(f):
    loc = str(f.get("file") or "")
    return f"{loc}:{f['line']}" if loc and f.get("line") is not None else loc or "no location"


def _finding_text(f, n=None):
    head = f"{f.get('severity') or '?'} | {f.get('title') or '(no title)'} | {_where(f)}"
    return f"{f'[{n}]' if n else '-'} {head}\n{f.get('body') or ''}".rstrip()


def triage_questions(findings):
    qs = []
    for i, f in enumerate(findings, 1):
        who = f"Finding [{i}] {f.get('title') or '(no title)'} ({_where(f)})"
        qs.append({"type": "choice", "name": f"f{i}_repeat", "choices": REPEAT_CHOICES,
                   "instructions": f"{who}\nWas the same problem raised in a previous round? "
                                   "Judge only from the findings and diff above."})
        qs.append({"type": "choice", "name": f"f{i}_cause", "choices": CAUSE_CHOICES,
                   "instructions": f"{who}\nWhat caused this problem? Judge only from the findings and diff above."})
    return qs


def cmd_triage(ap, args):
    cur = load_findings(ap, args.findings)
    if not cur:
        print(f"preflight: no findings in {args.findings}")
        return
    prev = [(p, load_findings(ap, p)) for p in args.previous]
    diff = _diff_or_none(args, MAX_DIFF)
    if diff is None:
        return
    parts = [f"=== CURRENT FINDINGS ({args.findings}) ===", *(_finding_text(f, i) for i, f in enumerate(cur, 1))]
    for p, fs in prev:
        parts += [f"=== PREVIOUS ROUND ({p}) ===", *([_finding_text(f) for f in fs] or ["(no findings)"])]
    if not prev:
        parts.append("=== PREVIOUS ROUNDS ===\nNo previous round was supplied.")
    answers = _ask("\n\n".join(parts + [diff]), triage_questions(cur))
    rows, counts, unknown = [], Counter(), []
    for i, f in enumerate(cur, 1):
        cells = []
        for kind, allowed in (("repeat", ("new", "repeat")), ("cause", ("this_change", "pre_existing", "bypass"))):
            a = answers.get(f"f{i}_{kind}")
            v = _verdict(a, allowed)
            counts[v] += 1
            if v == "unknown":
                unknown.append(a)
            p = _prob(a, v)
            cells.append(v if v == "unknown" or p is None else f"{v} ({_num(p)})")
        title = _cell(f.get("title") or "(no title)")
        rows.append(f"| {i} | {_cell(f.get('severity') or '?')} | {title[:80]} | {cells[0]} | {cells[1]} |")
    print("| # | severity | title | repeat | cause |\n|---|---|---|---|---|\n" + "\n".join(rows))
    print(f"\nadvisory only: {counts['repeat']} repeat, {counts['pre_existing']} pre_existing, "
          f"{counts['bypass']} bypass, {counts['unknown']} unknown")
    _note_unknown(unknown)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="preflight.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    refs = argparse.ArgumentParser(add_help=False)
    refs.add_argument("--base", default=BASE)
    refs.add_argument("--head", default=HEAD)
    p = sub.add_parser("ac", parents=[refs], help="check each acceptance criterion of a plan")
    p.add_argument("--plan", required=True)
    p.add_argument("--evidence", nargs="+", action="extend", default=[], metavar="FILE")
    p.add_argument("--max-diff-chars", type=int, default=MAX_DIFF)
    p.set_defaults(run=cmd_ac)
    p = sub.add_parser("triage", parents=[refs], help="sort the findings of a review round")
    p.add_argument("--findings", required=True)
    p.add_argument("--previous", nargs="+", action="extend", default=[], metavar="FILE")
    p.set_defaults(run=cmd_triage)
    args = ap.parse_args(argv)
    if args.base.startswith("-") or args.head.startswith("-"):  # a ref like --output=x would make git write a file
        ap.error("--base and --head must be git refs, not options")
    if args.cmd == "ac" and args.max_diff_chars < 0:
        ap.error("--max-diff-chars must be >= 0")
    args.run(ap, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
