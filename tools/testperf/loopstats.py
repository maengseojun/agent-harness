#!/usr/bin/env python3
"""Re-runs the MAE-323 baseline measurement from Claude Code transcripts and the harness state folder.

Read-only on its inputs, standard library only. It prints aggregates only: no transcript text, prompt or file
content leaves this process. Replaces the one-off scripts (a1..a17) kept under refs/mae323/analysis.
"""
import argparse
import collections
import datetime as dt
import glob
import json
import os
import re
import statistics
import sys
from multiprocessing import Pool

EFFORTS = ("low", "medium", "high", "xhigh", "max")
HIGH = ("xhigh", "max")
SPLIT = (2, 1, 317)  # CLI version from which a subagent on another model no longer inherits the session effort

# Baseline table of docs/design/MAE-323-plan.md ("기준값 (최근 7일, 2026-11-05 측정)"). Numeric value per row.
BASELINE = {
    "subagent_xhigh_share": 92.0,
    "full_test_runs": 107.0, "full_test_hours": 6.8, "full_test_per_branch": 4.0,
    "impact_test_uses": 0.0,
    "post_first_review_share": 68.0,
    "review_pass_pct": 34.0,
    "prs_4plus_reviews": 12.0, "prs_total": 26.0,
    "stop_blocks": 164.0,
    "record_writes": 621.0, "record_per_turn": 1.3,
    "verify_skips": 67.0,
    "implementer_delegations": 13.0, "main_edits": 792.0,
    "effort_named_calls": 1.0, "delegation_calls": 156.0,
    "codex_exec_direct": 73.0,
    "start_ctx_k_low": 75.0, "start_ctx_k_high": 80.0,
    "skills": 49.0, "skill_bytes": 20693.0, "skills_over_260": 38.0,
    "mutation_detected": 9.0, "mutation_total": 20.0,
}

RECORD_TOOLS = re.compile(
    r"^mcp__[^_].*__(save_issue|save_comment|save_document|save_project|save_status_update|write_note|patch_note|"
    r"update_frontmatter|manage_tags|notion-create-pages|notion-update-page|notion-create-comment)$")
TS = re.compile(r'"timestamp":"([^"]+)"')


def pt(s):
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError, TypeError):
        return None


def ver_tuple(v):
    m = re.match(r"(\d+)\.(\d+)\.(\d+)", v or "")
    return tuple(int(x) for x in m.groups()) if m else None


CODEX = re.compile(r"\bcodex\b[^|;&\n]*\bexec\b")
IMPACT = re.compile(r"python3?\S*\s+\S*impact\.py\s+(run|select)")


def codex_purpose(cmd):
    """Class of a direct `codex exec` call from its own flags and words (the prompt usually comes from a file)."""
    c = cmd.lower()
    if re.search(r"--help|--version|model ok|\bgrep\b.*codex exec", c):
        return "probe"
    if re.search(r"\b(review|verdict|findings)\b", c):
        return "review"
    if re.search(r"\b(image|png|jpe?g|logo|poster|illustration|mockup)\b", c):
        return "image"
    if re.search(r"workspace-write|danger-full-access|--full-auto", c):
        return "write-capable work"
    if re.search(r"read-only|-s read", c):
        return "read-only analysis"
    return "other"


def bash_flags(cmd):
    f = set()
    for key, pat in (("pytest", "pytest"), ("skip", "maeng-verify skip"),
                     ("review", "maeng-review run"), ("commit", "git commit"), ("ship", "maeng-ship")):
        if pat in cmd:
            f.add(key)
    if IMPACT.search(cmd):
        f.add("impactrun")
    if "pytest" in cmd and not re.search(r"pytest[^\n|;&]*(tests?/|\.py|::| -k )", cmd):
        f.add("fullcmd")
    return f


def branch_tag(tool, inp):
    """Phase marker of a tool call for the per-branch timeline (code edit, review run, ship, test run)."""
    if tool["name"] in ("Edit", "Write") and not re.search(r"/docs/|\.md$|scratchpad|Obsidian", str(inp.get("file_path"))):
        return "code"
    if tool["name"] in ("Agent", "Task") and "implementer" in str(tool["st"]):
        return "code"
    if "review" in tool["flags"]:
        return "review"
    if "ship" in tool["flags"] and re.search(r"maeng-ship merge", str(inp.get("command"))):
        return "ship"
    if "pytest" in tool["flags"] or "maeng-verify exec" in str(inp.get("command")):
        return "test"
    return None


