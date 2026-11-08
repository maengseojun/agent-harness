"""S2 / AC-2: the reviewer, claim-check and duplicate-check routes are resolved from policy/roles.json at execution.
Expected models and efforts are written here as literals from the table, never read back from the code under test."""
import argparse
import json
import shutil
import stat
import sys
from pathlib import Path

import pytest

from maeng import receipts, routing, state
from . import test_cli

REPO = Path(__file__).resolve().parents[3]
ROLES = REPO / "plugins/maeng-harness/policy/roles.json"
ROUTING = REPO / "plugins/maeng-harness/lib/maeng/routing.py"
SCRIPTS = REPO / "plugins/maeng-tools/skills/decisions/scripts"
SOL, ASTRA, OPUS, FABLE = "gpt-6.1-sol", "gpt-6-astra", "claude-opus-5-5", "claude-fable-5-1"


class RouteRuns(test_cli.ReviewRunFixture):
    fake_claude = test_cli.ClaudeBackend.fake_claude

    def run_review(self, kind, *extra, claude=None, codex=None):
        fake = claude or self.fake_claude(model=OPUS if kind == "code" else FABLE)[0]
        who = [] if any(x.startswith("--author") for x in extra) else ["--author-model", "unlisted-author"]
        return self.cli("maeng-review", ["run", *who, "--kind", kind, "--pr", "7", "--base", self.base, "--head", self.h,
                                         "--base-ref", "main", *extra], self.repo,
                        extra_env={"MAENG_CLAUDE": str(fake), "MAENG_CODEX": str(codex or self.codex)})

    def codex_launch(self):
        argv = json.loads(self.log.read_text())
        return argv[argv.index("-m") + 1], [a for a in argv if a.startswith("model_reasoning_effort=")]

    def reviewer(self, r):
        return receipts.load(json.loads(r.stdout)["receipt"])["verdict"]["reviewer"]

    def dead_codex(self):
        dead = self.tmp / "dead-codex"
        dead.write_text(f"#!{sys.executable}\nimport sys\nif sys.argv[1:3] == ['features', 'list']:\n    sys.exit(0)\n"
                        f"print('usage limit reached', file=sys.stderr)\nsys.exit(1)\n")
        dead.chmod(dead.stat().st_mode | stat.S_IEXEC)
        return dead

    def test_fable_planner_sends_the_parent_review_to_astra_high(self):
        fake, claude_log, _ = self.fake_claude(model=FABLE)
        r = self.run_review("parent", "--planner-model", FABLE, claude=fake)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(claude_log.exists(), "Fable must not review a Fable-planned parent")
        self.assertEqual(self.codex_launch(), (ASTRA, ['model_reasoning_effort="high"']))
        rev = self.reviewer(r)
        self.assertEqual((rev["model"], rev["effort"], rev["resource"], rev["row"], rev["route"]),
                         (ASTRA, "high", "gpt_pro", "roles.parent", "routes.review"))
        self.assertEqual(rev["skipped"], [{"model": FABLE, "effort": "high", "resource": "claude_code",
                                           "reason": f"same model as the planner ({FABLE})", "match": "model"}])
        self.assertNotIn("fallback_from", rev)

    def test_sol_author_sends_the_child_code_review_to_opus_high(self):
        fake, claude_log, _ = self.fake_claude(model=OPUS)
        r = self.run_review("code", "--author-model", SOL, claude=fake)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.log.exists(), "Sol must not review a Sol-written change")
        argv = json.loads(claude_log.read_text())
        self.assertEqual((argv[argv.index("--model") + 1], argv[argv.index("--effort") + 1]), (OPUS, "high"))
        rev = self.reviewer(r)
        self.assertEqual((rev["model"], rev["resource"], rev["row"], rev["author"]),
                         (OPUS, "claude_code", "roles.code_child", "codex"))
        self.assertEqual(rev["skipped"], [{"model": SOL, "effort": "xhigh", "resource": "gpt_pro",
                                           "reason": f"same model as the author ({SOL})", "match": "model"}])

    def test_author_family_flag_is_recorded_as_a_family_match(self):
        r = self.run_review("code", "--author", "codex")
        self.assertEqual(r.returncode, 0, r.stderr)
        skipped = self.reviewer(r)["skipped"]
        self.assertEqual([(s["model"], s["match"], s["reason"]) for s in skipped],
                         [(SOL, "family", "same family as the author (codex)")])

    def test_a_different_exact_author_does_not_exclude_sol(self):
        r = self.run_review("code", "--author-model", ASTRA)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.codex_launch(), (SOL, ['model_reasoning_effort="xhigh"']))
        self.assertEqual(self.reviewer(r)["skipped"], [])

    def test_every_candidate_excluded_is_blocked_with_exit_2(self):
        fake, claude_log, _ = self.fake_claude(model=FABLE)
        r = self.run_review("parent", "--author", "codex", "--planner-model", "claude", claude=fake)
        self.assertEqual(r.returncode, 2, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["verdict"], "blocked")
        self.assertEqual([(s["model"], s["match"]) for s in out["reviewer"]["skipped"]],
                         [(FABLE, "family"), (ASTRA, "family"), (OPUS, "family")])
        self.assertFalse(self.log.exists() or claude_log.exists(), "no reviewer may start")
        self.assertEqual(list(receipts.receipts_dir().glob("*.json")) if receipts.receipts_dir().exists() else [], [])

    def test_a_review_without_an_author_identity_is_refused_before_any_dispatch(self):
        for kind in ("code", "notion"):
            with self.subTest(kind=kind):
                r = self.cli("maeng-review", ["run", "--kind", kind, "--pr", "7", "--base", self.base, "--head", self.h,
                                              "--base-ref", "main"], self.repo, extra_env={"MAENG_CODEX": str(self.codex)})
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)  # fails on the old code: the review ran
                self.assertIn("--author-model", r.stderr)
                self.assertFalse(self.log.exists())

    def test_a_missing_planner_model_is_refused_not_waived(self):
        fake, claude_log, _ = self.fake_claude(model=FABLE)
        r = self.run_review("parent", claude=fake)
        self.assertEqual(r.returncode, 2)
        self.assertIn("--planner-model", r.stderr)
        self.assertFalse(self.log.exists() or claude_log.exists())

    def test_a_failed_first_candidate_advances_to_the_second_and_says_why(self):
        fake, claude_log, _ = self.fake_claude(model=OPUS)
        r = self.run_review("code", claude=fake, codex=self.dead_codex())
        self.assertEqual(r.returncode, 0, r.stderr)
        argv = json.loads(claude_log.read_text())
        self.assertEqual((argv[argv.index("--model") + 1], argv[argv.index("--effort") + 1]), (OPUS, "high"))
        rev = self.reviewer(r)
        self.assertEqual(rev["fallback_from"], {"model": SOL, "effort": "xhigh", "attempts": 3})
        self.assertEqual([(s["model"], s["reason"].split(":")[0]) for s in rev["skipped"]], [(SOL, "unavailable")])
        self.assertIn("usage limit reached", rev["skipped"][0]["reason"])
        self.assertNotIn("match", rev["skipped"][0])

    def test_all_candidates_unavailable_is_blocked_with_exit_2(self):
        fake, claude_log, _ = self.fake_claude(model=OPUS, is_error=True)
        r = self.run_review("code", claude=fake, codex=self.dead_codex())
        self.assertEqual(r.returncode, 2, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["verdict"], "blocked")
        self.assertEqual([s["model"] for s in out["reviewer"]["skipped"]], [SOL, OPUS, FABLE])
        self.assertTrue(all(s["reason"].startswith("unavailable") for s in out["reviewer"]["skipped"]))

    def test_bound_author_is_skipped_after_the_first_candidate_fails(self):
        state.update(self.sid, lambda st: st["binding"].update(author_model=OPUS), self.repo)
        fake, claude_log, _ = self.fake_claude(model=FABLE)
        r = self.cli("maeng-review", ["run", "--kind", "code", "--pr", "7", "--base", self.base, "--head", self.h,
                                      "--base-ref", "main"], self.repo,
                     extra_env={"MAENG_CLAUDE": str(fake), "MAENG_CODEX": str(self.dead_codex())})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.reviewer(r)["model"], FABLE)
        self.assertEqual([(s["model"], s.get("match")) for s in self.reviewer(r)["skipped"]],
                         [(SOL, None), (OPUS, "model")])
        argv = json.loads(claude_log.read_text())
        self.assertEqual(argv[argv.index("--model") + 1], FABLE)

    def test_both_bound_exclusions_survive_every_availability_fallback(self):
        for author, planner, excluded in ((SOL, OPUS, "planner"), (OPUS, SOL, "author")):
            with self.subTest(excluded=excluded):
                state.update(self.sid, lambda st: st["binding"].update(author_model=author, planner_model=planner), self.repo)
                fake, _, _ = self.fake_claude(model=FABLE, is_error=True)
                r = self.cli("maeng-review", ["run", "--kind", "parent", "--pr", "7", "--base", self.base,
                                              "--head", self.h, "--base-ref", "main"], self.repo,
                             extra_env={"MAENG_CLAUDE": str(fake), "MAENG_CODEX": str(self.dead_codex())})
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                out = json.loads(r.stdout)
                self.assertEqual(out["verdict"], "blocked")
                skipped = out["reviewer"]["skipped"]
                self.assertEqual([s["model"] for s in skipped], [FABLE, ASTRA, OPUS])
                self.assertTrue(all(s["reason"].startswith("unavailable") for s in skipped[:2]))
                self.assertEqual(skipped[2]["reason"], f"same model as the {excluded} ({OPUS})")
                self.assertFalse(self.log.exists(), "Astra failed via the stub; Opus must never start")

    def test_unknown_explicit_author_is_refused_instead_of_disabling_exclusion(self):
        r = self.run_review("code", "--author-model", "unknown")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("--author-model", r.stderr)
        self.assertFalse(self.log.exists())

    def test_eta_world_is_still_refused_before_any_reviewer(self):
        eta = self.make_repo("eta_v1")
        r = self.cli("maeng-review", ["run", "--kind", "code", "--pr", "7", "--base", self.base, "--head", self.h,
                                      "--base-ref", "main", "--author-model", SOL], eta,
                     extra_env={"MAENG_CODEX": str(self.codex)})
        self.assertEqual(r.returncode, 2)
        self.assertIn("personal world", r.stderr)
        self.assertFalse(self.log.exists())


