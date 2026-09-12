"""The live board - a mirrored depth ladder in the Operator Amber register.

Layout discipline: one accent doing the work (amber chrome), cyan for derived
numbers, green/rose only on the ladder where bid/ask is a functional read.
Generous gutters, recessive rules, no decorative color. Glyphs degrade to ASCII
when the terminal can't encode block characters (Windows cp1252).
"""
from __future__ import annotations

import math
import time

from ..venue.base import Book, Market
from .theme import Theme

BAR = 14


def _bar(frac: float, blocks: str, width: int = BAR) -> str:
    frac = max(0.0, min(1.0, frac))
    total = frac * width
    full = int(total)
    s = blocks[-1] * full
    if full < width:
        idx = int((total - full) * 8)
        if idx > 0:
            s += blocks[idx - 1]
    return s


def _decimals_for(prices: list[float]) -> int:
    """Precision follows the book's actual tick, not the price magnitude.

    A $2509.10/$2509.20 ETH ladder needs 1dp or every row renders identically;
    a 77008/77009 BTC ladder needs 0. Derive it from the smallest gap present.
    """
    uniq = sorted({round(p, 10) for p in prices})
    # round the gaps: float noise turns a 0.10 tick into 0.0999999999, which
    # floors to an extra decimal and renders 2,506.250 instead of 2,506.25
    gaps = [round(b - a, 8) for a, b in zip(uniq, uniq[1:]) if b - a > 1e-9]
    tick = min(gaps) if gaps else 1.0
    return max(0, min(6, -math.floor(math.log10(tick))))


def _px(p: float, decimals: int = 4) -> str:
    return f"{p:,.{decimals}f}"


def _sz(s: float) -> str:
    return f"{s:,.0f}" if s >= 1000 else f"{s:g}"


def render_header(venue: str, n_markets: int, theme: Theme | None = None, live: bool = True) -> str:
    t = theme or Theme()
    left = t.amber("xstruct", bold=True) + t.faint(f"  {t.g.arrow}  ") + t.bright(venue)
    clock = time.strftime("%H:%M:%S")
    status = (t.green(t.g.dot) + t.muted(" live")) if live else t.muted("idle")
    sep = t.faint("   ·   ")
    right = t.muted(f"{n_markets} markets") + sep + t.muted(clock) + sep + status
    return f"\n  {left}{' ' * 6}{right}\n"


def render_board(book: Book, market: Market | None = None, theme: Theme | None = None, top: int = 5) -> str:
    t = theme or Theme()
    rows = min(top, len(book.bids), len(book.asks))
    shown = [lv.price for lv in book.bids[:rows]] + [lv.price for lv in book.asks[:rows]]
    dec = _decimals_for(shown) if shown else 4

    stats = ""
    if book.mid is not None and book.spread is not None:
        stats = (
            t.muted("mid ") + t.cyan(_px(book.mid, min(6, dec + 1)), bold=True)
            + t.faint("   ") + t.muted("spr ") + t.cyan(_px(book.spread, dec))
        )

    lines = ["", "  " + t.bright(book.symbol, bold=True) + "   " + stats]
    if market is not None and market.description:
        desc = market.description
        if len(desc) > 64:
            desc = desc[:61] + "..."
        lines.append("  " + t.muted(desc))
    lines.append("")

    if rows == 0:
        lines.append("  " + t.muted("(no two-sided book)"))
        return "\n".join(lines)

    sizes = [lv.size for lv in book.bids[:rows]] + [lv.size for lv in book.asks[:rows]]
    peak = max(sizes) if sizes else 1.0
    peak = peak or 1.0

    for i in range(rows):
        b, a = book.bids[i], book.asks[i]
        bid_bar = _bar(b.size / peak, t.g.blocks).rjust(BAR)
        ask_bar = _bar(a.size / peak, t.g.blocks).ljust(BAR)
        lines.append(
            "    "
            + t.muted(_sz(b.size).rjust(9))
            + " "
            + t.green(bid_bar)
            + "  "
            + t.ink(_px(b.price, dec).rjust(10))
            + t.faint(f"  {t.g.pipe}  ")
            + t.ink(_px(a.price, dec).ljust(10))
            + t.rose(ask_bar)
            + " "
            + t.muted(_sz(a.size))
        )
    return "\n".join(lines)


def render_rule(width: int = 72, theme: Theme | None = None) -> str:
    t = theme or Theme()
    return "  " + t.faint(t.g.rule * width)
