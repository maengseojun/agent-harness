"""Synthetic hook wire fixtures; no live services, agents, or user settings."""
import json
import io
import os
import stat
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
import test_run
import tool_hook
import work_records
from ledger import LedgerError, canonical, sha
from run import execute


class ToolHookTests(unittest.TestCase):
    def test_convert_page_to_skill_is_protected_under_both_notion_names(self):
        for name in ('mcp__codex_apps__notion_notion_convert_page_to_skill',
                     'mcp__notion__convert_page_to_skill'):
            with self.subTest(name=name):
                args = {'page_url': 'https://app.notion.com/p/' + 'a' * 32}
                self.assertEqual('write', tool_hook.protected(name, args))
                self.assertTrue(work_records.notion_write(name, args))
                self.assertEqual('deny', work_records.handle({
                    'hook_event_name': 'PreToolUse', 'session_id': 'fixture-coordinator',
                    'tool_use_id': 'unapproved', 'tool_name': name, 'tool_input': args},
                    self.root / 'unapproved-records')['hookSpecificOutput']['permissionDecision'])

    def test_unsupported_notion_operations_never_become_task_obligations(self):
        self.config(); self.ready(complete=False)
        cases = [
            ('create_file_upload', {'filename': 'diagram.png'}),
            ('create_attachment', {'filename': 'diagram.svg', 'content': '<svg/>'}),
            ('create_database', {'parent': {'page_id': self.dest['target']}, 'schema': 'CREATE TABLE ("Name" TITLE)'}),
            ('create_folder', {'parent': {'page_id': self.dest['target']}, 'title': 'Files'}),
            ('update_data_source', {'data_source_id': self.dest['target']}),
            ('update_folder', {'folder_id': self.dest['target']}),
            ('create_view', {'database_id': self.dest['target'], 'data_source_id': 'source', 'name': 'All', 'type': 'table'}),
            ('update_view', {'view_id': 'different-target', 'name': 'All'}),
            ('move_pages', {'new_parent': {'page_id': self.dest['target']}, 'page_or_database_ids': ['page']}),
            ('duplicate_page', {'page_id': self.dest['target']}),
            ('create_comment', {'page_id': self.dest['target'], 'markdown': 'Comment'}),
            ('convert_page_to_skill', {'page_url': self.dest['target']}),
            ('update_page', {'page_id': self.dest['target'], 'command': 'update_properties', 'icon': '⭐'}),
            ('update_page', {'page_id': self.dest['target'], 'command': 'replace_content', 'new_str': 'Body', 'cover': 'https://example.com/image.png'}),
            ('update_page', {'page_id': self.dest['target'], 'command': 'insert_content', 'content': 'Body', 'position': {'type': 'end'}}),
            ('update_page', {'page_id': self.dest['target'], 'command': 'apply_template', 'template_id': 'template'}),
            ('update_page', {'page_id': self.dest['target'], 'command': 'update_verification', 'verification_status': 'verified'}),
        ]
        for endpoint, args in cases:
            with self.subTest(endpoint=endpoint, args=args):
                tool = 'mcp__codex_apps__notion_notion_' + endpoint
                path = self.project / 'unsupported-payload.json'
                path.write_text(canonical(args))
                gate = {'operation_id': 'unsupported', 'destination_id': self.dest['id'],
                        'workspace': self.dest['workspace'], 'target': self.dest['target'],
                        'operation': 'update', 'payload_path': str(path),
                        'payload_sha256': sha(path.read_bytes()), 'authorization_ref': self.dest['authorization_ref']}
                with self.assertRaisesRegex(LedgerError, 'no native provider readback adapter; write blocked'):
                    self.prepare('unsupported', 'write', tool, args, gate)
                self.assertEqual('deny', self.event('PreToolUse', tool, args)
                                 ['hookSpecificOutput']['permissionDecision'])
                hooks = self.call('status')['runtime_hooks']
                self.assertNotIn('unsupported', hooks.get('tool_calls', {}))
                self.assertEqual({}, hooks['writes'])

    def test_notion_task_target_is_derived_from_actual_input(self):
        self.config(); self.ready(complete=False)
        path = self.project / 'target-payload.json'
        path.write_text(canonical({'title': 'Approved title'}))
        gate = {'operation_id': 'target', 'destination_id': self.dest['id'],
                'workspace': self.dest['workspace'], 'target': self.dest['target'],
                'operation': 'update', 'payload_path': str(path),
                'payload_sha256': sha(path.read_bytes()), 'authorization_ref': self.dest['authorization_ref']}
        with self.assertRaisesRegex(LedgerError, 'actual write resource mismatch'):
            self.prepare('wrong-target', 'write', 'mcp__codex_apps__notion_notion_update_page',
                         {'page_id': 'different-target', 'command': 'update_properties',
                          'properties': {'title': 'Approved title'}}, gate)
        self.assertEqual({}, self.call('status')['runtime_hooks']['writes'])

    def test_unsupported_task_write_does_not_consume_record_approval(self):
        self.config(); self.ready(complete=False)
        base = self.root / 'blocked-records'
        draft = self.project / 'view-draft.md'
        draft.write_text('Rename the approved view to All.')
        tool = 'mcp__codex_apps__notion_notion_update_view'
        args = {'view_id': self.dest['target'], 'name': 'All'}
        candidate = work_records.dispatch({
            'action': 'propose', 'session_id': 'fixture-coordinator', 'task_id': 'same-id',
            'result_key': 'view', 'record_kind': 'operation', 'draft_path': str(draft),
            'linear_refs': [], 'completion_basis': 'fixture', 'notion_target': self.dest['target'],
            'endix': False, 'tool_name': tool, 'tool_input': args,
            'expected_state': {'name': 'All'}}, base)
        revision = candidate['revisions'][-1]
        ids = {'session_id': 'fixture-coordinator', 'candidate_id': candidate['candidate_id'],
               'revision_id': revision['revision_id']}
        work_records.dispatch({**ids, 'action': 'presented', 'presentation_ref': 'fixture'}, base)
        work_records.dispatch({**ids, 'action': 'decide', 'draft_sha256': revision['draft_sha256'],
                               'decision': 'approved', 'user_decision_ref': 'fixture-user'}, base)
        before = (base / 'state.json').read_bytes()
        result = work_records.handle({'hook_event_name': 'PreToolUse', 'cwd': str(self.project),
            'session_id': 'fixture-coordinator', 'tool_use_id': 'blocked-view',
            'tool_name': tool, 'tool_input': args}, base)
        self.assertEqual('deny', result['hookSpecificOutput']['permissionDecision'])
        self.assertEqual(before, (base / 'state.json').read_bytes())
        self.assertEqual({}, self.call('status')['runtime_hooks']['writes'])

    def test_operation_record_and_task_gates_require_provider_page_readback(self):
        self.write_plan()
        base = self.root / 'operation-records'
        draft = self.project / 'operation-draft.md'
        draft.write_text(self.write_args['new_str'])
        candidate = work_records.dispatch({
            'action': 'propose', 'session_id': 'fixture-coordinator', 'task_id': 'same-id',
            'result_key': 'operation', 'record_kind': 'operation', 'draft_path': str(draft),
            'linear_refs': [], 'completion_basis': 'fixture', 'notion_target': self.dest['target'],
            'endix': False, 'tool_name': self.write_tool, 'tool_input': self.write_args,
            'expected_state': {'content': draft.read_text()}}, base)
        revision = candidate['revisions'][-1]
        ids = {'session_id': 'fixture-coordinator', 'candidate_id': candidate['candidate_id'],
               'revision_id': revision['revision_id']}
        work_records.dispatch({**ids, 'action': 'presented', 'presentation_ref': 'fixture'}, base)
        work_records.dispatch({**ids, 'action': 'decide', 'draft_sha256': revision['draft_sha256'],
                               'decision': 'approved', 'user_decision_ref': 'fixture-user'}, base)
        event = {'hook_event_name': 'PreToolUse', 'cwd': str(self.project),
                 'session_id': 'fixture-coordinator', 'tool_use_id': 'operation-write',
                 'tool_name': self.write_tool, 'tool_input': self.write_args}
        self.assertEqual('allow', work_records.handle(event, base)['hookSpecificOutput']['permissionDecision'])
        self.event('PostToolUse', self.write_tool, self.write_args, {'ok': True}, event_id='operation-write')
        self.assertEqual('deny', work_records.handle({**event, 'tool_use_id': 'retry'}, base)
                         ['hookSpecificOutput']['permissionDecision'])
        self.assertEqual('uncertain', self.call('status')['runtime_hooks']['writes']['save']['outcome'])
        with self.assertRaises(LedgerError):
            self.call('complete')
        write = self.call('status')['runtime_hooks']['tool_calls']['save-call']
        for response in ({'ok': True}, {'observed_state': {'content': draft.read_text()}},
                         self.read_response(target='wrong-page'), self.read_response(body='Different body')):
            with self.subTest(response=response), self.assertRaises(LedgerError):
                tool_hook.actual_payload(write, self.write_args, self.read_tool, self.read_args, response)
        # Exercise the provider's native wire response, not an observed_state attestation.
        self.fetch(self.read_response())
        self.assertEqual('verified', self.call('status')['runtime_hooks']['writes']['save']['outcome'])
        self.assertEqual('done', self.call('complete')['stage'])

    def test_exact_notion_sentence_update_and_actual_readback(self):
        target = 'https://app.notion.com/p/' + 'a' * 32
        tool = 'mcp__codex_apps__notion_notion_update_page'
        updates = [{'old_str': 'The record is awaiting save.', 'new_str': 'The record is saved and linked.'}]
        args = {'page_id': target, 'command': 'update_content', 'content_updates': updates}
        payload = {'content_updates': updates}
        self.assertEqual(('notion', 'update', target, payload), tool_hook.request_payload(tool, args, self.project))
        path = self.project / 'sentence-payload.json'
        path.write_text(canonical(payload))
        write = {'service': 'notion', 'tool_name': tool,
                 'gate': {'payload_path': str(path), 'target': target, 'operation': 'update'}}
        def read(body, url=target):
            value = {'metadata': {'type': 'page'}, 'url': url,
                     'text': '<page>\n<properties>\n{"title":"Record"}\n</properties>\n<content>\n' + body + '\n</content>\n</page>'}
            return tool_hook.actual_payload(write, args, 'mcp__codex_apps__notion_fetch', {'id': target}, value)
        self.assertEqual(canonical(payload).encode(), read(updates[0]['new_str']))
        for body in (updates[0]['old_str'], updates[0]['old_str'] + '\n' + updates[0]['new_str'], 'Missing'):
            with self.assertRaises(LedgerError):
                read(body)
        with self.assertRaises(LedgerError):
            read(updates[0]['new_str'], target.replace('a' * 32, 'b' * 32))
        with self.assertRaises(LedgerError):
            tool_hook.request_payload(tool, {**args, 'properties': {'title': 'Other'}}, self.project)
        self.config(); self.ready(complete=False)
        args['page_id'] = self.dest['target']
        gate = {'operation_id': 'sentence-write', 'destination_id': self.dest['id'],
                'workspace': self.dest['workspace'], 'target': self.dest['target'], 'operation': 'update',
                'payload_path': str(path), 'payload_sha256': sha(path.read_bytes()),
                'authorization_ref': self.dest['authorization_ref']}
        self.prepare('sentence-write', 'write', tool, args, gate)
        self.event('PreToolUse', tool, args)
        self.event('PostToolUse', tool, args, {'page_id': args['page_id']})
        read_tool, read_args = 'mcp__codex_apps__notion_fetch', {'id': args['page_id']}
        self.prepare('sentence-read', 'readback', read_tool, read_args, {'write_call_id': 'sentence-write'})
        self.event('PreToolUse', read_tool, read_args, event_id='sentence-read')
        value = {'metadata': {'type': 'page'}, 'url': args['page_id'],
                 'text': '<page>\n<properties>\n{"title":"Record"}\n</properties>\n<content>\n'
                         + updates[0]['new_str'] + '\n</content>\n</page>'}
        self.event('PostToolUse', read_tool, read_args, value, event_id='sentence-read')
        self.assertEqual('verified', self.call('status')['runtime_hooks']['writes']['sentence-write']['outcome'])

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
        self.assertTrue(tool_hook.linear_description_matches(expected, actual + ' changed', aliases, workspace))
        self.assertFalse(tool_hook.linear_description_matches(expected,
                         actual.replace('cb5a5e0b-ccfc-4ec2-b547-ebf208f484a9',
                                        '4f6c608e-2e52-4e76-b968-15bc9987f5de'), aliases, workspace))
        self.assertFalse(tool_hook.linear_description_matches(expected,
                         actual.replace('/issue/MAE-11/', '/issue/MAE-12/'), aliases, workspace))
        self.assertFalse(tool_hook.linear_description_matches(expected,
                         actual.replace('/maeng/', '/endix/', 1), aliases, workspace))

    def test_linear_description_accepts_pr_mention_when_content_matches(self):
        expected = '기존 내용. PR #9가 병합됐고 본문을 확인했다.'
        mention = ('<pull-request id="7c9a406c-0723-4f7d-92cd-bb6ea49c77d0" '
                   'href="https://linear.app/maeng/review/fix-native-git-push-matching">'
                   'maengseojun/agent-harness#9</pull-request>')
        actual = expected.replace('PR #9', mention)
        workspace = 'https://linear.app/maeng'
        links = [{'title': 'PR #9', 'url': 'https://github.com/maengseojun/agent-harness/pull/9'}]
        self.assertTrue(tool_hook.linear_description_matches(expected, actual, {}, workspace, links))
        self.assertTrue(tool_hook.linear_description_matches(expected, expected.replace('#9', mention), {}, workspace, links))
        self.assertTrue(tool_hook.linear_description_matches(expected, actual + ' 추가', {}, workspace, links))
        self.assertTrue(tool_hook.linear_description_matches(expected,
                        '머리말\n기존  내용.\n' + mention + '가 병합됐고 본문을 확인했다.\n덧붙인 메모',
                        {}, workspace, links))
        self.assertFalse(tool_hook.linear_description_matches(expected,
                         actual.replace('본문을 확인했다.', '본문을 아직 확인하지 못했다.'), {}, workspace, links))
        self.assertFalse(tool_hook.linear_description_matches(expected, actual.replace('#9', '#10'), {}, workspace, links))
        self.assertFalse(tool_hook.linear_description_matches(expected, actual + '\n실제 연결 PR #10.', {}, workspace, links))
        self.assertFalse(tool_hook.linear_description_matches(expected, actual + '\nother/repo#9', {}, workspace, links))
        self.assertFalse(tool_hook.linear_description_matches(expected,
                         actual + '\n[다른 PR](https://github.com/other/repo/pull/10)', {}, workspace, links))
        self.assertFalse(tool_hook.linear_description_matches(expected,
                         actual + '\n' + mention.replace('#9', '#10').replace('7c9a406c', '8c9a406c'),
                         {}, workspace, links))
        self.assertFalse(tool_hook.linear_description_matches(expected, actual.replace('/maeng/', '/endix/'), {}, workspace, links))
        self.assertFalse(tool_hook.linear_description_matches(expected,
                         actual.replace('maengseojun/agent-harness#9', 'other-owner/other-repo#9'), {}, workspace, links))
        self.assertFalse(tool_hook.linear_description_matches(expected, actual, {}, workspace))
        self.assertFalse(tool_hook.linear_description_matches(expected, actual, {}, None))
        old = ('<pull-request id="b495e17d-ddc8-48ef-89cc-824f2d18fb85" '
               'href="https://linear.app/maeng/review/mae-21-old">'
               'maengseojun/agent-harness#8</pull-request>')
        prior = '이전 ' + old + ' 기록. ' + expected
        rendered = '이전 ' + old.replace('maengseojun/agent-harness#8', 'MAE-21: old title') + ' 기록. ' + actual
        self.assertTrue(tool_hook.linear_description_matches(prior, rendered, {}, workspace, links))
        self.assertFalse(tool_hook.linear_description_matches(prior,
                         rendered.replace('b495e17d-ddc8-48ef-89cc-824f2d18fb85',
                                          '7c9a406c-0723-4f7d-92cd-bb6ea49c77d0'), {}, workspace, links))
        self.assertFalse(tool_hook.linear_description_matches(prior,
                         rendered.replace('/review/mae-21-old', '/review/other-pr'), {}, workspace, links))

    def test_linear_markdown_url_angle_delimiters_preserve_destination(self):
        url = 'https://app.notion.com/p/' + 'a' * 32
        expected = 'Result: [Record](' + url + '). Pending review.'
        actual = expected.replace('(' + url + ')', '(<' + url + '>)')
        matches = lambda text: tool_hook.linear_description_matches(expected, text, {}, 'https://linear.app/maeng')
        self.assertTrue(matches(actual))
        self.assertFalse(matches(actual.replace('a' * 32, 'b' * 32)))
        self.assertFalse(matches(actual.replace(' Pending review.', '')))

    def test_linear_markdown_pr_link_accepts_matching_native_mention(self):
        url = 'https://github.com/maengseojun/agent-harness/pull/12'
        expected = 'PR 결과: [PR #12](' + url + ') 병합 확인.'
        mention = ('<pull-request id="3502fd5b-0347-4dec-860b-ff285cd4edfd" '
                   'href="https://linear.app/maeng/review/fix-admission">'
                   'maengseojun/agent-harness#12</pull-request>')
        actual = 'PR 결과: ' + mention + ' 병합 확인.'
        links = [{'title': 'PR #12', 'url': url}]
        matches = lambda text: tool_hook.linear_description_matches(
            expected, text, {}, 'https://linear.app/maeng', links)
        self.assertTrue(matches(actual))
        self.assertFalse(matches(actual.replace('#12', '#13')))
        self.assertFalse(matches(actual.replace('maengseojun/agent-harness', 'other/repo')))
        self.assertFalse(matches(actual.replace('/maeng/', '/endix/')))
        self.assertFalse(matches(actual.replace(' 병합 확인.', '')))
        self.assertFalse(tool_hook.linear_description_matches(
            expected, actual, {}, 'https://linear.app/maeng', []))

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

    def test_coordinator_persistence_failure_cancels_exact_unexecuted_admission(self):
        self.write_plan()
        base = self.root / 'records'
        draft = self.project / 'record-draft.md'
        draft.write_text(self.write_args['new_str'])
        c = work_records.dispatch({'action': 'propose', 'session_id': 'fixture-coordinator',
            'task_id': 'same-id', 'result_key': 'fixture', 'draft_path': str(draft),
            'linear_refs': ['linear:fixture'], 'output_issue_ref': 'linear:fixture', 'completion_basis': 'fixture',
            'project_index_target': 'index', 'notion_target': 'fixture-resource', 'endix': False,
            'tool_name': self.write_tool, 'tool_input': self.write_args}, base)
        ids = {'session_id': 'fixture-coordinator', 'candidate_id': c['candidate_id'],
               'revision_id': c['revisions'][-1]['revision_id']}
        work_records.dispatch({**ids, 'action': 'presented', 'presentation_ref': 'fixture'}, base)
        work_records.dispatch({**ids, 'action': 'decide', 'draft_sha256': c['revisions'][-1]['draft_sha256'],
            'decision': 'approved', 'user_decision_ref': 'fixture-user'}, base)
        before = (base / 'state.json').read_bytes()
        event = {'hook_event_name': 'PreToolUse', 'cwd': str(self.project),
                 'session_id': 'fixture-coordinator', 'tool_use_id': 'unexecuted',
                 'tool_name': self.write_tool, 'tool_input': self.write_args}
        real_fsync = os.fsync
        def fail_directory_sync(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError('fixture directory sync failure')
            return real_fsync(fd)
        failures = [patch.object(work_records.tempfile, 'mkstemp',
                                 side_effect=OSError('fixture disk failure')),
                    patch.object(work_records.os, 'fsync', side_effect=fail_directory_sync)]
        real_tasks = tool_hook.session_tasks
        def deny_post_admission_reread(event, *args, **kwargs):
            if self.call('status')['runtime_hooks']['tool_calls']['save-call']['phase'] == 'admitted':
                raise OSError('fixture post-admission read failure')
            return real_tasks(event, *args, **kwargs)
        for failure in failures:
            with failure, patch.object(tool_hook, 'session_tasks', side_effect=deny_post_admission_reread):
                self.assertEqual('deny', work_records.handle(event, base)
                                 ['hookSpecificOutput']['permissionDecision'])
            self.assertEqual(before, (base / 'state.json').read_bytes())
            state = self.call('status')['runtime_hooks']
            self.assertEqual('prepared', state['tool_calls']['save-call']['phase'])
            self.assertEqual('absent', state['writes']['save']['outcome'])
        self.assertEqual('allow', work_records.handle({**event, 'tool_use_id': 'retry'}, base)
                         ['hookSpecificOutput']['permissionDecision'])
        self.assertEqual(3, self.call('status')['runtime_hooks']['writes']['save']['attempt'])
        recorded = (base / 'state.json').read_bytes()
        (base / 'state.json').write_text('{unreadable')
        self.assertEqual('deny', work_records.handle({**event, 'tool_use_id': 'retry'}, base)
                         ['hookSpecificOutput']['permissionDecision'])
        self.assertEqual('admitted', self.call('status')['runtime_hooks']['tool_calls']['save-call']['phase'])
        self.assertEqual('pending', self.call('status')['runtime_hooks']['writes']['save']['outcome'])
        (base / 'state.json').write_bytes(recorded)
        with self.assertRaisesRegex(LedgerError, 'exact unobserved'):

            self.call('cancel-tool', call_id='save-call', event_id='unexecuted', reason_ref='stale')
        self.event('PostToolUse', self.write_tool, self.write_args, {'ok': True}, event_id='retry')
        with self.assertRaisesRegex(LedgerError, 'exact unobserved'):
            self.call('cancel-tool', call_id='save-call', event_id='retry', reason_ref='too late')

    def test_pre_only_admission_requires_explicit_absence_before_retry(self):
        self.write_plan()
        self.event('PreToolUse', self.write_tool, self.write_args, event_id='denied-by-sibling')
        with self.assertRaisesRegex(LedgerError, 'concurrent'):
            self.event('PreToolUse', self.write_tool, self.write_args, event_id='too-early')
        (self.project / 'absence.txt').write_text('synthetic independent absence fixture')
        self.call('after-write', operation_id='save', attempt=1, workspace='fixture-space',
                  target='fixture-resource', outcome='uncertain', evidence_path='absence.txt')
        with self.assertRaisesRegex(LedgerError, 'concurrent'):
            self.event('PreToolUse', self.write_tool, self.write_args, event_id='still-uncertain')
        self.call('after-write', operation_id='save', attempt=1, workspace='fixture-space',
                  target='fixture-resource', outcome='absent', evidence_path='absence.txt')
        self.event('PreToolUse', self.write_tool, self.write_args, event_id='approved-retry')
        self.assertEqual(2, self.call('status')['runtime_hooks']['writes']['save']['attempt'])

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

    def test_blocked_sibling_does_not_break_linear_identity_read_for_active_task(self):
        self.config('linear')
        sibling = {'task_id': 'blocked-sibling', 'owner': 'fixture-coordinator'}
        execute(self.project, 'start', {**self.request, **sibling})
        execute(self.project, 'configure-hooks', {**sibling, 'output_owner': 'personal',
                'destinations': [], 'write_paths': [], 'requirements': []})
        execute(self.project, 'block', {**sibling, 'kind': 'requirements', 'reason_ref': 'actual blocker'})
        self.event('PostToolUse', 'mcp__linear__get_workspace', {},
                   {'structuredContent': {'id': self.dest['workspace']}}, event_id='active-workspace')
        self.assertEqual(self.dest['workspace'], self.call('status')['runtime_hooks']['connections']['mcp__linear__']['workspace'])
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

    def test_push_matches_destination_and_commit_despite_output_options(self):
        planned = {'cmd': 'git push origin HEAD:feat/fix', 'workdir': str(self.project)}
        path = self.project / 'push.json'
        path.write_text(canonical(planned))
        frozen = {'commit': 'a' * 40, 'ref': 'refs/heads/feat/fix'}
        (self.project / 'frozen-push.json').write_text(canonical(frozen))
        call = {'phase': 'prepared', 'kind': 'write', 'tool_name': 'Bash',
                'input': {'path': str(path)}, 'input_sha256': sha(canonical(tool_hook.arguments('Bash', planned)).encode()),
                'gate': {'target': 'https://api.github.com/repos/example/private/git/refs/heads/feat/fix',
                         'payload_path': str(self.project / 'frozen-push.json')}}
        task = {'_database': str(self.project / '.harness' / 'tasks.sqlite')}
        current_sha = ['a' * 40]
        def git_output(command, **_):
            if 'get-url' in command:
                return 'https://github.com/example/private.git\n'
            if '--show-toplevel' in command:
                return str(command[2]) + '\n'
            return current_sha[0] + '\n'
        with patch('subprocess.check_output', side_effect=git_output):
            actual = {**planned, 'max_output_tokens': 1000, 'yield_time_ms': 10000}
            args = tool_hook.arguments('exec_command', actual)
            self.assertTrue(tool_hook.matches_call(task, call, 'exec_command', args, sha(canonical(args).encode())))
            current_sha[0] = 'b' * 40
            self.assertFalse(tool_hook.matches_call(task, call, 'exec_command', args, sha(canonical(args).encode())))
            current_sha[0] = 'a' * 40
            elsewhere = {**args, 'workdir': str(self.root)}
            self.assertFalse(tool_hook.matches_call(task, call, 'exec_command', elsewhere,
                             sha(canonical(elsewhere).encode())))
            for command in ('git push origin HEAD:feat/other', 'git push --force origin HEAD:feat/fix',
                            'git push origin HEAD:feat/fix; touch bad', 'git push origin HEAD:feat/$(whoami)'):
                with self.subTest(command=command):
                    changed = {**args, 'command': command}
                    self.assertFalse(tool_hook.matches_call(task, call, 'exec_command', changed,
                                     sha(canonical(changed).encode())))

    def test_git_ref_readback_ignores_output_options_only(self):
        planned = {'cmd': 'gh api repos/example/private/git/ref/heads/feat/fix'}
        path = self.project / 'readback.json'
        path.write_text(canonical(planned))
        call = {'phase': 'prepared', 'kind': 'readback', 'tool_name': 'Bash',
                'input': {'path': str(path)}, 'input_sha256': sha(canonical(tool_hook.arguments('Bash', planned)).encode())}
        task = {'_database': str(self.project / '.harness' / 'tasks.sqlite')}
        actual = tool_hook.arguments('exec_command', {**planned, 'max_output_tokens': 1000})
        self.assertTrue(tool_hook.matches_call(task, call, 'exec_command', actual, sha(canonical(actual).encode())))
        changed = {**actual, 'command': 'gh api repos/example/private/git/ref/heads/feat/other'}
        self.assertFalse(tool_hook.matches_call(task, call, 'exec_command', changed, sha(canonical(changed).encode())))

    def push_lifecycle(self, duplicate):
        execute(self.project, 'start', self.request)
        target = 'https://api.github.com/repos/example/private/git/refs/heads/feat/fix'
        self.call('configure-hooks', output_owner='personal', destinations=[{
            'id': 'branch', 'service': 'github', 'workspace': 'example/private',
            'target': target, 'output_owner': 'personal', 'operations': ['push'],
            'authorization_ref': 'fixture:authorized'}], write_paths=[], requirements=[])
        (self.project / 'summary.md').write_text('Reviewed push\n')
        (self.project / 'check.txt').write_text('Passed\n')
        (self.project / 'review.txt').write_text('Approved\n')
        artifact = self.call('artifact', path='summary.md', worker_id='fixture-worker')['artifact']['sha256']
        self.call('check', artifact_sha256=artifact, evidence_path='check.txt', check_id='fixture',
                  agent_id='fixture-worker', exit_code=0)
        self.call('review', artifact_sha256=artifact, evidence_path='review.txt',
                  agent_id='fixture-reviewer', verdict='approved', covered_conditions=[0])
        payload = {'commit': 'a' * 40, 'ref': 'refs/heads/feat/fix'}
        (self.project / 'payload.json').write_text(canonical(payload))
        base = {'cmd': 'git push origin HEAD:feat/fix', 'workdir': str(self.project)}
        def git_output(command, **_):
            if 'get-url' in command:
                return 'https://github.com/example/private.git\n'
            if '--show-toplevel' in command:
                return str(self.project) + '\n'
            return 'a' * 40 + '\n'
        actual = {**base, 'max_output_tokens': 1000, 'yield_time_ms': 10000}
        with patch('subprocess.check_output', side_effect=git_output):
            planned_calls = (base, {**base, 'max_output_tokens': 400}) if duplicate else (base,)
            for number, args in enumerate(planned_calls, 1):
                gate = {'operation_id': 'push-' + str(number), 'destination_id': 'branch',
                        'workspace': 'example/private', 'target': target, 'operation': 'push',
                        'payload_path': 'payload.json', 'payload_sha256': sha(canonical(payload).encode()),
                        'authorization_ref': 'fixture:authorized'}
                self.prepare('push-' + str(number), 'write', 'functions__exec_command', args, gate)
            admitted = self.event('PreToolUse', 'functions__exec_command', actual, event_id='push-native')
            self.assertEqual('allow', admitted['hookSpecificOutput']['permissionDecision'])
            self.event('PostToolUse', 'functions__exec_command', actual,
                       {'exit_code': 0, 'output': 'pushed'}, event_id='push-native')
            read = {'cmd': 'gh api repos/example/private/git/ref/heads/feat/fix'}
            self.prepare('fetch-push', 'readback', 'functions__exec_command', read,
                         {'write_call_id': 'push-1'})
            actual_read = {**read, 'max_output_tokens': 1000}
            self.event('PreToolUse', 'functions__exec_command', actual_read, event_id='fetch-native')
            self.event('PostToolUse', 'functions__exec_command', actual_read,
                       {'exit_code': 0, 'output': canonical({'url': target, 'object': {'sha': 'a' * 40},
                                                            'ref': 'refs/heads/feat/fix'})}, event_id='fetch-native')
        calls = self.call('status')['runtime_hooks']
        self.assertEqual('observed', calls['tool_calls']['push-1']['phase'])
        self.assertEqual('observed', calls['tool_calls']['fetch-push']['phase'])
        self.assertEqual('verified', calls['writes']['push-1']['outcome'])
        if duplicate:
            self.assertEqual('prepared', calls['tool_calls']['push-2']['phase'])
            with self.assertRaisesRegex(LedgerError, 'incomplete'):
                self.call('complete')
        else:
            self.assertEqual('done', self.call('complete')['stage'])

    def test_semantic_push_full_native_lifecycle(self):
        self.push_lifecycle(False)

    def test_duplicate_semantic_push_plans_admit_once(self):
        self.push_lifecycle(True)

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

    def test_pr_merge_requires_reviewed_head_and_merged_readback(self):
        execute(self.project, 'start', self.request)
        dest = {'id': 'pr-merge', 'service': 'github', 'workspace': 'example/private',
                'target': 'https://github.com/example/private/pull/9', 'output_owner': 'personal',
                'operations': ['update'], 'authorization_ref': 'fixture:approved-merge'}
        self.call('configure-hooks', output_owner='personal', destinations=[dest],
                  write_paths=['output'], requirements=[])
        self.ready(complete=False)
        args = {'repository_full_name': 'example/private', 'pr_number': 9,
                'expected_head_sha': 'a' * 40, 'merge_method': 'merge'}
        payload = {'merged': True, 'head_sha': 'a' * 40, 'merge_method': 'merge'}
        (self.project / 'pr-merge-payload.json').write_text(canonical(payload))
        gate = {'operation_id': 'merge-pr', 'destination_id': dest['id'],
                'workspace': dest['workspace'], 'target': dest['target'], 'operation': 'update',
                'payload_path': 'pr-merge-payload.json', 'payload_sha256': sha(canonical(payload).encode()),
                'authorization_ref': dest['authorization_ref']}
        tool = 'mcp__codex_apps__github_merge_pull_request'
        read_tool = 'mcp__codex_apps__github_fetch_pr'
        read_args = {'repo_full_name': 'example/private', 'pr_number': 9}
        self.prepare('merge-pr', 'write', tool, args, gate)
        self.event('PreToolUse', tool, args)
        self.event('PostToolUse', tool, args, {'structuredContent': {'merged': True, 'sha': 'b' * 40}})
        self.prepare('fetch-merge', 'readback', read_tool, read_args, {'write_call_id': 'merge-pr'})
        self.event('PreToolUse', read_tool, read_args, event_id='pr-merge-read')
        base = {'number': 9, 'url': dest['target'], 'head_sha': 'a' * 40,
                'merged': False, 'merge_commit_sha': 'b' * 40}
        denied = self.event('PostToolUse', read_tool, read_args,
                            {'structuredContent': {'pull_request': base}}, event_id='pr-merge-read')
        self.assertIn('merge or reviewed head mismatch', denied['reason'])
        self.event('PreToolUse', read_tool, read_args, event_id='pr-merge-retry')
        denied = self.event('PostToolUse', read_tool, read_args,
                            {'structuredContent': {'pull_request': {**base, 'merged': True,
                                                                    'merge_commit_sha': 'c' * 40}}}, event_id='pr-merge-retry')
        self.assertIn('merge or reviewed head mismatch', denied['reason'])
        self.event('PreToolUse', read_tool, read_args, event_id='pr-merge-confirm')
        self.event('PostToolUse', read_tool, read_args,
                   {'structuredContent': {'pull_request': {**base, 'merged': True}}}, event_id='pr-merge-confirm')
        self.assertEqual('verified', self.call('status')['runtime_hooks']['writes']['merge-pr']['outcome'])

    def test_pr_merge_without_response_commit_cannot_verify(self):
        args = {'repository_full_name': 'example/private', 'pr_number': 9,
                'expected_head_sha': 'a' * 40, 'merge_method': 'merge'}
        payload = {'merged': True, 'head_sha': 'a' * 40, 'merge_method': 'merge'}
        path = self.project / 'missing-merge-sha.json'
        path.write_text(canonical(payload))
        write = {'service': 'github', 'tool_name': 'mcp__codex_apps__github_merge_pull_request',
                 'gate': {'operation': 'update', 'target': 'https://github.com/example/private/pull/9',
                          'payload_path': str(path)}}
        observed = {'pull_request': {'number': 9, 'url': write['gate']['target'],
                    'head_sha': 'a' * 40, 'merged': True, 'merge_commit_sha': None}}
        with self.assertRaisesRegex(LedgerError, 'merge or reviewed head mismatch'):
            tool_hook.actual_payload(write, args, 'mcp__codex_apps__github_fetch_pr',
                                     {'repo_full_name': 'example/private', 'pr_number': 9},
                                     {'structuredContent': observed})

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