def parse_file(path):
    """Compact per-file facts. Returns (path, bad_lines, rows); rows are plain tuples/dicts without text."""
    sub = "/subagents/" in path
    bad = 0
    reqs, tools, results, blocks, humans, apireq, ev = {}, [], {}, [], [], {}, []
    try:
        fh = open(path, errors="replace")
    except OSError:
        return path, 1, None
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if not (line.startswith("{") and line.endswith("}")):
                bad += 1
                continue
            if '"type":"api-request"' in line[:60]:
                m = re.search(r'"id":"([^"]+)"', line[:400])
                e = re.search(r'"output_config":\{[^{}]*?"effort":"(\w+)"', line)
                if m:
                    apireq[m.group(1)] = e.group(1) if e else None
                continue
            if ('"type":"assistant"' not in line and '"type":"user"' not in line
                    and "hook_blocking_error" not in line):
                continue
            try:
                o = json.loads(line)
            except ValueError:
                bad += 1
                continue
            if not isinstance(o, dict):
                bad += 1
                continue
            t = pt(o.get("timestamp"))
            if t is None:
                continue
            ty = o.get("type")
            if ty == "assistant":
                m = o.get("message") or {}
                rid = o.get("requestId")
                if rid and m.get("model") and m.get("model") != "<synthetic>":
                    r = reqs.setdefault(rid, dict(t=t, model=m["model"], ref=o.get("requestRef"), ver=o.get("version"),
                                                  eff=o.get("effort"), pte=o.get("perTurnEffort"), sub=sub,
                                                  br=o.get("gitBranch"), uuid=o.get("uuid"), agent=o.get("agentId"), ag=o.get("attributionAgent"),
                                                  t1=t, out=0,
                                                  ctx=(m.get("usage") or {}).get("input_tokens", 0)
                                                  + (m.get("usage") or {}).get("cache_read_input_tokens", 0)
                                                  + (m.get("usage") or {}).get("cache_creation_input_tokens", 0)))
                    r["t"] = min(r["t"], t)
                    r["t1"] = max(r["t1"], t)
                    r["out"] = max(r["out"], (m.get("usage") or {}).get("output_tokens", 0))
                tag = None
                for b in m.get("content") or []:
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        i = b.get("input") or {}
                        n = b.get("name") or ""
                        cmd = str(i.get("command") or "") if n == "Bash" else ""
                        tools.append(dict(id=b.get("id"), t=t, name=n, uuid=o.get("uuid"), sub=sub, br=o.get("gitBranch"),
                                          flags=bash_flags(cmd), codex=codex_purpose(cmd) if CODEX.search(cmd) and "maeng-review" not in cmd else None,
                                          st=i.get("subagent_type"), eff=i.get("effort"), model=i.get("model"),
                                          file=str(i.get("file_path") or "")[-80:] if n in ("Edit", "Write") else "",
                                          ver=o.get("version")))
                        tag = branch_tag(tools[-1], i) or tag
                if not sub and o.get("gitBranch") and o.get("uuid"):
                    ev.append((t, "a", tag, o["gitBranch"], o["uuid"]))
            elif ty == "user":
                if not sub and o.get("gitBranch") and o.get("uuid"):
                    ev.append((t, "u", None, o["gitBranch"], o["uuid"]))
                c = (o.get("message") or {}).get("content")
                if isinstance(c, list):
                    for b in c:
                        if isinstance(b, dict) and b.get("type") == "tool_result":
                            cc = b.get("content")
                            s = cc if isinstance(cc, str) else " ".join(x.get("text", "") for x in (cc or []) if isinstance(x, dict))
                            p = re.search(r"(?:(\d+) failed, )?(\d+) passed[^\n]* in ([\d.]+)s", s)
                            results[b.get("tool_use_id")] = (t, int(p.group(2)) if p else 0,
                                                             float(p.group(3)) if p else 0.0, int(p.group(1) or 0) if p else 0)
                origin = (o.get("origin") or {}).get("kind") if isinstance(o.get("origin"), dict) else o.get("origin")
                if origin == "human" and not o.get("isMeta") and not (isinstance(c, list) and any(
                        isinstance(b, dict) and b.get("type") == "tool_result" for b in c)):
                    humans.append(t)
            else:
                at = (o.get("attachment") or {}).get("type") if ty == "attachment" else None
                if at == "hook_blocking_error":
                    blocks.append((t, o.get("uuid")))
    for r in reqs.values():
        r["papi"] = apireq.get(r["ref"])
    return path, bad, dict(reqs=reqs, tools=tools, results=results, blocks=blocks, humans=humans, ev=ev)


