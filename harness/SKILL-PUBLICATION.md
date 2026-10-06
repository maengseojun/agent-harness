# Personal skill publication hook

The UserPromptSubmit hook establishes a per-session baseline of personal skill
folders. Stop detects new/changed SKILL.md, references, scripts, metadata and
assets, including the personal agent-harness repository's worktrees. Installed
plugin caches and `.system` folders are outside scope. Pre-existing differences
are not automatically treated as user-authorized updates. Local skill removal
is reported, not propagated as a remote deletion.

On a changed folder without a matching publication receipt, Stop asks the agent
to finish the existing loop: inspect authorization and content, validate, publish
reviewed skill files to the live default branch, read back remote files and
reconcile the installation. It does not stage, commit or push unfinished edits.
The continuation is bounded when `stop_hook_active` is true; an outage does not
trap the human in an infinite hook loop. It is a publication reminder, not a
universal sandbox or proof that an agent obeyed it.

Install with the selected local Python interpreter:

```
python3 -B harness/skill_publication_hook.py install
```

The installer adds UserPromptSubmit and Stop handlers, preserves existing hooks,
backs up hooks.json, and installs a hash-named script. It does not modify Codex
hook trust. A new conversation/review may be needed before native dispatch.

After publishing and validating a skill, record authoritative readback:

```
python3 -B /absolute/path/to/skill-publication-HASH.py verify --skill /absolute/personal/skill-folder
```

`verify` uses the authenticated gh CLI against maengseojun/agent-harness, discovers
the live default branch, pins its commit, checks the complete file set and every
file byte, then binds a receipt to the inspected local digest. A branch-only copy,
missing/extra file or subsequent edit does not clear the reminder. Run it for
both source and installed folders that changed. A receipt proves publication,
not substantive review or automatic cloud installation. No network calls run in
ordinary hook dispatch.

State lives under ~/.local/share/agent-harness/skill-publication. Tests use a
temporary home and mocked provider reads; test results are distinct from native
hook dispatch. For a harmless live probe, establish a baseline, create a temporary
personal skill folder, observe Stop, and remove the probe to restore the baseline.
Do not publish the probe or alter trust approvals to force the test to succeed.
