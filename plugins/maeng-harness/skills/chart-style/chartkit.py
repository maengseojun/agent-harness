"""chartkit: three-mode matplotlib style for Henry's charts.

mode="publish"  : dark editorial chart (title / source / as-of / wordmark), for posts and articles
mode="bay"      : same dark layout with the BAY six-blue palette as series colors, for BAY articles
mode="analysis" : plain white chart, close to matplotlib defaults, for quick looks

Typical use:
    import chartkit as ck
    fig, ax = ck.figure("publish")               # or "bay" / "analysis"
    ax.plot(x, y, color=ck.C["blue"], lw=2, marker="o", ms=4)
    ck.money_axis(ax, "y")                        # $20K, $1.2M ...
    ck.date_axis(ax)                              # rotated date labels
    ck.finish(fig, title="ORE PROTOCOL BUYBACK & BURN (DAILY)",
              source="Defillama", asof="Nov 4, 2025", out="chart.png")
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import font_manager as fm
from matplotlib.ticker import FuncFormatter, PercentFormatter
import numpy as np

# ---------------------------------------------------------------- fonts
_PREFERRED = ["Inter", "Pretendard", "Noto Sans CJK KR", "Noto Sans CJK JP",
              "Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic",
              "Helvetica Neue", "Arial", "DejaVu Sans"]
_available = {f.name for f in fm.fontManager.ttflist}
FONT_STACK = [f for f in _PREFERRED if f in _available] or ["DejaVu Sans"]

# ---------------------------------------------------------------- colors
# Publish palette: saturated on near-black. Order = priority when several series.
C = {
    "blue":   "#1E5EFF",
    "green":  "#19D67B",
    "red":    "#F0656A",
    "purple": "#8B5CF6",
    "teal":   "#3DD1B6",
    "orange": "#F59E0B",
    "cyan":   "#22D3EE",
    "gray":   "#6E6E6E",
    "light":  "#B8B8B8",
    "white":  "#F2F2F2",
}
SERIES = [C["blue"], C["green"], C["red"], C["purple"], C["teal"], C["orange"], C["gray"]]
ACCENT = "#2B8AE6"          # single highlighted bar / line in an otherwise gray chart
BG = "#121212"
GRID = "#3A3A3A"
TXT = "#EDEDED"
MUTED = "#9A9A9A"

# Callout box fills (dark text on pastel), matching the event-annotation convention:
# trade/action = orange, external event = red, outcome/result = green, neutral = gray
CALLOUT = {
    "trade":   ("#E8B86D", "#1A1A1A"),
    "event":   ("#C96A6A", "#1A1A1A"),
    "result":  ("#8BC98B", "#1A1A1A"),
    "neutral": ("#BDBDBD", "#1A1A1A"),
}

# BAY article palette: the publish layout and background, with the BAY blues as the series colors
BAY = {"deep": "#02122F", "primary": "#02295B", "point": "#08428B", "highlight": "#0A61E7",
       "secondary": "#129AF0", "light": "#E6F1FD"}
THEMES = {
    "publish": dict(bg=BG, txt=TXT, muted=MUTED, grid=GRID, series=SERIES, accent=ACCENT,
                    base_bar=None, shade="#2A2F3A", callout=CALLOUT, brand="sdh2"),
    "bay": dict(bg=BG, txt=TXT, muted=MUTED, grid=GRID,
                series=[BAY["secondary"], BAY["light"], BAY["highlight"], "#8FB0DC", "#5B7FB5", "#6E6E6E"],
                accent=BAY["secondary"], base_bar=BAY["point"], shade="#1C2B45",
                callout={"trade": (BAY["light"], BAY["deep"]), "event": (BAY["secondary"], "#FFFFFF"),
                         "result": (BAY["highlight"], "#FFFFFF"), "neutral": ("#8FB0DC", BAY["deep"])},
                brand="BAY"),
}
T = THEMES["publish"]

SIZES = {              # inches; dpi below gives 1920x1080-class pixels
    "twitter": (12.0, 6.75),   # 16:9 - default for posts
    "wide":    (12.0, 5.4),    # short and wide - single time series in an article
    "square":  (9.0, 9.0),
    "tall":    (12.0, 10.0),   # two stacked panels
}
DPI = 160

_mode = "publish"


def _rc_publish():
    plt.rcParams.update({
        "font.family": FONT_STACK,
        "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
        "axes.edgecolor": BG, "axes.linewidth": 0,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.spines.left": False, "axes.spines.bottom": False,
        "axes.grid": True, "axes.grid.axis": "y",
        "grid.color": GRID, "grid.linestyle": (0, (2, 4)), "grid.linewidth": 0.8,
        "axes.axisbelow": True,
        "xtick.color": TXT, "ytick.color": TXT,
        "xtick.labelsize": 9.5, "ytick.labelsize": 9.5,
        "xtick.major.size": 0, "ytick.major.size": 0,
        "xtick.major.pad": 6, "ytick.major.pad": 8,
        "axes.labelcolor": TXT, "axes.labelsize": 10, "axes.labelweight": "normal",
        "axes.labelpad": 10,
        "axes.titlesize": 12, "axes.titleweight": "medium", "axes.titlecolor": TXT,
        "axes.prop_cycle": matplotlib.cycler(color=SERIES),
        "legend.frameon": False, "legend.fontsize": 8.5, "legend.labelcolor": TXT,
        "legend.handlelength": 1.6, "legend.handleheight": 0.8,
        "lines.linewidth": 1.8, "lines.markersize": 4,
        "text.color": TXT,
    })


def _rc_bay():
    """BAY variant: publish layout and background, BAY blues as series, slightly larger type (article width)."""
    _rc_publish()
    t = THEMES["bay"]
    plt.rcParams.update({
        "figure.facecolor": t["bg"], "axes.facecolor": t["bg"], "savefig.facecolor": t["bg"], "axes.edgecolor": t["bg"],
        "grid.color": t["grid"], "xtick.color": t["txt"], "ytick.color": t["txt"],
        "xtick.labelsize": 11, "ytick.labelsize": 11, "axes.labelsize": 11.5, "legend.fontsize": 10,
        "axes.labelcolor": t["txt"], "axes.titlecolor": t["txt"], "text.color": t["txt"],
        "axes.prop_cycle": matplotlib.cycler(color=t["series"]), "legend.labelcolor": t["txt"],
        "lines.linewidth": 2.4, "lines.markersize": 6,
    })


def _rc_analysis():
    plt.rcParams.update(plt.rcParamsDefault)
    plt.rcParams.update({
        "font.family": FONT_STACK,
        "figure.facecolor": "white", "axes.facecolor": "white",
        "axes.grid": True, "grid.linestyle": "--", "grid.alpha": 0.5, "grid.color": "#CCCCCC",
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.edgecolor": "#444444",
        "axes.titlesize": 12, "axes.labelsize": 10,
        "xtick.labelsize": 9, "ytick.labelsize": 9,
        "legend.fontsize": 9, "legend.frameon": True, "legend.framealpha": 0.9,
        "lines.linewidth": 1.5,
        "axes.axisbelow": True,
    })


def figure(mode: str = "publish", size="twitter", nrows: int = 1, ncols: int = 1,
           sharex: bool = False, height_ratios=None, **kw):
    """Create fig, ax (or array of axes) with the mode's rcParams applied."""
    global _mode, T
    _mode = mode
    T = THEMES.get(mode, THEMES["publish"])
    {"publish": _rc_publish, "bay": _rc_bay}.get(mode, _rc_analysis)()
    figsize = SIZES.get(size, size) if isinstance(size, str) else size
    if mode == "analysis" and isinstance(size, str) and size == "twitter":
        figsize = (12.0, 5.0)
    gridspec_kw = {"height_ratios": height_ratios} if height_ratios else None
    fig, ax = plt.subplots(nrows, ncols, figsize=figsize, dpi=DPI, sharex=sharex,
                           gridspec_kw=gridspec_kw, **kw)
    return fig, ax


