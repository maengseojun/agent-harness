"""Cooperative work-record approvals; no network, prompt storage or authentication.

JSON stdin: {action: assess|propose|presented|decide|saved|reviewed|linked|finalized|resume|status, ...}, or a native hook
object. propose requires session_id, task_id, result_key (stable outcome identity),
draft_path, linear_refs, completion_basis, project_index_target, notion_target,
endix (bool), tool_name and tool_input (exact JSON object). Returns candidate_id,
revision_id, draft_sha256 and input_sha256; all later actions require session_id,
candidate_id and revision_id. decide additionally requires draft_sha256,
decision (approved|rejected|deferred), user_decision_ref; Endix approval also
requires endix_authorization_ref. presented requires presentation_ref.

saved requires readback_path, page_url, target and evidence_ref. The separate
readback JSON is {content: fetched draft text, properties: fetched property map,
parent_target: actual parent page or collection identity, page_url, target,
evidence_ref}. Requested properties, body and actual resource are compared.
Legacy revisions without property hashes also require approved_input_path:
a separate JSON file matching the original input_sha256. Approval hashes remain unchanged.
reviewed requires review_ref after a saved receipt. resume requires candidate_id,
revision_id, from_session_id, session_id and resume_ref; it preserves history and
uncertain dispatch state and revokes any unused approval. status with task_id can
find the stable candidate across sessions; this local store is not a session ACL.
Reconciliation of absence uses saved with outcome=absent, target, evidence_ref
and readback_path containing {absent:true,target,evidence_ref}. This never renews
permission: a new explicit approval reference permits one new attempt after absence. Additional index writes or
final rewrites need their own presented, concretely approved proposal. New draft
revisions preserve the canonical saved page and old decisions/history.

References and readback provenance are caller attestations, not authenticated
user decisions or service observations. Hooks intercept direct named MCP Notion
calls only, not shell scripts, browser actions or calls hidden inside wrappers.
The host/skill judges substantive work and completion; no prompt classifier here.
assess requires session_id, cwd, task_id, result_sha256 (from the reminder),
assessment_ref and exactly one of candidate_id or deferred_reason. It rechecks
bound task artifact/check/review/source evidence and stores only evidence metadata.
Stop requests one assessment per task result; it never concludes tasks itself.
This file supplies handlers; it does not register hooks or install a skill.
"""
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import urlsplit

import ledger
import tool_hook
from tool_hook import tool_name, notion_identity

BASE = Path.home() / '.local/share/agent-harness/work-records'
SKILL = Path.home() / '.codex/skills/work-records/SKILL.md'
LIMIT = 2 * 1024 * 1024
POLICY = ('Linear is always brain/memo/draft; personal Notion is the completed-record '
          'library. For substantive work consult {skill}. Judge completion from actual '
          'results; propose and present the draft before requesting a user decision. '
          'After an approved write, read back the saved record separately, then request '
          'review and concrete permission for a final rewrite or extra index write. '
          'Endix Notion needs separate explicit authorization. User references are '
          'cooperative attestations, not authentication. Never infer completion from Stop.')


def fingerprint(value):
    return ledger.sha(ledger.canonical(value).encode())


def record_tool(name):
    name = tool_name(name)
    prefix = 'mcp__codex_apps__notion_'
    return prefix + name[len(prefix):].removeprefix('notion_') if name.startswith(prefix) else name


def notion_write(name, args=None):
    name = record_tool(name) if isinstance(name, str) else ''
    return (name.startswith('mcp__')
            and bool(re.search(r'(?:^|_)(notion)(?:_|$)', name))
            and tool_hook.protected(name, args or {}) == 'write')


def context(name, message, deny=False):
    if name == 'PreToolUse':
        return {'hookSpecificOutput': {'hookEventName': name,
                'permissionDecision': 'deny' if deny else 'allow',
                'permissionDecisionReason': message}}
    return {'hookSpecificOutput': {'hookEventName': name, 'additionalContext': message}}


def draft(path):
    return ledger.sha(ledger.read_file(path, LIMIT))


def current(revision):
    ledger.require(draft(revision['draft_path']) == revision['draft_sha256'],
                   'draft changed; propose and present a new revision')


def reference(data, key):
    return ledger.text(data.get(key), key, 4096)


