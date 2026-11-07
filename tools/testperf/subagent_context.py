#!/usr/bin/env python3
"""MAE-323 AC-11: what a subagent's first request carries, read from its Claude Code transcript.

`record` launches the probe itself (fresh session, nonce in the prompt, candidate definition hashed) so the
transcript is bound to the launch; the check re-reads it and verifies nonce, definition hash and plugin version.
A missing usage field is `unknown`, never zero, and `--require-observed` fails on unknown. Stdlib only.

  subagent_context.py record --plugin-dir plugins/maeng-tools --out E                    # launch, record, check
  subagent_context.py --evidence E --omit-trial agent-y.jsonl                            # record the trial, check
  subagent_context.py --evidence E --max-input-tokens 20000 --require-observed          # check only
"""
import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid

CACHE = ("cache_creation_input_tokens", "cache_read_input_tokens")
STANDARD = "maeng-tools:standard"
TRIAL = "maeng-tools:design"


def first_user_text(path):
    """Text of the first user message of a transcript ('' when there is none)."""
    for l in open(path, encoding="utf-8"):
        r = json.loads(l) if l.strip() else {}
        if r.get("type") == "user":
            c = (r.get("message") or {}).get("content")
            return c if isinstance(c, str) else " ".join(x.get("text", "") for x in c or [] if isinstance(x, dict))
    return ""


def definition_sha256(repo):
    return hashlib.sha256(open(os.path.join(repo, "plugins", "maeng-tools", "agents", "standard.md"), "rb").read()).hexdigest()


def probe(repo, plugin_dir, projects):
    """Launch one headless session that spawns the standard agent with a nonce; return the binding fields."""
    nonce, sid = os.urandom(8).hex(), str(uuid.uuid4())
    prompt = (f"Call the Agent tool exactly once with subagent_type {STANDARD} and the prompt "
              f"'probe {nonce}: reply with the single word ok'. Then reply done.")
    # prompt before the variadic --allowedTools, which swallows a following argument
    r = subprocess.run(["claude", "-p", prompt, "--session-id", sid, "--plugin-dir", plugin_dir,
                        "--allowedTools", "Agent"], capture_output=True, text=True, cwd=repo)
    slug = re.sub(r"[^A-Za-z0-9]", "-", repo)
    files = [f for f in glob.glob(os.path.join(projects, slug, sid, "subagents", "agent-*.jsonl"))]
    if r.returncode or not files:
        raise SystemExit(f"probe failed (exit {r.returncode}, {len(files)} subagent transcripts): {r.stderr[-300:]}")
    return {"nonce": nonce, "session_id": sid, "plugin_dir": plugin_dir, "path": files[0]}


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


def binding_problems(std, repo):
    """The transcript must carry the launch nonce and the candidate definition must be the one that was hashed."""
    out = []
    path = os.path.expanduser(std.get("transcript") or "")
    if not std.get("nonce"):
        out.append("standard: nonce missing")
    elif os.path.isfile(path) and std["nonce"] not in first_user_text(path):
        out.append("standard: nonce not in the transcript's first user message (not the recorded launch)")
    if not std.get("definition_sha256"):
        out.append("standard: definition_sha256 missing")
    elif std["definition_sha256"] != definition_sha256(repo):
        out.append("standard: definition_sha256 differs from this checkout's agents/standard.md")
    return out


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
    return out + binding_problems(std, repo)


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
    argv = sys.argv[1:] if argv is None else argv
    rec = bool(argv) and argv[0] == "record"
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--evidence", required=not rec, help="evidence JSON, read and (when recording) written")
    ap.add_argument("--out", help="record: evidence JSON to write (default --evidence)")
    ap.add_argument("--plugin-dir", default="plugins/maeng-tools", help="record: candidate plugin tree")
    ap.add_argument("--max-input-tokens", type=int, default=20000)
    ap.add_argument("--require-observed", action="store_true", help="fail on unknown usage")
    ap.add_argument("--omit-trial", help="transcript of the omitClaudeMd trial on the design agent")
    ap.add_argument("--projects-dir", default=os.path.expanduser("~/.claude/projects"))
    a = ap.parse_args(argv[1:] if rec else argv)
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if rec:
        a.evidence, a.require_observed = a.out or a.evidence, True
        if not a.evidence:
            ap.error("record needs --out")
    ev = json.load(open(a.evidence)) if os.path.exists(a.evidence) else {}
    if rec:
        # the definition and version are hashed before the launch; the transcript is read after it
        sha, ver = definition_sha256(repo), plugin_info(repo)["version"]
        bind = probe(repo, a.plugin_dir, a.projects_dir)
        std = observe(bind.pop("path"))
        if bind["nonce"] not in first_user_text(std["transcript"]):
            print("nonce not in the subagent transcript's first user message", file=sys.stderr)
            return 2
        ev["standard"] = {**bind, "definition_sha256": sha, **std}
    if a.omit_trial:
        ev["omit_claude_md_trial"] = observe(a.omit_trial)
    if rec or a.omit_trial:
        ev["plugin"] = plugin_info(repo)
        ev["plugin"]["loaded_with"] = f"--plugin-dir {a.plugin_dir}"
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
