"""Findings as shareable PNGs - Operator Amber, dark-first.

Design rules this file follows (they are not preferences):
  - Two measures of different scale get two stacked panels, never a dual y-axis.
  - Categorical color = venue identity, assigned in fixed order, never cycled.
    Palette validated for CVD separation + contrast against the dark surface.
  - Text wears ink tokens, never the series color; a colored mark carries identity.
  - >=2 series get a legend AND direct labels, so identity is never color-alone.
  - Thin marks (2px lines), recessive grid (y only), no chart junk.
"""
from __future__ import annotations

from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# --- Operator Amber. Two surfaces, each validated separately.
# Light is the default because a README renders light for most visitors, and a dark
# chart dropped into a light page reads as a hole punched in it.
#
# Light steps were re-validated against the ACTUAL brand paper (#f7f3e9), not the
# generic near-white. The dark-mode steps fail there: amber 2.88 and green 2.97
# against a 3.0 floor. Warmer paper eats contrast.
THEMES = {
    "light": {
        "surface": "#f7f3e9",   # warm paper
        "series": ["#b45309", "#0369a1", "#15803d"],  # contrast 4.53 / 5.35 / 4.53
        "ink": "#1c1917",
        "muted": "#57534e",     # 6.89, clears the 4.5 text floor
        "faint": "#ddd7c7",
        "zero": "#a8a29e",
    },
    "dark": {
        "surface": "#0e0e11",
        "series": ["#d97706", "#0891b2", "#16a34a"],
        "ink": "#e7e5e4",
        "muted": "#8a8078",
        "faint": "#2a2724",
        "zero": "#57534e",
    },
}

FONTS = ["Geist Mono", "Space Grotesk", "Segoe UI", "DejaVu Sans"]


def _style_axis(ax, t: dict, ylabel: str | None = None) -> None:
    ax.set_facecolor(t["surface"])
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(t["faint"])
        ax.spines[side].set_linewidth(0.8)
    ax.grid(axis="y", color=t["faint"], linewidth=0.7, alpha=0.9)
    ax.set_axisbelow(True)
    ax.tick_params(colors=t["muted"], labelsize=8, length=0)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_color(t["muted"])
    if ylabel:
        ax.set_ylabel(ylabel, color=t["muted"], fontsize=8.5, labelpad=8)


