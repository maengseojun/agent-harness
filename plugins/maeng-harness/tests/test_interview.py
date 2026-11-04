"""MAE-313: the comprehension gate. Expected values come from the Spec (docs/design/MAE-313-plan.md) or hand reasoning."""
import hashlib
import json
import os
import unittest
import unittest.mock

from maeng import interview
from .helpers import HarnessCase

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

    def declare(self, parts=None, **extra):
        """A map; `parts` is {name: [globs]} or {name: ([globs], [aliases])}."""
        parts = parts or {"mint": ["src/mint/**"], "launch": ["src/launch/**"]}
        built = {n: {"paths": v[0], "aliases": v[1]} if isinstance(v, tuple) else {"paths": v, "aliases": []}
                 for n, v in parts.items()}
        built[interview.OVERALL] = {"paths": [], "aliases": []}
        interview.save_map(self.key, {"parts": built, "test": None, "current": {}, **extra})

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


if __name__ == "__main__":
    unittest.main()
