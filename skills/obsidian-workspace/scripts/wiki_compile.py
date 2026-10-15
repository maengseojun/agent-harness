#!/usr/bin/env python3
"""Preview or apply an explicit, source-hash-bound Obsidian wiki plan."""

import argparse
import json
import re
from pathlib import Path
from urllib.parse import unquote

import source_snapshot as snapshot


HASH_RE = snapshot.HASH_RE
OPERATION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
TEXT_SUFFIXES = {".body", ".csv", ".html", ".json", ".md", ".text", ".tsv", ".txt", ".xml", ".yaml", ".yml"}
WIKILINK_RE = re.compile(r"!?\[\[([^\]]+)\]\]")
MARKDOWN_LINK_RE = re.compile(r"(?<!!)(?<!\\)\[([^\]\n]*)\]\(\s*(<[^>\n]*>|(?:\\.|[^)\s])+)(?:\s+(['\"])[^\)\n]*?\3)?\s*\)")
FENCED_CODE_RE = re.compile(r"(?ms)^[ \t]*(```+|~~~+)[^\n]*\n.*?^[ \t]*\1[ \t]*$")
INLINE_CODE_RE = re.compile(r"(?<!`)`[^`\n]*`(?!`)")
BACKUP_ROOT = "raw/wiki-compile-versions"


def fail(code, message):
    raise snapshot.SnapshotError(code, message)


def validate_plan(value):
    if not isinstance(value, dict) or set(value) != {"operation_id", "hub", "sources", "notes"}:
        fail("invalid_plan", "plan must contain exactly operation_id, hub, sources, and notes")
    operation_id = value["operation_id"]
    if not isinstance(operation_id, str) or not OPERATION_ID_RE.fullmatch(operation_id) or operation_id in {".", ".."}:
        fail("invalid_plan", "operation_id must be a short path-safe identifier")

    hub = value["hub"]
    parts = snapshot.validate_relative_path(hub)
    if len(parts) < 2 or parts[0] != "hubs" or not hub.lower().endswith(".md"):
        fail("invalid_hub", "hub must be an exact Markdown path under hubs/")

    sources = value["sources"]
    notes = value["notes"]
    if not isinstance(sources, list) or not sources or not isinstance(notes, list) or not notes:
        fail("invalid_plan", "plan needs at least one selected source and one derived note")

    source_paths = set()
    for source in sources:
        if not isinstance(source, dict) or set(source) != {"path", "sha256"}:
            fail("invalid_source", "each source must contain exactly path and sha256")
        path, digest = source["path"], source["sha256"]
        parts = snapshot.validate_relative_path(path)
        allowed = parts[0] == "raw" or (len(parts) >= 3 and parts[:2] == ["wiki", "sources"])
        if not allowed or path.startswith(BACKUP_ROOT + "/") or Path(path).suffix.lower() not in TEXT_SUFFIXES:
            fail("invalid_source", "sources must be selected text files under raw/ or wiki/sources/")
        if path in source_paths:
            fail("duplicate_source", f"duplicate source path: {path}")
        if not isinstance(digest, str) or not HASH_RE.fullmatch(digest):
            fail("invalid_source", f"source sha256 is invalid: {path}")
        source_paths.add(path)

    target_paths = set()
    for note in notes:
        if not isinstance(note, dict) or set(note) != {"path", "expected_sha256", "body"}:
            fail("invalid_note", "each note must contain exactly path, expected_sha256, and body")
        path, expected, body = note["path"], note["expected_sha256"], note["body"]
        parts = snapshot.validate_relative_path(path)
        is_wiki = len(parts) >= 3 and parts[0] == "wiki" and parts[1] in {"answers", "concepts", "entities"}
        is_index_or_log = path in {"wiki/index.md", "log.md"}
        is_selected_hub = path == hub
        if not path.lower().endswith(".md") or not (is_wiki or is_index_or_log or is_selected_hub):
            fail("invalid_target", "targets must be derived wiki notes, wiki/index.md, log.md, or the selected hub")
        if path in target_paths or path in source_paths:
            fail("duplicate_target", f"duplicate or source target path: {path}")
        if expected is not None and (not isinstance(expected, str) or not HASH_RE.fullmatch(expected)):
            fail("invalid_note", f"expected_sha256 must be null or a lowercase SHA-256: {path}")
        if not isinstance(body, str) or not body.strip() or "\x00" in body:
            fail("invalid_note", f"body must be non-empty UTF-8 text: {path}")
        try:
            body.encode("utf-8")
        except UnicodeEncodeError:
            fail("invalid_note", f"body contains invalid UTF-8 text: {path}")
        target_paths.add(path)

    return value


