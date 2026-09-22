"""Offline, unactivated PR-to-documentation followup proposal.

Run: python3 harness/followups.py < event.json
     python3 harness/followups.py --self-test

Input is one JSON object with required fields:
  repository: GitHub owner/repo; pr_number: positive integer;
  merge_sha: full, nonzero 40-hex merge commit (not a branch or short SHA);
  event_type: pr_merged | document_updated; origin: external | harness;
  is_cleanup: boolean; documentation_impact: true | false | "unknown".
False impact also requires a nonblank no_doc_change_reason string. A document
update carries its originating PR identity and cannot be marked as a cleanup PR.
All fields validate before decisions; unknown impact always blocks. Known-impact
cleanup PRs and document updates terminate, including harness-origin updates.

decide(event) is pure and raises ValueError on invalid input. The CLI emits one
JSON object: a decision (exit 0, including blocked), or status=invalid_input and
error (exit 2). No credentials, configuration, files, or services are accessed.
Identity syntax is checked, not the truth of the supplied merge/origin/impact.

Linear policy is unavailable: proposals require policy review and approval.
The versioned key uses only the case-normalized repository, PR number and SHA;
it fits the ledger task ID contract. Callers must separately enforce ledger
uniqueness and reconcile connector outcomes. Keys do NOT make external writes
exactly-once, and this helper creates no ledger task or Linear issue.
"""

import argparse
import hashlib
import json
import re
import sys


