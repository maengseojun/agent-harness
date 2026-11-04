"""Hook event handlers. Each returns the JSON object to print (or None)."""
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

from . import evidence, gates, guard, interview, receipts, state, status, stub
from . import tree as treelib
from .common import git_out, home_dir, now_iso, read_json, sha256, vault_dir
from .shellparse import ParseError, program, split_segments

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
EDIT_TOOLS = ("Edit", "Write", "NotebookEdit", "MultiEdit")
UUID = re.compile(r"[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}")
REJECTED = re.compile(r"stale info|non-fast-forward|\[rejected\]|\[remote rejected\]|rejected", re.I)
COMMIT_SUBS = {"commit", "merge", "rebase", "am", "cherry-pick", "revert", "pull"}
# Linear servers whose writes count as a personal record (`linear-maeng` is the user's own workspace server)
PERSONAL_LINEAR = ("mcp__claude_ai_Linear__", "mcp__linear__", "mcp__linear-maeng__")
ARCHIVE_AFTER_DAYS = 14


def warn(msg):
    print("maeng-harness: " + msg, file=sys.stderr)


def deny_out(reason):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def context_out(event, text):
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}


def world_of(payload, st=None):
    """Session world: the world of the session's project root (guard.session_root), not of the hook's cwd."""
    return guard.classify(guard.session_root(payload.get("cwd") or os.getcwd(), (st or {}).get("cwd")))


# ---- SessionStart --------------------------------------------------------

def plugin_version():
    try:
        return read_json(PLUGIN_ROOT / ".claude-plugin/plugin.json")["version"]
    except (OSError, ValueError, KeyError):
        return "?"


def _scalar(val):
    """A one-line YAML scalar: the text inside quotes, else the text before a ` #` comment."""
    val = val.strip()
    if val[:1] in ("'", '"'):
        end = val.find(val[0], 1)
        rest = val[end + 1:].strip() if end > 0 else "?"
        return val[1:end] if not rest or rest.startswith("#") else val  # junk after the quote stays malformed
    return val.split(" #", 1)[0].strip()


def _archive_candidates():
    """Project hubs whose frontmatter `closed` date is ARCHIVE_AFTER_DAYS or more days old and not yet archived."""
    found, today = [], date.today()
    for hub in sorted((vault_dir() / "hubs/projects").glob("*.md")):
        try:
            with open(hub, encoding="utf-8") as f:
                head = f.read(4096).splitlines()  # shortcut: a frontmatter longer than 4 KB is skipped; raise it if hubs grow
            if head[0].strip() != "---":
                continue
            fm = {}
            for line in head[1:]:
                if line.strip() == "---":
                    break
                key, _, val = line.partition(":")
                fm[key] = _scalar(val)
            else:
                continue  # no closing ---
            closed = date.fromisoformat(fm.get("closed", ""))
        except (OSError, ValueError, IndexError):
            continue
        if (today - closed).days >= ARCHIVE_AFTER_DAYS and fm.get("status") != "archived":
            found.append(f"{hub.stem} ({closed})")
    return found