def load_plan(value, vault):
    path = Path(value)
    if not path.is_absolute():
        fail("invalid_plan_path", "plan path must be absolute")
    try:
        if path.is_symlink() or not path.is_file():
            fail("invalid_plan_path", "plan must be an existing regular file, not a symlink")
        resolved = path.resolve(strict=True)
        if resolved.is_relative_to(vault.resolve(strict=True)):
            fail("invalid_plan_path", "plan files must stay outside the vault")
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=snapshot.reject_duplicate_keys)
    except snapshot.SnapshotError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        fail("invalid_plan", f"cannot read a unique-key UTF-8 JSON plan: {exc}")
    return validate_plan(value), resolved, snapshot.sha256(raw)


def backup_path(operation_id, target):
    suffix = target[len("wiki/"):] if target.startswith("wiki/") else target
    return f"{BACKUP_ROOT}/{operation_id}/{suffix}.body"


def markdown_targets(body):
    visible = FENCED_CODE_RE.sub("", body)
    visible = INLINE_CODE_RE.sub("", visible)
    for match in MARKDOWN_LINK_RE.finditer(visible):
        raw = match.group(2)
        target = raw[1:-1] if raw.startswith("<") and raw.endswith(">") else raw
        target = re.sub(r"\\([\\`*_{}\[\]()#+\-.!<>| ])", r"\1", target)
        target = unquote(re.split(r"[?#]", target, maxsplit=1)[0])
        if (target and not target.startswith("//") and
                not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target) and
                Path(target).suffix.lower() == ".md"):
            yield target


def extract_links(notes):
    links = []
    seen = set()
    for note in notes:
        for match in WIKILINK_RE.finditer(note["body"]):
            target = match.group(1).split("|", 1)[0].strip().split("#", 1)[0].strip()
            if not target:
                target = note["path"][:-3]
            if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target):
                continue
            if Path(target).suffix and Path(target).suffix.lower() != ".md":
                continue
            item = (note["path"], target)
            if item not in seen:
                seen.add(item)
                links.append({"source": item[0], "target": item[1]})
        for target in markdown_targets(note["body"]):
            item = (note["path"], target)
            if item not in seen:
                seen.add(item)
                links.append({"source": item[0], "target": item[1]})
    return links


def classify_target(note, state):
    if state["exists"] and state["body"] == note["body"]:
        return "noop"
    expected = note["expected_sha256"]
    if expected is None:
        if state["exists"]:
            fail("target_conflict", f"target exists with different content: {note['path']}")
        return "create"
    if not state["exists"] or snapshot.sha256(state["body"].encode("utf-8")) != expected:
        fail("target_conflict", f"target no longer matches expected_sha256: {note['path']}")
    return "update"


def unique_paths(paths):
    return list(dict.fromkeys(paths))


