---
name: personal-essay
description: Use when the user writes a piece whose point is their own stance, experience and judgment - 독후감, 감상문, 소감문, 에세이, 칼럼, 회고, 자기 생각이 담긴 과제 글, "내 생각 담아서 써줘", "내 경험 넣어서", book report, reflection, opinion essay. Turns the user's memo (stance, real experiences, reservations, outlook) and the assignment's constraints into a submission draft they own and can defend, then runs their revision loop (title, ending, cutting repetition). Prose-level coherence and evidence handling go to coherent-writing; source-only reports with no personal stance go to coherent-writing or prepare-work-deliverable.
---

# Personal essay

The reader should hear the user thinking, not a summary with an opinion attached. The user supplies the ideas and the experiences; the model arranges, connects and trims them. The user may have to present or defend the piece, so every claim in it must be one they made or accepted.

## Inputs (fill the frame before drafting)

Collect these from the request, attachments and earlier turns. Use [the brief template](references/brief-template.md) when the user wants to fill it in themselves.

1. **Assignment constraints, verbatim**: length, required parts, AI-use rule, presentation or grading, deadline. Keep the original text; it decides what "done" means.
2. **Source material**: the book, article or event, or the user's notes on it.
3. **Author memo**: their stance, one or two real experiences (what happened and what they concluded), where they disagree or hold back, what they expect for the future, and the structure they want.
4. **Format**: page size and length, font size, alignment, title line, name and ID line, file type.
5. **Reader and ending**: who the piece speaks to (grader, classmates, team, public) and how it should close. Any close works when it fits the user's purpose: a general conclusion, a proposal (what we should do), a hypothesis or open question, a regret or what remained unresolved, or a reflection. The user chooses; do not default to one type.

If the author memo is missing or thin, ask briefly for: stance in one sentence, one real experience and its result, one point of disagreement or deferral, what the reader should take away, and how they want to close. Ask once, together. Do not draft their views for them.

## Ownership rules

- Never invent an experience, a result, a feeling, a number or a quote from the user. If an experience has no stated outcome, write it without one or ask.
- Keep the user's own wording for their key claims and the title they chose.
- When you add an idea the user did not give (a book example that fits, a counterpoint, a structure), say so in your reply as a suggestion, separate from what the user said, and leave it out of the draft or mark it until they accept it.
- State forecasts as the user's expectation ("~수 있다고 본다"), not as facts.
- Book claims come from the supplied material. Do not add page numbers or quotes you have not seen.

## Default shape

Follow the user's outline when they give one. Otherwise, for a piece about a book, article, lecture or event:

1. **Short summary, about 15-20%**: the source's core claim, how its argument moves, one concrete example from it, and the through-line in one sentence. Pieces with no source (a retrospective, a column) open with the situation or question instead.
2. **My view, about 40%**: where the source met the user's experience, and where experience complicated or qualified it ("그러나 ~만으로 충분하지는 않았다") rather than simple agreement. Tie one example from the source to that experience. Place each reservation next to the claim it qualifies, with its scope ("~라는 뜻은 아니며 ~정도의 생각이다"). Defer judgment openly on parts outside the user's experience and call that their limit, not the source's flaw.
3. **Wider meaning and close, about 40%**: what the view implies beyond the user (the assignment's theme, the reader's situation, the future, stated as the user's expectation), then the close the user chose. A proposal gets concrete, numbered items that each reuse an idea already developed. A conclusion states what the piece has earned in a sentence or two. A hypothesis says what would confirm or overturn it. A regret or open question names what is missing and why it matters. Whatever the type, the close adds something the body has not already said; one sentence back to the source is optional.

Title: the thesis as a short declarative phrase; for a source-based piece, add a subtitle naming it (e.g. "우리는 모두 ~가 된다 - 『책』과 ~"). Section headings say the section's claim, not its category.

First person (나는) and plain declarative endings (~다), unless the user writes otherwise. Write the reasoning in prose; lists only for genuinely parallel items such as numbered proposals. Run the coherent-writing pass on the draft for paragraph links, Korean commas and references.

## Revision loop

- Once the user edits the draft themselves, their version is the base. Change only what they ask about and report the rest as suggestions.
- For an ending review, check that it closes the way the user chose and speaks to the intended reader, and that each closing sentence adds something the body has not already said. When asked to cut repetition, remove restatements of earlier sections first and keep the close itself.
- Answer in Korean when the user writes in Korean, including explanations of your suggestions.
- After each revision, check length against the format (A4 2 pages at 11pt is about 3,000-3,300 Korean characters with spaces, including title and headings).

## Delivery

- Produce the file in the requested format with its skill (docx for Word). Leave the title line and the name/ID line where the user specified.
- Give a short prep note when the piece may be presented: the one-line thesis, two or three likely questions, and which parts are personal expectation rather than fact.
- Mention remaining typos you see in the user's final text; do not fix their final file silently.
- Record the work in Obsidian or Notion only when the user asks, through obsidian-workspace or work-records, and label it as the user's work.

A worked case with its full input and revision sequence is in [the Peopleware example](references/example-peopleware.md).
