# Review: the main agent checks the finished output

Run this after the output is complete and before you deliver it.
- **Page or slides:** run every part.
- **Chat answer:** run part 2 against your own text.

Fix what fails with small edits, then run the failing part again. Do not rewrite the whole output.

## 1. One look

- [ ] Run `python3 <this skill>/scripts/check_palette.py <file>`. It must print `palette: house tokens only`.
  - With a requested profile, add `--tokens ~/.diagram-design/profiles/<slug>.md`.
  - A value you borrowed on purpose goes in with `--allow` and is named in the delivery.
  - So does a color that only appears as quoted text, such as an example hex in a sentence.
- [ ] Fonts: only the effective token set's stack from [look.md](look.md).
- [ ] One token set across the whole output. Nothing from the default set may be left in a page that uses another profile.
  - No face that came from a reference: Clash Display, Satoshi, Geist, Instrument Serif, Inter, JetBrains Mono, Excalifont.
- [ ] The same element looks the same everywhere: background, title position, type ramp, stroke weights, the 용어 box and the check list.
  - In a deck, compare the first, a middle and the last slide side by side.
- [ ] `accent` is on 1–2 elements per figure.
- [ ] No state is shown by color alone.
- [ ] Nothing leaked from a reference's own system. Look for:
  - gradient or textured backgrounds, or a theme that changes between slides (frontend-slides);
  - `ve-` tags or kit classes (visual-explainer);
  - `#FAF9F7` (isas1);
  - emoji markers (grilling).

## 2. Content

- [ ] **Chain.** Each step in method.md §4 is present, or is dropped because it is empty.
  - The answer starts from the first premise, not from the conclusion.
  - The map comes first, then the chain.
- [ ] **Terms.**
  - Every term is defined once, at first use.
  - Later chapters use only earlier terms.
  - No synonym rotation.
  - The same word is used in the title, the figure, the table and the text.
- [ ] **Carry-forward.** Each chapter opens with "앞에서 가져오는 것" and does not re-explain those items.
- [ ] **Figure choice.**
  - Each structured phase has one figure, and the whole flow has one.
  - Each type was chosen from the 45-type guide, and you can name the guide row it matched.
  - A mode applied to the whole flow follows look.md § Modes. Under reduced motion and in print, the page shows the final state.
- [ ] **Icons.** Every figure had the icon pass: each concrete node or outcome has its icon next to its word label; abstract nodes have none; one icon style per figure.
- [ ] **No new facts in figures.** Every node, edge and number in a figure appears in the text draft.
- [ ] **Nothing cut.** Every number, condition and hedge from the sources is still there.
- [ ] **Analogies.** Each one is labelled and says where it stops being true.
- [ ] **Map.** All five sections are present, or are marked "없음". Each decision has:
  - its options and trade-offs;
  - what it depends on;
  - a recommendation that "yes" accepts.
  - A blocked decision sits under 대기.
- [ ] **Your own calls** are labelled 제 판단 with a reason.
- [ ] **Sources.** "The source says", "I infer" and "unverified" are kept apart.
- [ ] **Reasoning faults.** Name each one you find, and fix it:
  - a term that shifts its meaning mid-argument (equivocation);
  - explaining X with X;
  - a step that skips its reason.
  - These names come from fabric's `find_logical_fallacies`, which is linked, not vendored.
- [ ] **Check list.** It has 1–3 items and is the last thing in the output.

## 3. Rendered

- [ ] Open the page in the Browser pane. Look at it at desktop width and at about 375px, in light and in dark mode.
  - The pane cannot act on a local file, and a published Artifact asks for a claude.ai sign-in. Serve the file with a throwaway `preview_start` config instead. Wrap it in a doctype and a viewport meta, as the Artifact skeleton does.
  - Check for overlapping or clipped labels and anything off the edge.
  - At 375px the page body must not scroll sideways.
  - The comparison table fits the width, so the recommended column is visible without scrolling.
  - Each arrow needs its own `path`. `marker-end` on a multi-segment path heads only its last segment.
- [ ] Check Korean line breaks with the `hangul-wrap` skill.
- [ ] Slides: each slide fits the 1920×1080 stage with no overflow at 1280×720.

## 4. Record

In the delivery message, list:
- anything borrowed from outside the house system ("borrowed: what, from where, mapped to which token");
- every check you could not run.
