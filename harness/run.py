"""Project-independent entry point for the local harness (Python stdlib only).

Use --project explicitly in agent calls. start accepts a create request plus owner
and optional skill_paths; new starts default to library closeout with separate
Notion draft approval. File paths
are relative to the project; skill paths may be outside it. closeout resolves
GitHub files[].path against the project and expects separate readback files.
doctor and list take no stdin. --help includes the underlying command contract.
"""

import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys

import ledger


def skill_root():
    script = Path(__file__).resolve()
    installed = script.parent.parent
    if (installed / "SKILL.md").is_file():
        return installed
    return script.parent.parent / ".agents/skills/harness-run"


def verify_install():
    root = skill_root()
    manifest = root / "manifest.json"
    if not manifest.exists():
        # Repository checkout: the installed package always carries a manifest.
        ledger.require(Path(__file__).resolve().parent.name == "harness",
                       "installed manifest missing; reinstall the harness")
        return {"installation": "source-checkout", "skill": str(root)}
    data = json.loads(manifest.read_text())
    expected_files = {"SKILL.md", "agents/openai.yaml", "scripts/ledger.py",
                      "scripts/run.py", "references/README.md"}
    allowed_files = (expected_files, expected_files | {"references/NOTION-WORKSPACE.md"},
                     expected_files | {"references/NOTION-WORKSPACE.md", "scripts/tool_hook.py"},
                     expected_files | {"references/NOTION-WORKSPACE.md", "scripts/tool_hook.py",
                                       "scripts/work_records.py", "references/work-records/SKILL.md"})
    ledger.require(isinstance(data, dict) and set(data) == {"files", "release_id"}
                   and isinstance(data["files"], dict) and set(data["files"]) in allowed_files,
                   "invalid install manifest")
    hashes = json.dumps(data["files"], sort_keys=True, separators=(",", ":")).encode()
    ledger.require(ledger.sha(hashes) == data["release_id"] == root.parent.name,
                   "install release digest mismatch")
    for relative, expected in data["files"].items():
        path = root / relative
        ledger.require(path.resolve().is_relative_to(root.resolve()), "invalid install manifest path")
        ledger.require(ledger.sha(ledger.read_file(str(path))) == expected,
                       "installed files changed; reinstall before running")
    return {"installation": "user", "skill": str(root), "release": data["release_id"]}


def local_pin(value):
    path = Path(ledger.text(value, "skill path", 4096)).expanduser().resolve()
    ledger.require(path.name == "SKILL.md", "skill_paths must name SKILL.md files")
    return {"name": path.parent.name, "path": str(path),
            "sha256": ledger.sha(ledger.read_file(str(path), 256 * 1024)), "source": "local"}


def skill_path(project, value):
    path = Path(ledger.text(value, "skill path", 4096)).expanduser()
    return str((path if path.is_absolute() else project / path).resolve())


def project_path(project, value):
    path = Path(ledger.text(value, "path", 4096)).expanduser()
    if not path.is_absolute():
        path = project / path
    # Tracked files retain their identity: resolving a symlink would hide a
    # later retarget from the ledger's freshness checks. Skill inputs differ.
    resolved = path.resolve()
    ledger.require(resolved.is_relative_to(project), "file path escapes the selected project")
    ledger.require(not any(part.is_symlink() for part in (path, *path.parents)),
                   "tracked file paths must not use symlinks")
    return str(resolved)


