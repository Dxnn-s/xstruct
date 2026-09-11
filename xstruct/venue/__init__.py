"""Venue adapters. All venue-specific logic (auth, endpoints, fee math) lives here,
behind the `Venue` interface, so the engine and analytics never import a venue.

Concrete adapters import httpx lazily (inside the network call), so importing this
package stays dependency-free until you actually hit a live venue."""

from .base import Book, Level, Market, Trade, Venue
from .hyperliquid import HyperliquidVenue
from .pascal import PascalVenue
from .paper import PaperVenue

__all__ = [
    "Venue",
    "Market",
    "Book",
    "Level",
    "Trade",
    "PaperVenue",
    "HyperliquidVenue",
    "PascalVenue",
]
