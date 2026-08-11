"""Live board printer — polls a venue, prints the top of book, logs to SQLite.

Week 1 demo entrypoint:  python -m xstruct.cli --iters 20 --sleep 0.5
Swap PaperVenue for a real adapter in Week 2 and the rest is unchanged — that's
the point of the thin waist.
"""
from __future__ import annotations

import argparse
import time

from .collect.store import TickStore
from .venue.base import Book
from .venue.paper import PaperVenue


def render_board(book: Book, top: int = 5) -> str:
    lines = [
        f"  {book.venue}:{book.symbol}   mid={book.mid:.3f}  spread={book.spread:.3f}",
        "        bids                asks",
    ]
    for i in range(min(top, len(book.bids), len(book.asks))):
        b, a = book.bids[i], book.asks[i]
        lines.append(f"   {b.size:7.1f} @ {b.price:.3f}   |   {a.price:.3f} @ {a.size:7.1f}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="xstruct live board (paper adapter)")
    ap.add_argument("--iters", type=int, default=20, help="polling iterations")
    ap.add_argument("--sleep", type=float, default=0.5, help="seconds between polls")
    ap.add_argument("--db", default="xstruct.db", help="sqlite tick store path")
    args = ap.parse_args()

    venue = PaperVenue()
    store = TickStore(args.db)
    markets = venue.get_markets()
    print(f"[xstruct] {venue.name} adapter - {len(markets)} markets, logging to {args.db}\n")

    for _ in range(args.iters):
        for m in markets:
            book = venue.get_book(m.symbol, depth=10)
            trades = venue.get_trades(m.symbol, limit=10)
            store.record_book(book)
            store.record_trades(trades)
            print(render_board(book))
        print(f"  [stored] books={store.count('books')} trades={store.count('trades')}")
        print("-" * 44)
        time.sleep(args.sleep)


if __name__ == "__main__":
    main()