def parse_notes_result(paths, payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("notes"), list) or len(payload["notes"]) != len(paths):
        fail("obsidian_cli_invalid_output", "Obsidian eval returned an unexpected note list")
    result = {}
    for expected, item in zip(paths, payload["notes"]):
        if not isinstance(item, dict) or item.get("path") != expected or not isinstance(item.get("exists"), bool):
            fail("obsidian_cli_invalid_output", f"Obsidian eval returned an invalid entry for {expected}")
        if item.get("error"):
            fail("obsidian_note_unavailable", f"cannot read selected vault path {expected}: {item['error']}")
        if item["exists"]:
            if not isinstance(item.get("body"), str):
                fail("obsidian_cli_invalid_output", f"Obsidian eval returned no text body for {expected}")
            result[expected] = {"exists": True, "body": item["body"], "sha256": snapshot.sha256(item["body"].encode("utf-8"))}
        else:
            result[expected] = {"exists": False, "body": None, "sha256": None}
    return result


def parse_eval(output):
    if not output.startswith("=> "):
        fail("obsidian_cli_invalid_output", f"Obsidian eval returned no JSON result: {output[:200]!r}")
    try:
        return json.loads(output[3:])
    except json.JSONDecodeError as exc:
        fail("obsidian_cli_invalid_output", f"Obsidian eval returned invalid JSON: {exc}")


LINK_JS = r'''function linkCandidates(target, source, planned) {
  const clean = target.split("|")[0].split("#")[0].trim();
  const value = clean || source.replace(/\.md$/i, "");
  const normalize = parts => {
    const normalized = [];
    for (const part of parts) {
      if (!part || part === ".") continue;
      if (part === "..") { if (!normalized.length) return null; normalized.pop(); }
      else normalized.push(part);
    }
    return normalized.join("/");
  };
  const rootCandidate = normalize(value.startsWith("/") ? value.slice(1).split("/") : value.split("/"));
  const relativeCandidate = value.startsWith("/") ? null : normalize([...source.split("/").slice(0, -1), ...value.split("/")]);
  const candidates = [];
  for (const candidate of [rootCandidate, relativeCandidate]) {
    if (candidate) candidates.push(candidate, candidate.toLowerCase().endsWith(".md") ? candidate : candidate + ".md");
  }
  if (!value.includes("/")) {
    const base = value.replace(/\.md$/i, "");
    for (const path of planned) if (path.split("/").pop().replace(/\.md$/i, "") === base) candidates.push(path);
  }
  if (candidates.some(path => planned.has(path))) return true;
  const found = app.metadataCache.getFirstLinkpathDest(value, source);
  if (found && found.extension === "md") return true;
  return candidates.some(path => {
    const file = app.vault.getAbstractFileByPath(path);
    return !!file && file.extension === "md";
  });
}
function markdownTargets(body) {
  let visible=body.replace(/^[ \t]*(```+|~~~+)[^\n]*\n[\s\S]*?^[ \t]*\1[ \t]*$/gm, "");
  visible=visible.replace(/(?<!`)`[^`\n]*`(?!`)/g, "");
  const targets=[];
  const pattern=/(?<!!)(?<!\\)\[([^\]\n]*)\]\(\s*(<[^>\n]*>|(?:\\.|[^)\s])+)(?:\s+(["'])[^)\n]*?\3)?\s*\)/g;
  for(const match of visible.matchAll(pattern)){
    let target=match[2];
    if(target.startsWith("<")&&target.endsWith(">"))target=target.slice(1,-1);
    target=target.replace(/\\([\\`*_{}\[\]()#+\-.!<>| ])/g,"$1");
    target=target.split(/[?#]/,1)[0];
    try{target=decodeURIComponent(target);}catch(_){}
    if(target&&!target.startsWith("//")&&!/^[A-Za-z][A-Za-z0-9+.-]*:/.test(target)&&/\.md$/i.test(target))targets.push(target);
  }
  return targets;
}
function missingWikiLinks(notes, planned) {
  const missing = [];
  for (const note of notes) {
    const targets=[];
    for (const match of note.body.matchAll(/!?\[\[([^\]]+)\]\]/g)) targets.push(match[1].split("|")[0].split("#")[0].trim());
    targets.push(...markdownTargets(note.body));
    for (const target of targets) {
      if (target && /^[A-Za-z][A-Za-z0-9+.-]*:/.test(target)) continue;
      if (target && /\.[^/]+$/.test(target) && !/\.md$/i.test(target)) continue;
      if (!linkCandidates(target, note.path, planned)) missing.push({source: note.path, target});
    }
  }
  return missing;
}'''


