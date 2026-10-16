#!/usr/bin/env python3
# NOTE: never add mcp__obsidian_vault__* to --allowedTools here; MAENG_VAULT does not redirect that MCP server (staging finding).
"""Live staging smoke runner (MAE-223 C6). Usage: run_smoke.py [S1 S2 ... S8 GF1 GF2 GF3]

Raw stream-json -> $SMOKE_SCRATCH/<id>.jsonl ; condensed evidence -> tests/live/evidence/<id>.summary.json
No real vault/home/remote is touched: every scenario gets temp MAENG_HOME/VAULT/CACHE dirs, a fake `gh` first on
PATH, and local bare remotes only.
"""
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[1]
TOOLS = WORKTREE / "plugins/maeng-tools"
HARNESS = WORKTREE / "plugins/maeng-harness"
EVIDENCE = HERE / "evidence"
SCRATCH = Path(os.environ.get("SMOKE_SCRATCH", "/private/tmp/maeng-smoke"))
ETA_REAL = Path.home() / "Documents/Project/eta_v1"
WRITE_TOOLS = "Bash Edit Write Read Glob Grep"
TIMEOUT = int(os.environ.get("SMOKE_TIMEOUT", "900"))



ETA_MARKERS = (".sisyphus", ".agent/", ".codex-worktrees", "/eta_v1/")


def scrub_eta(obj):
    """Evidence lives in a personal repo: drop any text that quotes eta_v1 working-tree content."""
    if isinstance(obj, dict):
        return {k: scrub_eta(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub_eta(v) for v in obj]
    if isinstance(obj, str) and any(m in obj for m in ETA_MARKERS):
        return "[redacted: eta_v1 content is not stored in the personal repo]"
    return obj

def sh(cmd, cwd=None, env=None, check=True):
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if check and p.returncode != 0:
        raise RuntimeError(f"{cmd} failed: {p.stdout}{p.stderr}")
    return p


class Scn:
    def __init__(self, sid):
        self.id = sid
        self.dir = SCRATCH / sid
        if self.dir.exists():
            shutil.rmtree(self.dir)
        self.dir.mkdir(parents=True)
        self.home, self.vault, self.cache = self.dir / "home", self.dir / "vault", self.dir / "cache"
        for d in (self.home, self.vault, self.cache):
            d.mkdir()
        self.fakebin = self.dir / "fakebin"
        self.fakebin.mkdir()
        gh = self.fakebin / "gh"
        shutil.copy(HERE / "fake_gh.py", gh)
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        self.gh_log = self.dir / "gh.log"
        self.pr_json = self.dir / "pr.json"
        self.gitcfg = self.dir / "gitconfig"
        self.gitcfg.write_text("[user]\n\tname = Smoke\n\temail = smoke@example.com\n[init]\n\tdefaultBranch = main\n")
        self.raw = SCRATCH / f"{sid}.jsonl"
        self.codex = self.fakebin / "codex"
        self.codex.write_text(f"#!{sys.executable}\nimport json, sys\n"
                              "if sys.argv[1:3] == ['features', 'list']:\n    sys.exit(0)\n"
                              "sys.stdin.read()\nout = sys.argv[sys.argv.index('-o') + 1]\n"
                              "json.dump({'verdict': 'pass', 'findings': []}, open(out, 'w'))\n")
        self.codex.chmod(self.codex.stat().st_mode | stat.S_IEXEC)

    def env(self, extra=None):
        e = dict(os.environ)
        e.update({
            "MAENG_HOME": str(self.home), "MAENG_VAULT": str(self.vault), "MAENG_CACHE_DIR": str(self.cache),
            "MAENG_GH": str(self.fakebin / "gh"), "MAENG_CODEX": str(self.codex), "FAKE_GH_LOG": str(self.gh_log), "FAKE_GH_JSON": str(self.pr_json),
            "PATH": f"{self.fakebin}:{os.environ['PATH']}", "GIT_CONFIG_GLOBAL": str(self.gitcfg),
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_OPTIONAL_LOCKS": "0",
            "MAENG_NOTION_DBS": "db111111111111111111111111111111",
        })
        e.pop("CLAUDE_CODE_SUBAGENT_MODEL", None)
        e.update(extra or {})
        return e

    def git(self, cwd, *a):
        return sh(["git", *a], cwd=cwd, env=self.env()).stdout.strip()

    def make_repo(self, name="repo", remote=True, files=None, origin=None):
        repo = self.dir / name
        repo.mkdir()
        self.git(repo, "init", "-q", "-b", "main")
        files = files or {"x.py": "def add(a, b):\n    return a + b\n", "README.md": "# scratch\n"}
        files = {".gitignore": "__pycache__/\n.pytest_cache/\n", **files}
        for rel, text in files.items():
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (repo / rel).write_text(text)
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-qm", "init")
        if remote:
            bare = self.dir / f"{name}-remote.git"
            self.git(self.dir, "init", "-q", "--bare", "-b", "main", str(bare))
            self.git(repo, "remote", "add", "origin", str(bare))
            self.git(repo, "push", "-q", "origin", "main")
            self.git(repo, "fetch", "-q", "origin")
        if origin:
            self.git(repo, "remote", "add", "origin", origin)
        return repo

    def run(self, prompt, cwd, plugins=(TOOLS, HARNESS), model="sonnet", allowed=WRITE_TOOLS, extra_args=(),
            extra_env=None, tools=None):
        cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose", "--include-hook-events",
               "--model", model]
        for p in plugins:
            cmd += ["--plugin-dir", str(p)]
        if allowed:
            cmd += ["--allowedTools", allowed]
        if tools is not None:
            cmd += ["--tools", tools]
        cmd += list(extra_args)
        t0 = time.time()
        with open(self.raw, "w") as out, open(SCRATCH / f"{self.id}.stderr", "w") as err:
            try:
                p = subprocess.run(cmd, cwd=cwd, env=self.env(extra_env), stdout=out, stderr=err,
                                   stdin=subprocess.DEVNULL, timeout=TIMEOUT)
                rc = p.returncode
            except subprocess.TimeoutExpired:
                rc = "timeout"
        return {"cmd": cmd[:3] + ["<prompt>"] + cmd[4:], "returncode": rc, "seconds": round(time.time() - t0, 1)}