def find_files(root, lo):
    fs = set(glob.glob(os.path.join(root, "*", "*.jsonl")))
    fs |= set(glob.glob(os.path.join(root, "*", "*", "subagents", "**", "*.jsonl"), recursive=True))
    out = []
    for p in sorted(fs):
        try:
            if os.path.getmtime(p) >= lo:
                out.append(p)
        except OSError:
            pass
    return out


def load(root, lo, hi, jobs=8):
    """Merge per-file facts inside [lo, hi). Duplicates from resumed sessions are dropped by request id / uuid."""
    files = find_files(root, lo)
    data = dict(files=len(files), blocks_raw=0, bad_files=[], reqs={}, tools=[], results={}, blocks={}, humans=set(), ev={})
    seen_tool = set()
    if len(files) > 8 and jobs > 1:
        with Pool(jobs) as P:
            parsed = P.map(parse_file, files, chunksize=4)
    else:
        parsed = [parse_file(p) for p in files]
    for path, bad, d in parsed:
        if bad or d is None:
            data["bad_files"].append(path)
        if d is None:
            continue
        for rid, r in d["reqs"].items():
            if lo <= r["t"] < hi and rid not in data["reqs"]:
                data["reqs"][rid] = r
        for tl in d["tools"]:
            if lo <= tl["t"] < hi and tl["uuid"] + str(tl["id"]) not in seen_tool:
                seen_tool.add(tl["uuid"] + str(tl["id"]))
                data["tools"].append(tl)
        data["results"].update(d["results"])
        for t, u in d["blocks"]:
            if lo <= t < hi:
                data["blocks_raw"] += 1
                data["blocks"][u or t] = t
        data["humans"].update(t for t in d["humans"] if lo <= t < hi)
        if re.search(r"agent-harness|worktrees", path):  # the old branch analysis read only these project folders
            for t, k, tag, br, u in d["ev"]:
                if lo <= t < hi:
                    data["ev"].setdefault(u, (t, k, tag, br))
    return data


# ---------------------------------------------------------------- metrics

def median(a):
    return statistics.median(a) if a else None


def subagents(data):
    """Per subagent: version of its first request, dominant effort, active seconds (request gaps capped at 300 s)."""
    by = collections.defaultdict(list)
    for r in data["reqs"].values():
        if r["sub"] and r["agent"]:
            by[r["agent"]].append(r)
    out = []
    for a, L in by.items():
        L.sort(key=lambda r: r["t"])
        act = sum(min(y["t"] - x["t"], 300) for x, y in zip(L, L[1:])) + (L[-1]["t1"] - L[-1]["t"])
        eff = collections.Counter(req_effort(r) for r in L).most_common(1)[0][0]
        out.append(dict(agent=a, ver=L[0]["ver"], eff=eff, act=act, type=L[0]["ag"] or "general-purpose", ctx=L[0]["ctx"]))
    return out


def req_effort(r):
    return r["papi"] or r["pte"] or r["eff"]


def share_high(subs):
    tot = sum(s["act"] for s in subs)
    return 100 * sum(s["act"] for s in subs if s["eff"] in HIGH) / tot if tot else None


def version_split(subs):
    """Share of subagent active time at xhigh or above, per CLI version and split at SPLIT."""
    buckets = {"before 2.1.317": [], "2.1.317 and later": [], "version not recorded": []}
    per = collections.defaultdict(list)
    for s in subs:
        v = ver_tuple(s["ver"])
        per[s["ver"] or "none"].append(s)
        buckets["version not recorded" if v is None else ("before 2.1.317" if v < SPLIT else "2.1.317 and later")].append(s)
    return buckets, per


def full_tests(data):
    runs = {}
    for t in data["tools"]:
        if t["name"] == "Bash":
            r = data["results"].get(t["id"])
            if r and r[1] >= 300:  # 300 or more tests passed: a full run, not a targeted one
                runs[round(t["t"])] = (r[2], t["br"])
    return len(runs), sum(v[0] for v in runs.values()) / 3600, len({v[1] for v in runs.values()})


