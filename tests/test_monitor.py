"""Offline tests for the cross-venue mispricing monitor, using stub venues with
fixed books so the math is deterministic."""
from xstruct.monitor.mispricing import scan_event
from xstruct.venue.base import Book, Level, Market, Venue


class StubVenue(Venue):
    def __init__(self, name, bid, ask):
        self.name = name
        self._bid, self._ask = bid, ask

    def get_markets(self):
        return [Market(self.name, "EVT")]

    def get_book(self, symbol, depth=10):
        return Book(self.name, symbol, 0.0, [Level(self._bid, 100)], [Level(self._ask, 100)])

    def get_trades(self, symbol, limit=50):
        return []


def test_mid_dislocation():
    a = StubVenue("A", 0.50, 0.52)  # mid 0.51
    b = StubVenue("B", 0.60, 0.62)  # mid 0.61
    d = scan_event("evt", [(a, "EVT"), (b, "EVT")])
    assert abs(d.mid_spread - 0.10) < 1e-9


def test_arb_detected_when_crossed():
    # A's bid (0.60) is above B's ask (0.52): buy B @0.52, sell A @0.60 -> +0.08
    a = StubVenue("A", 0.60, 0.62)
    b = StubVenue("B", 0.50, 0.52)
    d = scan_event("evt", [(a, "EVT"), (b, "EVT")])
    assert abs(d.arb_edge - 0.08) < 1e-9
    assert "buy B" in d.arb_desc and "sell A" in d.arb_desc


def test_no_arb_when_aligned():
    a = StubVenue("A", 0.50, 0.52)
    b = StubVenue("B", 0.51, 0.53)
    d = scan_event("evt", [(a, "EVT"), (b, "EVT")])
    assert d.arb_edge == 0.0


def test_fee_eats_thin_edge():
    a = StubVenue("A", 0.60, 0.62)
    b = StubVenue("B", 0.50, 0.52)  # raw edge 0.08
    d = scan_event("evt", [(a, "EVT"), (b, "EVT")], fee=0.10)  # fee wipes it
    assert d.arb_edge == 0.0


def test_gap_inside_overlapping_quotes_is_not_meaningful():
    # mids differ by 0.02, but the two books overlap: A quotes 0.50-0.60, B 0.52-0.62.
    # nobody has disagreed about anything, the mids just landed apart inside one range.
    a = StubVenue("A", 0.50, 0.60)
    b = StubVenue("B", 0.52, 0.62)
    d = scan_event("evt", [(a, "EVT"), (b, "EVT")])
    assert abs(d.mid_spread - 0.02) < 1e-9
    assert d.noise_floor is not None and d.mid_spread <= d.noise_floor
    assert d.meaningful is False


def test_gap_that_clears_the_quotes_is_meaningful():
    a = StubVenue("A", 0.50, 0.52)  # tight, mid 0.51
    b = StubVenue("B", 0.60, 0.62)  # tight, mid 0.61
    d = scan_event("evt", [(a, "EVT"), (b, "EVT")])
    assert d.meaningful is True
