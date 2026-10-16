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
    for service in ('notion', 'linear', 'github'):
        prefix = 'mcp__codex_apps__' + service + '__'
        if name.startswith(prefix):
            endpoint = name[len(prefix):]
            if service == 'notion' and endpoint in ('create_pages', 'update_page', 'create_file_upload'):
                endpoint = 'notion_' + endpoint
            return 'mcp__codex_apps__' + service + '_' + endpoint
    if name in ('Bash', 'exec_command') or name.endswith('__exec_command'):
        return 'Bash'
    if name in ('Agent', 'spawn_agent') or name.endswith('__spawn_agent'):
        return 'spawn_agent'
    if name in ('wait_agent', 'multi_agent_v1wait_agent') or name.endswith('__wait_agent'):
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
        # Generic query/GraphQL operations can mutate. Only typed read APIs pass;
        # search text and SQL in query_data_sources never decide permission.
        typed_query = suffix.endswith(('query_data_sources', 'query_multiple_data_sources'))
        if (re.search(r'(?:^|_)(create|update|delete|append|add|edit|remove|archive|write|save|publish|merge|close|reopen|move|duplicate|restore|convert)(?:_|$)', suffix)
                or (not typed_query and re.search(r'(?:^|_)(query|graphql)(?:_|$)', suffix))):
            return 'write'
        if re.search(r'(?:^|_)(get|read|fetch|search|list|query|retrieve|find)(?:_|$)', suffix):
            return None
        return 'write'  # Unknown service operations need an explicit reviewed intent.
    return None


# Supported provider operations are deliberately typed. Unknown writes are denied.
def provider(name):
    name = tool_name(name)
    for prefix in ('mcp__linear__', 'mcp__linear_endix__'):
        if name.startswith(prefix):
            return 'linear_' + name[len(prefix):]
    ledger.require(name.startswith('mcp__codex_apps__'), 'unsupported provider namespace')
    return name.removeprefix('mcp__codex_apps__')


def linear_connector(name):
    return next((prefix for prefix in ('mcp__linear__', 'mcp__linear_endix__')
                 if name.startswith(prefix)), None)


def linear_connection(store, name, gate):
    prefix = linear_connector(name)
    observed = store.hooks().get('connections', {}).get(prefix)
    ledger.require(observed and observed['workspace'] == gate['workspace']
                   and store.work_current(observed['evidence']),
                   'fetch the actual Linear workspace through this connector before preparing a write')
    destination = next(d for d in store.hooks()['policy']['destinations'] if d['id'] == gate['destination_id'])
    ledger.require(destination['output_owner'] == ('personal' if prefix == 'mcp__linear__' else 'endix'),
                   'Linear connector ownership differs from authorized destination')
    return observed


def _unescape_linear_json_array_delimiters(body):
    """Normalize only Linear-escaped, strict JSON object-member array delimiters."""
    literal_code = re.compile(
        r'(?ms)^ {0,3}(?:(' + r'\x60' + r'{3,})|(~{3,}))[^\n]*\n.*?'
        r'(?:^ {0,3}(?:\1' + r'\x60' + r'*|\2~*)[ \t\r]*$|\Z)'
        r'|(?m:^ {0,3}>[^\n]*$)'
        r'|(?m:^(?: {4}|\t)[^\n]*$)'
        r'|(?<!' + r'\x60' + r')(' + r'\x60' + r'+)(?!' + r'\x60' + r').*?(?<!' + r'\x60' + r')\3(?!' + r'\x60' + r')')
    array_member = re.compile(
        r'(?ms)(?P<prefix>^[ \t]*"(?:[^"\\]|\\.)+"[ \t]*:[ \t]*)'
        r'(?P<opening>\\\[)(?P<items>.*?)'
        r'(?P<close_indent>(?:^[ \t]*)?)(?P<closing>\\\])'
        r'(?P<tail>[ \t]*(?:,)?[ \t]*(?=\r?$))')
    code_spans = [(match.start(), match.end()) for match in literal_code.finditer(body)]

    def overlaps_code(start, end):
        return any(left < end and start < right for left, right in code_spans)

    def reject_constant(value):
        raise ValueError("non-JSON constant: " + value)

    def normalize(match):
        if (overlaps_code(match.start("opening"), match.end("opening"))
                or overlaps_code(match.start("closing"), match.end("closing"))):
            return match.group(0)
        try:
            json.loads("[" + match.group("items") + "]", parse_constant=reject_constant)
        except (TypeError, ValueError):
            return match.group(0)
        return (match.group("prefix") + "[" + match.group("items")
                + match.group("close_indent") + "]" + match.group("tail"))

    return array_member.sub(normalize, body)


