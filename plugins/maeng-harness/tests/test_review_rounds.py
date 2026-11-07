"""MAE-326 S3 / AC-5: counted heads, guarded round-two narrowing and the one confirmation run."""
import hashlib
import json

from maeng import receipts
from .test_cli import ReviewRunFixture, load_bin

REV = hashlib.sha256(b"AC-1 feature works").hexdigest()  # the fixture plan's acceptance section
HIGH = {"severity": "high", "title": "T1 broken", "body": "b", "file": "app.py", "line": 1}


class Rounds(ReviewRunFixture):
    def reply(self, verdict, findings=()):
        self.result.write_text(json.dumps({"verdict": verdict, "findings": list(findings)}))

    def commit_file(self, name, text, msg="c"):
        (self.repo / name).write_text(text)
        h = self.commit_all(self.repo, msg)
        self.run_check(self.repo, "pytest -q")  # a new head needs its own verification evidence
        self.cli("maeng-verify", ["plan", "--met", "AC-1"], self.repo, check=True)
        return h

    def run_at(self, head, *extra, base=None):
        self.log.unlink(missing_ok=True)
        return self.cli("maeng-review", ["run", "--kind", "code", "--pr", "7", "--base", base or self.base,
                                         "--head", head, "--base-ref", "main", *extra], self.repo,
                        extra_env={"MAENG_CODEX": str(self.codex)})

    def bundle(self):
        sent = self.stdin_log.read_text()
        return json.loads(sent[sent.index("\n{") + 1:])

    def stored_reviews(self):
        return sorted((self.maeng_home / "reviews").glob("*.json"), key=lambda p: p.stat().st_mtime_ns)

    def stored_subject(self, r=None):
        """Subject of the newest stored verdict (a run prints only verdict, receipt and findings)."""
        return json.loads(self.stored_reviews()[-1].read_text())["subject"]


class Counting(Rounds):
    def test_same_head_reruns_and_blocked_verdicts_do_not_count(self):
        rv = load_bin("maeng-review")
        self.reply("fail", [HIGH])
        r = self.run_at(self.h)
        repo = self.stored_subject(r)["repo"]
        self.assertEqual(rv.prior_rounds(repo, "7"), 1)
        self.run_at(self.h)  # same head again
        self.reply("blocked", [{**HIGH, "file": None, "line": None, "title": "cannot judge"}])
        self.run_at(self.h)
        self.assertEqual(self.run_at(self.h, "--exclude", "app.py").returncode, 1)  # a scope split of the same head
        self.assertEqual(rv.prior_rounds(repo, "7"), 1)
        self.reply("fail", [HIGH])
        h2 = self.commit_file("app.py", "print('two')\n")
        self.run_at(h2)
        self.assertEqual(rv.prior_rounds(repo, "7"), 2)
        h3 = self.commit_file("app.py", "print('three')\n")
        r = self.run_at(h3)
        self.assertEqual(r.returncode, 2)
        self.assertIn("review round cap", r.stderr)
        self.assertIn("--confirm", r.stderr)
        self.assertFalse(self.log.exists())
        self.assertEqual(self.run_at(self.h).returncode, 1)  # an already reviewed head is still reviewable

    def test_a_local_block_spends_no_round(self):
        rv = load_bin("maeng-review")
        self.reply("fail", [HIGH])
        repo = self.stored_subject(self.run_at(self.h))["repo"]
        (self.repo / "app.py").write_text("print('unverified')\n")
        h2 = self.commit_all(self.repo, "no evidence")
        self.assertEqual(self.run_at(h2).returncode, 2)
        self.assertEqual(rv.prior_rounds(repo, "7"), 1)


