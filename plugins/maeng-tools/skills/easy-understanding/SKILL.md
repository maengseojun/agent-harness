---
name: easy-understanding
description: "Explain concepts, systems, research or decisions - /easy-understanding, 설명해줘, 쉽게 설명해줘, 이해하기 쉽게, 처음부터 설명, 교과서처럼, 기초부터, 리서치 정리, 내가 놓친 것, 결정해야 할 것 정리, 전체 흐름 그림으로, 구조도로 보여줘, explain this, help me understand, explain from first principles. Map the flow, missed points and decisions, then explain from first premises in connected textbook chapters. Use diagram-explainer for visuals. One concept stays in chat; research or decisions use one Artifact page; slides only on request. Plain diagrams go to diagram-explainer; honor brief-answer requests."
---

# Easy understanding

The reader is smart and new to the field. Every output does three things:

1. **Map:** the whole flow, plus what the reader missed and what they must decide.
2. **Chain:** the logic from its first premise, not from the conclusion.
3. **Chapters:** textbook register. Each chapter assumes the previous ones and carries their terms forward.

Reply in the user's language. The fixed labels in `references/` are written in Korean. For another language, use the [fixed-label table](references/method.md#fixed-labels) and keep each label identical across the output.

## How the references combine

`upstream/` holds verbatim copies of the references ([SOURCES.md](upstream/SOURCES.md) lists each repo, commit, license and checksum). Do not read them by default. The merged rules in `references/` are what you follow. Read an upstream file only when its merged rule does not cover the case in front of you.

**References serve narrow roles; they never run a whole output.**
- Each role below has one merged rule in one place, so two references never give competing instructions for the same thing.
- A reference may serve several narrow roles. For example, understanding-ladder sets size, sentences and the check list.
- No reference produces a whole section, page or slide in its own style. Colors, fonts and backgrounds come only from the **Colors, fonts** row.
- A past slide deck broke this rule: one reference ran some slides and another ran the rest, and the backgrounds and charts clashed.

Every vendored reference appears in this table:

