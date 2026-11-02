# Method: what to say, and in what order

The reader is smart and new to the field. Every section below names the reference that owns it. Read that upstream file only when the rule here is not enough.

## 1. Size the answer

**Owner:** understanding-ladder, Step 1 ([SKILL.upstream.md](../upstream/understanding-ladder/SKILL.upstream.md)).

| Question | Size |
|---|---|
| One concept, a definition, a procedure, A vs B | **Chat**: text and a text map |
| Research, a decision with several branches, or a structure of about 5+ connected parts | **Page**: one Artifact |
| The core difficulty is "change X, and Y changes" | **Interactive** section inside the page |
| The user asks for slides | **Slides** |
| The user asks for a video | **Storyboard** ([level-4-video.md](../upstream/understanding-ladder/references/level-4-video.md)), or `tutorial-video` when the user wants the actual file |

- A format the user names wins.
- Otherwise pick the smallest size that fully answers.
- When unsure, go one size smaller and offer the next one in one closing line.
- For a page, slides or an interactive section, open with one line that states the choice and why. Do not ask which size the user wants.

## 2. Facts are your job; decisions are the user's

**Owner:** grilling ([SKILL.upstream.md](../upstream/mattpocock-skills/grilling/SKILL.upstream.md) line 28).

- Look up every fact you can reach: files, tools, the web, sources.
- Put only real decisions to the user.
- Keep three kinds of statement apart: what the source says, what you infer, and what is unverified (eli5-plus line 35).

## 3. Write the text draft first

**Owner:** understanding-ladder, "Every rung starts from a rung-1 draft".

- Write the chain (§4) and the map (§6) as plain text before you draw anything.
- A figure, a slide or a widget adds no fact that the draft lacks. A new fact goes into the draft first.

## 4. The chain: start from the first step

**Owner:** eli5-plus, Core approach ([SKILL.upstream.md](../upstream/eli5-plus/SKILL.upstream.md) lines 16–26). That file calls its order a menu. This skill fixes the order.

The opening prerequisite chain (0.x) is re-derived in our own words from Mr.-Ranedeer-AI-Tutor's prerequisite curriculum. That repo has no license, so it is not vendored: <https://github.com/JushBJJ/Mr.-Ranedeer-AI-Tutor>.

**A concept**

0. **Starting point, 0.1 → 0.n.** List the prerequisites as a numbered chain that stops just before the topic. Include only what a smart newcomer may lack. Skip the chain when there are none.
1. **Problem.** Say what problem this solves and why the problem arises.
2. **Intuition.** Give one concrete case or analogy.
   - Label it as an analogy (비유).
   - In one line, say where it stops being true.
   - Then say what the analogy hides.
3. **Mechanism.** Give the real causal chain: condition → what happens → result.
   - Use plain words first, then name the term.
   - The analogy never replaces this step.
4. **Worked example.** Use real values. Novices learn faster from worked examples (learning-opportunities [PRINCIPLES.md](../upstream/learning-opportunities/resources/PRINCIPLES.md), "Worked Example Effect").
5. **Limits.** Cover trade-offs, failure modes and the common misconception that would build a wrong mental model.
6. **One sentence.** The whole idea in one sentence.

**A decision or research question**

0. **Starting point, 0.x**, as above.
1. **Destination and constraints.** What we are trying to reach, and what is already fixed.
2. **Why the road forks.** The mechanism that makes the options differ.
3. **Each option.** How it works, with a worked example.
4. **Comparison.** Good, caution and bad cells, plus the trade-off on each side.
5. **Recommendation and its reasons.**

For each step:
- Drop a step only when it is empty for this topic. Do not announce the drop.
- Keep one causal chain. A few connected ideas beat a list of facts.

## 5. Chapters build on each other

**Owner:** mattpocock teach ([GLOSSARY-FORMAT.md](../upstream/mattpocock-skills/teach/GLOSSARY-FORMAT.md)).

Each step in §4 is a chapter.

- **One idea per chapter.** The title states the chapter's claim, not its topic.
- **Carry forward.** Open with one line, "앞에서 가져오는 것: …", that names the terms and results from earlier chapters this chapter uses. Do not re-explain them.
- **Term ledger:**
  - Define a term once, where it first appears.
  - After that, use it without defining it again.
  - Never rotate synonyms.
  - Use earlier terms inside later definitions.
  - When the field has several words for one thing, pick one. Note the others as words to avoid.
  - When the field uses a term loosely, state the meaning used here.