class Narrowing(Rounds):
    def first_round(self, *extra):
        self.reply("fail", [HIGH])
        r = self.run_at(self.h, *extra)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    def second_head(self):
        self.commit_file("other.py", "x = 1\n", "other")
        return self.commit_file("app.py", "print('fixed')\n", "fix")

    def second_round(self, head, *extra, base=None):
        self.reply("pass")
        r = self.run_at(head, *extra, base=base)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return self.bundle(), self.stored_subject(r), r

    def test_round_two_reads_only_the_change_since_the_previous_head(self):
        self.first_round()
        h2 = self.second_head()
        bundle, subject, r = self.second_round(h2)
        self.assertEqual(bundle["review_mode"], "round2")
        self.assertEqual([f["title"] for f in bundle["previous_findings"]], ["T1 broken"])
        self.assertIn("other.py", bundle["diff"])  # not read in full before: full
        self.assertNotIn("app.py", bundle["diff"])
        self.assertIn("fixed", bundle["delta_diff"])  # read in full before: only what changed since
        self.assertEqual(subject["coverage"], [{"file": "app.py", "mode": "delta"}, {"file": "other.py", "mode": "full"}])
        self.assertEqual((subject["review_mode"], subject["previous_head"]), ("round2", self.h))
        self.assertEqual(subject["files_reviewed"], ["app.py", "other.py"])
        recs, problem = receipts.find_code(self.repo, subject["repo"], self.base, h2, "refs/heads/main", REV)
        self.assertEqual(len(recs or []), 1, problem)  # the narrowed receipt still covers every file for ship

    def assert_full(self, bundle, subject):
        self.assertEqual(bundle["review_mode"], "round2")
        self.assertEqual({c["mode"] for c in subject["coverage"]}, {"full"})
        self.assertFalse(bundle.get("delta_diff"))
        self.assertEqual([f["title"] for f in bundle["previous_findings"]], ["T1 broken"])

    def test_a_different_base_means_full_scope(self):
        self.first_round()
        h2 = self.second_head()
        self.assert_full(*self.second_round(h2, base=self.h)[:2])

    def test_changed_criteria_mean_full_scope(self):
        self.first_round()
        h2 = self.second_head()
        plan = self.tmp / "plan2.md"
        plan.write_text("Requirements -> acceptance:\nAC-1 feature works well\n\n## Verification\nAC-1: pytest\n")
        self.cli("maeng-verify", ["bind", "MAE-221", "--plan", str(plan), "--parent", "MAE-216"], self.repo, check=True)
        self.cli("maeng-verify", ["plan", "--met", "AC-1"], self.repo, check=True)
        bundle, subject, _ = self.second_round(h2)
        self.assert_full(bundle, subject)
        self.assertNotEqual(subject["criteria_rev"], REV)

    def test_a_head_that_does_not_descend_from_the_previous_head_means_full_scope(self):
        self.first_round()
        self.git(self.repo, "checkout", "-q", "-b", "other", self.base)
        h2 = self.commit_file("app.py", "print('sibling')\n", "sibling")
        self.assert_full(*self.second_round(h2)[:2])

    def test_missing_coverage_metadata_means_full_scope(self):
        self.first_round()
        for f in self.stored_reviews():  # a receipt written before coverage existed
            v = json.loads(f.read_text())
            v["subject"].pop("coverage")
            f.write_text(json.dumps(v))
        h2 = self.second_head()
        self.assert_full(*self.second_round(h2)[:2])

    def test_previously_excluded_files_are_read_in_full(self):
        self.commit_file("extra.py", "y = 1\n", "extra")
        self.reply("fail", [HIGH])
        r = self.run_at(self.git(self.repo, "rev-parse", "HEAD").stdout.strip(), "--exclude", "app.py")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        h2 = self.commit_file("extra.py", "y = 2\n", "extra again")
        bundle, subject, _ = self.second_round(h2)
        self.assertEqual(subject["coverage"], [{"file": "app.py", "mode": "full"}, {"file": "extra.py", "mode": "delta"}])
        self.assertIn("app.py", bundle["diff"])
        self.assertNotIn("extra.py", bundle["diff"])