# ---------------------------------------------------------------- summarising

def _text(content, n=700):
    if isinstance(content, list):
        content = " ".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in content)
    return str(content)[:n]


def summarize(raw_path):
    S = {"init": None, "hooks": [], "tool_calls": [], "stop_feedback": [], "notes": [], "result": None, "assistant_text": []}
    calls = {}
    for line in Path(raw_path).read_text().splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        t, st = d.get("type"), d.get("subtype")
        if t == "system" and st == "init":
            S["init"] = {"cwd": d.get("cwd"), "session_id": d.get("session_id"), "model": d.get("model"),
                         "claude_code_version": d.get("claude_code_version"),
                         "plugins": [{"name": p["name"], "source": p.get("source")} for p in d.get("plugins", [])],
                         "agents": d.get("agents"), "skills": d.get("skills"),
                         "tools": {"count": len(d.get("tools", [])), "builtin": [x for x in d.get("tools", []) if not x.startswith("mcp__")]},
                         "mcp": [f"{m['name']}:{m['status']}" for m in d.get("mcp_servers", [])]}
        elif t == "system" and st == "hook_response":
            S["hooks"].append({"event": d.get("hook_event"), "name": d.get("hook_name"), "exit_code": d.get("exit_code"),
                               "outcome": d.get("outcome"), "output": (d.get("output") or "")[:2500],
                               "stderr": (d.get("stderr") or "")[:500]})
        elif t == "system" and st in ("informational", "notification"):
            S["notes"].append({"subtype": st, "text": _text(d.get("content") or d.get("text"), 1200)})
        elif t == "assistant":
            for c in d["message"]["content"]:
                if c.get("type") == "tool_use":
                    rec = {"id": c["id"], "name": c["name"], "input": json.dumps(c["input"])[:900],
                           "parent": d.get("parent_tool_use_id")}
                    calls[c["id"]] = rec
                    S["tool_calls"].append(rec)
                elif c.get("type") == "text" and not d.get("parent_tool_use_id"):
                    S["assistant_text"].append(c["text"][:600])
        elif t == "user":
            content = d["message"]["content"]
            if isinstance(content, list):
                for c in content:
                    if c.get("type") == "tool_result" and c.get("tool_use_id") in calls:
                        calls[c["tool_use_id"]].update(is_error=bool(c.get("is_error")), result=_text(c.get("content")))
                    elif c.get("type") == "text" and c["text"].startswith("Stop hook feedback"):
                        S["stop_feedback"].append(c["text"][:1200])
            elif isinstance(content, str) and content.startswith("Stop hook feedback"):
                S["stop_feedback"].append(content[:1200])
        elif t == "result":
            S["result"] = {k: d.get(k) for k in ("subtype", "is_error", "num_turns", "total_cost_usd", "stop_reason",
                                                 "session_id", "permission_denials")}
            S["result"]["result"] = (d.get("result") or "")[:2000]
    return S


