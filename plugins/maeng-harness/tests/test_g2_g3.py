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

    def test_out_of_scope_notion_write_is_not_gated(self):
        other = {"parent": {"page_id": "cccccccccccccccccccccccccccccccc"}, "pages": []}
        self.assertFalse(self.call(CREATE, other, "t1")[0])
        self.assertFalse(self.pre(self.repo, "mcp__claude_ai_Notion__notion-search", {"query": "x"})[0])

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

    def test_bash_read_only_access_to_eta_allowed(self):
        e = self.eta_root
        self.allowed(f"cat {e}/file.txt")
        self.allowed(f"ls {e}")
        self.allowed(f"grep -r eta {e}")
        self.allowed(f"git -C {e} log --oneline")
        self.allowed(f"cd {e} && ls")