def branch_times(data):
    """Per branch: seconds in plan, build and review phase (event gaps capped at 300 s, up to the last ship)."""
    st = collections.defaultdict(list)
    for t, _k, tag, br in data["ev"].values():
        if br not in ("feat/harness-v1", "HEAD", "main"):
            st[br].append((t, tag))
    rows = []
    for br, ev in st.items():
        ev.sort(key=lambda x: x[0])
        if len(ev) < 20:
            continue
        code = next((e[0] for e in ev if e[1] == "code"), None)
        rev = next((e[0] for e in ev if e[1] == "review"), None)
        ship = [e[0] for e in ev if e[1] == "ship"]
        last = ship[-1] if ship else ev[-1][0]
        ph = collections.Counter()
        for a, b in zip(ev, ev[1:]):
            if a[0] > last:
                break
            p = ("plan" if (code is None or a[0] < code) and (rev is None or a[0] < rev)
                 else ("build" if rev is None or a[0] < rev else "review"))
            ph[p] += min(b[0] - a[0], 300)
        if sum(ph.values()) > 600:
            rows.append(ph)
    return rows


def read_reviews(state, lo, hi):
    """Review runs stored by maeng-review in the window (file mtime; the files carry no timestamp)."""
    out, bad = [], 0
    for f in glob.glob(os.path.join(state, "reviews", "*.json")):
        try:
            if not lo <= os.path.getmtime(f) < hi:
                continue
            d = json.load(open(f))
            out.append((d.get("verdict"), (d.get("subject") or {}).get("repo"), (d.get("subject") or {}).get("pr")))
        except (OSError, ValueError, AttributeError):
            bad += 1
    return out, bad


def read_roles(path):
    try:
        d = json.load(open(path))
        grades = d["grades"]
        return {g: v for g, v in grades.items() if isinstance(v, dict) and v.get("agent") and v.get("ceiling") in EFFORTS}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        sys.exit("loopstats: --roles file unusable: %s" % e)


def over_ceiling(data, grades):
    """Subagent requests whose effort ranks above the ceiling of the grade whose agent definition ran them."""
    ceil = {v["agent"].split(":")[-1]: EFFORTS.index(v["ceiling"]) for v in grades.values()}
    n = checked = 0
    for r in data["reqs"].values():
        k = (r["ag"] or "").split(":")[-1]
        e = req_effort(r)
        if r["sub"] and k in ceil and e in EFFORTS:
            checked += 1
            n += EFFORTS.index(e) > ceil[k]
    return n, checked


def skill_stats(repo):
    n = total = over = 0
    for p in sorted(glob.glob(os.path.join(repo, "plugins", "*", "skills", "*", "SKILL.md"))):
        m = re.match(r"---\n(.*?)\n---", open(p, encoding="utf-8").read(), re.S)
        if not m:
            continue
        nm = re.search(r"^name:\s*(.*)$", m.group(1), re.M)
        ds = re.search(r"^description:\s*(.*)$", m.group(1), re.M)
        b = len(((nm.group(1) if nm else "") + (ds.group(1) if ds else "")).strip("\"' ").encode())
        n += 1
        total += b
        over += b > 260
    return n, total, over


def compare(v, base, cause):
    if v is None:
        return "미측정"
    if base == 0:
        return "match" if v == 0 else "diff: %s vs 0; %s" % (fmt(v), cause)
    rel = (v - base) / base
    return "match" if abs(rel) <= 0.05 else "diff %+.1f%%: %s" % (100 * rel, cause)


def fmt(v):
    return "미측정" if v is None else ("%d" % v if float(v).is_integer() else "%.1f" % v)


def collect(args, lo, hi):
    data = load(args.projects, lo, hi)
    st = find_state(args)
    rv, rv_bad = read_reviews(st, lo, hi)
    return data, st, rv, rv_bad


def find_state(args):
    return args.state or str(os.environ.get("MAENG_HOME") or os.path.expanduser("~/.local/share/maeng-harness"))


