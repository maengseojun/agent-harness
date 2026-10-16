#!/usr/bin/env python3
"""Model-routing check (design §2): for a session, find parent-transcript Agent calls by subagent_type
maeng-tools:{architect,implementer,researcher}, correlate each with subagents/agent-*.jsonl (via meta.json toolUseId),
and assert the resolved model family. Requires >= 1 call per type. Also asserts that read-only agents used no write tool.

Usage: check_models.py <session_id> | --summary evidence/S4.summary.json
Exit 0 on pass, 1 on failure. Prints a JSON report.
"""
import glob
import json
import os
import sys
from pathlib import Path

EXPECT = {"maeng-tools:architect": "opus", "maeng-tools:implementer": "sonnet", "maeng-tools:researcher": "haiku"}
READ_ONLY = {"maeng-tools:architect", "maeng-tools:researcher"}
WRITE_TOOLS = {"Write", "Edit", "NotebookEdit", "MultiEdit", "Bash"}
AGENTS_DIR = Path(__file__).resolve().parents[2] / "plugins/maeng-tools/agents"


def family(model):
    m = (model or "").lower()
    return next((f for f in ("opus", "sonnet", "haiku") if f in m), "unknown")


def frontmatter_tools(agent):
    name = agent.split(":")[1]
    for line in (AGENTS_DIR / f"{name}.md").read_text().splitlines()[1:]:
        if line.strip() == "---":
            break
        if line.startswith("tools:"):
            return [t.strip() for t in line.split(":", 1)[1].split(",")]
    return None  # inherits


def load(path):
    out = []
    for line in Path(path).read_text().splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def check(session_id):
    hits = glob.glob(os.path.expanduser(f"~/.claude/projects/*/{session_id}.jsonl"))
    if not hits:
        return {"ok": False, "error": f"no transcript for session {session_id}"}
    transcript = Path(hits[0])
    subdir = transcript.with_suffix("") / "subagents"
    calls, results = {}, {}
    for d in load(transcript):
        content = d.get("message", {}).get("content")
        if not isinstance(content, list):
            continue
        for c in content:
            if c.get("type") == "tool_use" and c.get("name") in ("Agent", "Task"):
                calls[c["id"]] = c["input"].get("subagent_type")
            elif c.get("type") == "tool_result" and isinstance(d.get("toolUseResult"), dict):
                results[c["tool_use_id"]] = d["toolUseResult"]
    sub = {}
    for meta in subdir.glob("agent-*.meta.json"):
        m = json.loads(meta.read_text())
        models, tools = set(), set()
        for d in load(meta.with_suffix("").with_suffix(".jsonl")):
            msg = d.get("message", {})
            if msg.get("role") == "assistant" and msg.get("model"):
                models.add(msg["model"])
            for c in msg.get("content") if isinstance(msg.get("content"), list) else []:
                if c.get("type") == "tool_use":
                    tools.add(c["name"])
        sub[m["toolUseId"]] = {"agentType": m.get("agentType"), "models": sorted(models), "tools_used": sorted(tools)}
    rows, errors = [], []
    seen = {t: 0 for t in EXPECT}
    for tuid, stype in calls.items():
        if stype not in EXPECT:
            continue
        seen[stype] += 1
        s = sub.get(tuid)
        if not s:
            errors.append(f"{stype} call {tuid}: no subagent transcript")
            continue
        fams = {family(m) for m in s["models"]}
        row = {"subagent_type": stype, "tool_use_id": tuid, "models": s["models"], "resolvedModel":
               (results.get(tuid) or {}).get("resolvedModel"), "tools_used": s["tools_used"], "expected": EXPECT[stype]}
        if fams != {EXPECT[stype]}:
            errors.append(f"{stype}: expected {EXPECT[stype]} got {s['models']}")
        if family(row["resolvedModel"]) != EXPECT[stype]:
            errors.append(f"{stype}: resolvedModel {row['resolvedModel']} != {EXPECT[stype]}")
        if stype in READ_ONLY and WRITE_TOOLS & set(s["tools_used"]):
            errors.append(f"{stype}: used write-capable tool(s) {sorted(WRITE_TOOLS & set(s['tools_used']))}")
        rows.append(row)
    for t, n in seen.items():
        if n < 1:
            errors.append(f"no call to {t}")
    static = {}
    for a in READ_ONLY:
        tl = frontmatter_tools(a)
        static[a] = tl
        if tl is None or WRITE_TOOLS & set(tl):
            errors.append(f"{a}: frontmatter tools {tl} allow writes")
    return {"ok": not errors, "session": session_id, "transcript": str(transcript), "calls": rows,
            "frontmatter_tools": static, "errors": errors}


if __name__ == "__main__":
    sid = sys.argv[1]
    if sid == "--summary":
        sid = json.load(open(sys.argv[2]))["init"]["session_id"]
    rep = check(sid)
    print(json.dumps(rep, indent=1))
    sys.exit(0 if rep["ok"] else 1)