| Role | Owner | Merged rule |
|---|---|---|
| Size and format | understanding-ladder | [method.md §1](references/method.md#1-size-the-answer) |
| Facts vs decisions | mattpocock grilling | [method.md §2](references/method.md#2-facts-are-your-job-decisions-are-the-users) |
| Order of the chain | eli5-plus (+ Ranedeer's 0.x idea, paraphrased) | [method.md §4](references/method.md#4-the-chain-start-from-the-first-step) |
| Term carry-forward | mattpocock teach GLOSSARY-FORMAT | [method.md §5](references/method.md#5-chapters-build-on-each-other) |
| Textbook register: purpose before mechanism, no condescension | DreambigOu ELI5 (Important Reminders) | method.md §5 |
| Map sections | mattpocock wayfinder | [method.md §6](references/method.md#6-the-map-the-flow-what-you-missed-what-to-decide) |
| Decision order | mattpocock grilling (frontier) | method.md §6 |
| What you missed | discernment-nudge + superpowers brainstorming | method.md §6 |
| Blind-spot sweep | superpowers builder-check | method.md §6 |
| Sentences | understanding-ladder rung 1 + isas1 eli5-succinct | [method.md §7](references/method.md#7-sentences) |
| Check list | understanding-ladder + learning-opportunities | [method.md §8](references/method.md#8-close-with-a-check-list) |
| Obsidian copy of the map | axton mermaid-visualizer | [method.md §9](references/method.md#9-across-sessions-only-when-asked) |
| **Colors, fonts** | **diagram-explainer (sibling skill): its style guide by default, another of its profiles on request** | [look.md § Token source](references/look.md#token-source) |
| Figure type for each phase and for the whole flow, checked every time | diagram-explainer visual-type-guide (45 types) | [look.md § Choosing the figure](references/look.md#choosing-the-figure-check-the-45-types-every-time) |
| Modes for the whole flow (accessible, animated, artistic) | isas1 summary modes | [look.md § Modes](references/look.md#modes-for-the-whole-flow) |
| Figure rules (not look) | visual-explainer | look.md § Figures |
| Page typography and reading order | isas1 summary | look.md § Page |
| Slide stage and engine | frontend-slides (sibling skill), presets off | look.md § Slides |
| Slide content budget | visual-explainer slides.md | look.md § Slides |
| Final consistency check | the main agent | [review.md](references/review.md) |

## Flow

1. **Size it** (method §1). For a page, slides or an interactive section, state the choice in one line, then continue without asking.
2. **Gather facts yourself** (method §2). Only decisions go to the user.
3. **Write the text draft:** the chain (§4) as chapters (§5), and the map (§6).
4. **Page size only: run the blind-spot sweep** (method §6). Fold the answers in.
5. **Build the output** in the one look (look.md).
   - Before each figure, check the 45-type guide to choose its type: one per structured phase, and one for the whole flow.
   - For the whole flow, also check the modes.
   - For chat, use text only, with the map as an indented tree.
6. **Review** (review.md). The main agent checks look, content and the rendered result, fixes with small edits, and checks again.
7. **Deliver.** Chat: the answer itself. Page or slides: publish with the Artifact tool and give the link. Name any borrowed value and any check you could not run.
8. **Drive, once the explanation has landed.** When the output looks finished and the user's follow-up questions are few, ask once whether to upload it to the school Drive (look.md § Page). Upload only on a yes.

Order inside the output: **map → chain chapters → check list.** A page opens with the map figure and one line saying where the reader stands. This replaces diagram-explainer's "conclusion first": the reader sees the destination at once, and the explanation still starts from the first premise.

## Conflicts already settled

Do not reopen these for each output.

| Conflict | Settled as |
|---|---|
| Length: eli5-succinct ≤150 words, summary ≤200 words, textbook chapters | The map stays short. Each chapter holds one idea and may run as long as the idea needs. |
| Analogy: ELI5 always uses one; visual-explainer says no metaphors | Use one only in the intuition step. Label it and say where it stops being true. |
| Accuracy: ELI5's "80% is fine" vs ladder's "nothing cut" | Nothing cut. A decision needs its conditions. |
| Default reader: ELI5's age 5 vs eli18 | eli18: a smart adult new to this. |
| Ordering: diagram-explainer and archify put the conclusion first; this skill starts from the first premise | Map first, then the chain from the first premise. |
| Look: diagram-explainer, frontend-slides presets, the visual-explainer kit, the isas1 palette, isas1 artistic's "real colour" | One token set per output. It is diagram-explainer's style guide unless the user asks for another of its profiles. Others contribute rules, never colors, fonts or backgrounds. Artistic mode keeps its motif and scale rules and uses `--series-n` for extra hues. |
| Mermaid: ladder's default vs visual-explainer's "only on request" | Not in chat or on pages. Only for the Obsidian copy (method §9). |
| Pauses: learning-opportunities and grilling wait for answers | No quiz pauses. Put the check list at the end, and list decisions with recommended answers. |
| Asking about format: diagram-explainer "confirm before drawing" vs ladder "don't ask" | State the choice in one line and proceed. |

## Considered and not used

These repos were looked at and do not ship here:
- Mr.-Ranedeer-AI-Tutor, excalidraw-diagram-skill, visualise and grill-me-skill have no license. The only idea taken is Ranedeer's 0.x prerequisite chain, written in our own words.
- archify, superpowers' visual companion, theme-factory, canvas-design and teach's HTML each bring their own theme.
- fabric patterns and claude-plugins-official `learning-output-style` are paraphrased in method.md and review.md, not vendored.
- ljg-explain-concept, nuwa-skill and book-to-skill are off purpose.

## Maintenance

- Check that the upstream copies are still verbatim: `cd upstream && shasum -a 256 -c SHA256SUMS`.
- Updating a reference:
  1. Copy the new upstream file in unchanged.
  2. Update SOURCES.md and SHA256SUMS.
  3. Re-read the merged rule that cites it.
- Do not edit a file under `upstream/`. Changes belong in `references/`.
