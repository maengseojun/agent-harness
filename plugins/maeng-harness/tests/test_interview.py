"""MAE-313: the comprehension gate. Expected values come from the Spec (docs/design/MAE-313-plan.md) or hand reasoning."""
import hashlib
import json
import os
import stat
import sys
import unittest
import unittest.mock

from maeng import guard, interview
from .helpers import ROOT, HarnessCase, run
from .test_merge import MergeBase

REAL_PS = interview._ps

WRAPPED = ("<system-reminder>x", "<task-notification>x", "<cross-session-message>x", "<side-sessions-event>x",
           "<ci-monitor-event>x", "  \n<system-reminder>indented")


class InterviewCase(HarnessCase):
    """A personal repo, its state key and a `ps` that sees an interactive parent."""

    def setUp(self):
        super().setUp()
        self.repo = self.make_repo()
        self.key = interview.repo_key(self.repo)
        self.ps = {}
        patcher = unittest.mock.patch.object(interview, "_ps", side_effect=lambda pid: self.ps.get(str(pid), ("", "")))
        patcher.start()
        self.addCleanup(patcher.stop)

    def prompt(self, text, sid=None, cwd=None):
        return interview.on_prompt({"prompt": text, "session_id": sid or self.sid, "cwd": str(cwd or self.repo)})

    def declare(self, parts=None, key=None, **extra):
        """A map; `parts` is {name: [globs]} or {name: ([globs], [aliases])}."""
        parts = parts or {"mint": ["src/mint/**"], "launch": ["src/launch/**"]}
        built = {n: {"paths": v[0], "aliases": v[1]} if isinstance(v, tuple) else {"paths": v, "aliases": []}
                 for n, v in parts.items()}
        built[interview.OVERALL] = {"paths": [], "aliases": []}
        interview.save_map(key or self.key, {"parts": built, "test": None, "current": {}, **extra})

    def open_rec(self, **fields):
        rec = {"kind": "design", "stage": "design", "part": "mint", "awaiting": "answer", "answer": None, **fields}
        interview.save_open(self.key, self.sid, rec)
        return rec

    def rec(self, sid=None):
        return interview.load_open(self.key, sid or self.sid)

    def ledger(self):
        path = self.maeng_home / "interviews" / self.key / "ledger.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()]


class RepoKey(InterviewCase):
    def test_worktrees_of_one_repository_share_the_key(self):
        wt = self.tmp / "wt"
        self.git(self.repo, "worktree", "add", "-q", "-b", "side", str(wt))
        self.assertEqual(interview.repo_key(wt), self.key)
        self.assertNotIn("/", self.key)

    def test_another_origin_has_another_key_and_no_origin_has_none(self):
        other = self.make_repo("other")
        self.git(other, "remote", "set-url", "origin", "https://github.com/someone/else.git")
        self.assertNotEqual(interview.repo_key(other), self.key)
        self.assertTrue(interview.repo_key(other).startswith("github.com_someone_else-"))
        bare = self.make_repo("bare", with_remote=False)
        self.assertIsNone(interview.repo_key(bare))
        self.assertIsNone(interview.repo_key(self.tmp / "missing"))


class MapAndPasses(InterviewCase):
    def test_no_map_is_none_and_a_corrupt_map_raises(self):
        self.assertIsNone(interview.load_map(self.key))
        path = self.maeng_home / "interviews" / self.key / "map.json"
        path.parent.mkdir(parents=True)
        path.write_text("{not json")
        with self.assertRaises(ValueError):
            interview.load_map(self.key)

    def test_parts_of_matches_globs_and_returns_every_owner(self):
        self.declare({"mint": ["src/mint/**", "docs/mint.md"], "launch": ["src/**/*.sol"], "ui": []})
        m = interview.load_map(self.key)
        self.assertEqual(interview.parts_of(m, "src/mint/a/b.py"), ["mint"])
        self.assertEqual(interview.parts_of(m, "docs/mint.md"), ["mint"])
        self.assertCountEqual(interview.parts_of(m, "src/mint/Token.sol"), ["mint", "launch"])
        self.assertEqual(interview.parts_of(m, "src/other.py"), [])
        self.assertEqual(interview.parts_of(m, "README.md"), [])
        self.assertEqual(interview.parts_of(None, "README.md"), [])

    def test_design_pass_waiver_and_reopen(self):
        self.assertFalse(interview.passed(self.key, "mint", "design"))
        interview.record_pass(self.key, "design", part="mint")
        self.assertTrue(interview.passed(self.key, "mint", "design"))
        self.assertFalse(interview.passed(self.key, "launch", "design"))
        interview.record_waiver(self.key, "design", "launch", "later")
        self.assertTrue(interview.passed(self.key, "launch", "design"))
        self.assertTrue(interview.clear_design(self.key, "mint"))
        self.assertTrue(interview.clear_design(self.key, "launch"))
        self.assertFalse(interview.clear_design(self.key, "launch"))
        self.assertFalse(interview.passed(self.key, "mint", "design"))
        self.assertFalse(interview.passed(self.key, "launch", "design"))

    def test_merge_pass_is_bound_to_the_patch_and_a_waiver_to_the_pr(self):
        interview.record_pass(self.key, "merge", pr=7, patch="aaa", head="h1")
        self.assertTrue(interview.passed(self.key, 7, "merge", "aaa"))
        self.assertTrue(interview.passed(self.key, 9, "merge", "aaa"))  # same patch on another PR number
        self.assertFalse(interview.passed(self.key, 7, "merge", "bbb"))
        self.assertFalse(interview.passed(self.key, 7, "merge"))
        interview.record_waiver(self.key, "pr", 7, "r")
        self.assertTrue(interview.passed(self.key, 7, "merge", "bbb"))
        self.assertTrue(interview.passed(self.key, "7", "merge"))
        self.assertFalse(interview.passed(self.key, 8, "merge", "bbb"))