# ---------------------------------------------------------------- axis formatting
def _si_formatter(axis_obj, prefix=""):
    """One unit (K/M/B) for the whole axis, chosen from the axis range at draw time,
    with just enough decimals that neighbouring ticks don't collide (no '2M 2M 2M')."""
    def fmt(v, _):
        lo, hi = axis_obj.get_view_interval()
        top = max(abs(lo), abs(hi))
        unit, suf = (1e9, "B") if top >= 1e9 else (1e6, "M") if top >= 1e6 else (1e3, "K") if top >= 1e3 else (1, "")
        ticks = axis_obj.get_majorticklocs()
        step = np.min(np.diff(ticks)) / unit if len(ticks) > 1 else 1
        dec = 0 if step >= 1 else 1 if step >= 0.1 else 2
        if v == 0:
            return f"{prefix}0"
        return f"{prefix}{v/unit:.{dec}f}{suf}"
    return FuncFormatter(fmt)


def money_axis(ax, axis="y"):
    """$20K / $1.2M / $5.9B tick labels (one unit per axis)."""
    a = ax.yaxis if axis == "y" else ax.xaxis
    a.set_major_formatter(_si_formatter(a, "$"))


def count_axis(ax, axis="y"):
    """0 / 1M / 2.5M style counts (one unit per axis)."""
    a = ax.yaxis if axis == "y" else ax.xaxis
    a.set_major_formatter(_si_formatter(a, ""))


