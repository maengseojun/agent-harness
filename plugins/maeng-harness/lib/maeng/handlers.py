"""Hook event handlers. Each returns the JSON object to print (or None)."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import evidence, gates, guard, receipts, state, stub
from . import tree as treelib
from .common import home_dir, now_iso, read_json, sha256, vault_dir
from .shellparse import ParseError, program, split_segments

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
EDIT_TOOLS = ("Edit", "Write", "NotebookEdit", "MultiEdit")
UUID = re.compile(r"[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}")
REJECTED = re.compile(r"stale info|non-fast-forward|\[rejected\]|\[remote rejected\]|rejected", re.I)
COMMIT_SUBS = {"commit", "merge", "rebase", "am", "cherry-pick", "revert", "pull"}


def warn(msg):
    print("maeng-harness: " + msg, file=sys.stderr)


def deny_out(reason):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def context_out(event, text):
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}


def world_of(payload, st=None):
    """Session world: the cwd the session started in when known, else the hook's cwd."""
    cwd = (st or {}).get("cwd") or payload.get("cwd") or os.getcwd()
    return guard.classify(cwd)


# ---- SessionStart --------------------------------------------------------

def plugin_version():
    try:
        return read_json(PLUGIN_ROOT / ".claude-plugin/plugin.json")["version"]
    except (OSError, ValueError, KeyError):
        return "?"


def build_context(cwd):
    lines = [f"maeng-harness {plugin_version()} (personal world). Gates: G1 code-ship, G2 Notion, G3 eta."]
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
    missing = [str(p) for p in guard.eta_checkouts() if guard.isolation_missing(p)]
    if missing:
        lines.append(f"{len(missing)} eta checkout(s) lack isolation: run `maeng-eta-isolate --apply`.")
    text = "\n".join(lines)
    return text.encode()[:2000].decode(errors="ignore")


def on_session_start(payload):
    cwd, sid = payload.get("cwd", os.getcwd()), payload.get("session_id", "")
    world = guard.classify(cwd)
    if world == guard.ETA:
        return context_out("SessionStart", "maeng-harness is loaded in an eta checkout (misconfigured). Personal "
                           "hooks are inert here. Run `maeng-eta-isolate --apply` and restart this session.")
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

def on_prompt(payload):
    sid, cwd = payload.get("session_id", ""), payload.get("cwd", os.getcwd())
    st = state.load(sid, cwd)
    if world_of(payload, st) != guard.PERSONAL:
        return None
    tree, _ = treelib.tree_id(cwd)
    def mark(s):
        s["turn"] += 1
        s["cwd"] = s.get("cwd") or cwd
        if tree:
            s["baseline_tree"] = s["baseline_tree"] or tree
            s["last_tree"] = tree
    state.update(sid, mark, cwd)
    return None


# ---- PreToolUse ----------------------------------------------------------

def on_pre(payload):
    sid, cwd = payload.get("session_id", ""), payload.get("cwd", os.getcwd())
    st = state.load(sid, cwd)
    world = world_of(payload, st)
    if world == guard.ETA:
        return None
    tool, tin, tuid = payload.get("tool_name", ""), payload.get("tool_input") or {}, payload.get("tool_use_id", "")
    tin = tin if isinstance(tin, dict) else {}
    try:
        dec = gates.evaluate(tool, tin, gates.Ctx(cwd, st, world), tuid)
    except Exception as exc:  # gate cannot decide: fail closed
        return deny_out(f"maeng gate error ({type(exc).__name__}: {exc}); denied because the gate cannot decide.")
    if not dec.allow:
        return deny_out(dec.reason)
    if world != guard.PERSONAL:
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
    if rec:
        run_cwd = gates._abs(rec["cd"], cwd) if rec["cd"] else cwd
        tree_start, _ = treelib.tree_id(run_cwd)
        common = treelib.common_dir(run_cwd)
    key = tuid or sha256(str(tin.get("command", "")))[:16]

    def mark(st):
        if rec:
            evidence.pre_runner(st, key, tin.get("command", ""), rec, tree_start, common)
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
    linear = tool.startswith(("mcp__claude_ai_Linear__", "mcp__linear__")) and name.startswith(("save_", "create_", "update_"))
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
        if pend.get("checks") and not interrupted:
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
        tier = "Astra gpt-6-astra, medium (child-task PR)"
    else:
        tier = "Sol gpt-6.1-sol, xhigh (small implementation)"
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
        if name in ("notion-create-pages", "notion-update-page", "notion-update-data-source"):
            if failed:
                err = " ".join(str(x) for x in ((payload or {}).get("error"), (payload or {}).get("tool_response"), tresp) if x)
                if CONFIRMED_NOTION_REJECTION.search(err):
                    receipts.journal_rejected(tuid)
                # else (timeout, connection reset, unknown): the write may have landed; stay pending until reconcile
            else:
                ids = notion_ids(tresp) if name == "notion-create-pages" else notion_ids(tin)
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
            stub.write(s, "UNVERIFIED/UNRECORDED" if missing else "ok", missing)
        except OSError as exc:
            warn(f"session stub failed: {exc}")
    state.update(sid, mark, cwd)
    if not missing:
        return None
    if payload.get("stop_hook_active"):
        return {"systemMessage": "UNVERIFIED / UNRECORDED: " + " | ".join(missing)}
    return {"decision": "block", "reason": "Before stopping, resolve:\n- " + "\n- ".join(missing)}


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
    if world_of(payload, st) != guard.PERSONAL or not st.get("stub"):
        return None
    state.update(sid, lambda s: stub.write(s, "ended", ended=True), cwd)
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
