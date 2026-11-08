"""AC-1 prompt fixtures and a deliberately failing live-evidence gate until the lead supplies real readbacks.

Fixtures validate the contract only; they never register a task, deliver a message or populate the saved evidence.
"""
import copy
import hashlib
import json
import re
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[3]
PROMPT = REPO / "tools/watch/weekly-changes.md"
EVIDENCE = REPO / "docs/design/MAE-323-b3-watch.json"
SCHEDULE = {"cron": "0 0 * * 1", "timezone": "UTC"}
SOURCE_HOSTS = {
    "anthropic-model-changes": "platform.claude.com",
    "anthropic-cli-changes": "github.com",
    "anthropic-deprecations": "platform.claude.com",
    "openai-model-changes": "platform.openai.com",
    "openai-cli-changes": "developers.openai.com",
    "openai-deprecations": "platform.openai.com",
}
RULES = {
    "repository_writes": "Never edit roles.json or any repository file.",
    "none_found": 'Use "none found" only after a successful read of that source (status "read").',
    "retry": "Update ONE existing Linear tracking issue; never create a new issue, including on retry.",
    "unread": "Report unread sources with an error; unknown coverage is incomplete.",
    "zero_read": "Zero sources read is incomplete, never success.",
    "delivery": "Read both the issue comment and Slack message back; a failed delivery or readback is incomplete.",
}


def check_https(value):
    assert isinstance(value, str), "URL must be an https string"
    parsed = urlsplit(value)
    assert parsed.scheme == "https" and parsed.hostname and not re.search(r"\s", value), "URL must be https"
    return parsed


def parse_prompt(text):
    blocks = re.findall(r"^```json\n(.*?)\n```$", text, re.M | re.S)
    assert len(blocks) == 1, "one machine-readable JSON contract is required"
    contract = json.loads(blocks[0])
    sources = contract.get("sources")
    assert isinstance(sources, list) and sources, "source inventory must not be empty"
    assert len(sources) == len(SOURCE_HOSTS), "inventory must cover both vendors' models, CLI and deprecations"
    assert {s["id"] for s in sources} == set(SOURCE_HOSTS), "source IDs must be unique and complete"
    for source in sources:
        assert check_https(source["url"]).hostname == SOURCE_HOSTS[source["id"]], "source must be official"
        assert source.get("read", "").strip(), "each source needs reading instructions"
    assert contract.get("schedule") == SCHEDULE, "schedule must be Monday 00:00 UTC"
    assert contract.get("window") == {"days": 7, "end": "scheduled_at", "interval": "[start,end)"}, "window changed"
    assert contract.get("linear_tracking_issue") == "{{LINEAR_TRACKING_ISSUE}}", "private issue placeholder required"
    assert contract.get("slack_channel") == "{{SLACK_CHANNEL}}", "private channel placeholder required"
    assert contract.get("slack_summary_lines") == 5, "Slack summary must have five lines"
    for key, rule in RULES.items():
        assert contract.get("rules", {}).get(key) == rule, f"required rule missing or changed: {key}"
    return contract


def check_evidence(record, prompt_bytes):
    registration, delivery = record.get("registration"), record.get("delivery")
    assert isinstance(registration, dict) and isinstance(delivery, dict), (
        "AC-1 LIVE EVIDENCE MISSING: lead must fill registration and at least one actual delivery after "
        "schedule registration and both destination readbacks; nulls and fixtures are not delivery evidence"
    )
    task_id = registration.get("task_id")
    assert isinstance(task_id, str) and re.fullmatch(r"[^\s{}<>]+", task_id), "registration.task_id is required"
    assert registration.get("schedule") == SCHEDULE, "registration.schedule must be Monday 00:00 UTC"
    assert registration.get("prompt_sha256") == hashlib.sha256(prompt_bytes).hexdigest(), "registered prompt sha256 mismatch"
    run_at = datetime.fromisoformat(delivery.get("run_at", "").replace("Z", "+00:00"))
    assert run_at.tzinfo is not None and run_at.utcoffset() == timedelta(0), "delivery.run_at must be UTC"
    count = delivery.get("sources_read")
    assert type(count) is int and 0 < count <= len(SOURCE_HOSTS), "delivery.sources_read must be a nonzero inventory count"
    check_https(delivery.get("issue_comment_url"))
    check_https(delivery.get("slack_message_url"))
    assert delivery.get("readback") is True, "delivery.readback must be true after BOTH destination reads"