def linear_description_matches(expected, actual, aliases, workspace_url=None, expected_links=None):
    """Compare content after Linear renders issue and PR mentions."""
    if not isinstance(expected, str) or not isinstance(actual, str):
        return False
    # ponytail: list-contained fences stay literal; avoid a Markdown parser dependency.
    nested_fence = r'(?m)^ {0,3}(?:[-+*]|\d+[.)])\s+(?:`{3,}|~{3,})'
    if re.search(nested_fence, expected + '\n' + actual):
        return expected == actual
    expected = _unescape_linear_json_array_delimiters(expected)
    actual = _unescape_linear_json_array_delimiters(actual)
    code = re.compile(r'(?ms)^ {0,3}(?:(`{3,})|(~{3,}))[^\n]*\n.*?'
                      r'(?:^ {0,3}(?:\1`*|\2~*)[ \t\r]*$|\Z)'
                      r'|(?m:^ {0,3}>[^\n]*$)|(?m:^(?: {4}|\t)[^\n]*$)'
                      r'|(?<!`)(`+)(?!`).*?(?<!`)\3(?!`)'
                      r'|(?<![\\$])\$\$.*?(?<!\\)\$\$(?!\$)'
                      r'|(?<![\\$])\$(?![\s$])[^$\n]*?(?<![\s\\])\$(?!\$)'
                      r'|\\\(.*?\\\)'
                      r'|(?m:^ {0,3}\\\[.*?\\\])'
                      r'|\\\[(?!(?:1-\w+,1\+\w+|token(?:/share)?)\\\]).*?\\\]')
    if [m[0] for m in code.finditer(expected)] != [m[0] for m in code.finditer(actual)]:
        return False
    protect_code = lambda body: code.sub(lambda m: '\x19' + m[0].encode().hex() + '\x18', body)
    strong_splits = []
    # Linear splits an observed strong span around unchanged single-line inline code.
    # shortcut: nested emphasis and code-only/quoted/multiline spans stay literal.
    for span in re.finditer(r'(?<![\\*])\*\*([^*\n]+)\*\*(?!\*)', protect_code(expected)):
        parts = re.split(r'(\x19[0-9a-f]+\x18)', span[1])
        if (len(parts) < 3 or not parts[0].strip() or not parts[-1].strip()
                or any(re.search(r'[_\\~\[\]<>]', p) for p in parts[::2])
                or not all(re.fullmatch(r'`[^`\r\n]+`', bytes.fromhex(p[1:-1]).decode())
                           for p in parts[1::2])):
            continue
        rendered = []
        for index, part in enumerate(parts):
            if index % 2:
                rendered.append(part)
            else:
                plain = part.strip(' \t')
                left = part[:len(part)-len(part.lstrip(' \t'))]
                right = part[len(part.rstrip(' \t')):]
                rendered.append(left + '**' + plain + '**' + right if plain else part)
        strong_splits.append((span[0], ''.join(rendered)))
    from urllib.parse import urlsplit, unquote
    known = {identifier: uuid for uuid, identifier in aliases.items()}
    workspace = urlsplit(workspace_url).path.strip('/') if workspace_url else None
    tag = re.compile(r'<issue id="([a-f0-9-]+)" href="(https://linear\.app/[^\"]+)">([A-Z]+-\d+)</issue>')
    pr_tag = re.compile(r'<pull-request id="([a-f0-9-]+)" href="(https://linear\.app/[^\"]+)">([^<]*)</pull-request>')
    existing_prs = {match[1]: match[2] for match in pr_tag.finditer(expected)}
    unexpected_prs = set()
    mismatched_url_labels = []
    github_prs = set()
    for link in expected_links or []:
        parsed = urlsplit(link.get('url', ''))
        parts = parsed.path.strip('/').split('/')
        if parsed.scheme == 'https' and parsed.netloc == 'github.com' and len(parts) == 4 and parts[2] == 'pull':
            github_prs.add((parts[0].lower(), parts[1].lower(), parts[3]))

    def render_pr(match):
        uuid, url, label = match.groups()
        path = urlsplit(url).path.split('/')
        if uuid in existing_prs and url != existing_prs[uuid]:
            unexpected_prs.add(uuid)
            return match.group(0)
        if not (workspace and len(path) >= 4 and path[1:3] == [workspace, 'review'] and path[3]):
            if uuid not in existing_prs:
                unexpected_prs.add(uuid)
            return match.group(0)
        pr = re.fullmatch(r'([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)#(\d+)', label)
        if (uuid not in existing_prs and pr and (pr[1].lower(), pr[2].lower(), pr[3]) in github_prs
                and re.search(r'(?<![A-Za-z0-9])PR #' + pr[3] + r'(?!\d)', expected)):
            return ('#' if match.string[max(0, match.start() - 3):match.start()] == 'PR ' else 'PR #') + pr[3]
        if uuid not in existing_prs:
            unexpected_prs.add(uuid)
        return '\x1d' + uuid + ':' + workspace + '\x1c'

    def normalize(body):
        body = protect_code(body)
        for original, rendered in strong_splits:
            body = body.replace(original, rendered)
        # ponytail: normalize simple list markers only; code/nested blocks fail closed.
        if not re.search(r'(?m)^\s*(?:```|~~~)|^(?: {4}| {0,3}\t)', body):
            body = re.sub(r'(?m)^[-+] (?=\S)(?![-+* \t]+\r?$)', '* ', body)
        # Linear discards table alignment and escapes literal units/ranges.
        body = re.sub(r'(?m)^\|[ \t]*:?-{2,}:?[ \t]*(?:\|[ \t]*:?-{2,}:?[ \t]*)+\|[ \t]*$',
                      lambda m: '|' + '|'.join('--' for _ in m[0].strip().split('|')[1:-1]) + '|', body)
        body = re.sub(r'\\\[(token(?:/share)?)\\\]', r'[\1]', body)
        body = re.sub(r'(?<=\d)\\~(?=\d)', '~', body)
        # Linear escapes literal multiplication and guard ranges; URLs stay exact.
        body = re.sub(r'https?://[^\s<>]+|(?<=[\w)])[ \t]*\\\*(?=[ \t]*[\w(])'
                      r'|(?<!\\)\\\[(1-\w+,1\+\w+)\\\](?![\[(])',
                      lambda m: m[0] if m[0].startswith(('http://', 'https://'))
                      else m[0].replace('\\*', '*').replace('\\[', '[').replace('\\]', ']'), body)
        body = re.sub(r'(\[[^\[\]\n]+\]\()<([^<>\s]+)>\)', r'\1\2)', body)
        def unicode_path(match):
            decoded = unquote(match[0], errors='strict')
            return decoded if all(ord(c) > 127 for c in decoded) else match[0]
        # Decode only valid non-ASCII path bytes; reserved ASCII stays literal.
        def url_path(match):
            try:
                return re.sub(r'(?:%[0-9A-Fa-f]{2})+', unicode_path, match[0])
            except UnicodeDecodeError:
                return match[0]
        body = re.sub(r'https?://[^\s<>"()]+', url_path, body)
        # Linear turns bare URLs into self-labelled links; code is protected above.
        def self_link(match):
            label, target = match.groups()
            if label != target:
                mismatched_url_labels.append(match.group(0))
                return match.group(0)
            return target
        body = re.sub(r'\[(https?://[^\[\]\s]+)\]\((https?://[^()\s]+)\)', self_link, body)
        body = re.sub(r'<(https?://[^<>\s]+)>', r'\1', body)
        body = re.sub(r'\[draw\.io\]\(http://draw\.io\)', 'draw.io', body)
        # Linear auto-links an unquoted dotted equality to http:// plus its exact label.
        body = re.sub(r'\[([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+==[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)\]\(http://\1\)', r'\1', body)
        def pr_link(match):
            number, owner, repo, target = match.groups()
            return ('PR #' + number if number == target
                    and (owner.lower(), repo.lower(), target) in github_prs
                    else match.group(0))

        body = re.sub(r'\[PR #(\d+)\]\(https://github\.com/'
                      r'([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/pull/(\d+)\)', pr_link, body)
        def replace(match):
            uuid, url, identifier = match.groups()
            path = urlsplit(url).path.split('/')
            if (len(path) < 4 or not path[1] or path[2:4] != ['issue', identifier]
                    or (uuid in aliases and aliases[uuid] != identifier)
                    or (identifier in known and known[identifier] != uuid)):
                return match.group(0)
            return '\x1f' + uuid + ':' + identifier.encode().hex() + ':' + path[1].encode().hex() + '\x1e'

        body = pr_tag.sub(render_pr, tag.sub(replace, body))
        if workspace:
            for identifier, uuid in known.items():
                body = re.sub(r'(?<![A-Za-z0-9-])' + re.escape(identifier) + r'(?![A-Za-z0-9-])',
                              '\x1f' + uuid + ':' + identifier.encode().hex() + ':' + workspace.encode().hex() + '\x1e', body)
        return body

    expected_lines = [re.sub(r'\s+', ' ', line).strip() for line in normalize(expected).split('\n') if line.strip()]
    actual_text = re.sub(r'\s+', ' ', normalize(actual)).strip()
    repo_pr = r'(?<![\w./])([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)#(\d+)\b'
    github_url_pr = r'https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/pull/(\d+)(?!\d)'
    allowed_repo_prs = github_prs | {(owner.lower(), repo.lower(), number)
                                    for owner, repo, number in re.findall(repo_pr, expected)}
    allowed_repo_prs.update((owner.lower(), repo.lower(), number)
                            for owner, repo, number in re.findall(github_url_pr, expected, re.I))
    actual_repo_prs = {(owner.lower(), repo.lower(), number)
                       for owner, repo, number in re.findall(repo_pr, actual_text)}
    actual_repo_prs.update((owner.lower(), repo.lower(), number)
                           for owner, repo, number in re.findall(github_url_pr, actual_text, re.I))
    allowed_prs = {number for _, _, number in allowed_repo_prs}
    allowed_prs.update(re.findall(r'(?<!\w)PR\s*#(\d+)\b', expected))
    actual_prs = set(re.findall(r'(?<!\w)PR\s*#(\d+)\b', actual_text))
    if mismatched_url_labels or unexpected_prs or not actual_prs <= allowed_prs or not actual_repo_prs <= allowed_repo_prs:
        return False
    if not expected_lines:
        return not actual_text
    return actual_text == ' '.join(expected_lines)