def page_identity(value):
    # Notion page URLs may include a title before the stable 32-hex page ID.
    match = re.search(r'([a-fA-F0-9]{32})(?:[/?#]|$)', str(value).replace('-', ''))
    return match.group(1).lower() if match else str(value)


def notion_page_url(value):
    if not isinstance(value, str):
        return False
    url = urlsplit(value)
    host = url.hostname or ''
    return url.scheme == 'https' and (host in ('app.notion.com', 'notion.so', 'www.notion.so')
                                      or host.endswith('.notion.site'))


def links_to_page(body, page):
    if not isinstance(body, str):
        return False
    urls = re.findall(r'https://[^\s<>"\])]+', body)
    return any(notion_page_url(url) and page_identity(url) == page_identity(page) for url in urls)


def validate_write(revision, args, canonical=None):
    endpoint = revision['tool_name'].split('__')[-1]
    body = ledger.read_file(revision['draft_path'], LIMIT).decode('utf-8')
    if endpoint.endswith('create_pages'):
        ledger.require(canonical is None, 'canonical page exists; update it instead of creating a duplicate')
        pages = args.get('pages')
        ledger.require(isinstance(pages, list) and len(pages) == 1
                       and isinstance(pages[0], dict) and pages[0].get('content') == body,
                       'prepare one page whose content exactly matches the draft')
        parent = args.get('parent')
        ledger.require(isinstance(parent, dict), 'explicit Notion parent required')
        target = ('collection://' + parent['data_source_id'] if 'data_source_id' in parent
                  else parent.get('page_id'))
        ledger.require(target == revision['notion_target'], 'write target does not match proposal')
    elif endpoint.endswith('update_page'):
        command = args.get('command')
        ledger.require(command in ('replace_content', 'update_content', 'update_properties'),
                       'record updates require exact content or property changes')
        ledger.require(page_identity(args.get('page_id')) == page_identity(revision['notion_target']),
                       'write target does not match proposal')
        if command == 'replace_content':
            ledger.require(args.get('new_str') == body, 'replacement content does not match draft')
            ledger.require(not args.get('properties'), 'replace_content cannot update properties')
        elif command == 'update_content':
            updates = args.get('content_updates')
            ledger.require(isinstance(updates, list) and updates and all(
                isinstance(item, dict) and isinstance(item.get('old_str'), str)
                and isinstance(item.get('new_str'), str) and item['old_str'] != item['new_str']
                and item['new_str'] in body for item in updates),
                'content updates must match the complete proposed draft')
            ledger.require(not args.get('properties'), 'update_content cannot update properties')
        else:
            ledger.require(isinstance(args.get('properties'), dict) and args['properties'],
                           'property update needs exact nonempty properties')
            ledger.require('new_str' not in args and 'content' not in args,
                           'property update cannot change body')
        if canonical:
            ledger.require(page_identity(args.get('page_id')) == page_identity(canonical['page_url']),
                           'rewrite must target canonical saved page')
    else:
        raise ledger.LedgerError('record proposals support create_pages or update_page only')