class VaultCLI:
    def __init__(self, invoke=None):
        self.invoke = invoke

    def call(self, arguments):
        return (self.invoke or snapshot.invoke_obsidian)(arguments)

    def assert_vault(self, vault):
        actual = self.call(["vault", "info=path"])
        if actual != str(vault):
            fail("wrong_vault", f"Obsidian CLI resolved a different or empty vault path: {actual!r}")

    def eval_json(self, code):
        return parse_eval(self.call(["eval", "code=" + code]))

    def read_notes(self, paths):
        if not paths:
            return {}
        request = json.dumps({"paths": paths}, ensure_ascii=False, separators=(",", ":"))
        code = (
            "(async()=>{const request=" + request + ";if(app.vault.adapter.getBasePath()!==" +
            json.dumps(str(snapshot.EXPECTED_VAULT)) + ")throw new Error('wrong vault');const notes=[];"
            "for(const path of request.paths){const file=app.vault.getAbstractFileByPath(path);"
            "if(!file){notes.push({path,exists:false});continue;}if(typeof file.extension!=='string'||file.path!==path)"
            "throw new Error('path is not a regular file: '+path);notes.push({path,exists:true,body:await app.vault.read(file)});}"
            "return JSON.stringify({notes});})()"
        )
        return parse_notes_result(paths, self.eval_json(code))

    def check_links(self, links, planned_paths):
        if not links:
            return []
        request = json.dumps({"links": links, "planned": planned_paths}, ensure_ascii=False, separators=(",", ":"))
        code = (
            "(async()=>{const request=" + request + ";if(app.vault.adapter.getBasePath()!==" +
            json.dumps(str(snapshot.EXPECTED_VAULT)) + ")throw new Error('wrong vault');" + LINK_JS +
            "const planned=new Set(request.planned);return JSON.stringify({missing:request.links.filter(link=>!linkCandidates(link.target,link.source,planned))});})()"
        )
        payload = self.eval_json(code)
        if not isinstance(payload, dict) or not isinstance(payload.get("missing"), list):
            fail("obsidian_cli_invalid_output", "Obsidian eval returned an invalid link check")
        return payload["missing"]

    def apply(self, plan_path, plan_hash, operation_id):
        code = self.apply_code(plan_path, plan_hash)
        payload = self.eval_json(code)
        if not isinstance(payload, dict) or payload.get("operation_id") != operation_id:
            fail("obsidian_cli_invalid_output", "Obsidian eval returned an invalid apply receipt")
        if payload.get("status") not in {"applied", "noop", "rejected", "partial_failure"}:
            fail("obsidian_cli_invalid_output", "Obsidian eval returned an unknown apply status")
        paths = payload.get("performed_paths")
        if not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
            fail("obsidian_cli_invalid_output", "Obsidian eval returned invalid performed_paths")
        return payload

    @staticmethod
    def apply_code(plan_path, plan_hash):
        template = r'''(async()=>{
const stagedPath=__PLAN_PATH__, expectedPlanHash=__PLAN_HASH__, expectedVault=__VAULT__;
const performed=[];
const errorInfo=(code,path,message)=>({code,path,message:String(message||code)});
try {
  const fs=require("fs"), crypto=require("crypto");
  if(app.vault.adapter.getBasePath()!==expectedVault) throw Object.assign(new Error("wrong vault"),{code:"wrong_vault"});
  const bytes=fs.readFileSync(stagedPath);
  if(crypto.createHash("sha256").update(bytes).digest("hex")!==expectedPlanHash) throw Object.assign(new Error("staged plan changed"),{code:"plan_changed"});
  const plan=JSON.parse(bytes.toString("utf8"));
__LINK_JS__
  const hash=text=>crypto.createHash("sha256").update(text,"utf8").digest("hex");
const read=async path=>{const file=app.vault.getAbstractFileByPath(path);if(!file)return {exists:false,body:null,file:null};if(typeof file.extension!=="string"||file.path!==path)throw Object.assign(new Error("path is not a regular file"),{code:"path_conflict",path});return {exists:true,body:await app.vault.read(file),file};};
  const checkSources=async()=>{for(const source of plan.sources){const current=await read(source.path);if(!current.exists||hash(current.body)!==source.sha256)throw Object.assign(new Error("selected source changed"),{code:"source_changed",path:source.path});}};
  const planned=new Set(plan.notes.map(note=>note.path));
  const ensureFolders=async filePath=>{const parts=filePath.split("/");parts.pop();let current="";for(const part of parts){current=current?current+"/"+part:part;const folder=app.vault.getAbstractFileByPath(current);if(folder){if(!Array.isArray(folder.children))throw Object.assign(new Error("target parent is not a folder"),{code:"parent_conflict",path:current});}else{await app.vault.createFolder(current);performed.push(current);}}};
  const targetAction=(note,current)=>{if(current.exists&&current.body===note.body)return "noop";if(note.expected_sha256===null){if(current.exists)throw Object.assign(new Error("target has different content"),{code:"target_conflict",path:note.path});return "create";}if(!current.exists||hash(current.body)!==note.expected_sha256)throw Object.assign(new Error("target changed from expected hash"),{code:"target_conflict",path:note.path});return "update";};
  const backupPath=(target)=>{const suffix=target.startsWith("wiki/")?target.slice(5):target.startsWith("hubs/")?target:target;return "raw/wiki-compile-versions/"+plan.operation_id+"/"+suffix+".body";};
  await checkSources();
  const hub=await read(plan.hub);
  if(!planned.has(plan.hub)&&!hub.exists)throw Object.assign(new Error("selected hub is missing"),{code:"missing_hub",path:plan.hub});
  const missing=missingWikiLinks(plan.notes,planned);
  if(missing.length)throw Object.assign(new Error("plan has missing note links"),{code:"missing_links",path:missing[0].source});
  const actions=[];
  for(const note of plan.notes){
    const current=await read(note.path), action=targetAction(note,current), backup=backupPath(note.path);
    if(action==="update"){
      const prior=await read(backup);
      if(prior.exists&&prior.body!==current.body)throw Object.assign(new Error("backup already contains different bytes"),{code:"backup_conflict",path:backup});
    }else if(action==="create"&&(await read(backup)).exists){
      throw Object.assign(new Error("operation id already has a backup for this target"),{code:"backup_conflict",path:backup});
    }
    for(const path of [note.path, ...(action==="update"?[backup]:[])]){
      let parent=path.split("/");parent.pop();let currentPath="";
      for(const part of parent){currentPath=currentPath?currentPath+"/"+part:part;const folder=app.vault.getAbstractFileByPath(currentPath);if(folder&&!Array.isArray(folder.children))throw Object.assign(new Error("target parent is not a folder"),{code:"parent_conflict",path:currentPath});}
    }
    actions.push({note,action,current,backup});
  }
  for(const item of actions){
    const {note,backup}=item;
    await checkSources();
    let current=await read(note.path), action=targetAction(note,current);
    if(action==="noop")continue;
    if(action!==item.action)throw Object.assign(new Error("target changed after preflight"),{code:"target_conflict",path:note.path});
    if(action==="update"){
      const prior=await read(backup);
      if(!prior.exists){await ensureFolders(backup);await app.vault.create(backup,current.body);performed.push(backup);}
      else if(prior.body!==current.body)throw Object.assign(new Error("backup changed after preflight"),{code:"backup_conflict",path:backup});
    }
    await checkSources();
    current=await read(note.path);
    action=targetAction(note,current);
    if(action==="noop")continue;
    if(action!==item.action)throw Object.assign(new Error("target changed before write"),{code:"target_conflict",path:note.path});
    await ensureFolders(note.path);
    current=await read(note.path);
    action=targetAction(note,current);
    if(action==="noop")continue;
    if(action!==item.action)throw Object.assign(new Error("target changed before write"),{code:"target_conflict",path:note.path});
    if(current.exists)await app.vault.modify(current.file,note.body);else await app.vault.create(note.path,note.body);
    performed.push(note.path);
  }
  return JSON.stringify({operation_id:plan.operation_id,status:performed.some(path=>plan.notes.some(note=>note.path===path))?"applied":"noop",performed_paths:performed});
}catch(error){
  let operation_id=null;try{operation_id=JSON.parse(require("fs").readFileSync(stagedPath,"utf8")).operation_id;}catch(_){}
  return JSON.stringify({operation_id,status:performed.length?"partial_failure":"rejected",performed_paths:performed,error:errorInfo(error.code||"apply_failed",error.path||null,error.message||error)});
}
})()'''
        replacements = {
            "__PLAN_PATH__": json.dumps(str(plan_path)),
            "__PLAN_HASH__": json.dumps(plan_hash),
            "__VAULT__": json.dumps(str(snapshot.EXPECTED_VAULT)),
            "__LINK_JS__": LINK_JS,
        }
        return re.sub(r"__PLAN_PATH__|__PLAN_HASH__|__VAULT__|__LINK_JS__", lambda match: replacements[match.group(0)], template)


