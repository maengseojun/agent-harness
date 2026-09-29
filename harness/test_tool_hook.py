"""Synthetic hook wire fixtures; no live services, agents, or user settings."""
import json
import io
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
import test_run
import tool_hook
from ledger import LedgerError, canonical, sha
from run import execute


class ToolHookTests(unittest.TestCase):
    def native_working_plan(self):
        self.config('linear')
        tool = 'mcp__linear__save_issue'
        args = {'id': self.dest['target'], 'description': 'working draft', 'parentId': 'parent-uuid',
                'project': 'project-id', 'blockedBy': ['FIX-2'], 'relatedTo': ['FIX-3'],
                'links': [{'title': 'Source', 'url': 'https://example.com/source'}], 'priority': 2}
        (self.project / 'payload.json').write_text(canonical({k: v for k, v in args.items() if k != 'id'}))
        gate = {'operation_id': 'working', 'destination_id': 'saved', 'workspace': self.dest['workspace'],
                'target': self.dest['target'], 'operation': 'update', 'payload_path': 'payload.json',
                'payload_sha256': sha((self.project / 'payload.json').read_bytes()),
                'authorization_ref': self.dest['authorization_ref'], 'purpose': 'working-context'}
        with self.assertRaisesRegex(LedgerError, 'actual Linear workspace'):
            self.prepare('working', 'write', tool, args, gate)
        self.event('PostToolUse', 'mcp__linear__get_workspace', {},
                   {'content': [{'type': 'text', 'text': canonical({'id': self.dest['workspace']})}]}, event_id='workspace')
        self.event('PostToolUse', 'mcp__linear__get_issue', {'id': 'FIX-2'},
                   {'structuredContent': {'id': 'FIX-2', 'uuid': 'parent-uuid'}}, event_id='parent')
        self.prepare('working', 'write', tool, args, gate)
        return tool, args, gate

    def test_native_linear_context_before_artifact_and_relations_readback(self):
        tool, args, gate = self.native_working_plan()
        read_tool, read_args = 'mcp__linear__get_issue', {'id': args['id'], 'includeRelations': True}
        with self.assertRaisesRegex(LedgerError, 'actual Linear relations'):
            self.prepare('bad-fetch', 'readback', read_tool, {'id': args['id']}, {'write_call_id': 'working'})
        with self.assertRaisesRegex(LedgerError, 'account fetch'):
            self.prepare('bad-connector', 'readback', 'mcp__linear_endix__get_issue', read_args, {'write_call_id': 'working'})
        self.prepare('working-fetch', 'readback', read_tool, read_args, {'write_call_id': 'working'})
        self.assertIsNone(self.call('status')['artifact'])
        self.assertEqual('allow', self.event('PreToolUse', tool, args)['hookSpecificOutput']['permissionDecision'])
        self.event('PostToolUse', tool, args, {'structuredContent': {'id': args['id']}})
        observed = {'id': args['id'], 'description': 'working draft', 'parentId': 'FIX-2',
                    'projectId': 'project-id', 'project': 'Project', 'priority': {'value': 2, 'name': 'High'},
                    'relations': {'blockedBy': [{'id': 'FIX-2'}], 'relatedTo': [{'id': 'FIX-3'}, {'id': 'OLD'}]},
                    'attachments': args['links']}
        bad = {**observed, 'relations': {'blockedBy': [], 'relatedTo': [{'id': 'FIX-3'}]}}
        self.event('PreToolUse', read_tool, read_args, event_id='wrong-relations')
        failed = self.event('PostToolUse', read_tool, read_args, {'structuredContent': bad}, event_id='wrong-relations')
        self.assertIn('relation is missing', failed['reason'])
        self.event('PreToolUse', read_tool, read_args, event_id='real-relations')
        self.event('PostToolUse', read_tool, read_args, {'structuredContent': observed}, event_id='real-relations')
        self.assertEqual('verified', self.call('status')['runtime_hooks']['writes']['working']['outcome'])
        # Later artifact verification must not discard already saved progress.
        state = self.ready(complete=False)
        self.assertEqual('verified', state['runtime_hooks']['writes']['working']['outcome'])
        self.assertEqual('done', self.call('complete')['stage'])

    def test_native_linear_wrong_workspace_and_owner_cannot_write(self):
        tool, args, gate = self.native_working_plan()
        self.event('PostToolUse', 'mcp__linear_endix__get_workspace', {},
                   {'structuredContent': {'id': self.dest['workspace']}}, event_id='team-workspace')
        with self.assertRaisesRegex(LedgerError, 'ownership'):
            self.prepare('wrong-owner', 'write', 'mcp__linear_endix__save_issue', args,
                         {**gate, 'operation_id': 'wrong-owner'})
        self.event('PostToolUse', 'mcp__linear__get_workspace', {},
                   {'structuredContent': {'id': 'different-account'}}, event_id='switched')
        with self.assertRaisesRegex(LedgerError, 'actual Linear workspace'):
            self.event('PreToolUse', tool, args)
        # A failed connection observation must revoke a previously usable binding.
        with self.assertRaisesRegex(LedgerError, 'prior connection invalidated'):
            self.event('PostToolUse', 'mcp__linear__get_workspace', {}, {'isError': True}, event_id='failed-identity')
        self.assertNotIn('mcp__linear__', self.call('status')['runtime_hooks'].get('connections', {}))

    def test_linear_description_accepts_verified_issue_autolinks_only(self):
        aliases = {'4f6c608e-2e52-4e76-b968-15bc9987f5de': 'MAE-10',
                   'cb5a5e0b-ccfc-4ec2-b547-ebf208f484a9': 'MAE-11'}
        expected = ('<issue id="4f6c608e-2e52-4e76-b968-15bc9987f5de" '
                    'href="https://linear.app/maeng/issue/MAE-10/한글">MAE-10</issue> and MAE-11')
        actual = ('<issue id="4f6c608e-2e52-4e76-b968-15bc9987f5de" '
                  'href="https://linear.app/maeng/issue/MAE-10/%ED%95%9C%EA%B8%80">MAE-10</issue> and '
                  '<issue id="cb5a5e0b-ccfc-4ec2-b547-ebf208f484a9" '
                  'href="https://linear.app/maeng/issue/MAE-11/new">MAE-11</issue>')
        workspace = 'https://linear.app/maeng'
        self.assertTrue(tool_hook.linear_description_matches(expected, actual, aliases, workspace))
        self.assertFalse(tool_hook.linear_description_matches(expected, actual, aliases))
        self.assertFalse(tool_hook.linear_description_matches(expected, actual + ' changed', aliases, workspace))
        self.assertFalse(tool_hook.linear_description_matches(expected,
                         actual.replace('cb5a5e0b-ccfc-4ec2-b547-ebf208f484a9',
                                        '4f6c608e-2e52-4e76-b968-15bc9987f5de'), aliases, workspace))
        self.assertFalse(tool_hook.linear_description_matches(expected,
                         actual.replace('/issue/MAE-11/', '/issue/MAE-12/'), aliases, workspace))
        self.assertFalse(tool_hook.linear_description_matches(expected,
                         actual.replace('/maeng/', '/endix/', 1), aliases, workspace))

    def test_native_readback_rechecks_workspace_before_and_after_dispatch(self):
        tool, args, gate = self.native_working_plan()
        read_tool, read_args = 'mcp__linear__get_issue', {'id': args['id'], 'includeRelations': True}
        self.prepare('working-fetch', 'readback', read_tool, read_args, {'write_call_id': 'working'})
        self.event('PreToolUse', tool, args)
        self.event('PostToolUse', tool, args, {'structuredContent': {'id': args['id']}})
        self.event('PostToolUse', 'mcp__linear__get_workspace', {},
                   {'structuredContent': {'id': 'different-account'}}, event_id='switched-before')
        with self.assertRaisesRegex(LedgerError, 'actual Linear workspace'):
            self.event('PreToolUse', read_tool, read_args, event_id='fetch')
        with self.assertRaisesRegex(LedgerError, 'actual Linear workspace'):
            self.prepare('new-fetch', 'readback', read_tool, read_args, {'write_call_id': 'working'})
        self.event('PostToolUse', 'mcp__linear__get_workspace', {},
                   {'structuredContent': {'id': self.dest['workspace']}}, event_id='restored')
        self.event('PreToolUse', read_tool, read_args, event_id='fetch')
        self.event('PostToolUse', 'mcp__linear__get_workspace', {},
                   {'structuredContent': {'id': 'different-account'}}, event_id='switched-after')
        result = self.event('PostToolUse', read_tool, read_args,
                            {'structuredContent': {'id': args['id']}}, event_id='fetch')
        self.assertIn('actual Linear workspace', result['reason'])
        self.assertEqual('conflict', self.call('status')['runtime_hooks']['writes']['working']['outcome'])

    def test_working_purpose_cannot_bypass_notion_verification(self):
        self.config()
        (self.project / 'payload.json').write_text(canonical({'body': 'draft'}))
        gate = {'operation_id': 'save', 'destination_id': 'saved', 'workspace': self.dest['workspace'],
                'target': self.dest['target'], 'operation': 'update', 'payload_path': 'payload.json',
                'payload_sha256': sha((self.project / 'payload.json').read_bytes()),
                'authorization_ref': self.dest['authorization_ref'], 'purpose': 'working-context'}
        with self.assertRaisesRegex(LedgerError, 'authorized personal Linear'):
            self.prepare('notion-working', 'write', 'mcp__codex_apps__notion_notion_update_page',
                         {'page_id': self.dest['target'], 'command': 'replace_content', 'new_str': 'draft'}, gate)

    def test_read_search_words_and_real_generic_mutations(self):
        for name in ('mcp__codex_apps__notion__search', 'mcp__codex_apps__notion_query_data_sources', 'mcp__linear__list_issues'):
            self.assertIsNone(tool_hook.protected(name, {'query': 'mutation'}))
        for name in ('mcp__notion__query', 'mcp__codex_apps__notion__query'):
            for query in ('mutation { deletePage }', '# comment\nmutation { deletePage }', '\ufeffmutation { deletePage }', 'query { pages }'):
                self.assertEqual('write', tool_hook.protected(name, {'query': query}))
        self.assertEqual('write', tool_hook.protected('mcp__notion__delete_page', {'id': 'page'}))

    def test_notion_page_parent_readback_uses_actual_nearest_parent(self):
        tool = 'mcp__codex_apps__notion__create_pages'
        args = {'parent': {'page_id': 'parent-id'}, 'pages': [{'properties': {'title': 'Result'}, 'content': 'Result'}]}
        self.assertEqual(('notion', 'create', 'parent-id', {'body': 'Result', 'title': 'Result'}),
                         tool_hook.request_payload(tool, args, self.project))
        value = {'metadata': {'type': 'page'}, 'url': 'https://www.notion.so/created',
                 'text': '<page>\n<ancestor-path>\n<parent-page url="https://www.notion.so/root"/>\n'
                         '<parent-page url="https://www.notion.so/parent-id"/>\n</ancestor-path>\n'
                         '<properties>\n{"title":"Result"}\n</properties>\n<content>\nResult\n</content>\n</page>'}
        parsed = tool_hook.response_value({'structuredContent': value})
        self.assertEqual('https://www.notion.so/parent-id', parsed['notion_parent'])
        write = {'service': 'notion', 'tool_name': tool, 'created_resource': 'created',
                 'gate': {'operation': 'create', 'target': 'parent-id', 'payload_path': str(self.project / 'expected.json')}}
        (self.project / 'expected.json').write_text(canonical({'body': 'Result', 'title': 'Result'}))
        tool_hook.actual_payload(write, args, 'mcp__codex_apps__notion_fetch', {'id': 'created'}, {'structuredContent': value})
        with self.assertRaisesRegex(LedgerError, 'identity mismatch'):
            tool_hook.actual_payload(write, args, 'mcp__codex_apps__notion_fetch', {'id': 'created'},
                                     {'structuredContent': {**value, 'text': value['text'].replace('/parent-id', '/wrong')}})
    def setUp(self):
        test_run.ProjectRunnerTests.setUp(self)
        patcher = patch.object(tool_hook, "SESSIONS", self.root / "sessions")
        patcher.start()
        self.addCleanup(patcher.stop)
    call = test_run.ProjectRunnerTests.call
    ready = test_run.ProjectRunnerTests.ready

    def event(self, name, tool, args=None, response=None, event_id='call-1', **extra):
        return tool_hook.handle({'hook_event_name': name, 'cwd': str(self.project),
                                'session_id': 'fixture-coordinator', 'tool_use_id': event_id,
                                'tool_name': tool, 'tool_input': args or {},
                                'tool_response': response, **extra})

    def config(self, service='notion'):
        execute(self.project, 'start', self.request)
        self.dest = {'id': 'saved', 'service': service, 'workspace': 'fixture-space',
                     'target': ('https://github.com/example/private/issues/7' if service == 'github' else 'fixture-resource'), 'output_owner': 'personal',
                     'operations': ['update'], 'authorization_ref': 'fixture:authorized'}
        self.call('configure-hooks', output_owner='personal', destinations=[self.dest],
                  write_paths=['output'], requirements=[])

    def prepare(self, call_id, kind, tool, args, gate, **extra):
        path = call_id + '.json'
        (self.project / path).write_text(canonical(args))
        return self.call('prepare-tool', call_id=call_id, kind=kind, tool_name=tool,
                         input_path=path, gate=gate, **extra)

    def write_plan(self, service='notion', tool=None, args=None, body='reviewed content'):
        self.config(service); self.ready(complete=False)
        payload = {'description' if service == 'linear' else 'body': body}
        (self.project / 'payload.json').write_text(canonical(payload))
        names = {'notion': ('notion_notion_update_page', 'notion_fetch'),
                 'linear': ('linear_save_issue', 'linear_get_issue'),
                 'github': ('github_update_issue', 'github_fetch_issue')}
        write_args = {
            'notion': {'page_id': self.dest['target'], 'command': 'replace_content',
                       'new_str': body},
            'linear': {'id': self.dest['target'], 'link_id': self.dest['workspace'], **payload},
            'github': {'repository_full_name': 'example/private', 'issue_number': 7, **payload},
        }
        self.write_tool = tool or 'mcp__codex_apps__' + names[service][0]
        self.write_args = args or write_args[service]
        gate = {'operation_id': 'save', 'destination_id': 'saved', 'workspace': self.dest['workspace'],
                'target': self.dest['target'], 'operation': 'update', 'payload_path': 'payload.json',
                'payload_sha256': sha(canonical(payload).encode()), 'authorization_ref': self.dest['authorization_ref']}
        self.prepare('save-call', 'write', self.write_tool, self.write_args, gate)
        self.read_tool = 'mcp__codex_apps__' + names[service][1]
        self.read_args = {
            'notion': {'id': self.dest['target']},
            'linear': {'id': self.dest['target'], 'link_id': self.dest['workspace']},
            'github': {'repository_full_name': 'example/private', 'issue_number': 7},
        }[service]
        self.prepare('fetch-call', 'readback', self.read_tool, self.read_args,
                     {'write_call_id': 'save-call'})
        return payload

    def do_write(self):
        pre = self.event('PreToolUse', self.write_tool, self.write_args)
        self.assertEqual('allow', pre['hookSpecificOutput']['permissionDecision'])
        self.event('PostToolUse', self.write_tool, self.write_args, {'isError': True, 'error': 'synthetic timeout'})

    def read_response(self, target=None, body='reviewed content'):
        target = self.dest['target'] if target is None else target
        service = self.dest['service']
        if service == 'notion':
            value = {'metadata': {'type': 'page'},
                     'url': 'https://app.notion.com/p/' + target + '?pvs=204',
                     'text': '<page>\n<properties>\n{}\n</properties>\n<content>\n'
                             + body + '\n</content>\n</page>'}
            return {'content': [{'type': 'text', 'text': json.dumps(value)}]}
        if service == 'linear':
            return {'structuredContent': {'id': target, 'identifier': 'FIX-7', 'description': body}}
        return {'content': [{'type': 'text', 'text': json.dumps({'html_url': target, 'body': body})}]}

    def fetch(self, response, event_id='fetch-1'):
        self.event('PreToolUse', self.read_tool, self.read_args, event_id=event_id)
        return self.event('PostToolUse', self.read_tool, self.read_args, response, event_id=event_id)

    def test_ordinary_tools_and_other_sessions_are_not_gated(self):
        self.assertEqual({}, self.event('PreToolUse', 'mcp__codex_apps__notion_notion_update_page', {'id': 'x'}))
        self.config()
        self.assertEqual({}, self.event('PreToolUse', 'mcp__codex_apps__notion_fetch', {'id': 'x'}))
        self.assertEqual({}, self.event('PreToolUse', 'mcp__codex_apps__notion_notion_update_page', {'id': 'x'}, session_id='other-session'))

    def test_unprepared_writes_and_delegations_are_denied(self):
        execute(self.project, 'start', self.request)
        for tool, args in [('mcp__codex_apps__notion_notion_update_page', {'id': 'x'}),
                           ('mcp__codex_apps__linear_save_issue', {}), ('mcp__codex_apps__github_create_issue', {}),
                           ('Bash', {'command': 'git push origin HEAD'}),
                           ('Bash', {'command': 'gh api repos/example/private/issues -X POST'}),
                           ('multi_agent_v1__spawn_agent', {'message': 'scope missing'})]:
            self.assertEqual('deny', self.event('PreToolUse', tool, args)['hookSpecificOutput']['permissionDecision'])

    def test_automatic_write_and_actual_readback_for_three_services(self):
        for service in ('notion', 'linear', 'github'):
            with self.subTest(service=service):
                # A separate temporary project for each service, no task policy mutation.
                if service != 'notion':
                    self.setUp()
                payload = self.write_plan(service)
                with self.assertRaisesRegex(LedgerError, 'incomplete'):
                    self.call('complete')
                self.do_write()
                self.assertEqual('uncertain', self.call('status')['runtime_hooks']['writes']['save']['outcome'])
                with self.assertRaisesRegex(LedgerError, 'reconcile'):
                    self.event('PreToolUse', self.write_tool, self.write_args, event_id='repeat-write')
                self.fetch(self.read_response())
                self.assertEqual('verified', self.call('status')['runtime_hooks']['writes']['save']['outcome'])
                self.assertEqual('done', self.call('complete')['stage'])

    def test_added_notion_links_verify_without_hiding_text_drift(self):
        self.write_plan(); self.do_write()
        response = self.read_response(body='[reviewed](https://example.com) content')
        self.fetch(response)
        self.assertEqual('verified', self.call('status')['runtime_hooks']['writes']['save']['outcome'])
        self.assertEqual('block', self.fetch(self.read_response(body='[changed](https://example.com) content'),
                                           'changed-read')['decision'])

    def test_legacy_normalized_payload_cannot_override_raw_approved_body(self):
        self.write_plan(body='    a\n\n    b'); self.do_write()
        write = self.call('status')['runtime_hooks']['tool_calls']['save-call']
        legacy = self.project / 'legacy-payload.json'
        legacy.write_text(canonical({'body': '    a\n    b'}))
        write['gate']['payload_path'] = str(legacy)
        with self.assertRaisesRegex(LedgerError, 'write readback mismatch'):
            tool_hook.actual_payload(write, self.write_args, self.read_tool, self.read_args,
                                     self.read_response(body='    a\n    b'))
        content = tool_hook.actual_payload(write, self.write_args, self.read_tool, self.read_args,
                                           self.read_response(body='    a\n\n    b'))
        self.assertEqual(canonical({'body': '    a\n    b'}).encode(), content)

    def test_notion_code_blanks_survive_request_and_readback_normalization(self):
        self.write_plan(body='    a\n\n    b'); self.do_write()
        result = self.fetch(self.read_response(body='    a\n    b'))
        self.assertEqual('block', result['decision'])
        self.assertEqual('conflict', self.call('status')['runtime_hooks']['writes']['save']['outcome'])
        self.fetch(self.read_response(body='    a\n\n    b'), 'correct-code')
        self.assertEqual('verified', self.call('status')['runtime_hooks']['writes']['save']['outcome'])

    def test_mismatched_readback_blocks_then_real_reconciliation_succeeds(self):
        self.write_plan(); self.do_write()
        result = self.fetch(self.read_response(target='wrong-resource'))
        self.assertEqual('block', result['decision'])
        self.assertEqual('conflict', self.call('status')['runtime_hooks']['writes']['save']['outcome'])
        with self.assertRaisesRegex(LedgerError, 'incomplete'):
            self.call('complete')
        self.assertEqual('block', self.fetch(self.read_response(body='wrong'), 'fetch-2')['decision'])
        self.fetch(self.read_response(), 'fetch-3')
        self.assertEqual('done', self.call('complete')['stage'])

    def test_exact_input_immutability_and_post_event_identity(self):
        self.write_plan()
        self.assertEqual('deny', self.event('PreToolUse', self.write_tool, {**self.write_args, 'id': 'other'})['hookSpecificOutput']['permissionDecision'])
        with self.assertRaisesRegex(LedgerError, 'no matching pre-tool'):
            self.event('PostToolUse', self.write_tool, self.write_args, {}, event_id='not-admitted')
        (self.project / 'save-call.json').write_text('changed')
        with self.assertRaisesRegex(LedgerError, 'input changed'):
            self.event('PreToolUse', self.write_tool, self.write_args)

    def test_replayed_pre_and_post_events_are_idempotent(self):
        self.write_plan()
        self.event('PreToolUse', self.write_tool, self.write_args)
        self.event('PreToolUse', self.write_tool, self.write_args)
        response = {'ok': True}
        self.event('PostToolUse', self.write_tool, self.write_args, response)
        self.event('PostToolUse', self.write_tool, self.write_args, response)
        self.assertEqual(1, self.call('status')['runtime_hooks']['writes']['save']['attempt'])
        with self.assertRaisesRegex(LedgerError, 'event changed'):
            self.event('PostToolUse', self.write_tool, self.write_args, {'ok': False})

    def test_delegation_contract_injection_and_final_wait_result(self):
        self.config(); self.ready(complete=False)
        args = {'message': 'Read-only independent review', 'fork_context': False}
        gate = {'delegation_id': 'reviewer', 'role': 'reviewer', 'description': 'check artifact',
                'acceptance': ['Grounded actions'], 'write_paths': [], 'refs': ['fixture:source']}
        self.prepare('review-call', 'delegate', 'spawn_agent', args, gate)
        pre = self.event('PreToolUse', 'multi_agent_v1__spawn_agent', args)
        updated = pre['hookSpecificOutput']['updatedInput']
        self.assertIn('HARNESS_CONTRACT', updated['message'])
        self.assertIn('authorization_scope', updated['message'])
        self.assertEqual({}, self.event('SubagentStop', ''))
        self.event('PostToolUse', 'spawn_agent', updated, {'agent_id': 'actual-reviewer'})
        # SubagentStop may still be continued by another hook, so it is not final proof.
        self.event('SubagentStop', '', agent_id='actual-reviewer', last_assistant_message='draft')
        receipt = self.call('status')['runtime_hooks']['tool_calls']['review-call']['subagent_stop']
        self.assertEqual('actual-reviewer', receipt['agent_id'])
        self.event('SubagentStop', '', agent_id='actual-reviewer', last_assistant_message='draft')
        self.assertEqual(receipt, self.call('status')['runtime_hooks']['tool_calls']['review-call']['subagent_stop'])
        with self.assertRaisesRegex(LedgerError, 'incomplete'):
            self.call('complete')
        self.event('PostToolUse', 'multi_agent_v1__wait_agent', response={'status': {'actual-reviewer': {'completed': 'Independent result'}}}, event_id='wait-1')
        self.assertEqual('finished', self.call('status')['runtime_hooks']['delegations']['reviewer']['outcome'])
        self.assertEqual('done', self.call('complete')['stage'])

    def test_notion_native_fetch_envelope_uses_actual_body_and_properties(self):
        raw = {'content': [{'type': 'text', 'text': json.dumps({
            'metadata': {'type': 'page'}, 'url': 'https://app.notion.com/p/real-id?pvs=204',
            'text': '<page>\n<parent-data-source url="collection://real-parent"/>\n<properties>\n{"Task ID":"real-task"}\n</properties>\n<content>\n## Result\n\nActual saved content\n</content>\n</page>'})}]}
        value = tool_hook.response_value(raw)
        self.assertEqual('https://app.notion.com/p/real-id', value['notion_target'])
        self.assertEqual('collection://real-parent', value['notion_parent'])
        self.assertEqual('## Result\nActual saved content', value['notion_body'])
        self.assertEqual({'Task ID': 'real-task'}, value['notion_properties'])
        changed = json.loads(raw['content'][0]['text']); changed['truncated'] = True
        with self.assertRaisesRegex(LedgerError, 'incomplete'):
            tool_hook.response_value({'structuredContent': changed})

    def test_bound_worktree_remains_gated_when_hook_cwd_is_elsewhere(self):
        self.config()
        tool_hook.bind_session(self.project, 'same-id', 'fixture-coordinator')
        event = {'hook_event_name': 'PreToolUse', 'cwd': str(self.root),
                 'session_id': 'fixture-coordinator', 'tool_use_id': 'call-other-cwd',
                 'tool_name': 'mcp__codex_apps__notion_notion_update_page', 'tool_input': {'id': 'x'}}
        self.assertEqual('deny', tool_hook.handle(event)['hookSpecificOutput']['permissionDecision'])
        self.assertEqual('block', tool_hook.handle({**event, 'hook_event_name': 'Stop'})['decision'])

    def test_verified_resource_drift_blocks_completion_and_good_refetch_is_idempotent(self):
        self.write_plan(); self.do_write()
        self.fetch(self.read_response())
        self.fetch(self.read_response(), 'repeat-fetch')
        self.assertEqual('block', self.fetch(self.read_response(body='changed remotely'), 'drift-fetch')['decision'])
        self.assertEqual('blocked', self.call('status')['stage'])
        with self.assertRaisesRegex(LedgerError, 'blocked'):
            self.call('complete')

    def test_positive_absence_allows_retry_but_timeout_does_not(self):
        self.write_plan(); self.do_write()
        (self.project / 'absence.txt').write_text('synthetic reliable absence fixture')
        self.call('after-write', operation_id='save', attempt=1, workspace='fixture-space',
                  target='fixture-resource', outcome='absent', evidence_path='absence.txt')
        self.event('PreToolUse', self.write_tool, self.write_args, event_id='retry-call')
        self.assertEqual(2, self.call('status')['runtime_hooks']['writes']['save']['attempt'])

    def test_resolved_old_write_is_superseded_after_repair_without_hiding_uncertain_write(self):
        self.write_plan(); self.do_write()
        self.fetch(self.read_response())
        self.call('repair', reason_ref='fixture:revision')
        (self.project / 'summary.md').write_text('repaired artifact')
        digest = self.call('artifact', path='summary.md', worker_id='fixture-worker')['artifact']['sha256']
        self.call('check', artifact_sha256=digest, evidence_path='check.txt', check_id='fixture', agent_id='fixture-worker', exit_code=0)
        self.call('review', artifact_sha256=digest, evidence_path='review.txt', agent_id='fixture-reviewer', verdict='approved', covered_conditions=[0])
        self.assertEqual('superseded', self.call('status')['runtime_hooks']['tool_calls']['save-call']['phase'])
        gate = self.call('status')['runtime_hooks']['tool_calls']['save-call']['gate']
        self.prepare('new-save-call', 'write', self.write_tool, self.write_args, {**gate, 'operation_id': 'new-save'})
        self.event('PreToolUse', self.write_tool, self.write_args, event_id='new-save-event')
        with self.assertRaisesRegex(LedgerError, 'incomplete'):
            self.call('complete')

    def test_native_connector_namespace_matches_normalized_plan(self):
        self.write_plan()
        write_name = 'mcp__codex_apps__notion__notion_update_page'
        read_name = 'mcp__codex_apps__notion__fetch'
        pre = self.event('PreToolUse', write_name, self.write_args)
        self.assertEqual('allow', pre['hookSpecificOutput']['permissionDecision'])
        self.event('PostToolUse', write_name, self.write_args, {'ok': True})
        self.event('PreToolUse', read_name, self.read_args, event_id='native-fetch')
        self.event('PostToolUse', read_name, self.read_args, self.read_response(), event_id='native-fetch')
        self.assertEqual('verified', self.call('status')['runtime_hooks']['writes']['save']['outcome'])
        self.assertEqual('mcp__codex_apps__linear_save_issue',
                         tool_hook.tool_name('mcp__codex_apps__linear__save_issue'))
        self.assertEqual('mcp__codex_apps__github_update_issue',
                         tool_hook.tool_name('mcp__codex_apps__github__update_issue'))

    def test_native_json_text_preserves_delegation_readback_and_error_flags(self):
        self.config(); self.ready(complete=False)
        args = {'message': 'Read-only review', 'fork_context': False}
        gate = {'delegation_id': 'reviewer', 'role': 'reviewer', 'description': 'native JSON response',
                'acceptance': ['Confirm actual result'], 'write_paths': [], 'refs': []}
        self.prepare('review-call', 'delegate', 'spawn_agent', args, gate)
        pre = self.event('PreToolUse', 'spawn_agent', args)
        self.event('PostToolUse', 'spawn_agent', pre['hookSpecificOutput']['updatedInput'],
                   json.dumps({'agent_id': 'actual-reviewer', 'nickname': 'fixture'}))
        self.event('PostToolUse', 'multi_agent_v1wait_agent', response=json.dumps({'status': {
            'actual-reviewer': {'completed': 'Actual final result'}}}), event_id='native-wait')
        self.assertEqual('finished', self.call('status')['runtime_hooks']['delegations']['reviewer']['outcome'])
        self.setUp(); self.write_plan(); self.do_write()
        failed = self.read_response(); failed['isError'] = True
        self.assertEqual('block', self.fetch(json.dumps(failed), 'failed-native-read')['decision'])
        self.fetch(json.dumps(self.read_response()), 'native-read')
        self.assertEqual('verified', self.call('status')['runtime_hooks']['writes']['save']['outcome'])

    def test_final_wait_preserves_prior_explicit_reconciliation(self):
        self.config(); self.ready(complete=False)
        args = {'message': 'Read-only review', 'fork_context': False}
        gate = {'delegation_id': 'reviewer', 'role': 'reviewer', 'description': 'reconciliation',
                'acceptance': ['Confirm result'], 'write_paths': [], 'refs': []}
        self.prepare('review-call', 'delegate', 'spawn_agent', args, gate)
        pre = self.event('PreToolUse', 'spawn_agent', args)
        self.event('PostToolUse', 'spawn_agent', pre['hookSpecificOutput']['updatedInput'],
                   {'agent_id': 'actual-reviewer'})
        sibling = {'task_id': 'blocked-sibling', 'owner': 'fixture-coordinator'}
        execute(self.project, 'start', {**self.request, **sibling})
        execute(self.project, 'configure-hooks', {**sibling, 'output_owner': 'personal',
                'destinations': [], 'write_paths': [], 'requirements': []})
        execute(self.project, 'block', {**sibling, 'kind': 'requirements', 'reason_ref': 'actual blocker'})
        response = {'status': {'actual-reviewer': {'completed': 'Actual final result'}}}
        self.event('PostToolUse', 'wait', response=response, event_id='exec-cell-wait')
        self.assertEqual('pending', self.call('status')['runtime_hooks']['delegations']['reviewer']['outcome'])
        self.event('PostToolUse', 'wait_agent', response={'status': {}, 'timed_out': True}, event_id='timeout')
        self.assertEqual('pending', self.call('status')['runtime_hooks']['delegations']['reviewer']['outcome'])
        path = self.project / 'actual-final.json'
        path.write_text(json.dumps(response))
        self.call('after-delegate', delegation_id='reviewer', agent_id='actual-reviewer',
                  outcome='finished', evidence_path=str(path))
        recorded = self.call('status')['runtime_hooks']['delegations']['reviewer']
        self.event('PostToolUse', 'wait_agent', response=response, event_id='later-wait')
        self.assertEqual(recorded, self.call('status')['runtime_hooks']['delegations']['reviewer'])
        self.assertEqual('blocked', execute(self.project, 'status', {'task_id': sibling['task_id']})['stage'])

    def test_malformed_wire_input_fails_closed(self):
        for raw in ('{', 'x' * (2 * 1024 * 1024 + 1)):
            with self.subTest(raw_size=len(raw)), patch('sys.stdin', io.StringIO(raw)), patch('sys.stderr', io.StringIO()):
                with self.assertRaises(SystemExit) as stopped:
                    tool_hook.main()
                self.assertEqual(2, stopped.exception.code)

    def test_invalid_plan_does_not_create_an_immutable_obligation(self):
        self.config(); self.ready(complete=False)
        args = {'message': 'bad reviewer scope'}
        gate = {'delegation_id': 'bad', 'role': 'reviewer', 'description': 'review',
                'acceptance': ['check'], 'write_paths': ['output'], 'refs': []}
        with self.assertRaisesRegex(LedgerError, 'read-only'):
            self.prepare('bad-call', 'delegate', 'spawn_agent', args, gate)
        self.assertNotIn('bad-call', self.call('status')['runtime_hooks'].get('tool_calls', {}))

    def test_wrong_gate_target_content_or_service_is_denied(self):
        self.write_plan()
        original = self.call('status')['runtime_hooks']['tool_calls']['save-call']['gate']
        cases = [({'target': 'wrong-resource'}, 'resource|target|destination'),
                 ({'payload_sha256': sha(b'wrong content')}, 'content|payload'),
                 ({}, 'service')]
        for index, (changes, message) in enumerate(cases):
            with self.subTest(index=index):
                tool, args = self.write_tool, self.write_args
                if index == 2:
                    tool = 'mcp__codex_apps__linear_save_issue'
                    args = {'id': self.dest['target'], 'link_id': self.dest['workspace'],
                            'description': 'reviewed content'}
                gate = {**original, **changes, 'operation_id': 'bad-' + str(index)}
                with self.assertRaisesRegex(LedgerError, message):
                    self.prepare('bad-' + str(index), 'write', tool, args, gate)
                self.assertNotIn('bad-' + str(index),
                                 self.call('status')['runtime_hooks']['tool_calls'])

    def test_linear_update_cannot_change_unreviewed_team(self):
        with self.assertRaisesRegex(LedgerError, 'unreviewed team'):
            self.write_plan('linear', args={'id': 'fixture-resource', 'link_id': 'fixture-space',
                                           'description': 'reviewed content', 'team': 'unauthorized-team'})

    def test_local_echo_readback_and_custom_projection_are_denied(self):
        self.write_plan()
        with self.assertRaisesRegex(LedgerError, 'authoritative'):
            self.prepare('echo-read', 'readback', 'exec_command',
                         {'cmd': 'echo "reviewed content"', 'workdir': str(self.project)},
                         {'write_call_id': 'save-call'})
        with self.assertRaisesRegex(LedgerError, 'invalid readback gate'):
            self.prepare('projection-read', 'readback', self.read_tool, self.read_args,
                         {'write_call_id': 'save-call', 'projection': {'body': ['body']}})
        calls = self.call('status')['runtime_hooks']['tool_calls']
        self.assertNotIn('echo-read', calls)
        self.assertNotIn('projection-read', calls)

    def test_matching_readback_with_is_error_remains_blocked(self):
        for service in ('notion', 'linear', 'github'):
            with self.subTest(service=service):
                if service != 'notion':
                    self.setUp()
                self.write_plan(service); self.do_write()
                response = {**self.read_response(), 'isError': True}
                result = self.fetch(response)
                self.assertEqual('block', result['decision'])
                self.assertIn('failed', result['reason'])
                self.assertEqual('conflict', self.call('status')['runtime_hooks']['writes']['save']['outcome'])
                with self.assertRaisesRegex(LedgerError, 'incomplete'):
                    self.call('complete')

    def test_shell_workdir_and_other_arguments_are_retained(self):
        args = {'cmd': 'gh api repos/example/private/issues/7',
                'workdir': str(self.project), 'yield_time_ms': 1000}
        normalized = tool_hook.arguments('functions__exec_command', args)
        self.assertEqual(normalized, {'command': args['cmd'], 'workdir': args['workdir'],
                                      'yield_time_ms': 1000})
        elsewhere = tool_hook.arguments('exec_command', {**args, 'workdir': str(self.root)})
        self.assertNotEqual(sha(canonical(normalized).encode()), sha(canonical(elsewhere).encode()))
        self.assertEqual(tool_hook.arguments('Bash', normalized), normalized)

    def test_attached_gh_api_mutator_flags_are_protected(self):
        self.config()
        for flag in ('-fbody=changed', '-Fbody=@payload.json', '--field=body=changed',
                     '--raw-field=body=changed', '--input=payload.json', '-XPOST',
                     '-XPATCH', '-XPUT', '-XDELETE', '--method=PATCH'):
            with self.subTest(flag=flag):
                args = {'command': 'gh api repos/example/private/issues/7 ' + flag}
                self.assertEqual('write', tool_hook.protected('Bash', args))
                self.assertEqual('deny', self.event('PreToolUse', 'Bash', args)
                                 ['hookSpecificOutput']['permissionDecision'])
        self.assertIsNone(tool_hook.protected('Bash',
                          {'command': 'gh api repos/example/private/issues/7'}))

    def test_pr_creation_uses_actual_pr_readback(self):
        execute(self.project, 'start', self.request)
        dest = {'id': 'pr', 'service': 'github', 'workspace': 'example/private',
                'target': 'https://github.com/example/private/pulls', 'output_owner': 'personal',
                'operations': ['create'], 'authorization_ref': 'fixture:approved-pr'}
        self.call('configure-hooks', output_owner='personal', destinations=[dest],
                  write_paths=['output'], requirements=[])
        self.ready(complete=False)
        args = {'repository_full_name': 'example/private', 'base': 'feat/harness-v1',
                'head': 'feat/harness-github-flow', 'title': 'Fix GitHub delivery',
                'body': 'Linked to personal Linear work.', 'draft': True}
        payload = {k: args[k] for k in ('base', 'head', 'title', 'body', 'draft')}
        (self.project / 'pr-payload.json').write_text(canonical(payload))
        gate = {'operation_id': 'pr-create', 'destination_id': 'pr', 'workspace': dest['workspace'],
                'target': dest['target'], 'operation': 'create', 'payload_path': 'pr-payload.json',
                'payload_sha256': sha(canonical(payload).encode()),
                'authorization_ref': dest['authorization_ref']}
        tool = 'mcp__codex_apps__github_create_pull_request'
        read_tool = 'mcp__codex_apps__github_fetch_pr'
        read_args = {'repo_full_name': 'example/private', 'pr_number': 9}
        self.prepare('create-pr', 'write', tool, args, gate, expected_head_sha='a' * 40)
        self.event('PreToolUse', tool, args)
        self.event('PostToolUse', tool, args, {'structuredContent': {'pull_request': {'number': 9}}})
        self.prepare('fetch-pr', 'readback', read_tool, read_args, {'write_call_id': 'create-pr'})
        self.event('PreToolUse', read_tool, read_args, event_id='pr-read')
        observed = {'pull_request': {'number': 9, 'url': 'https://github.com/example/private/pull/9',
                    'head': args['head'], 'head_sha': 'a' * 40, 'base': args['base'],
                    'title': args['title'], 'body': args['body'], 'draft': True}}
        self.event('PostToolUse', read_tool, read_args,
                   {'structuredContent': observed}, event_id='pr-read')
        self.assertEqual('verified', self.call('status')['runtime_hooks']['writes']['pr-create']['outcome'])

    def test_concurrent_readback_admission_is_denied(self):
        self.write_plan(); self.do_write()
        barrier = Barrier(2)
        def admit(event_id):
            barrier.wait(timeout=5)
            try:
                return self.event('PreToolUse', self.read_tool, self.read_args,
                                  event_id=event_id)
            except LedgerError as error:
                return str(error)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(admit, ('read-a', 'read-b')))
        allowed = [result for result in results if isinstance(result, dict)]
        denied = [result for result in results if isinstance(result, str)]
        self.assertEqual(len(allowed), 1)
        self.assertEqual(allowed[0]['hookSpecificOutput']['permissionDecision'], 'allow')
        self.assertEqual(len(denied), 1)
        self.assertIn('concurrent tool admission denied', denied[0])
        admitted = self.call('status')['runtime_hooks']['tool_calls']['fetch-call']['event_id']
        self.event('PostToolUse', self.read_tool, self.read_args,
                   self.read_response(), event_id=admitted)
        self.assertEqual('verified', self.call('status')['runtime_hooks']['writes']['save']['outcome'])

    def test_notion_create_readback_binds_returned_page_and_matches_payload(self):
        execute(self.project, 'start', self.request)
        parent = '22222222-2222-2222-2222-222222222222'
        created = '11111111-1111-1111-1111-111111111111'
        target = 'collection://' + parent
        self.call('configure-hooks', output_owner='personal', destinations=[{
            'id': 'saved', 'service': 'notion', 'workspace': 'fixture-space',
            'target': target, 'output_owner': 'personal', 'operations': ['create'],
            'authorization_ref': 'fixture:authorized'}], write_paths=['output'], requirements=[])
        self.ready(complete=False)
        properties = {'title': 'Result', 'Task ID': 'same-id'}
        payload = {'body': '## Result\nReviewed created content', **properties}
        (self.project / 'create-payload.json').write_text(canonical(payload))
        tool = 'mcp__codex_apps__notion_notion_create_pages'
        args = {'parent': {'data_source_id': parent}, 'pages': [{
            'properties': properties, 'content': '## Result\n\nReviewed created content'}]}
        self.prepare('create-call', 'write', tool, args, {
            'operation_id': 'create', 'destination_id': 'saved', 'workspace': 'fixture-space',
            'target': target, 'operation': 'create', 'payload_path': 'create-payload.json',
            'payload_sha256': sha(canonical(payload).encode()),
            'authorization_ref': 'fixture:authorized'})
        read_tool = 'mcp__codex_apps__notion_fetch'
        read_args = {'id': created}
        gate = {'write_call_id': 'create-call'}
        with self.assertRaisesRegex(LedgerError, 'created resource ID unavailable'):
            self.prepare('early-fetch', 'readback', read_tool, read_args, gate)
        self.assertEqual('allow', self.event('PreToolUse', tool, args)
                         ['hookSpecificOutput']['permissionDecision'])
        self.event('PostToolUse', tool, args, {'content': [{'type': 'text', 'text': json.dumps({
            'pages': [{'id': created, 'url': 'https://www.notion.so/' + created}]})}]})
        calls = self.call('status')['runtime_hooks']['tool_calls']
        self.assertEqual(created, calls['create-call']['created_resource'])
        with self.assertRaisesRegex(LedgerError, 'actual created page'):
            self.prepare('wrong-fetch', 'readback', read_tool,
                         {'id': '33333333-3333-3333-3333-333333333333'}, gate)
        self.prepare('created-fetch', 'readback', read_tool, read_args, gate)
        calls = self.call('status')['runtime_hooks']['tool_calls']
        self.assertNotIn('early-fetch', calls)
        self.assertNotIn('wrong-fetch', calls)
        self.assertEqual('allow', self.event('PreToolUse', read_tool, read_args,
                                           event_id='created-read')
                         ['hookSpecificOutput']['permissionDecision'])
        response = {'content': [{'type': 'text', 'text': json.dumps({
            'metadata': {'type': 'page'}, 'url': 'https://app.notion.com/p/' + created,
            'text': '<page>\n<parent-data-source url="' + target + '"/>\n<properties>\n'
                    + json.dumps(properties) + '\n</properties>\n<content>\n'
                    + '## Result\n\nReviewed created content\n</content>\n</page>'})}]}
        result = self.event('PostToolUse', read_tool, read_args, response,
                            event_id='created-read')
        self.assertNotEqual('block', result.get('decision'))
        self.assertEqual('verified', self.call('status')['runtime_hooks']['writes']['create']['outcome'])
        self.assertEqual('done', self.call('complete')['stage'])

    def test_stop_checks_local_tasks_and_is_bounded(self):
        self.config()
        result = self.event('Stop', '')
        self.assertEqual('block', result['decision'])
        self.assertIn('systemMessage', self.event('Stop', '', stop_hook_active=True))
        self.ready()
        self.assertEqual({}, self.event('Stop', ''))


if __name__ == '__main__':
    unittest.main()