def proposal(data):
    result = {key: reference(data, key) for key in (
        'completion_basis', 'notion_target', 'tool_name')}
    result['record_kind'] = ledger.choice(data.get('record_kind', 'outcome'), {'outcome', 'policy'})
    result['project_index_target'] = (reference(data, 'project_index_target')
                                      if result['record_kind'] == 'outcome' else data.get('project_index_target', ''))
    ledger.require(isinstance(result['project_index_target'], str), 'invalid project index target')
    result['draft_path'] = ledger.path_name(data['draft_path'])
    result['draft_sha256'] = draft(result['draft_path'])
    result['linear_refs'] = ledger.strings(data['linear_refs'], 'linear_refs', empty=True)
    result['output_issue_ref'] = (reference(data, 'output_issue_ref')
                                  if result['record_kind'] == 'outcome' else '')
    ledger.require(result['record_kind'] == 'policy' or result['output_issue_ref'] in result['linear_refs'],
                   'outcome record needs an original Linear output issue')
    ledger.require(type(data.get('endix')) is bool, 'explicit endix flag required')
    result['endix'] = data['endix']
    result['tool_name'] = record_tool(result['tool_name'])
    args = data.get('tool_input')
    ledger.require(isinstance(args, dict) and notion_write(result['tool_name'], args),
                   'exact Notion mutation tool and input required')
    # Only hashes are stored: neither the draft body nor tool input is retained.
    validate_write(result, args)
    body = ledger.read_file(result['draft_path'], LIMIT).decode('utf-8')
    result['body_sha256'] = ledger.sha(ledger.plain_summary(body.encode()).encode())
    props = args['pages'][0].get('properties', {}) if result['tool_name'].endswith('create_pages') else args.get('properties', {})
    ledger.require(isinstance(props, dict), 'requested properties must be an object')
    result['property_hashes'] = {key: fingerprint(value) for key, value in props.items()}
    for url in [result['project_index_target'], *result['linear_refs']]:
        if not url:
            continue
        ledger.require(not url.startswith('https://') or url in body,
                       'include the intended index and Linear links in the draft')
    result['related_candidates'] = ledger.strings(data.get('related_candidates', []), 'related_candidates', empty=True)
    result['input_sha256'] = fingerprint(args)
    result['revision_id'] = fingerprint({key: result[key] for key in
        ('draft_sha256', 'notion_target', 'endix', 'record_kind', 'tool_name', 'input_sha256',
         'linear_refs', 'output_issue_ref', 'project_index_target', 'completion_basis', 'related_candidates')})
    return result


def selected(state, data):
    candidate = state.get(reference(data, 'candidate_id'))
    ledger.require(candidate is not None, 'unknown candidate')
    ledger.require(candidate['session_id'] == ledger.identifier(data.get('session_id')),
                   'candidate belongs to another session')
    revision = candidate['revisions'][-1]
    ledger.require(revision['revision_id'] == reference(data, 'revision_id'), 'stale revision')
    return candidate, revision


def page_url(value):
    value = ledger.text(value, 'page_url', 4096)
    url = urlsplit(value)
    ledger.require(url.scheme == 'https' and url.hostname and not url.username
                   and (url.hostname == 'notion.so' or url.hostname.endswith('.notion.so')
                        or url.hostname == 'notion.site' or url.hostname.endswith('.notion.site')
                        or (url.hostname == 'app.notion.com' and re.fullmatch(r'/p/[a-f0-9]{32}/?', url.path)))
                   and url.path not in ('', '/'), 'actual Notion page URL required')
    return value


def migrate(state):
    # Installed v1 files have no attempts; retain their consumed approvals.
    state.setdefault('_assessments', {})
    for candidate in candidates_in(state):
        for revision in candidate['revisions']:
            revision.setdefault('record_kind', 'outcome')
            revision.setdefault('output_issue_ref', revision.get('linear_refs', [''])[0]
                                if revision.get('linear_refs') else '')
            revision.setdefault('editorial_state', 'saved-draft' if revision.get('write_state') == 'saved' else 'not-saved')
            revision.setdefault('link_state', ('not-required' if revision['record_kind'] == 'policy' else 'pending')
                                if revision.get('write_state') == 'saved' else 'not-saved')
            if 'attempts' not in revision:
                revision['attempts'] = ([{'tool_use_id': revision['tool_use_id'],
                    'write_state': revision['write_state'],
                    **({'receipt': revision['receipt'].copy()} if revision.get('receipt') else {})}]
                    if revision.get('tool_use_id') else [])


def candidates_in(state):
    return [value for key, value in state.items() if key != '_assessments']


