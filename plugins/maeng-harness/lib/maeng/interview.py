"""Comprehension gate state: the part map, design and merge passes, waivers, answer capture and seals.
State lives in home_dir()/interviews/<repo slug>/ (map.json, passes.json, ledger.jsonl, open/<session>.json,
seals/); every worktree of a repository shares the slug. The model flows are in bin/maeng-interview."""
import json
import os
import re
import subprocess
import sys

from . import gates, ghcmd, guard, quiz, receipts, state
from . import schema as jsonschema
from . import tree as treelib
from .common import git, git_out, home_dir, locked, now_iso, read_json, sha256, write_json
from .shellparse import SHELLS, ParseError, program, split_segments

WRAPPERS = ("<system-reminder>", "<task-notification>", "<cross-session-message", "Another Claude session sent a message:",
            "<side-sessions-event>", "<ci-monitor-event>")
MODEL = "claude-opus-5-5"  # D-4: the interviewer is Opus in both worlds
OVERALL, LIMIT = "overall", 150  # LIMIT: changed lines at which a PR needs a merge pass (what harness-run calls one task)
WAIVE_PR = re.compile(r"\s*면제\s+#(\d+)\s+(\S.*)", re.S)
WAIVE_PART = re.compile(r"\s*면제\s+([^\s#]+)\s+(\S.*)", re.S)


class Refused(Exception):
    """A request the gate refuses; the text is for the agent."""


def warn(msg):
    print("maeng-harness: " + msg, file=sys.stderr)


# ---- state files ---------------------------------------------------------

def slug(repo):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", repo).strip("_") + "-" + sha256(repo)[:8]


def repo_key(cwd):
    """The state directory name of cwd's repository, or None without an origin remote (shortcut: such a repository
    has no gate; upgrade when a map is wanted for a repository with no remote)."""
    repo = guard.normalize_repo(git_out(cwd, "config", "--get", "remote.origin.url") or "")
    return slug(repo) if repo else None


def _file(key, name):
    return home_dir() / "interviews" / key / name


def load_map(key):
    """The part map, None without one; ValueError when the file is unreadable."""
    return read_json(_file(key, "map.json"))


def save_map(key, m):
    write_json(_file(key, "map.json"), m)  # callers that read first hold locked(_file(key, "map.json"))


def parts_of(m, rel):
    """Names of the parts whose path globs match the repo-relative path `rel`."""
    return [name for name, p in ((m or {}).get("parts") or {}).items()
            if any(treelib.glob_regex(g).match(rel) for g in p.get("paths") or [])]


def _load_passes(key):
    p = read_json(_file(key, "passes.json")) or {}
    p.setdefault("design", {})
    p.setdefault("merge", [])
    w = p.setdefault("waivers", {})
    w.setdefault("design", {})
    w.setdefault("pr", {})
    return p


def _update_passes(key, fn):
    path = _file(key, "passes.json")
    with locked(path):
        p = _load_passes(key)
        fn(p)
        write_json(path, p)


def passed(key, part, stage, digest=None):
    """design: `part` has a pass or a waiver. merge: a pass exists for the patch id `digest`, or PR `part` is waived."""
    p = _load_passes(key)
    if stage == "design":
        return part in p["design"] or part in p["waivers"]["design"]
    return str(part) in p["waivers"]["pr"] or (digest is not None and any(r.get("patch") == digest for r in p["merge"]))


def record_pass(key, stage, part=None, pr=None, patch=None, head=None):
    def put(p):
        if stage == "design":
            p["design"][part] = {"at": now_iso()}
        else:
            p["merge"].append({"pr": pr, "patch": patch, "head": head, "at": now_iso()})
    _update_passes(key, put)


def record_waiver(key, kind, ident, reason):
    """kind: `design` (ident is a part) or `pr`."""
    _update_passes(key, lambda p: p["waivers"][kind].__setitem__(str(ident), {"reason": reason, "at": now_iso()}))


def clear_design(key, part):
    """A-5: reopen a part. -> True when a pass or a waiver was there."""
    had = []
    def drop(p):
        had.extend([p["design"].pop(part, None), p["waivers"]["design"].pop(part, None)])
    _update_passes(key, drop)
    return any(had)


def ledger(key, **fields):
    """Counts and hashes only, never question, rubric, answer or reason text (A-7)."""
    path = _file(key, "ledger.jsonl")
    with locked(path), open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": now_iso(), **fields}, ensure_ascii=False, sort_keys=True) + "\n")


