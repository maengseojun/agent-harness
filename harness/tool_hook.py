"""Four lifecycle gates for local Codex tools; no network or model calls.

Planned tool inputs are frozen once by prepare-tool. Events, not agent reminders,
execute the existing gates. Actual fetch results supply readback evidence.
"""
import json
import fcntl
import copy
import os
import tempfile
from pathlib import Path
import re
import shlex
import sqlite3
import sys

import ledger


SESSIONS = Path.home() / '.local/share/agent-harness/tool-sessions'


def session_path(session):
    ledger.identifier(session)
    ledger.require(not any(p.is_symlink() for p in (SESSIONS, *SESSIONS.parents)), 'symlinked hook session store')
    return SESSIONS / (ledger.sha(session.encode()) + '.json')


def bind_session(project, task_id, session):
    """CLI-only binding: real Codex owner ID, including managed worktree projects."""
    path = session_path(session)
    SESSIONS.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path = path.with_suffix('.lock')
    ledger.require(not lock_path.is_symlink(), 'symlinked hook session lock')
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        entries = json.loads(ledger.read_file(str(path))) if path.exists() else []
        item = {'project': str(Path(project).resolve(strict=True)), 'task_id': ledger.identifier(task_id)}
        ledger.require(isinstance(entries, list), 'invalid hook session bindings')
        if item in entries:
            return
        ledger.require(len(entries) < 64, 'too many hook session bindings; inspect old projects')
        entries.append(item)
        descriptor, temporary = tempfile.mkstemp(dir=SESSIONS)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(ledger.canonical(entries).encode())
                stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)


def tool_name(name):
    if name in ('Bash', 'exec_command') or name.endswith('__exec_command'):
        return 'Bash'
    if name in ('Agent', 'spawn_agent') or name.endswith('__spawn_agent'):
        return 'spawn_agent'
    if name == 'wait_agent' or name.endswith('__wait_agent'):
        return 'wait_agent'
    return name


def arguments(name, value):
    ledger.require(isinstance(value, dict), 'tool arguments must be an object')
    if tool_name(name) == 'Bash':
        command = value.get('command', value.get('cmd'))
        ledger.require(isinstance(command, str), 'shell command missing')
        return {**{k: v for k, v in value.items() if k not in {'cmd', 'command'}}, 'command': command}
    return value


def protected(name, args):
    name = tool_name(name)
    if name == 'spawn_agent':
        return 'delegate'
    if name == 'Bash':
        # ponytail: direct git/gh writes only; indirect scripts need explicit
        # prepare-tool declarations, not a pretend universal shell sandbox.
        try:
            tokens = shlex.split(args.get('command', ''))
        except ValueError:
            return None  # Unsupported indirect shell syntax; declared calls still match exactly.
        for i, token in enumerate(tokens):
            program = Path(token).name
            tail = tokens[i + 1:]
            if program == 'git' and 'push' in tail:
                return 'write'
            if program == 'gh':
                if tail and tail[0] == 'api':
                    if any(x in tail for x in ('-f', '-F', '--field', '--raw-field', '--input')):
                        return 'write'
                    if any(x in tail for x in ('POST', 'PATCH', 'PUT', 'DELETE', 'graphql')) or any(
                            x.startswith(('--field=', '--raw-field=', '--input=', '-f', '-F'))
                            or x.upper() in ('-XPOST', '-XPATCH', '-XPUT', '-XDELETE', '--METHOD=POST', '--METHOD=PATCH', '--METHOD=PUT', '--METHOD=DELETE')
                            for x in tail):
                        return 'write'
                elif any(x in tail for x in ('create', 'edit', 'merge', 'comment', 'close', 'reopen', 'delete', 'upload')):
                    return 'write'
        return None
    if name.startswith('mcp__') and re.search(r'(?:^|_)(linear|github|notion)(?:_|$)', name):
        suffix = name.split('__')[-1]
        if (re.search(r'(?:^|_)(create|update|delete|append|add|edit|remove|archive|write|save|publish|merge|close|reopen)(?:_|$)', suffix)
                or re.search(r'\bmutation\b', ledger.canonical(args))):
            return 'write'
        if re.search(r'(?:^|_)(get|read|fetch|search|list|query|retrieve|find)(?:_|$)', suffix):
            return None
        return 'write'  # Unknown service operations need an explicit reviewed intent.
    return None