class Capture(InterviewCase):
    def test_the_opening_sessions_message_becomes_the_answer(self):
        self.open_rec()
        note = self.prompt("it mints tokens once per epoch")
        self.assertEqual(self.rec()["answer"], "it mints tokens once per epoch")
        self.assertIn("maeng-interview next", note)

    def test_another_sessions_message_is_not_recorded(self):
        self.open_rec()
        self.assertIsNone(self.prompt("not yours", sid="sess-other"))
        self.assertIsNone(self.rec()["answer"])
        self.assertIsNone(self.rec("sess-other"))

    def test_a_system_wrapped_message_is_never_an_answer(self):
        self.open_rec()
        for text in WRAPPED:
            with self.subTest(text=text):
                self.assertIsNone(self.prompt(text))
                self.assertIsNone(self.rec()["answer"])

    def test_an_approval_is_not_an_answer_and_a_second_message_extends_the_first(self):
        self.open_rec()
        self.assertIsNone(self.prompt("승인 #5"))
        self.assertIsNone(self.rec()["answer"])
        self.prompt("first")
        self.prompt("second")
        self.assertEqual(self.rec()["answer"], "first\n\nsecond")

    def test_stop_closes_the_record_without_a_ledger_line(self):
        self.open_rec(awaiting="retry")
        self.assertIn("no penalty", self.prompt("  중단\n"))
        self.assertIsNone(self.rec())
        self.assertFalse((self.maeng_home / "interviews" / self.key / "ledger.jsonl").exists())
        self.open_rec()
        self.prompt("중단 아니고 계속")  # only the exact word stops
        self.assertEqual(self.rec()["answer"], "중단 아니고 계속")

    def test_an_appeal_is_taken_only_after_a_miss_and_needs_an_argument(self):
        self.open_rec(awaiting="retry")
        self.assertIsNone(self.prompt("이의"))
        self.assertIsNone(self.prompt("just chatting"))
        self.assertNotIn("appeal", self.rec())
        self.assertIn("maeng-interview appeal", self.prompt("이의 the rubric wants a fact I did state"))
        self.assertEqual(self.rec()["appeal"], "the rubric wants a fact I did state")
        self.assertIsNone(self.rec()["answer"])
        self.open_rec()  # while a question is open the same words are the answer
        self.prompt("이의 있어요, 그런데 답은 이렇습니다")
        self.assertEqual(self.rec()["answer"], "이의 있어요, 그런데 답은 이렇습니다")
        self.assertNotIn("appeal", self.rec())

    def test_nothing_open_and_no_map_touches_nothing(self):
        self.assertIsNone(self.prompt("hello"))
        self.assertIsNone(self.prompt("면제 ghost nothing declared"))
        self.assertFalse(self.maeng_home.exists())

    def test_a_map_without_an_open_record_creates_no_file(self):
        self.declare()
        before = sorted(p.name for p in (self.maeng_home / "interviews" / self.key).iterdir())
        self.assertIsNone(self.prompt("hello mint"))
        self.assertEqual(sorted(p.name for p in (self.maeng_home / "interviews" / self.key).iterdir()), before)