def task_results(event):
    if not event.get('cwd'):
        return []
    results = []
    for task in tool_hook.session_tasks(event, include_completed=True):
        artifact, check, review = (task.get(key) for key in ('artifact', 'check', 'review'))
        if (task.get('work_status') not in ('verified', 'concluded') or task.get('repair_open')
                or not all((artifact, check, review))):
            continue
        digest = artifact['sha256']
        if (check.get('artifact_sha256') != digest or review.get('artifact_sha256') != digest
                or not review.get('agent_id')
                or review['agent_id'] in task.get('owners', []) + task.get('workers', [])
                or type(check.get('exit_code')) is not int
                or review.get('verdict') not in ('approved', 'concluded')
                or (task['work_status'] == 'verified' and
                    (check.get('exit_code') != 0 or review.get('verdict') != 'approved'))):
            continue
        evidence = [artifact, check['evidence'], review['evidence']]
        sources = task.get('request', {}).get('closeout', {})
        paths = sources.get('source_paths', sources.get('github_paths', []))
        if any(set(record.get('sources', {})) != set(paths) for record in (check, review)):
            continue
        evidence.extend(item for record in (check, review) for item in record.get('sources', {}).values())
        try:
            if not all(ledger.current(item) for item in evidence):
                continue
        except OSError:
            continue
        # Copy only evidence metadata, never task prompts, descriptions or bodies.
        check = {key: check[key] for key in ('artifact_sha256', 'evidence', 'exit_code', 'sources') if key in check}
        review = {key: review[key] for key in ('artifact_sha256', 'evidence', 'verdict', 'sources') if key in review}
        basis = {'artifact': {key: artifact[key] for key in ('path', 'sha256')}, 'check': check, 'review': review,
                 'work_status': task['work_status']}
        key = fingerprint([task['_database'], task['task_id']])
        results.append((key, task['task_id'], fingerprint(basis), basis))
    return results