# Supported provider operations are deliberately typed. Unknown writes are denied.
def provider(name):
    ledger.require(name.startswith('mcp__codex_apps__'), 'unsupported provider namespace')
    return name.removeprefix('mcp__codex_apps__')


def notion_identity(value):
    from urllib.parse import urlsplit
    text = str(value)
    kind = 'collection' if text.startswith('collection://') else 'page'
    token = text.removeprefix('collection://') if kind == 'collection' else text
    if '://' in token:
        token = urlsplit(token).path.rstrip('/').split('/')[-1]
    return kind, token.replace('-', '').lower()


def shell_tokens(args):
    tokens = shlex.split(args['command'])
    ledger.require(tokens and not any(token in (';', '&&', '||', '|', '>', '<') for token in tokens), 'compound provider command unsupported')
    return tokens


def git_push(args, project):
    import shutil
    import subprocess
    tokens = shell_tokens(args)
    git = shutil.which('git')
    ledger.require(git and tokens[0] in ('git', git), 'unsupported git executable')
    ledger.require(args.get('workdir') or '-C' in tokens[:3], 'explicit Git working directory required')
    root = Path(args.get('workdir', project)).resolve(strict=True)
    position = 1
    if tokens[position:position + 1] == ['-C']:
        root = (root / tokens[position + 1]).resolve(strict=True)
        position += 2
    ledger.require(tokens[position:position + 1] == ['push'] and len(tokens) == position + 3, 'use explicit git push REMOTE SOURCE:BRANCH')
    remote, spec = tokens[position + 1:]
    ledger.require(':' in spec and not spec.startswith(('-', '+', ':')), 'explicit nonforce push refspec required')
    source, branch = spec.split(':', 1)
    ledger.require(source and branch and not branch.startswith('-'), 'invalid push refspec')
    def local(*command):
        return subprocess.check_output([git, '-C', str(root), *command], text=True, timeout=3).strip()
    url = remote if remote.startswith(('https://', 'git@')) else local('remote', 'get-url', '--push', remote)
    match = re.fullmatch(r'(?:https://github.com/|git@github.com:)([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?', url)
    ledger.require(match, 'unsupported GitHub push remote')
    branch = branch.removeprefix('refs/heads/')
    ledger.require(re.fullmatch(r'[A-Za-z0-9_./-]+', branch), 'unsupported push branch')
    sha = local('rev-parse', '--verify', source + '^{commit}')
    target = 'https://api.github.com/repos/' + match[1] + '/git/refs/heads/' + branch
    return target, {'commit': sha, 'ref': 'refs/heads/' + branch}


