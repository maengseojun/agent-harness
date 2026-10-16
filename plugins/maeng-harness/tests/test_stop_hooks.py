import json
from pathlib import Path

from .helpers import HOOK, HarnessCase

LINEAR_COMMENT = "mcp__claude_ai_Linear__save_comment"
OBSIDIAN_WRITE = "mcp__obsidian_vault__write_note"


def snapshot(*roots):
    seen = {}
    for root in roots:
        root = Path(root)
        if root.exists():
            for p in sorted(root.rglob("*")):
                seen[str(p)] = (p.stat().st_mtime_ns, p.stat().st_size) if p.is_file() else None
    return seen


class StopBase(HarnessCase):
    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.start(self.repo)

    def change_code(self, text="print('changed')\n"):
        (self.repo / "app.py").write_text(text)
        self.hook("PostToolUse", self.repo, tool_name="Edit", tool_input={"file_path": str(self.repo / "app.py")},
                  tool_response={})

    def stop(self, active=False):
        return self.hook("Stop", self.repo, stop_hook_active=active)

    def record(self, issue="MAE-220", tool=LINEAR_COMMENT, **extra):
        tin = extra or {"issueId": issue, "body": "progress"}
        self.hook("PostToolUse", self.repo, tool_name=tool, tool_input=tin, tool_response={"id": "c1"}, tool_use_id="r")

    def sessions(self):
        d = self.vault / "wiki/sessions"
        return sorted(d.glob("*.md")) if d.exists() else []


class StopTests(StopBase):
    def test_block_once_then_system_message_and_state_kept(self):
        self.change_code()
        rc, out, _ = self.stop(active=False)
        self.assertEqual(out["decision"], "block")
        self.assertIn("UNVERIFIED", out["reason"])
        self.assertIn("UNRECORDED", out["reason"])
        before = self.load_state()
        rc, out, _ = self.stop(active=True)
        self.assertNotIn("decision", out)
        self.assertIn("UNVERIFIED / UNRECORDED", out["systemMessage"])
        after = self.load_state()
        self.assertEqual(before["baseline_tree"], after["baseline_tree"])
        self.assertGreater(after["last_change_seq"], after["last_record_seq"])
        # the obligation survives into the next stop attempt
        self.assertEqual(self.stop(active=False)[1]["decision"], "block")

    def test_verified_and_recorded_stops_cleanly(self):
        self.change_code()
        self.run_check(self.repo, "pytest -q")
        self.record(issue="MAE-1")           # unbound: any Linear write after the change counts
        self.assertEqual(self.stop()[1], None)

    def test_skip_satisfies_verification_but_record_still_needed(self):
        self.change_code()
        self.cli("maeng-verify", ["skip", "prototype"], self.repo)
        out = self.stop()[1]
        self.assertNotIn("UNVERIFIED", out["reason"])
        self.assertIn("UNRECORDED", out["reason"])

    def test_question_only_turn_and_docs_only_change_pass(self):
        self.assertIsNone(self.stop()[1])
        (self.repo / "README.md").write_text("# changed docs\n")
        self.hook("PostToolUse", self.repo, tool_name="Write", tool_input={"file_path": str(self.repo / "README.md")}, tool_response={})
        self.assertIsNone(self.stop()[1])

    def test_failed_check_keeps_verification_obligation(self):
        self.change_code()
        self.run_check(self.repo, "pytest -q", ok=False)
        self.record(issue="MAE-1")
        out = self.stop()[1]
        self.assertIn("unresolved failure: pytest", out["reason"])

    def test_session_stub_written_and_refreshed_in_place(self):
        self.stop()
        files = self.sessions()
        self.assertEqual(len(files), 1)
        text = files[0].read_text()
        self.assertRegex(files[0].name, rf"^SESSION-none-\d{{8}}-\d{{4}}-{self.sid[:8]}\.md$")
        self.assertIn("world: personal", text)
        self.cli("maeng-verify", ["bind", "MAE-220"], self.repo)
        self.change_code()
        self.stop()
        self.assertEqual(self.sessions(), files)                 # same file refreshed, not duplicated
        self.assertIn("UNVERIFIED/UNRECORDED", files[0].read_text())
        self.assertIn("linear: [MAE-220]", files[0].read_text())
        self.hook("SessionEnd", self.repo, reason="other")
        ended = files[0].read_text()
        self.assertIn("ended:", ended)
        # Regression (staging S1): SessionEnd must keep the last Stop's open obligations.
        self.assertIn("Status: ended (UNVERIFIED/UNRECORDED)", ended)
        self.assertIn("## Open", ended)
        self.assertEqual([p for p in files[0].parent.iterdir() if p.name.startswith(".tmp")], [])

    def test_no_vault_means_no_stub_and_no_error(self):
        import shutil
        shutil.rmtree(self.vault)
        rc, out, err = self.stop()
        self.assertEqual(rc, 0)
        self.assertFalse(self.vault.exists())


