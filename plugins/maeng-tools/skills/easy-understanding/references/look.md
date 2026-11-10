# Look: one design system

**Owner: [diagram-explainer](../../diagram-explainer/SKILL.md).** Every visual in this skill uses one token set, the **house tokens**, for a page, a slide deck or an interactive widget. By default the house tokens are diagram-explainer's style guide and the user's five local faces. On request they come from another diagram-explainer profile (see Token source below).

Other references supply rules about *what* to draw and *how much*. They never supply colors, fonts, backgrounds or themes.

This is the rule that keeps a mixed-reference output from breaking. A past deck followed one reference on some slides and another reference on others, so its backgrounds and charts clashed slide to slide.

## Token source

**One output uses one token set.** You may change the set. You may never mix two sets in one output.

| The user | Effective style guide |
|---|---|
| Says nothing about the design | Default: diagram-explainer [style-guide.md](../../diagram-explainer/references/style-guide.md) with the [local fonts](../../diagram-explainer/references/local-fonts.md) |
| Names a saved profile | `~/.diagram-design/profiles/<slug>.md`. List the library to show what exists. |
| Wants a new token set from a source: a URL, another skill, a design system, a folder or pasted tokens | A new profile made through diagram-explainer [onboarding.md](../../diagram-explainer/references/onboarding.md) |

Rules for a requested token set:

- **Use diagram-explainer's own mechanism.** Validate the slug, the file format and the structural check by [profiles.md](../../diagram-explainer/references/profiles.md).
- **Read a named profile directly for this output.** Do not copy it over the installed `style-guide.md`. That would change every later diagram. Change the default only when the user asks for that.
- **Make a new profile through onboarding steps 1–4:**
  1. Read the source.
  2. Extract the colors and fonts.
  3. Map them onto the same semantic roles (`paper`, `ink`, `muted`, `accent`, …).
  4. Show the diff and run the constraint and contrast checks.
  - With the user's approval, write the result as a new profile file in the profile format. Do not write it into the working copy. Then read that profile for this output.
- **Keep the role names.** Every rule in this file names roles, not hex values, so the rest of this skill works unchanged on any profile.
- **Take fonts from the effective guide's Typography and Font source.** The five local faces apply only to the default set.
- **Name the token set in the delivery.** Pass its file to the palette check: `check_palette.py --tokens <file>`.

## Tokens