def request_payload(name, args, project):
    if tool_name(name) == 'Bash':
        target, payload = git_push(args, project)
        return 'github', 'push', target, payload
    endpoint = provider(name)
    if endpoint == 'notion_notion_update_page':
        command = args.get('command')
        base = {'page_id', 'command', 'allow_async'}
        if command == 'replace_content':
            ledger.require(set(args) <= base | {'new_str'}, 'unsupported Notion mutation fields')
            payload = {'body': ledger.plain_summary(args['new_str'].encode())}
        elif command == 'update_properties':
            ledger.require(set(args) <= base | {'properties'}, 'unsupported Notion mutation fields')
            payload = dict(args['properties'])
        else:
            raise ledger.LedgerError('use full Notion content or property replacement for automatic verification')
        return 'notion', 'update', args['page_id'], payload
    if endpoint == 'notion_notion_create_pages':
        ledger.require(set(args) <= {'parent', 'pages', 'allow_async'} and len(args['pages']) == 1, 'prepare one explicit Notion page at a time')
        page = args['pages'][0]
        ledger.require(set(page) <= {'properties', 'content'}, 'unsupported Notion page fields')
        parent = args['parent']
        ledger.require(set(parent) <= {'data_source_id', 'type'} and parent.get('data_source_id'), 'explicit Notion parent required')
        target = 'collection://' + parent['data_source_id'] if 'data_source_id' in parent else parent['page_id']
        return 'notion', 'create', target, {'body': ledger.plain_summary(page.get('content', '').encode()), **page['properties']}
    if endpoint == 'linear_save_issue':
        allowed = {'id', 'link_id', 'team', 'title', 'description', 'state', 'priority', 'dueDate'}
        ledger.require(set(args) <= allowed, 'unsupported Linear mutation fields; use complete supported values')
        ledger.require(not (args.get('id') and 'team' in args), 'Linear update cannot change an unreviewed team')
        target = args.get('id', args.get('team'))
        ledger.require(target, 'Linear issue ID or team required')
        payload = {k: v for k, v in args.items() if k not in {'id', 'link_id', 'team'}}
        return 'linear', 'update' if args.get('id') else 'create', target, payload
    repo = args.get('repository_full_name')
    ledger.require(isinstance(repo, str) and re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo), 'explicit GitHub repository required')
    if endpoint in ('github_create_issue', 'github_update_issue'):
        allowed = {'repository_full_name', 'issue_number', 'title', 'body', 'state', 'state_reason', 'labels', 'assignees', 'milestone'}
        ledger.require(set(args) <= allowed, 'unsupported GitHub issue fields')
        target = 'https://github.com/' + repo
        update = endpoint == 'github_update_issue'
        if update:
            target += '/issues/' + str(args['issue_number'])
        return 'github', 'update' if update else 'create', target, {k: v for k, v in args.items() if k not in {'repository_full_name', 'issue_number'}}
    if endpoint in ('github_create_file', 'github_update_file'):
        ledger.require(set(args) <= {'repository_full_name', 'branch', 'path', 'content', 'message', 'sha'} and args.get('branch'), 'explicit file branch and supported fields required')
        target = 'https://github.com/' + repo + '/blob/' + args['branch'] + '/' + args['path']
        return 'github', 'create' if endpoint == 'github_create_file' else 'update', target, {'content': args['content']}
    raise ledger.LedgerError('unsupported provider write adapter')


def validate_request(store, name, args, gate):
    service, operation, target, payload = request_payload(name, args, Path(store.path).parent.parent)
    destination = next((d for d in store.hooks()['policy']['destinations'] if d['id'] == gate['destination_id']), None)
    ledger.require(destination and destination['service'] == service and operation == gate['operation'], 'actual service or operation mismatch')
    ledger.require((notion_identity(target) == notion_identity(gate['target']) if service == 'notion' else target == gate['target']), 'actual write resource mismatch')
    if service == 'linear':
        ledger.require(args['link_id'] == gate['workspace'], 'actual Linear account mismatch')
    ledger.require(ledger.sha(ledger.canonical(payload).encode()) == gate['payload_sha256'], 'actual write content differs from planned payload')
    return service, payload


def read_request(write, write_args, name, args):
    service = write['service']
    if write['gate']['operation'] == 'create':
        created = write.get('created_resource') or (write_args.get('path') if service == 'github' and 'content' in write_args else None)
        ledger.require(created, 'created resource ID unavailable; reconcile actual write response before automatic readback')
        if service == 'notion':
            ledger.require(notion_identity(args.get('id')) == notion_identity(created), 'fetch the actual created page')
        elif service == 'linear':
            ledger.require(args.get('id') == created, 'fetch the actual created issue')
        elif 'content' not in write_args:
            ledger.require(args.get('issue_number') == created, 'fetch the actual created issue')
    if tool_name(name) == 'Bash':
        import shutil
        tokens = shell_tokens(args)
        gh = shutil.which('gh')
        ledger.require(service == 'github' and tool_name(write['tool_name']) == 'Bash' and gh
                       and len(tokens) == 3 and tokens[0] in ('gh', gh) and tokens[1] == 'api', 'only plain authoritative gh api GET is a shell readback')
        endpoint = write['gate']['target'].removeprefix('https://api.github.com/')
        expected = endpoint.replace('/git/refs/', '/git/ref/', 1)
        ledger.require(tokens[2] in (endpoint, expected), 'GitHub readback endpoint mismatch')
        return service
    endpoint = provider(name)
    if service == 'notion':
        ledger.require(endpoint == 'notion_fetch' and set(args) <= {'id', 'include_discussions', 'include_transcript'}, 'authoritative Notion fetch required')
        if write['gate']['operation'] == 'update':
            ledger.require(notion_identity(args['id']) == notion_identity(write['gate']['target']), 'readback resource differs from actual write')
    elif service == 'linear':
        ledger.require(endpoint == 'linear_get_issue' and args.get('link_id') == write_args['link_id'], 'authoritative Linear account fetch required')
        if write['gate']['operation'] == 'update':
            ledger.require(args['id'] == write_args['id'], 'readback issue differs from actual write')
    else:
        expected = 'github_fetch_file' if 'content' in write_args else 'github_fetch_issue'
        ledger.require(endpoint == expected and args.get('repository_full_name') == write_args['repository_full_name'], 'authoritative GitHub repository fetch required')
        if expected == 'github_fetch_file':
            ledger.require(args.get('path') == write_args['path'] and args.get('ref') == write_args['branch'] and not args.get('start_line') and not args.get('end_line') and args.get('encoding', 'utf-8') == 'utf-8', 'read complete file from the actual write branch')
        elif write['gate']['operation'] == 'update':
            ledger.require(args.get('issue_number') == write_args['issue_number'], 'readback issue differs from actual write')
    return service


