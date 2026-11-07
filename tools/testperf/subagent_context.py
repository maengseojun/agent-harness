#!/usr/bin/env python3
"""MAE-323 AC-11: what a subagent's first request carries, read from its Claude Code transcript.

Record an observation (path given, or the newest transcript modified after a probe) into the evidence JSON, then
check it. A missing usage field is `unknown`, never zero, and `--require-observed` fails on unknown. Stdlib only.

  subagent_context.py --evidence E --standard agent-x.jsonl --omit-trial agent-y.jsonl   # record, then check
  subagent_context.py --evidence E --max-input-tokens 20000 --require-observed          # check only
"""
import argparse
import glob
import json
import os
import re
import sys

CACHE = ("cache_creation_input_tokens", "cache_read_input_tokens")
STANDARD = "maeng-tools:standard"
TRIAL = "maeng-tools:design"


def newest_after(projects, epoch):
    slug = re.sub(r"[^A-Za-z0-9]", "-", os.getcwd())
    files = [f for f in glob.glob(os.path.join(projects, slug, "*", "subagents", "agent-*.jsonl"))
             if os.path.getmtime(f) > epoch]
    return max(files, key=os.path.getmtime) if files else None


def observe(path):
    """The first request of one subagent transcript: usage, agent type, model, CLI version, CLAUDE.md presence."""
    recs = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    meta = path[:-len(".jsonl")] + ".meta.json"
    agent = json.load(open(meta)).get("agentType") if os.path.exists(meta) else None
    reply = next((r for r in recs if r.get("type") == "assistant"
                  and isinstance((r.get("message") or {}).get("usage"), dict)), None)
    usage = reply["message"]["usage"] if reply else {}
    claude_md = any("Contents of" in x.get("text", "") and "CLAUDE.md" in x.get("text", "")
                    for r in recs if r.get("type") == "api-request-blob"
                    for x in (r.get("message") or {}).get("content", []) if isinstance(x, dict))
    out = {"transcript": path, "agent_type": agent, "model": (reply or {}).get("message", {}).get("model"),
           "cli_version": next((r["version"] for r in recs if r.get("version")), None),
           "input_tokens": usage.get("input_tokens"), "claude_md_in_first_request": claude_md}
    for k in CACHE:
        out[k] = usage.get(k)
    parts = [out["input_tokens"]] + [out[k] for k in CACHE]
    out["total_input_tokens"] = sum(parts) if all(isinstance(p, int) for p in parts) else None
    out["status"] = "observed" if out["total_input_tokens"] is not None and agent and out["model"] else "unknown"
    return out


def plugin_info(repo):
    p = json.load(open(os.path.join(repo, "plugins", "maeng-tools", ".claude-plugin", "plugin.json")))
    return {"name": p["name"], "version": p["version"], "loaded_with": "--plugin-dir plugins/maeng-tools"}


def trial_result(std, trial):
    """supported only when the baseline run shows the CLAUDE.md block and the trial run does not."""
    if std["status"] != "observed" or trial["status"] != "observed":
        return "unknown"
    return "supported" if std["claude_md_in_first_request"] and not trial["claude_md_in_first_request"] \
        else "unsupported"


def transcript_problems(std, repo):
    """Re-read the recorded transcript and compare it with the JSON; the JSON alone proves nothing."""
    path = os.path.expanduser(std.get("transcript") or "")
    if not os.path.isfile(path):
        return [f"standard: transcript missing: {path!r}"]
    try:
        seen = observe(path)
    except (ValueError, OSError) as e:
        return [f"standard: transcript is not readable JSONL: {e}"]
    out = [f"standard: {k} is {std.get(k)!r} in the JSON but {seen[k]!r} in the transcript"
           for k in ("agent_type", "model", "cli_version", "total_input_tokens") if std.get(k) != seen[k]]
    total = seen["total_input_tokens"]
    if not isinstance(total, int) or total <= 0:
        out.append(f"standard: transcript usage total is {total!r}, not a positive count (unknown, not zero)")
    return out


def problems(ev, limit, require, repo=None):
    std = ev.get("standard") or {}
    out = []
    if std.get("agent_type") != STANDARD:
        out.append(f"standard: transcript belongs to {std.get('agent_type')!r}, not {STANDARD!r}")
    total = std.get("total_input_tokens")
    if isinstance(total, int) and total > limit:
        out.append(f"standard: first request carries {total} input tokens, over {limit}")
    if require:  # unknown is a failure only here; without the flag it is just reported
        if std.get("status") != "observed":
            out.append("standard: no observed usage (unknown)")
        out += [f"standard: {k} missing" for k in ("cli_version", "model") + CACHE if std.get(k) is None]
        have = (ev.get("plugin") or {}).get("version")
        if not have:
            out.append("plugin version missing")
        elif repo and have != plugin_info(repo)["version"]:
            out.append(f"plugin version {have!r} differs from this checkout's {plugin_info(repo)['version']!r}")
        if repo:
            out += transcript_problems(std, repo)
        if (ev.get("omit_claude_md_trial") or {}).get("result") not in ("supported", "unsupported"):
            out.append("omitClaudeMd trial not recorded")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--evidence", required=True, help="evidence JSON, read and (when recording) written")
    ap.add_argument("--max-input-tokens", type=int, default=20000)
    ap.add_argument("--require-observed", action="store_true", help="fail on unknown usage")
    ap.add_argument("--standard", help="transcript of the standard-agent probe")
    ap.add_argument("--omit-trial", help="transcript of the omitClaudeMd trial on the design agent")
    ap.add_argument("--after", type=float, help="use the newest transcript modified after this epoch instead of a path")
    ap.add_argument("--projects-dir", default=os.path.expanduser("~/.claude/projects"))
    a = ap.parse_args(argv)
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ev = json.load(open(a.evidence)) if os.path.exists(a.evidence) else {}
    for key, given in (("standard", a.standard), ("omit_claude_md_trial", a.omit_trial)):
        if given:
            path = newest_after(a.projects_dir, a.after) if given == "newest" else given
            if not path:
                print(f"no transcript after {a.after}", file=sys.stderr)
                return 2
            ev[key] = observe(path)
    if a.standard or a.omit_trial:
        ev["plugin"] = plugin_info(repo)
        ev["cli_version"] = (ev.get("standard") or {}).get("cli_version")
        if "standard" in ev and "omit_claude_md_trial" in ev:
            ev["omit_claude_md_trial"].update(
                field="omitClaudeMd", result=trial_result(ev["standard"], ev["omit_claude_md_trial"]),
                baseline_claude_md_in_first_request=ev["standard"]["claude_md_in_first_request"])
        json.dump(ev, open(a.evidence, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        open(a.evidence, "a").write("\n")
    bad = problems(ev, a.max_input_tokens, a.require_observed, repo)
    std = ev.get("standard") or {}
    print(f"standard input tokens: {std.get('total_input_tokens')} (input {std.get('input_tokens')}, "
          f"cache_creation {std.get('cache_creation_input_tokens')}, cache_read {std.get('cache_read_input_tokens')}); "
          f"limit {a.max_input_tokens}; plugin {(ev.get('plugin') or {}).get('version')}; cli {ev.get('cli_version')}; "
          f"omitClaudeMd {(ev.get('omit_claude_md_trial') or {}).get('result')}")
    for p in bad:
        print("FAIL " + p, file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