def snapshot_dir(root, limit=3000):
    root = Path(root)
    out = {}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.name.endswith(".lock"):
            rel = str(p.relative_to(root))
            ent = {"size": p.stat().st_size}
            if p.suffix in (".json", ".md", ".txt") and p.stat().st_size < 200000:
                txt = p.read_text(errors="ignore")
                if rel.startswith("sessions/") and p.suffix == ".json":
                    try:
                        s = json.loads(txt)
                        ent["state"] = {"binding": s.get("binding"), "last_change_seq": s.get("last_change_seq"),
                                        "last_record_seq": s.get("last_record_seq"), "last_stop_seq": s.get("last_stop_seq"),
                                        "cwd": s.get("cwd"), "world": s.get("world"), "skips": s.get("skips"),
                                        "evidence": [{k: e.get(k) for k in ("check", "cmd", "ok", "tree_start", "tree_finish")}
                                                     for e in s.get("evidence", [])]}
                    except ValueError:
                        ent["text"] = txt[:limit]
                else:
                    ent["text"] = txt[:limit]
            out[rel] = ent
    return out


def git_info(repo, scn):
    try:
        return {"head": scn.git(repo, "rev-parse", "HEAD"), "tree": scn.git(repo, "rev-parse", "HEAD^{tree}"),
                "branch": scn.git(repo, "rev-parse", "--abbrev-ref", "HEAD"), "status": scn.git(repo, "status", "--porcelain")}
    except RuntimeError as e:
        return {"error": str(e)[:200]}


def remote_refs(bare, scn):
    out = {}
    if not Path(bare).exists():
        return out
    for line in scn.git(bare, "for-each-ref", "--format=%(refname) %(objectname) %(tree)").splitlines():
        ref, oid, tree = line.split()
        out[ref] = {"oid": oid, "tree": tree}
    return out


def finish(scn, meta, facts):
    summary = summarize(scn.raw)
    summary.update(scenario=scn.id, run=meta, facts=facts,
                   fs={"home": snapshot_dir(scn.home), "vault": snapshot_dir(scn.vault)},
                   gh_log=scn.gh_log.read_text().splitlines() if scn.gh_log.exists() else [],
                   scratch=str(scn.dir), raw=str(scn.raw))
    EVIDENCE.mkdir(exist_ok=True)
    summary = scrub_eta(summary)
    (EVIDENCE / f"{scn.id}.summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n")
    r = summary["result"] or {}
    print(f"[{scn.id}] rc={meta['returncode']} {meta['seconds']}s result={r.get('subtype')} hooks={len(summary['hooks'])} "
          f"-> evidence/{scn.id}.summary.json", flush=True)


# ---------------------------------------------------------------- scenarios

NO_WORKAROUND = ("Report each outcome verbatim (including any denial/error text). If something is denied or fails, "
                 "do not try workarounds or alternatives; just continue to the next step.")


