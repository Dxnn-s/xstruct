"""Kalshi read-path adapter (Week 2).

Public host, no auth: https://api.elections.kalshi.com/trade-api/v2
Shapes verified live 2026-09-14.

  GET /events?limit=N&status=open        -> {"events":[{"event_ticker","title",...}]}
  GET /markets?event_ticker=<et>         -> {"markets":[{"ticker","title","status",
                                              "yes_bid_dollars","yes_ask_dollars",...}]}
  GET /markets/{ticker}/orderbook?depth=N-> {"orderbook_fp":{"yes_dollars":[[px,sz],...],
                                                             "no_dollars":[[px,sz],...]}}

THE THING THAT MATTERS HERE: Kalshi publishes no ask side. Both entries are BIDS,
one to buy YES and one to buy NO, and both arrive ASCENDING. A NO bid at 0.88 is
economically a YES ask at 1 - 0.88 = 0.12, so the ask book has to be synthesized by
inverting the NO side. Verified against their own reported top of book:

    yes_dollars best (highest) 0.1000  == reported yes_bid 0.1000
    no_dollars  best (highest) 0.8800  -> 1 - 0.88 = 0.1200 == reported yes_ask 0.1200

Take the wire order at face value and every spread, mid and cross-venue dislocation
downstream is quietly wrong.

Prices are already in dollars (0 to 1), so they sit on the same implied-probability
scale as Pascal and Polymarket with no rescaling.

Listing note: the unfiltered /markets feed is dominated by multivariate
"CROSSCATEGORY-SHARD" combination markets with empty books, so discovery goes
through /events with with_nested_markets=true, one request for everything.
"""
from __future__ import annotations

import time
from typing import Callable

from .base import Book, Level, Market, Trade, Venue

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"


class KalshiVenue(Venue):
    name = "kalshi"

    def __init__(
        self,
        tickers: list[str] | None = None,
        events: int = 8,
        timeout: float = 15.0,
        get_fn: Callable[[str, dict], object] | None = None,
    ) -> None:
        self._tickers = tickers          # explicit market tickers win over discovery
        self._events = events            # how many events to walk when discovering
        self._timeout = timeout
        self._get = get_fn or self._http_get
        self._client = None

    def _http_get(self, path: str, params: dict) -> object:
        import httpx

        if self._client is None:
            self._client = httpx.Client(timeout=self._timeout, base_url=BASE_URL)
        r = self._client.get(path, params=params)
        r.raise_for_status()
        return r.json()

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def get_markets(self) -> list[Market]:
        if self._tickers:
            out = []
            for t in self._tickers:
                d = self._get("/markets", {"tickers": t})
                for m in d.get("markets", []):
                    out.append(self._market(m))
            return out

        out: list[Market] = []
        # with_nested_markets returns every market inline, so discovery is ONE request.
        # Walking events and fetching /markets per event was 60+ calls and tripped 429.
        evs = self._get("/events", {"limit": self._events, "status": "open",
                                    "with_nested_markets": "true"})
        for e in evs.get("events", []):
            et = e.get("event_ticker") or ""
            if not et or "CROSSCATEGORY" in et:
                continue
            for m in e.get("markets") or []:
                out.append(self._market(m, et))
        return out

    def _market(self, m: dict, event_ticker: str = "") -> Market:
        return Market(
            venue=self.name,
            symbol=m.get("ticker", ""),
            description=(m.get("title") or "")[:96],
            kind="binary",
            event_key=m.get("event_ticker") or event_ticker,
        )

    def get_book(self, symbol: str, depth: int = 10) -> Book:
        d = self._get(f"/markets/{symbol}/orderbook", {"depth": depth})
        ob = d.get("orderbook_fp") or d.get("orderbook") or {}
        raw_yes = ob.get("yes_dollars") or ob.get("yes") or []
        raw_no = ob.get("no_dollars") or ob.get("no") or []

        # YES bids: taken as-is, then sorted best (highest) first.
        bids = sorted(
            (Level(float(px), float(sz)) for px, sz in raw_yes),
            key=lambda lv: lv.price, reverse=True,
        )[:depth]

        # Asks do not exist on the wire. A NO bid at p is a YES ask at 1 - p.
        asks = sorted(
            (Level(round(1.0 - float(px), 6), float(sz)) for px, sz in raw_no),
            key=lambda lv: lv.price,
        )[:depth]

        # the orderbook payload carries no timestamp, so stamp it at fetch
        return Book(venue=self.name, symbol=symbol, ts=time.time(), bids=bids, asks=asks)

    def get_trades(self, symbol: str, limit: int = 50) -> list[Trade]:
        # Public trade history is not wired here yet. Empty keeps the interface honest.
        return []