def actual_payload(write, write_args, read_name, read_args, raw):
    ledger.require(not isinstance(raw, dict) or (not raw.get('isError') and raw.get('exit_code', 0) == 0), 'readback tool failed')
    value = response_value(raw)
    ledger.require(isinstance(value, dict) and not value.get('isError') and not value.get('error'), 'provider readback failed')
    service = write['service']
    expected = json.loads(ledger.read_file(write['gate']['payload_path']))
    read_request(write, write_args, read_name, read_args)
    if service == 'notion':
        ledger.require('notion_body' in value, 'authoritative Notion page envelope required')
        actual_target = value['notion_parent'] if write['gate']['operation'] == 'create' else value['notion_target']
        ledger.require(notion_identity(actual_target) == notion_identity(write['gate']['target']), 'readback resource identity mismatch')
        result = {key: value['notion_body'] if key == 'body' else value['notion_properties'][key] for key in expected}
    elif service == 'linear':
        if write['gate']['operation'] == 'update':
            ledger.require(read_args['id'] in (value.get('id'), value.get('identifier')), 'readback issue identity mismatch')
        else:
            team = value.get('team')
            ledger.require((team.get('id') if isinstance(team, dict) else team) == write['gate']['target'], 'created issue team mismatch')
        result = {key: value.get('status', value.get('state')) if key == 'state' else value[key] for key in expected}
        if isinstance(result.get('state'), dict):
            result['state'] = result['state']['name']
    elif tool_name(write['tool_name']) == 'Bash':
        ledger.require(value.get('url') == write['gate']['target'], 'remote GitHub ref identity mismatch')
        result = {'commit': value['object']['sha'], 'ref': value['ref']}
    elif 'content' in expected:
        ledger.require(value.get('path') == write_args['path'], 'remote file path mismatch')
        result = {'content': value['content']}
    else:
        url = value.get('html_url', value.get('url', ''))
        ledger.require(url.startswith('https://github.com/' + write_args['repository_full_name'] + '/issues/'), 'remote issue repository mismatch')
        if write['gate']['operation'] == 'update':
            ledger.require(url == write['gate']['target'], 'remote issue identity mismatch')
        result = {key: value[key] for key in expected}
    return ledger.canonical(result).encode()

def response_value(raw):
    value = raw
    if isinstance(raw, dict):
        if isinstance(raw.get('output'), str):
            try:
                value = json.loads(raw['output'])
            except ValueError:
                pass
        elif 'structuredContent' in raw:
            value = raw['structuredContent']
        else:
            content = raw.get('content')
            if isinstance(content, list) and len(content) == 1 and isinstance(content[0], dict) and content[0].get('type') == 'text':
                try:
                    value = json.loads(content[0]['text'])
                except (ValueError, KeyError):
                    pass
    if isinstance(value, dict) and isinstance(value.get('metadata'), dict) and value['metadata'].get('type') == 'page':
        ledger.require(not value.get('truncated') and not value.get('unknown_block_count'), 'Notion readback is incomplete')
        text = value.get('text', '')
        header, separator, body = text.partition('<content>\n')
        body, closing, _ = body.rpartition('\n</content>\n</page>')
        props = re.search(r'<properties>\n(.*?)\n</properties>', header, re.S)
        ledger.require(separator and closing and props, 'Notion page envelope missing')
        parent = re.search(r'<parent-data-source url="([^"]+)"', header)
        value = {**value, 'notion_body': ledger.plain_summary(body.encode()),
                 'notion_properties': json.loads(props[1]),
                 'notion_target': value['url'].split('?')[0],
                 'notion_parent': parent[1] if parent else None}
    return value


