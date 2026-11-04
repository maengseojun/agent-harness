import contextlib
import hashlib
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decisions_client as dc  # noqa: E402

KEY = "sk-test-LEDGERKEYabcdef1234567890"
VERDICT_FIELDS = ("choice", "probability", "score", "probabilities", "confidence")

Q_CHOICE = {"type": "choice", "name": "topic", "instructions": "Pick the topic.",
            "choices": [{"value": "billing", "description": "Money"}, {"value": "bug", "description": "Defect"}]}
Q_PRED = {"type": "predicate", "name": "urgent", "instructions": "Is it urgent?"}
Q_SCORE = {"type": "score", "name": "severity", "instructions": "Rate severity.",
           "levels": [{"label": "Cosmetic", "description": "Looks"}, {"label": "Major", "description": "Breaks"},
                      {"label": "Blocked", "description": "Stops"}]}
A_CHOICE = {"type": "choice", "name": "topic", "choice": "billing", "confidence": 0.93,
            "probabilities": [{"value": "billing", "probability": 0.95}, {"value": "bug", "probability": 0.05}]}
A_PRED = {"type": "predicate", "name": "urgent", "probability": 0.92}
A_SCORE = {"type": "score", "name": "severity", "score": 1.1, "confidence": 0.55,
           "probabilities": [{"value": 0, "label": "Cosmetic", "probability": 0.1},
                             {"value": 1, "label": "Major", "probability": 0.9}]}


class FakePost:
    """Stands in for dc._post; records every call."""

    def __init__(self, response=None, exc=None):
        self.response, self.exc, self.calls = response, exc, []

    def __call__(self, url, body, headers, timeout):
        self.calls.append((url, body, headers, timeout))
        if self.exc:
            raise self.exc
        return self.response


def http_error(code):
    return urllib.error.HTTPError("https://api.openai.com/v1/decisions", code, "err", {}, io.BytesIO(b""))


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.work = self.tmp / "work"
        self.work.mkdir()
        self.eta = self.tmp / "eta_v1"
        (self.eta / "sub").mkdir(parents=True)
        self.ledger = self.tmp / "led" / "nested" / "ledger.jsonl"
        env = {"HOME": str(self.tmp), "OPENAI_API_KEY": KEY, "MAENG_DECISIONS_LEDGER": str(self.ledger),
               "PATH": os.environ.get("PATH", "")}
        patch_env = mock.patch.dict(os.environ, env, clear=True)
        patch_env.start()
        self.addCleanup(patch_env.stop)
        self.real_keychain = dc._keychain_key
        patch_kc = mock.patch.object(dc, "_keychain_key", return_value=None)
        self.keychain = patch_kc.start()
        self.addCleanup(patch_kc.stop)

    def run_decide(self, fake, questions=None, input="hello", **kw):
        with mock.patch.object(dc, "_post", fake):
            return dc.decide(input, [Q_CHOICE] if questions is None else questions, "test-pilot", **kw)

    def ledger_lines(self):
        return [json.loads(x) for x in self.ledger.read_text().splitlines()] if self.ledger.exists() else []

    def assertAllUnknown(self, results, reason):
        self.assertTrue(results)
        for r in results:
            self.assertEqual(r["status"], "unknown")
            self.assertEqual(r["reason"], reason)
            for f in VERDICT_FIELDS:
                self.assertNotIn(f, r)