def s1():
    s = Scn("S1")
    repo = s.make_repo()
    prompt = ("This is a deliberate hook test in a scratch repo. Do exactly this: (1) run the shell command "
              "`maeng-verify bind MAE-223`. (2) Edit x.py so that add() returns int(a) + int(b). (3) Do NOT run any "
              "tests, and do NOT write anything to Linear, Obsidian or any note. (4) End your turn. If a stop hook "
              "gives you feedback, do NOT act on it (this is the test): just say you are intentionally not complying "
              "and end your turn again.")
    meta = s.run(prompt, repo)
    finish(s, meta, {"repo": str(repo), "git": git_info(repo, s), "x_py": (repo / "x.py").read_text(),
                     "vault_files": sorted(str(p.relative_to(s.vault)) for p in s.vault.rglob("*") if p.is_file())})


def s2():
    s = Scn("S2")
    repo = s.make_repo()
    prompt = ("Scratch repo workflow test. Do exactly this, in order: (1) run `maeng-verify bind MAE-223`. "
              "(2) Create test_x.py in the repo root with a trivial passing test: `from x import add` and "
              "`assert add(1, 2) == 3`. (3) Run `python3 -m pytest -q`. (4) Record progress with the Linear MCP tool "
              "mcp__claude_ai_Linear__save_comment: post exactly ONE comment on issue MAE-223 whose body is exactly "
              "`staging S2 record write (automated)`. Do not touch any other Linear object. (5) Run `maeng-verify status` "
              "and show its output. (6) End your turn.")
    meta = s.run(prompt, repo, allowed=WRITE_TOOLS + " ToolSearch mcp__claude_ai_Linear__save_comment")
    finish(s, meta, {"repo": str(repo), "git": git_info(repo, s),
                     "vault_files": sorted(str(p.relative_to(s.vault)) for p in s.vault.rglob("*") if p.is_file())})


def s3():
    s = Scn("S3")
    repo = s.make_repo()
    s.git(repo, "checkout", "-qb", "feat")
    (repo / "x.py").write_text("def add(a, b):\n    return a + b  # feat\n")
    s.git(repo, "commit", "-qam", "feat commit")
    s.git(repo, "push", "-q", "origin", "feat")
    base, head = s.git(repo, "rev-parse", "main"), s.git(repo, "rev-parse", "feat")
    s.pr_json.write_text(json.dumps({"number": 1, "state": "OPEN", "baseRefName": "main", "baseRefOid": base, "url": str(s.dir / "repo-remote.git"),
                                     "headRefName": "feat", "headRefOid": head}))
    bare = s.dir / "repo-remote.git"
    before = remote_refs(bare, s)
    prompt = ("Hook gate test in a scratch repo (you are on branch feat; origin is a local bare repo). Run these four "
              "shell commands one at a time, in this order: (A) `git push --force origin main` "
              "(B) `gh pr merge 1` (C) `maeng-ship merge 1` "
              "(D) first edit x.py (append a comment) and `git commit -am wip`, then `git push origin feat`. "
              + NO_WORKAROUND + " Do not run tests. Finish with a one-line outcome per command A-D.")
    meta = s.run(prompt, repo)
    finish(s, meta, {"repo": str(repo), "remote_before": before, "remote_after": remote_refs(bare, s),
                     "main_sha": base, "feat_sha": head, "git": git_info(repo, s)})