class ChangeWatch(unittest.TestCase):
    def setUp(self):
        self.prompt_bytes = PROMPT.read_bytes()
        self.text = self.prompt_bytes.decode("utf-8")
        self.record = json.loads(EVIDENCE.read_text())
        self.contract = parse_prompt(self.text)

    def encode(self, contract):
        return "```json\n" + json.dumps(contract) + "\n```"

    def fixture(self):
        # Synthetic validator input only; never copied into the saved evidence.
        return {
            "registration": {"task_id": "fixture-task", "schedule": dict(SCHEDULE),
                             "prompt_sha256": hashlib.sha256(self.prompt_bytes).hexdigest()},
            "delivery": {"run_at": "2026-11-09T00:00:00Z", "sources_read": 1,
                         "issue_comment_url": "https://example.invalid/issue-comment",
                         "slack_message_url": "https://example.invalid/slack-message", "readback": True},
        }

    def test_prompt_contract(self):
        self.assertEqual(len(self.contract["sources"]), 6)
        for field in ("checked_at", "status", "error", "changes", "deprecation_date", "published_at"):
            with self.subTest(field=field):
                self.assertIn(f"`{field}`", self.text)

    def test_missing_or_malformed_json(self):
        for text in ("", "```json\n{}\n```\n```json\n{}\n```", "```json\n{\n```"):
            with self.subTest(text=text), self.assertRaises((AssertionError, ValueError)):
                parse_prompt(text)

    def test_empty_or_incomplete_inventory(self):
        for sources in (None, [], self.contract["sources"][:-1], self.contract["sources"][:1] * 6):
            contract = copy.deepcopy(self.contract)
            contract["sources"] = sources
            with self.subTest(sources=sources), self.assertRaisesRegex(AssertionError, "inventory|source IDs"):
                parse_prompt(self.encode(contract))

    def test_non_https_unofficial_or_empty_source(self):
        for key, value in (("url", "http://platform.claude.com/"), ("url", "relative"), ("url", ""),
                           ("url", None), ("url", "https://example.invalid/"), ("url", "https://bad host/"),
                           ("read", "")):
            contract = copy.deepcopy(self.contract)
            contract["sources"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(AssertionError):
                parse_prompt(self.encode(contract))

    def test_each_safety_and_coverage_rule_is_required(self):
        for key in RULES:
            contract = copy.deepcopy(self.contract)
            del contract["rules"][key]
            with self.subTest(rule=key), self.assertRaisesRegex(AssertionError, key):
                parse_prompt(self.encode(contract))

    def test_schedule_window_and_destinations_are_required(self):
        for key in ("schedule", "window", "linear_tracking_issue", "slack_channel", "slack_summary_lines"):
            contract = copy.deepcopy(self.contract)
            del contract[key]
            with self.subTest(key=key), self.assertRaises(AssertionError):
                parse_prompt(self.encode(contract))

    def test_evidence_fixture_accepts_nonzero_reads_and_both_readbacks(self):
        check_evidence(self.fixture(), self.prompt_bytes)

    def test_missing_registration_or_delivery_is_not_evidence(self):
        for key in ("registration", "delivery"):
            record = self.fixture()
            record[key] = None
            with self.subTest(key=key), self.assertRaisesRegex(AssertionError, "LIVE EVIDENCE MISSING"):
                check_evidence(record, self.prompt_bytes)

    def test_bad_registration_or_changed_prompt_is_rejected(self):
        for key, value in (("task_id", ""), ("task_id", None), ("task_id", "{{TASK_ID}}"),
                           ("schedule", {"cron": "0 0 * * 0", "timezone": "UTC"}), ("prompt_sha256", "0" * 64)):
            record = self.fixture()
            record["registration"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(AssertionError):
                check_evidence(record, self.prompt_bytes)
        with self.assertRaisesRegex(AssertionError, "sha256 mismatch"):
            check_evidence(self.fixture(), self.prompt_bytes + b"\n")

    def test_delivery_requires_a_real_utc_run_time(self):
        for value in ("", "not-a-date", "2026-11-09T00:00:00", "2026-11-09T09:00:00+09:00"):
            record = self.fixture()
            record["delivery"]["run_at"] = value
            with self.subTest(value=value), self.assertRaises((AssertionError, ValueError)):
                check_evidence(record, self.prompt_bytes)

    def test_zero_or_unknown_source_reads_cannot_pass(self):
        for value in (0, -1, None, True, "1", 7):
            record = self.fixture()
            record["delivery"]["sources_read"] = value
            with self.subTest(value=value), self.assertRaisesRegex(AssertionError, "nonzero inventory count"):
                check_evidence(record, self.prompt_bytes)

    def test_missing_delivery_links_or_failed_readback_cannot_pass(self):
        for key, value in (("issue_comment_url", None), ("issue_comment_url", "http://example.invalid/comment"),
                           ("slack_message_url", ""), ("slack_message_url", "http://example.invalid/message"),
                           ("readback", False), ("readback", "true"), ("readback", 1)):
            record = self.fixture()
            record["delivery"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(AssertionError):
                check_evidence(record, self.prompt_bytes)

    # LIVE EVIDENCE GATE: intentionally fails until the lead attaches real registration and delivery. Never xfail/mock.
    def test_actual_registration_and_delivery_evidence_required(self):
        check_evidence(self.record, self.prompt_bytes)


if __name__ == "__main__":
    unittest.main()
