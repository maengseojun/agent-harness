"""Cooperative gate regression tests; no live service or agent claims."""
import unittest
from pathlib import Path
import test_run as runner_fixture
from ledger import LedgerError, sha
from run import execute


class RuntimeHooksTests(unittest.TestCase):
    setUp = runner_fixture.ProjectRunnerTests.setUp
    call = runner_fixture.ProjectRunnerTests.call
    ready = runner_fixture.ProjectRunnerTests.ready
    # Reuse the isolated project/runner fixture, not its inherited test suite.
    def configured(self, requirements=None):
        execute(self.project, 'start', self.request)
        self.dest = {'id': 'notion', 'service': 'notion', 'workspace': 'personal-space',
                     'target': 'https://www.notion.so/fixed-page', 'output_owner': 'personal',
                     'operations': ['update'], 'authorization_ref': 'user:scoped-write'}
        self.policy = {'output_owner': 'personal', 'destinations': [self.dest],
                       'write_paths': ['output'], 'requirements': requirements or []}
        self.call('configure-hooks', **self.policy)

    def checked(self):
        # ready() starts the same immutable fixture request idempotently.
        return self.ready(complete=False)

    def intent(self, **extra):
        payload = self.project / 'payload.json'
        if not payload.exists():
            payload.write_text('{"body":"checked","properties":{"Task ID":"same-id"}}')
        return self.call('before-write', operation_id='write-1', destination_id='notion',
                         workspace='personal-space', target=self.dest['target'], operation='update',
                         payload_path='payload.json', payload_sha256=sha(payload.read_bytes()),
                         authorization_ref='user:scoped-write', **extra)

    def observed(self, outcome, attempt=1, **extra):
        (self.project / 'observed.txt').write_text('fixture remote observation: ' + outcome)
        return self.call('after-write', operation_id='write-1', attempt=attempt,
                         workspace='personal-space', target=self.dest['target'], outcome=outcome,
                         evidence_path='observed.txt', **extra)

    def test_write_binding_reconcile_and_readback(self):
        self.configured(); self.checked()
        first = self.intent()
        self.assertTrue(first['hook']['should_write'])
        with self.assertRaisesRegex(LedgerError, 'reconcile'):
            self.intent()
        self.observed('uncertain')
        with self.assertRaisesRegex(LedgerError, 'reconcile'):
            self.intent()
        self.observed('absent')
        self.assertEqual(self.intent()['hook']['attempt'], 2)
        with self.assertRaisesRegex(LedgerError, 'stale write attempt'):
            self.observed('verified', readback_path='payload.json')
        (self.project / 'readback.json').write_text('wrong')
        with self.assertRaisesRegex(LedgerError, 'mismatch'):
            self.observed('verified', attempt=2, readback_path='readback.json')
        (self.project / 'readback.json').write_bytes((self.project / 'payload.json').read_bytes())
        self.observed('verified', attempt=2, readback_path='readback.json')
        self.assertFalse(self.intent()['hook']['should_write'])
        self.assertEqual(self.call('complete')['stage'], 'done')
        (self.project / 'readback.json').write_text('drift')
        self.assertEqual(self.call('status')['stage'], 'awaiting-requirements')

    def test_write_scope_and_payload_change_rejected(self):
        self.configured(); self.checked()
        (self.project / 'payload.json').write_text('payload')
        args = dict(operation_id='write-1', destination_id='notion', workspace='other-space',
                    target=self.dest['target'], operation='update', payload_path='payload.json',
                    payload_sha256=sha(b'payload'), authorization_ref='user:scoped-write')
        with self.assertRaisesRegex(LedgerError, 'mismatch'):
            self.call('before-write', **args)
        args['workspace'] = 'personal-space'; args['payload_sha256'] = sha(b'old')
        with self.assertRaisesRegex(LedgerError, 'payload changed'):
            self.call('before-write', **args)
        self.intent(); self.observed('conflict')
        with self.assertRaisesRegex(LedgerError, 'reconcile'):
            self.intent()
        with self.assertRaisesRegex(LedgerError, 'incomplete'):
            self.call('complete')

    def test_frozen_policy_and_duplicate_operation(self):
        self.configured()
        with self.assertRaisesRegex(LedgerError, 'frozen'):
            self.call('configure-hooks', **{**self.policy, 'write_paths': []})
        self.checked(); self.intent()
        args = dict(operation_id='write-2', destination_id='notion', workspace='personal-space',
                    target=self.dest['target'], operation='update', payload_path='payload.json',
                    payload_sha256=sha((self.project / 'payload.json').read_bytes()),
                    authorization_ref='user:scoped-write')
        with self.assertRaisesRegex(LedgerError, 'existing operation'):
            self.call('before-write', **args)

    def test_duplicate_payload_path_cannot_bypass_operation_dedup(self):
        self.configured(); self.checked(); self.intent()
        (self.project / 'another-payload.json').write_bytes((self.project / 'payload.json').read_bytes())
        with self.assertRaisesRegex(LedgerError, 'existing operation'):
            self.call('before-write', operation_id='write-2', destination_id='notion',
                      workspace='personal-space', target=self.dest['target'], operation='update',
                      payload_path='another-payload.json', payload_sha256=sha((self.project / 'payload.json').read_bytes()),
                      authorization_ref='user:scoped-write')

    def test_delegation_scope_overlap_and_frozen_skills(self):
        self.configured()
        args = dict(role='worker', description='bounded output', acceptance=['one output'],
                    write_paths=['output/a'], refs=['fixture:source'])
        contract = self.call('before-delegate', delegation_id='worker-1', **args)['hook']['contract']
        self.assertEqual(contract['output_owner'], 'personal')
        self.assertTrue(contract['skills'][0]['text'])
        with self.assertRaisesRegex(LedgerError, 'overlap'):
            self.call('before-delegate', delegation_id='worker-2', **{**args, 'write_paths': ['output']})
        with self.assertRaisesRegex(LedgerError, 'exceeds'):
            self.call('before-delegate', delegation_id='worker-3', **{**args, 'write_paths': ['other']})
        with self.assertRaisesRegex(LedgerError, 'escapes'):
            self.call('before-delegate', delegation_id='worker-4', **{**args, 'write_paths': ['../escape']})
        self.checked()
        with self.assertRaisesRegex(LedgerError, 'incomplete'):
            self.call('complete')
        (self.project / 'worker.txt').write_text('fixture actual worker result')
        self.call('after-delegate', delegation_id='worker-1', agent_id='another-worker',
                  outcome='finished', evidence_path='worker.txt')
        self.assertEqual(self.call('complete')['stage'], 'done')

    def test_reviewer_is_readonly_and_not_author(self):
        self.configured(); self.checked()
        args = dict(role='reviewer', description='check actual artifact and evidence',
                    acceptance=['all acceptance'], write_paths=[], refs=['fixture:request'])
        self.call('before-delegate', delegation_id='review-1', **args)
        with self.assertRaisesRegex(LedgerError, 'read-only'):
            self.call('before-delegate', delegation_id='review-2', **{**args, 'write_paths': ['output']})
        (self.project / 'verifier.txt').write_text('fixture verifier output')
        with self.assertRaisesRegex(LedgerError, 'authored'):
            self.call('after-delegate', delegation_id='review-1', agent_id='fixture-worker',
                      outcome='finished', evidence_path='verifier.txt')
        self.call('after-delegate', delegation_id='review-1', agent_id='different-reviewer',
                  outcome='finished', evidence_path='verifier.txt')

    def test_required_install_evidence_and_drift(self):
        self.configured([{'id': 'install', 'kind': 'evidence', 'target': 'installed release hash'}])
        self.checked()
        with self.assertRaisesRegex(LedgerError, 'incomplete'):
            self.call('complete')
        (self.project / 'install.txt').write_text('fixture installer verification')
        with self.assertRaisesRegex(LedgerError, 'independent'):
            self.call('requirement', requirement_id='install', evidence_path='install.txt', agent_id='fixture-worker')
        self.call('requirement', requirement_id='install', evidence_path='install.txt', agent_id='fixture-reviewer')
        self.assertEqual(self.call('complete')['stage'], 'done')
        (self.project / 'install.txt').write_text('changed')
        self.assertEqual(self.call('status')['stage'], 'awaiting-requirements')

    def test_required_child_is_actually_inspected(self):
        self.configured([{'id': 'child', 'kind': 'child', 'target': 'child-task'}]); self.checked()
        with self.assertRaisesRegex(LedgerError, 'incomplete'):
            self.call('complete')
        child = {**self.request, 'task_id': 'child-task'}
        execute(self.project, 'start', child)
        def call(action, **extra):
            return execute(self.project, action, {'task_id': 'child-task',
                           **({} if action == 'status' else {'owner': 'fixture-coordinator'}), **extra})
        (self.project / 'child.md').write_text('child artifact')
        digest = call('artifact', path='child.md', worker_id='child-worker')['artifact']['sha256']
        call('check', artifact_sha256=digest, evidence_path='check.txt', check_id='child-check',
             agent_id='child-worker', exit_code=0)
        call('review', artifact_sha256=digest, evidence_path='review.txt', agent_id='child-reviewer',
             verdict='approved', covered_conditions=[0])
        with self.assertRaisesRegex(LedgerError, 'incomplete'):
            self.call('complete')
        call('complete')
        self.assertEqual(self.call('complete')['stage'], 'done')
        (self.project / 'child.md').write_text('child changed')
        self.assertEqual(self.call('status')['stage'], 'awaiting-requirements')


    def repair_checked(self):
        self.call('repair', reason_ref='fixture:changed-work')
        (self.project / 'summary.md').write_text('repaired artifact')
        digest = self.call('artifact', path='summary.md', worker_id='fixture-worker')['artifact']['sha256']
        self.call('check', artifact_sha256=digest, evidence_path='check.txt', check_id='fixture',
                  agent_id='fixture-worker', exit_code=0)
        self.call('review', artifact_sha256=digest, evidence_path='review.txt',
                  agent_id='fixture-reviewer', verdict='approved', covered_conditions=[0])

    def test_repair_preserves_history_without_stranding_writes(self):
        self.configured(); self.checked(); self.intent()
        (self.project / 'readback.json').write_bytes((self.project / 'payload.json').read_bytes())
        self.observed('verified', readback_path='readback.json')
        self.repair_checked()
        self.assertEqual(self.call('status')['runtime_hooks']['writes']['write-1']['outcome'], 'superseded')
        self.assertEqual(self.call('complete')['stage'], 'done')

    def test_uncertain_old_write_still_requires_reconciliation_after_repair(self):
        self.configured(); self.checked(); self.intent(); self.observed('uncertain')
        self.repair_checked()
        with self.assertRaisesRegex(LedgerError, 'incomplete'):
            self.call('complete')
        (self.project / 'readback.json').write_bytes((self.project / 'payload.json').read_bytes())
        self.observed('verified', readback_path='readback.json')
        self.assertEqual(self.call('complete')['stage'], 'done')

    def test_confirmed_absent_old_write_terminates_after_repair(self):
        self.configured(); self.checked(); self.intent(); self.observed('uncertain')
        self.repair_checked()
        self.observed('absent')
        record = self.call('status')['runtime_hooks']['writes']['write-1']
        self.assertEqual(record['outcome'], 'superseded')
        self.assertEqual(record['resolution_outcome'], 'absent')
        self.assertEqual(self.call('complete')['stage'], 'done')

    def test_blocked_delegate_can_finish_and_worker_invalidates_its_review(self):
        self.configured()
        self.call('before-delegate', delegation_id='worker-1', role='worker', description='bounded work',
                  acceptance=['output'], write_paths=['output'], refs=[])
        self.checked()
        (self.project / 'worker.txt').write_text('fixture result')
        self.call('after-delegate', delegation_id='worker-1', agent_id='fixture-reviewer',
                  outcome='blocked', evidence_path='worker.txt')
        state = self.call('after-delegate', delegation_id='worker-1', agent_id='fixture-reviewer',
                          outcome='finished', evidence_path='worker.txt')
        self.assertIsNone(state['review'])
        with self.assertRaisesRegex(LedgerError, 'reviewed'):
            self.call('complete')

    def test_repaired_work_needs_renewed_requirement_evidence(self):
        self.configured([{'id': 'install', 'kind': 'evidence', 'target': 'installed release'}]); self.checked()
        (self.project / 'install.txt').write_text('fixture install verification')
        self.call('requirement', requirement_id='install', evidence_path='install.txt', agent_id='fixture-reviewer')
        self.repair_checked()
        with self.assertRaisesRegex(LedgerError, 'incomplete'):
            self.call('complete')

    def test_missing_receipt_reports_blocked_and_can_recover(self):
        self.configured(); self.checked(); self.intent()
        (self.project / 'readback.json').write_bytes((self.project / 'payload.json').read_bytes())
        self.observed('verified', readback_path='readback.json')
        (self.project / 'readback.json').unlink()
        self.assertEqual(self.call('status')['stage'], 'blocked')
        # A mutation persists the I/O blocker discovered during status computation.
        with self.assertRaisesRegex(LedgerError, 'incomplete'):
            self.call('complete')
        self.assertEqual(self.call('status')['stage'], 'blocked')
        (self.project / 'readback.json').write_bytes((self.project / 'payload.json').read_bytes())
        self.call('clear-blocker', resolution_ref='fixture:receipt-restored')
        self.assertEqual(self.call('complete')['stage'], 'done')

if __name__ == '__main__':
    unittest.main()
