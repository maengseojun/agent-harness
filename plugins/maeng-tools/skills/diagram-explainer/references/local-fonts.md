# Personal default fonts — five installed faces

The user selected these downloaded faces as the default on 2026-10-14. They are five font files in two families, not five families:

| File in the user's Library/Fonts | Actual face | Use |
| --- | --- | --- |
| LINESeedKR-Rg.ttf | LINESeedSansKR-Regular | Korean text at 400 |
| LINESeedKR-Bd.ttf | LINESeedSansKR-Bold | Korean titles and emphasis at 700 |
| NunitoSans-Regular.ttf | NunitoSans-Regular | Latin text at 400 |
| NunitoSans-SemiBold.ttf | NunitoSans-SemiBold | Latin secondary emphasis at 600 |
| NunitoSans-Bold.ttf | NunitoSans-Bold | Latin titles and emphasis at 700 |

Inline [local-fonts.css](../assets/local-fonts.css) into the final HTML and SVG styles. Use `'Diagram Nunito Sans', 'Diagram LINE Seed Sans KR', system-ui, sans-serif` for normal labels; Nunito provides Latin glyphs and LINE Seed provides Hangul. Use 400 or 700 for mixed/Korean emphasis because no Korean 600 face was downloaded. Use tabular numbers when aligned numeric columns need them; use a system monospace only for actual code that needs fixed spacing. Do not bring back Casual or the previous serif/Geist font defaults.

Original Diagram Design layout, colors, shapes, connectors and type guides remain the base. Example files retain their original typography as layout references; apply this explicit personal font override when authoring new results. Mechanical export from the authored source must carry the same font-face declarations. Use the upstream SVG export helper's `--system-fonts` option to avoid adding Google Fonts imports for this local-font default.

These local faces are verified on this Mac. They are not embedded by the CSS and cannot be assumed present on another device. Keep an inspected PNG with delivery; embed or package the unchanged font files with their licenses only when portable font fidelity is requested. Inspect actual platform fonts and label bounds after any typography change. The official provenance and OFL notices are in [fonts/NOTICE.md](../assets/fonts/NOTICE.md).