def notion_identity(value):
    from urllib.parse import urlsplit
    text = str(value)
    kind = 'collection' if text.startswith('collection://') else 'page'
    token = text.removeprefix('collection://') if kind == 'collection' else text
    if '://' in token:
        token = urlsplit(token).path.rstrip('/').split('/')[-1]
    token = token.replace('-', '').lower()
    match = re.search(r'([a-f0-9]{32})$', token)
    return kind, match[1] if match else token


def shell_tokens(args):
    ledger.require(not re.search(r'[$`\r\n]', args['command']), 'shell expansion unsupported for provider command')
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
    checkout = str(Path(local('rev-parse', '--show-toplevel')).resolve(strict=True))
    target = 'https://api.github.com/repos/' + match[1] + '/git/refs/heads/' + branch
    return target, {'commit': sha, 'ref': 'refs/heads/' + branch}, checkout


def matches_call(task, call, name, args, fingerprint, hook_event, event_id):
    import subprocess
    if hook_event == 'PreToolUse':
        if call['phase'] == 'observed' and call['kind'] == 'readback':
            return False
        if call['phase'] == 'admitted' and call.get('event_id') != event_id:
            return False
    elif hook_event == 'PostToolUse':
        if (call['phase'] not in {'admitted', 'observed'}
                or call.get('event_id') != event_id):
            return False
    if call['phase'] in {'superseded', 'retired'} or call['tool_name'] != tool_name(name):
        return False
    if tool_name(name) == 'Bash' and call['kind'] == 'write':
        try:
            planned = arguments(call['tool_name'], json.loads(ledger.read_file(call['input']['path'])))
            project = Path(task['_database']).parent.parent
            target, payload, checkout = git_push(args, project)
            _, _, planned_checkout = git_push(planned, project)
            frozen = json.loads(ledger.read_file(call['gate']['payload_path']))
            return target == call['gate']['target'] and payload == frozen and checkout == planned_checkout
        except (ledger.LedgerError, OSError, ValueError, KeyError, subprocess.SubprocessError):
            return False
    if fingerprint in (call['input_sha256'], call.get('effective_input_sha256')):
        return True
    if tool_name(name) != 'Bash':
        return False
    try:
        planned = arguments(call['tool_name'], json.loads(ledger.read_file(call['input']['path'])))
        if call['kind'] == 'readback':
            return protected(name, args) is None and shell_tokens(args) == shell_tokens(planned)
        return False
    except (ledger.LedgerError, OSError, ValueError, KeyError, subprocess.SubprocessError):
        return False


