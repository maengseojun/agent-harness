#!/usr/bin/env python3
"""Enroll historical review verdicts that carried critical/high findings (AC-13 corpus), and validate the file.

  review_replay.py build --out FILE       write the case manifest from the stored reviews
  review_replay.py check --manifest FILE  validate the schema, print counts; non-zero when empty
  review_replay.py replay --manifest FILE --results FILE ...  rebuild each bundle from git, run the case's reviewer
                                          with the current maeng-review prompt, report lost critical/high blockers

Sources: <home>/receipts (pass receipts only) and <home>/reviews (every review run incl. fail/blocked, where the
blocking findings live). They overlap; a verdict is counted once. Finding bodies are never copied (public repo).
"""
import argparse
import ast
import concurrent.futures
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins/maeng-harness/lib"))
from maeng import evidence, receipts, schema  # noqa: E402
from maeng.common import canonical, git_out, home_dir, sha256, write_json  # noqa: E402

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


REPLAY_NOTE = ("historical replay: the original run's verification evidence is not reproduced; judge the diff against "
               "the criteria and do not answer blocked for missing evidence")
RULE = ("An expected finding is matched by a new critical/high finding in the same file within 20 lines, or with title "
        "token Jaccard similarity >= 0.5 (lowercase alphanumeric tokens of 3+ characters); a finding without a file "
        "matches by title only.")
PLAN_RE = re.compile(r"^docs/design/MAE-[^/]*-plan\.md$")
KIND_NOTE = "kind is 'code' for every replayed case: the manifest does not record code vs parent"
_MR = None


def maeng_review():
    """The maeng-review script (no .py suffix) loaded as a module, once."""
    global _MR
    if _MR is None:
        path = str(ROOT / "plugins/maeng-harness/bin/maeng-review")
        spec = importlib.util.spec_from_loader("maeng_review_replay", importlib.machinery.SourceFileLoader(
            "maeng_review_replay", path))
        _MR = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_MR)
    return _MR


_PROMPT = None


def review_prompt(a):
    """The review prompt the replay sends: maeng-review's current PROMPT, or with --prompt-from, the PROMPT literal of
    bin/maeng-review at that commit (the pre-change baseline on the same reconstructed bundles)."""
    global _PROMPT
    if _PROMPT is None:
        commit = getattr(a, "prompt_from", None)
        if not commit:
            _PROMPT = maeng_review().PROMPT
        else:
            src = _git(ROOT, "show", f"{commit}:plugins/maeng-harness/bin/maeng-review")
            if src is None:
                raise SystemExit(f"--prompt-from {commit}: bin/maeng-review not found at that commit")
            tree = ast.parse(src)
            lit = next((n.value for n in tree.body if isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == "PROMPT" for t in n.targets)), None)
            if not isinstance(lit, ast.Constant) or not isinstance(lit.value, str):
                raise SystemExit(f"--prompt-from {commit}: no PROMPT string literal in bin/maeng-review")
            _PROMPT = lit.value
    return _PROMPT


def enrolled_cases(commit, path):
    """The cases list committed at `commit` for `path` (repo-relative); None when it cannot be read."""
    p = subprocess.run(["git", "-C", str(ROOT), "show", f"{commit}:{path}"], capture_output=True, text=True)
    try:
        return json.loads(p.stdout)["cases"] if p.returncode == 0 else None
    except (ValueError, KeyError, TypeError):
        return None


def _git(repo, *args):
    try:
        return git_out(repo, *args, timeout=120)
    except UnicodeDecodeError:  # a binary file: the reviewer cannot read it either
        return None


def _blobs(repo, head, files):
    """{path: text at head} through one `git cat-file --batch`; absent and non-UTF-8 files are skipped."""
    p = subprocess.run(["git", "-C", str(repo), "cat-file", "--batch"], capture_output=True,
                       input="".join(f"{head}:{f}\n" for f in files).encode())
    out, i, res = p.stdout, 0, {}
    for f in files:
        nl = out.index(b"\n", i)
        hdr = out[i:nl].split()
        i = nl + 1
        if len(hdr) == 3 and hdr[1] == b"blob":
            n = int(hdr[2])
            try:
                res[f] = out[i:i + n].decode("utf-8").strip()  # strip: the same text maeng-review's git_out gives
            except UnicodeDecodeError:
                pass
            i += n + 1
    return res