class Waivers(InterviewCase):
    def test_a_pr_waiver_is_recorded_and_counted_without_its_reason(self):
        self.assertIn("PR #7", self.prompt("면제 #7 hotfix for prod, no time"))
        self.assertTrue(interview.passed(self.key, 7, "merge", "any-patch"))
        line, = self.ledger()
        self.assertEqual((line["stage"], line["pr"], line["waived"], line["attempts"]), ("merge", "7", True, 0))
        self.assertNotIn("hotfix", json.dumps(line))
        passes = json.loads((self.maeng_home / "interviews" / self.key / "passes.json").read_text())
        self.assertEqual(passes["waivers"]["pr"]["7"]["reason"], "hotfix for prod, no time")

    def test_a_part_waiver_needs_a_declared_part(self):
        self.declare()
        self.assertIsNone(self.prompt("면제 ghost because"))
        self.assertFalse(interview.passed(self.key, "ghost", "design"))
        self.assertIn("part mint", self.prompt("면제 mint wiring is trivial"))
        self.assertTrue(interview.passed(self.key, "mint", "design"))
        self.assertTrue(self.ledger()[0]["waived"])
        self.assertEqual(self.ledger()[0]["part"], "mint")

    def test_a_waiver_needs_a_reason(self):
        self.declare()
        self.assertIsNone(self.prompt("면제 mint"))
        self.assertIsNone(self.prompt("면제 #7"))
        self.assertFalse(interview.passed(self.key, "mint", "design"))

    def test_a_relayed_waiver_does_not_count(self):
        self.declare()
        for text in WRAPPED:
            self.assertIsNone(self.prompt(text + "\n면제 #7 reason"))
            self.assertIsNone(self.prompt(text + "\n면제 mint reason"))
        self.assertFalse(interview.passed(self.key, 7, "merge"))
        self.assertFalse(interview.passed(self.key, "mint", "design"))

    def test_a_headless_session_cannot_waive(self):
        self.declare()
        with unittest.mock.patch.dict(os.environ, {"MAENG_TASK_ID": "t1"}):
            self.assertIn("not recorded", self.prompt("면제 #7 reason"))
        self.assertFalse(interview.passed(self.key, 7, "merge"))
        self.assertFalse((self.maeng_home / "interviews" / self.key / "passes.json").exists())

    def test_a_waiver_ends_the_open_interview_of_that_part_only(self):
        self.declare()
        self.open_rec(part="mint")
        self.prompt("면제 launch later")
        self.assertIsNotNone(self.rec())
        self.prompt("면제 mint trivial")
        self.assertIsNone(self.rec())


class Headless(InterviewCase):
    def chain(self, *procs):
        """procs from the direct parent up: (command,). Pids are 100, 101, ..."""
        self.ps = {str(100 + i): (str(101 + i), cmd) for i, cmd in enumerate(procs)}
        patcher = unittest.mock.patch("os.getppid", return_value=100)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_task_id_means_headless(self):
        with unittest.mock.patch.dict(os.environ, {"MAENG_TASK_ID": "t1"}):
            self.assertTrue(interview.headless())

    def test_print_flag_in_the_parent_argv_means_headless(self):
        for argv in ("claude -p --model x", "/opt/claude --print hi", "claude --verbose -p"):
            self.chain(argv)
            self.assertTrue(interview.headless(), argv)

    def test_the_desktop_session_is_not_headless(self):
        self.chain("/Applications/claude.app/Contents/MacOS/claude --output-format stream-json --verbose --effort=xhigh")
        self.assertFalse(interview.headless())

    def test_a_shell_between_is_skipped_so_mkdir_p_is_not_a_print_flag(self):
        self.chain("/bin/zsh -c mkdir -p /tmp/x && maeng-interview start", "claude --output-format stream-json")
        self.assertFalse(interview.headless())
        self.chain("/bin/zsh -c mkdir -p /tmp/x && maeng-interview start", "claude -p go")
        self.assertTrue(interview.headless())

    def test_a_failing_ps_is_not_headless(self):
        self.ps = {}
        self.assertFalse(interview.headless())

    def test_ps_output_is_split_into_parent_pid_and_command(self):
        with unittest.mock.patch("subprocess.run", return_value=unittest.mock.Mock(stdout="  4321 /bin/zsh -c  echo hi\n")) as run:
            self.assertEqual(REAL_PS(77), ("4321", "/bin/zsh -c  echo hi"))
        self.assertEqual(run.call_args.args[0], ["ps", "-o", "ppid=,command=", "-p", "77"])
        with unittest.mock.patch("subprocess.run", side_effect=OSError("no ps")):
            self.assertEqual(REAL_PS(77), ("", ""))


class NamingNote(InterviewCase):
    def setUp(self):
        super().setUp()
        self.declare({"mint": ["src/mint/**"], "launch": (["src/launch/**"], ["런치"]), "gov": ["src/gov/**"]},
                     current={self.sid: "mint"})

    def test_naming_another_part_before_the_current_one_passed_adds_a_note(self):
        note = self.prompt("Let's start on launch now")
        self.assertIn("`launch`", note)
        self.assertIn("`mint`", note)
        self.assertIn("switch launch", note)
        self.assertIn("`launch`", self.prompt("이제 런치 보자"))  # by alias

    def test_word_match_only_and_never_the_reserved_overall(self):
        self.assertIsNone(self.prompt("launchpad is a different word"))
        self.assertIsNone(self.prompt("overall this looks fine"))
        self.assertIsNone(self.prompt("keep going on mint"))

    def test_no_note_once_the_current_part_passed_and_nothing_else_changes(self):
        before = (self.maeng_home / "interviews" / self.key / "map.json").read_text()
        interview.record_pass(self.key, "design", part="mint")
        self.assertIsNone(self.prompt("now launch"))
        interview.clear_design(self.key, "mint")
        self.prompt("now launch")
        self.assertEqual((self.maeng_home / "interviews" / self.key / "map.json").read_text(), before)
        self.assertIsNone(self.rec())