def request_payload(name, args, project):
    if tool_name(name) == 'Bash':
        target, payload, _ = git_push(args, project)
        return 'github', 'push', target, payload
    endpoint = provider(name)
    # ponytail: native readback covers pages only; add provider-specific adapters
    # before admitting other operations, never substitute the gate's own target.
    if endpoint.startswith('notion_'):
        ledger.require(endpoint in ('notion_notion_create_pages', 'notion_notion_update_page'),
                       'unsupported Notion operation: no native provider readback adapter; write blocked')
    if endpoint == 'notion_notion_update_page':
        command = args.get('command')
        base = {'page_id', 'command', 'allow_async'}
        ledger.require(command in ('replace_content', 'update_properties', 'update_content'),
                       'unsupported Notion page command: no native provider readback adapter; write blocked')
        ledger.require(set(args) <= base | {'new_str', 'properties', 'content_updates'},
                       'unsupported Notion mutation fields: no native provider readback adapter; write blocked')
        if command == 'replace_content':
            ledger.require(set(args) <= base | {'new_str'}, 'unsupported Notion mutation fields')
            payload = {'body': ledger.plain_summary(args['new_str'].encode())}
        elif command == 'update_properties':
            ledger.require(set(args) <= base | {'properties'}, 'unsupported Notion mutation fields')
            payload = dict(args['properties'])
        elif command == 'update_content':
            updates = args.get('content_updates')
            ledger.require(set(args) <= base | {'content_updates'} and isinstance(updates, list) and updates
                           and all(isinstance(item, dict) and set(item) == {'old_str', 'new_str'}
                                   and isinstance(item['old_str'], str) and item['old_str']
                                   and isinstance(item['new_str'], str) and item['new_str'] for item in updates),
                           'exact nonempty Notion sentence replacements required')
            payload = {'content_updates': updates}
        return 'notion', 'update', args['page_id'], payload
    if endpoint == 'notion_notion_create_pages':
        ledger.require(set(args) <= {'parent', 'pages', 'allow_async'} and len(args['pages']) == 1, 'prepare one explicit Notion page at a time')
        page = args['pages'][0]
        ledger.require(set(page) <= {'properties', 'content'}, 'unsupported Notion page fields')
        parent = args['parent']
        ledger.require(isinstance(parent, dict) and set(parent) <= {'data_source_id', 'page_id', 'type'}
                       and bool(parent.get('data_source_id')) != bool(parent.get('page_id')), 'explicit Notion parent required')
        ledger.require(not parent.get('type') or parent['type'] == ('data_source_id' if parent.get('data_source_id') else 'page_id'), 'Notion parent type mismatch')
        target = 'collection://' + parent['data_source_id'] if 'data_source_id' in parent else parent['page_id']
        return 'notion', 'create', target, {'body': ledger.plain_summary(page.get('content', '').encode()), **page['properties']}
    if endpoint == 'linear_save_document':
        ledger.require(linear_connector(name), 'native Linear document connector required')
        ledger.require(set(args) <= {'id', 'title', 'content', 'issue', 'project', 'initiative', 'cycle', 'team'},
                       'use full supported Linear document values, not patches')
        parents = [key for key in ('issue', 'project', 'initiative', 'cycle', 'team') if key in args]
        ledger.require(len(parents) <= 1 and (args.get('id') or len(parents) == 1 and args.get('title')),
                       'Linear document creation needs a title and exactly one parent')
        target = args.get('id') or args[parents[0]]
        return 'linear', 'update' if args.get('id') else 'create', target, {k: v for k, v in args.items() if k != 'id'}
    if endpoint == 'linear_save_issue':
        allowed = {'id', 'link_id', 'team', 'title', 'description', 'state', 'priority', 'dueDate',
                   'project', 'parentId', 'blockedBy', 'blocks', 'relatedTo', 'links', 'labels'}
        ledger.require(set(args) <= allowed, 'unsupported Linear mutation fields; use complete supported values')
        for key in ('blockedBy', 'blocks', 'relatedTo', 'labels'):
            if key in args:
                ledger.strings(args[key], key, empty=True)
        if 'links' in args:
            ledger.require(isinstance(args['links'], list) and all(isinstance(link, dict)
                           and set(link) == {'title', 'url'} and all(isinstance(v, str) and v for v in link.values())
                           for link in args['links']), 'Linear links require title and URL')
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
    if endpoint == 'github_create_pull_request':
        required = {'repository_full_name', 'base', 'head', 'title', 'body', 'draft'}
        ledger.require(set(args) == required and all(isinstance(args[k], str) and args[k]
                       for k in ('base', 'head', 'title')) and isinstance(args['body'], str)
                       and type(args['draft']) is bool, 'explicit PR branch, title, body and draft state required')
        return ('github', 'create', 'https://github.com/' + repo + '/pulls',
                {k: args[k] for k in ('base', 'head', 'title', 'body', 'draft')})
    if endpoint == 'github_merge_pull_request':
        required = {'repository_full_name', 'pr_number', 'expected_head_sha', 'merge_method'}
        ledger.require(set(args) == required and type(args['pr_number']) is int and args['pr_number'] > 0
                       and isinstance(args['expected_head_sha'], str)
                       and re.fullmatch(r'[a-f0-9]{40}', args['expected_head_sha'])
                       and args['merge_method'] in ('merge', 'squash', 'rebase'),
                       'explicit PR, reviewed head and merge method required')
        return ('github', 'update', 'https://github.com/' + repo + '/pull/' + str(args['pr_number']),
                {'merged': True, 'head_sha': args['expected_head_sha'], 'merge_method': args['merge_method']})
    if endpoint in ('github_create_file', 'github_update_file'):
        ledger.require(set(args) <= {'repository_full_name', 'branch', 'path', 'content', 'message', 'sha'} and args.get('branch'), 'explicit file branch and supported fields required')
        target = 'https://github.com/' + repo + '/blob/' + args['branch'] + '/' + args['path']
        return 'github', 'create' if endpoint == 'github_create_file' else 'update', target, {'content': args['content']}
    raise ledger.LedgerError('unsupported provider write adapter')



