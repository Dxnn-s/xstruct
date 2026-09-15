"""Offline tests for the Kalshi adapter.

The one that matters is the YES/NO inversion. Kalshi publishes no ask side: both
books are bids, one to buy YES and one to buy NO, both ascending. A NO bid at p is
a YES ask at 1 - p. The canned numbers below are real, pulled live 2026-09-14 from
KXELONMARS-99, where Kalshi itself reported yes_bid 0.1000 and yes_ask 0.1200.
"""
from xstruct.venue.base import Book, Market
from xstruct.venue.kalshi import KalshiVenue

BOOK = {
    "orderbook_fp": {
        # both sides ascending on the wire, both are BIDS
        "yes_dollars": [["0.0700", "2195.84"], ["0.0800", "1253.00"],
                        ["0.0900", "735.07"], ["0.1000", "162.35"]],
        "no_dollars": [["0.8500", "1050.00"], ["0.8600", "10.00"],
                       ["0.8700", "1799.44"], ["0.8800", "265.22"]],
    }
}
EVENTS = {"events": [{"event_ticker": "KXELONMARS-99", "title": "Will Elon Musk visit Mars?",
                      "markets": [{"ticker": "KXELONMARS-99", "event_ticker": "KXELONMARS-99",
                                   "title": "Will Elon Musk visit Mars before Aug 1, 2099?",
                                   "status": "active"}]}]}
MARKETS = {"markets": [{"ticker": "KXELONMARS-99", "event_ticker": "KXELONMARS-99",
                        "title": "Will Elon Musk visit Mars before Aug 1, 2099?",
                        "status": "active", "yes_bid_dollars": "0.1000",
                        "yes_ask_dollars": "0.1200"}]}


def fake_get(path, params):
    if path == "/events":
        return EVENTS
    if path == "/markets":
        return MARKETS
    if path.endswith("/orderbook"):
        return BOOK
    raise AssertionError(path)


def venue():
    return KalshiVenue(get_fn=fake_get)


def test_ask_is_synthesized_from_the_no_book():
    b = venue().get_book("KXELONMARS-99", depth=10)
    # best NO bid 0.88 -> best YES ask 0.12, which is what Kalshi itself reports
    assert b.asks[0].price == 0.12
    # best YES bid is the HIGHEST yes level, not the first one on the wire
    assert b.bids[0].price == 0.10
    assert b.bids[0].price < b.asks[0].price


def test_sides_are_monotonic_after_conversion():
    b = venue().get_book("KXELONMARS-99", depth=10)
    assert all(b.bids[i].price > b.bids[i + 1].price for i in range(len(b.bids) - 1))
    assert all(b.asks[i].price < b.asks[i + 1].price for i in range(len(b.asks) - 1))


def test_mid_and_spread_match_the_venues_own_quote():
    b = venue().get_book("KXELONMARS-99")
    assert abs(b.mid - 0.11) < 1e-9
    assert abs(b.spread - 0.02) < 1e-9
    assert b.ts > 0  # stamped at fetch; the payload has no timestamp of its own


def test_sizes_survive_the_inversion():
    b = venue().get_book("KXELONMARS-99", depth=10)
    # inverting price must not reorder size onto the wrong level
    assert b.asks[0].size == 265.22   # the 0.88 NO level
    assert b.bids[0].size == 162.35   # the 0.10 YES level


def test_prices_stay_on_the_probability_scale():
    b = venue().get_book("KXELONMARS-99", depth=10)
    assert all(0.0 < lv.price < 1.0 for lv in list(b.bids) + list(b.asks))


def test_discovery_goes_through_events():
    ms = venue().get_markets()
    assert len(ms) == 1 and isinstance(ms[0], Market)
    assert ms[0].symbol == "KXELONMARS-99" and ms[0].kind == "binary"


def test_trades_empty_is_honest():
    assert venue().get_trades("KXELONMARS-99") == []
