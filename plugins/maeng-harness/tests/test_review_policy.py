"""MAE-326 S3 / AC-4: the review criteria V-1 to V-6 in the prompt and in the verdict validation."""
import json
import stat
import sys

from maeng import receipts
from .test_cli import ClaudeBackend, ReviewRunFixture


def finding(severity, file="app.py", line=1, title="t", body="b"):
    return {"severity": severity, "title": title, "body": body, "file": file, "line": line}


class ReviewPolicy(ReviewRunFixture):
    def reply(self, verdict, findings):
        self.result.write_text(json.dumps({"verdict": verdict, "findings": findings}))

    def stored(self):
        d = receipts.receipts_dir()
        return list(d.glob("*.json")) if d.exists() else []

    def run_with_claude(self, fake):
        return self.review_env({"MAENG_CODEX": str(self.codex), "MAENG_CLAUDE": str(fake)})

    def review_env(self, env):
        return self.cli("maeng-review", ["run", "--author-model", "unlisted-author", "--kind", "code", "--pr", "7", "--base", self.base, "--head", self.h,
                                         "--base-ref", "main"], self.repo, extra_env=env)

    def test_medium_and_low_alone_never_fail(self):
        for verdict in ("pass", "fail"):  # a reviewer's fail with no critical/high is not a fail
            with self.subTest(verdict=verdict):
                self.reply(verdict, [finding("medium", title="m"), finding("low", title="l")])
                r = self.review()
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                out = json.loads(r.stdout)
                self.assertEqual(out["verdict"], "pass")
                self.assertEqual([f["title"] for f in out["findings"]], ["m", "l"])
                self.assertTrue(receipts.load(out["receipt"]))

    def test_high_or_critical_fails(self):
        for sev in ("high", "critical"):
            self.reply("fail", [finding(sev)])
            r = self.review()
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIsNone(json.loads(r.stdout)["receipt"])

    def test_no_findings_is_a_valid_pass(self):
        r = self.review()
        self.assertEqual((r.returncode, json.loads(r.stdout)["findings"]), (0, []))

    def test_pass_with_an_open_high_is_rejected_and_stores_no_receipt(self):
        for sev in ("high", "critical"):
            self.reply("pass", [finding(sev)])
            r = self.review()
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertEqual(json.loads(r.stdout)["verdict"], "blocked")
            self.assertIn("unresolved critical/high", r.stderr)
            self.assertEqual(self.stored(), [])

    def test_a_rejected_response_goes_to_the_next_candidate(self):
        self.reply("pass", [finding("high")])
        fake, _, _ = ClaudeBackend.fake_claude(self)
        r = self.run_with_claude(fake)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        rev = receipts.load(json.loads(r.stdout)["receipt"])["verdict"]["reviewer"]
        self.assertEqual((rev["model"], rev["fallback_from"]["model"]), ("claude-opus-5-5", "gpt-6.1-sol"))

    def test_a_finding_without_file_and_line_is_rejected(self):
        for bad in (finding("high", file=None, line=None), finding("high", line=None), finding("high", line=0),
                    finding("medium", file=None, line=None),
                    finding("high", file=None, line=None, title="missing file/function: docs/x.md", body="not an AC")):
            with self.subTest(bad=bad):
                self.reply("fail", [bad])
                r = self.review()
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn("missing file/function exception", r.stderr)
                self.assertEqual(self.stored(), [])

    def test_the_missing_file_exception_names_the_ac(self):
        miss = finding("high", file=None, line=None, title="missing file/function: docs/x.md", body="AC-1 asks for it")
        self.reply("fail", [miss])
        r = self.review()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout)["findings"], [miss])

    def test_low_findings_are_capped_at_five_plus_a_count(self):
        self.reply("pass", [finding("medium", title="m")] + [finding("low", title=f"l{i}") for i in range(8)])
        out = json.loads(self.review().stdout)
        self.assertEqual([f["title"] for f in out["findings"]], ["m", "l0", "l1", "l2", "l3", "l4", "외 3건"])
        self.assertEqual(receipts.load(out["receipt"])["verdict"]["findings"], out["findings"])

    def test_an_empty_or_refused_response_is_never_a_clean_review(self):
        for body in ("", "null", "[]", "not json"):
            with self.subTest(body=body):
                self.result.write_text(body)
                none, _, _ = ClaudeBackend.fake_claude(self, structured=False)  # a refusal: no structured output
                r = self.run_with_claude(none)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertEqual((json.loads(r.stdout)["verdict"], self.stored()), ("blocked", []))
                fake, _, _ = ClaudeBackend.fake_claude(self)  # same path: replaces the refusing one
                r = self.run_with_claude(fake)  # the next candidate, not the empty answer, decides
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(receipts.load(json.loads(r.stdout)["receipt"])["verdict"]["reviewer"]["model"],
                                 "claude-opus-5-5")
                for p in self.stored():
                    p.unlink()

    def test_the_prompt_carries_the_criteria(self):
        self.review()
        sent = self.stdin_log.read_text()
        for needle in ("medium and low never fail", "missing file/function:", "At most 5 low findings",
                       "Try to falsify each AC", "No findings with verdict pass is a valid review"):
            self.assertIn(needle, sent)
