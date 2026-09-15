"""Live board - polls a venue, renders the depth ladder, logs to SQLite.

  python -m xstruct.cli                        # paper adapter (offline, zero deps)
  python -m xstruct.cli --venue hyperliquid    # live Hyperliquid perp books
  python -m xstruct.cli --venue pascal         # live Pascal prediction markets

Because everything venue-specific lives behind the Venue interface, swapping the
adapter is the only change - the loop below never knows which venue it's polling.
"""
from __future__ import annotations

import argparse
import sys
import time

from .collect.store import TickStore
from .render.board import render_board, render_header, render_rule
from .render.theme import Theme
from .venue.base import Venue


def make_venue(name: str, symbols: list[str] | None) -> Venue:
    if name == "paper":
        from .venue.paper import PaperVenue

        return PaperVenue()
    if name == "hyperliquid":
        from .venue.hyperliquid import HyperliquidVenue

        return HyperliquidVenue(symbols=symbols or ["BTC", "ETH", "SOL"])
    if name == "kalshi":
        from .venue.kalshi import KalshiVenue

        return KalshiVenue(tickers=symbols)
    if name == "polymarket":
        from .venue.polymarket import PolymarketVenue

        # symbols are outcome token ids here; Pascal republishes them per market
        return PolymarketVenue(tokens={t: t for t in (symbols or [])})
    if name == "pascal":
        from .venue.pascal import PascalVenue

        return PascalVenue(symbols=symbols)  # None = all listed markets
    raise SystemExit(f"unknown venue: {name!r} (choices: paper, hyperliquid, pascal, polymarket, kalshi)")


def main() -> None:
    ap = argparse.ArgumentParser(description="xstruct live board")
    ap.add_argument("--venue", default="paper", help="paper | hyperliquid | pascal | polymarket | kalshi")
    ap.add_argument("--symbols", default=None, help="comma-separated symbol filter (e.g. BTC,ETH)")
    ap.add_argument("--iters", type=int, default=20, help="polling iterations")
    ap.add_argument("--sleep", type=float, default=0.5, help="seconds between polls")
    ap.add_argument("--depth", type=int, default=10, help="book depth to fetch")
    ap.add_argument("--rows", type=int, default=5, help="ladder rows to draw")
    ap.add_argument("--max-markets", type=int, default=4, help="cap markets on the board")
    ap.add_argument("--db", default="xstruct.db", help="sqlite tick store path")
    ap.add_argument("--no-color", action="store_true", help="disable ANSI color")
    args = ap.parse_args()

    # Windows consoles default to cp1252; the ladder needs UTF-8 (falls back to ASCII glyphs).
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    theme = Theme(enabled=False if args.no_color else None)
    symbols = [s.strip() for s in args.symbols.split(",")] if args.symbols else None
    venue = make_venue(args.venue, symbols)
    store = TickStore(args.db)
    markets = venue.get_markets()[: args.max_markets]

    for _ in range(args.iters):
        print(render_header(venue.name, len(markets), theme))
        for m in markets:
            book = venue.get_book(m.symbol, depth=args.depth)
            trades = venue.get_trades(m.symbol, limit=10)
            store.record_book(book)
            store.record_trades(trades)
            print(render_board(book, market=m, theme=theme, top=args.rows))
        print()
        print(render_rule(theme=theme))
        print(
            "  "
            + theme.muted("stored ")
            + theme.cyan(f"{store.count('books')}")
            + theme.muted(" books  ")
            + theme.cyan(f"{store.count('trades')}")
            + theme.muted(" trades")
        )
        time.sleep(args.sleep)


if __name__ == "__main__":
    main()