def prepare(store, d):
    hooks = store.hooks()
    call_id = ledger.identifier(d['call_id'])
    kind = ledger.choice(d['kind'], {'write', 'delegate', 'readback'})
    name = ledger.text(d['tool_name'], 'tool_name', 256)
    source = ledger.snapshot(d['input_path'])
    args = arguments(name, json.loads(ledger.read_file(d['input_path'])))
    gate = d['gate']
    ledger.require(isinstance(gate, dict), 'invalid tool gate')
    if kind in ('write', 'delegate'):
        action = 'before-write' if kind == 'write' else 'before-delegate'
        ledger.validate(action, {'task_id': store.task['task_id'], 'owner': store.task['owner'], **gate})
        ledger.require((kind == 'delegate') == (tool_name(name) == 'spawn_agent'), 'tool kind mismatch')
        # Reuse the actual validator on a private snapshot, without admission.
        # Invalid plans must not become immutable completion obligations.
        preview = copy.copy(store)
        preview.task = copy.deepcopy(store.task)
        getattr(preview, action.replace('-', '_'))(gate)
        identity = 'operation_id' if kind == 'write' else 'delegation_id'
        ledger.require(not any(key != call_id and call['kind'] == kind
                               and call['gate'][identity] == gate[identity]
                               and call['phase'] != 'superseded'
                               for key, call in hooks.get('tool_calls', {}).items()),
                       'reuse the existing planned operation or delegation')
        if kind == 'write':
            validate_request(store, name, args, gate)
            store.verified_work()
            ledger.require(ledger.snapshot(gate['payload_path'])['sha256'] == gate['payload_sha256'], 'write payload changed')
        else:
            ledger.require(isinstance(args.get('message'), str) or isinstance(args.get('items'), list), 'delegation needs a prompt')
    else:
        ledger.require(set(gate) == {'write_call_id'}, 'invalid readback gate')
        write = hooks.get('tool_calls', {}).get(gate['write_call_id'])
        ledger.require(write and write['kind'] == 'write', 'readback needs a planned write')
        ledger.require(protected(name, args) is None, 'readback must be a read operation')
        write_args = arguments(write['tool_name'], json.loads(ledger.read_file(write['input']['path'])))
        read_request(write, write_args, name, args)
    record = {'kind': kind, 'tool_name': tool_name(name), 'input': source,
              'input_sha256': ledger.sha(ledger.canonical(args).encode()), 'gate': gate, 'phase': 'prepared',
              'artifact_sha256': store.task['artifact']['sha256'] if kind == 'write' else None}
    if kind == 'write':
        record['service'] = validate_request(store, name, args, gate)[0]
    calls = hooks.setdefault('tool_calls', {})
    old = calls.get(call_id)
    if old:
        ledger.require(all(old[k] == v for k, v in record.items() if k != 'phase'), 'planned tool call is frozen')
    else:
        ledger.require(not any(x['tool_name'] == record['tool_name'] and x['input_sha256'] == record['input_sha256']
                               for x in calls.values() if x['phase'] != 'superseded'), 'reuse the existing planned tool call')
        calls[call_id] = record
    store.task['completion_requested'] = False


def evidence(store, call_id, event_id, label, content):
    db = Path(store.path)
    directory = db.parent / 'tool-evidence'
    ledger.require(not directory.is_symlink(), 'tool evidence directory must not be a symlink')
    directory.mkdir(mode=0o700, exist_ok=True)
    token = ledger.sha(ledger.canonical([store.task['task_id'], call_id, event_id, label]).encode())
    path = directory / (token + '.json')
    try:
        with path.open('xb') as stream:
            stream.write(content)
    except FileExistsError:
        ledger.require(ledger.read_file(str(path)) == content, 'event evidence cannot be replaced')
    return str(path)


def output(event, message, deny=False, updated=None):
    if event == 'PreToolUse':
        data = {'hookEventName': event, 'permissionDecision': 'deny' if deny else 'allow',
                'permissionDecisionReason': message}
        if updated is not None:
            data['updatedInput'] = updated
        return {'hookSpecificOutput': data}
    if deny and event == 'PostToolUse':
        return {'decision': 'block', 'reason': message}
    return {'hookSpecificOutput': {'hookEventName': event, 'additionalContext': message}}


