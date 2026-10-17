#!/usr/bin/env python3
"""Assert each scenario's expected result from tests/live/evidence/<id>.summary.json (hook events + fs/state facts).
Usage: assert_smoke.py [S1 ...]   -> prints a check table, writes evidence/results.json, exit 1 if any check fails."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EV = HERE / "evidence"
sys.path.insert(0, str(HERE))
BUILTIN_AGENTS = {"claude", "claude-code-guide", "codebase-explorer-builtin", "Explore", "general-purpose", "Plan", "statusline-setup"}
ETA_REPO_AGENTS = {"explorer", "implementer", "planner", "researcher", "reviewer"}  # eta_v1/.claude/agents (eta world, allowed)


def load(sid):
    return json.loads((EV / f"{sid}.summary.json").read_text())


def hooks(S, event, name_prefix=None):
    return [h for h in S["hooks"] if h["event"] == event and (not name_prefix or h["name"].startswith(name_prefix))]


def out_json(h):
    try:
        return json.loads(h["output"])
    except ValueError:
        return {}


def denies(S):
    res = []
    for h in hooks(S, "PreToolUse"):
        spec = out_json(h).get("hookSpecificOutput", {})
        if spec.get("permissionDecision") == "deny":
            res.append(spec.get("permissionDecisionReason", ""))
    return res


def call(S, needle):
    return next((t for t in S["tool_calls"] if needle in t["input"] or needle == t["name"]), None)


def stub_files(S):
    return [k for k in S["fs"]["vault"] if k.startswith("wiki/sessions/SESSION-")]


def sessions(S):
    return [v["state"] for k, v in S["fs"]["home"].items() if k.startswith("sessions/") and "state" in v]


def s1(S):
    stops = hooks(S, "Stop")
    first, second = (out_json(stops[0]), out_json(stops[1])) if len(stops) >= 2 else ({}, {})
    stub = stub_files(S)
    stub_txt = S["fs"]["vault"][stub[0]]["text"] if stub else ""
    return [
        ("first Stop blocks with UNVERIFIED+UNRECORDED", first.get("decision") == "block" and "UNVERIFIED" in first.get("reason", "") and "UNRECORDED" in first.get("reason", "")),
        ("agent received 'Stop hook feedback' continuation", len(S["stop_feedback"]) >= 1),
        ("second Stop allows with systemMessage UNVERIFIED / UNRECORDED", "UNVERIFIED / UNRECORDED" in second.get("systemMessage", "") and "decision" not in second),
        ("exactly two Stop events", len(stops) == 2),
        ("session stub written in temp vault for MAE-223", bool(stub) and "SESSION-MAE-223" in stub[0]),
        ("stub finalized by SessionEnd (ended: timestamp)", "\nended: " in stub_txt),
        ("[extra, design §5.3/5.5] stub still lists the open UNVERIFIED/UNRECORDED items after SessionEnd", "UNVERIFIED" in stub_txt and "UNRECORDED" in stub_txt),
        ("state binds MAE-223 and keeps unverified (no evidence)", any((s["binding"] or {}).get("issue") == "MAE-223" and not s["evidence"] for s in sessions(S))),
    ]


def s2(S):
    stops = hooks(S, "Stop")
    sc = [t for t in S["tool_calls"] if t["name"] == "mcp__claude_ai_Linear__save_comment"]
    st = call(S, "maeng-verify status")
    return [
        ("no Stop block (all Stop outputs empty)", bool(stops) and all(not h["output"].strip() for h in stops)),
        ("no stop-hook feedback injected", not S["stop_feedback"]),
        ("pytest ran and passed", any("pytest" in t["input"] and "1 passed" in (t.get("result") or "") for t in S["tool_calls"])),
        ("exactly one Linear save_comment on MAE-223, succeeded", len(sc) == 1 and "MAE-223" in sc[0]["input"] and "staging S2 record write (automated)" in sc[0]["input"] and not sc[0].get("is_error")),
        ("maeng-verify status shows ship_verified true", bool(st) and '"ship_verified": true' in (st.get("result") or "").replace("  ", " ").replace('"ship_verified":true', '"ship_verified": true') or '"ship_verified": true' in S["result"]["result"]),
        ("state: >=1 ok evidence", any(any(e["ok"] for e in s["evidence"]) for s in sessions(S))),
        ("state: record seq >= change seq", any(s["last_record_seq"] >= s["last_change_seq"] for s in sessions(S))),
        ("session stub written", bool(stub_files(S))),
    ]


def s3(S):
    d = denies(S)
    ms = call(S, "maeng-ship merge 1")
    f = S["facts"]
    return [
        ("A force push denied by G1", any("force pushes are denied" in r for r in d)),
        ("B gh pr merge denied by G1", any("`gh pr merge` is denied" in r for r in d)),
        ("C maeng-ship merge refused (no receipt/unverified), exit 1, nothing pushed", bool(ms) and ms.get("is_error") and ("not ship-verified" in ms["result"] or "merge denied" in ms["result"])),
        ("D push of unverified commit denied by G1", any("not ship-verified" in r and "pushed commit" in r for r in d)),
        ("remote refs unchanged", f["remote_before"] == f["remote_after"]),
        ("fake gh never invoked for merge", not any('"merge"' in l for l in S["gh_log"])),
    ]


WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit", "Bash"}


def s4(S):
    import check_models
    rep = check_models.check(S["init"]["session_id"])
    S["models_report"] = rep
    (EV / "S4.models.json").write_text(json.dumps(rep, indent=1) + "\n")  # fresh per run, never a stale copy
    texts = " ".join(S["result"]["result"].split())
    return [
        ("main session model is opus", "opus" in S["init"]["model"]),
        ("check_models: haiku/opus/sonnet for researcher/architect/implementer, >=1 call each, read-only agents used no write tool", rep["ok"] or str(rep["errors"])),
        ("negative: note.txt not created", S["facts"]["note_txt_exists"] is False),
        ("negative: a later researcher call used no write-capable tool",
         any(c["subagent_type"].endswith("researcher") and not (WRITE_TOOLS & set(c["tools_used"]))
             for c in rep.get("calls", [])[1:])),
        ("frontmatter of researcher/architect lists no write tool", all(t and not ({"Write", "Edit", "Bash"} & set(t)) for t in rep.get("frontmatter_tools", {}).values())),
    ]


def s5(S):
    names = [p["name"] for p in S["init"]["plugins"]]
    agents = set(S["init"]["agents"])
    personal = sorted(a for a in agents if a not in BUILTIN_AGENTS | ETA_REPO_AGENTS and not a.startswith("maeng-tools:") and not a.startswith("eta-"))
    f = S["facts"]
    return [
        ("init plugins include eta-rules, eta-craft, maeng-tools", {"eta-rules", "eta-craft", "maeng-tools"} <= set(names)),
        ("init has NO maeng-harness", "maeng-harness" not in names),
        ("no personal agents beyond maeng-tools ones (init.agents)", not personal or f"personal agents leaked: {personal}"),
        ("no personal loose skills in init.skills (e.g. harness-run, work-records)", not ({"harness-run", "work-records", "obsidian-workspace"} & set(S["init"]["skills"])) or "loose ~/.claude/skills still loaded (pre-retirement)"),
        ("zero maeng hook output (no hook output mentions maeng)", all("maeng" not in (h["output"] + h["stderr"]).lower() for h in S["hooks"])),
        ("temp MAENG_HOME/VAULT unchanged (empty)", not S["fs"]["home"] and not S["fs"]["vault"]),
        ("eta team checkouts (dev, contracts, web, docs) and eta_v1 folder unchanged", f["eta_before"] == f["eta_after"]),
        ("session answered OK", S["result"]["result"].strip() == "OK"),
    ]


def s9(S):
    names = [p["name"] for p in S["init"]["plugins"]]
    f = S["facts"]
    ctx = [h for h in S["hooks"] if h["event"] == "SessionStart" and h["output"].strip()]
    other = [h for h in S["hooks"] if h["event"] != "SessionStart" and h["output"].strip()]
    txt = out_json(ctx[0]).get("hookSpecificOutput", {}).get("additionalContext", "") if ctx else ""
    return [
        ("init plugins include eta-rules and eta-craft (team checkout loads eta plugins)", {"eta-rules", "eta-craft"} <= set(names)),
        ("init does NOT list linear (personal synced plugin off)", not any(n.startswith("linear") for n in names)),
        ("at most one SessionStart line, single-line", len(ctx) <= 1 and "\n" not in txt),
        ("no other hook produced output (no block/deny/context)", not other),
        ("no personal record writes (temp MAENG_HOME and vault empty)", not S["fs"]["home"] and not S["fs"]["vault"]),
        ("no Stop feedback", not S["stop_feedback"]),
        ("dev/contracts git status and HEAD unchanged", f["checkout_before"] == f["checkout_after"]),
        ("session answered OK", S["result"]["result"].strip() == "OK"),
    ]


def s6(S):
    ctx = [h for h in S["hooks"] if h["event"] == "SessionStart" and h["output"].strip()]
    other = [h for h in S["hooks"] if h["event"] != "SessionStart" and h["output"].strip()]
    txt = out_json(ctx[0]).get("hookSpecificOutput", {}).get("additionalContext", "") if ctx else ""
    return [
        ("exactly one SessionStart warning line", len(ctx) == 1 and "\n" not in txt and "maeng-eta-isolate" in txt),
        ("no other hook produced output (no block/deny/context)", not other),
        ("temp MAENG_HOME state dir empty (no session state, no last-bindings)", not S["fs"]["home"]),
        ("temp vault empty (no session stub)", not S["fs"]["vault"]),
        ("no Stop feedback", not S["stop_feedback"]),
        ("agent actions unaffected (hello.txt written, HEAD unchanged)", S["facts"]["hello_exists"] and S["facts"]["git"]["head"] == S["facts"]["head_before"]),
    ]


def g3_denied(S, needle):
    """True when the tool call whose command contains `needle` was denied by a maeng G3 hook."""
    for c in S["tool_calls"]:
        if needle in (c.get("input") or "") and c.get("is_error") and "maeng G3" in (c.get("result") or ""):
            return True
    return False


def s7(S):
    d = denies(S)
    a = next((c for c in S["tool_calls"] if (c.get("input") or "").startswith("[redacted eta call")), None)
    f = S["facts"]
    return [
        ("A read-only git -C on a real eta checkout allowed and returned output",
         bool(a) and not a.get("is_error") and "0 lines" not in (a.get("result") or "")),
        # Match the denied command and a G3 denial, not one exact message (taint or command-specific checks may answer).
        ("B git -C eta-classified repo commit denied by G3", g3_denied(S, "commit --allow-empty")),
        ("C gh pr create -R endix-foundation-v1/x denied by G3", g3_denied(S, "gh pr create -R endix-foundation-v1/x")),
        ("eta-classified repo HEAD unchanged", f["eta_repo_head_before"] == f["eta_repo_head_after"]),
        ("eta team checkouts and eta_v1 folder unchanged", f["eta_before"] == f["eta_after"]),
        ("fake gh not invoked for pr create", not any("create" in l for l in S["gh_log"])),
    ]


def s8(S):
    f = S["facts"]
    ship = call(S, "maeng-ship merge 1")
    rec = f["receipts"][0] if f["receipts"] else {}
    ev_trees = {e["tree_finish"] for s in sessions(S) for e in s["evidence"] if e["ok"]}
    return [
        ("maeng-ship merge succeeded", bool(ship) and not ship.get("is_error") and "merged PR 1" in ship["result"]),
        ("remote main fast-forwarded to reviewed head", f["remote_after"]["refs/heads/main"]["oid"] == f["head"]),
        ("receipt consumed (single use)", rec.get("status") == "consumed" and rec.get("result", {}).get("merge_sha") == f["head"]),
        ("merge tree == verified tree == feat tree", f["remote_after"]["refs/heads/main"]["tree"] == f["feat_tree"] and f["feat_tree"] in ev_trees),
        ("no hook deny along the flow", not denies(S)),
        ("feat branch untouched on remote", f["remote_before"]["refs/heads/feat"] == f["remote_after"]["refs/heads/feat"]),
    ]


def gf_factory(expect_block):
    def gf(S):
        pushed = "refs/heads/feat" in S["facts"]["remote_after"]
        push = call(S, "git push origin feat")
        blocked = bool(push) and push.get("is_error") and ("onFailure" in push["result"] or "hook error" in push["result"])
        return [
            (f"git push {'blocked' if expect_block else 'allowed'} through Claude Code", blocked if expect_block else not blocked),
            ("remote has no feat branch" if expect_block else "remote received feat (fail-open)", (not pushed) if expect_block else pushed),
        ]
    return gf


CHECKS = {"S1": s1, "S2": s2, "S3": s3, "S4": s4, "S5": s5, "S6": s6, "S7": s7, "S8": s8, "S9": s9,
          "GF1": gf_factory(True), "GF2": gf_factory(True), "GF3": gf_factory(True), "GF4": gf_factory(True)}


def main(ids):
    results, bad = {}, 0
    run = json.loads((EV / "run.json").read_text()) if (EV / "run.json").exists() else {}
    for sid in ids:
        try:
            S = load(sid)
            if not run or S.get("run_id") != run.get("run_id"):
                rows = [("evidence is from the current run (run.json run_id matches)",
                         f"stale or unmatched evidence: summary run_id={S.get('run_id')} run.json={run.get('run_id')}")]
            elif S.get("error"):
                rows = [("scenario ran without crashing", S["error"].strip().splitlines()[-1])]
            else:
                rows = CHECKS[sid](S)
        except Exception as exc:  # noqa: BLE001
            rows = [(f"assertion crashed: {type(exc).__name__}: {exc}", False)]
        results[sid] = [{"check": n, "pass": ok is True, "detail": ("" if ok is True else str(ok))} for n, ok in rows]
        print(f"== {sid}")
        for r in results[sid]:
            print(f"  [{'PASS' if r['pass'] else 'FAIL'}] {r['check']}" + (f"  <- {r['detail']}" if r["detail"] and r["detail"] != "False" else ""))
            bad += not r["pass"]
    (EV / "results.json").write_text(json.dumps(results, indent=1) + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or list(CHECKS)))
