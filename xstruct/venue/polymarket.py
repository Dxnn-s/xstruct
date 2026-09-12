"""Polymarket read-path adapter (Week 2).

Public CLOB endpoints, no keys. Shapes verified live against
https://clob.polymarket.com on 2026-09-11:
  GET /book?token_id=<id> -> {"market":<condition_id>,"asset_id":<token_id>,
                              "timestamp":"<ms>","bids":[{"price","size"},...],
                              "asks":[...]}
  GET /midpoint?token_id=<id> -> {"mid":"0.86"}

Ordering note: the API does NOT return levels best-first (bids came back
ascending), so we sort both sides ourselves rather than trusting the wire order.

A Polymarket "symbol" here is the outcome token_id. That is deliberate: Pascal
hands us `reference.market_outcome_token_id` for the same event, so the two
venues join on a value we already have.
"""
from __future__ import annotations

from typing import Callable

from .base import Book, Level, Market, Trade, Venue

BASE_URL = "https://clob.polymarket.com"


class PolymarketVenue(Venue):
    name = "polymarket"

    def __init__(
        self,
        tokens: dict[str, str] | None = None,
        timeout: float = 10.0,
        get_fn: Callable[[str, dict], object] | None = None,
    ) -> None:
        # tokens maps a human label -> outcome token_id (label is cosmetic)
        self._tokens = tokens or {}
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
        return [
            Market(venue=self.name, symbol=tok, description=label, kind="binary", event_key=tok)
            for label, tok in self._tokens.items()
        ]

    def get_book(self, symbol: str, depth: int = 10) -> Book:
        data = self._get("/book", {"token_id": symbol})
        raw_bids = data.get("bids", []) or []
        raw_asks = data.get("asks", []) or []
        # sort ourselves: best bid = highest, best ask = lowest
        bids = sorted((Level(float(l["price"]), float(l["size"])) for l in raw_bids),
                      key=lambda lv: lv.price, reverse=True)[:depth]
        asks = sorted((Level(float(l["price"]), float(l["size"])) for l in raw_asks),
                      key=lambda lv: lv.price)[:depth]
        ts = float(data.get("timestamp", 0)) / 1000.0
        return Book(venue=self.name, symbol=symbol, ts=ts, bids=bids, asks=asks)

    def get_trades(self, symbol: str, limit: int = 50) -> list[Trade]:
        # Public trade history lives behind the data API / auth; the read path here
        # is book-only. Returning empty keeps the interface honest.
        return []

    def midpoint(self, symbol: str) -> float | None:
        data = self._get("/midpoint", {"token_id": symbol})
        mid = data.get("mid")
        return float(mid) if mid is not None else None