@pytest.fixture
def review():
    return test_cli.load_bin("maeng-review")


@pytest.fixture
def table():
    return json.loads(ROLES.read_text(encoding="utf-8"))


def ns(**kw):
    return argparse.Namespace(**{"author": None, "author_model": None, "planner_model": None, **kw})


def test_plan_review_with_an_astra_planner_takes_the_next_candidate(review, table):
    sel = review.select(table, "plan", None, ns(planner_model=ASTRA))
    assert (sel["model"], sel["effort"], sel["resource"], sel["row"]) == (OPUS, "xhigh", "claude_code", "roles.plan")
    assert [(s["model"], s["match"]) for s in sel["skipped"]] == [(ASTRA, "model")]
    free = review.select(table, "plan", None, ns(planner_model=OPUS))
    assert (free["model"], free["effort"]) == (ASTRA, "high")  # Astra first when it is not the planner


def test_plan_and_parent_need_the_planner_but_other_kinds_do_not(review, table):
    for kind in ("plan", "parent"):
        with pytest.raises(routing.RoutingError, match="planner"):
            review.select(table, kind, None, ns())
    assert review.select(table, "docs", None, ns())["model"] == ASTRA
    assert review.select(table, "docs", None, ns(planner_model=ASTRA))["model"] == ASTRA  # no planner exclusion


