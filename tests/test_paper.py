from xstruct.venue.base import Book, Market
from xstruct.venue.paper import PaperVenue


def test_markets():
    v = PaperVenue()
    ms = v.get_markets()
    assert len(ms) >= 1
    assert all(isinstance(m, Market) for m in ms)


def test_book_wellformed():
    v = PaperVenue()
    sym = v.get_markets()[0].symbol
    b = v.get_book(sym, depth=10)
    assert isinstance(b, Book)
    assert len(b.bids) == 10 and len(b.asks) == 10
    # no crossed book: best bid strictly below best ask
    assert b.bids[0].price < b.asks[0].price
    # bids descend, asks ascend
    assert all(b.bids[i].price > b.bids[i + 1].price for i in range(len(b.bids) - 1))
    assert all(b.asks[i].price < b.asks[i + 1].price for i in range(len(b.asks) - 1))
    assert 0 < b.mid < 1
    assert b.spread > 0


def test_trades():
    v = PaperVenue()
    sym = v.get_markets()[0].symbol
    ts = v.get_trades(sym, limit=10)
    assert len(ts) >= 1
    assert all(t.side in ("buy", "sell") for t in ts)


def test_store_roundtrip(tmp_path):
    from xstruct.collect.store import TickStore

    v = PaperVenue()
    store = TickStore(str(tmp_path / "t.db"))
    sym = v.get_markets()[0].symbol
    store.record_book(v.get_book(sym))
    store.record_trades(v.get_trades(sym))
    assert store.count("books") == 1
    assert store.count("trades") >= 1