def resolve_plan(repo, case):
    """-> (plan_path, resolution) by the rule: issue plan, single changed plan, most-changed plan, none."""
    base, head = case["base"], case["head"]
    pinned = case.get("plan_path")  # the path the original review recorded, when the manifest has one
    if pinned and _git(repo, "cat-file", "-e", f"{head}:{pinned}") is not None:
        return pinned, "pinned"
    try:
        issue = (json.loads((home_dir() / "reviews" / f"{case['id']}.json").read_text(encoding="utf-8"))
                 .get("subject") or {}).get("issue")
    except (OSError, ValueError):
        issue = None
    if issue:
        path = f"docs/design/{issue}-plan.md"
        if _git(repo, "cat-file", "-e", f"{head}:{path}") is not None:
            return path, "issue"
    names = (_git(repo, "diff", "--name-only", "--no-renames", f"{base}...{head}") or "").splitlines()
    changed = [n for n in names if PLAN_RE.match(n) and _git(repo, "cat-file", "-e", f"{head}:{n}") is not None]
    if len(changed) == 1:
        return changed[0], "changed-single"
    if changed:
        stat = {}
        for line in (_git(repo, "diff", "--numstat", "--no-renames", f"{base}...{head}") or "").splitlines():
            a, d, n = (line.split("\t") + ["", "", ""])[:3]
            stat[n] = (int(a) if a.isdigit() else 0) + (int(d) if d.isdigit() else 0)
        return max(sorted(changed), key=lambda n: stat.get(n, 0)), "changed-largest"
    return None, "none"


def stored_scope(case):
    """The original run's scope (files_reviewed/excluded/delegated, exclusion_reason) from the stored review, when
    the review split a large PR with --path/--exclude/--delegate; None when the stored review is absent or unsplit."""
    try:
        s = json.loads((home_dir() / "reviews" / f"{case['id']}.json").read_text(encoding="utf-8")).get("subject") or {}
    except (OSError, ValueError):
        return None
    if not s.get("files_reviewed") or not (s.get("files_excluded") or s.get("files_delegated")):
        return None
    return {"files": sorted(s["files_reviewed"]), "excluded_files": sorted(s.get("files_excluded") or []),
            "delegated_files": sorted(s.get("files_delegated") or []), "exclusion_reason": s.get("exclusion_reason")}


def reconstruct(repo, case):
    """-> (bundle, plan_path, resolution), or (None, None, None) when git cannot produce the diff."""
    base, head = case["base"], case["head"]
    scope = stored_scope(case)
    sel = ["--", *scope["files"]] if scope else []
    diff = _git(repo, "diff", "--no-renames", f"{base}...{head}", *sel)
    names = _git(repo, "diff", "--name-only", "--no-renames", f"{base}...{head}", *sel)
    if diff is None or names is None:
        return None, None, None
    files = sorted(set(names.splitlines()))
    contents = _blobs(repo, head, files)
    plan_path, how = resolve_plan(repo, case)
    text = _git(repo, "show", f"{head}:{plan_path}") if plan_path else None
    crit, checks = evidence.parse_plan_text(text) if text else (None, None)
    return {"kind": "code", "repo": case["repo"], "pr": case["pr"], "files_reviewed": files, "evidence_files": {},
            "tool_reference": None,
            "scope": {"paths": scope["files"] if scope else [], "exclude": [],
                      "excluded_files": scope["excluded_files"] if scope else [], "delegate": [],
                      "delegated_files": scope["delegated_files"] if scope else [],
                      "exclusion_reason": scope["exclusion_reason"] if scope else None,
                      "scope_source": "stored review" if scope else "whole diff"},
            "base": base, "head": head, "diff": diff, "changed_files": contents, "criteria": crit,
            "criteria_rev": evidence.criteria_rev(text) if text else None, "plan_text": text,
            "required_checks": checks, "evidence": [], "evidence_binding": [], "ship_verified": None,
            "ship_verified_reasons": [], "missing": [], "review_mode": "initial",
            "replay_note": REPLAY_NOTE}, plan_path, how


