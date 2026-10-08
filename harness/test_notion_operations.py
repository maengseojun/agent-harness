"""Behavior checks for exact Notion authoring-operation approval."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import work_records as records

class Operations(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.base=self.root/'state'
        self.asset=self.root/'diagram.png';self.asset.write_bytes(b'image bytes')
        self.draft=self.root/'plan.md';self.draft.write_text('Upload this reviewed diagram to the personal page.')
        self.target='https://app.notion.com/p/'+'a'*32
        self.request=dict(action='propose',session_id='s',task_id='t',result_key='upload',record_kind='operation',draft_path=str(self.draft),linear_refs=[],completion_basis='reviewed',notion_target=self.target,endix=False,tool_name='mcp__codex_apps__notion_notion_create_file_upload',tool_input={'filename':'diagram.png'},asset_paths=[str(self.asset)],expected_state={'filename':'diagram.png','status':'uploaded'})
        self.tasks=patch.object(records.tool_hook,'session_tasks',return_value=[]);self.tasks.start();self.addCleanup(self.tasks.stop)
        self.mock=patch.object(records.tool_hook,'handle',return_value={});self.mock.start();self.addCleanup(self.mock.stop)
    def call(self,d):return records.dispatch(d,self.base)
    def prepare(self,r=None):
        r=r or self.request;c=self.call(r);v=c['revisions'][-1];self.ids=dict(session_id='s',candidate_id=c['candidate_id'],revision_id=v['revision_id'])
        self.call(dict(action='presented',**self.ids,presentation_ref='shown'))
        self.call(dict(action='decide',**self.ids,draft_sha256=v['draft_sha256'],decision='approved',user_decision_ref='user-save'))
        return dict(hook_event_name='PreToolUse',session_id='s',tool_use_id='once',tool_name=r['tool_name'],tool_input=r['tool_input'])
    def test_bound_asset_and_single_dispatch(self):
        e=self.prepare();self.assertEqual('allow',records.handle(e,self.base)['hookSpecificOutput']['permissionDecision'])
        e['tool_use_id']='again';self.assertEqual('deny',records.handle(e,self.base)['hookSpecificOutput']['permissionDecision'])
    def test_changed_file_denied(self):
        e=self.prepare();self.asset.write_bytes(b'different');self.assertEqual('deny',records.handle(e,self.base)['hookSpecificOutput']['permissionDecision'])
    def test_input_or_session_change_denied(self):
        e=self.prepare();e['tool_input']={'filename':'other.png'};self.assertEqual('deny',records.handle(e,self.base)['hookSpecificOutput']['permissionDecision'])
        e['tool_input']=self.request['tool_input'];e['session_id']='other';self.assertEqual('deny',records.handle(e,self.base)['hookSpecificOutput']['permissionDecision'])
    def test_database_destination_and_schema(self):
        r=copy.deepcopy(self.request);r.update(result_key='db',tool_name='mcp__codex_apps__notion_notion_create_database',tool_input={'parent':{'page_id':'a'*32},'schema':'CREATE TABLE ("Name" TITLE)'},asset_paths=[],expected_state={'title':'Registry'})
        e=self.prepare(r);e['tool_input']['schema']='changed';self.assertEqual('deny',records.handle(e,self.base)['hookSpecificOutput']['permissionDecision'])
        r['result_key']='wrong';r['tool_input']['parent']['page_id']='b'*32
        with self.assertRaises(records.ledger.LedgerError):self.call(r)
    def test_readback_required_and_mismatch_rejected(self):
        self.prepare();f=self.root/'receipt.json';f.write_text(json.dumps({'target':self.target,'evidence_ref':'fetch','resource_url':'file-upload://id','observed_state':{'status':'uploaded','filename':'diagram.png'}}))
        d=dict(action='saved',**self.ids,readback_path=str(f),target=self.target,evidence_ref='fetch')
        with self.assertRaises(records.ledger.LedgerError):self.call(d)
        e=dict(hook_event_name='PreToolUse',session_id='s',tool_use_id='once',tool_name=self.request['tool_name'],tool_input=self.request['tool_input']);records.handle(e,self.base)
        bad=json.loads(f.read_text());bad['observed_state']['status']='pending';f.write_text(json.dumps(bad))
        with self.assertRaises(records.ledger.LedgerError):self.call(d)
        bad['observed_state']['status']='uploaded';f.write_text(json.dumps(bad));self.assertEqual('saved',self.call(d)['revisions'][-1]['write_state'])
    def test_unknown_or_agent_operation_rejected(self):
        r=copy.deepcopy(self.request);r['tool_name']='mcp__codex_apps__notion_notion_create_unknown'
        with self.assertRaises(records.ledger.LedgerError):self.call(r)

if __name__=='__main__':unittest.main()