def preflight(plan, adapter):
    sources = plan["sources"]
    notes = plan["notes"]
    target_paths = [note["path"] for note in notes]
    read_paths = unique_paths([source["path"] for source in sources] + [plan["hub"]] + target_paths)
    states = adapter.read_notes(read_paths)
    source_rows = []
    for source in sources:
        current = states[source["path"]]
        if not current["exists"]:
            fail("source_missing", f"selected source is missing: {source['path']}")
        if current["sha256"] != source["sha256"]:
            fail("source_changed", f"selected source hash changed: {source['path']}")
        source_rows.append({"path": source["path"], "sha256": source["sha256"], "verified": True})

    if plan["hub"] not in target_paths and not states[plan["hub"]]["exists"]:
        fail("missing_hub", f"selected hub is missing: {plan['hub']}")

    changes = []
    backup_targets = []
    for note in notes:
        current = states[note["path"]]
        action = classify_target(note, current)
        item = {
            "path": note["path"], "action": action,
            "expected_sha256": note["expected_sha256"], "current_sha256": current["sha256"],
        }
        item["backup_path"] = backup_path(plan["operation_id"], note["path"])
        backup_targets.append((note, current, item["backup_path"], action))
        changes.append(item)

    backup_states = adapter.read_notes(unique_paths(path for _, _, path, _ in backup_targets))
    for note, current, path, action in backup_targets:
        prior = backup_states[path]
        if action == "create" and prior["exists"]:
            fail("backup_conflict", f"version path already exists for a new target: {path}")
        if action == "update" and prior["exists"] and prior["body"] != current["body"]:
            fail("backup_conflict", f"version path already contains different text: {path}")
        if action == "update":
            row = next(item for item in changes if item["path"] == note["path"])
            row["backup_reused"] = prior["exists"]

    links = extract_links(notes)
    missing = adapter.check_links(links, target_paths)
    if missing:
        first = missing[0]
        fail("missing_link", f"note link from {first.get('source')} does not resolve: {first.get('target')}")

    return {"sources": source_rows, "changes": changes, "links_checked": len(links), "states": states, "backup_states": backup_states}