def delegated_input(args, contract):
    updated = dict(args)
    text = '\n\nHARNESS_CONTRACT\n' + ledger.canonical(contract)
    if isinstance(updated.get('message'), str):
        updated['message'] += text
    else:
        updated['items'] = [*updated['items'], {'type': 'text', 'text': text}]
    return updated


def event(store, d):
    e = d['event']
    ledger.require(e.get('session_id') == store.task['owner'], 'hook session does not own task')
    name = e.get('hook_event_name')
    calls = store.task.get('runtime_hooks', {}).get('tool_calls', {})
    if name == 'PostToolUse' and tool_name(e.get('tool_name', '')) == 'wait_agent':
        response = response_value(e.get('tool_response'))
        ledger.require(isinstance(response, dict), 'invalid wait-agent result')
        statuses = response.get('status', {})
        ledger.require(isinstance(statuses, dict), 'invalid wait-agent statuses')
        for call_id, item in calls.items():
            final = statuses.get(item.get('agent_id'))
            if item['kind'] != 'delegate' or item['phase'] == 'finished' or not isinstance(final, dict):
                continue
            message = final.get('completed') or final.get('errored')
            if not isinstance(message, str) or not message.strip():
                continue
            path = evidence(store, call_id, e['tool_use_id'], 'agent-result', ledger.canonical(final).encode())
            store.after_delegate({'delegation_id': item['gate']['delegation_id'], 'agent_id': item['agent_id'],
                                  'outcome': 'finished' if 'completed' in final else 'blocked', 'evidence_path': path})
            item['phase'] = 'finished' if 'completed' in final else 'blocked'
        return {}
    args = arguments(e.get('tool_name', ''), e.get('tool_input') or {})
    digest = ledger.sha(ledger.canonical(args).encode())
    matching = [(key, item) for key, item in calls.items() if item['phase'] != 'superseded' and item['tool_name'] == tool_name(e.get('tool_name', ''))
                and digest in (item['input_sha256'], item.get('effective_input_sha256'))]
    ledger.require(len(matching) <= 1, 'ambiguous planned tool call')
    if not matching:
        ledger.require(name != 'PreToolUse' or protected(e.get('tool_name', ''), args) is None,
                       'No planned Harness call. Use prepare-tool with the exact tool input and authorized gate.')
        return {}
    call_id, item = matching[0]
    ledger.require(store.work_current(item['input']), 'planned tool input changed')
    event_id = ledger.text(e.get('tool_use_id'), 'tool_use_id', 256)
    if name == 'PreToolUse':
        if item.get('event_id') == event_id and item['phase'] == 'admitted':
            updated = delegated_input(args, store.hooks()['delegations'][item['gate']['delegation_id']]['contract']) if item['kind'] == 'delegate' and digest == item['input_sha256'] else None
            return output(name, 'Harness gate already admitted this event.', updated=updated)
        retryable = item['kind'] == 'write' and store.hooks()['writes'].get(item['gate']['operation_id'], {}).get('outcome') == 'absent'
        ledger.require(item['phase'] != 'admitted', 'concurrent tool admission denied')
        ledger.require(item['phase'] == 'prepared' or item['kind'] == 'readback' or retryable, 'Call already dispatched; reconcile before retrying')
        updated = None
        if item['kind'] == 'write':
            ledger.require(store.task['artifact'] and item['artifact_sha256'] == store.task['artifact']['sha256'], 'planned write version changed; prepare a new call')
            validate_request(store, item['tool_name'], args, item['gate'])
            store.before_write(item['gate'])
            ledger.require(store.hook_result['should_write'], 'Write already verified; skip duplicate')
            item['attempt'] = store.hook_result['attempt']
        elif item['kind'] == 'delegate':
            store.before_delegate(item['gate'])
            updated = delegated_input(args, store.hook_result['contract'])
            item['effective_input_sha256'] = ledger.sha(ledger.canonical(updated).encode())
        else:
            write = calls[item['gate']['write_call_id']]
            ledger.require(write.get('attempt'), 'Write has not passed its pre-tool gate')
        item.update(phase='admitted', event_id=event_id)
        store.task['completion_requested'] = False
        return output(name, 'Harness ' + item['kind'] + ' gate passed.', updated=updated)
    if name != 'PostToolUse':
        return {}
    ledger.require(item.get('event_id') == event_id, 'Post-tool event has no matching pre-tool admission')
    raw = e.get('tool_response')
    raw_bytes = ledger.canonical(raw).encode()
    if item['phase'] == 'observed':
        ledger.require(item.get('response_sha256') == ledger.sha(raw_bytes), 'post-tool event changed')
        return {}
    path = evidence(store, call_id, event_id, 'response', raw_bytes)
    if item['kind'] == 'write':
        gate = item['gate']
        if gate['operation'] == 'create' and isinstance(raw, dict) and not raw.get('isError'):
            value = response_value(raw)
            if isinstance(value, dict):
                if item['service'] == 'notion':
                    pages = value.get('pages', [])
                    page = pages[0] if isinstance(pages, list) and len(pages) == 1 else value
                    if isinstance(page, dict):
                        item['created_resource'] = page.get('id') or page.get('url')
                elif item['service'] == 'linear':
                    item['created_resource'] = value.get('id')
                else:
                    item['created_resource'] = value.get('number')
        store.after_write({'operation_id': gate['operation_id'], 'attempt': item['attempt'],
                           'workspace': gate['workspace'], 'target': gate['target'],
                           'outcome': 'uncertain', 'evidence_path': path})
        result = output(name, 'Write response recorded; fetch the actual resource using the prepared readback call before completion or retry.')
    elif item['kind'] == 'delegate':
        value = response_value(raw)
        agent = value.get('agent_id') if isinstance(value, dict) else None
        ledger.require(agent, 'Agent creation was not confirmed; reconcile before another dispatch')
        item['agent_id'] = ledger.identifier(agent)
        result = output(name, 'Agent ID recorded. Confirm its final result through wait_agent; completion remains pending.')
    else:
        write = calls[item['gate']['write_call_id']]
        gate = write['gate']
        existing_write = store.hooks()['writes'][gate['operation_id']]
        try:
            write_args = arguments(write['tool_name'], json.loads(ledger.read_file(write['input']['path'])))
            content = actual_payload(write, write_args, item['tool_name'], args, raw)
            ledger.require(ledger.sha(content) == gate['payload_sha256'], 'write readback mismatch')
        except (ledger.LedgerError, KeyError, TypeError, ValueError) as exc:
            if existing_write['outcome'] == 'verified':
                store.task['blocker'] = {'kind': 'requirements', 'reference': 'verified-resource-readback-drift'}
                store.task['completion_requested'] = False
            else:
                store.after_write({'operation_id': gate['operation_id'], 'attempt': write['attempt'],
                                   'workspace': gate['workspace'], 'target': gate['target'],
                                   'outcome': 'conflict', 'evidence_path': path})
            result = output(name, str(exc) + '; completion and write retry remain blocked.', deny=True)
        else:
            readback = evidence(store, call_id, event_id, 'readback', content)
            if existing_write['outcome'] != 'verified':
                store.after_write({'operation_id': gate['operation_id'], 'attempt': write['attempt'],
                                   'workspace': gate['workspace'], 'target': gate['target'],
                                   'outcome': 'verified', 'evidence_path': path, 'readback_path': readback})
            result = output(name, 'Actual readback matches the reviewed payload; write verified.')
    item.update(phase='observed', response_sha256=ledger.sha(raw_bytes))
    return result


