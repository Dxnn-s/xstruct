"""Live board printer - polls a venue, prints the top of book, logs to SQLite.

  python -m xstruct.cli                        # paper adapter (offline, zero deps)
  python -m xstruct.cli --venue hyperliquid    # live Hyperliquid book (needs httpx)
  python -m xstruct.cli --venue hyperliquid --symbols BTC,ETH --iters 3

Because everything venue-specific lives behind the Venue interface, swapping the
adapter is the only change - the loop below never knows which venue it's polling.
"""
from __future__ import annotations

import argparse
import time

from .collect.store import TickStore
from .venue.base import Book, Venue


def make_venue(name: str, symbols: list[str] | None) -> Venue:
    if name == "paper":
        from .venue.paper import PaperVenue

        return PaperVenue()
    if name == "hyperliquid":
        from .venue.hyperliquid import HyperliquidVenue

        return HyperliquidVenue(symbols=symbols or ["BTC", "ETH", "SOL"])
    raise SystemExit(f"unknown venue: {name!r} (choices: paper, hyperliquid)")


def render_board(book: Book, top: int = 5) -> str:
    mid = book.mid if book.mid is not None else float("nan")
    spread = book.spread if book.spread is not None else float("nan")
    lines = [
        f"  {book.venue}:{book.symbol}   mid={mid:.4g}  spread={spread:.4g}",
        "        bids                   asks",
    ]
    for i in range(min(top, len(book.bids), len(book.asks))):
        b, a = book.bids[i], book.asks[i]
        lines.append(f"   {b.size:10.4g} @ {b.price:<10.6g} |  {a.price:<10.6g} @ {a.size:10.4g}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="xstruct live board")
    ap.add_argument("--venue", default="paper", help="paper | hyperliquid")
    ap.add_argument("--symbols", default=None, help="comma-separated symbol filter (e.g. BTC,ETH)")
    ap.add_argument("--iters", type=int, default=20, help="polling iterations")
    ap.add_argument("--sleep", type=float, default=0.5, help="seconds between polls")
    ap.add_argument("--depth", type=int, default=10, help="book depth to fetch")
    ap.add_argument("--db", default="xstruct.db", help="sqlite tick store path")
    args = ap.parse_args()

    symbols = [s.strip() for s in args.symbols.split(",")] if args.symbols else None
    venue = make_venue(args.venue, symbols)
    store = TickStore(args.db)
    markets = venue.get_markets()
    print(f"[xstruct] {venue.name} adapter - {len(markets)} markets, logging to {args.db}\n")

    for _ in range(args.iters):
        for m in markets:
            book = venue.get_book(m.symbol, depth=args.depth)
            trades = venue.get_trades(m.symbol, limit=10)
            store.record_book(book)
            store.record_trades(trades)
            print(render_board(book))
        print(f"  [stored] books={store.count('books')} trades={store.count('trades')}")
        print("-" * 48)
        time.sleep(args.sleep)


if __name__ == "__main__":
    main()