def _open_file(key, sid):
    return _file(key, f"open/{state.safe_id(sid)}.json")


def load_open(key, sid):
    return read_json(_open_file(key, sid))


def save_open(key, sid, rec):
    path = _open_file(key, sid)
    with locked(path):
        write_json(path, rec)


def close_open(key, sid):
    _open_file(key, sid).unlink(missing_ok=True)


# ---- who is asking -------------------------------------------------------

def _ps(pid):
    """-> (parent pid, command line) of a process; ("", "") when ps fails."""
    try:
        out = subprocess.run(["ps", "-o", "ppid=,command=", "-p", str(pid)], capture_output=True, text=True,
                             timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return "", ""
    ppid, _, cmd = out.strip().partition(" ")
    return ppid, cmd.strip()


def headless():
    """A `claude -p` run (a dots task or a child session): MAENG_TASK_ID is set, or the claude process above this
    one has `-p` or `--print` in its argv. CLAUDE_CODE_ENTRYPOINT cannot tell (a child inherits it), A-3.
    shortcut: only shells are skipped on the way up, so a wrapper such as `node claude -p` counts as the argv;
    upgrade if headless runs are launched through one."""
    if os.environ.get("MAENG_TASK_ID"):
        return True
    pid = str(os.getppid())
    for _ in range(4):
        ppid, cmd = _ps(pid)
        argv = cmd.split()
        if argv and os.path.basename(argv[0]) in SHELLS and ppid.isdigit():  # the Bash tool's shell: its parent is claude
            pid = ppid
            continue
        return bool({"-p", "--print"} & set(argv))
    return False


# ---- capture -------------------------------------------------------------

def capture(key, sid, prompt):
    """The user's message as what the open record of this session awaits (A-4). -> a note for the agent, or None
    when nothing is awaited or the message is not an answer."""
    path = _open_file(key, sid)
    if not path.exists():  # no lock file, no directory: nothing is touched
        return None
    text = prompt.strip()
    with locked(path):
        rec = read_json(path)
        if not rec:
            return None
        wait = rec.get("awaiting")
        if text == "중단":
            path.unlink(missing_ok=True)
            return "maeng: the user closed the open interview (중단); no penalty. Do not restart it unless they ask."
        if wait == "retry" and text.startswith("이의") and text[2:].strip():
            rec["appeal"] = text[2:].strip()
            note = "maeng: the user's appeal was recorded. Run `maeng-interview appeal`."
        elif wait in ("answer", "choice") and not receipts.APPROVE.match(prompt):
            rec["answer"] = prompt if rec.get("answer") is None else rec["answer"] + "\n\n" + prompt
            note = ("maeng: the user's message was recorded as their answer. Run `maeng-interview next`." if wait == "answer"
                    else "maeng: the user's choice was recorded. Run `maeng-interview reveal <digest>`.")
        else:
            return None
        write_json(path, rec)
    return note


def _waiver(prompt, m):
    """-> (kind, ident, reason) of a `면제` message, else None. A part waiver needs a declared part."""
    hit = WAIVE_PR.fullmatch(prompt)
    if hit:
        return "pr", hit.group(1), hit.group(2).strip()
    hit = WAIVE_PART.fullmatch(prompt)
    if hit and hit.group(1) in ((m or {}).get("parts") or {}):
        return "design", hit.group(1), hit.group(2).strip()
    return None


def _waive(key, sid, rec, waiver):
    kind, ident, reason = waiver
    record_waiver(key, kind, ident, reason)
    ledger(key, stage="design" if kind == "design" else "merge", **{"part" if kind == "design" else "pr": ident},
           attempts=(rec or {}).get("attempts", 0), first_try=False, appeals=(rec or {}).get("appeals", 0),
           appeal_upheld=(rec or {}).get("appeal_upheld", 0), waived=True)
    if rec and str(rec.get("part" if kind == "design" else "pr")) == ident:
        close_open(key, sid)  # the waived interview or quiz is over
    return f"maeng: the user waived {'part ' if kind == 'design' else 'PR #'}{ident}; the gate counts it as passed."


def _naming_note(key, sid, prompt, m):
    """AC-2: the message names another part while this session's current part has no design pass."""
    cur = (m.get("current") or {}).get(sid)
    if not cur or passed(key, cur, "design"):
        return None
    for name, p in (m.get("parts") or {}).items():
        if name not in (cur, OVERALL) and any(re.search(rf"(?<!\w){re.escape(w)}(?!\w)", prompt, re.I)
                                              for w in [name, *(p.get("aliases") or [])]):
            return (f"maeng: the message names part `{name}`, but the current part `{cur}` has no design pass. "
                    f"`maeng-interview switch {name}` refuses until `{cur}` passes (or the user waives it with `면제 {cur} <reason>`).")
    return None


def on_prompt(payload):
    """UserPromptSubmit: the user's message as an answer, an appeal, a stop or a waiver. -> a note for the agent, or
    None. Touches nothing when this session has no open record, the repository has no map and the message is not a
    waiver (the eta side-effect test)."""
    prompt, sid = payload.get("prompt"), payload.get("session_id", "")
    if not isinstance(prompt, str) or prompt.lstrip().startswith(WRAPPERS):  # a wrapped message is never the user's
        return None
    key = repo_key(payload.get("cwd") or os.getcwd())
    if not key:
        return None
    rec, m = load_open(key, sid), load_map(key)
    waiver = _waiver(prompt, m)
    if not (rec or m or waiver):
        return None
    if waiver:
        if headless():  # A-11: a waiver the user typed; a `claude -p` child could write one for itself
            return "maeng: a waiver counts only when the user types it in an interactive session; not recorded."
        return _waive(key, sid, rec, waiver)
    return capture(key, sid, prompt) or (_naming_note(key, sid, prompt, m) if m else None)


# ---- seal ----------------------------------------------------------------

def seal(key, sid, data):
    """Store the recommendation (bytes) and wait for the user's choice (D-8). -> the first 12 characters of its sha256."""
    digest = sha256(data)
    cur = load_open(key, sid)
    if cur and cur.get("kind") != "seal":
        raise Refused("an interview or quiz is open in this session; finish it or have the user send 중단 first")
    path = _file(key, f"seals/{digest}.txt")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)  # not atomic: reveal checks the digest of what it reads
    save_open(key, sid, {"kind": "seal", "awaiting": "choice", "answer": None, "digest": digest, "opened_at": now_iso()})
    return digest[:12]