def project_for(e):
    cwd = e.get('cwd')
    ledger.require(isinstance(cwd, str) and Path(cwd).is_absolute(), 'hook project missing')
    directory = Path(cwd).resolve(strict=True)
    return next((p for p in (directory, *directory.parents) if (p / '.harness/tasks.sqlite').is_file()), None)


def handle(e):
    import run
    run.verify_install()
    name = e.get('hook_event_name')
    if name not in ('PreToolUse', 'PostToolUse', 'SubagentStop', 'Stop'):
        return {}
    local = project_for(e)
    session = e.get('session_id')
    ledger.require(isinstance(session, str), 'hook session missing')
    path = session_path(session)
    bindings = json.loads(ledger.read_file(str(path))) if path.exists() else []
    ledger.require(isinstance(bindings, list) and len(bindings) <= 64, 'invalid hook session bindings')
    projects = {Path(item['project']) for item in bindings}
    if local:
        projects.add(local)
    tasks = []
    from contextlib import closing
    for project in projects:
        db = project / '.harness/tasks.sqlite'
        if not db.exists():
            continue
        ledger.require(not any(part.is_symlink() for part in (db, *db.parents)), 'symlinked task ledger')
        with closing(sqlite3.connect(db.as_uri() + '?mode=ro', uri=True, timeout=1)) as connection:
            candidates = [json.loads(row[0]) for row in connection.execute('SELECT state FROM tasks')]
        tasks.extend({**t, '_database': str(db)} for t in candidates
                     if t.get('owner') == session and t.get('runtime_hooks_required')
                     and not t.get('paused') and not (t.get('completion_requested') and t.get('stage') == 'done'))
    if not tasks:
        return {}
    if name in ('Stop', 'SubagentStop'):
        if name == 'SubagentStop':
            if any(c.get('agent_id') == e.get('agent_id') for t in tasks for c in t.get('runtime_hooks', {}).get('tool_calls', {}).values()):
                return output(name, 'Subagent returned. Use wait_agent to confirm the final result before recording completion; this lifecycle event may still be continued.')
            return {}
        pending = []
        for t in tasks:
            state = ledger.Ledger(t['_database']).dispatch('status', {'task_id': t['task_id']})
            if state['stage'] not in ('done', 'blocked', 'paused'):
                pending.append({'task_id': state['task_id'], 'stage': state['stage'], 'next_action': state['next_action']})
        if not pending:
            return {}
        reason = 'Harness completion gate: ' + ledger.canonical(pending) + '. Resume these tasks, verify writes and independent review, or record an actual blocker; do not claim Done.'
        return {'systemMessage': reason} if e.get('stop_hook_active') else {'decision': 'block', 'reason': reason}
    args = arguments(e.get('tool_name', ''), e.get('tool_input') or {})
    fingerprint = ledger.sha(ledger.canonical(args).encode())
    selected = [t for t in tasks if any(c['phase'] != 'superseded' and c['tool_name'] == tool_name(e.get('tool_name', '')) and fingerprint in
                (c['input_sha256'], c.get('effective_input_sha256')) for c in t.get('runtime_hooks', {}).get('tool_calls', {}).values())]
    if name == 'PostToolUse' and tool_name(e.get('tool_name', '')) == 'wait_agent':
        for t in tasks:
            ledger.Ledger(t['_database']).dispatch('tool-event', {'task_id': t['task_id'], 'owner': t['owner'], 'event': e})
        return {}
    if not selected:
        if name == 'PreToolUse' and protected(e.get('tool_name', ''), args):
            return output(name, 'Tracked Harness action has no prepared call. Freeze its exact input and gate with prepare-tool first.', deny=True)
        return {}
    ledger.require(len(selected) == 1, 'ambiguous task for tool call')
    t = selected[0]
    return ledger.Ledger(t['_database']).dispatch('tool-event', {'task_id': t['task_id'], 'owner': t['owner'], 'event': e})['hook']


def main():
    e = {}
    try:
        raw = sys.stdin.read(2 * 1024 * 1024 + 1)
        ledger.require(len(raw) <= 2 * 1024 * 1024, 'hook event too large')
        e = json.loads(raw)
        ledger.require(isinstance(e, dict), 'expected hook event object')
        result = handle(e)
    except (ledger.LedgerError, OSError, ValueError, TypeError, KeyError, sqlite3.Error) as exc:
        message = 'Harness automatic gate unavailable; do not treat this call as verified. ' + (str(exc) if isinstance(exc, ledger.LedgerError) else 'Inspect the task and installation.')
        name = e.get('hook_event_name') if isinstance(e, dict) else None
        if name == 'PreToolUse':
            result = output(name, message, deny=True)
        elif name == 'Stop':
            result = {'systemMessage': message} if e.get('stop_hook_active') else {'decision': 'block', 'reason': message}
        elif name == 'PostToolUse':
            result = output(name, message, deny=True)
        elif name == 'SubagentStop':
            result = {'systemMessage': message}
        else:
            print(message, file=sys.stderr)
            raise SystemExit(2)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