def build_rows(data, rv, repo, compare_baseline):
    """List of (label, value, baseline key or None, cause shown on a difference)."""
    T = data["tools"]
    main_t = [t for t in T if not t["sub"]]
    subs = subagents(data)
    runs, hours, nbr = full_tests(data)
    bt = branch_times(data)
    tot = sum(sum(p.values()) for p in bt)
    after = 100 * sum(p["review"] for p in bt) / tot if tot else None
    passes = sum(1 for v, _r, _p in rv if v == "pass")
    pr_runs = collections.Counter((r, p) for _v, r, p in rv if p)
    pr_pass = [v for v, _r, p in rv if p]
    alt = 100 * pr_pass.count("pass") / len(pr_pass) if pr_pass else None
    turns = len(data["humans"])
    rec = sum(1 for t in main_t if RECORD_TOOLS.match(t["name"]))
    ag = [t for t in T if t["name"] in ("Agent", "Task")]
    cdx = collections.Counter(t["codex"] for t in T if t["codex"])
    ctx = collections.defaultdict(list)
    for s in subs:
        if s["type"] in ("implementer", "maeng-tools:implementer", "general-purpose"):
            ctx[s["type"].split(":")[-1]].append(s["ctx"] / 1000)
    n_skill, skill_b, over = skill_stats(repo)
    win = "baseline window ended at the measurement time on 2026-11-05, this one at 00:00 that day"
    rows = [
        ("subagent active time at xhigh or above, %", share_high(subs), "subagent_xhigh_share",
         "baseline script not kept; this uses the dominant effort per subagent and gaps capped at 300 s"),
        ("full test runs (300+ passed)", runs if data["tools"] else None, "full_test_runs", win),
        ("full test hours", hours, "full_test_hours", win),
        ("full test runs per branch", runs / nbr if nbr else None, "full_test_per_branch", win),
        ("impact-test runs (impact.py run/select)", sum(1 for t in T if "impactrun" in t["flags"]), "impact_test_uses", "a command ran it"),
        ("time share after the first review, %", after, "post_first_review_share",
         win + "; %d branches" % len(bt)),
        ("review pass ratio, %", 100 * passes / len(rv) if rv else None, "review_pass_pct",
         "review files carry no timestamp (mtime used) and the baseline denominator is unknown; runs with a PR only give %s%%" % fmt(alt)),
        ("PRs with 4 or more review runs", sum(1 for v in pr_runs.values() if v >= 4), "prs_4plus_reviews", "file mtime window, baseline window ended later on 2026-11-05"),
        ("PRs with a review run", len(pr_runs), "prs_total", "file mtime window, baseline window ended later on 2026-11-05"),
        ("Stop blocks", len(data["blocks"]), "stop_blocks",
         "counted once per uuid; raw lines incl. copies in resumed-session files: %d" % data["blocks_raw"]),
        ("record writes by the main thread (Linear save_*, Obsidian write/patch/frontmatter, Notion pages)", rec, "record_writes",
         "baseline subset of tools not recorded; without save_issue and update_frontmatter the count is %d"
         % sum(1 for t in main_t if RECORD_TOOLS.match(t["name"]) and not t["name"].endswith(("save_issue", "update_frontmatter")))),
        ("record writes per human turn", rec / turns if turns else None, "record_per_turn", "turns = human prompts in all projects"),
        ("maeng-verify skip calls", sum(1 for t in T if "skip" in t["flags"]), "verify_skips", win),
        ("implementer delegations", sum(1 for t in ag if "implementer" in str(t["st"])), "implementer_delegations", win),
        ("main-thread Edit/Write calls", sum(1 for t in main_t if t["name"] in ("Edit", "Write")), "main_edits", win),
        ("delegation calls naming an effort", sum(1 for t in ag if t["eff"]), "effort_named_calls", win),
        ("delegation calls", len(ag), "delegation_calls", win),
        ("direct codex exec calls (no maeng-review)", sum(cdx.values()), "codex_exec_direct",
         "pattern is `codex ... exec` in one shell segment; baseline script not kept"),
    ]
    for name, key in (("implementer", "implementer"), ("general-purpose", "general-purpose")):
        v = median(ctx[key])
        rows.append(("start context median of %s, k tokens" % name, v, "start_ctx_k_low" if name == "implementer" else "start_ctx_k_high",
                     "baseline range is 75-80k"))
    rows += [
        ("skills", n_skill, "skills", "skills added or removed since 2026-11-05"),
        ("skill name+description bytes", skill_b, "skill_bytes", "single-line frontmatter parse of this tree"),
        ("skills over 260 bytes", over, "skills_over_260", "measured on name+description of this tree"),
        ("mutation detection (9 of 20 sampled)", None, None, "needs a run of tools/testperf/mutate.py"),
    ]
    return rows, dict(subs=subs, runs=runs, hours=hours, bt=bt, rv=rv, pr_runs=pr_runs, cdx=cdx, after=after, ctx=ctx)


