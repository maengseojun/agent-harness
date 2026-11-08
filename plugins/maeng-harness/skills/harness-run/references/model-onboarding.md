# Model onboarding

Complete these five steps before proposing a role replacement. Keep the incumbent routing until approval.

## 1. Probe the response

Run a small response probe through the intended CLI with the candidate's exact model ID and effort.
Record the CLI ID/version, requested and observed model ID, exit status and response.
Mark response validity `invalid` for a refusal, empty or malformed output, failed invocation or wrong model.
Stop until the probe returns a valid response; retain failed attempts as limitations.

## 2. Check official sources

Read official model documentation, CLI documentation/release notes and deprecation notices for both incumbent and candidate.
Record source URLs, checked-at dates, availability, supported effort and retirement dates.
Keep unread sources and uncertain dates `unknown`; resolve access gaps before recommending replacement.

## 3. Record the candidate

Keep this candidate row in the comparison record outside `plugins/maeng-harness/policy/roles.json`.
Fill every placeholder from evidence; keep policy unchanged during evaluation.

| Status | Role | Incumbent model ID | Candidate model ID | CLI ID/version | Effort | Source URLs | Checked at | Deprecation dates |
|---|---|---|---|---|---|---|---|---|
| candidate | <role> | <incumbent-id> | <candidate-id> | <cli/version> | <effort> | <official URLs> | <date> | <dates or unknown> |

## 4. Compare a fixed task pair

Freeze exactly one implementation task and one review task before either model runs.
Assign nonempty task IDs; save complete input bundles, their digests and judging criteria with the record.
Populate this pair from representative harness work; replace task descriptions with concrete frozen inputs before execution.
Reject an empty pair, missing inputs or judging criteria, and unfilled placeholders.

| Task ID | Representative task | Judging criteria |
|---|---|---|
| implement | Fix a bounded harness bug using its approved Spec/Plan, source, callers and regression inputs. | Satisfy the supplied AC; demonstrate the regression fails before and passes after; avoid unrelated edits. |
| review | Review a frozen harness patch with a known AC violation, full changed files and verification evidence. | Find the known violation with file/line and a reproducing input; apply V-1 through V-6. |

Run both tasks once with the incumbent and once with the candidate, using identical inputs and judging criteria.
Keep the same tool access, limits and declared effort for each model; record unsupported settings as limitations.
Restart both models on both tasks if inputs or criteria change; retain earlier attempts separately.
Fill four result rows from actual outputs and checks; judge quality against each frozen criterion.
Record elapsed seconds and usage when available; mark unavailable usage `unknown`, never zero.

| Task ID | Model ID | CLI ID/version | Effort | Response validity | Quality | Elapsed seconds | Usage | Limitations | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| implement | <incumbent-id> | <cli/version> | <effort> | <valid/invalid> | <criterion results> | <seconds> | unknown | <limits> | <output/check links> |
| implement | <candidate-id> | <cli/version> | <effort> | <valid/invalid> | <criterion results> | <seconds> | unknown | <limits> | <output/check links> |
| review | <incumbent-id> | <cli/version> | <effort> | <valid/invalid> | <criterion results> | <seconds> | unknown | <limits> | <output/check links> |
| review | <candidate-id> | <cli/version> | <effort> | <valid/invalid> | <criterion results> | <seconds> | unknown | <limits> | <output/check links> |

## 5. Stop for user approval

Present the candidate row, four results, source checks, limitations and proposed policy diff to the user.
**STOP for explicit user approval before replacing a role or editing `roles.json`, including a date-only edit.**
Treat a candidate row or passing comparison as evidence, not approval; record the user's decision and exact approved scope.
After an approved replacement, recheck the affected row's `sourceUrl` and `verifiedAt` against freshly read official sources.
Run the role and documentation sync checks from the repository root:
`python3 -m pytest -q plugins/maeng-harness/tests/test_roles.py plugins/maeng-harness/tests/test_docs_sync.py`.
Record the results and remaining limitations; keep onboarding incomplete if a source or sync check fails.