def upload_payload(args, gate):
    """Bind upload preparation to one immutable asset and its intended page."""
    ledger.require(set(args) <= {'filename', 'content_type'} and isinstance(args.get('filename'), str),
                   'unsupported upload fields')
    ledger.require('content_type' not in args or isinstance(args['content_type'], str) and args['content_type'],
                   'invalid upload content type')
    payload = json.loads(ledger.read_file(gate['payload_path']))
    upload = payload.get('upload', {})
    ledger.require(set(payload) == {'upload'} and set(upload) ==
                   {'target', 'filename', 'asset_path', 'asset_sha256'}, 'exact upload asset binding required')
    ledger.require(gate['operation'] == 'update' and
                   notion_identity(upload['target']) == notion_identity(gate['target']) and
                   args['filename'] == upload['filename'] == Path(upload['asset_path']).name,
                   'upload filename or destination mismatch')
    ledger.require(Path(upload['asset_path']).is_absolute(), 'absolute upload asset path required')
    asset = ledger.read_file(upload['asset_path'], 20 * 1024 * 1024)
    ledger.require(asset and ledger.sha(asset) == upload['asset_sha256'], 'approved upload file changed')
    return payload

def validate_request(store, name, args, gate):
    if tool_name(name) == 'mcp__codex_apps__notion_notion_create_file_upload':
        payload = upload_payload(args, gate)
        service, operation, target = 'notion', 'update', payload['upload']['target']
    else:
        service, operation, target, payload = request_payload(name, args, Path(store.path).parent.parent)
    destination = next((d for d in store.hooks()['policy']['destinations'] if d['id'] == gate['destination_id']), None)
    ledger.require(destination and destination['service'] == service and operation == gate['operation'], 'actual service or operation mismatch')
    ledger.require((notion_identity(target) == notion_identity(gate['target']) if service == 'notion' else target == gate['target']), 'actual write resource mismatch')
    if service == 'linear':
        if linear_connector(name):
            ledger.require('link_id' not in args, 'native Linear does not accept link_id')
            linear_connection(store, name, gate)
        else:
            ledger.require(args.get('link_id') == gate['workspace'], 'actual Linear account mismatch')
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
        elif tool_name(write['tool_name']) == 'mcp__codex_apps__github_create_pull_request':
            ledger.require(args.get('pr_number') == created, 'fetch the actual created PR')
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
        connector = linear_connector(write['tool_name'])
        document = provider(write['tool_name']) == 'linear_save_document'
        ledger.require(endpoint == ('linear_get_document' if document else 'linear_get_issue') and (linear_connector(name) == connector
                       if connector else args.get('link_id') == write_args['link_id']), 'authoritative Linear account fetch required')
        ledger.require(not document or set(args) == {'id'}, 'read complete Linear document')
        if any(key in write_args for key in ('blockedBy', 'blocks', 'relatedTo')):
            ledger.require(args.get('includeRelations') is True, 'fetch actual Linear relations for relation writes')
        if write['gate']['operation'] == 'update':
            ledger.require(args['id'] == write_args['id'], 'readback issue differs from actual write')
    else:
        expected = ('github_fetch_pr' if tool_name(write['tool_name']) in ('mcp__codex_apps__github_create_pull_request', 'mcp__codex_apps__github_merge_pull_request')
                    else 'github_fetch_file' if 'content' in write_args else 'github_fetch_issue')
        repository = args.get('repo_full_name') if expected == 'github_fetch_pr' else args.get('repository_full_name')
        ledger.require(endpoint == expected and repository == write_args['repository_full_name'], 'authoritative GitHub repository fetch required')
        if expected == 'github_fetch_file':
            ledger.require(args.get('path') == write_args['path'] and args.get('ref') == write_args['branch'] and not args.get('start_line') and not args.get('end_line') and args.get('encoding', 'utf-8') == 'utf-8', 'read complete file from the actual write branch')
        elif write['gate']['operation'] == 'update':
            if expected == 'github_fetch_pr':
                ledger.require(args.get('pr_number') == write_args['pr_number'], 'readback PR differs from actual merge')
            else:
                ledger.require(args.get('issue_number') == write_args['issue_number'], 'readback issue differs from actual write')
    return service