def reveal(key, sid, digest):
    """The sealed bytes, once the user's own message arrived after the seal (T6)."""
    rec = load_open(key, sid)
    if not rec or rec.get("kind") != "seal" or len(digest) < 12 or not rec["digest"].startswith(digest):
        raise Refused("nothing is sealed under that digest in this session")
    if rec.get("answer") is None:
        raise Refused("the user has not answered since the seal; reveal only after their own message")
    data = _file(key, f"seals/{rec['digest']}.txt").read_bytes()
    if sha256(data) != rec["digest"]:
        raise Refused("the sealed text changed on disk; do not use it")
    ledger(key, stage="seal", digest=rec["digest"][:12], revealed=True)
    close_open(key, sid)
    return data


# ---- PreToolUse (K1, every world) ----------------------------------------

EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
FAST = ("gh", "interviews", "MAENG_CLAUDE")  # a Bash command with none of these is not ours
MERGE_MCP = re.compile(r"mcp__.+__merge_pull_request")
# shortcut: a text match on the state path, not a shell parse; a `cd` into the directory and a relative name slips
# through. Upgrade if agents do that.
STATE_PATH = re.compile(r"maeng-harness/interviews|MAENG_HOME\}?/interviews")
PR_FIELDS = "number,additions,deletions,files,baseRefOid,headRefOid"
MERGES = {"--auto", "--admin", "--merge", "-m", "--rebase", "-r", "--squash", "-s"}
HIDDEN = ("maeng: the interview state ({what}) belongs to the CLI and the user; the agent does not read or write the "
          "questions, rubrics or answers (comprehension-gate skill). Use `maeng-interview`.")
NEED = ("maeng: PR #{pr} {why}, and has no merge-quiz pass for patch {patch}. In a clean checkout of the PR head run "
        "`maeng-interview start --stage merge --pr {pr}`; the user answers in their own messages. The user can waive "
        "it with `면제 #{pr} <reason>`; `승인 #{pr}` does not replace it.")


def _read(fn, *args):
    """fn(*args); Refused when the gate's state is unreadable, which denies the matched call."""
    try:
        return fn(*args)
    except (OSError, ValueError) as exc:
        raise Refused(f"maeng: the comprehension gate's state is unreadable ({type(exc).__name__}: {exc}); move or fix "
                      f"it with the user. The call is denied until then.")