class RecordObligation(StopBase):
    def setUp(self):
        super().setUp()
        self.cli("maeng-verify", ["bind", "MAE-220"], self.repo)
        self.change_code()
        self.run_check(self.repo, "pytest -q")

    def blocked_for_record(self):
        out = self.stop()[1]
        return bool(out) and "UNRECORDED" in out.get("reason", "")

    def test_unrelated_writes_do_not_count(self):
        self.record(issue="MAE-999")
        self.assertTrue(self.blocked_for_record())
        self.record(tool=OBSIDIAN_WRITE, path="wiki/sessions/x.md", content="---\nlinear: [MAE-5]\n---\nbody")
        self.assertTrue(self.blocked_for_record())
        self.record(tool=LINEAR_COMMENT, issueId="MAE-2200", body="near miss")
        self.assertTrue(self.blocked_for_record())
        self.hook("PostToolUse", self.repo, tool_name="mcp__claude_ai_Linear__get_issue",
                  tool_input={"id": "MAE-220"}, tool_response={}, tool_use_id="g")
        self.assertTrue(self.blocked_for_record())

    def test_related_linear_or_obsidian_write_counts(self):
        self.record(issue="MAE-220")
        self.assertFalse(self.blocked_for_record())

    def test_obsidian_note_with_linear_frontmatter_counts(self):
        self.record(tool=OBSIDIAN_WRITE, path="wiki/sessions/y.md", content="---\nid: y\nlinear: [MAE-220]\n---\nbody")
        self.assertFalse(self.blocked_for_record())

    def test_obsidian_frontmatter_update_counts(self):
        self.record(tool="mcp__obsidian_vault__update_frontmatter", path="wiki/a.md", frontmatter={"linear": ["MAE-220"]})
        self.assertFalse(self.blocked_for_record())

    def test_vault_file_write_with_frontmatter_counts(self):
        note = self.vault / "wiki/sessions/z.md"
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text("---\nlinear: [MAE-220]\n---\n")
        self.hook("PostToolUse", self.repo, tool_name="Write",
                  tool_input={"file_path": str(note), "content": "---\nlinear: [MAE-220]\n---\n"}, tool_response={})
        self.assertFalse(self.blocked_for_record())

    def test_start_comment_then_more_changes_still_requires_record(self):
        self.record(issue="MAE-220")                       # "starting work" style comment
        self.assertFalse(self.blocked_for_record())
        self.change_code("print('more changes after the comment')\n")
        self.run_check(self.repo, "pytest -q")
        self.assertTrue(self.blocked_for_record())
        self.record(issue="MAE-220")
        self.assertFalse(self.blocked_for_record())

    def test_decision_and_commit_are_substantive_changes(self):
        self.record(issue="MAE-220")
        self.assertFalse(self.blocked_for_record())
        self.cli("maeng-verify", ["decision", "use lease push"], self.repo)
        self.assertTrue(self.blocked_for_record())
        self.record(issue="MAE-220")
        self.git(self.repo, "checkout", "-qb", "work")
        self.hook("PostToolUse", self.repo, tool_name="Bash", tool_input={"command": "git commit --allow-empty -m x"},
                  tool_use_id="c", tool_response={})
        self.assertTrue(self.blocked_for_record())

    def test_failed_record_write_does_not_count(self):
        self.hook("PostToolUseFailure", self.repo, tool_name=LINEAR_COMMENT,
                  tool_input={"issueId": "MAE-220", "body": "x"}, tool_use_id="f", error="boom")
        self.assertTrue(self.blocked_for_record())


class SubagentAndStart(StopBase):
    def test_subagent_stop_requires_report_sections_once(self):
        kw = dict(agent_type="maeng-tools:implementer")
        out = self.hook("SubagentStop", self.repo, last_assistant_message="done, all good", stop_hook_active=False, **kw)[1]
        self.assertEqual(out["decision"], "block")
        self.assertIsNone(self.hook("SubagentStop", self.repo, last_assistant_message="x", stop_hook_active=True, **kw)[1])
        self.assertIsNone(self.hook("SubagentStop", self.repo, last_assistant_message="Verification: ok\nUnfinished: none",
                                    stop_hook_active=False, **kw)[1])
        self.assertIsNone(self.hook("SubagentStop", self.repo, last_assistant_message="x", agent_type="maeng-tools:researcher")[1])

    def test_session_start_context_is_small_and_exports_session_id(self):
        env_file = self.tmp / "envfile"
        self.env["CLAUDE_ENV_FILE"] = str(env_file)
        rc, out, _ = self.hook("SessionStart", self.repo, source="startup")
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertLessEqual(len(ctx.encode()), 2048)
        self.assertIn("maeng-harness", ctx)
        self.assertIn(f"MAENG_SESSION_ID={self.sid}", env_file.read_text())

    def test_session_start_lists_unisolated_eta_checkouts(self):
        self.eta_root.mkdir()
        rc, out, _ = self.hook("SessionStart", self.repo, source="startup")
        self.assertIn("maeng-eta-isolate", out["hookSpecificOutput"]["additionalContext"])