def run_reviewer(case, prompt_text, out_schema, cwd):
    """-> (result, error). The case's own model and effort; the only place a real reviewer is launched."""
    mr = maeng_review()
    model, effort = case["reviewer"]["model"], case["reviewer"]["effort"]
    if str(model).startswith("claude-"):
        result, _aux, err = mr.run_claude(model, effort, out_schema, prompt_text, cwd)
        return result, err
    with tempfile.TemporaryDirectory(prefix="maeng-replay-") as d:
        sp, op = Path(d, "schema.json"), Path(d, "out.json")
        write_json(sp, out_schema)
        return mr.codex_attempts(model, effort, sp, op, prompt_text, cwd)


def _tokens(t):
    return set(re.findall(r"[a-z0-9]{3,}", (t or "").lower()))


def similar(a, b):
    x, y = _tokens(a), _tokens(b)
    return bool(x and y) and len(x & y) / len(x | y) >= 0.5


def match(exp, found):
    for f in found:
        if f.get("severity") not in BLOCKING:
            continue
        near = (exp["file"] is not None and f.get("file") == exp["file"] and isinstance(f.get("line"), int)
                and isinstance(exp["line"], int) and abs(f["line"] - exp["line"]) <= 20)
        if near or similar(exp["title"], f.get("title")):
            return {k: f.get(k) for k in ("severity", "title", "file", "line")}
    return None


def bundle_sha256(bundle):
    return hashlib.sha256(json.dumps(bundle, sort_keys=True).encode("utf-8")).hexdigest()


def run_case(case, a, repo, out_schema):
    """-> the per-case result dict (not yet saved)."""
    mr = maeng_review()
    t0 = time.time()
    res = {"id": case["id"], "status": "not_reconstructable", "reviewer": case["reviewer"], "verdict": None,
           "findings": [], "bundle_sha256": None, "bundle_bytes": None, "prompt_bytes": None, "duration_s": 0,
           "plan_path": None, "plan_resolution": None, "criteria_rev": None, "error": None, "kind_note": KIND_NOTE,
           "ran_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    bundle, res["plan_path"], res["plan_resolution"] = (reconstruct(repo, case) if case.get("reconstructable")
                                                        else (None, None, None))
    if bundle is None:
        res["error"] = "cannot rebuild the bundle from git"
        return res
    prompt = review_prompt(a) + json.dumps(bundle, indent=1)
    res.update(criteria_rev=bundle["criteria_rev"], bundle_sha256=bundle_sha256(bundle),
               bundle_bytes=len(json.dumps(bundle).encode("utf-8")),
               prompt_bytes=len(prompt.encode("utf-8")))  # UTF-8 bytes: the cap is a byte limit, not code points
    if dry_status(res, a) == "too_large":
        res["status"] = "too_large"
        return res
    if a.dry_run:
        res["status"] = "would_run"
        return res
    result, err = run_reviewer(case, prompt, out_schema, str(repo))
    # a baseline prompt never promised the V-1..V-6 location rule: validate only schema and verdict consistency
    err = err or mr.response_error(result, out_schema, "docs" if getattr(a, "prompt_from", None) else "code")
    res["duration_s"] = round(time.time() - t0, 1)
    if err:
        res.update(status="error", error=str(err)[-500:])
        return res
    result = mr.settle(result, "code")
    res.update(status="ok", verdict=result["verdict"], findings=[
        {k: f.get(k) for k in ("severity", "title", "file", "line")} for f in result["findings"]])
    return res


def dry_status(res, a):
    return "too_large" if res["prompt_bytes"] > a.max_bytes else "ok"