def gate(payload, world):
    """PreToolUse: -> a deny reason, or None. An exception while matching warns and allows (T7); once a call has
    matched, an unreadable state or PR denies."""
    tool, tin, cwd = payload.get("tool_name"), payload.get("tool_input"), payload.get("cwd") or os.getcwd()
    try:
        if tool == "Bash":
            return _bash_gate(tin["command"], world, cwd) if any(w in tin["command"] for w in FAST) else None
        if tool in EDIT_TOOLS:
            return _edit_gate(tin, cwd)
        if world != guard.PERSONAL and MERGE_MCP.fullmatch(tool):
            return _mcp_merge_gate(tin, cwd)
    except Refused as why:
        return str(why)
    except Exception as exc:
        warn(f"interview gate error ({type(exc).__name__}: {exc}); the call is allowed")
    return None


def _names_state(text):
    return str(home_dir() / "interviews") in text or STATE_PATH.search(text)


def _bash_gate(command, world, cwd):
    if gates.CLAUDE_SET.search(command):  # before the CLI's exemption: on its line this picks who grades the user
        raise Refused(HIDDEN.format(what="MAENG_CLAUDE, which names the interview model"))
    try:  # `maeng-interview ...` is the sanctioned route: its arguments are not read, its redirects are
        texts = [" ".join(seg.redirects if program(seg.tokens)[0] == "maeng-interview" else seg.tokens + seg.redirects)
                 for seg in split_segments(command.rstrip())]
    except ParseError:
        texts = [command]
    if any(_names_state(t) for t in texts):
        raise Refused(HIDDEN.format(what="its directory"))
    if world == guard.PERSONAL:  # `gh pr merge` is G1's there, and maeng-ship holds the merge gate
        return None
    for toks in _merge_calls(command):
        info = ghcmd.parse_gh(toks)
        why = _pr_gate(cwd, info["pos"][2] if len(info["pos"]) > 2 else None, info["repo"])
        if why:
            return why
    return None


def _only_disables_auto(toks):
    return "--disable-auto" in toks and not MERGES & {t.partition("=")[0] for t in toks}


def _merge_calls(command):
    """Token lists of the `gh pr merge` calls in the command (also in `sh -c` and `eval`), with or without --auto."""
    try:
        return [toks for prog, toks in gates.simple_commands(command)
                if prog == "gh" and not {"--help", "-h"} & set(toks) and not _only_disables_auto(toks) and ghcmd.parse_gh(toks)["pos"][:2] == ["pr", "merge"]]
    except ParseError:
        if re.search(r"\bgh\b.*\bmerge\b", command, re.S):
            raise Refused("maeng: cannot parse this command and it mentions `gh ... merge`; run the merge as a simpler command.")
        return []


def _mcp_merge_gate(tin, cwd):
    number = tin.get("pullNumber") or tin.get("pull_number")
    if not number:
        raise Refused("maeng: cannot tell which PR this merge call is for, so the comprehension gate denies it.")
    owner, name = tin.get("owner"), tin.get("repo")
    return _pr_gate(cwd, str(number), f"{owner}/{name}" if owner and name else None)


def _edit_gate(tin, cwd):
    path = tin.get("file_path") or tin.get("notebook_path") or tin.get("path")
    if not isinstance(path, str) or not path:
        return None
    target = os.path.realpath(gates._abs(path, cwd))
    base = os.path.realpath(home_dir() / "interviews")
    if target == base or target.startswith(base + os.sep):
        raise Refused(HIDDEN.format(what="a file in it"))
    where = guard._nearest_dir(target)
    top, key = treelib.toplevel(where), repo_key(where)
    if not (top and key):
        return None
    m = load_map(key)  # unreadable: still matching, so T7 allows and warns; no edit in the repo may hinge on this file
    rel = os.path.relpath(target, os.path.realpath(top))
    parts = parts_of(m, rel)
    if not parts or headless():  # A-3: a headless run skips the write gate, not the merge gate
        return None
    missing = [p for p in (OVERALL, *parts) if not _read(passed, key, p, "design")]
    if missing:
        raise Refused(f"maeng: `{rel}` belongs to part {', '.join(parts)}, and these have no design interview pass yet: "
                      f"{', '.join(missing)}. Ask the user for the interview "
                      f"(`maeng-interview start --stage design --part <part> --material <file>`, comprehension-gate "
                      f"skill); they can waive one with `면제 <part> <reason>`.")
    return None