def decide(event):
    """Validate a normalized event and return a deterministic proposal decision."""
    required = {
        "repository", "pr_number", "merge_sha", "event_type", "origin",
        "is_cleanup", "documentation_impact",
    }
    if not isinstance(event, dict) or not required <= event.keys():
        raise ValueError("Expected an event object with all required fields")
    if event.keys() - required - {"no_doc_change_reason"}:
        raise ValueError("Unexpected event fields")

    repository = event["repository"]
    if (not isinstance(repository, str) or not re.fullmatch(
            r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?/[A-Za-z0-9_.-]{1,100}",
            repository)
            or "--" in repository.split("/")[0]
            or repository.split("/")[1] in {".", ".."}):
        raise ValueError("repository must be a GitHub owner/repo name")
    number = event["pr_number"]
    if type(number) is not int or number <= 0:
        raise ValueError("pr_number must be a positive integer")
    merge_sha = event["merge_sha"]
    if (not isinstance(merge_sha, str)
            or not re.fullmatch(r"[0-9a-fA-F]{40}", merge_sha)
            or merge_sha == "0" * 40):
        raise ValueError("merge_sha must be a full nonzero 40-hex commit SHA")
    if event["event_type"] not in ("pr_merged", "document_updated"):
        raise ValueError("event_type must be pr_merged or document_updated")
    if event["origin"] not in ("external", "harness"):
        raise ValueError("origin must be external or harness")
    if type(event["is_cleanup"]) is not bool:
        raise ValueError("is_cleanup must be a boolean")
    if event["event_type"] == "document_updated" and event["is_cleanup"]:
        raise ValueError("A document update cannot be a cleanup PR")
    impact = event["documentation_impact"]
    if type(impact) is not bool and impact != "unknown":
        raise ValueError("documentation_impact must be true, false, or unknown")
    reason = event.get("no_doc_change_reason")
    if "no_doc_change_reason" in event and (
            not isinstance(reason, str) or not reason.strip()
            or any(ord(char) < 32 for char in reason)):
        raise ValueError("no_doc_change_reason must be nonblank text")
    if impact is False and reason is None:
        raise ValueError("False documentation impact requires no_doc_change_reason")

    identity = [repository.lower(), number, merge_sha.lower()]
    key = "pr-docs-v1:" + hashlib.sha256(
        json.dumps(identity, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    result = {
        "scope": "unactivated_proposal",
        "idempotency_key": key,
        "status": "terminal",
        "reason": None,
        "blocker": None,
        "proposal": None,
    }
    if reason is not None:
        result["no_doc_change_reason"] = reason.strip()
    if impact == "unknown":
        result.update(status="blocked", reason="documentation_impact_unknown",
                      blocker="Resolve documentation impact before any followup decision.")
    elif event["is_cleanup"]:
        result["reason"] = "cleanup_pr"
    elif event["event_type"] == "document_updated":
        result["reason"] = ("harness_origin_document_update"
                            if event["origin"] == "harness" else "not_a_pr_merge")
    elif impact is False:
        result["reason"] = "no_doc_change"
    else:
        result.update(
            status="approval_pending", reason="documentation_followup_proposed",
            blocker="Linear policy unavailable; verify team policy and approval before activation.",
            proposal={
                "task_id": key,
                "kind": "doc",
                "repository": identity[0],
                "pr_number": number,
                "merge_sha": identity[2],
                "description": "Review documentation against approved intent and completion conditions.",
                "acceptance": [
                    "Confirm approved intent and completion conditions against the merged changes.",
                    "Update only approved document targets, or record a no-doc-change reason.",
                    "Do not delete temporary specs/plans or purge old documents.",
                ],
            },
        )
    return result


def _json_object(pairs):
    """Reject ambiguous duplicate JSON fields instead of silently overriding them."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def self_test():
    """One embedded regression check; no extra artifacts or external IO."""
    event = {
        "repository": "Example/Project", "pr_number": 42, "merge_sha": "a" * 40,
        "event_type": "pr_merged", "origin": "external", "is_cleanup": False,
        "documentation_impact": True,
    }
    before = event.copy()
    result = decide(event)
    key = result["idempotency_key"]
    assert event == before
    assert result == decide(dict(reversed(list(event.items()))))
    assert key == decide(dict(event, repository="example/project", merge_sha="A" * 40))["idempotency_key"]
    for change in ({"merge_sha": "b" * 40}, {"pr_number": 43}, {"repository": "example/other"}):
        assert key != decide(dict(event, **change))["idempotency_key"]
    assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", key)
    assert result["scope"] == "unactivated_proposal"
    assert result["status"] == "approval_pending" and result["blocker"]
    assert result["proposal"]["task_id"] == key

    for kind in ({}, {"is_cleanup": True}, {"event_type": "document_updated", "origin": "harness"}):
        for impact in (True, False, "unknown"):
            candidate = dict(event, **kind, documentation_impact=impact)
            if impact is False:
                candidate["no_doc_change_reason"] = "Only internal formatting changed."
            outcome = decide(candidate)
            assert outcome["idempotency_key"] == key
            if impact == "unknown":
                assert outcome["status"] == "blocked" and outcome["blocker"]
            elif kind or impact is False:
                assert outcome["status"] == "terminal"
                expected = ("cleanup_pr" if kind.get("is_cleanup") else
                            "harness_origin_document_update" if kind else "no_doc_change")
                assert outcome["reason"] == expected
            else:
                assert outcome["status"] == "approval_pending"
            assert (outcome["proposal"] is not None) == (outcome["status"] == "approval_pending")
            if impact is False:
                assert outcome["no_doc_change_reason"] == candidate["no_doc_change_reason"]

    invalid = [None, [], {}, {k: v for k, v in event.items() if k != "origin"}]
    for terminal in ({}, {"is_cleanup": True}, {"event_type": "document_updated", "origin": "harness"}):
        for change in (
            {"repository": "../repo"}, {"repository": "https://github.com/a/b"},
            {"repository": None}, {"pr_number": True}, {"pr_number": 0},
            {"pr_number": "42"}, {"pr_number": 1.5}, {"merge_sha": "main"},
            {"merge_sha": "a" * 39}, {"merge_sha": "g" * 40}, {"merge_sha": "0" * 40},
            {"event_type": "pr_opened"}, {"origin": "unrecognized"},
            {"is_cleanup": "false"}, {"documentation_impact": "true"},
            {"documentation_impact": 1}, {"documentation_impact": None},
            {"documentation_impact": False},
            {"documentation_impact": False, "no_doc_change_reason": "  "},
            {"no_doc_change_reason": None}, {"no_doc_change_reason": 123},
            {"unexpected": True},
        ):
            invalid.append({**event, **terminal, **change})
    for candidate in invalid:
        try:
            decide(candidate)
        except ValueError:
            continue
        raise AssertionError("Invalid input was accepted")
    try:
        json.loads('{"is_cleanup": false, "is_cleanup": true}', object_pairs_hook=_json_object)
    except ValueError:
        pass
    else:
        raise AssertionError("Duplicate JSON fields were accepted")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--self-test", action="store_true", help="Run embedded offline regression checks")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        print(json.dumps({"self_test": "passed"}))
        return 0
    try:
        result = decide(json.load(sys.stdin, object_pairs_hook=_json_object))
    except ValueError as error:
        print(json.dumps({"status": "invalid_input", "error": str(error)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
