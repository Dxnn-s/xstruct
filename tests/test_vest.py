"""Offline tests for the Vest adapter. Payloads are trimmed copies of live
responses from server-prod.hz.vestmarkets.com/v2 on 2026-10-15."""
from xstruct.venue.base import Book, Market, Trade
from xstruct.venue.vest import VestVenue

INFO = {
    "symbols": [
        {"symbol": "BTC-PERP", "displayName": "Bitcoin", "asset": "crypto", "tradingStatus": "TRADING"},
        {"symbol": "SMH-USD-PERP", "displayName": "VanEck Semiconductor ETF", "asset": "stock", "tradingStatus": "TRADING"},
        {"symbol": "OLD-PERP", "displayName": "Gone", "asset": "crypto", "tradingStatus": "DELISTED"},
    ]
}
# wire order deliberately scrambled: the adapter must sort, not trust
DEPTH = {
    "bids": [["82261.48", "0.0001"], ["82261.50", "0.0001"], ["82261.49", "0.0001"]],
    "asks": [["82262.68", "0.0001"], ["82262.66", "0.0001"], ["82262.67", "0.0001"]],
    "ts_ms": 1792097124257,
}
TRADES = [
    {"id": "0xdec8", "price": "82316.330000", "qty": "0.0832", "quoteQty": "6848.72", "time": 1792096066114},
    {"id": "0x233d", "price": "82252.340000", "qty": "0.1244", "quoteQty": "10232.19", "time": 1792094840627},
]


def fake_get(path, params):
    if path == "/exchangeInfo":
        return INFO
    if path == "/depth":
        assert params["symbol"] == "BTC-PERP"
        return DEPTH
    if path == "/trades":
        return TRADES
    raise AssertionError(path)


def venue(**kw):
    return VestVenue(get_fn=fake_get, **kw)


def test_markets_keep_only_trading():
    ms = venue().get_markets()
    assert {m.symbol for m in ms} == {"BTC-PERP", "SMH-USD-PERP"}
    assert all(isinstance(m, Market) and m.kind == "perp" for m in ms)


def test_markets_carry_asset_class():
    desc = {m.symbol: m.description for m in venue().get_markets()}
    assert "stock" in desc["SMH-USD-PERP"] and "crypto" in desc["BTC-PERP"]


def test_symbol_filter():
    assert [m.symbol for m in venue(symbols=["BTC-PERP"]).get_markets()] == ["BTC-PERP"]


def test_book_sorted_both_sides_not_crossed():
    b = venue().get_book("BTC-PERP", depth=10)
    assert isinstance(b, Book)
    assert [l.price for l in b.bids] == [82261.50, 82261.49, 82261.48]
    assert [l.price for l in b.asks] == [82262.66, 82262.67, 82262.68]
    assert b.bids[0].price < b.asks[0].price
    assert abs(b.spread - 1.16) < 1e-6
    assert b.ts > 1.7e9


def test_book_depth_slice():
    b = venue().get_book("BTC-PERP", depth=1)
    assert len(b.bids) == 1 and len(b.asks) == 1 and b.bids[0].price == 82261.50


def test_trades_parse_without_side():
    ts = venue().get_trades("BTC-PERP", limit=5)
    assert all(isinstance(t, Trade) for t in ts)
    assert ts[0].price == 82316.33 and ts[0].size == 0.0832
    assert ts[0].side == "unknown"
    assert ts[0].ts > ts[1].ts
