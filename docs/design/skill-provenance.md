# Skill provenance (MAE-216 / MAE-219 C2)

Date: 2026-10-17. Source labels: `repo` = `skills/` (git-tracked) or `.agents/skills/`; `loose` = `~/.claude/skills/<name>`; `_to_delete` = `~/.claude/skills/_to_delete/<name>`; `release` = `~/.local/share/agent-harness/releases/3cdfa165.../`. Repo file mtimes (2026-10-17 00:36) are checkout times and carry no information; git commit dates were used for repo copies. Losing copies are under `archive/2026-10-17-mae216/<name>-<source-label>/`. Nothing under `~/.claude/skills` was modified (copy only). `__pycache__`, `.pyc` and `.DS_Store` were excluded; skill contents were otherwise copied verbatim (no slimming or splitting).

Diverging skills (AC-2): coherent-writing, diagram-explainer, hangul-wrap, interactive-explainer, obsidian-workspace, presentation-design-interview, work-records. harness-run also differs (listed separately; its release copy supersedes the repo copy).

| skill | chosen source | other sources | differences found | reason |
|---|---|---|---|---|
| aside-browser | loose ~/.claude/skills/aside-browser | none | single source | only copy |
| ask-claude | loose ~/.claude/skills/ask-claude | none | single source | only copy |
| blockchain-upstream-review | repo skills/blockchain-upstream-review | loose ~/.claude/skills/blockchain-upstream-review | none (diff -r identical) | identical content; repo is the git-tracked source |
| chart-style | ~/.claude/skills/_to_delete/chart-style | none | single source | only copy (craft skill shared with eta-craft) |
| coherent-writing | repo skills/coherent-writing | loose ~/.claude/skills/coherent-writing (archived) | repo has extra agents/openai.yaml; loose lacks it; SKILL.md identical | repo is a strict superset; loose is not older in substance |
| design-reference | loose ~/.claude/skills/design-reference | none | single source | only copy |
| diagram-explainer | repo skills/diagram-explainer | loose ~/.claude/skills/diagram-explainer (archived) | repo has extra LICENSE; 310 shared files identical | repo is a strict superset |
| error-fix-manual-1 | loose ~/.claude/skills/error-fix-manual-1 | none | single source | only copy |
| execute-code-brief | repo skills/execute-code-brief | none | single source | only copy (loose copy absent; also folded into harness-run references/README.md per release) |
| explainer | repo skills/explainer | loose ~/.claude/skills/explainer | none (diff -r identical) | identical content; repo is the git-tracked source |
| foundry-testing | ~/.claude/skills/_to_delete/foundry-testing | none | single source | only copy (craft skill shared with eta-craft) |
| frontend-guidance | loose ~/.claude/skills/frontend-guidance | none | single source | only copy |
| frontend-slides | loose ~/.claude/skills/frontend-slides | none | single source | only copy |
| gh-address-comments | loose ~/.claude/skills/gh-address-comments | none | single source | only copy |
| gh-fix-ci | loose ~/.claude/skills/gh-fix-ci | none | single source | only copy |
| graphify-repository | loose ~/.claude/skills/graphify-repository | none | single source | only copy |
| hangul-wrap | repo skills/hangul-wrap | loose ~/.claude/skills/hangul-wrap (archived) | repo has extra LICENSE; shared files identical | repo is a strict superset |
| harness-run | release copy via loose symlink ~/.claude/skills/harness-run -> ~/.local/share/agent-harness/releases/3cdfa165.../harness-run (mtime 2026-10-14 22:44) | repo .agents/skills/harness-run (archived; last commit cff774a 2026-10-08) | release SKILL.md: new description, adds 'Planning and coding handoffs' (task-brief/execute-code-brief consolidated into references/README.md), Middleman code-question wording replaces the older 'blocker' wording, Stop 'advise' vs 'remind'; release additionally has manifest.json, references/{README.md,NOTION-WORKSPACE.md,work-records/SKILL.md}, scripts/{run,ledger,tool_hook,work_records}.py; repo has only SKILL.md and agents/openai.yaml (identical) | release is newer by date and content and the only copy with references/scripts. The task named repo .agents as the source; deviation recorded. Nested references/work-records/SKILL.md kept as in the release. Contains Endix-specific wording (Middleman, END-629) to be reviewed in the later hygiene task |
| html-prototype-interview | repo skills/html-prototype-interview | ~/.claude/skills/_to_delete/html-prototype-interview | none (identical) | identical content; repo is the git-tracked source |
| interactive-explainer | loose ~/.claude/skills/interactive-explainer | repo skills/interactive-explainer (archived) | loose SKILL.md adds 'Choose the rendering route' (Archify 3.0.1 + graphify adapter), pairs-with wording, plus references/archify-local.md, references/graphify-adapter.md, scripts/archify_local.mjs, scripts/graphify_to_archify.py; repo is SKILL.md only (last commit 2026-10-13) | loose is the newer, substantively larger feature set (deployed 2026-10-16 18:13); repo is a strict subset |
| linear | loose ~/.claude/skills/linear | none | single source | only copy |
| manuscript-writing-review | loose ~/.claude/skills/manuscript-writing-review | none | single source | only copy |
| notion-authoring | repo skills/notion-authoring | loose ~/.claude/skills/notion-authoring | none (diff -r identical) | identical content; repo is the git-tracked source |
| obsidian-workspace | loose ~/.claude/skills/obsidian-workspace, plus scripts/ocr_pdf.swift taken from repo | repo skills/obsidian-workspace (archived) | loose adds scripts/advanced_pdf.py, test_advanced_pdf.py, convert_source.py --pdf-engine-config/--pdf-pages (MinerU route), conversion.md 'Complex PDF pages' section, test_convert_source.py updates; repo has scripts/ocr_pdf.swift which the loose copy lacks even though its convert_source.py and conversion.md reference it (loose copy would hash-fail). Repo last commit 49a811e 2026-10-15 16:32 | loose is the newer, superset feature set; the one missing file ocr_pdf.swift is byte-identical to the repo file and was added so the skill is self-consistent. This is the only synthesized (non-verbatim) skill |
| playwright | loose ~/.claude/skills/playwright | none | single source | only copy |
| prepare-work-deliverable | repo skills/prepare-work-deliverable | loose ~/.claude/skills/prepare-work-deliverable | none (diff -r identical) | identical content; repo is the git-tracked source |
| presentation-design-interview | repo skills/presentation-design-interview | loose ~/.claude/skills/presentation-design-interview (archived) | repo has extra agents/openai.yaml; SKILL.md identical | repo is a strict superset |
| proof-guided-optimization | ~/.claude/skills/_to_delete/proof-guided-optimization | none | single source | only copy (craft skill shared with eta-craft) |
| screenshot | loose ~/.claude/skills/screenshot | none | single source | only copy |
| skill-feedback | repo skills/skill-feedback | loose ~/.claude/skills/skill-feedback | none (diff -r identical) | identical content; repo is the git-tracked source |
| solidity-habits | ~/.claude/skills/_to_delete/solidity-habits | none | single source | only copy (craft skill shared with eta-craft) |
| task-brief | repo skills/task-brief | none | single source | only copy (loose copy absent; also folded into harness-run references/README.md per release) |
| tutorial-video | repo skills/tutorial-video | loose ~/.claude/skills/tutorial-video | none (diff -r identical) | identical content; repo is the git-tracked source |
| vercel-deploy | loose ~/.claude/skills/vercel-deploy | none | single source | only copy |
| work-records | release copy via loose symlink ~/.claude/skills/work-records -> .../harness-run/references/work-records (mtime 2026-10-14 22:44) | repo skills/work-records (archived) | SKILL.md differs: release replaces the repo 'blocker' definition with Middleman-code-question wording and adds a 'Middleman code questions' section (about 30 lines more in release) | release is the newer deployed content; same release as harness-run |
| writing-a-vault | ~/.claude/skills/_to_delete/writing-a-vault | none | single source | only copy (craft skill shared with eta-craft) |
| writing-an-auction | ~/.claude/skills/_to_delete/writing-an-auction | none | single source | only copy (craft skill shared with eta-craft) |

Destination plugins: maeng-tools (22 skills) and maeng-harness (15 skills), per `docs/design/MAE-216-two-harness.md` section 1.1. Retired and not copied: eta-*, using-eta-*, endix-workflow (repo `skills/endix-workflow` and `_to_delete`), subscription-harness.

**Archive policy (Opus review, 2026-10-17).** The losing copies of coherent-writing, diagram-explainer, hangul-wrap and presentation-design-interview were strict subsets of the chosen repo copies (verified with `diff -rq`: nothing exists only in the loose copy), so they are not archived. Those loose originals remain under `~/.claude/skills` until the reversible quarantine at release. The archive keeps only the copies with unique content: interactive-explainer (repo), obsidian-workspace (repo), harness-run (repo .agents), work-records (repo).
