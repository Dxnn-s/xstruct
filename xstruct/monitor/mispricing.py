"""Cross-venue mispricing monitor.

Point several venue listings that refer to the SAME underlying event at this, and it
surfaces (a) how far their mids disagree and (b) any locked cross-venue edge (a best
bid on one venue above a best ask on another, past fees).

Venue-agnostic by construction: it only touches the `Venue` interface, so paper,
Hyperliquid, and Pascal all plug in identically. For binary/prediction markets the
mid is the implied probability, which is what makes cross-venue comparison meaningful.

Run the offline demo:  python -m xstruct.monitor.mispricing
"""
from __future__ import annotations

from dataclasses import dataclass

from ..venue.base import Venue


@dataclass
class VenueQuote:
    venue: str
    symbol: str
    bid: float | None
    ask: float | None
    mid: float | None


@dataclass
class Dislocation:
    label: str
    quotes: list[VenueQuote]
    mid_spread: float | None  # max mid - min mid across venues
    arb_edge: float           # best locked cross-venue edge (<= 0 means none)
    arb_desc: str
    # A mid gap only means the venues disagree if it clears the quotes themselves.
    # Two books whose bid-ask ranges overlap have not disagreed about anything; their
    # mids just landed in different places inside the same range. On thin markets that
    # is most of them, so reporting the raw gap there is reporting noise.
    noise_floor: float | None = None   # sum of the half-spreads
    meaningful: bool = False           # mid gap exceeds the floor


def _quote(venue: Venue, symbol: str) -> VenueQuote:
    b = venue.get_book(symbol, depth=1)
    bid = b.bids[0].price if b.bids else None
    ask = b.asks[0].price if b.asks else None
    return VenueQuote(venue.name, symbol, bid, ask, b.mid)


def scan_event(label: str, listings: list[tuple[Venue, str]], fee: float = 0.0) -> Dislocation:
    """`listings` = [(venue, symbol), ...] all referring to the same underlying event."""
    quotes = [_quote(v, s) for v, s in listings]
    mids = [q.mid for q in quotes if q.mid is not None]
    mid_spread = (max(mids) - min(mids)) if len(mids) >= 2 else None

    half_spreads = [
        (q.ask - q.bid) / 2 for q in quotes
        if q.ask is not None and q.bid is not None
    ]
    noise_floor = sum(sorted(half_spreads, reverse=True)[:2]) if len(half_spreads) >= 2 else None
    meaningful = bool(
        mid_spread is not None and noise_floor is not None and mid_spread > noise_floor
    )

    best_edge = 0.0
    best_desc = "none"
    for a in quotes:
        for b in quotes:
            if a is b or a.bid is None or b.ask is None:
                continue
            edge = a.bid - b.ask - fee  # sell on a's bid, buy on b's ask
            if edge > best_edge:
                best_edge = edge
                best_desc = f"buy {b.venue}@{b.ask:.4g} / sell {a.venue}@{a.bid:.4g} -> +{edge:.4g}"
    return Dislocation(label, quotes, mid_spread, best_edge, best_desc, noise_floor, meaningful)


def render(d: Dislocation) -> str:
    lines = [f"[{d.label}]"]
    for q in d.quotes:
        mid = f"{q.mid:.4g}" if q.mid is not None else "n/a"
        bid = f"{q.bid:.4g}" if q.bid is not None else "n/a"
        ask = f"{q.ask:.4g}" if q.ask is not None else "n/a"
        lines.append(f"   {q.venue:>12}:{q.symbol:<28} bid={bid:<8} ask={ask:<8} mid={mid}")
    spread = f"{d.mid_spread:.4g}" if d.mid_spread is not None else "n/a"
    if d.noise_floor is not None and d.mid_spread is not None:
        verdict = "real" if d.meaningful else f"inside the spread, ignore (floor {d.noise_floor:.4g})"
        lines.append(f"   mid dislocation: {spread}  [{verdict}]")
    else:
        lines.append(f"   mid dislocation: {spread}")
    lines.append(f"   arb: {d.arb_desc}" if d.arb_edge > 0 else "   arb: none")
    return "\n".join(lines)


def _demo() -> None:
    # Offline demo: two paper venues (different seeds) standing in for two exchanges
    # listing the same event. Swap in PascalVenue + a Polymarket adapter for the live version.
    from ..venue.paper import PaperVenue

    a = PaperVenue(seed=1)
    b = PaperVenue(seed=2)
    sym = a.get_markets()[0].symbol
    d = scan_event(f"same event: {sym}", [(a, sym), (b, sym)], fee=0.0)
    print(render(d))
    print("\n(swap the two paper venues for Pascal + Polymarket to run this live;")
    print(" Pascal already exposes the shared Polymarket condition_id via Market.event_key.)")


if __name__ == "__main__":
    _demo()