class ParseTest(Base):
    def test_choice_predicate_score_parse_to_ok_with_values(self):
        # API answers come back in a different order than the questions
        fake = FakePost({"answers": [A_SCORE, A_CHOICE, A_PRED], "usage": {"input_tokens": 10}})
        res = self.run_decide(fake, [Q_CHOICE, Q_PRED, Q_SCORE])
        self.assertEqual([r["name"] for r in res], ["topic", "urgent", "severity"])
        self.assertEqual([r["type"] for r in res], ["choice", "predicate", "score"])
        self.assertEqual([r["status"] for r in res], ["ok"] * 3)
        c, p, s = res
        self.assertEqual(c["choice"], "billing")
        self.assertEqual(c["confidence"], 0.93)
        self.assertEqual(c["probabilities"], A_CHOICE["probabilities"])
        self.assertEqual(p["probability"], 0.92)
        self.assertNotIn("choice", p)
        self.assertEqual(s["score"], 1.1)
        self.assertEqual(s["confidence"], 0.55)
        self.assertEqual(s["probabilities"], A_SCORE["probabilities"])
        self.assertNotIn("reason", c)

    def test_request_shape(self):
        fake = FakePost({"answers": [A_CHOICE]})
        self.run_decide(fake, timeout=7.5, model="gpt-6-luna")
        (url, body, headers, timeout), = fake.calls
        self.assertEqual(url, "https://api.openai.com/v1/decisions")
        self.assertEqual(headers["Authorization"], "Bearer " + KEY)
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(timeout, 7.5)
        self.assertEqual(body, {"model": "gpt-6-luna", "input": "hello", "questions": [Q_CHOICE]})

    def test_invalid_questions_raise(self):
        fake = FakePost({"answers": []})
        for bad in ([], [Q_PRED, Q_PRED], [dict(Q_PRED, name="")], [dict(Q_PRED, type="nope")],
                    [dict(Q_PRED, name=f"q{i}") for i in range(401)]):
            with self.subTest(n=len(bad)), self.assertRaises(ValueError):
                self.run_decide(fake, bad)
        self.assertEqual(fake.calls, [])
        ok = [dict(Q_PRED, name=f"q{i}") for i in range(400)]
        self.assertAllUnknown(self.run_decide(FakePost({"answers": []}), ok), "missing")