def pct_axis(ax, axis="y", xmax=100, decimals=0):
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(PercentFormatter(xmax=xmax, decimals=decimals))


def date_axis(ax, fmt="%Y-%m-%d", rotate=45, locator=None, every=None):
    """Rotated date ticks. `every` = day interval; `locator` overrides."""
    if locator is None and every:
        locator = mdates.DayLocator(interval=every)
    if locator is not None:
        ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.DateFormatter(fmt))
    for lbl in ax.get_xticklabels():
        lbl.set_rotation(rotate)
        lbl.set_ha("right" if rotate else "center")
        lbl.set_rotation_mode("anchor")


def rotate_xticks(ax, rotate=45):
    for lbl in ax.get_xticklabels():
        lbl.set_rotation(rotate)
        lbl.set_ha("right" if rotate else "center")
        lbl.set_rotation_mode("anchor")


# ---------------------------------------------------------------- annotation helpers
def callout(ax, x, y, text, kind="neutral", dx=40, dy=40, fontsize=7.5):
    """Callout box with a connector to (x, y), plus a dot on the point.
    kind: trade (orange) / event (red) / result (green) / neutral (gray).
    dx, dy: offset of the box from the point, in points."""
    fill, fg = T["callout"][kind]
    ax.plot([x], [y], marker="o", ms=6, mfc=fill, mec="white", mew=0.9, zorder=6, ls="none")
    ax.annotate(text, xy=(x, y), xytext=(dx, dy), textcoords="offset points",
                fontsize=fontsize, color=fg, zorder=7, ma="left",
                ha="left" if dx >= 0 else "right", va="bottom" if dy >= 0 else "top",
                bbox=dict(boxstyle="round,pad=0.45,rounding_size=0.3", fc=fill, ec="none"),
                arrowprops=dict(arrowstyle="-", color=fill, lw=1.0, shrinkA=0, shrinkB=3))


def event_line(ax, x, label=None, color="#E5C05B", side="left", y=0.98, fontsize=8):
    """Dashed vertical marker for a point in time, optional label at the top."""
    ax.axvline(x, color=color, ls="--", lw=1.0, zorder=3)
    if label:
        ax.text(x, y, ("  " if side == "left" else "") + label + ("  " if side == "right" else ""),
                transform=ax.get_xaxis_transform(), color=color, fontsize=fontsize,
                ha=side, va="top")


def note(ax, text, loc="lower right", color="#E8A33D", fontsize=8.5):
    """Summary box inside the axes (e.g. 'Vol after 0.99: $100,255 (75%)')."""
    pos = {"lower right": (0.985, 0.04, "right", "bottom"),
           "upper right": (0.985, 0.96, "right", "top"),
           "lower left": (0.015, 0.04, "left", "bottom"),
           "upper left": (0.015, 0.96, "left", "top")}[loc]
    ax.text(pos[0], pos[1], text, transform=ax.transAxes, ha=pos[2], va=pos[3],
            fontsize=fontsize, color=color,
            bbox=dict(boxstyle="round,pad=0.5", fc=T["bg"] if _mode in ("publish", "bay") else "white",
                      ec=color, lw=1.0))


