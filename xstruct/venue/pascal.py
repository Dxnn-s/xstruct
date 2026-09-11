"""Pascal read-path adapter (Week 2).

Public data host, no keys (signing is the write path, later). Field shapes verified
live against https://data.pascal.trade/api/v1 on 2026-09-11:
  GET /markets                 -> {"status","data":[{"symbol","taker_fee_rate","maker_rebate_share",
                                     "tick_size_min","display_attributes":{"event_description",
                                     "market_description","expected_resolution_time_ms",
                                     "reference":{"kind","market_slug","condition_id",...}}}]}
  GET /books?symbols=<sym>     -> {"status","data":{"books":{<sym>:{"asks":[[px,sz],...],
                                     "bids":[[px,sz],...]}}},"state_time_ms",...}
                                   asks ascending (best/lowest first), bids descending (best/highest first),
                                   px in [0,1] = implied probability (binary market)
  GET /trades?symbols=<sym>    -> {"status","data":{"items":[...]}}  (was empty at probe time)

Pascal markets carry `reference.condition_id` -> we surface it as Market.event_key so the
cross-venue monitor can line Pascal up against the same event on Polymarket.

The GET function is injectable so tests run fully offline.
"""
from __future__ import annotations

from typing import Callable

from .base import Book, Level, Market, Trade, Venue

BASE_URL = "https://data.pascal.trade/api/v1"


class PascalVenue(Venue):
    name = "pascal"

    def __init__(
        self,
        symbols: list[str] | None = None,
        timeout: float = 8.0,
        get_fn: Callable[[str, dict], object] | None = None,
    ) -> None:
        self._symbols = symbols  # optional client-side filter (API lists all)
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
        data = self._get("/markets", {})
        out: list[Market] = []
        for m in data.get("data", []):
            sym = m.get("symbol")
            if not sym or (self._symbols and sym not in self._symbols):
                continue
            da = m.get("display_attributes", {}) or {}
            ref = da.get("reference", {}) or {}
            event_key = ref.get("condition_id") or ref.get("market_slug") or ""
            desc = da.get("event_description") or da.get("market_description") or ""
            out.append(Market(venue=self.name, symbol=sym, description=desc, kind="binary", event_key=event_key))
        return out

    def get_book(self, symbol: str, depth: int = 10) -> Book:
        data = self._get("/books", {"symbols": symbol})
        books = data.get("data", {}).get("books", {})
        b = books.get(symbol, {})
        bids = [Level(float(px), float(sz)) for px, sz in b.get("bids", [])[:depth]]
        asks = [Level(float(px), float(sz)) for px, sz in b.get("asks", [])[:depth]]
        ts = float(data.get("state_time_ms", 0)) / 1000.0
        return Book(venue=self.name, symbol=symbol, ts=ts, bids=bids, asks=asks)

    def get_trades(self, symbol: str, limit: int = 50) -> list[Trade]:
        # Endpoint verified; item shape not seen populated at probe time -> parse defensively.
        data = self._get("/trades", {"symbols": symbol})
        items = data.get("data", {}).get("items", []) or []
        out: list[Trade] = []
        for t in items[:limit]:
            px = t.get("px", t.get("price"))
            sz = t.get("sz", t.get("size"))
            if px is None or sz is None:
                continue
            side_raw = str(t.get("side", "")).lower()
            side = "buy" if side_raw in ("b", "buy", "bid") else "sell"
            ts = float(t.get("time_ms", t.get("time", 0))) / 1000.0
            out.append(Trade(self.name, symbol, ts, float(px), float(sz), side))
        return out