def actual_payload(write, write_args, read_name, read_args, raw, linear_aliases=None, linear_workspace_url=None):
    raw = wire_value(raw)
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
        if 'upload' in expected:
            upload_payload(write_args, write['gate'])
            source = write.get('upload_source')
            # ponytail: only native media outside code; transformed references stay uncertain.
            body = re.sub(r'(?ms)^ {0,3}(`{3,}|~{3,})[^\n]*\n.*?^ {0,3}\1[^\n]*(?:\n|$)|`+[^`]*`+', '', value['notion_body'])
            sources = re.findall(r'(?m)^ {0,3}!\[[^\]\n]*\]\(([^)\s]+)\)', body)
            sources += re.findall(r'(?m)^ {0,3}<(?:image|file|pdf|audio|video)\b[^>\n]*\bsrc="([^\"]+)"',
                                                body)
            ledger.require(isinstance(source, str) and source and source in sources,
                           'uploaded asset is not independently visible on the intended page')
            return ledger.canonical(expected).encode()
        if 'content_updates' in expected:
            ledger.require(all(item['new_str'] in value['notion_body']
                               and (item['old_str'] in item['new_str'] or item['old_str'] not in value['notion_body'])
                               for item in expected['content_updates']), 'Notion sentence readback mismatch')
            return ledger.canonical(expected).encode()
        result = {key: value['notion_body'] if key == 'body' else value['notion_properties'][key] for key in expected}
        if 'body' in expected:
            approved_body = (write_args['pages'][0].get('content', '') if write['gate']['operation'] == 'create'
                             else write_args.get('new_str', expected['body']))
            properties = value['notion_properties']
            ledger.require(ledger.notion_body_matches(approved_body, result['body'],
                           properties.get('Name', properties.get('title'))), 'write readback mismatch')
            result['body'] = expected['body']
    elif service == 'linear' and provider(write['tool_name']) == 'linear_save_document':
        ledger.require(read_args['id'] in (value.get('id'), value.get('slugId')), 'readback document identity mismatch')
        aliases = {**write.get('linear_aliases', {}), **(linear_aliases or {})}
        result = {}
        for key, wanted in expected.items():
            actual = value.get(key)
            if key in ('issue', 'project', 'initiative', 'cycle', 'team'):
                ledger.require(isinstance(actual, dict) and (wanted in (actual.get('id'), actual.get('name'))
                               or aliases.get(wanted, wanted) == aliases.get(actual.get('id'), actual.get('id'))),
                               'Linear document parent mismatch')
                actual = wanted
            elif key == 'content':
                ledger.require(linear_description_matches(wanted, actual, aliases, linear_workspace_url),
                               'Linear document content mismatch')
                actual = wanted
            result[key] = actual
    elif service == 'linear':
        if write['gate']['operation'] == 'update':
            ledger.require(read_args['id'] in (value.get('id'), value.get('uuid'), value.get('identifier')), 'readback issue identity mismatch')
        else:
            team = value.get('team')
            ledger.require(write['gate']['target'] in (value.get('teamId'), team.get('id') if isinstance(team, dict) else team), 'created issue team mismatch')
        aliases = {**write.get('linear_aliases', {}), **(linear_aliases or {})}
        identity = lambda item: aliases.get(str(item), str(item))
        result = {}
        for key, wanted in expected.items():
            actual = value.get('status', value.get('state')) if key == 'state' else value.get(key)
            if key in ('state', 'priority') and isinstance(actual, dict):
                actual = actual['name' if key == 'state' else 'value']
            if key == 'parentId':
                ledger.require(identity(actual) == identity(wanted), 'Linear parent differs from planned parent')
                actual = wanted
            elif key == 'project':
                choices = (value.get('projectId'), actual.get('id') if isinstance(actual, dict) else actual,
                           actual.get('name') if isinstance(actual, dict) else None)
                ledger.require(wanted in choices, 'Linear project differs from planned project')
                actual = wanted
            elif key in ('blockedBy', 'blocks', 'relatedTo'):
                actual = value.get('relations', {}).get(key)
                ledger.require(isinstance(actual, list) and all(identity(item) in
                    {identity(rel.get('id')) for rel in actual} for item in wanted), 'Linear relation is missing')
                actual = wanted
            elif key == 'links':
                actual = value.get('attachments', value.get('links', []))
                ledger.require(isinstance(actual, list) and all(any(
                    link.get('title') == item.get('title') and link.get('url') == item.get('url')
                    for link in actual) for item in wanted), 'Linear source link is missing')
                actual = wanted
            elif key == 'labels':
                names = {item.get('name') if isinstance(item, dict) else item for item in actual or []}
                ids = {item.get('id') if isinstance(item, dict) else item for item in actual or []}
                ledger.require(set(wanted) in (names, ids), 'Linear labels differ from planned labels')
                actual = wanted
            elif key == 'description':
                ledger.require(linear_description_matches(wanted, actual, aliases, linear_workspace_url, expected.get('links')),
                               'Linear description differs from planned content')
                actual = wanted
            result[key] = actual
    elif tool_name(write['tool_name']) == 'Bash':
        ledger.require(value.get('url') == write['gate']['target'], 'remote GitHub ref identity mismatch')
        result = {'commit': value['object']['sha'], 'ref': value['ref']}
    elif tool_name(write['tool_name']) == 'mcp__codex_apps__github_merge_pull_request':
        pr = value.get('pull_request', value)
        merge_sha = write.get('merge_sha')
        ledger.require(isinstance(merge_sha, str) and re.fullmatch(r'[a-f0-9]{40}', merge_sha)
                       and isinstance(pr, dict) and pr.get('number') == write_args['pr_number']
                       and pr.get('url') == write['gate']['target']
                       and pr.get('merged') is True and pr.get('merge_commit_sha') == merge_sha
                       and pr.get('head_sha') == write_args['expected_head_sha'],
                       'remote PR merge or reviewed head mismatch')
        result = {'merged': True, 'head_sha': pr['head_sha'], 'merge_method': write_args['merge_method']}
    elif tool_name(write['tool_name']) == 'mcp__codex_apps__github_create_pull_request':
        number = read_args['pr_number']
        pr = value.get('pull_request', value)
        ledger.require(isinstance(pr, dict) and pr.get('number') == number and
                       pr.get('html_url', pr.get('url')) ==
                       'https://github.com/' + write_args['repository_full_name'] + '/pull/' + str(number),
                       'remote PR identity mismatch')
        ledger.require(pr.get('head_sha') == write['expected_head_sha'], 'remote PR head commit differs from reviewed delivery')
        head = pr.get('head')
        base = pr.get('base')
        result = {'head': head.get('ref') if isinstance(head, dict) else head or pr.get('headRefName'),
                  'base': base.get('ref') if isinstance(base, dict) else base or pr.get('baseRefName'),
                  'title': pr.get('title'), 'body': pr.get('body'), 'draft': pr.get('draft')}
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

def wire_value(raw):
    # Native Codex hooks serialize tool_response as JSON text.
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except ValueError:
            raise ledger.LedgerError('tool response is not valid JSON') from None
    return raw