def bar_colors(n, highlight=None, accent=ACCENT):
    """Gray ramp for n ranked bars (1st = lightest on dark bg), one optional accent bar.
    Use when the point is a ranking with one item the reader should find."""
    if _mode == "publish":
        ramp = [matplotlib.colors.to_hex(c) for c in plt.cm.Greys(np.linspace(0.3, 0.75, n))]
        ramp = ramp[::-1]                                   # light -> dark on dark bg
    elif _mode == "bay":
        ramp = [T["base_bar"]] * n                          # one blue, accent carries the point
        accent = accent if accent != ACCENT else T["accent"]
    else:
        ramp = [matplotlib.colors.to_hex(c) for c in plt.cm.Greys(np.linspace(0.45, 0.8, n))]
    if highlight is not None:
        ramp[highlight] = accent
    return ramp


def flush_x(ax):
    """Remove side padding so area/stack charts touch the axes edges, as in the references."""
    ax.margins(x=0)


def legend(ax, loc="upper left", ncol=1, **kw):
    return ax.legend(loc=loc, ncol=ncol, **kw)


# ---------------------------------------------------------------- layout & save
def finish(fig, title=None, source=None, asof=None, subtitle=None,
           brand=None, out=None, left=0.09, right=0.96, bottom_in=1.05,
           header_in=None, hspace=0.35):
    """Place the header (title, source/as-of, wordmark), lay out, and save.

    publish / bay: uppercase title top-left, muted source/as-of lines under it, brand top-right
             (sdh2 for publish, BAY for bay; pass brand=... to override, brand="" for none).
             Header and footer are sized in inches so they look the same on every figure size.
    analysis: title on the axes (single panel) or as suptitle; source/as-of in a small footer.
    left/right: axes extent as figure fraction (widen `right` gap for an outside legend).
    bottom_in: inches reserved below the axes (rotated date labels need ~1.05).
    """
    W, H = fig.get_size_inches()
    if brand is None:
        brand = T["brand"] if _mode in ("publish", "bay") else None
    if _mode in ("publish", "bay"):
        TXT_, MUTED_ = T["txt"], T["muted"]
        x0 = 0.4 / W                                # 0.4in side margin for header text
        n_sub = sum(bool(s) for s in (subtitle, source, asof))
        hdr = header_in if header_in is not None else 0.55 + 0.19 * n_sub + 0.45
        fig.subplots_adjust(top=1 - hdr / H, bottom=bottom_in / H, left=left, right=right,
                            hspace=hspace)
        y_title = 1 - 0.45 / H
        if title:
            fig.text(x0, y_title, title.upper(), fontsize=17, fontweight="medium",
                     color=TXT_, ha="left", va="center")
        lines = []
        if subtitle: lines.append(subtitle)
        if source:   lines.append(f"Source: {source}")
        if asof:     lines.append(f"Data as of {asof}")
        if lines:
            fig.text(x0, 1 - 0.72 / H, "\n".join(lines), fontsize=9.5, color=MUTED_,
                     ha="left", va="top", linespacing=1.35)
        if brand:
            fig.text(1 - x0, y_title, brand, fontsize=14, fontweight="medium",
                     color=TXT_, ha="right", va="center")
    else:
        axes = fig.get_axes()
        if title and len(axes) == 1:
            axes[0].set_title(title, pad=12)
        elif title:
            fig.suptitle(title, fontsize=12, y=0.98)
        foot = " · ".join([s for s in
                           ([f"Source: {source}"] if source else []) +
                           ([f"Data as of {asof}"] if asof else [])])
        fig.tight_layout(rect=(0, 0.03 if foot else 0, 1, 0.95 if (title and len(axes) > 1) else 1))
        if foot:
            fig.text(0.01, 0.01, foot, fontsize=8, color="#666666", ha="left", va="bottom")
    if out:
        fig.savefig(out, dpi=DPI)
        plt.close(fig)
    return fig