def apply_result(plan, plan_path, plan_hash, adapter, before):
    all_backup_paths = [backup_path(plan["operation_id"], note["path"]) for note in plan["notes"]]
    effect_paths = unique_paths([note["path"] for note in plan["notes"]] + all_backup_paths)
    apply_error = None
    receipt = None
    try:
        adapter.assert_vault(snapshot.validate_vault(str(snapshot.EXPECTED_VAULT)))
        receipt = adapter.apply(plan_path, plan_hash, plan["operation_id"])
    except Exception as exc:
        apply_error = {"code": getattr(exc, "code", "apply_uncertain"), "message": str(exc)}

    try:
        after = adapter.read_notes(effect_paths)
    except Exception as exc:
        return {
            "ok": False, "status": "uncertain", "operation_id": plan["operation_id"],
            "performed_paths": receipt["performed_paths"] if receipt else None,
            "observed_changed_paths": [], "readback": [],
            "error": apply_error or {"code": getattr(exc, "code", "readback_failed"), "message": str(exc)},
            "readback_error": str(exc),
        }

    changed = []
    readback = []
    note_by_path = {note["path"]: note for note in plan["notes"]}
    for path in effect_paths:
        old = before.get(path, {"exists": False, "sha256": None})
        current = after[path]
        if old["exists"] != current["exists"] or old["sha256"] != current["sha256"]:
            changed.append(path)
        if path in note_by_path:
            readback.append({"path": path, "exists": current["exists"], "sha256": current["sha256"], "desired_match": current["exists"] and current["body"] == note_by_path[path]["body"]})
        elif current["exists"]:
            readback.append({"path": path, "exists": True, "sha256": current["sha256"], "desired_match": None})

    receipt_status = receipt["status"] if receipt else "uncertain"
    all_desired = all(after[note["path"]]["exists"] and after[note["path"]]["body"] == note["body"] for note in plan["notes"])
    if apply_error:
        status, ok = "uncertain", False
    elif receipt_status == "partial_failure":
        status, ok = "partial_failure", False
    elif receipt_status == "rejected":
        status, ok = ("partial_failure", False) if changed else ("rejected", False)
    elif not all_desired:
        status, ok = ("partial_failure", False) if changed else ("uncertain", False)
    elif changed:
        status, ok = "applied", True
    else:
        status, ok = "noop", True
    error = receipt.get("error") if receipt else apply_error
    return {
        "ok": ok, "status": status, "operation_id": plan["operation_id"],
        "performed_paths": receipt["performed_paths"] if receipt else None,
        "observed_changed_paths": changed, "readback": readback, "error": error,
    }