- Colors: the effective style guide's § Tokens (default: [style-guide.md § Tokens](../../diagram-explainer/references/style-guide.md#tokens)). Use both the light and the dark columns. Do not copy hex values into this skill; read them from there.
- Fonts: the effective guide's typography (default: [local-fonts.md](../../diagram-explainer/references/local-fonts.md), with [local-fonts.css](../../diagram-explainer/assets/local-fonts.css) inlined).
- Stroke, radius and the 4px grid: [style-guide.md § Stroke, radius, spacing](../../diagram-explainer/references/style-guide.md#stroke-radius-spacing).
- In CSS, name each custom property after its role: `--paper`, `--paper-2`, `--ink`, `--muted`, `--soft`, `--rule`, `--rule-solid`, `--accent`, `--accent-tint`, `--link`, `--guard`, `--data`, `--series-1`…`--series-5`. Define them on `:root`, and define the dark values with the Artifact dark-mode selectors.
- `accent` goes on 1–2 elements per figure. On a decision page, those are the next decision and the recommended option.

## Figures

### Choosing the figure: check the 45 types every time

Do this whenever you are about to draw the whole flow, or a chapter (phase) whose idea has structure. A phase has structure when it has an order, causes, parts, states, actors, a cycle, layers or quantities.

1. Open diagram-explainer's [visual-type-guide.md](../../diagram-explainer/references/visual-type-guide.md). Do not pick a type from memory.
   - When the question is about data, also check its **Analysis charts** table ([type-analysis.md](../../diagram-explainer/references/type-analysis.md)). Data questions include retention, many segments, monitoring a metric, experiment results, forecasts, time to an event, channel attribution and model performance.
   - An analysis chart marked advanced always keeps its "how to read it" caption.
2. Name the shape of the content in one phrase. For example: "steps with branches", "several actors handing off work", "one effect with grouped causes", "a cycle that feeds itself", "events in time".
3. Find the row whose "If you're showing…" matches that phrase.
4. Read that type guide (`type-*.md`) and its example, then draw.
5. Apply the guide's rules of thumb:
   - If a 3-column table says the same thing, use the table.
   - If two types fit, pick the dominant axis.

Defaults for this skill:
- **Whole flow:** one coherent canvas, following diagram-explainer's personal one-canvas rule. Each phase is a region of the canvas, in reading order.
- **Phase:** at most one figure per chapter. Its type is chosen by the steps above.
- **Decision map:** a tree (`type-tree.md`). Grilling calls it a *design tree*: the destination is the root, and each decision branches into the decisions that hang off it.
- **Logic chain:** a left-to-right flowchart, from the first premise to the conclusion.
- **Comparison of options:** a table with good, caution and bad cells.
- Use the figure rules owned by visual-explainer ([SKILL.upstream.md § Show, don't tell](../upstream/visual-explainer/SKILL.upstream.md)). Take only the rules: one claim per figure, a verb on every arrow, draw the difference, and never encode state by color alone. Do not take its kit, registers, `ve-` tags or fonts.

### Icons in every figure

Every figure in this skill gets the icon pass: the map, each phase figure, the whole-flow canvas, slide figures and interactive widgets. After the layout, go through the nodes and region headers. Where one is a concrete thing (a document, an agent or person, a store, a message, a tool) or an outcome (kept/lost, passed/failed), add an icon by diagram-explainer's [Icons on nodes](../../diagram-explainer/references/explanation-design.md#icons-on-nodes) rule. Abstract nodes (a rule, a property, a decision) stay text. Icons are inline SVG from [primitive-icons.md](../../diagram-explainer/references/primitive-icons.md) drawn with `currentColor`, so they follow the house tokens in light and dark. A chat answer is exempt: its map stays a text-only indented tree (§ Chat), with no SVG.

### State on the decision map

Visual-explainer says to encode state in form, not by color alone. These are its states, mapped onto house tokens:

| State | Form | Token | Word label |
|---|---|---|---|
| Destination | root box, `stroke-strong` | `ink` | 목적지 |
| Settled | solid box | `muted` stroke | 정함 |
| To decide now (frontier) | box with a decision tag | `ink`; the first one gets `accent` + `accent-tint` | 결정 |
| Waits on another decision | the same box, with a dashed edge from its prerequisite | `soft` | 대기 |
| Fog: missed or not yet specified | dashed outline | `soft` | 흐림 |
| Out of scope | outside a boundary, hairline | `rule` | 범위 밖 |

### Good, caution and bad without new hues

The house palette has no status colors. Use a word and a glyph: 좋음 ● in `ink`, 주의 ◐ in `muted`, 나쁨 ○ in `soft`. The recommended option's column gets `accent-tint`.

## Modes for the whole flow

**Owner:** isas1 `summary` modes. Upstream files:
- [accessible.md](../upstream/isas1-skills/summary/modes/accessible.md)
- [artistic.md](../upstream/isas1-skills/summary/modes/artistic.md)
- [animated.md](../upstream/isas1-skills/summary/modes/animated.md)

When you draw the whole flow (the map, or a one-canvas overview of all phases), check these three modes and apply the ones that make the flow easier to follow. If the user names a mode, use it. Modes stack. Where they conflict, accessible wins.

| Mode | Use it when | Take | Do not take |
|---|---|---|---|
| **Accessible** | Always for the structure. Use the full profile when the user names ADHD, autism or dyslexia. | One idea per block. Literal headings. The same section order every time. State labelled in words. Nothing hidden behind a click. | — |
| **Animated** | The flow has an order the eye should follow, such as phases or a path through the map. | Draw the connecting line once, phase by phase. Reveal the phases in reading order with a short stagger. Use a slow pulse only on what is blocked or waiting. Each element's default style is its final state. Respect `prefers-reduced-motion` and print. | Any library or CDN. Animated body text. Loops that show no live state. |
| **Artistic** | The whole flow has one shape worth showing: a vessel filling, a line that turns at a point of no return, a limit everything sits against. | Name one motif that comes from the data. One element at least 5× body size carries the headline fact. Ornament that encodes data. | Its own colors and hues, and its fonts. House tokens and the house font stack stay. Use `--series-n` where it wants extra hues. Also not its 200-word limit. |

## Page (Artifact)

- **Layout:** diagram-explainer [archify-methods.md § Explaining a page](../../diagram-explainer/references/archify-methods.md#explaining-a-page). One question per panel, steps placed beside their diagram, one term per thing. Its "conclusion first" rule becomes "map first" here; see [method.md](method.md).
- **Typography and reading order:** owned by isas1 `summary` ([SKILL.upstream.md § Step 2](../upstream/isas1-skills/summary/SKILL.upstream.md)).
  - Body text is 16px or larger. Line height is 1.5 or more; use 1.7 for Korean.
  - Keep the measure near 65 characters, flush left.
  - Leave more space between sections than within them.
  - Use the Z-pattern for the top of the page and the F-pattern for text sections.
  - Use its SVG collision rules.
  - Do not take its colors or its 200-word limit.
- **Delivery:** publish the page with the Artifact tool.
  - The user may ask to upload to the school Drive. Or the output may look finished and the user may have few follow-up questions, meaning the explanation landed. In either case, ask once: "학교 Drive에도 올릴까요?".
  - Upload only on a yes, through diagram-explainer [delivery-storage.md](../../diagram-explainer/references/delivery-storage.md), including its readback check.
  - Do not ask while the user is still asking follow-up questions.

## Slides

Use this only when the user asks for slides.

From [frontend-slides](../../frontend-slides/SKILL.md), take only these parts:
- the **Fixed Stage Rules**;
- all of `viewport-base.css`;
- the slide engine in `html-template.md`: navigation, `.active` and reduced motion.

**Off:** its "Design Aesthetics" section, which asks for varied themes, gradient backgrounds and distinctive fonts. Also off: `STYLE_PRESETS.md`, `bold-template-pack` and the Phase 2 style discovery. Those choices caused the broken deck.

Replace the template's `:root` block like this:

| Template variable | House token |
|---|---|
| `--bg-primary` | `--paper` |
| `--bg-secondary` | `--paper-2` |
| `--text-primary` | `--ink` |
| `--text-secondary` | `--muted` |
| `--accent` | `--accent` |
| `--accent-glow` | `--accent-tint` |
| `--font-display`, `--font-body` | the house font stack |

Keep the template's sizes and spacing at the 1920×1080 stage.

For how much goes on each slide, use visual-explainer [slides.md](../upstream/visual-explainer/references/slides.md):
- List every source item and map each one to a slide. Never drop an item.
- Follow its budget per slide.
- Put one focal point on each slide.

Every slide uses the same background, title position and type ramp.

## Interactive (rung 3)

- **Behavior:** understanding-ladder [level-3-html.md](../upstream/understanding-ladder/references/level-3-html.md). Use 1–3 parameters, update live, give every slider a value and a unit, and label sample data as sample data.
- **Look:** house tokens. Each quantity keeps one color everywhere: `--series-n` in the plot and the same color in the text.

## Chat

A small answer stays in text. Draw structure with a numbered chain or an indented tree. Do not put a colored widget in chat. If the structure needs a real picture, the answer has outgrown chat; make it a page.

## Borrowing a value the house system lacks

Some needs have no house value, such as a slider control or a slide type ramp. For those:
1. Take the value from the reference that owns the role.
2. Express it with house tokens.
3. Add it to the review notes in the form "borrowed: what, from where, mapped to which token".

A new hex color is the last resort. Pass it to the palette check with `--allow` and name it in the delivery.