class Seal(InterviewCase):
    DATA = "추천: 방식 A\r\ntrailing  \n".encode()

    def test_seal_prints_the_digest_prefix_before_the_user_answers(self):
        digest = interview.seal(self.key, self.sid, self.DATA)
        self.assertEqual(digest, hashlib.sha256(self.DATA).hexdigest()[:12])
        self.assertEqual(self.rec()["awaiting"], "choice")
        self.assertIsNone(self.rec()["answer"])

    def test_reveal_refuses_until_the_user_answered_after_the_seal(self):
        digest = interview.seal(self.key, self.sid, self.DATA)
        with self.assertRaisesRegex(interview.Refused, "has not answered"):
            interview.reveal(self.key, self.sid, digest)
        self.prompt("<system-reminder>my choice is B")
        self.prompt("B please", sid="sess-other")
        with self.assertRaisesRegex(interview.Refused, "has not answered"):
            interview.reveal(self.key, self.sid, digest)
        self.assertIn("reveal", self.prompt("B please"))
        self.assertEqual(interview.reveal(self.key, self.sid, digest), self.DATA)

    def test_reveal_closes_the_seal_and_writes_a_ledger_line_without_the_text(self):
        digest = interview.seal(self.key, self.sid, self.DATA)
        self.prompt("A")
        interview.reveal(self.key, self.sid, digest)
        self.assertIsNone(self.rec())
        line, = self.ledger()
        self.assertEqual((line["stage"], line["digest"], line["revealed"]), ("seal", digest, True))
        self.assertNotIn("방식", json.dumps(line, ensure_ascii=False))
        with self.assertRaises(interview.Refused):
            interview.reveal(self.key, self.sid, digest)

    def test_reveal_needs_the_digest_that_was_printed(self):
        digest = interview.seal(self.key, self.sid, self.DATA)
        self.prompt("A")
        for bad in ("", digest[:6], "0" * 12, digest[:-1] + ("0" if digest[-1] != "0" else "1")):
            with self.subTest(bad=bad), self.assertRaisesRegex(interview.Refused, "nothing is sealed"):
                interview.reveal(self.key, self.sid, bad)

    def test_a_sealed_text_that_changed_on_disk_is_not_revealed(self):
        digest = interview.seal(self.key, self.sid, self.DATA)
        self.prompt("A")
        (self.maeng_home / "interviews" / self.key / "seals" / f"{hashlib.sha256(self.DATA).hexdigest()}.txt").write_bytes(b"changed")
        with self.assertRaisesRegex(interview.Refused, "changed on disk"):
            interview.reveal(self.key, self.sid, digest)

    def test_sealing_while_an_interview_is_open_is_refused_and_a_new_seal_replaces_an_old_one(self):
        self.open_rec()
        with self.assertRaisesRegex(interview.Refused, "is open"):
            interview.seal(self.key, self.sid, self.DATA)
        interview.close_open(self.key, self.sid)
        first = interview.seal(self.key, self.sid, b"one")
        second = interview.seal(self.key, self.sid, b"two")
        self.assertNotEqual(first, second)
        self.assertEqual(self.rec()["digest"][:12], second)

    def test_stop_cancels_the_seal_wait(self):
        digest = interview.seal(self.key, self.sid, self.DATA)
        self.prompt("중단")
        with self.assertRaises(interview.Refused):
            interview.reveal(self.key, self.sid, digest)


class GateCase(InterviewCase):
    def eta_repo(self, name="eta-clone"):
        """An eta checkout (by its origin); the same one on every call."""
        repo = self.tmp / name
        if not repo.exists():
            repo = self.make_repo(name, with_remote=False)
            self.git(repo, "remote", "add", "origin", "https://github.com/maengseojun/eta_v1.git")
        return repo


