import unittest
import json
import uuid

from maeng import receipts
from maeng.common import canonical, sha256
from .helpers import HarnessCase

DB = "db111111111111111111111111111111"
PAGE = "0a1b2c3d-1111-2222-3333-444455556666"
CREATE = "mcp__claude_ai_Notion__notion-create-pages"
UPDATE = "mcp__claude_ai_Notion__notion-update-page"
FETCH = "mcp__claude_ai_Notion__notion-fetch"


class G2Tests(HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.start(self.repo)
        self.payload = {"parent": {"data_source_id": DB}, "pages": [{"properties": {"title": "Outcome"}}]}

    def sol_pass(self, payload, dest, op, verdict="pass"):
        v = {"verdict": verdict, "reviewer": {"model": "gpt-6.1-sol", "effort": "medium"}, "findings": [],
             "subject": {"kind": "notion", "repo": None, "pr": None, "base": None, "head": None, "criteria_rev": None,
                         "digest": sha256(canonical(payload)), "destination": dest, "op": op}}
        f = self.tmp / f"v-{uuid.uuid4().hex[:6]}.json"
        f.write_text(json.dumps(v))
        return self.cli("maeng-review", ["store", str(f)], self.repo).stdout.strip()

    def call(self, tool, tin, tuid):
        return self.pre(self.repo, tool, tin, tool_use_id=tuid)

    def post(self, tool, tin, tuid, response=None, error=None):
        if error:
            return self.hook("PostToolUseFailure", self.repo, tool_name=tool, tool_input=tin, tool_use_id=tuid, error=error)
        return self.hook("PostToolUse", self.repo, tool_name=tool, tool_input=tin, tool_use_id=tuid, tool_response=response)

    def test_missing_receipt_denied(self):
        denied, reason = self.call(CREATE, self.payload, "t1")
        self.assertTrue(denied)
        self.assertIn("no Sol pass receipt", reason)

    def test_digest_and_destination_mismatch_denied(self):
        self.sol_pass(self.payload, DB, "create")
        changed = {**self.payload, "pages": [{"properties": {"title": "Edited after review"}}]}
        denied, reason = self.call(CREATE, changed, "t1")
        self.assertTrue(denied)
        self.assertIn("digest", reason)
        self.sol_pass(changed, "otherdb", "create")
        denied, reason = self.call(CREATE, changed, "t2")
        self.assertTrue(denied)
        self.assertIn("mismatch", reason)
        self.sol_pass(changed, DB, "update")
        self.assertTrue(self.call(CREATE, changed, "t3")[0])

    def test_unreadable_receipt_denied(self):
        key = self.sol_pass(self.payload, DB, "create")
        (receipts.receipts_dir() / f"{key}.json").write_text("not json")
        denied, reason = self.call(CREATE, self.payload, "t1")
        self.assertTrue(denied)
        self.assertIn("unreadable", reason)

    def test_fail_verdict_is_not_enough(self):
        self.sol_pass(self.payload, DB, "create", verdict="fail")
        self.assertTrue(self.call(CREATE, self.payload, "t1")[0])

    def test_out_of_scope_notion_write_is_not_gated(self):
        other = {"parent": {"page_id": "cccccccccccccccccccccccccccccccc"}, "pages": []}
        self.assertFalse(self.call(CREATE, other, "t1")[0])
        self.assertFalse(self.pre(self.repo, "mcp__claude_ai_Notion__notion-search", {"query": "x"})[0])

    def test_full_lifecycle_consumes_only_after_readback(self):
        key = self.sol_pass(self.payload, DB, "create")
        self.assertFalse(self.call(CREATE, self.payload, "t1")[0])
        self.assertEqual(receipts.load(key)["status"], "pending")
        self.assertEqual(receipts.read_journal()[0]["status"], "pending")
        self.post(CREATE, self.payload, "t1", response={"pages": [{"id": PAGE}]})
        self.assertEqual(receipts.read_journal()[0]["status"], "sent")
        self.assertEqual(receipts.load(key)["status"], "pending")
        self.post(FETCH, {"id": PAGE}, "t2", response={"title": "Outcome"})
        self.assertEqual(receipts.load(key)["status"], "consumed")
        self.assertIn(PAGE.replace("-", ""), receipts.registry_ids())
        self.assertTrue(self.call(CREATE, self.payload, "t3")[0])      # single use

    def test_rejected_create_allows_retry(self):
        key = self.sol_pass(self.payload, DB, "create")
        self.call(CREATE, self.payload, "t1")
        self.post(CREATE, self.payload, "t1", error="Notion API error: validation_error")
        self.assertEqual(receipts.load(key)["status"], "unconsumed")
        self.assertFalse(self.call(CREATE, self.payload, "t2")[0])

    def test_create_ok_but_readback_fails_blocks_next_update_until_reconcile(self):
        key = self.sol_pass(self.payload, DB, "create")
        self.call(CREATE, self.payload, "t1")
        self.post(CREATE, self.payload, "t1", response={"pages": [{"id": PAGE}]})
        self.post(FETCH, {"id": PAGE}, "t2", error="timeout")           # readback failed
        update = {"page_id": PAGE, "command": "update_properties", "properties": {"title": "v2"}}
        self.sol_pass(update, PAGE.replace("-", ""), "update")
        denied, reason = self.call(UPDATE, update, "t3")
        self.assertTrue(denied)
        self.assertIn("readback", reason)
        self.assertTrue(self.call(CREATE, self.payload, "t4")[0])       # every further G2 write is blocked
        out = self.cli("maeng-review", ["reconcile", "--notion", receipts.read_journal()[0]["id"], "--page-id", PAGE], self.repo)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(receipts.load(key)["status"], "consumed")
        self.assertFalse(self.call(UPDATE, update, "t5")[0])

    def test_reconcile_absent_page_allows_retry(self):
        key = self.sol_pass(self.payload, DB, "create")
        self.call(CREATE, self.payload, "t1")
        self.post(CREATE, self.payload, "t1", response={})              # no page id came back
        self.assertTrue(self.call(CREATE, self.payload, "t2")[0])
        self.cli("maeng-review", ["reconcile", "--notion", receipts.read_journal()[0]["id"], "--absent"], self.repo)
        self.assertEqual(receipts.load(key)["status"], "unconsumed")
        self.assertFalse(self.call(CREATE, self.payload, "t3")[0])

    def test_update_scope_is_the_registry(self):
        update = {"page_id": PAGE, "command": "update_properties"}
        self.assertFalse(self.call(UPDATE, update, "t1")[0])            # unknown page: not gated
        self.cli("maeng-review", ["registry", "seed", PAGE], self.repo)
        denied, reason = self.call(UPDATE, update, "t2")
        self.assertTrue(denied)
        self.assertIn("no Sol pass receipt", reason)


class G3Tests(HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.eta_root.mkdir()
        (self.eta_root / "file.txt").write_text("eta")
        self.start(self.repo)

    def denied(self, cmd, text=None):
        d, reason = self.bash_pre(self.repo, cmd)
        self.assertTrue(d, f"expected deny: {cmd} ({reason})")
        if text:
            self.assertIn(text, reason)

    def allowed(self, cmd):
        d, reason = self.bash_pre(self.repo, cmd)
        self.assertFalse(d, f"expected allow: {cmd} ({reason})")

    def test_edit_write_notebook_to_eta_denied(self):
        for tool, key in (("Edit", "file_path"), ("Write", "file_path"), ("NotebookEdit", "notebook_path")):
            self.assertTrue(self.pre(self.repo, tool, {key: str(self.eta_root / "file.txt")})[0], tool)
            self.assertTrue(self.pre(self.repo, tool, {key: str(self.eta_root / "new/dir/x.py")})[0], tool)
        self.assertFalse(self.pre(self.repo, "Edit", {"file_path": str(self.repo / "app.py")})[0])

    def test_eta_checkout_elsewhere_is_detected_by_origin(self):
        wt = self.make_repo("elsewhere", with_remote=False)
        self.git(wt, "remote", "add", "origin", "git@github.com:endix-foundation-v1/web.git")
        self.assertTrue(self.pre(self.repo, "Write", {"file_path": str(wt / "a.txt")})[0])
        self.denied(f"touch {wt}/x")

    def test_bash_local_targets(self):
        e = self.eta_root
        self.denied(f"git -C {e} commit -am x", "eta")
        self.denied(f"git -C {e} checkout -b x")
        self.denied(f"cd {e} && touch new.txt")
        self.denied(f"cd {e} && git commit -am x")
        self.denied(f"rm {e}/file.txt")
        self.denied(f"echo hi > {e}/file.txt")
        self.denied(f"cp app.py {e}/app.py")
        self.denied(f"sed -i s/a/b/ {e}/file.txt")

    def test_bash_read_only_access_to_eta_allowed(self):
        e = self.eta_root
        self.allowed(f"cat {e}/file.txt")
        self.allowed(f"ls {e}")
        self.allowed(f"grep -r eta {e}")
        self.allowed(f"git -C {e} log --oneline")
        self.allowed(f"cd {e} && ls")

    def test_session_cwd_drifting_into_eta_is_still_gated(self):
        d, _ = self.pre(self.eta_root, "Bash", {"command": "touch drift.txt"})
        self.assertTrue(d)    # the personal session's cwd persisted into eta: hooks stay active
        d, _ = self.pre(self.eta_root, "Bash", {"command": "ls"})
        self.assertFalse(d)

    def test_git_push_to_eta_urls(self):
        for url in ("https://github.com/maengseojun/eta_v1.git", "git@github.com:endix-foundation-v1/web.git",
                    "https://github.com/endix-foundation-v1/contracts"):
            self.denied(f"git push {url} feat", "eta")
            self.denied(f"git push {url} HEAD:refs/heads/feat")
        self.git(self.repo, "remote", "add", "etar", "https://github.com/maengseojun/eta_v1.git")
        self.denied("git push etar feat", "eta")
        self.denied(f"git push {self.eta_root} feat")

    def test_gh_remote_targets(self):
        self.denied("gh pr create -R endix-foundation-v1/x --title t --body b", "eta")
        self.denied("gh pr create --repo endix-foundation-v1/x --fill")
        self.denied("gh issue comment 1 -R maengseojun/eta_v1 -b hi")
        self.denied("gh api -X POST repos/endix-foundation-v1/x/issues/1/comments -f body=x")
        self.denied("gh issue create -R endix-foundation-v1/web -t x")
        self.allowed("gh pr view 1 -R endix-foundation-v1/x")
        self.allowed("gh issue list -R maengseojun/eta_v1")
        self.allowed("gh api repos/endix-foundation-v1/x/pulls")
        self.allowed("gh issue comment 1 -R maengseojun/other -b hi")

    def test_mcp_github_and_eta_linear(self):
        self.assertTrue(self.pre(self.repo, "mcp__github__create_issue", {"owner": "endix-foundation-v1", "repo": "x", "title": "t"})[0])
        self.assertTrue(self.pre(self.repo, "mcp__github__add_issue_comment", {"owner": "maengseojun", "repo": "eta_v1", "issue_number": 1, "body": "b"})[0])
        self.assertFalse(self.pre(self.repo, "mcp__github__get_issue", {"owner": "endix-foundation-v1", "repo": "x", "issue_number": 1})[0])
        self.assertFalse(self.pre(self.repo, "mcp__github__create_issue", {"owner": "maengseojun", "repo": "personal", "title": "t"})[0])
        self.assertTrue(self.pre(self.repo, "mcp__linear-endix__save_issue", {"title": "t"})[0])
        self.assertTrue(self.pre(self.repo, "mcp__linear-endix__save_comment", {"body": "b"})[0])
        self.assertFalse(self.pre(self.repo, "mcp__linear-endix__list_issues", {})[0])



class ShippedNotionDefaults(unittest.TestCase):
    def test_outcome_databases_gated_without_config(self):
        import os
        import tempfile
        from maeng import gates
        saved = {k: os.environ.get(k) for k in ("MAENG_NOTION_DBS", "MAENG_HOME")}
        with tempfile.TemporaryDirectory() as home:
            os.environ.pop("MAENG_NOTION_DBS", None)
            os.environ["MAENG_HOME"] = home
            try:
                dbs = gates.notion_dbs()
                runs = "7903c212-74ce-4738-997f-88c4421ab21d".replace("-", "")
                self.assertIn(runs, dbs)
                self.assertIn("e1e730a443014b538eb61f0fabc43840", dbs)
                scope = gates.notion_scope("mcp__claude_ai_Notion__notion-create-pages",
                                           {"parent": {"data_source_id": "7903c212-74ce-4738-997f-88c4421ab21d"}})
                self.assertEqual(scope, ("create", runs))
            finally:
                for k, v in saved.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