class Confirmation(Rounds):
    def setUp(self):
        super().setUp()
        self.reply("fail", [HIGH])
        self.repo_name = self.stored_subject(self.run_at(self.h))["repo"]
        self.h2 = self.commit_file("app.py", "print('two')\n", "two")
        self.assertEqual(self.run_at(self.h2).returncode, 1)  # round two leaves T1 open
        self.h3 = self.commit_file("app.py", "print('fix of T1')\n", "fix")

    def confirm(self, head=None, **kw):
        return self.run_at(head or self.h3, "--confirm", **kw)

    def test_a_closing_confirmation_issues_a_receipt_ship_accepts(self):
        self.reply("pass")
        r = self.confirm()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        bundle = self.bundle()
        self.assertEqual(bundle["review_mode"], "confirmation")
        self.assertEqual([f["title"] for f in bundle["open_findings"]], ["T1 broken"])
        # only the fixing diff since the round-two head, not the whole change
        self.assertEqual(bundle["diff"], self.git(self.repo, "diff", "--no-renames", self.h2, self.h3).stdout.strip())
        self.assertNotIn("+print('feature')", bundle["diff"])
        self.assertEqual(self.stored_subject(r)["previous_head"], self.h2)
        recs, problem = receipts.find_code(self.repo, self.repo_name, self.base, self.h3, "refs/heads/main", REV)
        self.assertEqual([x["verdict"]["subject"]["review_mode"] for x in recs or []], ["confirmation"], problem)
        self.assertEqual(recs[0]["status"], "unconsumed")

    def test_a_second_confirmation_is_refused_whatever_the_first_said(self):
        self.reply("fail", [HIGH])
        self.assertEqual(self.confirm().returncode, 1)
        self.assertIsNone(receipts.find_code(self.repo, self.repo_name, self.base, self.h3, "refs/heads/main", REV)[0])
        h4 = self.commit_file("app.py", "print('fix again')\n", "fix again")
        self.reply("pass")
        r = self.confirm(h4)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("already used", r.stdout)
        self.assertFalse(self.log.exists())  # no reviewer was dispatched

    def test_confirmation_after_a_base_or_criteria_change_is_blocked_and_not_consumed(self):
        self.reply("pass")
        r = self.confirm(base=self.h)  # the base moved since round two
        self.assertEqual(json.loads(r.stdout)["verdict"], "blocked", r.stdout + r.stderr)
        self.assertIn("the base changed", r.stdout)
        self.assertFalse(self.log.exists())
        plan = self.tmp / "plan2.md"
        plan.write_text("Requirements -> acceptance:\nAC-1 feature works well\n\n## Verification\nAC-1: pytest\n")
        self.cli("maeng-verify", ["bind", "MAE-221", "--plan", str(plan), "--parent", "MAE-216"], self.repo, check=True)
        self.cli("maeng-verify", ["plan", "--met", "AC-1"], self.repo, check=True)
        r = self.confirm()
        self.assertEqual(json.loads(r.stdout)["verdict"], "blocked", r.stdout + r.stderr)
        self.assertIn("criteria digest", r.stdout)
        self.assertFalse(self.log.exists())
        self.assertFalse(receipts.confirmation_used(self.repo_name, "7"))

    def test_the_confirmation_needs_the_counted_rounds_first(self):
        for f in self.stored_reviews()[:1]:
            f.unlink()
        self.reply("pass")
        r = self.confirm()
        self.assertEqual(json.loads(r.stdout)["verdict"], "blocked")
        self.assertIn("counted review rounds", r.stdout)
        self.assertFalse(self.log.exists())

    def test_nothing_to_confirm_after_a_passing_round_two(self):
        for f in self.stored_reviews():
            v = json.loads(f.read_text())
            if v["subject"]["head"] == self.h2:
                v["verdict"], v["findings"] = "pass", []
                f.write_text(json.dumps(v))
        self.reply("pass")
        r = self.confirm()
        self.assertEqual(r.returncode, 2)
        self.assertIn("no critical/high", r.stdout)

    def test_a_confirmation_never_passes_on_a_bad_answer(self):
        new = {**HIGH, "title": "T9 new finding"}
        bad = [("pass", [HIGH]), ("fail", [new]), ("pass", [new]), ("fail", [{**HIGH, "severity": "medium"}])]
        for verdict, findings in bad:
            with self.subTest(verdict=verdict, findings=findings):
                self.reply(verdict, findings)
                r = self.confirm()
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIsNone(receipts.find_code(self.repo, self.repo_name, self.base, self.h3, "refs/heads/main",
                                                     REV)[0])
                for p in (self.maeng_home / "receipts").glob("confirm-*"):
                    p.unlink()  # re-arm for the next case

    def test_an_unavailable_confirmation_never_passes(self):
        self.result.write_text("")
        r = self.confirm()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIsNone(receipts.find_code(self.repo, self.repo_name, self.base, self.h3, "refs/heads/main", REV)[0])

    def test_two_concurrent_reservations_cannot_both_win(self):
        self.assertFalse(receipts.confirmation_used("github.com/o/r", "5"))
        self.assertTrue(receipts.reserve_confirmation("github.com/o/r", "5", "a" * 40))
        self.assertFalse(receipts.reserve_confirmation("github.com/o/r", "5", "b" * 40))
        self.assertTrue(receipts.confirmation_used("github.com/o/r", "5"))
        self.assertTrue(receipts.reserve_confirmation("github.com/o/r", "6", "a" * 40))
