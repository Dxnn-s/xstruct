"""Hyperliquid read-path adapter (Week 2).

Public `info` endpoint only — no keys, no signing (that's the write path, Week 2b/3).
Field shapes verified live against https://api.hyperliquid.xyz/info on 2026-09-11:
  {"type":"meta"}         -> {"universe":[{"name","szDecimals","maxLeverage",...,"isDelisted"?}]}
  {"type":"l2Book","coin"}-> {"coin","time":<ms>,"levels":[[bids],[asks]]}, level={"px","sz","n"}
  {"type":"recentTrades","coin"} -> [{"coin","side":"A"|"B","px","sz","time":<ms>,...}]  (B=buy, A=sell)

The POST function is injectable so tests run fully offline.
"""
from __future__ import annotations

from typing import Callable

from .base import Book, Level, Market, Trade, Venue

INFO_URL = "https://api.hyperliquid.xyz/info"


class HyperliquidVenue(Venue):
    name = "hyperliquid"

    def __init__(
        self,
        symbols: list[str] | None = None,
        timeout: float = 8.0,
        post_fn: Callable[[dict], object] | None = None,
    ) -> None:
        self._symbols = symbols  # optional filter; None = all listed
        self._timeout = timeout
        self._post = post_fn or self._http_post
        self._client = None  # lazily created httpx.Client

    # --- transport (only imports httpx when actually hitting the network) ---
    def _http_post(self, payload: dict) -> object:
        import httpx

        if self._client is None:
            self._client = httpx.Client(timeout=self._timeout)
        r = self._client.post(INFO_URL, json=payload)
        r.raise_for_status()
        return r.json()

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    # --- read path ---
    def get_markets(self) -> list[Market]:
        data = self._post({"type": "meta"})
        out: list[Market] = []
        for asset in data.get("universe", []):
            if asset.get("isDelisted"):
                continue
            name = asset["name"]
            if self._symbols and name not in self._symbols:
                continue
            out.append(Market(venue=self.name, symbol=name, description=f"Hyperliquid perp {name}", kind="perp"))
        return out

    def get_book(self, symbol: str, depth: int = 10) -> Book:
        data = self._post({"type": "l2Book", "coin": symbol})
        levels = data.get("levels", [[], []])
        raw_bids = levels[0] if len(levels) > 0 else []
        raw_asks = levels[1] if len(levels) > 1 else []
        bids = [Level(float(l["px"]), float(l["sz"])) for l in raw_bids[:depth]]
        asks = [Level(float(l["px"]), float(l["sz"])) for l in raw_asks[:depth]]
        ts = float(data.get("time", 0)) / 1000.0
        return Book(venue=self.name, symbol=symbol, ts=ts, bids=bids, asks=asks)

    def get_trades(self, symbol: str, limit: int = 50) -> list[Trade]:
        data = self._post({"type": "recentTrades", "coin": symbol})
        out: list[Trade] = []
        for t in list(data)[:limit]:
            side = "buy" if t.get("side") == "B" else "sell"
            out.append(
                Trade(
                    venue=self.name,
                    symbol=symbol,
                    ts=float(t.get("time", 0)) / 1000.0,
                    price=float(t["px"]),
                    size=float(t["sz"]),
                    side=side,
                )
            )
        return out