def dislocation_chart(
    series: dict[str, list[tuple[float, float]]],
    out_path: str,
    title: str,
    subtitle: str | None = None,
    source: str = "xstruct",
    theme: str = "light",
) -> str:
    """`series` maps venue label -> [(unix_ts, mid), ...] for the SAME event.

    Top panel: each venue's implied price. Bottom panel: the gap between them.
    """
    t = THEMES[theme]
    plt.rcParams["font.family"] = FONTS

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(9, 5.6), dpi=200, sharex=True,
        gridspec_kw={"height_ratios": [2.4, 1], "hspace": 0.16},
    )
    fig.patch.set_facecolor(t["surface"])

    labels = list(series.keys())
    ends: list[tuple[float, object, str]] = []
    for i, label in enumerate(labels):
        pts = series[label]
        xs = [datetime.fromtimestamp(t) for t, _ in pts]
        ys = [v for _, v in pts]
        color = t["series"][i % len(t["series"])]
        ax1.plot(xs, ys, color=color, linewidth=2.0, solid_capstyle="round", label=label, zorder=3)
        if xs:
            ax1.plot([xs[-1]], [ys[-1]], "o", color=color, markersize=5, zorder=4)
            ends.append((ys[-1], xs[-1], label))

    _style_axis(ax1, t, "implied price")

    # Direct labels at the line ends, in ink (the mark carries identity, not the text).
    # Converging series would print on top of each other, so push them apart first.
    if ends:
        lo, hi = ax1.get_ylim()
        min_sep = (hi - lo) * 0.05
        ends.sort(key=lambda e: e[0])
        placed: list[tuple[float, object, str]] = []
        for y, x, label in ends:
            if placed and y - placed[-1][0] < min_sep:
                y = placed[-1][0] + min_sep
            placed.append((y, x, label))
        for y, x, label in placed:
            ax1.annotate(
                f"  {label}", xy=(x, y), color=t["ink"], fontsize=8.5,
                va="center", ha="left", annotation_clip=False,
            )
    leg = ax1.legend(
        loc="upper left", frameon=False, fontsize=8.5, handlelength=1.6,
        borderaxespad=0, labelcolor=t["ink"],
    )
    if leg:
        leg.set_zorder(5)

    # --- bottom panel: the gap (one series -> no legend; the label names it)
    if len(labels) >= 2:
        a, b = series[labels[0]], series[labels[1]]
        n = min(len(a), len(b))
        xs = [datetime.fromtimestamp(a[i][0]) for i in range(n)]
        gap = [a[i][1] - b[i][1] for i in range(n)]
        ax2.axhline(0, color=t["zero"], linewidth=0.9, zorder=2)
        ax2.plot(xs, gap, color=t["series"][0], linewidth=1.8, solid_capstyle="round", zorder=3)
        ax2.fill_between(xs, gap, 0, color=t["series"][0], alpha=0.16, zorder=1)
        _style_axis(ax2, t, f"{labels[0]} - {labels[1]}")
        if gap:
            ax2.margins(y=0.32)  # headroom so the callout never lands on the axis
            peak = max(gap, key=abs)
            idx = gap.index(peak)
            near_right = idx > 0.75 * len(xs)
            ax2.plot([xs[idx]], [peak], "o", color=t["series"][0], markersize=4.5, zorder=4)
            ax2.annotate(
                f"max gap {peak:+.4g}",
                xy=(xs[idx], peak),
                xytext=(-8 if near_right else 8, 11),  # always placed above the point
                textcoords="offset points",
                color=t["ink"], fontsize=8.5,
                ha="right" if near_right else "left",
                va="bottom",
                # the trough sits inside the shaded area, so back the text with the
                # surface colour rather than letting it print over the curve
                bbox=dict(facecolor=t["surface"], edgecolor="none", alpha=0.88, pad=1.6),
            )
    else:
        _style_axis(ax2, t)

    fig.autofmt_xdate(rotation=0, ha="center")

    fig.text(0.065, 0.965, title, color=t["ink"], fontsize=13.5, fontweight="bold", va="top")
    if subtitle:
        fig.text(0.065, 0.905, subtitle, color=t["muted"], fontsize=9.5, va="top")
    fig.text(
        0.065, 0.022,
        f"{source} · {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        color=t["muted"], fontsize=7.5, va="bottom",
    )

    fig.subplots_adjust(left=0.09, right=0.87, top=0.80, bottom=0.11)
    fig.savefig(out_path, facecolor=t["surface"], edgecolor="none")
    plt.close(fig)
    return out_path


def _demo(out_path: str = "dislocation.png") -> str:
    """Synthetic two-venue series so the chart can be eyeballed without a live pair.

    Shaped like the story actually worth showing: a gap that OPENS when one venue
    reprices a news move first, then CLOSES as arbitrageurs step in.
    """
    import random

    rng = random.Random(11)
    t0 = datetime.now().timestamp() - 60 * 45
    a, b, pa, pb = [], [], 0.62, 0.62
    for i in range(90):
        t = t0 + i * 30
        move = 0.006 if 28 <= i <= 46 else 0.0            # the repricing event
        lag = 0.0055 if 30 <= i <= 50 else 0.0            # pascal lags into it
        pull = min(0.22, max(0.0, (i - 50) * 0.018))      # arbs close it, ramped not snapped
        pb = min(0.95, max(0.05, pb + rng.gauss(0, 0.003) + move))
        pa = min(0.95, max(0.05, pa + rng.gauss(0, 0.003) + move - lag + pull * (pb - pa)))
        a.append((t, pa))
        b.append((t, pb))
    return dislocation_chart(
        {"pascal": a, "polymarket": b},
        out_path,
        "Same event, two venues, one price gap",
        "ACA_HOUSE_2026.NOTEXT_DEM, implied probability. Polymarket reprices first and Pascal lags in, so a gap opens and then closes.",
    )


if __name__ == "__main__":
    print(_demo())