def test_family_name_matches_by_prefix_exact_ids_by_equality(table):
    fam = routing.resolve(table, "code_child", author="claude")
    assert (fam["model"], fam["skipped"]) == (SOL, [])
    fam = routing.resolve(table, "parent", planner="claude")
    assert (fam["model"], [s["match"] for s in fam["skipped"]]) == (ASTRA, ["family"])
    exact = routing.resolve(table, "parent", planner="claude-opus-5-5-20261101")  # another id: not the same model
    assert (exact["model"], exact["skipped"]) == (FABLE, [])


def test_a_pinned_backend_and_unavailable_models_are_recorded_as_skips(table):
    sel = routing.resolve(table, "code_child", only="claude", unavailable={OPUS: "rc=1"})
    assert sel["model"] == FABLE
    assert [(s["model"], s["reason"]) for s in sel["skipped"]] == [
        (SOL, "pinned to the claude backend"), (OPUS, "unavailable: rc=1")]


def test_a_missing_review_route_starts_nothing(review, table, tmp_path, monkeypatch, capsys):
    del table["routes"]["review"]
    path = tmp_path / "roles.json"
    path.write_text(json.dumps(table), encoding="utf-8")
    monkeypatch.setattr(review, "ROLES_PATH", path)
    for name in ("require_personal", "code_bundle", "decisions_advisory", "run_codex", "run_claude"):
        monkeypatch.setattr(review, name, lambda *a, **kw: pytest.fail("review started without its route"))
    with pytest.raises(SystemExit) as exc:
        review.main(["run", "--kind", "code"])
    assert exc.value.code == 2
    assert "routes.review" in capsys.readouterr().err