def build_context(cwd):
    lines = [f"maeng-harness {plugin_version()} (personal world). Gate: G1 (no push to the default branch, merge only via maeng-ship).",
             "Ranks and approval lines: harness-run references/org-chart.md."]
    sugg = (read_json(home_dir() / "last-bindings.json", {}) or {}).get(str(Path(cwd).resolve()))
    if sugg:
        lines.append(f"Suggested binding (not active): maeng-verify bind {sugg.get('issue')} --plan {sugg.get('plan_doc', '<doc>')}")
    top = treelib.toplevel(cwd)
    if top:
        pol = treelib.load_policy(top)
        if pol["required"]:
            lines.append("Policy required checks: " + ", ".join(pol["required"]))
    sessions = vault_dir() / "wiki/sessions"
    if sessions.is_dir():
        newest = sorted(sessions.glob("SESSION-*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:1]
        if newest:
            lines.append("Latest session note: wiki/sessions/" + newest[0].name)
    # Cheap check only (full discovery walks every eta checkout; the hook has a 5s budget).
    if guard.eta_root().is_dir() and guard.isolation_missing(guard.eta_root()):
        lines.append("eta checkouts lack isolation: run `maeng-eta-isolate --apply`.")
    old = _archive_candidates()
    if old:
        lines.append(f"Archive candidates (closed {ARCHIVE_AFTER_DAYS}+ days, ask the CEO before maeng-archive): " + ", ".join(old))
    text = "\n".join(lines)
    return text.encode()[:2000].decode(errors="ignore")


def on_session_start(payload):
    cwd, sid = payload.get("cwd", os.getcwd()), payload.get("session_id", "")
    state.clear_quarantine(sid)  # a (re)started session begins with fresh state
    root = guard.session_root(cwd)
    world = guard.classify(root)
    if world == guard.ETA:
        try:
            top = guard.project_root(root)
            missing = top is None or guard.isolation_missing(top)
        except Exception:
            missing = True
        if not missing:
            return None
        return context_out("SessionStart", "this eta checkout's local settings lack the eta enables or the "
                           "ETA_ONLY_HOOKS code-only setting. Run "
                           "`maeng-eta-isolate --apply` and restart this session.")
    if world == guard.UNKNOWN:
        return None
    def init(st):
        st["cwd"], st["world"] = cwd, world
        st["started_at"] = st.get("started_at") or now_iso()
    state.update(sid, init, cwd)
    env_file = os.environ.get("CLAUDE_ENV_FILE")
    if env_file:
        with open(env_file, "a") as f:
            f.write(f"export MAENG_SESSION_ID={sid}\n")
    return context_out("SessionStart", build_context(cwd))


# ---- UserPromptSubmit ----------------------------------------------------

def add_context(out, text):
    """`out` (a UserPromptSubmit result or None) with `text` appended to its additionalContext."""
    prev = (out or {}).get("hookSpecificOutput", {}).get("additionalContext")
    return context_out("UserPromptSubmit", "\n".join(filter(None, [prev, text])))


def interview_note(payload):
    try:
        return interview.on_prompt(payload)  # K2: the user's answer, appeal, stop or waiver
    except Exception as exc:  # a tracker: never blocks the prompt
        warn(f"interview prompt check failed: {type(exc).__name__}: {exc}")
        return None


def on_prompt(payload):
    sid, cwd = payload.get("session_id", ""), payload.get("cwd", os.getcwd())
    st = state.load(sid, cwd)
    iv = interview_note(payload)
    if world_of(payload, st) != guard.PERSONAL:
        return context_out("UserPromptSubmit", iv) if iv else None
    out = record_approval(payload.get("prompt") or "", cwd)
    tree, _ = treelib.tree_id(cwd)
    new_task = not st.get("task_id")
    def mark(s):
        s["turn"] += 1
        s["cwd"] = s.get("cwd") or cwd
        s["task_id"] = s.get("task_id") or status.task_id_for(sid, payload.get("prompt"))
        if tree:
            s["baseline_tree"] = s["baseline_tree"] or tree
            s["last_tree"] = tree
        return s
    st = state.update(sid, mark, cwd)
    note = task_running(st, new_task)
    return add_context(out, "\n".join(filter(None, [note, iv]))) if note or iv else out


def task_running(st, new_task):
    """Mark the task running (the intake ack dots reads); on a session's first prompt, name a live other owner."""
    tid = st["task_id"]
    try:
        other = status.owner_conflict(tid, st["session_id"]) if new_task else None
        status.write(tid, st["session_id"], state="running", cwd=st.get("cwd"),
                     task_name=(st.get("binding") or {}).get("issue"), blocker=None, next_action=None)
    except (OSError, ValueError) as exc:
        warn(f"status file failed: {exc}")
        return None
    if other:
        return (f"maeng: task {tid} is already running in session {other}. Continue here only if the user meant to "
                f"hand it over; otherwise stop and say so.")
    return None


def record_approval(prompt, cwd):
    """`승인 #N` / `approve #N` from the user: approve PR N at its current head for maeng-ship."""
    m = receipts.APPROVE.match(prompt)
    if not m:
        return None
    pr = m.group(1)
    try:
        proc = subprocess.run([os.environ.get("MAENG_GH", "gh"), "pr", "view", pr, "--json", "headRefOid,url"],
                              cwd=cwd, capture_output=True, text=True, timeout=8)
        info = json.loads(proc.stdout) if proc.returncode == 0 else {}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        info = {}
    head = info.get("headRefOid")
    repo = guard.normalize_repo(re.sub(r"/pull/\d+/?$", "", str(info.get("url") or "")))
    if not head or not repo:
        return context_out("UserPromptSubmit", f"maeng: could not read PR #{pr} with gh, so the approval was NOT "
                                               f"recorded; tell the user.")
    receipts.store_approval(repo, pr, head, prompt)
    return context_out("UserPromptSubmit", f"maeng: the user approved PR #{pr} at head {head[:10]}. "
                                           f"`maeng-ship merge {pr}` accepts this approval in place of a review "
                                           f"receipt, for this head only.")


# ---- PreToolUse ----------------------------------------------------------

def on_pre(payload):
    sid, cwd = payload.get("session_id", ""), payload.get("cwd", os.getcwd())
    if state.is_quarantined(sid):  # regardless of cwd: the session's world is no longer known
        return deny_out("maeng: session state was quarantined; restart the session")
    st = state.load(sid, cwd)
    world = world_of(payload, st)
    why = interview.gate(payload, world)  # K1: before the eta return (D-5)
    if why:
        return deny_out(why)
    if world == guard.ETA:
        return None
    tool, tin, tuid = payload.get("tool_name"), payload.get("tool_input"), payload.get("tool_use_id", "")
    if not isinstance(tool, str) or not tool.strip():
        return deny_out("maeng gate: tool_name is missing or not a string; denied because the gate cannot tell "
                        "what the call does.")
    if not isinstance(tin, dict):  # the gate cannot inspect what it is asked to allow
        return deny_out("maeng gate: tool_input is not an object; denied because the gate cannot inspect the call.")
    try:
        dec = gates.evaluate(tool, tin, gates.Ctx(cwd, st, world), tuid)
    except Exception as exc:  # gate cannot decide: fail closed
        return deny_out(f"maeng gate error ({type(exc).__name__}: {exc}); denied because the gate cannot decide.")
    if not dec.allow:
        return deny_out(dec.reason)
    if world != guard.PERSONAL and not dec.effects:  # never skip the reservation of an allowed G2/G1 effect
        return None
    try:
        track_pre(sid, cwd, tool, tin, tuid, dec.effects)
    except Exception as exc:  # authorization effects could not be persisted: fail closed
        return deny_out(f"maeng: could not reserve the receipt/journal entry for this call "
                        f"({type(exc).__name__}: {exc}); denied because the mutation would be unjournaled.")
    return None


def track_pre(sid, cwd, tool, tin, tuid, effects):
    reserve = [(eff[1], eff[2]) for eff in effects if eff[0] == "receipt_pending"]
    receipt_keys = [k for k, _ in reserve]
    if reserve:
        receipts.begin_many(reserve)  # atomic under the receipt locks: a concurrent second call raises
    try:
        for eff in effects:
            if eff[0] == "journal_pending":
                receipts.journal_pending(eff[1])
    except Exception:
        for k in receipt_keys:
            try:
                receipts.reject(k, "reservation-rolled-back")
            except Exception:
                pass
        raise
    rec = None
    if tool == "Bash" and not tin.get("run_in_background"):
        rec = evidence.recognize(str(tin.get("command", "")))
    tree_start = common = run_cwd = None
    rel = ""
    if rec:
        run_cwd = gates._abs(rec["cd"], cwd) if rec["cd"] else cwd
        tree_start, _ = treelib.tree_id(run_cwd)
        common = treelib.common_dir(run_cwd)
        rel = evidence.rel_dir(run_cwd, treelib.toplevel(run_cwd))
    key = tuid or sha256(str(tin.get("command", "")))[:16]

    def mark(st):
        if rec:
            evidence.pre_runner(st, key, tin.get("command", ""), rec, tree_start, common, rel)
            st["pending"][key]["cwd"] = run_cwd
        if receipt_keys:
            st["pending"].setdefault(key, {})["receipt_keys"] = receipt_keys
    if rec or receipt_keys:
        state.update(sid, mark, cwd)


# ---- PostToolUse / PostToolUseFailure ------------------------------------

def _flatten(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from _flatten(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _flatten(v)
    elif obj is not None:
        yield str(obj)


def is_record_write(tool, tin, tresp, issue):
    """Does this successful tool call write a Linear/Obsidian record (for the bound issue)?"""
    name = tool.split("__")[-1]
    linear = tool.startswith(PERSONAL_LINEAR) and name.startswith(("save_", "create_", "update_"))
    obsidian = tool.startswith("mcp__obsidian_vault__") and name in ("write_note", "patch_note", "update_frontmatter")
    vault_file = False
    if tool in EDIT_TOOLS:
        p = tin.get("file_path") or tin.get("notebook_path") or ""
        try:
            vault_file = bool(p) and Path(p).resolve().is_relative_to(vault_dir().resolve())
        except OSError:
            vault_file = False
    if not (linear or obsidian or vault_file):
        return False
    if not issue:
        return True
    pat = re.compile(r"\b" + re.escape(issue) + r"\b", re.I)
    if linear:
        return any(pat.search(s) for s in _flatten([tin, tresp]))
    strings = list(_flatten(tin))
    fm = re.compile(r"(?mi)^linear:\s*.*\b" + re.escape(issue) + r"\b")
    if any(fm.search(s) for s in strings):
        return True
    pairs = tin.get("frontmatter") if isinstance(tin.get("frontmatter"), dict) else tin
    if isinstance(pairs, dict) and "linear" in pairs and pat.search(" ".join(_flatten(pairs["linear"]))):
        return True
    return any(pat.search(str(tin.get(k, ""))) for k in ("path", "file_path", "note_path", "name"))


def formatter_cmd(top, path):
    pol = treelib.load_policy(top)
    if pol.get("formatter"):
        return [a.replace("{file}", path) for a in pol["formatter"]]
    top_p = Path(top)
    has_ruff = (top_p / "ruff.toml").exists() or (top_p / ".ruff.toml").exists() or (
        (top_p / "pyproject.toml").exists() and "[tool.ruff" in (top_p / "pyproject.toml").read_text(errors="ignore"))
    if has_ruff and path.endswith(".py") and shutil.which("ruff"):
        return ["ruff", "format", path]
    return None


def run_formatter(cwd, tin):
    path = tin.get("file_path")
    top = treelib.toplevel(Path(path).parent if path and Path(path).parent.exists() else cwd) if path else None
    if not (path and top):
        return
    cmd = formatter_cmd(top, path)
    if cmd:
        subprocess.run(cmd, cwd=top, capture_output=True, timeout=8)


def bash_may_change(command):
    try:
        segs = split_segments(command)
    except ParseError:
        return True
    for seg in segs:
        prog, toks = program(seg.tokens)
        if prog == "git":
            sub = gates._parse_git_globals(toks)[0]
            if sub not in gates.READONLY_GIT:
                return True
        elif prog not in gates.READONLY_PROGS or seg.redirects:
            return True
    return False


def has_commit(command):
    try:
        for seg in split_segments(command):
            prog, toks = program(seg.tokens)
            if prog == "git" and gates._parse_git_globals(toks)[0] in COMMIT_SUBS:
                return True
    except ParseError:
        pass
    return False


def response_failed(tresp):
    """True when a PostToolUse tool_response says the command did not succeed (interrupted, error, non-zero exit)."""
    if not isinstance(tresp, dict):
        return False
    if tresp.get("interrupted") is True or tresp.get("is_error") is True or tresp.get("isError") is True:
        return True
    for key in ("returnCode", "return_code", "returncode", "exit_code", "exitCode", "exit_status", "code"):
        v = tresp.get(key)
        if isinstance(v, str) and re.fullmatch(r"-?\d+", v.strip()):
            v = int(v)
        if isinstance(v, int) and not isinstance(v, bool) and v != 0:
            return True
    return False


def on_post(payload, failed=False):
    sid, cwd = payload.get("session_id", ""), payload.get("cwd", os.getcwd())
    st0 = state.load(sid, cwd)
    if world_of(payload, st0) != guard.PERSONAL:
        return None
    tool, tin = payload.get("tool_name", ""), payload.get("tool_input") or {}
    tresp, tuid = payload.get("tool_response"), payload.get("tool_use_id", "")
    interrupted = bool(payload.get("is_interrupt"))
    out = {}
    try:
        if tool == "Bash":
            failed = failed or response_failed(tresp)
            payload = {**payload, "_zero_tests": evidence.ran_zero_tests(" ".join(gates._strings(tresp)))}
            out = post_bash(sid, cwd, st0, tin, tuid, failed, interrupted, payload)
        elif tool in EDIT_TOOLS and not failed:
            post_edit(sid, cwd, tool, tin, tresp)
        elif tool.startswith("mcp__"):
            post_mcp(sid, cwd, st0, tool, tin, tresp, tuid, failed, payload)
    except Exception as exc:
        warn(f"post-tool tracker failed: {type(exc).__name__}: {exc}")
    return out or None


def post_bash(sid, cwd, st0, tin, tuid, failed, interrupted, payload):
    command = str(tin.get("command", ""))
    key = tuid or sha256(command)[:16]
    pend = st0["pending"].get(key) or {}
    run_cwd = pend.get("cwd") or cwd
    need_tree = bool(pend.get("checks")) or (not failed and bash_may_change(command))
    tree = None
    if need_tree:
        tree, _ = treelib.tree_id(run_cwd)
    commit = not failed and has_commit(command)
    for receipt_key in pend.get("receipt_keys") or []:
        settle_merge_receipt(receipt_key, failed, payload)
    top = treelib.toplevel(run_cwd)

    def mark(st):
        if pend.get("checks") and payload.get("_zero_tests") and not failed:
            st["pending"].pop(key, None)  # the run executed no tests: not evidence (neither pass nor fail)
        elif pend.get("checks") and not interrupted:
            evidence.post_runner(st, key, not failed, tree)
        elif pend:
            st["pending"].pop(key, None)
        if tree and top and not failed:
            changed = st.get("last_tree") is None or treelib.relevant_diff(top, st["last_tree"], tree) != []
            if changed:
                st["last_change_seq"] = evidence.bump(st)
            st["last_tree"] = tree
        elif tree:
            st["last_tree"] = tree
        if commit:
            st["last_change_seq"] = evidence.bump(st)
    state.update(sid, mark, cwd)
    if not failed and re.search(r"\bgh\b.*\bpr\s+create\b", command):
        return context_out("PostToolUse", review_reminder(st0.get("binding")))
    return {}


def review_reminder(binding):
    if binding and binding.get("parent"):
        tier = "Sol gpt-6.1-sol, xhigh (child-task PR)"
    else:
        tier = "Sol gpt-6.1-sol, high (small implementation)"
    return f"PR created. Next: run `maeng-review` ({tier}) before `maeng-ship merge`."


def settle_merge_receipt(key, failed, payload):
    if not failed:
        rec = receipts.load(key)
        receipts.consume(key, {"merge_sha": (rec.get("intent") or {}).get("head_sha"), "via": "hook"})
        return
    err = str(payload.get("error") or payload.get("tool_response") or "")
    if REJECTED.search(err):
        receipts.reject(key, "confirmed-rejection")  # else stays pending until reconcile


def post_edit(sid, cwd, tool, tin, tresp):
    run_formatter(cwd, tin)
    path = tin.get("file_path") or tin.get("notebook_path") or ""
    wd = str(Path(path).parent) if path and Path(path).parent.exists() else cwd
    tree, _ = treelib.tree_id(wd)
    top = treelib.toplevel(wd)
    issue = (state.load(sid, cwd).get("binding") or {}).get("issue")
    record = is_record_write(tool, tin, tresp, issue)

    def mark(st):
        if tree and top:
            if st.get("last_tree") is None or treelib.relevant_diff(top, st["last_tree"], tree) != []:
                st["last_change_seq"] = evidence.bump(st)
            st["last_tree"] = tree
        if record:
            st["last_record_seq"] = evidence.bump(st)
    state.update(sid, mark, cwd)


def notion_ids(obj):
    return sorted({m.replace("-", "").lower() for s in _flatten(obj) for m in UUID.findall(s)})


CONFIRMED_NOTION_REJECTION = re.compile(
    r"validation_error|object_not_found|unauthorized|restricted_resource|invalid_request|invalid_json|"
    r"\b(?:http|status)[ :=]*(?:400|401|403|404|422)\b", re.I)


def post_mcp(sid, cwd, st0, tool, tin, tresp, tuid, failed, payload=None):
    name = tool.split("__")[-1]
    if tool.startswith("mcp__claude_ai_Notion__"):
        if name in ("notion-create-pages", "notion-update-page", "notion-duplicate-page") \
                or name in gates.NOTION_STRUCTURAL:
            if failed:
                err = " ".join(str(x) for x in ((payload or {}).get("error"), (payload or {}).get("tool_response"), tresp) if x)
                if CONFIRMED_NOTION_REJECTION.search(err):
                    receipts.journal_rejected(tuid)
                # else (timeout, connection reset, unknown): the write may have landed; stay pending until reconcile
            else:
                ids = notion_ids(tresp) if name in ("notion-create-pages", "notion-create-database", "notion-duplicate-page") \
                    else notion_ids(tin)
                receipts.journal_sent(tuid, ids)
        elif name == "notion-fetch" and not failed:
            for pid in notion_ids(tin):
                receipts.journal_readback(pid)
        return
    if failed:
        return
    issue = (st0.get("binding") or {}).get("issue")
    if is_record_write(tool, tin, tresp, issue):
        state.update(sid, lambda st: st.__setitem__("last_record_seq", evidence.bump(st)), cwd)


# ---- Stop / SubagentStop / SessionEnd ------------------------------------

def compute_missing(st, cwd):
    missing = []
    top, common = treelib.toplevel(cwd), treelib.common_dir(cwd)
    tree = None
    if top and common:
        tree, _ = treelib.tree_id(cwd)
        v = evidence.Verifier(st, top, common)
        if tree and v.code_changed_since(st.get("baseline_tree"), tree) and not v.stop_satisfied(tree):
            _, reasons = v.ship_verified(tree)
            missing.append("UNVERIFIED: code changed but this tree has no passing verification or skip ("
                           + "; ".join(reasons) + "). Run the required checks, or `maeng-verify skip \"<reason>\"`.")
        elif not tree and st.get("last_change_seq", 0) > st.get("last_stop_seq", 0):
            missing.append("UNVERIFIED: tree id unavailable (dirty submodule?), no evidence can be recorded.")
    if st.get("last_change_seq", 0) > st.get("last_record_seq", 0):
        issue = (st.get("binding") or {}).get("issue")
        target = f"the bound issue {issue}" if issue else "Linear or Obsidian"
        missing.append(f"UNRECORDED: write your progress/decisions to {target} (Linear comment or Obsidian note) "
                       f"after the last change. Do not ask the user; record it yourself.")
    return missing, tree


def on_stop(payload):
    sid, cwd = payload.get("session_id", ""), payload.get("cwd", os.getcwd())
    st = state.load(sid, cwd)
    if world_of(payload, st) != guard.PERSONAL:
        return None
    work_cwd = st.get("cwd") or cwd
    missing, tree = compute_missing(st, cwd if treelib.toplevel(cwd) else work_cwd)

    def mark(s):
        s["last_stop_seq"] = s["seq"]
        if not missing and tree:
            s["baseline_tree"] = tree
        try:
            note = stub.write(s, "UNVERIFIED/UNRECORDED" if missing else "ok", missing)
        except OSError as exc:
            note = None
            warn(f"session stub failed: {exc}")
        task_stopped(s, payload, missing, tree, work_cwd, note)
    state.update(sid, mark, cwd)
    if not missing:
        return None
    if payload.get("stop_hook_active"):
        return {"systemMessage": "UNVERIFIED / UNRECORDED: " + " | ".join(missing)}
    return {"decision": "block", "reason": "Before stopping, resolve:\n- " + "\n- ".join(missing)}


def task_stopped(st, payload, missing, tree, cwd, note):
    """Status at a stop: a blocked stop keeps running, a yielded one is blocked, else the reply's marker line."""
    if not st.get("task_id"):
        return
    if missing and not payload.get("stop_hook_active"):
        state_, summary = "running", None
    elif missing:
        state_, summary = "blocked", None
    else:
        state_, summary = status.outcome(payload.get("last_assistant_message"))
    vstate = status.verify_state(st.get("evidence", []), tree, any(m.startswith("UNVERIFIED") for m in missing))
    head = git_out(cwd, "rev-parse", "HEAD")
    clean = tree and git_out(cwd, "rev-parse", "HEAD^{tree}") == tree
    try:
        status.write(st["task_id"], st["session_id"], state=state_, cwd=cwd,
                     task_name=(st.get("binding") or {}).get("issue"),
                     result_summary=summary if state_ in ("done", "failed") else None,
                     next_action=summary if state_ == "needs_input" else None,
                     blocker=" | ".join(missing) if state_ == "blocked" else None,
                     head_sha=head, tree_sha=tree, verify_state=vstate,
                     verified_head_sha=head if vstate == "pass" and clean else None,
                     artifact_paths=[str(note)] if note else [])
    except (OSError, ValueError) as exc:
        warn(f"status file failed: {exc}")


def last_assistant_text(payload):
    text = payload.get("last_assistant_message")
    if text:
        return str(text)
    path = payload.get("agent_transcript_path")
    if not path or not Path(path).is_file():
        return ""
    last = ""
    for line in Path(path).read_text(errors="ignore").splitlines():
        try:
            msg = json.loads(line).get("message", {})
        except ValueError:
            continue
        if msg.get("role") == "assistant":
            content = msg.get("content")
            last = content if isinstance(content, str) else " ".join(
                c.get("text", "") for c in content or [] if isinstance(c, dict))
    return last


def on_subagent_stop(payload):
    sid, cwd = payload.get("session_id", ""), payload.get("cwd", os.getcwd())
    if world_of(payload, state.load(sid, cwd)) != guard.PERSONAL or payload.get("stop_hook_active"):
        return None
    if not str(payload.get("agent_type", "")).endswith("implementer"):
        return None
    text = last_assistant_text(payload)
    if "Verification:" in text and "Unfinished:" in text:
        return None
    return {"decision": "block", "reason": "End your report with the `Verification:` and `Unfinished:` sections."}


def on_session_end(payload):
    sid, cwd = payload.get("session_id", ""), payload.get("cwd", os.getcwd())
    st = state.load(sid, cwd)
    if world_of(payload, st) != guard.PERSONAL:
        return None
    if st.get("stub"):
        state.update(sid, lambda s: stub.write(s, "ended", ended=True), cwd)
    tid = st.get("task_id")
    try:
        cur = status.read(tid) if tid else {}
        if cur.get("session_id") == sid and cur.get("state") in ("running", "idle"):
            status.write(tid, sid, state="ended")
    except (OSError, ValueError) as exc:
        warn(f"status file failed: {exc}")
    return None


HANDLERS = {
    "SessionStart": on_session_start,
    "UserPromptSubmit": on_prompt,
    "PreToolUse": on_pre,
    "PostToolUse": on_post,
    "PostToolUseFailure": lambda p: on_post(p, failed=True),
    "Stop": on_stop,
    "SubagentStop": on_subagent_stop,
    "SessionEnd": on_session_end,
}
