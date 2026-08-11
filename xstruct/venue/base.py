"""The thin waist: the `Venue` interface + typed models.

Everything venue-specific (auth, endpoints, fee formula, matching semantics) is
isolated behind `Venue`. The engine, collector, report, and monitor depend ONLY
on these types — never on a concrete adapter. Getting this interface right in
Week 1 is what makes every later adapter a plug-in instead of a rewrite.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class Market:
    venue: str
    symbol: str
    description: str = ""
    # "binary" event contract (settles in [0,1]) | "perp" | "clob"
    kind: str = "clob"


@dataclass(frozen=True)
class Level:
    price: float
    size: float


@dataclass(frozen=True)
class Book:
    venue: str
    symbol: str
    ts: float
    bids: Sequence[Level]  # best (highest price) first
    asks: Sequence[Level]  # best (lowest price) first

    @property
    def mid(self) -> float | None:
        if self.bids and self.asks:
            return (self.bids[0].price + self.asks[0].price) / 2
        return None

    @property
    def spread(self) -> float | None:
        if self.bids and self.asks:
            return self.asks[0].price - self.bids[0].price
        return None


@dataclass(frozen=True)
class Trade:
    venue: str
    symbol: str
    ts: float
    price: float
    size: float
    side: str  # aggressor: "buy" | "sell"


class Venue(ABC):
    """One adapter per venue. Read path is live in Week 1; the write path
    (auth/fee/place/cancel) lands with the first real adapter (Week 2) and the
    MM engine (Week 3)."""

    name: str = "base"

    # --- read path (Week 1) ---
    @abstractmethod
    def get_markets(self) -> list[Market]:
        ...

    @abstractmethod
    def get_book(self, symbol: str, depth: int = 10) -> Book:
        ...

    @abstractmethod
    def get_trades(self, symbol: str, limit: int = 50) -> list[Trade]:
        ...

    # --- write path (stubs until the live adapters + engine land) ---
    def fee(self, price: float, size: float, side: str) -> float:
        raise NotImplementedError("fee() lands with the first live adapter (Week 2)")

    def auth(self, request: object) -> object:
        raise NotImplementedError("auth() lands with the first live adapter (Week 2)")

    def place(self, *args: object, **kwargs: object) -> object:
        raise NotImplementedError("place() lands with the MM engine (Week 3)")

    def cancel(self, *args: object, **kwargs: object) -> object:
        raise NotImplementedError("cancel() lands with the MM engine (Week 3)")

    def replace(self, *args: object, **kwargs: object) -> object:
        raise NotImplementedError("replace() lands with the MM engine (Week 3)")
