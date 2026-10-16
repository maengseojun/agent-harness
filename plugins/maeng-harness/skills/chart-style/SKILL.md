---
name: chart-style
description: "Henry's house style for data charts: publish (dark, sdh2 wordmark), bay (same dark layout with the BAY blues and BAY wordmark, charts in English) and analysis modes, rendered as PNG with matplotlib via the bundled chartkit module. Use for any chart, graph, plot, 차트, 그래프, 시각화 request."
---

# Chart style (sdh2)

Three modes, one module. Pick the mode from what the chart is for:

- `publish`: the chart will be posted, embedded in an article, or shown to others. Dark background (#121212), uppercase descriptive title top-left, muted "Source: ..." and "Data as of ..." lines under it, the `sdh2` wordmark top-right, no axes spines, dashed gridlines, regular-weight type everywhere (nothing bold). This is the default when in doubt.
- `bay`: the chart goes into a BAY (Blockchain at Yonsei) article. Same dark background and header as publish (the background is not a palette color), the BAY six-blue palette (`ck.BAY`: deep, primary, point, highlight, secondary, light) for the data and the `BAY` wordmark. Series cycle Secondary Blue → Light Blue → Highlight Blue → #8FB0DC → #5B7FB5 → gray; a ranked-bar ramp is Point Blue with a Secondary accent; Deep Navy only as a fill with a Light Blue edge (e.g. a third category in a bubble timeline). Charts are in English even when the article is Korean (the Korean lives in the diagrams and captions).
- `analysis`: Henry is looking at data with you and wants to see it fast. White background, matplotlib default colors, normal-case title. Zero decoration effort.

If Henry says the chart is for a post/글/트윗/발행 → publish. If it is for a BAY article (the Notion path says BAY, or he says BAY/학회) → bay. If he says 일단 보자 / quick look / 확인용 → analysis.

## Less is the style

The references have almost no text on the canvas, and every time a chart carried more it was rejected. Concretely:

- No formulas, no subtitles, no parameter lines, no sentences explaining the chart. `finish()` gets `title`, `source`, `asof` and nothing else. If a number needs a formula to be understood, the article explains it; the chart just shows the number.
- The title says what is plotted ("DEFI LENDING TVL: COLLATERALIZED VS UNCOLLATERALIZED"), never the conclusion ("기관은 절반만 상환되면 이익"). Claim-style titles are wrong even when the claim is true.
- One label per data point at most, short: "$50.1B · 645 protocols". Legends only when there are two or more series.
- No bold anywhere: not ticks, not legends, not callouts, not value labels. Hierarchy comes from size and color, not weight.
- Pick the simplest form that carries the message: two bars, a 100% stacked bar, a bubble timeline, one line with one shaded gap. A chart that needs a model to read (a profit curve over a parameter, an R*/P curve) is not a chart for an article; leave it out or put the number in the text.
- Illustrative charts (a stylised incident price path) are allowed when the real tick data is not available, but say so in `source="Illustrative, from ... incident reports"`.

## Workflow

1. Get the data into a pandas DataFrame or numpy arrays. Never invent numbers; if data is missing, ask or fetch it.
2. Set up the toolchain once per machine (Toolchain, below), then write your script with `chartkit` importable from it.
3. Pick the chart type from the table below. One chart carries one message; if you need two messages, make two charts (or two panels).
4. Build the chart with `chartkit`, save the PNG where deliverables go in this environment (Cowork: `/mnt/user-data/outputs/`; Claude Code or Cursor: the project folder, or wherever Henry says).
5. Open the PNG with the Read tool and look at it. Fix overlapping labels, clipped callouts, duplicate tick labels, a legend covering data. Re-render. Do not deliver a chart you have not looked at.
6. Deliver the PNG. Say in one line what the chart shows; don't describe the styling.

## Which chart

| Data / message | Chart | chartkit calls |
|---|---|---|
| One metric over time | line, markers if ≤ ~30 points | `ax.plot(..., marker="o", ms=3.5)`, `money_axis`/`count_axis`, `date_axis` |
| Composition over time, absolute | stacked area | `ax.stackplot(...)`, `flush_x`, `count_axis`, `legend` |
| Composition over time, share | 100% stacked area | normalise to 100 first, `pct_axis`, `flush_x`, legend outside (`right=0.86`) |
| Volume plus a rate | stacked bars + line on a twin axis | bars on `ax`, line on `ax.twinx()`, `pct_axis(ax2, xmax=1)`, `ax2.grid(False)` |
| Ranking, one item matters | vertical bars, gray ramp, one accent | `bar_colors(n, highlight=i)`, `rotate_xticks` |
| Price/probability with a story | line + soft fill + callout boxes | `ax.fill_between(alpha=0.18)`, `callout(...)` per event |
| Before/after a threshold | two panels sharing x | `figure(size="tall", nrows=2, sharex=True)`, `event_line`, `note` |
| Two quantities, one dwarfs the other | two horizontal bars, value label on each | `ax.barh`, `money_axis(ax, "x")`, `size="wide"`, tiny bar gets its label to the right |
| Share of a whole, a few cases | 100% stacked horizontal bars, one row per case | `ax.barh(y, a)`, `ax.barh(y, b, left=a)`, `pct_axis(ax, "x")`, labels inside the big segment |
| Timeline of events | markers on a horizontal line, size = magnitude (log), labels alternating above/below | `ax.scatter`, `ax.axhline(0)`, `YearLocator`, per-event `ha` to keep labels apart |
| Raw high-frequency series | thin line, no markers | `ax.plot(lw=0.9)`, analysis mode |
| Density of a scatter | hexbin, log color scale | `ax.hexbin(x, y, gridsize=60, bins="log", cmap="Reds")`, analysis mode |

Bars and areas start at zero. A line may zoom into its range. A twin-axis rate is always 0 to 100%. Two quantities on very different scales go in two panels sharing x, not on one axis.

## Rules that make it look like the references

- Color: one chart, one or two accent colors. Multi-series charts use `ck.SERIES` in order (blue, green, red, purple, teal) and lump the tail into a gray "Others". Ranked bars are a gray ramp with a single blue accent on the bar the reader should find.
- Title (publish): descriptive, not a slogan. "TOP 10 PROJECTS BY 7-DAY REVENUE IN SOLANA ECOSYSTEM", "POLYMARKET PRICE HISTORY OF '...'". `finish()` uppercases it. Korean titles stay as written.
- Source and as-of date are part of the chart in publish mode. Pass `source="Defillama, sdh2"` (add sdh2 when the numbers are Henry's own calculation) and `asof="Nov 4, 2025"`. Only omit `asof` for intraday event charts where the x-axis already is the date.
- Wordmark: `sdh2` in publish, `BAY` in bay (pass `brand=` to override, `brand=""` for none). Use `"sustainabledickhead2"` only if Henry asks for the full name. Never put another organisation's logo or name in that slot.
- BAY mode with several series: at most 3 blues plus gray; the third category is Deep Navy filled with a Light Blue edge rather than a fourth blue.
- Date axis: rotate 45°, and choose `every` (days) or a locator so there are at most ~16 labels. Use `%m-%d` when all dates share a year, `%H:%M` for intraday.
- Numbers: `money_axis` gives $20K / $1.2M with one unit per axis; `count_axis` gives 0 / 1M / 2.5M. Don't let matplotlib print 1e6 or 1000000. A twin axis gets its own `FuncFormatter` with the unit spelled out (`$120M`, not `$120`).
- Gridlines: y only by default. Add `ax.grid(True, axis="x")` for sparse daily lines (like the buyback chart) where the reader counts days.
- Area and stacked charts: call `flush_x(ax)` so the fill touches the axes edges. Lines with markers keep the default margin.
- Callouts: 3-4 short lines (time, type, key numbers). Kind by meaning: `trade` (orange) for Henry's/the subject's own actions, `event` (red) for external news, `result` (green) for the outcome, `neutral` otherwise. Place them with `dx, dy` so boxes don't cover the line, each other, or tick labels; that's the main thing to check in step 5. A value label that would fall outside the axes goes inside the bar in white instead.
- Few categories (≤5 bars) on a 16:9 canvas look empty; use `size="wide"` or `figure(size=(9, 6.75))`.
- Fonts: Inter for Latin, Noto Sans CJK / Apple SD Gothic Neo for Korean; the stack falls back automatically. Korean labels work without any extra setting.
- Sizes: `twitter` (16:9, default), `wide` (short single series for an article), `tall` (two panels), `square`, or any `(w, h)` in inches. All render at 160 dpi (1920 px wide).

## Analysis mode specifics

Keep matplotlib defaults where they don't hurt: tab10 colors, framed legend, left/bottom spines. Title in normal case on the axes. Same axis formatters and `date_axis` apply. Speed matters more than polish here; still look at the PNG before sending.

## Toolchain

`chartkit.py` and `requirements.txt` sit next to this SKILL.md. `setup.sh` installs them into a local folder the
first time and changes nothing on a second run. It needs network and Python 3.10 or newer.

```bash
bash "${CLAUDE_SKILL_DIR}/setup.sh"   # Codex or Cursor: the setup.sh in the folder that holds this SKILL.md
```

It installs into `${ETA_CRAFT_HOME:-$HOME/.eta-craft}/chartkit`, outside the plugin, so a plugin update does not
delete it: `chartkit.py` and a Python venv `.venv` (matplotlib, numpy, pandas). It also puts Inter in `~/.fonts` when
the venv's matplotlib does not see it. If the Inter download fails (no network), the font stack falls back to
Helvetica/DejaVu Sans and the chart still renders. Every run refreshes `chartkit.py` from the plugin copy.

Run your script with that folder's Python, with the folder on `PYTHONPATH`:

```bash
CHARTKIT="${ETA_CRAFT_HOME:-$HOME/.eta-craft}/chartkit"
PYTHONPATH="$CHARTKIT" "$CHARTKIT/.venv/bin/python" make_chart.py
```

## Recipes

Single series, publish:

```python
import chartkit as ck
fig, ax = ck.figure("publish")
ax.plot(df["date"], df["usd"], color="#3B9EFF", lw=1.8, marker="o", ms=3.5)
ck.money_axis(ax, "y"); ck.date_axis(ax, fmt="%m-%d", every=1); ax.grid(True, axis="x")
ck.finish(fig, title="ORE Protocol Buyback & Burn Activity (Daily)",
          source="Defillama, sdh2", asof="Nov 4, 2025", out="ore_buyback.png")
```

Stacked bars + rate line:

```python
fig, ax = ck.figure("publish")
ax.bar(d, real, width=0.8, color=ck.C["green"], label="Real Transactions")
ax.bar(d, gamed, width=0.8, bottom=real, color=ck.C["red"], label="Gamed Transactions")
ck.count_axis(ax); ax.set_ylabel("Transactions")
ax2 = ax.twinx(); ax2.plot(d, ratio, color=ck.C["orange"], lw=1.5, label="Gamed Tx Ratio (%)")
ax2.set_ylim(0, 1); ck.pct_axis(ax2, xmax=1); ax2.set_ylabel("Gamed Tx Ratio (%)"); ax2.grid(False)
for sp in ax2.spines.values(): sp.set_visible(False)
ck.date_axis(ax, every=7)
h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, loc="upper right")
ck.finish(fig, title="...", source="Artemis Terminal", asof="Jan 13, 2026", out=out)
```

Ranked bars with one highlight:

```python
fig, ax = ck.figure("publish")
ax.bar(names, vals, width=0.6, color=ck.bar_colors(len(names), highlight=names.index("ORE Protocol")))
ck.money_axis(ax); ck.rotate_xticks(ax, 45)
ck.finish(fig, title="Top 10 Projects by 7-Day Revenue in Solana Ecosystem", source="Defillama", asof="Nov 4, 2025", out=out)
```

Price story with callouts:

```python
fig, ax = ck.figure("publish")
ax.plot(t, price, color="#8FB3D9", lw=1.4); ax.fill_between(t, price, 0, color="#8FB3D9", alpha=0.18, lw=0)
ax.set_ylim(0, 1.05); ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:.2f}"))
ck.date_axis(ax, fmt="%H:%M", locator=mdates.HourLocator()); ax.set_xlabel("Time (Jan 3, 2026)"); ax.set_ylabel("Price")
ck.callout(ax, t_buy, 0.07, "Jan 3, 2:15 AM\nType: TRADE\nTotal Cost: $7,000\nAvg Price: $0.08", "trade", dx=-30, dy=170)
ck.callout(ax, t_news, 0.62, "Jan 3, 7:32 AM\nReports: Caracas Explosions\n[The War Zone]", "event", dx=-60, dy=40)
ck.callout(ax, t[-1], 1.0, "Jan 3, 1:41 PM\nType: REDEEM\nNet Profit: +$404,221", "result", dx=-150, dy=-40)
ck.finish(fig, title="Polymarket Price History of '...'", source="Polymarket, sdh2", out=out)
```

Two panels split by an event:

```python
fig, (a1, a2) = ck.figure("publish", size="tall", nrows=2, sharex=True)
a1.plot(tt, price, color=ck.C["cyan"], lw=1.4, marker="o", ms=2.5); a1.set_title("Price Trend", pad=10)
ck.event_line(a1, split, label="Stable > 0.99", side="right")
a2.fill_between(tt, vol, 0, where=tt <= split, color="#5A5A5A", step="post", label="Vol Before 0.99")
a2.fill_between(tt, vol, 0, where=tt >= split, color="#B8860B", step="post", label="Vol After 0.99")
ck.event_line(a2, split); ck.count_axis(a2); ck.legend(a2); ck.note(a2, "Vol. After 0.99: $100,255\n(75.0% of Total)")
ck.date_axis(a2, fmt="%H:%M", locator=mdates.MinuteLocator(interval=30)); a2.set_xlabel("Time (UTC)")
ck.finish(fig, title="Volume Before vs After Price Stabilized", source="Polymarket", out=out)
```

BAY article, two bars where one dwarfs the other:

```python
B = ck.BAY
fig, ax = ck.figure("bay", size="wide")
ax.barh(["Collateralized", "Uncollateralized\n(credit)"], [50.1e9, 24.4e6], height=0.5, color=[B["secondary"], B["light"]])
ax.invert_yaxis(); ax.set_xlim(0, 54e9); ck.money_axis(ax, "x"); ax.grid(True, axis="x"); ax.grid(False, axis="y")
ax.text(50.1e9 - 0.5e9, 0, "$50.1B · 645 protocols", va="center", ha="right", fontsize=15, color="white")
ax.text(0.5e9, 1, "$24.4M · 17 protocols · 0.05% of total", va="center", ha="left", fontsize=15, color=B["light"])
ck.finish(fig, title="DeFi Lending TVL: Collateralized vs Uncollateralized", source="DefiLlama", asof="Sep 2026", left=0.11, bottom_in=0.8, out=out)
```

BAY article, bubble timeline (three categories, log-sized bubbles):

```python
fig, ax = ck.figure("bay", size="wide")
ax.axhline(0, color="#8FB0DC", lw=1.6); ax.set_ylim(-1.1, 1.1); ax.set_yticks([]); ax.grid(False)
ax.xaxis.set_major_locator(mdates.YearLocator()); ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
colors = {"Type 1": B["secondary"], "Type 2": B["light"], "Credit": B["deep"]}
for t, name, typ, amt, usd, up, ha in events:
    size = 200 + 800 * np.log10(usd / 1e7)
    ax.scatter([t], [0], s=size, color=colors[typ], edgecolor=B["light"] if typ == "Credit" else B["deep"], linewidth=2, zorder=4)
    y = 0.62 if up else -0.62
    ax.plot([t, t], [0, y * 0.8], color=colors[typ], lw=1.4, ls=(0, (3, 3)))
    ax.text(t, y, f"{name}\n{amt}", ha=ha, va="bottom" if up else "top", fontsize=12, color=B["light"], linespacing=1.3)
ck.finish(fig, title="Major Lending Protocol Incidents, 2022-2026", source="Rekt, Maple, Aave · bubble size = loss", asof="Sep 2026", left=0.05, bottom_in=0.65, out=out)
```

Analysis mode: `fig, ax = ck.figure("analysis")`, plot, `ck.finish(fig, title="Transactions per Minute", out=out)`.