def replay(a):
    mpath = Path(a.manifest).resolve()
    m = json.loads(mpath.read_text(encoding="utf-8"))
    rel = os.path.relpath(mpath, ROOT)
    if enrolled_cases(a.enrolled_at, rel) != m["cases"]:
        print("manifest changed since enrollment")
        return 1
    repo = Path(a.repo).resolve()
    rdir = Path(a.results_dir) if a.results_dir else Path(a.results).parent / "review-replay"
    cases = [c for c in m["cases"] if not a.only or c["id"] in a.only]
    full = schema.load_schema()
    out_schema = {**full["$defs"]["reviewer_output"], "$defs": full["$defs"]}
    prompt_sha256 = hashlib.sha256(review_prompt(a).encode()).hexdigest()

    def one(c):
        f = rdir / f"{c['id']}.json"
        if f.exists() and not (a.force or a.dry_run):
            cached = json.loads(f.read_text(encoding="utf-8"))
            bundle, _, _ = reconstruct(repo, c) if c.get("reconstructable") else (None, None, None)
            if (bundle is not None and cached.get("prompt_sha256") == prompt_sha256
                    and cached.get("bundle_sha256") == bundle_sha256(bundle)):
                return cached
        r = run_case(c, a, repo, out_schema)
        r["prompt_sha256"] = prompt_sha256
        if not a.dry_run:
            rdir.mkdir(parents=True, exist_ok=True)
            write_json(f, r)
        return r

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, a.jobs)) as ex:
        done = list(ex.map(one, cases))
    if a.dry_run:
        for c, r in zip(cases, done):
            print(f"{c['id']} pr={c['pr']} reviewer={c['reviewer']['model']}/{c['reviewer']['effort']} "
                  f"bundle={r['bundle_bytes']} prompt={r['prompt_bytes']} plan={r['plan_resolution']} "
                  f"status={r['status']}")
        return 0
    return aggregate(a, m, rdir)


def aggregate(a, m, rdir):
    mr = maeng_review()
    prompt_sha256 = hashlib.sha256(review_prompt(a).encode()).hexdigest()
    rows, lost, verdicts, not_run = [], [], {}, []
    for c in m["cases"]:
        f = rdir / f"{c['id']}.json"
        r = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
        if r and r.get("prompt_sha256") != prompt_sha256:
            r = None
        status = r["status"] if r else "no_result"
        if r and status == "ok":
            verdicts[r["verdict"]] = verdicts.get(r["verdict"], 0) + 1
        elif c["reconstructable"] or r:
            not_run.append({"id": c["id"], "status": status})
        exp = [{**e, "matched": match(e, r["findings"]) if status == "ok" else None} for e in c["findings"]]
        lost += [(c["id"], e["title"]) for e in exp if status == "ok" and e["matched"] is None]
        rows.append({"id": c["id"], "status": status, "verdict": r and r["verdict"],
                     **{k: r.get(k) if r else None for k in
                        ("bundle_sha256", "bundle_bytes", "plan_path", "plan_resolution", "criteria_rev")},
                     "expected": exp})
    ran = sum(x["status"] == "ok" for x in rows)
    out = {"cases_total": len(m["cases"]), "cases_reconstructable": sum(bool(c["reconstructable"]) for c in m["cases"]),
           "cases_run": ran, "cases_not_run": not_run, "verdicts": verdicts, "lost_blockers": [
               {"id": i, "title": t} for i, t in lost], "rule": RULE, "kind_note": KIND_NOTE,
           "prompt_sha256": prompt_sha256,
           "prompt_from": getattr(a, "prompt_from", None) or "working tree", "enrolled_at": a.enrolled_at,
           "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "cases": rows,
           "expected": {c["id"]: c["findings"] for c in m["cases"]}}
    write_json(Path(a.results), out)
    print(f"cases_run={ran} lost_blockers={len(lost)} verdicts={verdicts}")
    for i, t in lost:
        print(f"LOST {i}: {t}")
    bad = False
    if a.require_complete and any(c["status"] != "ok" for c in rows if
                                  next(k for k in m["cases"] if k["id"] == c["id"])["reconstructable"]):
        print("FAIL: not every reconstructable case ran ok", file=sys.stderr)
        bad = True
    if a.max_lost_blockers is not None and len(lost) > a.max_lost_blockers:
        print(f"FAIL: lost_blockers {len(lost)} > {a.max_lost_blockers}", file=sys.stderr)
        bad = True
    return 1 if bad else 0