def action(state, data):
    operation = data.get('action')
    if operation == 'assess':
        session = ledger.identifier(data.get('session_id'))
        matches = [result for result in task_results(data) if result[1] == reference(data, 'task_id')
                   and result[2] == reference(data, 'result_sha256')]
        ledger.require(len(matches) == 1, 'assessment needs one actual current bound task result')
        key, task, digest, basis = matches[0]
        ledger.require(bool(data.get('candidate_id')) != bool(data.get('deferred_reason')),
                       'assessment requires candidate_id or deferred_reason')
        record = {'session_id': session, 'task_id': task, 'result_sha256': digest,
                  'basis': basis, 'assessment_ref': reference(data, 'assessment_ref')}
        if data.get('candidate_id'):
            candidate = state.get(reference(data, 'candidate_id'))
            ledger.require(candidate and candidate['session_id'] == session and candidate['task_id'] == task,
                           'assessment candidate must belong to this task/session')
            record['candidate_id'] = candidate['candidate_id']
            record['revision_id'] = candidate['revisions'][-1]['revision_id']
        else:
            record['deferred_reason'] = reference(data, 'deferred_reason')
        state['_assessments'].setdefault(key, {})[digest] = record
        return record
    if operation == 'resume':
        candidate = state.get(reference(data, 'candidate_id'))
        ledger.require(candidate is not None, 'unknown candidate')
        revision = candidate['revisions'][-1]
        ledger.require(candidate['session_id'] == reference(data, 'from_session_id')
                       and revision['revision_id'] == reference(data, 'revision_id'), 'stale takeover')
        session = ledger.identifier(data.get('session_id'))
        ref = reference(data, 'resume_ref')
        revision['history'].append({'resume_ref': ref, 'from_session_id': candidate['session_id'], 'session_id': session})
        candidate['session_id'] = session
        if revision['write_state'] in ('unwritten', 'absent') and revision['disposition'] == 'approved':
            revision.update(disposition='proposed', presented=False, stop_requested=False)
        return candidate
    if operation == 'propose':
        session = ledger.identifier(data.get('session_id'))
        task = ledger.identifier(data.get('task_id'))
        key = fingerprint([task, reference(data, 'result_key')])
        revision = proposal(data)
        candidate = state.get(key)
        if candidate:
            ledger.require(candidate['session_id'] == session, 'candidate belongs to another session')
            old = candidate['revisions'][-1]
            if old['revision_id'] == revision['revision_id']:
                ledger.require(all(old[key] == revision[key] for key in
                                   ('linear_refs', 'output_issue_ref', 'completion_basis', 'project_index_target',
                                    'related_candidates')),
                               'approved record references cannot be retargeted')
                return candidate
            ledger.require(old['write_state'] not in ('dispatched', 'uncertain'),
                           'reconcile uncertain write before any new revision')
            ledger.require(not any(r['revision_id'] == revision['revision_id'] for r in candidate['revisions']),
                           'historical revision cannot renew write permission')
        else:
            candidate = {'candidate_id': key, 'session_id': session, 'task_id': task,
                         'result_key': data['result_key'], 'canonical_page': None, 'revisions': []}
            state[key] = candidate
        revision.update(disposition='proposed', presented=False, stop_requested=False,
                        write_state='unwritten', history=[], attempts=[])
        candidate['revisions'].append(revision)
        return candidate
    if operation == 'status' and 'candidate_id' not in data:
        session = ledger.identifier(data.get('session_id'))
        return [c for c in candidates_in(state) if
                (c['task_id'] == data['task_id'] if 'task_id' in data else c['session_id'] == session)]
    candidate, revision = selected(state, data)
    if operation == 'status':
        return {**candidate, 'draft_current': draft(revision['draft_path']) == revision['draft_sha256']}
    if operation == 'presented':
        current(revision)
        revision['presented'] = True
        revision['presentation_ref'] = reference(data, 'presentation_ref')
    elif operation == 'decide':
        current(revision)
        ledger.require(revision['presented'], 'present draft before a decision')
        ledger.require(data.get('draft_sha256') == revision['draft_sha256'], 'decision draft hash mismatch')
        decision = ledger.choice(data.get('decision'), {'approved', 'rejected', 'deferred'})
        ref = reference(data, 'user_decision_ref')
        item = {'decision': decision, 'user_decision_ref': ref}
        if decision == 'approved' and revision['endix']:
            item['endix_authorization_ref'] = reference(data, 'endix_authorization_ref')
            ledger.require(item['endix_authorization_ref'] != ref, 'separate Endix permission reference required')
        if decision == 'approved':
            previous = [h for h in revision['history'] if h.get('decision') == 'approved']
            if revision['disposition'] == 'approved' and previous and previous[-1] == item:
                ledger.require(revision['write_state'] == 'unwritten', 'old approval cannot renew an attempt')
                return candidate
            ledger.require(ref not in {h['user_decision_ref'] for h in previous},
                           'new explicit approval reference required; old approval replay denied')
            if revision['endix']:
                ledger.require(item['endix_authorization_ref'] not in
                               {h.get('endix_authorization_ref') for h in previous},
                               'new separate Endix permission reference required')
        ledger.require(revision['write_state'] in ('unwritten', 'absent'),
                       'decision cannot renew dispatched permission')
        revision['history'].append(item)
        revision['disposition'] = decision
        if decision == 'approved' and revision['write_state'] == 'absent':
            revision['write_state'] = 'unwritten'
    elif operation == 'saved':
        ledger.require(revision['write_state'] in ('dispatched', 'uncertain', 'saved', 'absent', 'partial'),
                       'no dispatched write to reconcile')
        path = ledger.path_name(data['readback_path'])
        ledger.require(path != revision['draft_path'] and not os.path.samefile(path, revision['draft_path']),
                       'readback must be a separate file')
        if revision['write_state'] == 'saved':
            receipt = revision['receipt']
            ledger.require(data.get('outcome', 'saved') == 'saved'
                           and path == receipt['readback_path']
                           and data.get('evidence_ref') == receipt['evidence_ref']
                           and draft(path) == receipt['readback_sha256'],
                           'saved reconciliation is immutable; propose a new revision')
            return candidate
        readback = json.loads(ledger.read_file(path, LIMIT), object_pairs_hook=ledger.unique_object)
        target, evidence = reference(data, 'target'), reference(data, 'evidence_ref')
        ledger.require(target == revision['notion_target'] and readback['target'] == target
                       and readback['evidence_ref'] == evidence, 'readback target/evidence mismatch')
        ledger.require(not any(a.get('receipt', {}).get('evidence_ref') == evidence
                               for a in revision.get('attempts', [])[:-1]),
                       'readback evidence belongs to an older attempt; fetch again')
        outcome = data.get('outcome', 'saved')
        if outcome == 'absent':
            ledger.require(revision['write_state'] != 'saved' and readback.get('absent') is True,
                           'absence must be reconciled explicitly')
            receipt = {'outcome': 'absent', 'target': target, 'evidence_ref': evidence}
        else:
            ledger.require(outcome in ('saved', 'partial'), 'invalid reconciliation outcome')
            current(revision)
            url = page_url(data.get('page_url'))
            ledger.require(readback['page_url'] == url and isinstance(readback['content'], str)
                           and ledger.notion_body_matches(ledger.read_file(revision['draft_path'], LIMIT).decode('utf-8'), readback['content']),
                           'separate saved body does not match draft/page')
            properties = readback.get('properties')
            property_hashes = revision.get('property_hashes')
            if property_hashes is None:
                # Legacy approvals keep their original hashes; recover fields only from the frozen input.
                approved = json.loads(ledger.read_file(ledger.path_name(data.get('approved_input_path')), LIMIT),
                                      object_pairs_hook=ledger.unique_object)
                ledger.require(fingerprint(approved) == revision['input_sha256'], 'approved input hash mismatch')
                if (revision['tool_name'].endswith('update_page')
                        and approved.get('command') in ('replace_content', 'update_content')
                        and approved.get('properties')):
                    # Older approved mixed calls could apply content while ignoring properties.
                    validate_write(revision, {key: value for key, value in approved.items()
                                              if key != 'properties'})
                else:
                    validate_write(revision, approved)
                props = (approved['pages'][0].get('properties', {})
                         if revision['tool_name'].endswith('create_pages') else approved.get('properties', {}))
                ledger.require(isinstance(props, dict), 'approved properties must be an object')
                property_hashes = {key: fingerprint(value) for key, value in props.items()}
            properties_match = isinstance(properties, dict) and all(
                key in properties and fingerprint(properties[key]) == expected
                for key, expected in property_hashes.items())
            if outcome == 'partial':
                ledger.require(revision['tool_name'].endswith('update_page') and property_hashes
                               and not properties_match, 'partial outcome needs a verified property mismatch')
            else:
                ledger.require(properties_match, 'saved properties differ from approved values')
            if revision['tool_name'].endswith('create_pages'):
                ledger.require(notion_identity(readback.get('parent_target')) == notion_identity(target),
                               'actual parent differs from approved destination')
            else:
                ledger.require(page_identity(url) == page_identity(target), 'saved page differs from approved update target')
            old_page = candidate['canonical_page']
            ledger.require(old_page is None or page_identity(old_page['page_url']) == page_identity(url),
                           'preserve canonical page; revise that page instead of creating a duplicate')
            receipt = {'outcome': outcome, 'page_url': url, 'target': target, 'evidence_ref': evidence}
            if old_page is None:
                candidate['canonical_page'] = receipt.copy()
        receipt.update(readback_path=path, readback_sha256=draft(path))
        if revision.get('receipt') != receipt:
            revision['history'].append({'reconciliation': receipt})
        revision['receipt'] = receipt
        revision['write_state'] = outcome
        if outcome == 'saved':
            revision['editorial_state'] = 'saved-draft'
            revision['link_state'] = 'not-required' if revision['record_kind'] == 'policy' else 'pending'
        if revision.get('attempts'):
            revision['attempts'][-1].update(write_state=outcome, receipt=receipt.copy())
    elif operation == 'reviewed':
        ledger.require(revision['write_state'] == 'saved', 'save and reconcile the record before reviewing it')
        ref = reference(data, 'review_ref')
        revision['record_review_ref'] = ref
        revision['editorial_state'] = ledger.choice(data.get('verdict', 'needs-revision'),
                                                   {'approved', 'needs-revision'})
        revision['history'].append({'record_review_ref': ref})
    elif operation == 'linked':
        ledger.require(revision['record_kind'] == 'outcome' and revision['write_state'] == 'saved'
                       and candidate.get('canonical_page'),
                       'save and verify the canonical record first')
        page = candidate['canonical_page']['page_url']
        linear_path = ledger.path_name(data['linear_readback_path'])
        index_path = ledger.path_name(data['index_readback_path'])
        ledger.require(linear_path != index_path and linear_path != revision['draft_path']
                       and index_path != revision['draft_path'], 'independent link readbacks required')
        issue = json.loads(ledger.read_file(linear_path, LIMIT), object_pairs_hook=ledger.unique_object)
        index = json.loads(ledger.read_file(index_path, LIMIT), object_pairs_hook=ledger.unique_object)
        ledger.require(issue.get('issue_url') == revision['output_issue_ref']
                       and links_to_page(issue.get('description'), page),
                       'Linear output backlink missing or wrong')
        ledger.require(notion_page_url(index.get('index_url'))
                       and page_identity(index.get('index_url')) == page_identity(revision['project_index_target'])
                       and links_to_page(index.get('content'), page),
                       'Notion project index backlink missing or wrong')
        revision['link_state'] = 'verified'
        revision['link_evidence_ref'] = reference(data, 'evidence_ref')
        revision['link_readbacks'] = {'linear': ledger.sha(ledger.read_file(linear_path, LIMIT)),
                                      'index': ledger.sha(ledger.read_file(index_path, LIMIT))}
    elif operation == 'finalized':
        ledger.require(revision['write_state'] == 'saved'
                       and revision.get('link_state') == ('not-required' if revision['record_kind'] == 'policy' else 'verified')
                       and revision.get('editorial_state') == 'approved',
                       'final record needs verified Linear/Notion links and approved review')
        revision['editorial_state'] = 'final'
        revision['final_approval_ref'] = reference(data, 'user_decision_ref')
    else:
        raise ledger.LedgerError('unknown action')
    return candidate