def main(argv=None):
    import time
    t0 = time.perf_counter()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--until", default=dt.date.today().isoformat(), help="YYYY-MM-DD; window ends at 00:00 local of that day")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--roles", help="roles.json, for the count of requests above the grade ceiling")
    ap.add_argument("--projects", default=os.path.expanduser("~/.claude/projects"))
    ap.add_argument("--state", help="harness state folder (default MAENG_HOME or ~/.local/share/maeng-harness)")
    args = ap.parse_args(argv)
    try:
        until = dt.datetime.strptime(args.until, "%Y-%m-%d")
    except ValueError:
        sys.exit("loopstats: --until must be YYYY-MM-DD")
    hi = until.timestamp()
    lo = hi - args.days * 86400
    grades = read_roles(args.roles) if args.roles else None
    data, st, rv, rv_bad = collect(args, lo, hi)
    if not (data["reqs"] or data["tools"] or data["humans"]):
        print("loopstats: no transcript in the window %s .. %s under %s" % (
            dt.datetime.fromtimestamp(lo).date(), until.date(), args.projects), file=sys.stderr)
        return 2
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    rows, x = build_rows(data, rv, repo, True)
    base = args.until == "2026-11-05" and args.days == 7
    print("window %s .. %s (local, end exclusive); transcripts read: %d files" % (
        dt.datetime.fromtimestamp(lo).date(), until.date(), data["files"]))
    print("files that could not be parsed: %d (transcripts %d, review files %d)" % (
        len(data["bad_files"]) + rv_bad, len(data["bad_files"]), rv_bad))
    print()
    print("== baseline rows")
    for label, v, key, cause in rows:
        line = "%-78s %10s" % (label, fmt(v))
        if base and key:
            b = BASELINE[key]
            line += "  baseline %-8s %s" % (fmt(b), compare(v, b, cause))
        elif base:
            line += "  baseline %-8s %s" % ("-", cause)
        print(line)
    print()
    print("== subagent active time at xhigh or above, per CLI version (field `version` of each transcript line)")
    buckets, per = version_split(x["subs"])
    for k, L in buckets.items():
        v = share_high(L)
        print("%-24s subagents %4d  %s" % (k, len(L), "no data" if v is None else "%.1f%%" % v))
    for k, L in sorted(per.items()):
        print("   %-12s subagents %4d  %.1f%%" % (k, len(L), share_high(L) or 0))
    print()
    print("== new metrics")
    wall = [sum(p.values()) / 60 for p in x["bt"]]
    print("median wall time per branch, min: %s (%d branches)" % ("미측정" if not wall else "%.0f" % median(wall), len(wall)))
    ge3 = sum(1 for v in x["pr_runs"].values() if v >= 3)
    print("PRs with 3 or more review runs: %s" % ("미측정" if not x["pr_runs"] else "%d of %d (%.0f%%)" % (
        ge3, len(x["pr_runs"]), 100 * ge3 / len(x["pr_runs"]))))
    if grades is None:
        over, chk = None, None
        print("requests above the grade ceiling: 미측정 (needs --roles)")
    else:
        over, chk = over_ceiling(data, grades)
        print("requests above the grade ceiling: %d of %d checked subagent requests" % (over, chk))
    print("direct codex exec calls by purpose: %s" % (", ".join("%s %d" % kv for kv in sorted(x["cdx"].items())) or "none"))
    print()
    print("== scorecard (G1-G5)")
    print("G1 result quality: 미측정")
    print("G2 comprehension gates: interview and quiz passes 미측정 (state closed to agents, counted by maeng-interview); "
          "review runs %d, passes %d" % (len(x["rv"]), sum(1 for r in x["rv"] if r[0] == "pass")))
    print("G3 efficiency: full test hours %.1f, time share after the first review %s%%, median wall time per branch %s min" % (
        x["hours"], fmt(x["after"]), "미측정" if not wall else "%.0f" % median(wall)))
    print("G4 role performance: xhigh+ subagent time %s%%, requests above ceiling %s, implementer delegations %d, "
          "delegation calls naming an effort %d of %d" % (
              fmt(share_high(x["subs"])), "미측정" if over is None else over,
              sum(1 for t in data["tools"] if t["name"] in ("Agent", "Task") and "implementer" in str(t["st"])),
              sum(1 for t in data["tools"] if t["name"] in ("Agent", "Task") and t["eff"]),
              sum(1 for t in data["tools"] if t["name"] in ("Agent", "Task"))))
    print("G5 improvability: this script ran in %.0f s; baseline rows reproduced %s" % (
        time.perf_counter() - t0, "미측정" if not base else "%d of %d" % (
            sum(1 for _l, v, k, c in rows if k and compare(v, BASELINE[k], c) == "match"), sum(1 for r in rows if r[2]))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
