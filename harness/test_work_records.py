"""Isolated stdlib checks: python3 -B -m unittest discover -s harness -p test_work_records.py."""
from contextlib import closing
import copy
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import ledger
import work_records as records


class WorkRecordsTests(unittest.TestCase):
    def setUp(self):
        self.actual_session_tasks = getattr(records.tool_hook, "session_tasks", None)
        self.tasks = []
        self.task_mock = patch.object(records.tool_hook, 'session_tasks',
                                      side_effect=lambda *args, **kwargs: self.tasks, create=True)
        self.task_mock.start()
        self.pre_gate = patch.object(records.tool_hook, "handle", return_value={})
        self.pre_gate.start()
        self.addCleanup(self.pre_gate.stop)
        self.addCleanup(self.task_mock.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.base = self.root / 'private'
        self.draft = self.root / 'draft.md'
        self.draft.write_text('Verified result\n')
        self.proposal = dict(action='propose', session_id='session-1', task_id='task-1',
                             result_key='result-1', draft_path=str(self.draft), linear_refs=['linear:1'],
                             output_issue_ref='linear:1',
                             completion_basis='Focused tests passed', project_index_target='index-1',
                             notion_target='collection://records', endix=False,
                             tool_name='mcp__codex_apps__notion_notion_create_pages',
                             tool_input={'parent': {'data_source_id': 'records'},
                                         'pages': [{'content': self.draft.read_text(), 'properties': {'title': 'Result'}}]})
        self.candidate = self.call(self.proposal)
        self.revision = self.candidate['revisions'][-1]
        self.ids = dict(session_id='session-1', candidate_id=self.candidate['candidate_id'],
                        revision_id=self.revision['revision_id'])

    def call(self, data):
        return records.dispatch(data, self.base)

    def act(self, action, **values):
        return self.call(dict(self.ids, action=action, **values))

    def approve(self, **values):
        self.act('presented', presentation_ref='chat:shown')
        return self.act('decide', decision='approved', user_decision_ref='user:approve',
                        draft_sha256=self.revision['draft_sha256'], **values)

    def event(self, name='PreToolUse', **values):
        return dict(hook_event_name=name, session_id='session-1', tool_use_id='call-1',
                    tool_name=self.proposal['tool_name'], tool_input=self.proposal['tool_input'], **values)

    def denied(self, event):
        result = records.handle(event, self.base)
        self.assertEqual(result['hookSpecificOutput']['permissionDecision'], 'deny')

    def readback(self, **values):
        path = self.root / 'readback.json'
        body = dict(content=self.draft.read_text(), target=self.proposal['notion_target'],
                    page_url='https://www.notion.so/result-123', evidence_ref='fetch:1',
                    properties={'title': 'Result'}, parent_target=self.proposal['notion_target'])
        body.update(values)
        path.write_text(json.dumps(body))
        return dict(readback_path=str(path), page_url=body['page_url'], target=body['target'], evidence_ref=body['evidence_ref'])

    def test_legacy_revision_identity_preserves_attempt_history(self):
        keys = ('draft_sha256', 'notion_target', 'endix', 'record_kind',
                'tool_name', 'input_sha256', 'linear_refs', 'output_issue_ref',
                'project_index_target', 'completion_basis', 'related_candidates',
                'maintenance', 'maintenance_evidence_ref',
                'maintenance_current_readback_sha256')
        legacy_id = records.fingerprint({key: self.revision[key] for key in keys})
        self.assertEqual(legacy_id, self.revision['revision_id'])
        self.approve()
        records.handle(self.event(), self.base)
        again = self.call(self.proposal)
        self.assertEqual(1, len(again['revisions']))
        self.assertEqual('dispatched', again['revisions'][-1]['write_state'])
        event = self.event()
        event['tool_use_id'] = 'new-attempt'
        self.denied(event)

    def test_task_denial_does_not_consume_record_approval(self):
        self.approve()
        before = (self.base / 'state.json').read_bytes()
        denied = records.context('PreToolUse', 'No prepared call', deny=True)
        with patch.object(records.tool_hook, 'handle', return_value=denied):
            self.assertEqual(denied, records.handle(self.event(), self.base))
        self.assertEqual(before, (self.base / 'state.json').read_bytes())
        with patch.object(records.tool_hook, 'handle', return_value={}):
            self.assertEqual('allow', records.handle(self.event(), self.base)
                             ['hookSpecificOutput']['permissionDecision'])
        self.assertEqual('dispatched', self.act('status')['revisions'][-1]['write_state'])

    def test_record_denial_never_admits_task_and_other_tools_still_check(self):
        with patch.object(records.tool_hook, 'handle') as task_gate:
            self.denied(self.event())
            task_gate.assert_not_called()
        event = self.event()
        event['tool_input'] = {}
        event['tool_name'] = 'mcp__linear__save_issue'
        denied = records.context('PreToolUse', 'No prepared call', deny=True)
        with patch.object(records.tool_hook, 'handle', return_value=denied) as task_gate:
            self.assertEqual(denied, records.handle(event, self.base))
            task_gate.assert_called_once_with(event)

    def test_approval_hash_and_exact_tool_input_session(self):
        self.denied(self.event())
        with self.assertRaises(ledger.LedgerError):
            self.act('decide', decision='approved', user_decision_ref='user:1', draft_sha256=self.revision['draft_sha256'])
        self.act('presented', presentation_ref='chat:1')
        for values in ({'draft_sha256': '0' * 64, 'user_decision_ref': 'user:1'},
                       {'draft_sha256': self.revision['draft_sha256']}):
            with self.assertRaises(ledger.LedgerError):
                self.act('decide', decision='approved', **values)
        self.approve()
        changed = self.event()
        changed['tool_input'] = {'different': True}
        self.denied(changed)
        changed = self.event()
        changed['session_id'] = 'other-session'
        self.denied(changed)
        changed = self.event()
        changed['tool_name'] = 'mcp__notion__create_pages'
        self.denied(changed)
        self.assertEqual(self.call(self.event())['hookSpecificOutput']['permissionDecision'], 'allow')

    def test_changed_draft_invalidates_approval_and_retains_history(self):
        self.approve()
        self.draft.write_text('Revised result\n')
        self.denied(self.event())
        self.assertFalse(self.act('status')['draft_current'])
        proposal = copy.deepcopy(self.proposal)
        proposal['tool_input']['pages'][0]['content'] = self.draft.read_text()
        newer = self.call(proposal)
        self.assertEqual(len(newer['revisions']), 2)
        self.assertEqual(newer['revisions'][0]['history'][0]['decision'], 'approved')
        self.assertEqual(newer['revisions'][-1]['disposition'], 'proposed')
        self.denied(self.event())
        with self.assertRaises(ledger.LedgerError):
            self.act('presented', presentation_ref='stale')

    def test_team_requires_separate_permission(self):
        proposal = dict(self.proposal, endix=True)
        candidate = self.call(proposal)
        self.revision = candidate['revisions'][-1]
        self.ids['revision_id'] = self.revision['revision_id']
        with self.assertRaises(ledger.LedgerError):
            self.approve()
        with self.assertRaises(ledger.LedgerError):
            self.approve(endix_authorization_ref='user:approve')
        self.approve(endix_authorization_ref='user:endix-separate')
        self.assertEqual(self.call(self.event())['hookSpecificOutput']['permissionDecision'], 'allow')

    def test_uncertain_write_never_retries_or_becomes_saved_from_response(self):
        self.approve()
        self.call(self.event())
        self.assertEqual(self.call(self.event())['hookSpecificOutput']['permissionDecision'], 'allow')
        other = self.event(); other['tool_use_id'] = 'call-2'
        self.denied(other)
        result = self.call(self.event('PostToolUse', tool_response={'url': 'https://notion.so/result'}))
        self.assertIn('uncertain', result['hookSpecificOutput']['additionalContext'])
        self.assertEqual(self.act('status')['revisions'][-1]['write_state'], 'uncertain')
        self.denied(self.event())
        proposal = dict(self.proposal, notion_target='collection://changed')
        proposal['tool_input'] = copy.deepcopy(self.proposal['tool_input'])
        proposal['tool_input']['parent']['data_source_id'] = 'changed'
        with self.assertRaises(ledger.LedgerError):
            self.call(proposal)
        with self.assertRaises(ledger.LedgerError):
            self.act('decide', decision='approved', user_decision_ref='user:again', draft_sha256=self.revision['draft_sha256'])

    def test_saved_accepts_added_links_but_keeps_approval_binding(self):
        self.approve()
        self.call(self.event())
        values = self.readback(content='[Verified](https://example.com) result')
        saved = self.act('saved', **values)
        self.assertEqual('saved', saved['revisions'][-1]['write_state'])
        self.assertEqual(self.revision['draft_sha256'], saved['revisions'][-1]['draft_sha256'])
        self.draft.write_text('Changed result')
        with self.assertRaises(ledger.LedgerError):
            self.act('saved', **self.readback())

    def test_legacy_save_requires_original_frozen_input_and_properties(self):
        self.approve(); self.call(self.event())
        path = self.base / 'state.json'
        state = json.loads(path.read_text())
        revision = state[self.candidate['candidate_id']]['revisions'][-1]
        for key in ('property_hashes', 'body_sha256', 'attempts'):
            revision.pop(key, None)
        path.write_text(json.dumps(state))
        proof = self.root / 'original-input.json'
        proof.write_text(json.dumps({}))
        with self.assertRaisesRegex(ledger.LedgerError, 'approved input hash mismatch'):
            self.act('saved', approved_input_path=str(proof), **self.readback())
        proof.write_text(json.dumps(self.proposal['tool_input']))
        with self.assertRaisesRegex(ledger.LedgerError, 'properties'):
            self.act('saved', approved_input_path=str(proof), **self.readback(properties={'title': 'Changed'}))
        saved = self.act('saved', approved_input_path=str(proof), **self.readback())
        self.assertEqual('saved', saved['revisions'][-1]['write_state'])
        self.assertEqual(self.revision['draft_sha256'], saved['revisions'][-1]['draft_sha256'])
        self.assertEqual(self.revision['input_sha256'], saved['revisions'][-1]['input_sha256'])
        self.assertEqual(saved, self.act('saved', approved_input_path=str(proof), **self.readback()))

    def test_saved_requires_separate_matching_readback(self):
        with self.assertRaises(ledger.LedgerError):
            self.act('saved', **self.readback())
        self.approve()
        self.call(self.event())
        with self.assertRaises(ledger.LedgerError):
            self.act('saved', readback_path=str(self.draft), target=self.proposal['notion_target'],
                     page_url='https://notion.so/result', evidence_ref='fetch:1')
        for mismatch in ({'content': 'wrong'}, {'page_url': 'https://example.com/page'}, {'target': 'wrong'},
                         {'properties': {}}, {'properties': {'title': 'Wrong'}}, {'parent_target': 'collection://wrong'}):
            with self.assertRaises(ledger.LedgerError):
                self.act('saved', **self.readback(**mismatch))
        values = self.readback()
        saved = self.act('saved', **values)
        self.assertEqual(saved['revisions'][-1]['write_state'], 'saved')
        self.assertEqual(saved, self.act('saved', **values))
        self.denied(self.event())
        revised = dict(self.proposal, completion_basis='Reviewed final rewrite')
        candidate = self.call(revised)
        self.assertEqual(candidate['canonical_page'], saved['canonical_page'])
        self.assertEqual(candidate['revisions'][0]['receipt']['page_url'], values['page_url'])
        self.denied(self.event())

    def test_absence_reconciliation_does_not_renew_permission(self):
        self.approve()
        self.call(self.event())
        path = self.root / 'absence.json'
        path.write_text(json.dumps({'absent': True, 'target': self.proposal['notion_target'], 'evidence_ref': 'fetch:absent'}))
        self.act('saved', outcome='absent', readback_path=str(path), target=self.proposal['notion_target'], evidence_ref='fetch:absent')
        self.denied(self.event())
        self.assertEqual(self.call(self.proposal)['revisions'][-1]['write_state'], 'absent')

    def confirm_absent(self, evidence='fetch:absent'):
        path = self.root / 'absence.json'
        path.write_text(json.dumps({'absent': True, 'target': self.proposal['notion_target'],
                                    'evidence_ref': evidence}))
        return self.act('saved', outcome='absent', readback_path=str(path),
                        target=self.proposal['notion_target'], evidence_ref=evidence)

    def test_new_approval_after_absence_allows_exactly_one_retry(self):
        self.approve()
        self.call(self.event())
        self.confirm_absent()
        for ref in ('user:approve',):
            with self.assertRaises(ledger.LedgerError):
                self.act('decide', decision='approved', user_decision_ref=ref,
                         draft_sha256=self.revision['draft_sha256'])
        self.act('decide', decision='approved', user_decision_ref='user:retry',
                 draft_sha256=self.revision['draft_sha256'])
        self.denied(self.event())  # old event ID is not a new attempt
        retry = self.event(); retry['tool_use_id'] = 'call-2'
        self.assertEqual('allow', self.call(retry)['hookSpecificOutput']['permissionDecision'])
        self.assertEqual('allow', self.call(retry)['hookSpecificOutput']['permissionDecision'])
        before = self.act('status')
        self.call(self.event('PostToolUse', tool_response={'old': True}))
        self.assertEqual(before, self.act('status'))
        with self.assertRaises(ledger.LedgerError):
            self.confirm_absent()  # old fetch cannot resolve the new attempt
        self.call(dict(retry, hook_event_name='PostToolUse', tool_response={}))
        self.denied(retry)
        status = self.act('status')['revisions'][-1]
        self.assertEqual(2, len(status['attempts']))
        self.assertEqual('absent', status['attempts'][0]['write_state'])
        self.assertEqual('uncertain', status['attempts'][1]['write_state'])
        self.act('saved', **self.readback())
        with self.assertRaises(ledger.LedgerError):
            self.act('decide', decision='approved', user_decision_ref='user:third',
                     draft_sha256=self.revision['draft_sha256'])

    def test_resume_revokes_unused_retry_and_old_approval(self):
        self.approve()
        self.call(self.event())
        self.confirm_absent()
        self.act('decide', decision='approved', user_decision_ref='user:retry',
                 draft_sha256=self.revision['draft_sha256'])
        self.act('resume', from_session_id='session-1', session_id='session-2', resume_ref='continue')
        self.ids['session_id'] = 'session-2'
        self.act('presented', presentation_ref='shown-again')
        with self.assertRaises(ledger.LedgerError):
            self.act('decide', decision='approved', user_decision_ref='user:retry',
                     draft_sha256=self.revision['draft_sha256'])
        self.act('decide', decision='approved', user_decision_ref='user:new-session',
                 draft_sha256=self.revision['draft_sha256'])
        retry = self.event(); retry.update(session_id='session-2', tool_use_id='call-2')
        self.assertEqual('allow', self.call(retry)['hookSpecificOutput']['permissionDecision'])

    def test_installed_state_migrates_attempt_and_consumed_approval(self):
        self.approve()
        self.call(self.event())
        state_path = self.base / 'state.json'
        state = json.loads(state_path.read_text())
        state.pop('_assessments')
        revision = state[self.ids['candidate_id']]['revisions'][-1]
        revision.pop('attempts')
        revision['history'] = [h for h in revision['history'] if 'attempt' not in h]
        state_path.write_text(json.dumps(state))
        self.confirm_absent()
        with self.assertRaises(ledger.LedgerError):
            self.act('decide', decision='approved', user_decision_ref='user:approve',
                     draft_sha256=self.revision['draft_sha256'])
        self.assertEqual(1, len(self.act('status')['revisions'][-1]['attempts']))

    def verified_task(self, task_id='task-1'):
        check_path = self.root / 'check.txt'; check_path.write_text('tests passed')
        review_path = self.root / 'review.txt'; review_path.write_text('independent review passed')
        artifact = ledger.snapshot(str(self.draft))
        return dict(task_id=task_id, _database=str(self.root / 'tasks.sqlite'),
                    work_status='verified', artifact=artifact, owners=['session-1'], workers=['worker-1'],
                    check={'artifact_sha256': artifact['sha256'], 'exit_code': 0,
                           'evidence': ledger.snapshot(str(check_path))},
                    review={'artifact_sha256': artifact['sha256'], 'verdict': 'approved', 'agent_id': 'independent-reviewer',
                            'evidence': ledger.snapshot(str(review_path))})

    def test_assessment_without_draft_bounded_and_changed_result_reassessed(self):
        self.base.joinpath('state.json').write_text('{}')
        task = self.verified_task(); self.tasks.append(task)
        event = {'hook_event_name': 'Stop', 'session_id': 'session-1', 'cwd': str(self.root)}
        self.assertEqual('block', self.call(event)['decision'])
        self.assertEqual({}, self.call(event))
        result = records.task_results(event)[0]
        assessment = dict(action='assess', session_id='session-1', cwd=str(self.root), task_id='task-1',
                          result_sha256=result[2], assessment_ref='assessment:1',
                          deferred_reason='No reusable conclusion beyond the delivered fix')
        saved = self.call(assessment)
        self.assertEqual(task['artifact'], saved['basis']['artifact'])
        self.assertEqual(saved, self.call(assessment))
        self.assertEqual({}, self.call(event))
        self.draft.write_text('Changed verified result')
        self.tasks[:] = [self.verified_task()]
        self.assertEqual('block', self.call(event)['decision'])
        with self.assertRaises(ledger.LedgerError):
            self.call(assessment)

    def test_assessment_links_candidate_and_keeps_unchanged_decision_quiet(self):
        self.tasks.append(self.verified_task())
        event = {'hook_event_name': 'Stop', 'session_id': 'session-1', 'cwd': str(self.root)}
        result = records.task_results(event)[0]
        assessed = self.call(dict(action='assess', session_id='session-1', cwd=str(self.root), task_id='task-1',
                                 result_sha256=result[2], assessment_ref='assessment:1',
                                 candidate_id=self.ids['candidate_id']))
        self.assertEqual(self.ids['revision_id'], assessed['revision_id'])
        self.act('presented', presentation_ref='shown')
        for decision in ('deferred', 'rejected'):
            self.act('decide', decision=decision, user_decision_ref='user:' + decision,
                     draft_sha256=self.revision['draft_sha256'])
            self.assertEqual({}, self.call(event))

    def test_assessment_is_visible_once_during_stop_continuation(self):
        self.base.joinpath('state.json').write_text('{}')
        self.tasks.append(self.verified_task())
        event = {'hook_event_name': 'Stop', 'session_id': 'session-1', 'cwd': str(self.root), 'stop_hook_active': True}
        self.assertIn('Assess actual', self.call(event)['systemMessage'])
        self.assertEqual({}, self.call(event))

    def test_no_completion_inferred_from_stop_or_unverified_stale_task(self):
        self.base.joinpath('state.json').write_text('{}')
        event = {'hook_event_name': 'Stop', 'session_id': 'session-1', 'cwd': str(self.root), 'prompt': 'done'}
        self.assertEqual({}, self.call(event))
        task = self.verified_task()
        for change in ({'work_status': 'working'}, {'artifact': None}, {'check': None}, {'review': None},
                       {'review': dict(task['review'], artifact_sha256='old')},
                       {'review': dict(task['review'], agent_id='session-1')},
                       {'review': dict(task['review'], agent_id='worker-1')},
                       {'check': dict(task['check'], exit_code=1)}, {'repair_open': True}):
            self.tasks[:] = [dict(task, **change)]
            self.assertEqual({}, self.call(event))
        self.tasks[:] = [task]
        self.draft.write_text('stale artifact')
        self.assertEqual({}, self.call(event))

    def test_shared_classifier_is_used_after_normalization(self):
        with patch.object(records.tool_hook, 'protected', return_value=None) as classifier:
            self.assertFalse(records.notion_write('mcp__codex_apps__notion__search',
                                                  {'query': 'mutation update delete'}))
            classifier.assert_called_once_with('mcp__codex_apps__notion_search',
                                               {'query': 'mutation update delete'})
        with patch.object(records.tool_hook, 'protected', return_value='write'):
            self.assertTrue(records.notion_write('mcp__notion__update_page', {}))
            self.assertFalse(records.notion_write('mcp__linear__save_issue', {}))

    def test_duplicates_deferred_rejected_are_quiet(self):
        for decision in ('deferred', 'rejected', 'approved'):
            self.act('presented', presentation_ref='chat:1')
            candidate = self.act('decide', decision=decision, user_decision_ref='user:' + decision,
                                 draft_sha256=self.revision['draft_sha256'])
            self.assertEqual(candidate, self.call(self.proposal))
            self.assertEqual(self.call({'hook_event_name': 'Stop', 'session_id': 'session-1'}), {})
        identical = self.root / 'renamed-draft.md'
        identical.write_bytes(self.draft.read_bytes())
        updated = self.call(dict(self.proposal, completion_basis='Same result, reworded explanation',
                                 draft_path=str(identical), linear_refs=['linear:other'],
                                 output_issue_ref='linear:other'))
        self.assertNotEqual(self.revision['revision_id'], updated['revisions'][-1]['revision_id'])
        self.assertFalse(updated['revisions'][-1]['presented'])
        self.assertEqual('proposed', updated['revisions'][-1]['disposition'])
        self.assertIn('Present prepared', self.call({'hook_event_name': 'Stop', 'session_id': 'session-1'})['reason'])

    def test_shared_live_reads_and_mutations(self):
        for tool, args in (
            ('mcp__codex_apps__notion__search', {'query': 'mutation delete update'}),
            ('mcp__notion__fetch', {'url': 'https://notion.so/mutation'}),
            ('mcp__codex_apps__notion__query_data_sources', {'query': 'SELECT mutation FROM records'})):
            self.assertFalse(records.notion_write(tool, args))
        for name in ('mcp__notion__query', 'mcp__codex_apps__notion__query'):
            for query in ('mutation { deletePage }', '# comment\nmutation { deletePage }', '\ufeffmutation { deletePage }'):
                self.assertTrue(records.notion_write(name, {'query': query}))

    def test_missing_cwd_does_not_scan_bound_tasks(self):
        self.base.joinpath('state.json').write_text('{}')
        with patch.object(records.tool_hook, 'session_tasks', side_effect=AssertionError('must not scan')):
            self.assertEqual({}, self.call({'hook_event_name': 'Stop', 'session_id': 'session-1'}))

    def test_source_check_and_review_evidence_must_all_be_current(self):
        self.base.joinpath('state.json').write_text('{}')
        source = self.root / 'source.py'; source.write_text('original')
        task = self.verified_task()
        task['request'] = {'closeout': {'mode': 'library', 'source_paths': ['source.py']}}
        for record in (task['check'], task['review']):
            record['sources'] = {'source.py': ledger.snapshot(str(source))}
        self.tasks[:] = [task]
        event = {'hook_event_name': 'Stop', 'session_id': 'session-1', 'cwd': str(self.root)}
        source.write_text('changed')
        self.assertEqual({}, self.call(event))
        source.write_text('original')
        Path(task['check']['evidence']['path']).write_text('changed check')
        self.assertEqual({}, self.call(event))
        Path(task['check']['evidence']['path']).write_text('tests passed')
        Path(task['review']['evidence']['path']).write_text('changed review')
        self.assertEqual({}, self.call(event))
        Path(task['review']['evidence']['path']).write_text('independent review passed')
        self.assertEqual('block', self.call(event)['decision'])

    def test_real_bound_completed_task_scan_and_assessment(self):
        self.assertIsNotNone(self.actual_session_tasks, 'parent session_tasks helper required')
        self.base.joinpath('state.json').write_text('{}')
        task = self.verified_task()
        task.update(owner='session-1', runtime_hooks_required=True, completion_requested=True,
                    stage='done', paused=False)
        database = self.root / '.harness/tasks.sqlite'
        database.parent.mkdir()
        with closing(sqlite3.connect(database)) as connection:
            connection.execute('CREATE TABLE tasks (state TEXT)')
            connection.execute('INSERT INTO tasks VALUES (?)', (json.dumps(task),))
            connection.commit()
        event = {'hook_event_name': 'Stop', 'session_id': 'session-1', 'cwd': str(self.root)}
        with patch.object(records.tool_hook, 'session_tasks', self.actual_session_tasks), \
                patch.object(records.tool_hook, 'session_path', return_value=self.root / 'no-bindings.json'):
            self.assertEqual('block', self.call(event)['decision'])
            self.assertEqual({}, self.call(event))
            result = records.task_results(event)[0]
            self.call(dict(action='assess', session_id='session-1', cwd=str(self.root), task_id='task-1',
                           result_sha256=result[2], assessment_ref='actual-task:assessed',
                           deferred_reason='Result delivered; no standalone record needed'))
            self.assertEqual({}, self.call(event))
            self.assertEqual([], records.task_results(dict(event, session_id='other-session')))

    def test_endix_retry_requires_fresh_separate_reference(self):
        candidate = self.call(dict(self.proposal, endix=True))
        self.revision = candidate['revisions'][-1]; self.ids['revision_id'] = self.revision['revision_id']
        self.approve(endix_authorization_ref='user:endix')
        self.call(self.event()); self.confirm_absent()
        with self.assertRaises(ledger.LedgerError):
            self.act('decide', decision='approved', user_decision_ref='user:retry',
                     endix_authorization_ref='user:endix', draft_sha256=self.revision['draft_sha256'])
        self.act('decide', decision='approved', user_decision_ref='user:retry',
                 endix_authorization_ref='user:endix-retry', draft_sha256=self.revision['draft_sha256'])
        retry = self.event(); retry['tool_use_id'] = 'call-2'
        self.assertEqual('allow', self.call(retry)['hookSpecificOutput']['permissionDecision'])

    def test_native_connector_alias_is_the_same_approved_call(self):
        self.approve()
        event = self.event()
        event['tool_name'] = 'mcp__codex_apps__notion__create_pages'
        self.assertEqual('allow', self.call(event)['hookSpecificOutput']['permissionDecision'])

    def test_takeover_preserves_uncertain_write_and_saved_canonical_record(self):
        self.approve()
        self.call(self.event())
        self.call(self.event('PostToolUse', tool_response={}))
        found = self.call({'action': 'status', 'session_id': 'session-2', 'task_id': 'task-1'})
        self.assertEqual(self.candidate['candidate_id'], found[0]['candidate_id'])
        resumed = self.act('resume', from_session_id='session-1', session_id='session-2', resume_ref='user:continue')
        self.assertEqual('uncertain', resumed['revisions'][-1]['write_state'])
        self.ids['session_id'] = 'session-2'
        event = self.event(); event['session_id'] = 'session-2'
        self.denied(event)
        saved = self.act('saved', **self.readback())
        self.assertIsNotNone(saved['canonical_page'])
        reviewed = self.act('reviewed', review_ref='user:review-feedback')
        self.assertEqual('user:review-feedback', reviewed['revisions'][-1]['record_review_ref'])
        with self.assertRaises(ledger.LedgerError):
            self.act('resume', from_session_id='session-1', session_id='session-3', resume_ref='stale')

    def test_takeover_revokes_unused_approval(self):
        self.approve()
        resumed = self.act('resume', from_session_id='session-1', session_id='session-2', resume_ref='user:continue')
        self.assertEqual('proposed', resumed['revisions'][-1]['disposition'])
        self.assertFalse(resumed['revisions'][-1]['presented'])
        event = self.event(); event['session_id'] = 'session-2'
        self.denied(event)

    def test_update_receipt_checks_actual_page_identity_without_previous_save(self):
        target = 'https://app.notion.com/p/' + 'a' * 32
        proposal = dict(self.proposal, notion_target=target, tool_name='mcp__codex_apps__notion_notion_update_page',
                        tool_input={'page_id': target, 'command': 'replace_content', 'new_str': self.draft.read_text()})
        candidate = self.call(proposal)
        self.revision = candidate['revisions'][-1]; self.ids['revision_id'] = self.revision['revision_id']
        self.approve()
        event=self.event();event.update(tool_name=proposal['tool_name'],tool_input=proposal['tool_input'])
        self.call(event)
        with self.assertRaises(ledger.LedgerError):
            self.act('saved', **self.readback(target=target, page_url='https://app.notion.com/p/' + 'b' * 32))
        self.assertEqual('saved', self.act('saved', **self.readback(target=target, page_url=target))['revisions'][-1]['write_state'])

    def test_stop_is_bounded_even_without_presentation(self):
        event = {'hook_event_name': 'Stop', 'session_id': 'session-1', 'cwd': str(self.root)}
        self.assertEqual(self.call(event)['decision'], 'block')
        self.assertEqual(self.call(self.proposal)['revisions'][-1]['stop_requested'], True)
        for _ in range(4):
            self.assertEqual(self.call(event), {})
        proposal = dict(self.proposal, result_key='second-outcome')
        self.call(proposal)
        self.assertEqual(self.call(dict(event, stop_hook_active=True)), {})
        self.assertEqual(self.call(event), {})

    def test_namespaces_reads_unknown_mutations_and_fail_closed(self):
        for tool in ('mcp__codex_apps__notion_notion_update_page', 'mcp__codex_apps__notion__create_pages',
                     'mcp__notion__API_patch_block', 'mcp__notion__unknown_operation',
                     'mcp__notion__append_block_children', 'mcp__notion__update_page'):
            event = self.event()
            event['tool_name'] = tool
            self.denied(event)
        for tool in ('mcp__notion__retrieve_page', 'mcp__codex_apps__notion_notion_fetch', 'mcp__linear__save_issue'):
            event = self.event()
            event['tool_name'] = tool
            self.assertEqual(self.call(event), {})
        (self.base / 'state.json').write_text('broken state')
        self.denied(self.event())
        self.assertIn('unavailable', records.handle({'hook_event_name': 'Stop', 'session_id': 'session-1'}, self.base)['systemMessage'])

    def test_draft_payload_and_target_binding(self):
        for change in ({'notion_target': 'collection://wrong'},
                       {'tool_input': {'parent': {'data_source_id': 'records'}, 'pages': [{'content': 'wrong'}]}}):
            with self.assertRaises(ledger.LedgerError):
                self.call(dict(self.proposal, **change))
        event = self.event()
        event.update(tool_name='mcp__notion__query', tool_input={'query': 'mutation { deletePage }'})
        self.denied(event)
        for tool, args in (
                ('mcp__notion__delete_page', {'page_id': 'page'}),
                ('mcp__codex_apps__notion_notion_update_page',
                 {'page_id': 'page', 'command': 'update_properties', 'properties': {}})):
            with self.assertRaises(ledger.LedgerError):
                self.call(dict(self.proposal, tool_name=tool, tool_input=args, notion_target='page'))

    def test_native_page_url_and_cli_help(self):
        self.approve()
        self.call(self.event())
        url = 'https://app.notion.com/p/' + 'a' * 32
        self.assertEqual('saved', self.act('saved', **self.readback(page_url=url))['revisions'][-1]['write_state'])
        result = subprocess.run([sys.executable, '-B', str(Path(records.__file__)), '--help'],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(0, result.returncode)
        self.assertIn('propose', result.stdout)

    def test_canonical_create_denied_and_rewrite_needs_new_approval(self):
        self.approve()
        self.call(self.event())
        saved = self.act('saved', **self.readback())
        self.draft.write_text('Reviewed final body\n')
        proposal = copy.deepcopy(self.proposal)
        proposal['tool_input']['pages'][0]['content'] = self.draft.read_text()
        candidate = self.call(proposal)
        self.revision = candidate['revisions'][-1]
        self.ids['revision_id'] = self.revision['revision_id']
        self.approve()
        event = self.event()
        event['tool_input'] = proposal['tool_input']
        self.denied(event)
        url = saved['canonical_page']['page_url']
        proposal.update(notion_target=url, tool_name='mcp__codex_apps__notion_notion_update_page',
                        tool_input={'page_id': url, 'command': 'replace_content', 'new_str': self.draft.read_text()})
        candidate = self.call(proposal)
        self.revision = candidate['revisions'][-1]
        self.ids['revision_id'] = self.revision['revision_id']
        event.update(tool_name=proposal['tool_name'], tool_input=proposal['tool_input'])
        self.denied(event)
        self.approve()
        self.assertEqual(self.call(event)['hookSpecificOutput']['permissionDecision'], 'allow')
        self.assertEqual(self.act('saved', **self.readback(target=url))['canonical_page'], saved['canonical_page'])

    def test_privacy_and_private_permissions(self):
        prompt = 'SECRET PROMPT MUST NOT BE STORED'
        with patch.object(records, 'SKILL', self.root / 'installed/work-records/SKILL.md'):
            result = records.handle({'hook_event_name': 'UserPromptSubmit', 'prompt': prompt}, self.base)
        text = result['hookSpecificOutput']['additionalContext']
        self.assertIn('Linear', text)
        self.assertIn(str(self.root / 'installed/work-records/SKILL.md'), text)
        self.assertIn('not installed', text)
        state = (self.base / 'state.json').read_text()
        self.assertNotIn(prompt, state)
        self.assertNotIn(self.draft.read_text().strip(), state)
        self.assertNotIn('properties', state)
        self.assertEqual(os.stat(self.base).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(self.base / 'state.json').st_mode & 0o777, 0o600)

    def test_cli_bad_json_fails_closed_without_home_writes(self):
        result = subprocess.run([sys.executable, '-B', str(Path(records.__file__))], input='not JSON',
                                capture_output=True, text=True, env={**os.environ, 'HOME': str(self.root)})
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.root / '.local').exists())

    def test_partial_body_update_reconciles_before_separate_property_write(self):
        page = 'https://app.notion.com/p/' + 'a' * 32
        first = dict(self.proposal, notion_target=page,
                     tool_name='mcp__codex_apps__notion_notion_update_page',
                     tool_input={'page_id': page, 'command': 'replace_content',
                                 'new_str': self.draft.read_text(), 'properties': {'Outcome': 'new'}})
        with self.assertRaisesRegex(ledger.LedgerError, 'cannot update properties'):
            self.call(first)
        # A historical approved call may have contained ignored properties.
        first['tool_input']['properties'] = {}
        candidate = self.call(first)
        self.ids['revision_id'] = candidate['revisions'][-1]['revision_id']
        self.revision = candidate['revisions'][-1]
        self.approve()
        event = self.event(); event.update(tool_name=first['tool_name'], tool_input=first['tool_input'])
        self.call(event)
        saved = self.act('saved', **self.readback(target=page, page_url=page, properties={'title': 'Result'}))
        self.assertEqual('saved', saved['revisions'][-1]['write_state'])
        second = dict(first, tool_input={'page_id': page, 'command': 'update_properties',
                                         'properties': {'Outcome': 'new'}})
        candidate = self.call(second)
        self.ids['revision_id'] = candidate['revisions'][-1]['revision_id']
        self.revision = candidate['revisions'][-1]
        self.act('presented', presentation_ref='chat:property')
        self.act('decide', decision='approved', user_decision_ref='user:property',
                 draft_sha256=self.revision['draft_sha256'])
        event.update(tool_use_id='call-2', tool_input=second['tool_input'])
        self.call(event)
        with self.assertRaisesRegex(ledger.LedgerError, 'properties differ'):
            self.act('saved', **self.readback(target=page, page_url=page, properties={'Outcome': 'old'}))
        self.assertEqual('partial', self.act('saved', outcome='partial',
                         **self.readback(target=page, page_url=page,
                                         properties={'Outcome': 'old'}))['revisions'][-1]['write_state'])

    def test_saved_record_needs_independent_backlinks_and_review_to_finalize(self):
        page = 'https://app.notion.com/p/' + 'a' * 32
        index = 'https://app.notion.com/p/' + 'b' * 32
        issue = 'https://linear.app/maeng/issue/MAE-10'
        proposal = copy.deepcopy(self.proposal)
        other_issue = 'https://linear.app/maeng/issue/MAE-11'
        proposal.update(linear_refs=[issue, other_issue], output_issue_ref=issue,
                        project_index_target=index)
        self.draft.write_text(f'Verified result\n{issue}\n{other_issue}\n{index}\n')
        proposal['tool_input']['pages'][0]['content'] = self.draft.read_text()
        candidate = self.call(proposal)
        self.ids['revision_id'] = candidate['revisions'][-1]['revision_id']
        self.revision = candidate['revisions'][-1]
        self.approve()
        event = self.event(); event['tool_input'] = proposal['tool_input']
        self.call(event)
        saved = self.act('saved', **self.readback(page_url=page))
        self.assertEqual('saved-draft', saved['revisions'][-1]['editorial_state'])
        self.assertEqual('pending', saved['revisions'][-1]['link_state'])
        self.act('reviewed', review_ref='review:1', verdict='approved')
        with self.assertRaisesRegex(ledger.LedgerError, 'verified Linear/Notion links'):
            self.act('finalized', user_decision_ref='user:final')
        linear_path = self.root / 'linear.json'; index_path = self.root / 'index.json'
        linear_path.write_text(json.dumps({'issue_url': issue, 'description': 'no output link'}))
        index_path.write_text(json.dumps({'index_url': index, 'content': f'[result]({page})'}))
        link = dict(linear_readback_path=str(linear_path), index_readback_path=str(index_path), evidence_ref='fetch:links')
        with self.assertRaisesRegex(ledger.LedgerError, 'Linear output backlink'):
            self.act('linked', **link)
        linear_path.write_text(json.dumps({'issue_url': other_issue, 'description': f'[result]({page})'}))
        with self.assertRaisesRegex(ledger.LedgerError, 'Linear output backlink'):
            self.act('linked', **link)
        linear_path.write_text(json.dumps({'issue_url': issue,
                                           'description': f'[result](https://example.com/{"a" * 32})'}))
        with self.assertRaisesRegex(ledger.LedgerError, 'Linear output backlink'):
            self.act('linked', **link)
        linear_path.write_text(json.dumps({'issue_url': issue, 'description': f'[result]({page})'}))
        index_path.write_text(json.dumps({'index_url': 'https://app.notion.com/p/' + 'c' * 32,
                                          'content': f'[result]({page})'}))
        with self.assertRaisesRegex(ledger.LedgerError, 'project index backlink'):
            self.act('linked', **link)
        index_path.write_text(json.dumps({'index_url': 'https://example.com/' + 'b' * 32,
                                          'content': f'[result]({page})'}))
        with self.assertRaisesRegex(ledger.LedgerError, 'project index backlink'):
            self.act('linked', **link)
        index_path.write_text(json.dumps({'index_url': index, 'content': f'[result]({page})'}))
        linked = self.act('linked', **link)
        self.assertEqual('verified', linked['revisions'][-1]['link_state'])
        final = self.act('finalized', user_decision_ref='user:final')
        self.assertEqual('final', final['revisions'][-1]['editorial_state'])
        replay = self.act('saved', **self.readback(page_url=page))
        self.assertEqual('final', replay['revisions'][-1]['editorial_state'])
        self.assertEqual('verified', replay['revisions'][-1]['link_state'])

    def test_standing_maintenance_updates_outcome_but_cannot_confirm_completed(self):
        page = 'https://app.notion.com/p/' + 'a' * 32
        self.approve(); self.call(self.event())
        self.act('saved', **self.readback(page_url=page,
                 properties={'title': 'Result', 'Status': 'In progress', 'Outcome': 'Verification pending'}))
        current = self.root / 'current.json'
        current.write_text(json.dumps({'content': self.draft.read_text(), 'page_url': page,
            'evidence_ref': 'fetch:current-outcome',
            'properties': {'Status': 'In progress', 'Outcome': 'Verification pending'}}))
        proposal = dict(self.proposal, maintenance=True,
                        maintenance_evidence_ref='fetch:current-outcome',
                        maintenance_current_readback_path=str(current), notion_target=page,
                        tool_name='mcp__codex_apps__notion_notion_update_page',
                        tool_input={'page_id': page, 'command': 'update_properties',
                                    'properties': {'Outcome': 'Verification completed'}})
        for properties in ({'Status': 'Completed'}, {'Name': 'Other'}):
            with self.assertRaises(ledger.LedgerError):
                self.call(dict(proposal, tool_input={**proposal['tool_input'], 'properties': properties}))
        with self.assertRaisesRegex(ledger.LedgerError, 'bounded factual correction'):
            self.call(dict(proposal, tool_input={**proposal['tool_input'],
                      'properties': {'Outcome': 'Completely unrelated release shipped'}}))
        with self.assertRaises(ledger.LedgerError):
            self.call(dict(proposal, endix=True))
        candidate = self.call(proposal)
        self.ids['revision_id'] = candidate['revisions'][-1]['revision_id']
        revision = candidate['revisions'][-1]
        with self.assertRaisesRegex(ledger.LedgerError, 'present draft'):
            self.act('decide', decision='approved', user_decision_ref=records.STANDING_MAINTENANCE_REF,
                     draft_sha256=revision['draft_sha256'])
        self.act('decide', decision='approved', authorization_mode='standing-maintenance',
                 user_decision_ref=records.STANDING_MAINTENANCE_REF,
                 draft_sha256=revision['draft_sha256'])
        event = self.event(); event.update(tool_use_id='call-2', tool_name=proposal['tool_name'],
                                           tool_input=proposal['tool_input'])
        self.assertEqual('allow', self.call(event)['hookSpecificOutput']['permissionDecision'])
        readback = self.root / 'maintained.json'
        readback.write_text(json.dumps({'content': self.draft.read_text(), 'target': page,
            'page_url': page, 'evidence_ref': 'fetch:maintained', 'parent_target': 'collection://records',
            'properties': {'title': 'Result', 'Status': 'In progress', 'Outcome': 'Verification completed'}}))
        saved = self.act('saved', readback_path=str(readback), page_url=page, target=page,
                         evidence_ref='fetch:maintained')
        self.assertEqual('saved', saved['revisions'][-1]['write_state'])
        corrected = self.root / 'corrected.md'
        corrected.write_text('Verified outcome\n')
        current_sentence = self.root / 'current-sentence.json'
        current_sentence.write_text(json.dumps({'content': self.draft.read_text(), 'page_url': page,
            'evidence_ref': 'fetch:stale-sentence',
            'properties': {'Status': 'In progress', 'Outcome': 'Verification completed'}}))
        sentence = dict(proposal, draft_path=str(corrected),
                        maintenance_evidence_ref='fetch:stale-sentence',
                        maintenance_current_readback_path=str(current_sentence),
                        tool_input={'page_id': page, 'command': 'update_content',
                                    'content_updates': [{'old_str': 'Verified result',
                                                         'new_str': 'Verified outcome'}]})
        with self.assertRaisesRegex(ledger.LedgerError, 'bounded sentence correction'):
            self.call(sentence)

    def test_maintenance_keeps_prior_user_completed_decision_after_review_and_links(self):
        page = 'https://app.notion.com/p/' + 'a' * 32
        index = 'https://app.notion.com/p/' + 'b' * 32
        issue = 'https://linear.app/maeng/issue/MAE-20'
        self.draft.write_text(f'Verified result\n{issue}\n{index}\n')
        initial = copy.deepcopy(self.proposal)
        initial.update(linear_refs=[issue], output_issue_ref=issue, project_index_target=index)
        initial['tool_input']['pages'][0]['content'] = self.draft.read_text()
        candidate = self.call(initial)
        self.ids['revision_id'] = candidate['revisions'][-1]['revision_id']
        self.revision = candidate['revisions'][-1]
        self.approve()
        first = self.event(); first['tool_input'] = initial['tool_input']
        self.call(first)
        self.act('saved', **self.readback(page_url=page,
                 properties={'title': 'Result', 'Status': 'Completed', 'Outcome': 'verified'}))
        linear = self.root / 'linear.json'; index_path = self.root / 'index.json'
        linear.write_text(json.dumps({'issue_url': issue, 'description': f'[result]({page})'}))
        index_path.write_text(json.dumps({'index_url': index, 'content': f'[result]({page})'}))
        links = dict(linear_readback_path=str(linear), index_readback_path=str(index_path),
                     evidence_ref='fetch:links')
        self.act('linked', **links)
        self.act('reviewed', review_ref='review:initial', verdict='approved')
        self.act('finalized', user_decision_ref='user:completed')
        next_draft = self.root / 'maintained-draft.md'
        next_draft.write_text(self.draft.read_text())
        current = self.root / 'completed-current.json'
        current.write_text(json.dumps({'content': self.draft.read_text(), 'page_url': page,
            'evidence_ref': 'fetch:new-fact',
            'properties': {'Status': 'Completed', 'Outcome': 'verified'}}))
        maintenance = dict(initial, draft_path=str(next_draft), notion_target=page,
                           maintenance=True, maintenance_evidence_ref='fetch:new-fact',
                           maintenance_current_readback_path=str(current),
                           tool_name='mcp__codex_apps__notion_notion_update_page',
                           tool_input={'page_id': page, 'command': 'update_properties',
                                       'properties': {'Outcome': 'verified later'}})
        candidate = self.call(maintenance)
        self.ids['revision_id'] = candidate['revisions'][-1]['revision_id']
        revision = candidate['revisions'][-1]
        self.act('decide', decision='approved', authorization_mode='standing-maintenance',
                 user_decision_ref=records.STANDING_MAINTENANCE_REF,
                 draft_sha256=revision['draft_sha256'])
        event = self.event(); event.update(tool_use_id='call-2', tool_name=maintenance['tool_name'],
                                           tool_input=maintenance['tool_input'])
        self.call(event)
        later = self.root / 'later.json'
        later.write_text(json.dumps({'content': next_draft.read_text(), 'target': page,
            'page_url': page, 'evidence_ref': 'fetch:later', 'parent_target': 'collection://records',
            'properties': {'title': 'Result', 'Status': 'Completed', 'Outcome': 'verified later'}}))
        self.act('saved', readback_path=str(later), page_url=page, target=page,
                 evidence_ref='fetch:later')
        self.act('linked', **links)
        reviewed = self.act('reviewed', review_ref='review:later', verdict='approved')
        self.assertEqual('final', reviewed['revisions'][-1]['editorial_state'])
        self.assertEqual('user:completed', reviewed['revisions'][-1]['final_approval_ref'])

    def test_standing_sentence_correction_is_bounded(self):
        page = 'https://app.notion.com/p/' + 'a' * 32
        self.draft.write_text('Verified result\nEvidence and limits remain documented in this record.\n')
        initial = copy.deepcopy(self.proposal)
        initial['tool_input']['pages'][0]['content'] = self.draft.read_text()
        candidate = self.call(initial)
        self.ids['revision_id'] = candidate['revisions'][-1]['revision_id']
        self.revision = candidate['revisions'][-1]
        self.approve()
        event = self.event(); event['tool_input'] = initial['tool_input']
        self.call(event)
        self.act('saved', **self.readback(page_url=page, properties={'title': 'Result', 'Status': 'In progress'}))
        current = self.root / 'fresh.json'
        current.write_text(json.dumps({'content': self.draft.read_text(), 'page_url': page,
                                        'evidence_ref': 'fetch:fresh', 'properties': {'Status': 'In progress'}}))
        revised = self.root / 'revised.md'
        revised.write_text(self.draft.read_text().replace('Verified result', 'Verified outcome'))
        proposal = dict(initial, draft_path=str(revised), notion_target=page, maintenance=True,
                        maintenance_evidence_ref='fetch:fresh', maintenance_current_readback_path=str(current),
                        tool_name='mcp__codex_apps__notion_notion_update_page',
                        tool_input={'page_id': page, 'command': 'update_content',
                                    'content_updates': [{'old_str': 'Verified result',
                                                         'new_str': 'Verified outcome'}]})
        revised.write_text(revised.read_text() + 'Unapproved extra claim\n')
        with self.assertRaisesRegex(ledger.LedgerError, 'more than the prepared passages'):
            self.call(proposal)
        revised.write_text(revised.read_text().replace('Unapproved extra claim\n', ''))
        self.assertTrue(self.call(proposal)['revisions'][-1]['maintenance'])

    def test_standing_maintenance_cannot_retry_after_absence(self):
        page = 'https://app.notion.com/p/' + 'a' * 32
        self.approve(); self.call(self.event())
        self.act('saved', **self.readback(page_url=page,
                 properties={'title': 'Result', 'Status': 'In progress', 'Outcome': 'Verification pending'}))
        current = self.root / 'fresh.json'
        current.write_text(json.dumps({'content': self.draft.read_text(), 'page_url': page,
            'evidence_ref': 'fetch:fresh', 'properties': {'Status': 'In progress',
                                                        'Outcome': 'Verification pending'}}))
        proposal = dict(self.proposal, notion_target=page, maintenance=True,
                        maintenance_evidence_ref='fetch:fresh', maintenance_current_readback_path=str(current),
                        tool_name='mcp__codex_apps__notion_notion_update_page',
                        tool_input={'page_id': page, 'command': 'update_properties',
                                    'properties': {'Outcome': 'Verification completed'}})
        candidate = self.call(proposal)
        self.ids['revision_id'] = candidate['revisions'][-1]['revision_id']
        revision = candidate['revisions'][-1]
        decision = dict(decision='approved', authorization_mode='standing-maintenance',
                        user_decision_ref=records.STANDING_MAINTENANCE_REF,
                        draft_sha256=revision['draft_sha256'])
        self.act('decide', **decision)
        event = self.event(); event.update(tool_use_id='call-2', tool_name=proposal['tool_name'],
                                           tool_input=proposal['tool_input'])
        self.call(event)
        absent = self.root / 'absent.json'
        absent.write_text(json.dumps({'absent': True, 'target': page, 'evidence_ref': 'fetch:absent'}))
        self.act('saved', outcome='absent', readback_path=str(absent), target=page,
                 evidence_ref='fetch:absent')
        with self.assertRaisesRegex(ledger.LedgerError, 'standing decision'):
            self.act('decide', **decision)
        self.denied(event | {'tool_use_id': 'call-3'})

    def test_real_thread_id_rejects_entry_receipt(self):
        with patch.object(records, 'BASE', self.root / 'thread-bound'), patch.dict(os.environ, {'CODEX_THREAD_ID': 'real-thread'}):
            with self.assertRaisesRegex(ledger.LedgerError, 'entry receipt is not a session id'):
                records.dispatch(self.proposal)
            good = dict(self.proposal, session_id='real-thread')
            self.assertEqual('real-thread', records.dispatch(good)['session_id'])

    def test_policy_content_update_preserves_complete_draft_without_backlink_gate(self):
        page = 'https://app.notion.com/p/' + 'a' * 32
        self.draft.write_text('Current rule\nindex-1\nlinear:1\n')
        proposal = dict(self.proposal, result_key='policy-1', record_kind='policy',
                        notion_target=page, tool_name='mcp__codex_apps__notion_notion_update_page',
                        tool_input={'page_id': page, 'command': 'update_content',
                                    'content_updates': [{'old_str': 'Old rule', 'new_str': 'Current rule'}]})
        candidate = self.call(proposal)
        self.ids = dict(session_id='session-1', candidate_id=candidate['candidate_id'],
                        revision_id=candidate['revisions'][-1]['revision_id'])
        self.revision = candidate['revisions'][-1]
        self.approve()
        event = self.event(); event.update(tool_name=proposal['tool_name'], tool_input=proposal['tool_input'])
        self.call(event)
        saved = self.act('saved', **self.readback(target=page, page_url=page, properties={}))
        self.assertEqual('not-required', saved['revisions'][-1]['link_state'])
        stop = self.call({'hook_event_name': 'Stop', 'session_id': 'session-1'})
        self.assertNotIn('project-index backlinks', stop.get('reason', ''))

    def test_reproposal_cannot_retarget_approved_links(self):
        self.approve()
        missing_owner = dict(self.proposal); missing_owner.pop('output_issue_ref')
        with self.assertRaisesRegex(ledger.LedgerError, 'output_issue_ref'):
            self.call(missing_owner)
        changed = dict(self.proposal, project_index_target='different-index')
        candidate = self.call(changed)
        self.assertNotEqual(self.revision['revision_id'], candidate['revisions'][-1]['revision_id'])
        self.assertEqual('proposed', candidate['revisions'][-1]['disposition'])
        self.assertEqual('index-1', candidate['revisions'][0]['project_index_target'])

    def test_legacy_mixed_rewrite_can_record_verified_partial_result(self):
        page = 'https://app.notion.com/p/' + 'a' * 32
        proposal = dict(self.proposal, notion_target=page,
                        tool_name='mcp__codex_apps__notion_notion_update_page',
                        tool_input={'page_id': page, 'command': 'replace_content',
                                    'new_str': self.draft.read_text()})
        candidate = self.call(proposal)
        self.ids['revision_id'] = candidate['revisions'][-1]['revision_id']
        self.revision = candidate['revisions'][-1]
        self.approve()
        event = self.event(); event.update(tool_name=proposal['tool_name'], tool_input=proposal['tool_input'])
        self.call(event)
        mixed = dict(proposal['tool_input'], properties={'Outcome': 'new'})
        state_path = self.base / 'state.json'; state = json.loads(state_path.read_text())
        revision = state[self.ids['candidate_id']]['revisions'][-1]
        revision['input_sha256'] = records.fingerprint(mixed)
        revision.pop('property_hashes')
        state_path.write_text(json.dumps(state))
        approved = self.root / 'mixed-input.json'; approved.write_text(json.dumps(mixed))
        partial = self.act('saved', outcome='partial', approved_input_path=str(approved),
                           **self.readback(target=page, page_url=page, properties={'Outcome': 'old'}))
        self.assertEqual('partial', partial['revisions'][-1]['write_state'])


if __name__ == '__main__':
    unittest.main()
