"""Offline tests for the Pascal adapter — inject a fake GET fn (no network).
Canned payloads mirror the live shapes verified 2026-09-11."""
from xstruct.venue.base import Book, Market
from xstruct.venue.pascal import PascalVenue

MARKETS = {
    "status": "success",
    "data": [
        {
            "symbol": "ACA_HOUSE_2026.NOTEXT_DEM",
            "taker_fee_rate": "0.020000",
            "display_attributes": {
                "event_description": "ACA credits and 2026 House winner",
                "market_description": "Not extended, Democrats",
                "reference": {"kind": "polymarket", "market_slug": "aca-house", "condition_id": "0xb1dd35"},
            },
        }
    ],
}
BOOKS = {
    "status": "success",
    "state_time_ms": "1789163337588",
    "data": {
        "books": {
            "ACA_HOUSE_2026.NOTEXT_DEM": {
                "asks": [["0.870000", "403"], ["0.876000", "527"]],
                "bids": [["0.850000", "231"], ["0.844000", "303"]],
            }
        }
    },
}
TRADES_EMPTY = {"status": "success", "data": {"items": []}}


def fake_get(path, params):
    if path == "/markets":
        return MARKETS
    if path == "/books":
        assert params.get("symbols")
        return BOOKS
    if path == "/trades":
        return TRADES_EMPTY
    raise AssertionError(f"unexpected path {path}")


def venue():
    return PascalVenue(get_fn=fake_get)


def test_markets_and_event_key():
    ms = venue().get_markets()
    assert len(ms) == 1
    m = ms[0]
    assert isinstance(m, Market) and m.kind == "binary"
    assert m.event_key == "0xb1dd35"  # the shared Polymarket condition_id for cross-venue matching


def test_book_parse_probability():
    b = venue().get_book("ACA_HOUSE_2026.NOTEXT_DEM", depth=10)
    assert isinstance(b, Book)
    assert b.bids[0].price == 0.85 and b.asks[0].price == 0.87
    assert b.bids[0].price < b.asks[0].price  # not crossed
    assert 0 < b.mid < 1  # implied probability
    assert abs(b.spread - 0.02) < 1e-9


def test_trades_empty_ok():
    assert venue().get_trades("ACA_HOUSE_2026.NOTEXT_DEM") == []