def compare(a):
    """Baseline (old prompt) vs results (new prompt) on the same bundles. An expected finding is `kept` in a run when
    its `matched` is set. lost_vs_baseline = kept by the baseline and not by the new run: the blockers the prompt change
    itself lost. The absolute counts are printed too; the enrolled expectations stay the anchor of both runs."""
    base = json.loads(Path(a.baseline).read_text(encoding="utf-8"))
    new = json.loads(Path(a.results).read_text(encoding="utf-8"))
    if base.get("expected") != new.get("expected"):
        print("the two runs do not share the enrolled expectations")
        return 1
    bcase = {c["id"]: c for c in base["cases"]}
    ncase = {c["id"]: c for c in new["cases"]}
    out = {"baseline_prompt": base.get("prompt_from"), "new_prompt": new.get("prompt_from"), "cases_compared": 0,
           "expected": 0, "kept_baseline": 0, "kept_new": 0, "lost_vs_baseline": [], "gained_vs_baseline": [],
           "lost_by_both": 0, "cases_not_in_both": [], "excluded": [], "bundle_mismatch": [],
           "binding": "bundle_sha256"}
    for cid in sorted(bcase.keys() | ncase.keys()):
        bc, nc = bcase.get(cid), ncase.get(cid)
        bs, ns = (bc or {}).get("status", "no_result"), (nc or {}).get("status", "no_result")
        if bs != "ok":
            out["cases_not_in_both"].append(cid)
            out["excluded"].append({"id": cid, "baseline_status": bs, "new_status": ns,
                                    "reason": "baseline is not ok"})
            continue
        if not bc.get("bundle_sha256") or not (nc or {}).get("bundle_sha256"):
            out["binding"] = "criteria_rev+plan"
        if nc and (any(bc.get(k) != nc.get(k) for k in ("criteria_rev", "plan_path", "plan_resolution"))
                   or ((bc.get("bundle_sha256") or nc.get("bundle_sha256"))
                       and bc.get("bundle_sha256") != nc.get("bundle_sha256"))):
            out["bundle_mismatch"].append(cid)
            if ns == "ok":
                continue
        out["cases_compared"] += 1
        for i, be in enumerate(bc["expected"]):
            ne = nc["expected"][i] if ns == "ok" else {}
            out["expected"] += 1
            kb, kn = bool(be.get("matched")), bool(ne.get("matched"))
            out["kept_baseline"] += kb
            out["kept_new"] += kn
            if kb and not kn:
                lost = {"id": cid, "title": be.get("title")}
                if ns != "ok":
                    lost["reason"] = ns
                out["lost_vs_baseline"].append(lost)
            elif kn and not kb:
                out["gained_vs_baseline"].append({"id": cid, "title": ne.get("title")})
            elif not kb and not kn:
                out["lost_by_both"] += 1
    print(json.dumps(out, indent=1))
    print(f"cases_not_in_both={len(out['cases_not_in_both'])}", file=sys.stderr)
    if out["bundle_mismatch"]:
        print("FAIL: bundle mismatch", file=sys.stderr)
        return 1
    if out["cases_compared"] == 0 or out["expected"] == 0:
        print("FAIL: empty comparison denominator", file=sys.stderr)
        return 1
    if a.max_lost is not None and len(out["lost_vs_baseline"]) > a.max_lost:
        print(f"FAIL: {len(out['lost_vs_baseline'])} blockers kept by the baseline prompt are lost by the new prompt "
              f"(> {a.max_lost})", file=sys.stderr)
        return 1
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compare")
    c.add_argument("--baseline", required=True)
    c.add_argument("--results", required=True)
    c.add_argument("--max-lost", type=int)
    sub.add_parser("build").add_argument("--out", required=True)
    sub.add_parser("check").add_argument("--manifest", required=True)
    r = sub.add_parser("replay")
    r.add_argument("--manifest", required=True)
    r.add_argument("--results", required=True)
    r.add_argument("--results-dir")
    r.add_argument("--repo", default=str(ROOT))
    r.add_argument("--enrolled-at", default="a23f430")
    r.add_argument("--jobs", type=int, default=2)
    r.add_argument("--max-bytes", type=int, default=1100000)
    r.add_argument("--only", nargs="+")
    r.add_argument("--force", action="store_true")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--require-complete", action="store_true")
    r.add_argument("--max-lost-blockers", type=int)
    r.add_argument("--prompt-from", help="commit whose bin/maeng-review PROMPT is sent instead of the current one "
                                         "(the pre-change baseline on the same bundles)")
    a = ap.parse_args(argv)
    if a.cmd == "replay":
        return replay(a)
    if a.cmd == "compare":
        return compare(a)
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
