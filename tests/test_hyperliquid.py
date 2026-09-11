"""Offline tests for the Hyperliquid adapter — inject a fake POST fn so no network.
Canned payloads mirror the live shapes verified 2026-09-11."""
from xstruct.venue.base import Book, Market, Trade
from xstruct.venue.hyperliquid import HyperliquidVenue

META = {
    "universe": [
        {"name": "BTC", "szDecimals": 5, "maxLeverage": 40},
        {"name": "ETH", "szDecimals": 4, "maxLeverage": 25},
        {"name": "OLD", "szDecimals": 1, "maxLeverage": 3, "isDelisted": True},
    ]
}
L2 = {
    "coin": "BTC",
    "time": 1789162554557,
    "levels": [
        [{"px": "77312.0", "sz": "0.09677", "n": 5}, {"px": "77311.0", "sz": "0.0326", "n": 3}],
        [{"px": "77313.0", "sz": "0.10", "n": 2}, {"px": "77314.0", "sz": "0.20", "n": 4}],
    ],
}
TRADES = [
    {"coin": "BTC", "side": "A", "px": "77304.0", "sz": "0.00039", "time": 1789162569376},
    {"coin": "BTC", "side": "B", "px": "77305.0", "sz": "0.00014", "time": 1789162569377},
]


def fake_post(payload):
    t = payload["type"]
    if t == "meta":
        return META
    if t == "l2Book":
        return L2
    if t == "recentTrades":
        return TRADES
    raise AssertionError(f"unexpected payload {payload}")


def venue():
    return HyperliquidVenue(post_fn=fake_post)


def test_markets_drops_delisted():
    ms = venue().get_markets()
    names = {m.symbol for m in ms}
    assert names == {"BTC", "ETH"}  # OLD is delisted, excluded
    assert all(isinstance(m, Market) and m.kind == "perp" for m in ms)


def test_symbol_filter():
    ms = HyperliquidVenue(symbols=["BTC"], post_fn=fake_post).get_markets()
    assert [m.symbol for m in ms] == ["BTC"]


def test_book_parse():
    b = venue().get_book("BTC", depth=10)
    assert isinstance(b, Book)
    assert b.bids[0].price == 77312.0 and b.asks[0].price == 77313.0
    assert b.bids[0].price < b.asks[0].price  # not crossed
    assert abs(b.mid - 77312.5) < 1e-6
    assert abs(b.spread - 1.0) < 1e-6
    assert b.ts > 0


def test_book_depth_slice():
    b = venue().get_book("BTC", depth=1)
    assert len(b.bids) == 1 and len(b.asks) == 1


def test_trades_side_mapping():
    ts = venue().get_trades("BTC", limit=10)
    assert all(isinstance(t, Trade) for t in ts)
    assert ts[0].side == "sell"  # "A"
    assert ts[1].side == "buy"   # "B"
    assert ts[0].price == 77304.0
