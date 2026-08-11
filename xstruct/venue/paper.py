"""PaperVenue — a synthetic, zero-dependency adapter.

Generates random-walk binary-event markets with a well-formed order book and a
trade tape, so the whole stack (collector, engine, report, monitor) runs offline
for demos and CI before any real API keys exist. Seeded for reproducibility.
"""
from __future__ import annotations

import random
import time

from .base import Book, Level, Market, Trade, Venue


class PaperVenue(Venue):
    name = "paper"

    def __init__(self, symbols: list[str] | None = None, seed: int = 7) -> None:
        self._rng = random.Random(seed)
        self._symbols = symbols or ["ELECTION-2028-DEM", "FED-CUT-DEC", "BTC-100K-EOY"]
        self._mids = {s: self._rng.uniform(0.3, 0.7) for s in self._symbols}

    def get_markets(self) -> list[Market]:
        return [
            Market(venue=self.name, symbol=s, description=f"Synthetic paper market {s}", kind="binary")
            for s in self._symbols
        ]

    def _step(self, symbol: str) -> float:
        mid = self._mids[symbol] + self._rng.gauss(0, 0.005)
        mid = min(0.95, max(0.05, mid))  # keep off the [0,1] rails
        self._mids[symbol] = mid
        return mid

    def get_book(self, symbol: str, depth: int = 10) -> Book:
        mid = self._step(symbol)
        tick, half = 0.01, 0.005
        bids: list[Level] = []
        asks: list[Level] = []
        for i in range(depth):
            bp = round(mid - half - i * tick, 4)
            ap = round(mid + half + i * tick, 4)
            bids.append(Level(bp, round(self._rng.uniform(50, 500), 1)))
            asks.append(Level(ap, round(self._rng.uniform(50, 500), 1)))
        return Book(venue=self.name, symbol=symbol, ts=time.time(), bids=bids, asks=asks)

    def get_trades(self, symbol: str, limit: int = 50) -> list[Trade]:
        mid = self._mids[symbol]
        now = time.time()
        out: list[Trade] = []
        for i in range(min(limit, 10)):
            side = "buy" if self._rng.random() > 0.5 else "sell"
            px = round(min(0.99, max(0.01, mid + self._rng.gauss(0, 0.008))), 4)
            out.append(Trade(self.name, symbol, now - i, px, round(self._rng.uniform(10, 200), 1), side))
        return out
