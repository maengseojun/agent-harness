# Director brief

The brief replaces a mood prompt. Answer five questions, then fill the template. Ask only what the request leaves open, one question at a time, recommended answer first.

## Five questions

1. **무엇을 보여주나?** The product, feature or idea, in one line.
2. **보는 사람이 기억할 한 문장은?** One sentence. Everything else serves it.
3. **어떤 레퍼런스를 써도 되나?** Sites, films, decks the user allows, and what not to copy from them.
4. **실제 제품에서 와야 하는 것은?** Screens, recordings, logos, numbers that must be real.
5. **용납 못 하는 것은?** Hard no's: claims, competitor names, colors, tone, length.

## Defaults when the user does not say

| Field | Default | Why |
|---|---|---|
| Length | 30 s (15-60) | One idea, phone attention span |
| Aspects | 16:9 and 9:16 | Deck or site, plus social |
| Language | Korean on screen | The audience reads Korean |
| Sound | None; text carries the message | No paid generation without approval |
| Audience | Named in question 2's sentence | Forces a concrete viewer |

## BRIEF.md template

```markdown
---
slug: <kebab-case>
length: 30
aspects: [wide, vertical]
language: ko
sound: none
---

## FILM
What it shows:
Remember (one sentence):
Audience:
Where it plays:

## ASSETS
Real (must be used as is):
Allowed references:
Missing (ask before building):

## VISUAL RULES
From brand/frame.md:
Do not copy:
Never:

## DELIVERABLES
- wide.mp4 1920x1080, vertical.mp4 1080x1920
- poster frames, contact sheets, source, assets list

## Stated vs inferred
Stated by the user:
Inferred (correct me here):
```