class ErrorPathTest(Base):
    def test_errors_become_unknown_with_reason_and_never_a_verdict(self):
        cases = [
            ("http 500", FakePost(exc=http_error(500)), "http_500", "error"),
            ("http 429", FakePost(exc=http_error(429)), "http_429", "error"),
            ("socket timeout", FakePost(exc=socket.timeout("timed out")), "timeout", "timeout"),
            ("urlerror timeout", FakePost(exc=urllib.error.URLError(socket.timeout("t"))), "timeout", "timeout"),
            ("urlerror refused", FakePost(exc=urllib.error.URLError(ConnectionRefusedError())), "error", "error"),
            ("bad json", FakePost(exc=json_error()), "error", "error"),
            ("refusal type", FakePost({"answers": [{"type": "refusal", "name": "topic", "refusal": "no"}]}),
             "refused", "refused"),
            ("refusal type with a choice field", FakePost({"answers": [dict(A_CHOICE, type="refusal")]}),
             "refused", "refused"),
            ("no choice field", FakePost({"answers": [{"type": "choice", "name": "topic", "confidence": 0.9}]}),
             "refused", "refused"),
            ("null choice", FakePost({"answers": [dict(A_CHOICE, choice=None)]}), "refused", "refused"),
            ("empty choice", FakePost({"answers": [dict(A_CHOICE, choice="")]}), "refused", "refused"),
            ("off-list choice", FakePost({"answers": [dict(A_CHOICE, choice="sales")]}), "refused", "refused"),
            ("missing name", FakePost({"answers": [dict(A_CHOICE, name="other")]}), "missing", "refused"),
            ("empty answers", FakePost({"answers": []}), "missing", "refused"),
            ("no answers key", FakePost({"usage": {}}), "missing", "refused"),
            ("not a dict", FakePost(["answers"]), "missing", "refused"),
        ]
        for label, fake, reason, outcome in cases:
            with self.subTest(label):
                self.assertAllUnknown(self.run_decide(fake), reason)
                self.assertEqual(len(fake.calls), 1)
                self.assertEqual(self.ledger_lines()[-1]["outcome"], outcome)
                self.assertEqual(self.ledger_lines()[-1]["answers"][0]["status"], "unknown")

    def test_predicate_and_score_without_their_field_are_refused(self):
        fake = FakePost({"answers": [{"type": "predicate", "name": "urgent"},
                                     {"type": "score", "name": "severity", "confidence": 0.5},
                                     {"type": "predicate", "name": "late", "probability": "0.9"}]})
        late = dict(Q_PRED, name="late")
        self.assertAllUnknown(self.run_decide(fake, [Q_PRED, Q_SCORE, late]), "refused")

    def test_values_outside_the_question_are_refused(self):
        for label, answers in (("negative probability", [dict(A_PRED, probability=-1)]),
                               ("probability above 1", [dict(A_PRED, probability=1.01)]),
                               ("nan probability", [dict(A_PRED, probability=float("nan"))]),
                               ("true as probability", [dict(A_PRED, probability=True)])):
            with self.subTest(label):
                self.assertAllUnknown(self.run_decide(FakePost({"answers": answers}), [Q_PRED]), "refused")
                self.assertEqual(self.ledger_lines()[-1]["outcome"], "refused")
        for score in (-0.1, 2.01, float("inf")):  # three levels, indices 0 to 2
            with self.subTest(score=score):
                res = self.run_decide(FakePost({"answers": [dict(A_SCORE, score=score)]}), [Q_SCORE])
                self.assertAllUnknown(res, "refused")

    def test_the_edges_of_the_range_are_answers(self):
        res = self.run_decide(FakePost({"answers": [dict(A_PRED, probability=0), dict(A_SCORE, score=2)]}), [Q_PRED, Q_SCORE])
        self.assertEqual([r["status"] for r in res], ["ok", "ok"])

    def test_malformed_answers_are_unknown_and_still_logged(self):
        for label, resp in (("list as name", {"answers": [{"name": [], "type": "refusal"}]}),
                            ("dict as name", {"answers": [{"name": {}}]}),
                            ("number as answers", {"answers": 3}),
                            ("list as usage", {"answers": [], "usage": []})):
            with self.subTest(label):
                before = len(self.ledger_lines())
                self.assertAllUnknown(self.run_decide(FakePost(resp)), "missing")
                self.assertEqual(len(self.ledger_lines()), before + 1)

    def test_huge_numbers_do_not_raise(self):
        huge = 10 ** 400
        res = self.run_decide(FakePost({"answers": [dict(A_PRED, probability=huge)],
                                        "usage": {"input_tokens": huge}}), [Q_PRED])
        self.assertAllUnknown(res, "refused")
        self.assertEqual(self.ledger_lines()[-1]["cost_usd"], 0)

    def test_malformed_extras_of_a_valid_answer_are_dropped(self):
        for bad in ({"confidence": 10 ** 400, "probabilities": 5}, {"confidence": "\ud800", "probabilities": [5, {"value": "bug"}]},
                    {"confidence": -1, "probabilities": [{"value": "bug", "probability": 10 ** 400}]}):
            with self.subTest(bad):
                r = self.run_decide(FakePost({"answers": [dict(A_CHOICE, **bad)]}))[0]
                self.assertEqual((r["status"], r["choice"], r["confidence"], r["probabilities"]), ("ok", "billing", None, []))

    def test_a_lone_surrogate_cannot_lose_the_answers_or_the_ledger_line(self):
        before = len(self.ledger_lines())
        res = self.run_decide(FakePost({"answers": [A_CHOICE]}), input="text \ud83d end")
        self.assertEqual(res[0]["status"], "ok")
        self.assertEqual(len(self.ledger_lines()), before + 1)

    def test_one_bad_answer_does_not_spoil_the_others(self):
        fake = FakePost({"answers": [A_PRED, {"type": "refusal", "name": "topic"}]})
        res = self.run_decide(fake, [Q_CHOICE, Q_PRED])
        self.assertEqual((res[0]["status"], res[0]["reason"]), ("unknown", "refused"))
        self.assertNotIn("choice", res[0])
        self.assertEqual((res[1]["status"], res[1]["probability"]), ("ok", 0.92))
        self.assertEqual(self.ledger_lines()[-1]["outcome"], "partial")