def response_value(raw):
    raw = wire_value(raw)
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
        if not parent:
            ancestors = re.findall(r'<parent-page url="([^"]+)"', header)
            parent_url = ancestors[-1] if ancestors else None
        else:
            parent_url = parent[1]
        value = {**value, 'notion_body': ledger.plain_summary(body.encode()),
                 'notion_properties': json.loads(props[1]),
                 'notion_target': value['url'].split('?')[0],
                 'notion_parent': parent_url}
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
    pr_write = kind == 'write' and tool_name(name) == 'mcp__codex_apps__github_create_pull_request'
    ledger.require(('expected_head_sha' in d) == pr_write, 'PR write requires its reviewed head commit')
    if pr_write:
        ledger.require(isinstance(d['expected_head_sha'], str) and re.fullmatch(r'[a-f0-9]{40}', d['expected_head_sha']),
                       'invalid reviewed PR head commit')
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
                               and call['phase'] not in {'superseded', 'retired'}
                               for key, call in hooks.get('tool_calls', {}).items()),
                       'reuse the existing planned operation or delegation')
        if kind == 'write':
            validate_request(store, name, args, gate)
            ledger.require(ledger.snapshot(gate['payload_path'])['sha256'] == gate['payload_sha256'], 'write payload changed')
        else:
            ledger.require(isinstance(args.get('message'), str) or isinstance(args.get('items'), list), 'delegation needs a prompt')
    else:
        ledger.require(set(gate) == {'write_call_id'}, 'invalid readback gate')
        write = hooks.get('tool_calls', {}).get(gate['write_call_id'])
        ledger.require(write and write['kind'] == 'write', 'readback needs a planned write')
        ledger.require(protected(name, args) is None, 'readback must be a read operation')
        write_args = arguments(write['tool_name'], json.loads(ledger.read_file(write['input']['path'])))
        if linear_connector(write['tool_name']):
            linear_connection(store, write['tool_name'], write['gate'])
        read_request(write, write_args, name, args)
    record = {'kind': kind, 'tool_name': tool_name(name), 'input': source,
              'input_sha256': ledger.sha(ledger.canonical(args).encode()), 'gate': gate, 'phase': 'prepared',
              'artifact_sha256': (store.task['artifact']['sha256'] if kind == 'write'
                                  and gate.get('purpose') != 'working-context' else None)}
    if pr_write:
        record['expected_head_sha'] = d['expected_head_sha']
    if kind == 'write':
        record['service'] = validate_request(store, name, args, gate)[0]
        if linear_connector(name):
            record['linear_aliases'] = dict(linear_connection(store, name, gate).get('issues', {}))
    calls = hooks.setdefault('tool_calls', {})
    old = calls.get(call_id)
    if old:
        ledger.require(all(old[k] == v for k, v in record.items() if k != 'phase'), 'planned tool call is frozen')
    else:
        ledger.require(not any(x['tool_name'] == record['tool_name'] and x['input_sha256'] == record['input_sha256']
                               for x in calls.values() if x['phase'] not in {'superseded', 'retired'}
                               and not (kind == 'readback' and x['kind'] == 'readback'
                                        and x['phase'] == 'observed')), 'reuse the existing planned tool call')
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


def invalidate_document(store, target):
    if not target:
        return
    documents = store.hooks().get('execution_documents', {})
    for key, observed in list(documents.items()):
        if target in (key, observed.get('id'), observed.get('slug_id')):
            documents.pop(key)


def event(store, d):
    e = d['event']
    ledger.require(e.get('session_id') == store.task['owner'], 'hook session does not own task')
    name = e.get('hook_event_name')
    if name == 'SubagentStop':
        agent_id = e.get('agent_id')
        if not isinstance(agent_id, str) or not agent_id:
            return {}
        for call in store.hooks().get('tool_calls', {}).values():
            if call['kind'] == 'delegate' and call.get('agent_id') == agent_id:
                call.setdefault('subagent_stop', {'agent_id': agent_id, 'observed_at': ledger.now()})
                return output(name, 'Subagent returned. Use wait_agent to confirm the final result before recording completion; this lifecycle event may still be continued.')
        return {}
    connector = linear_connector(e.get('tool_name', ''))
    if name == 'PostToolUse' and connector:
        endpoint = provider(e['tool_name'])
        if endpoint == 'linear_save_document':
            invalidate_document(store, (e.get('tool_input') or {}).get('id'))
        if endpoint == 'linear_get_document' and connector == 'mcp__linear__':
            documents = store.hooks().setdefault('execution_documents', {})
            requested = (e.get('tool_input') or {}).get('id')
            documents.pop(requested, None)
            raw = wire_value(e.get('tool_response'))
            value = response_value(raw)
            if (isinstance(value, dict) and not value.get('error') and not value.get('isError')
                    and not (isinstance(raw, dict) and raw.get('isError'))
                    and requested in (value.get('id'), value.get('slugId'))
                    and isinstance(value.get('content'), str) and value.get('updatedAt')):
                path = evidence(store, 'execution-document', e['tool_use_id'], requested, ledger.canonical(raw).encode())
                documents[requested] = {'updated_at': value['updatedAt'], 'body_sha256': ledger.sha(value['content'].encode()),
                                        'task_issue': (value.get('issue') or {}).get('id'), 'owner': store.task['owner'],
                                        'id': value.get('id'), 'slug_id': value.get('slugId'), 'evidence': ledger.snapshot(path)}
        if endpoint == 'linear_get_workspace':
            connections = store.hooks().setdefault('connections', {})
            connections.pop(connector, None)
            raw = wire_value(e.get('tool_response'))
            value = response_value(raw)
            ledger.require(isinstance(value, dict) and not value.get('error')
                           and not value.get('isError') and not (isinstance(raw, dict) and raw.get('isError')),
                           'Linear workspace observation failed; prior connection invalidated')
            workspace = ledger.text(value.get('id'), 'actual Linear workspace')
            path = evidence(store, 'connection', e['tool_use_id'], connector, ledger.canonical(raw).encode())
            observed = {'workspace': workspace, 'evidence': ledger.snapshot(path), 'issues': {}}
            url = value.get('url')
            if url is not None:
                from urllib.parse import urlsplit
                parsed = urlsplit(url)
                ledger.require(parsed.scheme == 'https' and parsed.netloc == 'linear.app'
                               and len(parsed.path.strip('/').split('/')) == 1 and parsed.path.strip('/')
                               and not parsed.query and not parsed.fragment,
                               'invalid Linear workspace URL')
                observed['url'] = url
            connections[connector] = observed
            return output(name, 'Actual Linear connection recorded; exact authorized destination checks still apply.')
        if endpoint == 'linear_get_issue':
            observed = store.hooks().get('connections', {}).get(connector)
            value = response_value(e.get('tool_response'))
            if observed and isinstance(value, dict) and value.get('uuid') and value.get('id') and not value.get('isError'):
                observed['issues'][value['uuid']] = value['id']
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
            if store.hooks()['delegations'][item['gate']['delegation_id']]['outcome'] == 'finished':
                continue  # Preserve an already reconciled final result and its evidence.
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
    matching = [(key, item) for key, item in calls.items()
                if matches_call({**store.task, '_database': str(store.path)}, item,
                                e.get('tool_name', ''), args, digest, name, e.get('tool_use_id'))]
    if len(matching) > 1:
        exact = [(key, item) for key, item in matching if digest in
                 (item['input_sha256'], item.get('effective_input_sha256'))]
        if exact:
            matching = exact
        else:
            bindings = [{k: v for k, v in item['gate'].items() if k != 'operation_id'}
                        for _, item in matching]
            ledger.require(all(binding == bindings[0] for binding in bindings),
                           'ambiguous planned tool call')
            matching = matching[:1]
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
        ledger.require(item['phase'] == 'prepared' or retryable, 'Call already dispatched; reconcile before retrying')
        updated = None
        if item['kind'] == 'write':
            ledger.require(item['gate'].get('purpose') == 'working-context' or
                           (store.task['artifact'] and item['artifact_sha256'] == store.task['artifact']['sha256']), 'planned write version changed; prepare a new call')
            validate_request(store, item['tool_name'], args, item['gate'])
            store.before_write(item['gate'])
            ledger.require(store.hook_result['should_write'], 'Write already verified; skip duplicate')
            if linear_connector(item['tool_name']) and provider(item['tool_name']) == 'linear_save_document':
                invalidate_document(store, args.get('id'))
            item['attempt'] = store.hook_result['attempt']
            if tool_name(item['tool_name']) == 'Bash':
                item['effective_input_sha256'] = digest
        elif item['kind'] == 'delegate':
            store.before_delegate(item['gate'])
            updated = delegated_input(args, store.hook_result['contract'])
            item['effective_input_sha256'] = ledger.sha(ledger.canonical(updated).encode())
        else:
            write = calls[item['gate']['write_call_id']]
            if linear_connector(write['tool_name']):
                linear_connection(store, write['tool_name'], write['gate'])
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
        if tool_name(item['tool_name']) == 'mcp__codex_apps__github_merge_pull_request':
            value = response_value(raw)
            if isinstance(value, dict) and value.get('merged') is True and isinstance(value.get('sha'), str) and re.fullmatch(r'[a-f0-9]{40}', value['sha']):
                item['merge_sha'] = value['sha']
        if tool_name(item['tool_name']) == 'mcp__codex_apps__notion_notion_create_file_upload':
            value = response_value(raw)
            if isinstance(value, dict) and not value.get('error') and not value.get('isError') and not wire_value(raw).get('isError'):
                source = value.get('markdown_source')
                upload_id = value.get('file_upload_id')
                if not source and isinstance(upload_id, str) and re.fullmatch(r'[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}', upload_id):
                    source = 'file-upload://' + upload_id
                if isinstance(source, str) and len(source) <= 2048 and not re.search(r'[\s<>"\\]', source) and source.startswith(('attachment:', 'file-upload://', 'file_upload:', 'notion:', 'https:')):
                    item['upload_source'] = source
        if gate['operation'] == 'create' and isinstance(wire_value(raw), dict) and not wire_value(raw).get('isError'):
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
                    resource = value.get('pull_request', value.get('issue', value))
                    item['created_resource'] = resource.get('number', resource.get('issue_number')) if isinstance(resource, dict) else None
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
            connection = (linear_connection(store, write['tool_name'], gate)
                          if linear_connector(write['tool_name']) else None)
            content = actual_payload(write, write_args, item['tool_name'], args, raw,
                                     connection.get('issues', {}) if connection else None,
                                     connection.get('url') if connection else None)
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