class Hooks(GateCase):
    """K1 and K2: the handlers call the prompt capture."""

    def test_a_prompt_through_the_hook_is_captured_in_both_worlds(self):
        eta = self.eta_repo()
        for repo in (self.repo, eta):
            key = interview.repo_key(repo)
            interview.save_open(key, self.sid, {"kind": "design", "awaiting": "answer", "answer": None})
            rc, out, _ = self.hook("UserPromptSubmit", repo, prompt="my answer")
            self.assertEqual(rc, 0)
            self.assertIn("maeng-interview next", out["hookSpecificOutput"]["additionalContext"])
            self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
            self.assertEqual(interview.load_open(key, self.sid)["answer"], "my answer")

    def test_the_note_joins_the_other_prompt_context_in_personal(self):
        interview.save_open(self.key, self.sid, {"kind": "design", "awaiting": "answer", "answer": None})
        rc, out, _ = self.hook("UserPromptSubmit", self.repo, prompt="an answer")
        self.assertIn("maeng-interview next", out["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(self.load_state()["turn"], 1)  # the personal tracking still ran

    def test_a_normal_prompt_is_not_swallowed(self):
        self.declare()
        self.assertEqual(self.hook("UserPromptSubmit", self.eta_repo(), prompt="please fix the typo"), (0, None, ""))
        rc, out, _ = self.hook("UserPromptSubmit", self.repo, prompt="please fix the typo")
        self.assertNotIn("maeng-interview", json.dumps(out))

    def test_a_failing_prompt_check_never_blocks_the_prompt(self):
        if not self.in_process():
            self.skipTest("patches the module in this process")
        with unittest.mock.patch.object(interview, "on_prompt", side_effect=RuntimeError("boom")):
            rc, out, err = self.hook("UserPromptSubmit", self.repo, prompt="x")
        self.assertEqual(rc, 0)
        self.assertIn("interview prompt check failed", err)


class WriteGate(GateCase):
    """AC-1 / T1."""

    def setUp(self):
        super().setUp()
        self.eta = self.eta_repo()
        self.eta_key = interview.repo_key(self.eta)

    def edit(self, repo, rel, tool="Edit"):
        field = "notebook_path" if tool == "NotebookEdit" else "file_path"
        return self.pre(repo, tool, {field: str(repo / rel), "old_string": "a", "new_string": "b"})

    def both(self):
        return ((self.repo, self.key, "personal"), (self.eta, self.eta_key, "eta"))

    def test_without_a_map_or_on_an_unmapped_path_nothing_changes(self):
        for repo, key, world in self.both():
            with self.subTest(world=world):
                self.assertFalse(self.edit(repo, "src/mint/a.py")[0])
                self.declare(key=key)
                self.assertFalse(self.edit(repo, "README.md")[0])
                self.assertFalse(self.edit(repo, "src/other/b.py")[0])

    def test_a_mapped_path_is_denied_until_overall_and_the_part_passed(self):
        for repo, key, world in self.both():
            with self.subTest(world=world):
                self.declare(key=key)
                denied, why = self.edit(repo, "src/mint/a.py")
                self.assertTrue(denied)
                self.assertIn("overall, mint", why)
                interview.record_pass(key, "design", part="mint")
                denied, why = self.edit(repo, "src/mint/a.py")
                self.assertTrue(denied)
                self.assertIn("pass yet: overall", why)
                interview.record_pass(key, "design", part=interview.OVERALL)
                self.assertFalse(self.edit(repo, "src/mint/a.py")[0])
                self.assertTrue(self.edit(repo, "src/launch/c.py")[0])  # launch has no pass

    def test_every_edit_tool_and_a_new_file_are_covered(self):
        self.declare()
        for tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
            with self.subTest(tool=tool):
                self.assertTrue(self.edit(self.repo, "src/mint/deep/new/dir/x.py", tool)[0])

    def test_a_waiver_counts_as_a_pass(self):
        self.declare()
        interview.record_waiver(self.key, "design", "overall", "r")
        interview.record_waiver(self.key, "design", "mint", "r")
        self.assertFalse(self.edit(self.repo, "src/mint/a.py")[0])

    def test_a_path_in_two_parts_needs_both(self):
        self.declare({"mint": ["src/**"], "launch": ["src/launch/**"]})
        interview.record_pass(self.key, "design", part="overall")
        interview.record_pass(self.key, "design", part="mint")
        denied, why = self.edit(self.repo, "src/launch/c.py")
        self.assertTrue(denied)
        self.assertIn("pass yet: launch", why)

    def test_a_headless_run_is_exempt_but_not_from_the_state_directory(self):
        self.declare()
        self.env["MAENG_TASK_ID"] = "t1"
        self.assertFalse(self.edit(self.repo, "src/mint/a.py")[0])
        self.assertTrue(self.pre(self.repo, "Edit", {"file_path": str(self.maeng_home / "interviews" / "x")})[0])

    def test_the_file_decides_the_repository_not_the_cwd(self):
        self.declare()
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()
        self.assertTrue(self.pre(elsewhere, "Edit", {"file_path": str(self.repo / "src/mint/a.py")})[0])
        self.assertFalse(self.pre(self.repo, "Edit", {"file_path": str(elsewhere / "src/mint/a.py")})[0])

    def test_an_unreadable_map_denies_the_edit(self):
        path = self.maeng_home / "interviews" / self.key / "map.json"
        path.parent.mkdir(parents=True)
        path.write_text("{broken")
        denied, why = self.edit(self.repo, "README.md")
        self.assertTrue(denied)
        self.assertIn("unreadable", why)

    def test_the_state_directory_is_closed_to_edits_in_every_world(self):
        for repo, _, world in self.both():
            for tool in ("Edit", "Write"):
                with self.subTest(world=world, tool=tool):
                    denied, why = self.pre(repo, tool, {"file_path": str(self.maeng_home / "interviews" / "k" / "open" / "s.json")})
                    self.assertTrue(denied)
                    self.assertIn("belongs to the CLI", why)


class BashStateGate(GateCase):
    """A-6: the state directory and MAENG_CLAUDE."""

    def test_naming_the_directory_is_denied_in_both_worlds(self):
        base = self.maeng_home / "interviews"
        for repo in (self.repo, self.eta_repo()):
            for cmd in (f"cat {base}/k/open/s.json", f"ls {base}", "cat ~/.local/share/maeng-harness/interviews/k/map.json",
                        'ls "$MAENG_HOME/interviews"', f"echo hi > {base}/x", f"sh -c 'cat {base}/k/passes.json'",
                        f"true && cat {base}/k/open/s.json"):
                with self.subTest(cmd=cmd, repo=repo.name):
                    denied, why = self.bash_pre(repo, cmd)
                    self.assertTrue(denied)
                    self.assertIn("interview state", why)

    def test_setting_the_interview_model_is_denied_in_eta_by_the_gate_and_in_personal_by_g1(self):
        for repo in (self.eta_repo(), self.repo):
            denied, why = self.bash_pre(repo, "export MAENG_CLAUDE=/tmp/fake")
            self.assertTrue(denied)
            self.assertIn("MAENG_CLAUDE", why)
        self.assertTrue(self.bash_pre(self.eta_repo(), "env MAENG_CLAUDE=/tmp/fake python3 x.py")[0])

    def test_the_cli_itself_is_always_allowed_in_eta(self):
        eta = self.eta_repo()
        base = self.maeng_home / "interviews"
        self.assertFalse(self.bash_pre(eta, "MAENG_CLAUDE=/tmp/fake maeng-interview start --stage design")[0])
        self.assertFalse(self.bash_pre(eta, f"maeng-interview status && ls {self.tmp}")[0])
        self.assertTrue(self.bash_pre(eta, f"maeng-interview status && cat {base}/k/open/s.json")[0])  # only its own segment

    def test_ordinary_commands_that_mention_the_words_are_allowed(self):
        for repo in (self.repo, self.eta_repo()):
            for cmd in ("ls docs/interviews", "grep -rn interviews src", "git log --oneline | head -3",
                        "echo MAENG_CLAUDE is a name"):
                with self.subTest(cmd=cmd):
                    self.assertFalse(self.bash_pre(repo, cmd)[0])


class FailsOpen(GateCase):
    """T7."""

    def test_a_raising_matcher_allows_the_call_and_warns(self):
        if not self.in_process():
            self.skipTest("patches the module in this process")
        self.declare()
        for repo in (self.repo, self.eta_repo()):
            with unittest.mock.patch.object(interview, "_edit_gate", side_effect=RuntimeError("boom")):
                rc, out, err = self.hook("PreToolUse", repo, tool_name="Edit",
                                         tool_input={"file_path": str(repo / "src/mint/a.py")}, tool_use_id="t1")
            self.assertEqual((rc, out), (0, None))
            self.assertIn("interview gate error (RuntimeError: boom)", err)

    def test_a_command_the_matcher_cannot_read_is_allowed_in_eta(self):
        rc, out, err = self.hook("PreToolUse", self.eta_repo(), tool_name="Bash", tool_input={"command": 5}, tool_use_id="t1")
        self.assertEqual((rc, out), (0, None))
        self.assertIn("interview gate error", err)

    def test_the_eta_side_effect_test_is_unedited(self):
        diff = run(["git", "diff", "ad5c6e9", "--", "plugins/maeng-harness/tests/test_stop_hooks.py"],
                   cwd=ROOT.parents[1], env=self.env).stdout
        self.assertEqual(diff, "")

    def test_the_guard_comment_names_the_exception(self):
        self.assertIn("interview.gate", (ROOT / "lib/maeng/guard.py").read_text())


class MergeGateEta(GateCase):
    """AC-3 / T2 for `gh pr merge` and the merge MCP tool outside the personal world."""
    FIELDS = "number,additions,deletions,files,baseRefOid,headRefOid"

    def setUp(self):
        super().setUp()
        self.eta = self.eta_repo()
        self.eta_key = interview.repo_key(self.eta)
        self.base = self.head(self.eta)
        self.git(self.eta, "checkout", "-qb", "feat")
        (self.eta / "feat.py").write_text("".join(f"x{i} = {i}\n" for i in range(5)))
        self.h = self.commit_all(self.eta, "feat")
        self.pr_json, self.log = self.tmp / "pr.json", self.tmp / "gh.log"
        self.fake = self.tmp / "fake-gh"
        self.fake.write_text(f"#!{sys.executable}\nimport json, os, sys\n"
                             "open(os.environ['FAKE_GH_LOG'], 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
                             "sys.stdout.write(open(os.environ['FAKE_GH_JSON']).read())\n"
                             "sys.exit(int(os.environ.get('FAKE_GH_RC', '0')))\n")
        self.fake.chmod(self.fake.stat().st_mode | stat.S_IEXEC)
        self.env.update(MAENG_GH=str(self.fake), FAKE_GH_JSON=str(self.pr_json), FAKE_GH_LOG=str(self.log))
        self.declare({"mint": ["src/mint/**"]}, key=self.eta_key)
        self.set_pr(100, ["feat.py"])

    def set_pr(self, lines, paths):
        self.pr_json.write_text(json.dumps({"number": 7, "additions": lines - lines // 2, "deletions": lines // 2,
                                            "files": [{"path": p, "additions": 1, "deletions": 0} for p in paths],
                                            "baseRefOid": self.base, "headRefOid": self.h}))

    def patch(self):
        diff = run(["git", "diff", f"{self.base}...{self.h}"], cwd=self.eta, env=self.env).stdout
        return run(["git", "patch-id", "--stable"], cwd=self.eta, env=self.env, input_text=diff).stdout.split()[0]

    def merge(self, cmd="gh pr merge 7 --squash"):
        return self.bash_pre(self.eta, cmd)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_up_to_150_lines_and_an_unmapped_path_may_merge(self):
        self.set_pr(150, ["feat.py"])
        self.assertFalse(self.merge()[0])
        self.assertEqual(self.calls()[0], ["pr", "view", "7", "--json", self.FIELDS])

    def test_over_150_lines_or_a_mapped_path_needs_a_pass(self):
        for lines, paths in ((151, ["feat.py"]), (3, ["src/mint/a.py"]), (200, ["src/mint/a.py"])):
            self.set_pr(lines, paths)
            with self.subTest(lines=lines, paths=paths):
                denied, why = self.merge()
                self.assertTrue(denied)
                self.assertIn("merge-quiz pass", why)
                self.assertIn(self.patch()[:12], why)

    def test_every_gh_merge_route_is_covered(self):
        self.set_pr(151, ["feat.py"])
        for cmd in ("gh pr merge 7", "gh pr merge 7 --auto", "gh pr merge --auto --squash 7",
                    "gh pr merge 7 --admin --delete-branch", "sh -c 'gh pr merge 7'", 'bash -lc "gh pr merge 7 --auto"',
                    "eval 'gh pr merge 7'", "cd /tmp && gh pr merge 7", "true; gh pr merge 7",
                    "if true; then gh pr merge 7; fi", "echo $(gh pr merge 7)"):
            with self.subTest(cmd=cmd):
                self.assertTrue(self.merge(cmd)[0])

    def test_the_gh_call_reads_the_named_pr_and_repo(self):
        self.set_pr(10, ["feat.py"])
        self.merge("gh pr merge 7 -R someone/else")
        self.merge("gh pr merge")
        self.assertEqual(self.calls(), [["pr", "view", "7", "-R", "someone/else", "--json", self.FIELDS],
                                        ["pr", "view", "--json", self.FIELDS]])

    def test_other_gh_commands_are_not_read(self):
        for cmd in ("gh pr view 7", "gh pr merge --help", "gh pr list", "ls"):
            self.assertFalse(self.merge(cmd)[0], cmd)
        self.assertFalse(self.log.exists())

    def test_a_pass_for_this_patch_lets_it_merge_and_another_patch_does_not(self):
        self.set_pr(300, ["feat.py"])
        self.assertTrue(self.merge()[0])
        interview.record_pass(self.eta_key, "merge", pr=7, patch="not-this-patch", head=self.h)
        self.assertTrue(self.merge()[0])
        interview.record_pass(self.eta_key, "merge", pr=7, patch=self.patch(), head=self.h)
        self.assertFalse(self.merge()[0])
        self.assertFalse(self.merge("gh pr merge 7 --auto")[0])

    def test_a_waiver_for_the_pr_lets_it_through(self):
        self.set_pr(300, ["feat.py"])
        interview.record_waiver(self.eta_key, "pr", 8, "r")
        self.assertTrue(self.merge()[0])
        interview.record_waiver(self.eta_key, "pr", 7, "r")
        self.assertFalse(self.merge()[0])

    def test_an_unreadable_pr_denies(self):
        self.env["FAKE_GH_RC"] = "1"
        denied, why = self.merge()
        self.assertTrue(denied)
        self.assertIn("could not read the PR", why)
        del self.env["FAKE_GH_RC"]
        bad_types = json.dumps({"number": 7, "additions": "many", "deletions": 1, "files": [], "baseRefOid": "a", "headRefOid": "b"})
        for junk in ("not json", "{}", bad_types):
            self.pr_json.write_text(junk)
            with self.subTest(junk=junk[:20]):
                self.assertTrue(self.merge()[0])

    def test_a_command_it_cannot_parse_that_names_a_merge_is_denied(self):
        self.assertTrue(self.merge('gh pr merge 7 "unterminated')[0])
        self.assertFalse(self.merge('echo "unterminated')[0])

    def test_the_merge_mcp_tool_is_gated_in_eta(self):
        self.set_pr(300, ["feat.py"])
        for tool in ("mcp__github__merge_pull_request", "mcp__plugin_github_github__merge_pull_request"):
            denied, why = self.pre(self.eta, tool, {"owner": "maengseojun", "repo": "eta_v1", "pullNumber": 7})
            self.assertTrue(denied, tool)
            self.assertIn("merge-quiz pass", why)
        self.assertTrue(self.pre(self.eta, "mcp__github__merge_pull_request", {"owner": "o", "repo": "r"})[0])
        self.assertEqual(self.calls()[0], ["pr", "view", "7", "-R", "maengseojun/eta_v1", "--json", self.FIELDS])
        interview.record_pass(self.eta_key, "merge", pr=7, patch=self.patch(), head=self.h)
        self.assertFalse(self.pre(self.eta, "mcp__github__merge_pull_request",
                                  {"owner": "maengseojun", "repo": "eta_v1", "pull_number": 7})[0])

    def test_in_personal_the_merge_stays_with_g1(self):
        self.set_pr(300, ["feat.py"])
        denied, why = self.bash_pre(self.repo, "gh pr merge 7")
        self.assertTrue(denied)
        self.assertIn("maeng G1", why)
        self.assertNotIn("merge-quiz", why)
        denied, why = self.pre(self.repo, "mcp__github__merge_pull_request", {"owner": "o", "repo": "r", "pullNumber": 7})
        self.assertIn("maeng G1", why)
        self.assertFalse(self.log.exists())


class ShipGate(MergeBase):
    """AC-3 / T2 in personal: `maeng-ship merge` and the pass bound to the patch id."""

    def setUp(self):
        super().setUp()
        self.key = interview.repo_key(self.repo)
        self.env.update(MAENG_GH=str(self.fake_gh), FAKE_GH_JSON=str(self.pr_json))

    def declare(self, parts):
        built = {n: {"paths": v, "aliases": []} for n, v in parts.items()}
        built[interview.OVERALL] = {"paths": [], "aliases": []}
        interview.save_map(self.key, {"parts": built, "test": None, "current": {}})

    def grow(self, lines, name="big.py"):
        """A further commit adding `lines` lines; the PR now points at it, verified and reviewed."""
        (self.repo / name).write_text("".join(f"v{i} = {i}\n" for i in range(lines)))
        head = self.commit_all(self.repo, "big")
        self.git(self.repo, "push", "-q", "origin", "feat")
        self.set_pr(self.base, head)
        self.run_check(self.repo, "pytest -q")
        self.verdict(head=head)
        return head

    def patch(self, base, head):
        diff = self.git(self.repo, "diff", f"{base}...{head}").stdout
        return run(["git", "patch-id", "--stable"], cwd=self.repo, env=self.env, input_text=diff).stdout.split()[0]

    def test_a_small_unmapped_pr_ships_as_before(self):
        self.verdict()
        r = self.ship()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_pr_over_150_lines_is_refused_even_with_a_review_and_the_users_approval(self):
        head = self.grow(160)
        self.hook("UserPromptSubmit", self.repo, prompt="승인 #7")
        r = self.ship()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("merge-quiz pass", r.stderr)
        self.assertIn(self.patch(self.base, head)[:12], r.stderr)
        self.assertEqual(self.remote_main(), self.base)

    def test_exactly_150_changed_lines_ships(self):
        # c1 changes app.py (1 line added, 1 removed) and c2 adds lib.py (1 line): 3 changed lines, so 147 more make 150
        self.grow(147)
        r = self.ship()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_151_changed_lines_is_gated(self):
        self.grow(148)
        self.assertIn("changes 151 lines", self.ship().stderr)

    def test_a_pass_for_the_patch_or_a_waiver_lets_it_ship(self):
        head = self.grow(160)
        self.assertNotEqual(self.ship().returncode, 0)
        interview.record_pass(self.key, "merge", pr=7, patch=self.patch(self.base, head), head=head)
        r = self.ship()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_waiver_for_the_pr_lets_it_ship(self):
        self.grow(160)
        interview.record_waiver(self.key, "pr", 7, "hotfix")
        self.assertEqual(self.ship().returncode, 0)

    def test_a_small_pr_on_a_mapped_path_is_gated_too(self):
        self.declare({"app": ["app.py"]})
        self.verdict()
        r = self.ship()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("touches app", r.stderr)
        interview.record_waiver(self.key, "pr", 7, "r")
        self.assertEqual(self.ship().returncode, 0)

    def test_a_rebase_with_the_same_patch_keeps_the_pass_and_a_changed_diff_does_not(self):
        head = self.grow(160)
        interview.record_pass(self.key, "merge", pr=7, patch=self.patch(self.base, head), head=head)
        other = self.other_clone()
        (other / "elsewhere.txt").write_text("main moved")
        self.git(other, "add", "-A")
        self.git(other, "commit", "-qm", "main moved")
        self.git(other, "push", "-q", "origin", "main")
        self.git(self.repo, "fetch", "-q", "origin")
        self.git(self.repo, "rebase", "-q", "origin/main")
        new_base = self.git(self.repo, "rev-parse", "origin/main").stdout.strip()
        new_head = self.head(self.repo)
        self.assertNotEqual(new_head, head)
        repo = guard.normalize_repo(str(self.remote))
        self.assertIsNone(interview.require_merge(self.repo, repo, 7, new_base, new_head))
        (self.repo / "big.py").write_text("changed = 1\n" + (self.repo / "big.py").read_text())
        changed = self.commit_all(self.repo, "edit")
        self.assertIn("merge-quiz pass", interview.require_merge(self.repo, repo, 7, new_base, changed))


if __name__ == "__main__":
    unittest.main()