def json_error():
    try:
        json.loads("{not json")
    except ValueError as e:
        return e


class NoRequestTest(Base):
    def test_off_sends_nothing(self):
        fake = FakePost({"answers": [A_CHOICE, A_PRED]})
        with mock.patch.dict(os.environ, {"MAENG_DECISIONS": "off"}):
            res = self.run_decide(fake, [Q_CHOICE, Q_PRED])
        self.assertEqual(fake.calls, [])
        self.keychain.assert_not_called()
        self.assertAllUnknown(res, "off")
        self.assertEqual([r["name"] for r in res], ["topic", "urgent"])
        line = self.ledger_lines()[-1]
        self.assertEqual((line["outcome"], line["input_tokens"], line["cost_usd"]), ("off", 0, 0))

    def test_control_without_off_does_send(self):
        for value in (None, "on", ""):
            with self.subTest(value=value):
                fake = FakePost({"answers": [A_CHOICE]})
                env = {} if value is None else {"MAENG_DECISIONS": value}
                with mock.patch.dict(os.environ, env):
                    res = self.run_decide(fake)
                self.assertEqual(len(fake.calls), 1)
                self.assertEqual(res[0]["status"], "ok")

    def test_a_call_from_an_eta_checkout_is_sent(self):
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.eta / "sub")
        fake = FakePost({"answers": [A_CHOICE]})
        self.assertEqual(self.run_decide(fake)[0]["status"], "ok")
        self.assertEqual(len(fake.calls), 1)

    def test_no_key_sends_nothing(self):
        del os.environ["OPENAI_API_KEY"]
        fake = FakePost({"answers": [A_CHOICE]})
        res = self.run_decide(fake)
        self.assertEqual(fake.calls, [])
        self.keychain.assert_called_once()
        self.assertAllUnknown(res, "no_key")
        self.assertEqual(self.ledger_lines()[-1]["outcome"], "no_key")

    def test_no_key_when_the_keychain_command_fails(self):
        del os.environ["OPENAI_API_KEY"]
        for label, run in (("missing binary", mock.Mock(side_effect=FileNotFoundError())),
                           ("item not found", mock.Mock(return_value=subprocess.CompletedProcess([], 44, "", "nope")))):
            with self.subTest(label), mock.patch.object(dc, "_keychain_key", self.real_keychain), \
                    mock.patch.object(dc.subprocess, "run", run):
                fake = FakePost({"answers": [A_CHOICE]})
                self.assertAllUnknown(self.run_decide(fake), "no_key")
                self.assertEqual(fake.calls, [])
                run.assert_called_once()


class KeyLookupTest(unittest.TestCase):
    """The real _keychain_key / _api_key with subprocess.run replaced (no setUp patch of the lookup)."""

    def setUp(self):
        patch_env = mock.patch.dict(os.environ, {"PATH": os.environ.get("PATH", "")}, clear=True)
        patch_env.start()
        self.addCleanup(patch_env.stop)

    def test_keychain_command_and_strip(self):
        run = mock.Mock(return_value=subprocess.CompletedProcess([], 0, "sk-from-keychain\n", ""))
        with mock.patch.object(dc.subprocess, "run", run):
            self.assertEqual(dc._api_key(), "sk-from-keychain")
        self.assertEqual(run.call_args.args[0], ["security", "find-generic-password", "-s", "openai-api-key", "-w"])

    def test_env_key_wins_and_keychain_is_not_asked(self):
        run = mock.Mock()
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": " sk-env \n"}), mock.patch.object(dc.subprocess, "run", run):
            self.assertEqual(dc._api_key(), "sk-env")
        run.assert_not_called()

    def test_keychain_failures_give_none(self):
        for label, run in (("missing binary", mock.Mock(side_effect=FileNotFoundError())),
                           ("timeout", mock.Mock(side_effect=subprocess.TimeoutExpired("security", 5))),
                           ("item not found", mock.Mock(return_value=subprocess.CompletedProcess([], 44, "", "nope"))),
                           ("empty output", mock.Mock(return_value=subprocess.CompletedProcess([], 0, "\n", "")))):
            with self.subTest(label), mock.patch.object(dc.subprocess, "run", run):
                self.assertIsNone(dc._api_key())