- A chapter may use only terms defined in itself or in an earlier chapter.
- **One figure per phase.** A chapter whose idea has structure (an order, causes, parts, states, actors, a cycle, layers or quantities) gets one figure. Choose its type by checking the 45-type guide ([look.md § Choosing the figure](look.md#choosing-the-figure-check-the-45-types-every-time)). A chapter that is only a definition stays text.
- **On a page:** each chapter has a small 용어 box. It lists the chapter's new terms with a one-sentence definition each.
- **Register:**
  - Write like a good university textbook: motivate, define, derive, apply, bound.
  - Give the purpose before the mechanism (ELI5, Important Reminders).
  - Never condescend.

## 6. The map: the flow, what you missed, what to decide

These sections borrow from three references:
- **Sections:** wayfinder's map body ([SKILL.upstream.md](../upstream/mattpocock-skills/wayfinder/SKILL.upstream.md) § The map body).
- **Decision order:** grilling's frontier.
- **"Missed" checks:** discernment-nudge's three habits ([SKILL.upstream.md](../upstream/discernment-nudge/SKILL.upstream.md)) and superpowers brainstorming ([SKILL.upstream.md](../upstream/superpowers/brainstorming/SKILL.upstream.md) lines 56–59).

| Section | Holds |
|---|---|
| **목적지** (destination) | What reaching the end looks like, in 1–2 lines |
| **정해진 것** (settled) | Facts and settled decisions, one line each |
| **결정할 것** (to decide) | The frontier: decisions whose prerequisites are settled. For each one, see the list below this table. |
| **놓친 것** (missed) | A constraint, a conflict or a cheaper path. A claim worth checking, and against what. A step in the reasoning that needs a reason. Something the answer had to assume. A question still too blurry to decide. |
| **범위 밖** (out of scope) | What this answer does not cover |

For each decision in **결정할 것**:
- Give the context, why it matters, the options, and the trade-off on each side. This framing comes from claude-plugins-official `learning-output-style`; it is a paraphrase, not vendored.
- Give the recommended answer, worded so that "yes" accepts it (grilling lines 8, 24).
- Put a decision that hangs on another open decision under 대기, linked to that prerequisite (grilling line 26).
- Raise only real decisions that have more than one valid option.

**The whole flow.** On a page, draw the five sections as the decision map. When the topic is a process or a sequence of phases, also draw a one-canvas overview of all phases. Choose the figure type from the 45-type guide, and check the modes ([look.md § Modes for the whole flow](look.md#modes-for-the-whole-flow)).

Two more rules:
- Label everything you settled yourself as **제 판단** and give the reason. A default the user never heard is one they could not reject (superpowers lines 178–179).
- Write "없음" for an empty section rather than dropping it.

### Blind-spot sweep (page size)

**Owner:** superpowers [builder-check-prompt.md](../upstream/superpowers/brainstorming/builder-check-prompt.md).

1. Once the text draft exists, give it to a fresh subagent with the builder-check prompt. Fill `[DOMAIN]` with the field.
2. Sort what comes back into the three piles (superpowers brainstorming lines 234–243):
   - **Answered already:** put the answer into the draft.
   - **Minor:** decide it yourself and label it 제 판단.
   - **The user's:** add it to 결정할 것, most important first.
3. Without a subagent tool, read the draft as that builder yourself.

## 7. Sentences

**Owner:** understanding-ladder rung 1 (about 80% of ASD-STE100), with isas1 `eli5-succinct` for the reader rules. Applied to Korean:

- One idea per sentence.
- One term per meaning. Define it at first use.
- Name who does what. Prefer the active voice.
- Put the condition first: "X이면 Y한다".
- Write steps as a numbered list that starts with the action.
- No filler: 참고로, 결론적으로, 좋은 질문입니다.
- **Cut nothing.** Keep every number, condition and hedge (보통, ~일 수 있다). Simpler words, not less content. The result may be longer.
- Keep code, commands, paths, quoted errors and proper names exactly as they are.
- Use an analogy only when it does work. Drop it once it stops being accurate.
- When you do not know something, say so and name what the answer depends on.
- For "why", answer with a reason. For "how", answer with a sequence. For a yes/no question, put the answer on the first line.
- Match the user's register and vocabulary. Do not announce that you are doing this.

## 8. Close with a check list

**Owner:** understanding-ladder, "Always append 'What to check'". learning-opportunities supplies the reason: the fluency illusion.

- End with 1–3 items to verify: key numbers, assumptions, or a source that may disagree.
- You may make one item a self-check, such as "이 장의 인과 사슬을 용어 없이 한 문장으로 말해 보기".
- Do not stop to wait for an answer; the user chose no quiz pauses.
- A clearer, prettier output lowers the reader's guard, which is why the check list exists.

## 9. Across sessions (only when asked)

Within one answer the term ledger and the chapter chain carry the context. Use Obsidian only when the user asks to save a topic or to continue it later.

- **Save:** through the `obsidian-workspace` skill, one note per topic, containing:
  - 목적지;
  - 지금까지 이해한 것 (the chapter claims);
  - 용어 장부, in GLOSSARY format (term, definition, words to avoid);
  - 정해진 것 and 남은 결정;
  - the map as a Mermaid block, following the syntax rules in [mermaid-visualizer](../upstream/obsidian-visual-skills/mermaid-visualizer/SKILL.upstream.md) (Rules 1–4).
- **Resume:**
  1. Read the note first.
  2. Open with one line: "지난번까지: …".
  3. Continue from the next chapter, using the saved terms without defining them again.
  4. Update the note in place at the end.

## Fixed labels

The references write fixed labels in Korean because the user writes Korean. Reply in the user's language:
1. Pick each label's form in that language once.
2. Use exactly that form everywhere in the output: headings, figure tags, the check list.
3. For a language not in this table, translate the English column.

| Korean (default) | English |
|---|---|
| 목적지 | Destination |
| 정해진 것 · 정함 | Settled |
| 결정할 것 · 결정 | To decide |
| 대기 | Waiting on |
| 놓친 것 · 흐림 | Missed · Unclear |
| 범위 밖 | Out of scope |
| 앞에서 가져오는 것 | Carried forward |
| 이 장의 용어 | Terms in this chapter |
| 비유 · 이 비유가 틀리는 곳 | Analogy · Where the analogy breaks |
| 제 판단 | My call |
| 없음 | None |
| 지난번까지 | Last time |
| 확인 목록 | Check list |
| 좋음 · 주의 · 나쁨 | Good · Caution · Bad |
| 학교 Drive에도 올릴까요? | Shall I also upload this to the school Drive? |