def run(args, adapter=None):
    vault = snapshot.validate_vault(args.vault)
    adapter = adapter or VaultCLI()
    adapter.assert_vault(vault)
    plan, plan_path, plan_hash = load_plan(args.plan, vault)
    checked = preflight(plan, adapter)
    if not args.apply:
        return {
            "ok": True, "status": "preview", "applied": False,
            "operation_id": plan["operation_id"], "hub": plan["hub"],
            "sources": checked["sources"], "notes": checked["changes"],
            "links_checked": checked["links_checked"],
        }
    before = dict(checked["states"])
    before.update(checked["backup_states"])
    for path in [note["path"] for note in plan["notes"]]:
        backup = backup_path(plan["operation_id"], path)
        before.setdefault(backup, {"exists": False, "body": None, "sha256": None})
    return apply_result(plan, plan_path, plan_hash, adapter, before)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True, help="exact configured vault folder")
    parser.add_argument("--plan", required=True, help="absolute path to a private UTF-8 JSON plan")
    parser.add_argument("--apply", action="store_true", help="apply the explicitly reviewed plan; default is preview")
    args = parser.parse_args(argv)
    try:
        result = run(args)
    except snapshot.SnapshotError as exc:
        result = {"ok": False, "status": "rejected", "error": {"code": exc.code, "message": str(exc)}}
    except Exception as exc:
        result = {"ok": False, "status": "rejected", "error": {"code": "compile_failed", "message": str(exc)}}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