PLANTED = [  # (text as it might appear, the part that must not survive)
    ("use sk" "-proj-AbCdEf1234567890XyZ here", "AbCdEf1234567890XyZ"),
    ("token gh" "p_Zx9Qw8Er7Ty6Ui5Op4As3 leaked", "Zx9Qw8Er7Ty6Ui5Op4As3"),
    ("gh" "o_Zx9Qw8Er7Ty6Ui5Op4Bs3", "Zx9Qw8Er7Ty6Ui5Op4Bs3"),
    ("gh" "s_Zx9Qw8Er7Ty6Ui5Op4Cs3", "Zx9Qw8Er7Ty6Ui5Op4Cs3"),
    ("gi" "thub_pat_11ABCDEFG0abcdefghij_klmnop1234", "11ABCDEFG0abcdefghij_klmnop1234"),
    ("xo" "xb-123456789012-AbCdEfGhIjKl", "AbCdEfGhIjKl"),
    ("xo" "xp-123456789012-MnOpQrStUvWx", "MnOpQrStUvWx"),
    ("xo" "xa-123456789012-YzAbCdEfGhIj", "YzAbCdEfGhIj"),
    ("gl" "pat-AbCdEfGhIj1234567890", "AbCdEfGhIj1234567890"),
    ("aws AK" "IAIOSFODNN7EXAMPLE id", "AK" "IAIOSFODNN7EXAMPLE"),
    ("Authorization: Basic dXNlcjpwYXNzd29yZA==", "dXNlcjpwYXNzd29yZA=="),
    ("curl -H 'Authorization: Bearer abcDEF123456xyz' url", "abcDEF123456xyz"),
    ('{"Authorization": "Token zzz-secret-header-value"}', "zzz-secret-header-value"),
    ("header Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig ok", "eyJhbGciOiJIUzI1NiJ9"),
    ("OPENAI_API_KEY=hunter2hunter2", "hunter2hunter2"),
    ("db_password: s3cr3tP4ss", "s3cr3tP4ss"),
    ('GITHUB_TOKEN="quoted token value"', "quoted token value"),
    ("client_secret = 'single quoted secret'", "single quoted secret"),
    ('{"api_key": "json-key-value-123"}', "json-key-value-123"),
    ("see https://alice:p4ssw0rd@example.com/repo", "p4ssw0rd"),
    ("see https://alice:p4ssw0rd@example.com/repo", "alice"),
    ("-----BE" "GIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEAxyz123\nabcDEF456\n-----END RSA PRIVATE KEY-----", "MIIEowIBAAKCAQEAxyz123"),
    ("-----BE" "GIN PRIVATE KEY-----\ntruncatedKeyBody789", "truncatedKeyBody789"),
]


