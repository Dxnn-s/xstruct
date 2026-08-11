"""SQLite tick store — records books + trades for later microstructure analysis.

Deliberately schema-light and dependency-free for Week 1. The report layer
(Week 4) reads from this to compute spread decomposition, depth, fill quality,
and adverse-selection-near-resolution curves.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Iterable


class TickStore:
    def __init__(self, path: str = "xstruct.db") -> None:
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init()

    def _init(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS books (
              id     INTEGER PRIMARY KEY AUTOINCREMENT,
              venue  TEXT, symbol TEXT, ts REAL,
              mid    REAL, spread REAL,
              bids   TEXT, asks TEXT
            );
            CREATE TABLE IF NOT EXISTS trades (
              id     INTEGER PRIMARY KEY AUTOINCREMENT,
              venue  TEXT, symbol TEXT, ts REAL,
              price  REAL, size REAL, side TEXT
            );
            CREATE INDEX IF NOT EXISTS ix_books_sym  ON books(venue, symbol, ts);
            CREATE INDEX IF NOT EXISTS ix_trades_sym ON trades(venue, symbol, ts);
            """
        )
        self.conn.commit()

    def record_book(self, book: object) -> None:
        self.conn.execute(
            "INSERT INTO books(venue,symbol,ts,mid,spread,bids,asks) VALUES(?,?,?,?,?,?,?)",
            (
                book.venue, book.symbol, book.ts, book.mid, book.spread,
                json.dumps([[lv.price, lv.size] for lv in book.bids]),
                json.dumps([[lv.price, lv.size] for lv in book.asks]),
            ),
        )
        self.conn.commit()

    def record_trades(self, trades: Iterable[object]) -> None:
        self.conn.executemany(
            "INSERT INTO trades(venue,symbol,ts,price,size,side) VALUES(?,?,?,?,?,?)",
            [(t.venue, t.symbol, t.ts, t.price, t.size, t.side) for t in trades],
        )
        self.conn.commit()

    def count(self, table: str) -> int:
        if table not in ("books", "trades"):
            raise ValueError(f"unknown table {table!r}")
        return self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
