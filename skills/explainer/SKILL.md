---
name: explainer
description: Explain concepts, systems and research using the original Diagram Design method through diagram-explainer first. Produce the requested visual directly as HTML/SVG, while respecting explicit text-only, brief chat, interactive and video formats.
---

# Explainer

For a substantive explanation request, start with [diagram-explainer](../diagram-explainer/SKILL.md): the migrated original Diagram Design skill, 45 type guides and real templates. A visual result is the personal default unless the user explicitly asks for text only, a brief chat answer or a chat table. Read a fitting type/example, then author the final HTML with inline SVG directly. Return the result in the same task. Do not create another diagram first and redraw it into Diagram Design. SVG/PNG export is mechanical reuse of the authored source.

Resolve the reader's question, inspected evidence and explicit output requirements. A brief chat answer or explicit text-only/table-only request stays in that format. A direct diagram-explainer invocation requests a visual even when a timeline or causal map is called a `표`. A skill edit plus an artifact request requires both.

## Shared meaning and routes

Read [reference-contract.md](references/reference-contract.md) and the relevant scope/evidence sections of [explanation-design.md](references/explanation-design.md). Run `scripts/check_references.py --mode diagram` for figures or `--mode text` for prose. A missing/conflicting required source blocks only its affected step; name the gap rather than substituting stale content.

| Requested result | Route |
| --- | --- |
| Explanation, research overview, diagram or timeline | Diagram Design first through diagram-explainer; direct HTML/SVG and inspected preview |
| Explicit brief/text-only/chat table | Requested prose/table, no forced file |
| Manipulating values or stepping through states materially answers the question | Installed interactive-explainer, retaining the same evidence and conditions |
| Explicit video/script/storyboard | Installed tutorial-video; ordinary explanation does not authorize video |

Specialists execute their own contract without routing back recursively. Prefer one canvas for an overview/research synthesis and one complete canvas for a timeline. Use complementary diagrams only where they answer distinct questions within the whole. Avoid unnecessary page splits and report cards filled with prose.

## Verify and deliver

Use the original Diagram Design palette and layout with the five downloaded default faces in diagram-explainer's [local-fonts.md](../diagram-explainer/references/local-fonts.md). The retired Casual and personal-balanced profiles are not defaults. Generate a supporting symbol only if it adds useful meaning; compose the complete explanation in the SVG.

Keep facts, proposals, unknowns, chronology and causes distinct. Inspect real rendering, text fit, reading order and coverage. Preserve existing output files. Follow diagram-explainer's [personal additions](../diagram-explainer/references/personal-additions.md) and [school Drive storage](../diagram-explainer/references/delivery-storage.md): save sources/previews, verify the school account/folder, separately fetch raw files and return observed links.

For reviewed skill updates, follow [installation and maintenance](references/personal-installation.md). Source copy, installation, host discovery, actual execution and remote storage each need their own evidence.