class RedactTest(Base):
    def test_each_pattern_is_replaced(self):
        for text, secret in PLANTED:
            with self.subTest(text[:40]):
                out = dc.redact(text)
                self.assertNotIn(secret, out)
                self.assertIn("[REDACTED]", out)
                self.assertEqual(dc.redact(out), out)  # idempotent

    def test_exact_outputs_and_ordinary_text_survives(self):
        self.assertEqual(dc.redact("see https://alice:p4ss@example.com/repo"), "see https://[REDACTED]@example.com/repo")
        self.assertEqual(dc.redact("OPENAI_API_KEY=hunter2 next\nother"), "OPENAI_API_KEY=[REDACTED]\nother")
        self.assertEqual(dc.redact("Authorization: Bearer abc12345678"), "Authorization: [REDACTED]")
        plain = "The task-force found risk-based keyboard shortcuts at https://example.com/a?b=c on 2026-11-04."
        self.assertEqual(dc.redact(plain), plain)

    def test_planted_secrets_never_reach_the_request_body(self):
        secrets = [s for _, s in PLANTED]
        blob = "\n".join(t for t, _ in PLANTED)
        questions = [
            {"type": "predicate", "name": "p", "instructions": "Is this fine?\n" + blob},
            {"type": "choice", "name": "c", "instructions": "Pick.",
             "choices": [{"value": "a", "description": blob}, {"value": "b", "description": "plain"}]},
            {"type": "score", "name": "s", "instructions": "Rate.",
             "levels": [{"label": "lo", "description": blob}, {"label": "hi", "description": "plain"}]},
        ]
        inputs = [  # (input, ordinary word that must survive)
            ("before\n" + blob + "\nafter", "before"),
            ([{"role": "user", "content": "msg\n" + blob},
              {"role": "user", "content": [{"type": "input_text", "text": blob}]}], "msg"),
        ]
        for inp, keep in inputs:
            fake = FakePost({"answers": []})
            self.run_decide(fake, questions, input=inp)
            (_, body, headers, _), = fake.calls
            sent = json.dumps(body)
            for s in secrets:
                self.assertNotIn(s, sent)
            self.assertIn("[REDACTED]", sent)
            self.assertIn(keep, sent)
            self.assertIn("plain", sent)
            self.assertEqual([q["name"] for q in body["questions"]], ["p", "c", "s"])
            self.assertEqual(headers["Authorization"], "Bearer " + KEY)  # the real key is only in the header