def hook(state, event):
    name = event.get('hook_event_name')
    if name == 'UserPromptSubmit':
        return context(name, POLICY.format(skill=SKILL) +
                       ('' if SKILL.is_file() else ' Work-records skill is not installed; do not claim otherwise.'))
    if name not in ('PreToolUse', 'PostToolUse', 'Stop'):
        return {}
    session = ledger.identifier(event.get('session_id'))
    candidates = [c for c in candidates_in(state) if c['session_id'] == session]
    if name == 'Stop':
        missing = []
        for key, task, digest, basis in task_results(event):
            records = state['_assessments'].setdefault(key, {})
            if digest not in records:
                records[digest] = {'task_id': task, 'result_sha256': digest,
                                   'basis': basis, 'reminded': True}
                missing.append({'task_id': task, 'result_sha256': digest})
        pending = [c for c in candidates if not c['revisions'][-1]['presented']
                   and not c['revisions'][-1]['stop_requested']
                   and c['revisions'][-1]['disposition'] == 'proposed']
        unlinked = [c for c in candidates if c['revisions'][-1]['record_kind'] == 'outcome'
                    and c['revisions'][-1]['write_state'] == 'saved'
                    and c['revisions'][-1].get('link_state') != 'verified'
                    and not c['revisions'][-1].get('link_reminded')]
        # One bounded continuation for this batch, even when presentation fails.
        for candidate in pending:
            candidate['revisions'][-1]['stop_requested'] = True
        for candidate in unlinked:
            candidate['revisions'][-1]['link_reminded'] = True
        if not pending and not missing and not unlinked:
            return {}
        if missing:
            reason = ('Assess actual verified/concluded task results for an optional '
                    'work record using action=assess with assessment_ref and candidate_id or deferred_reason. '
                    'This is not completion or publication permission. Results: ' + ledger.canonical(missing) +
                    (' Present prepared candidates once: ' + ', '.join(c['candidate_id'] for c in pending) if pending else ''))
            return {'systemMessage': reason} if event.get('stop_hook_active') else {'decision': 'block', 'reason': reason}
        if event.get('stop_hook_active'):
            return {}
        if unlinked and not pending:
            return {'decision': 'block', 'reason': 'Saved work record still needs verified Linear output and '
                    'personal Notion project-index backlinks. Propose any Notion index write for separate approval; '
                    'then fetch both destinations and record linked. Candidates: ' +
                    ', '.join(c['candidate_id'] for c in unlinked)}
        return {'decision': 'block', 'reason': 'Present prepared work-record draft(s) once and ask '
                'for a user decision; then wait quietly. Candidates: ' +
                ', '.join(c['candidate_id'] for c in pending)}
    tool = event.get('tool_name')
    if not notion_write(tool, event.get('tool_input')):
        return {}
    tool = record_tool(tool)
    args = event.get('tool_input')
    ledger.require(isinstance(args, dict), 'Notion tool input must be an object')
    digest = fingerprint(args)
    matches = [(c, c['revisions'][-1]) for c in candidates
               if c['revisions'][-1]['tool_name'] == tool
               and c['revisions'][-1]['input_sha256'] == digest]
    ledger.require(len(matches) == 1, 'Notion write needs one approved exact tool/input for this session')
    candidate, revision = matches[0]
    event_id = reference(event, 'tool_use_id')
    if name == 'PreToolUse':
        current(revision)
        admitted = next((a for a in revision['attempts'] if a['tool_use_id'] == event_id), None)
        if admitted:
            ledger.require(admitted is revision['attempts'][-1]
                           and revision['write_state'] == 'dispatched', 'old admission cannot renew an attempt')
            return context(name, 'Same work-record admission already recorded; readback remains required.')
        validate_write(revision, args, candidate['canonical_page'])
        ledger.require(revision['disposition'] == 'approved' and revision['presented'], 'Notion draft is not approved')
        ledger.require(not revision['endix'] or next((h.get('endix_authorization_ref') for h in reversed(revision['history']) if h.get('decision') == 'approved'), None),
                       'Endix Notion requires separate explicit authorization')
        ledger.require(revision['write_state'] == 'unwritten', 'write already dispatched; reconcile, never automatically retry')
        attempt = {'tool_use_id': event_id, 'write_state': 'dispatched',
                   'approval_ref': next(h['user_decision_ref'] for h in reversed(revision['history'])
                                        if h.get('decision') == 'approved')}
        revision['attempts'].append(attempt)
        revision['history'].append({'attempt': len(revision['attempts']), **attempt})
        revision.update(write_state='dispatched', tool_use_id=event_id)
        return context(name, 'Exact approved work-record write admitted once; readback remains required.')
    attempt = next((a for a in revision['attempts'] if a['tool_use_id'] == event_id), None)
    ledger.require(attempt is not None, 'write observation has no matching admission')
    if attempt is not revision['attempts'][-1] or revision.get('tool_use_id') != event_id:
        return context(name, 'Historical write observation ignored; current attempt unchanged.')
    if revision['write_state'] in ('dispatched', 'uncertain'):
        revision['write_state'] = 'uncertain'
        revision['response_sha256'] = fingerprint(event.get('tool_response'))
        attempt.update(write_state='uncertain', response_sha256=revision['response_sha256'])
    return context(name, 'Write observed as uncertain, not saved. Reconcile actual page/body with a separate readback file.')


