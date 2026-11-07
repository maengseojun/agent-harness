"""Review routing consumes the role table and fails closed before starting a review."""
import argparse
import json

import pytest

from . import test_cli


KINDS = ("code_child", "code_small", "parent", "docs", "research", "notion", "plan")
CHILD = {"parent": "MAE-323", "criteria": ["AC-4"]}


@pytest.fixture
def review():
    return test_cli.load_bin("maeng-review")


@pytest.fixture
def table(review):
    return json.loads(review.ROLES_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def roles_file(review, table, tmp_path, monkeypatch):
    path = tmp_path / "roles.json"
    path.write_text(json.dumps(table), encoding="utf-8")
    monkeypatch.setattr(review, "ROLES_PATH", path)
    return path


def pair(row):
    return row["model"], row["effort"]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("backend", ("codex", "claude"))
def test_every_role_and_backend_matches_table(review, table, kind, backend, monkeypatch):
    row = table["roles"][kind]
    if kind == "parent":
        expected = row if backend == "claude" else next(
            s for s in row["standby"] if not s["model"].startswith("claude-"))
    else:
        expected = row if backend == "codex" else next(
            s for s in row["standby"] if s["model"].startswith("claude-"))
    cli_kind = "code" if kind.startswith("code_") else kind
    binding = CHILD if kind == "code_child" else None
    assert test_cli.pick(review, cli_kind, binding, backend) == pair(expected)
    assert test_cli.pick(review, cli_kind, binding) == pair(row)  # unpinned: the row's own model comes first


@pytest.mark.parametrize("kind,binding", (("code", CHILD), ("notion", None)))
def test_raised_opus_standbys_are_high(review, kind, binding):
    assert test_cli.pick(review, kind, binding, "claude") == ("claude-opus-5-5", "high")


@pytest.mark.parametrize("binding", (None, {}, {"parent": "MAE-323"}, {"criteria": ["AC-4"]},
                                     {"parent": "MAE-323", "criteria": []}))
def test_code_without_both_parent_and_criteria_is_small(review, table, binding):
    assert test_cli.pick(review, "code", binding, "codex") == pair(table["roles"]["code_small"])


def assert_run_rejects_roles(review, monkeypatch, capsys):
    # Validation must precede bundle construction, pre-flight, and either reviewer process.
    for name in ("require_personal", "code_bundle", "decisions_advisory", "run_codex", "run_claude"):
        monkeypatch.setattr(review, name, lambda *a, **kw: pytest.fail("review started with invalid roles"))
    with pytest.raises(ValueError, match="roles"):
        review.load_roles()
    with pytest.raises(SystemExit) as exc:
        review.main(["run", "--kind", "code"])
    assert exc.value.code == 2
    error = capsys.readouterr().err
    assert "error:" in error
    assert str(review.ROLES_PATH) in error


@pytest.mark.parametrize("kind", KINDS)
def test_missing_row_stops_even_another_kind(review, table, roles_file, kind, monkeypatch, capsys):
    del table["roles"][kind]
    roles_file.write_text(json.dumps(table), encoding="utf-8")
    assert_run_rejects_roles(review, monkeypatch, capsys)


@pytest.mark.parametrize("field", ("model", "effort", "standby"))
@pytest.mark.parametrize("kind", KINDS)
def test_incomplete_row_stops_run(review, table, roles_file, kind, field, monkeypatch, capsys):
    del table["roles"][kind][field]
    roles_file.write_text(json.dumps(table), encoding="utf-8")
    assert_run_rejects_roles(review, monkeypatch, capsys)


@pytest.mark.parametrize("kind", KINDS)
def test_missing_claude_standby_stops_run(review, table, roles_file, kind, monkeypatch, capsys):
    row = table["roles"][kind]
    row["standby"] = [s for s in row["standby"] if not s["model"].startswith("claude-")]
    roles_file.write_text(json.dumps(table), encoding="utf-8")
    assert_run_rejects_roles(review, monkeypatch, capsys)


@pytest.mark.parametrize("text", ("{broken", "null", "[]", "{}", '{"roles": []}'))
def test_broken_json_or_structure_stops_run(review, roles_file, text, monkeypatch, capsys):
    roles_file.write_text(text, encoding="utf-8")
    assert_run_rejects_roles(review, monkeypatch, capsys)


def test_missing_file_stops_run(review, roles_file, monkeypatch, capsys):
    roles_file.unlink()
    assert_run_rejects_roles(review, monkeypatch, capsys)


def test_unreadable_file_stops_run(review, roles_file, monkeypatch, capsys):
    def unreadable(*args, **kwargs):
        raise PermissionError("roles file is unreadable")
    monkeypatch.setattr(type(roles_file), "read_text", unreadable)
    assert_run_rejects_roles(review, monkeypatch, capsys)


def test_parent_requires_codex_standby(review, table, roles_file, monkeypatch, capsys):
    row = table["roles"]["parent"]
    row["standby"] = [s for s in row["standby"] if s["model"].startswith("claude-")]
    roles_file.write_text(json.dumps(table), encoding="utf-8")
    assert_run_rejects_roles(review, monkeypatch, capsys)


@pytest.mark.parametrize("field,value", (("model", ""), ("effort", None), ("effort", 3)))
def test_invalid_standby_pair_stops_run(review, table, roles_file, field, value, monkeypatch, capsys):
    table["roles"]["docs"]["standby"][0][field] = value
    roles_file.write_text(json.dumps(table), encoding="utf-8")
    assert_run_rejects_roles(review, monkeypatch, capsys)


def test_resolver_reads_changed_table(review, table, roles_file):
    row = table["roles"]["docs"]
    row.update(effort="high")
    row["standby"][0].update(effort="xhigh")
    roles_file.write_text(json.dumps(table), encoding="utf-8")
    assert test_cli.pick(review, "docs", None, "codex") == ("gpt-6-astra", "high")
    assert test_cli.pick(review, "docs", None, "claude") == ("claude-opus-5-5", "xhigh")


def test_roles_path_is_relative_to_script(review, table, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "policy").mkdir()
    (tmp_path / "policy/roles.json").write_text("{broken", encoding="utf-8")
    assert test_cli.pick(review, "docs", None, "codex") == pair(table["roles"]["docs"])


def test_run_help_does_not_require_roles(review, roles_file, capsys):
    roles_file.unlink()
    with pytest.raises(SystemExit) as exc:
        review.main(["run", "--help"])
    assert exc.value.code == 0
    assert "--author" in capsys.readouterr().out


class TestCodexAuthor(test_cli.ReviewRunFixture):
    fake_claude = test_cli.ClaudeBackend.fake_claude

    def test_code_by_codex_uses_opus_high(self):
        fake, log, _ = self.fake_claude()
        result = self.cli("maeng-review", ["run", "--kind", "code", "--pr", "7", "--base", self.base,
                                          "--head", self.h, "--base-ref", "main", "--author", "codex"],
                          self.repo, extra_env={"MAENG_CODEX": str(self.codex), "MAENG_CLAUDE": str(fake),
                                                "MAENG_REVIEW_BACKEND": "codex"})
        self.assertEqual(result.returncode, 0, result.stderr)
        argv = json.loads(log.read_text())
        self.assertEqual((argv[argv.index("--model") + 1], argv[argv.index("--effort") + 1]),
                         ("claude-opus-5-5", "high"))
        self.assertFalse(self.log.exists(), "Codex must not review its own code")
        receipt = test_cli.receipts.load(json.loads(result.stdout)["receipt"])
        reviewer = receipt["verdict"]["reviewer"]
        self.assertEqual((reviewer["model"], reviewer["effort"], reviewer["author"]),
                         ("claude-opus-5-5", "high", "codex"))


def test_parent_fable_effort_override_is_kept(review, monkeypatch):
    # Plan A-7: MAENG_FABLE_EFFORT stays for parent reviews; it does not touch the codex standby.
    args = argparse.Namespace(author=None, author_model=None, planner_model="claude-opus-5-5")
    table = review.load_roles()
    monkeypatch.setenv("MAENG_FABLE_EFFORT", "medium")
    assert pair(review.select(table, "parent", None, args)) == ("claude-fable-5-1", "medium")
    args.author_model = "claude-fable-5-1"  # Fable's own change: Astra runs and keeps the table effort
    assert pair(review.select(table, "parent", None, args)) == ("gpt-6-astra", "high")
    monkeypatch.delenv("MAENG_FABLE_EFFORT")
    args.author_model = None
    assert pair(review.select(table, "parent", None, args)) == ("claude-fable-5-1", "high")