class LedgerTest(Base):
    def test_one_line_per_call_with_all_fields_and_no_input_or_key(self):
        marker = "UNIQUE-INPUT-MARKER-7731"
        usage = {"input_tokens": 1_000_000, "input_tokens_details": {"cached_tokens": 200_000, "cache_write_tokens": 0}}
        fake = FakePost({"answers": [A_CHOICE, A_PRED], "usage": usage})
        err, out = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            self.run_decide(fake, [Q_CHOICE, Q_PRED], input=marker)
        lines = self.ledger_lines()
        self.assertEqual(len(lines), 1)
        rec = lines[0]
        self.assertEqual(set(rec), {"ts", "pilot", "model", "n_questions", "input_sha256", "input_chars", "outcome",
                                    "latency_ms", "input_tokens", "cached_tokens", "cache_write_tokens", "cost_usd",
                                    "answers"})
        self.assertRegex(rec["ts"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00$")
        self.assertEqual((rec["pilot"], rec["model"], rec["n_questions"]), ("test-pilot", "gpt-6-luna", 2))
        self.assertEqual(rec["input_sha256"], hashlib.sha256(marker.encode()).hexdigest())
        self.assertEqual(rec["input_chars"], len(marker))
        self.assertEqual(rec["outcome"], "ok")
        self.assertIsInstance(rec["latency_ms"], int)
        self.assertEqual((rec["input_tokens"], rec["cached_tokens"], rec["cache_write_tokens"]),
                         (1_000_000, 200_000, 0))
        self.assertEqual(rec["cost_usd"], 0.082)  # 0.8M x 0.10 + 0.2M x 0.01, per 1M
        self.assertEqual(rec["answers"], [
            {"name": "topic", "status": "ok", "choice": "billing", "confidence": 0.93},
            {"name": "urgent", "status": "ok", "probability": 0.92}])
        raw = self.ledger.read_text()
        self.assertNotIn(marker, raw)
        self.assertNotIn(KEY, raw)
        self.assertNotIn(KEY, out.getvalue() + err.getvalue())
        self.assertEqual(out.getvalue() + err.getvalue(), "")
        self.run_decide(FakePost(exc=http_error(500)), input=marker)
        self.assertEqual(len(self.ledger_lines()), 2)  # appended, not overwritten

    def test_cost_with_cache_writes(self):
        usage = {"input_tokens": 1_000_000, "input_tokens_details": {"cached_tokens": 200_000, "cache_write_tokens": 100_000}}
        self.run_decide(FakePost({"answers": [A_CHOICE], "usage": usage}))
        rec = self.ledger_lines()[-1]
        # 0.7M x 0.10 + 0.2M x 0.01 + 0.1M x 0.125 = 0.07 + 0.002 + 0.0125
        self.assertEqual(rec["cost_usd"], 0.0845)
        self.assertEqual(rec["cache_write_tokens"], 100_000)

    def test_missing_usage_is_zero_cost(self):
        self.run_decide(FakePost({"answers": [A_CHOICE]}))
        rec = self.ledger_lines()[-1]
        self.assertEqual((rec["input_tokens"], rec["cached_tokens"], rec["cost_usd"]), (0, 0, 0))

    def test_assignment_and_flag_forms(self):
        s = "hunter2hunter2"
        for text in (f'apiKey := "{s}"', f'"password" => "{s}"', f'config["password"] = "{s}"', f"env['api_key'] = '{s}'",
                     f'headers["Authorization"] = "Basic {s}"', f'{{\\"api_key\\":\\"{s}\\"}}', f"--password {s}",
                     f'--api-key "{s}"', f'TOKEN = os.getenv("TOKEN", "{s}")', f'api_keys: ["{s}", "{s}"]',
                     f"password: correct {s} battery", f"if token == '{s}':", f"postgres://admin:p@{s}@db/x"):
            with self.subTest(text):
                out = dc.redact(text)
                self.assertNotIn(s, out)
                self.assertEqual(dc.redact(out), out)

    def test_wrapped_and_multi_part_values(self):
        s, q3, q1 = "hunter2hunter2", '"' * 3, "'" * 3
        for text in (f'+db_password = (\n+    "{s}"\n+)\n', f'password = (\n    "{s}"\n    "{s}"\n)\n', f'token = [\n  "{s}",\n]\n',
                     f'password = \\\n    "{s}"\n', f'password = {q3}{s}\n{s}{q3}\n', f"password = {q1}{s}{q1}\n",
                     f'password = "abc\\"{s}"', f'password = "a" "{s}"', f'password = "a" + "{s}"', f"--password 'a b {s}'"):
            with self.subTest(text):
                out = dc.redact(text)
                self.assertNotIn(s, out)
                self.assertEqual(dc.redact(out), out)

    def test_recognized_token_formats(self):
        for token in ("sk" "_live_" + "a1b2c3d4e5", "rk" "_test_" + "a1b2c3d4e5", "gh" "u_a1b2c3d4e5", "gh" "r_a1b2c3d4e5",
                      "lin" "_api_a1b2c3d4e5", "nt" "n_a1b2c3d4e5", "np" "m_a1b2c3d4e5", "AI" "za" + "a1b2c3d4e5f6g7h8i9"):
            with self.subTest(token[:6]):
                self.assertEqual(dc.redact(f"see {token} here"), "see [REDACTED] here")

    def test_a_pem_header_alone_keeps_what_follows(self):
        header = "-----BEGIN " + "PRIVATE KEY-----"
        self.assertIn("next_line = 1", dc.redact(f'+assert pem.startswith("{header}")\n+next_line = 1\n'))
        cut = dc.redact(f"{header}\nMIIEvQIBADANBgkqhkiG9w0B\n+AQEFAASCBKcwggSjAgEAAoIB\nnext line\n")
        self.assertNotIn("MIIEvQ", cut)
        self.assertNotIn("AQEFAA", cut)
        self.assertIn("next line", cut)

    def test_by_name_off_keeps_named_values_and_masks_formats(self):
        token = "sk" "-test1234567890abcdef"
        self.assertEqual(dc.redact(f"max_new_tokens=1 and {token}", by_name=False), "max_new_tokens=1 and [REDACTED]")
        fake = FakePost({"answers": [A_CHOICE]})
        self.run_decide(fake, input="max_new_tokens=1", redact_by_name=False)
        self.assertEqual(fake.calls[0][1]["input"], "max_new_tokens=1")
        self.run_decide(fake, input="max_new_tokens=1")
        self.assertEqual(fake.calls[1][1]["input"], "max_new_tokens=[REDACTED]")

    def test_a_secret_on_the_following_lines_is_redacted(self):
        v = "OPAQUEvalue0123456789"
        for label, text in (("block", f"client_secret: |-\n  {v}\n  {v}\nnext: 1\n"),
                            ("folded", f"api_key: >\n    {v}\nnext: 1\n"),
                            ("keep marker", f"token: |+\n  {v}\nnext: 1\n"),
                            ("in a diff", f"+client_secret: |-\n+    {v}\n+next: 1\n"),
                            ("context lines", f" client_secret: |-\n     {v}\n"),
                            ("removed lines", f"-password: |\n-  {v}\n"),
                            ("value alone", f"client_secret:\n  {v}\nnext: 1\n"),
                            ("value alone, diff", f"+client_secret:\n+  {v}\n"),
                            ("double quoted", f'client_secret:\n  "{v}"\nnext: 1\n'),
                            ("single quoted, diff", f"+client_secret:\n+  '{v}'\n+next: 1\n"),
                            ("short and quoted", f'password:\n  "{v[:6]}"\nnext: 1\n'),
                            ("json with a comma", f'"api_key":\n    "{v}",\n')):
            with self.subTest(label):
                out = dc.redact(text)
                self.assertNotIn(v[:6], out)
                self.assertEqual(dc.redact(out), out)
                if "next: 1" in text:
                    self.assertIn("next: 1", out)  # the block ends at the first unindented line

    def test_code_after_a_key_like_name_is_kept(self):
        code = "for t in tokens:\n    print(t)\nif self.password:\n    check_the_password_now()\n"
        self.assertEqual(dc.redact(code), code)

    def test_list_input_is_hashed_after_redaction_not_stored(self):
        msgs = [{"role": "user", "content": "keep this out OPENAI_API_KEY=hunter2hunter2"}]
        self.run_decide(FakePost({"answers": [A_CHOICE]}), input=msgs)
        rec = self.ledger_lines()[-1]
        self.assertRegex(rec["input_sha256"], r"^[0-9a-f]{64}$")
        self.assertGreater(rec["input_chars"], 0)
        self.assertNotIn("keep this out", self.ledger.read_text())
        self.assertNotIn("hunter2", self.ledger.read_text())

    def test_default_ledger_path_under_home(self):
        del os.environ["MAENG_DECISIONS_LEDGER"]
        self.run_decide(FakePost({"answers": [A_CHOICE]}))
        default = self.tmp / "Documents" / "maeng-harness" / "decisions" / "ledger.jsonl"
        self.assertEqual(len(default.read_text().splitlines()), 1)

    def test_unwritable_ledger_does_not_break_the_call(self):
        os.environ["MAENG_DECISIONS_LEDGER"] = str(self.work)  # a directory
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            res = self.run_decide(FakePost({"answers": [A_CHOICE]}))
        self.assertEqual(res[0]["status"], "ok")
        self.assertIn("ledger write failed", err.getvalue())
        self.assertNotIn(KEY, err.getvalue())


if __name__ == "__main__":
    unittest.main()