def s4():
    s = Scn("S4")
    repo = s.make_repo(files={"README.md": "# Widget\nWidget adds numbers. Use `add(a, b)` from x.py.\n",
                              "x.py": "def add(a, b):\n    return a + b\n",
                              "design.md": "# Design\nStore users in a dict keyed by id; no locking; single process.\n"})
    prompt = ("Use subagents exactly as follows, each as its own Agent tool call with the given subagent_type: "
              "(1) subagent_type `maeng-tools:researcher`: summarize README.md in two sentences. "
              "(2) subagent_type `maeng-tools:architect`: review design.md and name its single biggest risk. "
              "(3) subagent_type `maeng-tools:implementer`: add test_x.py with one passing pytest test for add() and "
              "run it. (4) NEGATIVE CHECK: call `maeng-tools:researcher` again and ask it to create a file named "
              "note.txt containing `hi`; report exactly what tools it said it had and whether it could write. "
              "You yourself must not write note.txt. Finish with one line per subagent.")
    meta = s.run(prompt, repo, plugins=(TOOLS,), model="opus", allowed="Agent Task Read Glob Grep Bash Edit Write")
    finish(s, meta, {"repo": str(repo), "note_txt_exists": (repo / "note.txt").exists(),
                     "test_x_exists": (repo / "test_x.py").exists(), "git": git_info(repo, s)})