def test_a_candidate_whose_resource_lacks_the_model_raises(table):
    table["resources"]["gpt_pro"]["models"].remove(SOL)
    with pytest.raises(routing.RoutingError, match=SOL):
        routing.candidates(table, "code_child")
    del table["roles"]["docs"]
    with pytest.raises(routing.RoutingError, match="docs"):
        routing.candidates(table, "docs")


# ---- the two Decisions wrappers (maeng-tools) --------------------------------------------------------------------

@pytest.fixture
def decisions(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    import decisions_client, records, verify_claims
    calls = []

    def fake(input, questions, pilot, **kw):
        calls.append(kw)
        return [{"name": q["name"], "status": "unknown", "reason": "off"} for q in questions]
    monkeypatch.setattr(decisions_client, "decide", fake)
    monkeypatch.setenv("MAENG_DECISIONS_MODEL", "jev-1.14.0")  # an ambient setting must not reach the request
    return verify_claims, records, calls


def test_claim_check_passes_the_route_model_explicitly(decisions):
    verify_claims, _, calls = decisions
    verify_claims.verify([{"id": "c1", "claim": "x", "url": "https://example.com/a"}],
                         pages={"https://example.com/a": ("page text", "live")})
    assert [c["model"] for c in calls] == ["gpt-6-luna"]


def test_duplicate_and_related_checks_pass_the_route_model_explicitly(decisions):
    _, records, calls = decisions
    cands = [{"id": "A-1", "title": "t", "text": "body"}]
    records.duplicate("new thing", cands)
    records.related("task", cands)
    assert [c["model"] for c in calls] == ["gpt-6-luna", "gpt-6-luna"]


def test_a_missing_claim_route_raises_before_any_page_or_request(decisions, tmp_path, monkeypatch):
    verify_claims, _, calls = decisions
    root = tmp_path / "plugins"
    table = json.loads(ROLES.read_text(encoding="utf-8"))
    del table["routes"]["claim_check"]
    (root / "maeng-harness/policy").mkdir(parents=True)
    (root / "maeng-harness/policy/roles.json").write_text(json.dumps(table), encoding="utf-8")
    (root / "maeng-harness/lib/maeng").mkdir(parents=True)
    shutil.copy(ROUTING, root / "maeng-harness/lib/maeng/routing.py")
    monkeypatch.setattr(verify_claims, "__file__", str(root / "maeng-tools/skills/decisions/scripts/verify_claims.py"))
    monkeypatch.setattr(verify_claims, "fetch_page", lambda *a, **kw: pytest.fail("a page was fetched"))
    with pytest.raises(ValueError, match="claim_check"):  # RoutingError of the copy loaded by path
        verify_claims.verify([{"id": "c1", "claim": "x", "url": "https://example.com/a"}])
    assert calls == []


def test_the_route_table_is_found_from_a_versioned_installation(decisions, tmp_path):
    verify_claims, _, _ = decisions
    cache = tmp_path / "cache/maeng"
    script = cache / "maeng-tools/0.5.0/skills/decisions/scripts/verify_claims.py"
    for version, model in (("0.4.4", "gpt-old"), ("0.4.13", "gpt-6-luna")):  # 0.4.13 is newer than 0.4.4
        home = cache / "maeng-harness" / version
        (home / "policy").mkdir(parents=True)
        (home / "lib/maeng").mkdir(parents=True)
        shutil.copy(ROUTING, home / "lib/maeng/routing.py")
        table = json.loads(ROLES.read_text(encoding="utf-8"))
        table["routes"]["claim_check"]["model"] = model
        table["resources"]["openai_api"]["models"].append(model)
        (home / "policy/roles.json").write_text(json.dumps(table), encoding="utf-8")
    assert verify_claims.route_model("claim_check", script) == "gpt-6-luna"
    with pytest.raises(FileNotFoundError):
        verify_claims.route_model("claim_check", tmp_path / "elsewhere/a/b/c/d/e/f/verify_claims.py")


def test_a_dated_identity_matches_its_model():
    from maeng import routing
    assert routing._match("claude-opus-5-5", "claude-opus-5-5-20261101") == "model"
    assert routing._match("claude-opus-5-5", "claude-opus-5-5-beta") is None
    assert routing._match("claude-opus-5-5", "claude-opus-5") is None