def execute(project, action, data):
    project = Path(project).expanduser().resolve(strict=True)
    ledger.require(project.is_dir(), "project must be a directory")
    installation = verify_install()
    state = project / ".harness"
    ledger.require(not state.is_symlink(), "project .harness must not be a symlink")
    db = state / "tasks.sqlite"
    info = {**installation, "project": str(project), "database": str(db),
            "runtime": str(Path(__file__).resolve())}
    if action == "doctor":
        return {**info, "ledger_exists": db.is_file(), "python": sys.version.split()[0]}
    if action == "list" and not db.exists():
        return {**info, "tasks": []}
    if action == "start":
        ledger.require(isinstance(data, dict), "expected a JSON object")
        request = dict(data)
        owner = ledger.identifier(request.pop("owner", None))
        request.setdefault("closeout", {"mode": "library", "source_paths": []})
        paths = request.pop("skill_paths", [])
        ledger.require(isinstance(paths, list) and len(paths) <= 15, "invalid skill_paths")
        pins = [local_pin(str(skill_root() / "SKILL.md"))]
        for path in paths:
            pin = local_pin(skill_path(project, path))
            if pin["path"] not in {p["path"] for p in pins}:
                pins.append(pin)
        ledger.require(len({p["name"] for p in pins}) == len(pins), "duplicate skill names")
        ledger.validate("create", request)
        state.mkdir(mode=0o700, exist_ok=True)
        try:
            with (state / ".gitignore").open("x") as ignore:
                ignore.write("*\n")
        except FileExistsError:
            pass
        store = ledger.Ledger(str(db))
        store.dispatch("create", request)
        who = {"task_id": request["task_id"], "owner": owner}
        store.dispatch("claim", who)
        return {**store.dispatch("route", {**who, "skills": pins}), **info}
    ledger.require(db.is_file(), "no task ledger exists for this project; use start")
    store = ledger.Ledger(str(db))
    if action == "list":
        with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True) as connection:
            ids = [r[0] for r in connection.execute("SELECT id FROM tasks ORDER BY id")]
        tasks = []
        for task_id in ids:
            task = store.dispatch("status", {"task_id": task_id})
            tasks.append({key: task[key] for key in ("task_id", "stage", "next_action", "owner")})
        return {**info, "tasks": tasks}
    ledger.validate(action, data)
    data = dict(data)
    for field in ("path", "evidence_path", "readback_path", "payload_path", "input_path"):
        if field in data:
            data[field] = project_path(project, data[field])
    if action in {"configure-hooks", "before-delegate"}:
        data["write_paths"] = [project_path(project, path) for path in data["write_paths"]]
    if action == "prepare-tool":
        ledger.require(isinstance(data["gate"], dict), "invalid tool gate")
        data["gate"] = dict(data["gate"])
        if data["kind"] == "write":
            data["gate"]["payload_path"] = project_path(project, data["gate"]["payload_path"])
        elif data["kind"] == "delegate":
            data["gate"]["write_paths"] = [project_path(project, path) for path in data["gate"]["write_paths"]]
    if action == "check":
        ledger.require("source_paths" not in data, "runner resolves source_paths from the frozen policy")
        status = store.dispatch("status", {"task_id": data["task_id"]})
        policy = status["request"].get("closeout", {})
        if policy.get("mode") in {"managed", "github", "library"}:
            field = "source_paths" if policy["mode"] == "library" else "github_paths"
            data["source_paths"] = {path: project_path(project, path) for path in policy[field]}
    if action == "closeout":
        if "summary_path" in data:
            data["summary_path"] = project_path(project, data["summary_path"])
        if "files" in data:
            ledger.require(isinstance(data["files"], list)
                           and all(isinstance(item, dict) and set(item) == {"path", "readback_path"}
                                   for item in data["files"]), "invalid closeout files")
            data["files"] = [{**item, "local_path": project_path(project, item["path"]),
                              "readback_path": project_path(project, item["readback_path"])}
                             for item in data["files"]]
    if action == "route":
        data["skills"] = [{**pin, "path": skill_path(project, pin["path"])}
                          for pin in data["skills"]]
    if action in {"enqueue", "approve", "receipt"}:
        local = data.get("adapter") == "local"
        if action != "enqueue":
            status = store.dispatch("status", {"task_id": data["task_id"]})
            local = any(p["publication_id"] == data["publication_id"] and p["adapter"] == "local"
                        for p in status["publications"])
        if local:
            data["target"] = project_path(project, data["target"])
    return {**store.dispatch(action, data), **info}


def main():
    parser = argparse.ArgumentParser(description=__doc__ + "\n" + ledger.__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default=str(Path.cwd()), help="target workspace, defaults to cwd")
    parser.add_argument("command", choices=["doctor", "start", "list", *ledger.FIELDS])
    args = parser.parse_args()
    try:
        data = None
        if args.command not in {"doctor", "list"}:
            raw = sys.stdin.read(128 * 1024 + 1)
            ledger.require(len(raw) <= 128 * 1024, "request too large")
            data = json.loads(raw, object_pairs_hook=ledger.unique_object)
        session = os.environ.get("CODEX_THREAD_ID")
        if args.command in {"start", "resume"} and os.environ.get("CODEX_SESSION_ID"):
            ledger.require(session and isinstance(data, dict) and data.get("owner") == session,
                           "owner must equal CODEX_THREAD_ID; the entry receipt is not an owner")
        result = execute(args.project, args.command, data)
        if args.command in {"start", "resume"} and session and result.get("owner") == session:
            from tool_hook import bind_session
            bind_session(result["project"], result["task_id"], session)
        print(ledger.canonical(result))
        return 1 if result.get("stage") == "blocked" else 0
    except ledger.LedgerError as exc:
        print(ledger.canonical({"error": str(exc)}), file=sys.stderr)
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error, RuntimeError):
        print(ledger.canonical({"error": "request rejected; check project, input and installation"}), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