class EtaAndUnknown(HarnessCase):
    def test_eta_session_has_zero_side_effects(self):
        self.eta_root.mkdir()
        for cwd in (self.eta_root, self._eta_by_origin()):
            before = snapshot(self.maeng_home, self.vault, self.home)
            events = [("SessionStart", {"source": "startup"}), ("UserPromptSubmit", {"prompt": "x"}),
                      ("PreToolUse", {"tool_name": "Bash", "tool_input": {"command": "git push --force origin main"}, "tool_use_id": "1"}),
                      ("PostToolUse", {"tool_name": "Edit", "tool_input": {"file_path": str(cwd / "a")}, "tool_response": {}, "tool_use_id": "2"}),
                      ("PostToolUseFailure", {"tool_name": "Bash", "tool_input": {"command": "pytest"}, "error": "x", "tool_use_id": "3"}),
                      ("Stop", {"stop_hook_active": False}), ("SubagentStop", {"agent_type": "implementer"}),
                      ("SessionEnd", {"reason": "x"})]
            for event, fields in events:
                rc, out, err = self.hook(event, cwd, **fields)
                self.assertEqual(rc, 0, event)
                if event == "SessionStart":
                    ctx = out["hookSpecificOutput"]["additionalContext"]
                    self.assertIn("maeng-eta-isolate", ctx)
                    self.assertNotIn("\n", ctx)           # one warning line
                else:
                    self.assertIsNone(out, event)
            self.assertEqual(snapshot(self.maeng_home, self.vault, self.home), before)
        self.assertFalse(self.maeng_home.exists())

    def _eta_by_origin(self):
        repo = self.make_repo("eta-clone", with_remote=False)
        self.git(repo, "remote", "add", "origin", "https://github.com/maengseojun/eta_v1.git")
        return repo

    def test_unknown_classification_suppresses_records_and_denies_mutations(self):
        repo = self.make_repo("broken")
        self.git(repo, "checkout", "-qb", "feat")
        (repo / ".git/config").write_text("[core\n  broken")
        before = snapshot(self.maeng_home, self.vault)
        rc, out, _ = self.hook("SessionStart", repo, source="startup")
        self.assertIsNone(out)
        self.hook("UserPromptSubmit", repo, prompt="x")
        self.assertIsNone(self.hook("Stop", repo, stop_hook_active=False)[1])
        self.hook("SessionEnd", repo, reason="x")
        self.assertEqual(snapshot(self.maeng_home, self.vault), before)       # no state, no stub
        for cmd in ("git push origin feat", "git push --force origin feat", "gh pr comment 1 -b x", "gh pr create --fill",
                    "gh pr merge 1", "gh api -X POST repos/o/r/issues/1/comments -f body=x"):
            denied, reason = self.bash_pre(repo, cmd)
            self.assertTrue(denied, cmd)
            self.assertIn("cannot classify", reason)
        self.assertTrue(self.pre(repo, "Edit", {"file_path": str(repo / "app.py")})[0])
        self.assertTrue(self.pre(repo, "mcp__github__create_issue", {"owner": "o", "repo": "r", "title": "t"})[0])
        self.assertFalse(self.bash_pre(repo, "ls -la")[0])
        self.assertFalse(self.bash_pre(repo, "gh pr view 1")[0])
        self.assertFalse(self.pre(repo, "mcp__github__get_issue", {"owner": "o", "repo": "r", "issue_number": 1})[0])
        self.assertEqual(snapshot(self.maeng_home, self.vault), before)


class DispatcherFailureModes(HarnessCase):
    def run_main(self, stdin_text, handlers):
        import importlib.util
        import io
        from unittest import mock
        spec = importlib.util.spec_from_file_location("maeng_hooks_under_test", HOOK)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(mod.handlers, "HANDLERS", handlers), mock.patch("sys.stdin", io.StringIO(stdin_text)), \
                mock.patch("sys.stdout", out), mock.patch("sys.stderr", err):
            rc = mod.main()
        return rc, out.getvalue(), err.getvalue()

    def test_gate_crash_fails_closed_tracker_crash_fails_open(self):
        def boom(payload):
            raise RuntimeError("kaboom")
        rc, out, err = self.run_main(json.dumps({"hook_event_name": "PreToolUse"}), {"PreToolUse": boom})
        self.assertEqual(rc, 2)
        self.assertIn("kaboom", err)
        rc, out, err = self.run_main(json.dumps({"hook_event_name": "Stop"}), {"Stop": boom})
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")

    def test_malformed_input_and_unknown_events_are_inert(self):
        for text in ("", "not json", "[]"):
            rc, out, _ = self.run_main(text, {})
            self.assertEqual((rc, out), (0, ""))
        rc, out, _ = self.run_main(json.dumps({"hook_event_name": "Elicitation"}), {})
        self.assertEqual((rc, out), (0, ""))

    def test_internal_gate_error_becomes_deny_not_crash(self):
        repo = self.make_repo()
        self.start(repo)
        denied, reason = self.pre(repo, "Bash", {"command": 123})        # malformed tool_input
        self.assertFalse(denied)                                          # a non-string command is simply not parseable as risky
        denied, reason = self.pre(repo, "Bash", "garbage")
        self.assertFalse(denied)
