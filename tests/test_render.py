"""Board rendering tests - mostly guarding the tick-aware price precision,
which is what keeps a $0.10-tick ETH ladder from rendering every row identically."""
from xstruct.render.board import _bar, _decimals_for, _px, render_board
from xstruct.render.theme import Glyphs, Theme
from xstruct.venue.base import Book, Level

BLOCKS = "▏▎▍▌▋▊▉█"


def test_decimals_follow_tick_not_magnitude():
    # BTC-like: 1.0 tick at ~77k -> whole numbers
    assert _decimals_for([77008.0, 77009.0, 77010.0]) == 0
    # ETH-like: 0.10 tick at ~2.5k -> 1dp (magnitude alone would have said 0)
    assert _decimals_for([2506.2, 2506.3, 2506.4]) == 1
    # prediction market: 0.001 tick in [0,1] -> 3dp
    assert _decimals_for([0.850, 0.851, 0.852]) == 3


def test_decimals_survive_float_noise():
    # 2506.6 - 2506.4 style subtraction yields 0.0999999999...; must still read as 1dp
    prices = [2505.9, 2506.0, 2506.1, 2506.3, 2506.4, 2506.6]
    assert _decimals_for(prices) == 1


def test_px_uses_thousands_separator():
    assert _px(77008.0, 0) == "77,008"
    assert _px(2506.25, 2) == "2,506.25"
    assert _px(0.86, 4) == "0.8600"


def test_bar_scales_and_clamps():
    assert _bar(0.0, BLOCKS, 10) == ""
    assert _bar(1.0, BLOCKS, 10) == "█" * 10
    assert _bar(2.0, BLOCKS, 10) == "█" * 10  # clamped
    assert len(_bar(0.5, BLOCKS, 10)) <= 10


def test_ascii_fallback_has_no_unicode():
    g = Glyphs(unicode_ok=False)
    for s in (g.blocks, g.arrow, g.rule, g.pipe, g.dot):
        s.encode("ascii")  # raises if any non-ASCII slipped in


def test_board_renders_distinct_prices_for_tight_tick():
    bids = [Level(2506.2, 10), Level(2506.1, 20)]
    asks = [Level(2506.3, 10), Level(2506.4, 20)]
    book = Book("hyperliquid", "ETH", 0.0, bids, asks)
    out = render_board(book, theme=Theme(enabled=False), top=2)
    # a 0.10 tick needs exactly 1dp: enough to separate rows, no false precision
    assert "2,506.2" in out and "2,506.3" in out
    assert "2,506.20" not in out  # would be false precision for this tick


def test_board_handles_empty_book():
    book = Book("paper", "X", 0.0, [], [])
    out = render_board(book, theme=Theme(enabled=False))
    assert "no two-sided book" in out