def _read_pr(cwd, sel, repo):
    cmd = [os.environ.get("MAENG_GH", "gh"), "pr", "view", *([sel] if sel else []), *(["-R", repo] if repo else []),
           "--json", PR_FIELDS]
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=8)
        pr = json.loads(proc.stdout) if proc.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pr = None
    if not (isinstance(pr, dict) and all(isinstance(pr.get(k), int) for k in ("number", "additions", "deletions"))
            and isinstance(pr.get("files"), list) and all(isinstance(pr.get(k), str) for k in ("baseRefOid", "headRefOid"))):
        raise Refused("maeng: could not read the PR with gh within 8 seconds, so the comprehension gate cannot tell its "
                      "size; the merge is denied. Retry.")
    return pr


def _pr_gate(cwd, sel, repo):
    """The merge gate of a PR merged through gh or an MCP tool (not personal; there maeng-ship holds it)."""
    key = slug(guard.normalize_repo(repo)) if repo else repo_key(cwd)  # shortcut: a PR URL for another repo is keyed by cwd
    if not key:
        return None
    pr = _read_pr(cwd, sel, repo)
    return _merge_refusal(key, pr["number"], pr["additions"] + pr["deletions"], [f.get("path", "") for f in pr["files"]],
                          lambda: quiz.patch_id(cwd, pr["baseRefOid"], pr["headRefOid"]))


def _merge_refusal(key, pr, lines, paths, patch_of):
    """A-1: why the PR needs a merge pass it does not have, else None."""
    m = _read(load_map, key)
    hits = sorted({n for p in paths for n in parts_of(m, p)})
    if lines <= LIMIT and not hits:
        return None
    if _read(passed, key, pr, "merge"):  # a waiver for this PR
        return None
    patch = patch_of()
    if patch and _read(passed, key, pr, "merge", patch):
        return None
    why = f"changes {lines} lines (limit {LIMIT})" if lines > LIMIT else "touches " + ", ".join(hits)
    return NEED.format(pr=pr, why=why + (f" and touches {', '.join(hits)}" if hits and lines > LIMIT else ""),
                       patch=patch[:12] if patch else "unknown (fetch the PR head)")


def require_merge(cwd, pr, base, head):
    """maeng-ship (K3): why this PR may not merge without a merge pass, else None."""
    key = repo_key(cwd)  # the CLI's key, so no origin means no gate here too (A-15)
    if not key:
        return None
    try:
        rc, out, _ = git(cwd, "diff", "--numstat", "-z", "--no-renames", f"{base}...{head}")
        if rc != 0:
            raise Refused("maeng: cannot read the PR diff to size it, so the comprehension gate denies the merge.")
        rows = [r.split("\t", 2) for r in out.split("\0") if r]
        lines = sum(int(a) + int(d) for a, d, _ in rows if a.isdigit() and d.isdigit())  # a binary file counts 0
        return _merge_refusal(key, pr, lines, [p for *_, p in rows], lambda: quiz.patch_id(cwd, base, head))
    except Refused as why:
        return str(why)


# ---- the interview model -------------------------------------------------

def run_model(prompt, schema, cwd, tools="Read,Grep,Glob"):
    """One isolated `claude -p` Opus call (no settings, hooks or MCP) -> its schema-valid structured output.
    MAENG_CLAUDE names the binary (tests use a fake). Raises Refused; nothing is stored by the caller before it returns."""
    cmd = [os.environ.get("MAENG_CLAUDE") or "claude", "-p", "--setting-sources", "", "--strict-mcp-config", "--tools", tools,
           "--model", MODEL, "--effort", "high", "--output-format", "json", "--json-schema", json.dumps(schema)]
    try:
        proc = subprocess.run(cmd, cwd=cwd, input=prompt, capture_output=True, text=True, timeout=900)
        env = json.loads(proc.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise Refused(f"the interview model call failed ({type(exc).__name__}: {exc})")
    if not isinstance(env, dict) or proc.returncode != 0 or env.get("is_error"):
        raise Refused("the interview model call failed: " + str(env.get("result") if isinstance(env, dict) else proc.stderr)[-500:])
    usage = {k: v for k, v in (env.get("modelUsage") or {}).items() if isinstance(v, dict)}
    if not usage or not max(usage, key=lambda k: usage[k].get("outputTokens") or 0).startswith(MODEL):
        raise Refused(f"the interview model call ran on {sorted(usage)}, not {MODEL}; it is not used")
    result = env.get("structured_output")
    errors = jsonschema.validate(result, schema)
    if errors:
        raise Refused("the interview model's output violates its schema: " + "; ".join(errors))
    return result