def session_tasks(e, include_completed=False):
    """Read current bound task snapshots for both runtime and record reminders."""
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
                     and not t.get('paused') and (include_completed or not
                         (t.get('completion_requested') and t.get('stage') == 'done')))
    return tasks


def handle(e):
    import run
    run.verify_install()
    name = e.get('hook_event_name')
    if name not in ('PreToolUse', 'PostToolUse', 'SubagentStop', 'Stop'):
        return {}
    tasks = session_tasks(e)
    if not tasks:
        return {}
    if name in ('Stop', 'SubagentStop'):
        if name == 'SubagentStop':
            agent_id = e.get('agent_id')
            if not isinstance(agent_id, str) or not agent_id:
                return {}
            for task in tasks:
                if any(c['kind'] == 'delegate' and c.get('agent_id') == agent_id for c in task.get('runtime_hooks', {}).get('tool_calls', {}).values()):
                    return ledger.Ledger(task['_database']).dispatch('tool-event', {'task_id': task['task_id'], 'owner': task['owner'], 'event': e})['hook']
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
    if (name == 'PostToolUse' and linear_connector(e.get('tool_name', ''))
            and provider(e['tool_name']) == 'linear_save_document' and args.get('id')):
        for task in tasks:
            ledger.Ledger(task['_database']).dispatch('invalidate-document',
                {'task_id': task['task_id'], 'owner': task['owner'], 'document_id': args['id']})
    selected = [t for t in tasks if any(matches_call(t, c, e.get('tool_name', ''), args, fingerprint,
                                                               name, e.get('tool_use_id'))
                for c in t.get('runtime_hooks', {}).get('tool_calls', {}).values())]
    if name == 'PostToolUse' and tool_name(e.get('tool_name', '')) == 'wait_agent':
        for t in tasks:
            if not t.get('blocker'):
                ledger.Ledger(t['_database']).dispatch('tool-event', {'task_id': t['task_id'], 'owner': t['owner'], 'event': e})
        return {}
    if not selected:
        if name == 'PostToolUse' and linear_connector(e.get('tool_name', '')):
            for t in tasks:
                if not t.get('blocker'):
                    ledger.Ledger(t['_database']).dispatch('tool-event', {'task_id': t['task_id'], 'owner': t['owner'], 'event': e})
            return {}
        if name == 'PreToolUse' and protected(e.get('tool_name', ''), args):
            return output(name, 'Tracked Harness action has no prepared call. Freeze its exact input and gate with prepare-tool first.', deny=True)
        return {}
    ledger.require(len(selected) == 1, 'ambiguous task for tool call')
    t = selected[0]
    result = ledger.Ledger(t['_database']).dispatch('tool-event', {'task_id': t['task_id'], 'owner': t['owner'], 'event': e})['hook']
    return result


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
