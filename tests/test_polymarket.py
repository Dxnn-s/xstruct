"""Offline tests for the Polymarket adapter.

The important one is ordering: the live API returns bids ASCENDING and asks
DESCENDING, so trusting wire order would report a best ask of 0.99 instead of
the real one. The adapter sorts both sides itself.
"""
from xstruct.venue.base import Book
from xstruct.venue.polymarket import PolymarketVenue

# mirrors real wire order observed 2026-09-11: bids ascending, asks descending
BOOK = {
    "market": "0xb1dd35",
    "asset_id": "8664575628",
    "timestamp": "1789173198232",
    "bids": [
        {"price": "0.01", "size": "763.15"},
        {"price": "0.50", "size": "100"},
        {"price": "0.85", "size": "231"},
    ],
    "asks": [
        {"price": "0.99", "size": "5478.54"},
        {"price": "0.95", "size": "10"},
        {"price": "0.87", "size": "461"},
    ],
}


def fake_get(path, params):
    if path == "/book":
        assert params.get("token_id")
        return BOOK
    if path == "/midpoint":
        return {"mid": "0.86"}
    raise AssertionError(path)


def venue():
    return PolymarketVenue(tokens={"aca": "8664575628"}, get_fn=fake_get)


def test_best_levels_despite_wire_order():
    b = venue().get_book("8664575628", depth=10)
    assert isinstance(b, Book)
    assert b.bids[0].price == 0.85  # highest bid, not the 0.01 that came first
    assert b.asks[0].price == 0.87  # lowest ask, not the 0.99 that came first
    assert b.bids[0].price < b.asks[0].price


def test_sides_are_monotonic():
    b = venue().get_book("8664575628", depth=10)
    assert all(b.bids[i].price > b.bids[i + 1].price for i in range(len(b.bids) - 1))
    assert all(b.asks[i].price < b.asks[i + 1].price for i in range(len(b.asks) - 1))


def test_depth_slice_keeps_the_best():
    b = venue().get_book("8664575628", depth=1)
    assert len(b.bids) == 1 and b.bids[0].price == 0.85
    assert len(b.asks) == 1 and b.asks[0].price == 0.87


def test_markets_and_midpoint():
    ms = venue().get_markets()
    assert ms[0].symbol == "8664575628" and ms[0].kind == "binary"
    assert venue().midpoint("8664575628") == 0.86


def test_trades_empty_is_honest():
    assert venue().get_trades("8664575628") == []