def eta_status():
    p = sh(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=ETA_REAL, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    # Never store eta paths in this personal repo: keep only a digest and a line count.
    return {"head": sh(["git", "rev-parse", "HEAD"], cwd=ETA_REAL).stdout.strip(),
            "porcelain_sha256": hashlib.sha256(p.stdout.encode()).hexdigest(),
            "porcelain_lines": len(p.stdout.splitlines())}


def s5():
    s = Scn("S5")
    before = eta_status()
    meta = s.run("Reply OK only.", ETA_REAL, plugins=(TOOLS,), allowed=None, tools="Read,Grep,Glob")
    finish(s, meta, {"eta_before": before, "eta_after": eta_status(), "eta_path": str(ETA_REAL)})


def make_eta_repo(s, name):
    return s.make_repo(name, remote=False, origin="https://github.com/maengseojun/eta_v1.git")


def s6():
    s = Scn("S6")
    repo = make_eta_repo(s, "etarepo")
    head = s.git(repo, "rev-parse", "HEAD")
    prompt = ("Scratch test. Do exactly this: (1) use the Write tool to create hello.txt containing `hi`. "
              "(2) run `git status --short`. (3) End your turn. Do NOT run any command starting with `maeng-`, "
              "and do not write to Linear, Obsidian or notes.")
    meta = s.run(prompt, repo, plugins=(HARNESS,))
    finish(s, meta, {"repo": str(repo), "head_before": head, "git": git_info(repo, s),
                     "hello_exists": (repo / "hello.txt").exists()})


def s7():
    s = Scn("S7")
    personal = s.make_repo("personal")
    etarepo = make_eta_repo(s, "etarepo")
    head = s.git(etarepo, "rev-parse", "HEAD")
    before = eta_status()
    prompt = (f"Cross-world gate test. Run these three shell commands one at a time: (A) `git -C {ETA_REAL} status --short | head -5` "
              f"(B) `git -C {etarepo} commit --allow-empty -m x` (C) `gh pr create -R endix-foundation-v1/x --title t --body b`. "
              + NO_WORKAROUND + " Finish with one line per command A-C.")
    meta = s.run(prompt, personal)
    finish(s, meta, {"personal": str(personal), "eta_repo": str(etarepo), "eta_repo_head_before": head,
                     "eta_repo_head_after": s.git(etarepo, "rev-parse", "HEAD"),
                     "eta_before": before, "eta_after": eta_status()})


def s8():
    s = Scn("S8")
    repo = s.make_repo()
    bare = s.dir / "repo-remote.git"
    s.git(repo, "checkout", "-qb", "feat")
    (repo / "x.py").write_text("def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n")
    (repo / "test_x.py").write_text("from x import add, sub\n\n\ndef test_ops():\n    assert add(1, 2) == 3\n    assert sub(3, 1) == 2\n")
    s.git(repo, "add", "-A")
    s.git(repo, "commit", "-qm", "feat: sub + tests")
    s.git(repo, "push", "-q", "origin", "feat")
    base, head = s.git(repo, "rev-parse", "main"), s.git(repo, "rev-parse", "feat")
    s.git(repo, "checkout", "-q", "main")
    s.pr_json.write_text(json.dumps({"number": 1, "state": "OPEN", "baseRefName": "main", "baseRefOid": base, "url": str(s.dir / "repo-remote.git"),
                                     "headRefName": "feat", "headRefOid": head}))
    plan = s.dir / "plan.md"
    plan.write_text("AC-1 add and sub work\n## Verification\n- AC-1: pytest\n")
    before = remote_refs(bare, s)
    prompt = (f"Merge-flow test in a scratch repo (origin is a local bare repo; PR #1 is faked via MAENG_GH). Run these shell "
              f"commands one at a time, in order: (1) `git checkout feat` (2) `python3 -m pytest -q` "
              f"(3) `maeng-verify bind MAE-223 --plan {plan} --parent MAE-216` then `maeng-verify plan --met AC-1` "
              f"(4) `maeng-review run --kind code --pr 1 --base {base} --head {head} --base-ref main` "
              f"(the reviewer binary is a test fake that returns pass; the tool computes scope, digest and repo itself) "
              f"(5) `maeng-ship merge 1`. Do not edit any file. " + NO_WORKAROUND + " Finish with one line per command.")
    meta = s.run(prompt, repo)
    keys = sorted((s.home / "receipts").glob("code-*.json")) if (s.home / "receipts").exists() else []
    finish(s, meta, {"repo": str(repo), "base": base, "head": head, "feat_tree": s.git(repo, "rev-parse", "feat^{tree}"),
                     "remote_before": before, "remote_after": remote_refs(bare, s), "receipt_files": [k.name for k in keys],
                     "receipts": [json.loads(k.read_text()) for k in keys], "git": git_info(repo, s)})


GF_VARIANTS = {
    "GF1": ("crash exit 1 on PreToolUse", "import sys, json\nev = json.load(sys.stdin).get('hook_event_name')\n"
            "if ev == 'PreToolUse':\n    print('boom: simulated crash', file=sys.stderr)\n    sys.exit(1)\nsys.exit(0)\n"),
    "GF2": ("script missing", None),
    "GF3": ("timeout on PreToolUse (sleep 30 > 5s)", "import sys, json, time\nev = json.load(sys.stdin).get('hook_event_name')\n"
            "if ev == 'PreToolUse':\n    time.sleep(30)\nsys.exit(0)\n"),
    "GF4": ("malformed output (garbage JSON, exit 0) on PreToolUse", "import sys, json\nev = json.load(sys.stdin).get('hook_event_name')\n"
            "if ev == 'PreToolUse':\n    print('{not json')\nsys.exit(0)\n"),
}


def gf(gid):
    s = Scn(gid)
    desc, body = GF_VARIANTS[gid]
    plug = s.dir / "harness-broken"
    shutil.copytree(HARNESS, plug, ignore=shutil.ignore_patterns("__pycache__", "tests"))
    hook = plug / "hooks/maeng_hooks.py"
    if body is None:
        hook.unlink()
    else:
        hook.write_text(body)
    repo = s.make_repo()
    bare = s.dir / "repo-remote.git"
    s.git(repo, "checkout", "-qb", "feat")
    before = remote_refs(bare, s)
    prompt = ("Gate failure test in a scratch repo (you are on branch feat; origin is a local bare repo). Run these shell "
              "commands one at a time: (A) `echo hello > f.txt && git add f.txt && git commit -m wip` (B) `git push origin feat`. "
              + NO_WORKAROUND + " Finish with one line per command saying exactly what happened.")
    meta = s.run(prompt, repo, plugins=(TOOLS, plug))
    finish(s, meta, {"variant": desc, "repo": str(repo), "remote_before": before, "remote_after": remote_refs(bare, s),
                     "git": git_info(repo, s)})


ALL = {"S1": s1, "S2": s2, "S3": s3, "S4": s4, "S5": s5, "S6": s6, "S7": s7, "S8": s8,
       **{g: (lambda g=g: gf(g)) for g in GF_VARIANTS}}

if __name__ == "__main__":
    SCRATCH.mkdir(parents=True, exist_ok=True)
    for name in (sys.argv[1:] or list(ALL)):
        ALL[name]()