def dispatch(data, base=None):
    """Serialize all local transitions; tests pass a private temporary directory."""
    if base is None and isinstance(data, dict) and data.get('action') not in ('status', None):
        active = os.environ.get('CODEX_THREAD_ID')
        if active:
            ledger.require(data.get('session_id') == active,
                           'use CODEX_THREAD_ID; the entry receipt is not a session id')
    base = Path(base) if base is not None else BASE
    ledger.path_name(str(base))
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(base, 0o700)
    lock_fd = os.open(base / 'state.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = base / 'state.json'
        state = json.loads(ledger.read_file(str(path)), object_pairs_hook=ledger.unique_object) if path.exists() else {}
        ledger.require(isinstance(state, dict), 'invalid work-record state')
        migrate(state)
        result = hook(state, data) if 'hook_event_name' in data else action(state, data)
        fd, temporary = tempfile.mkstemp(dir=base, prefix='.records-')
        try:
            with os.fdopen(fd, 'w') as stream:
                stream.write(ledger.canonical(state))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            directory = os.open(base, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return result


def handle(event, base=None):
    try:
        ledger.require(isinstance(event, dict), 'JSON object required')
        return dispatch(event, base)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        message = 'Work-record gate unavailable or request invalid; no completion is verified. Inspect local state and reconcile writes.'
        name = event.get('hook_event_name') if isinstance(event, dict) else None
        if name == 'PreToolUse' and notion_write(event.get('tool_name'), event.get('tool_input')):
            if isinstance(exc, ledger.LedgerError):
                message = f'Work-record write rejected: {exc}'
            return context(name, message, deny=True)
        if name:
            return {'systemMessage': message}
        raise


def main():
    if sys.argv[1:] in (['--help'], ['-h']):
        print(__doc__)
        return
    try:
        raw = sys.stdin.read(LIMIT + 1)
        ledger.require(len(raw) <= LIMIT, 'input too large')
        data = json.loads(raw, object_pairs_hook=ledger.unique_object)
        print(ledger.canonical(handle(data)))
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        # Unparseable input may be a protected write: hook exit 2 fails closed.
        print('Work-record gate unavailable; no completion is verified.', file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
