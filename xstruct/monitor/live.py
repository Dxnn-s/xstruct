"""Live cross-venue scan on the SAME event.

Two pairs, joined two different ways:

  pascal    Pascal republishes the Polymarket outcome token_id per market, so the
            books join on an exact key. No guessing.
  kalshi    Kalshi publishes nothing that maps to Polymarket, so titles are matched
            by IDF-weighted overlap (see match.py for why plain overlap fails).

    python -m xstruct.monitor.live
    python -m xstruct.monitor.live --pair kalshi --events 60
"""
from __future__ import annotations

import argparse
import sys

from ..render.theme import Theme
from ..venue.kalshi import KalshiVenue
from ..venue.pascal import PascalVenue
from ..venue.polymarket import PolymarketVenue
from .match import match
from .mispricing import Dislocation, scan_event


def scan_live(max_events: int = 4, fee: float = 0.0) -> list[Dislocation]:
    pascal = PascalVenue()
    refs = pascal.polymarket_refs()
    poly = PolymarketVenue(tokens={r["symbol"]: r["token_id"] for r in refs})

    out: list[Dislocation] = []
    for r in refs:
        if len(out) >= max_events:
            break
        try:
            d = scan_event(
                r["description"][:58] or r["symbol"],
                [(pascal, r["symbol"]), (poly, r["token_id"])],
                fee=fee,
            )
        except Exception:
            continue  # a venue can be missing a book for a given event
        if any(q.mid is not None for q in d.quotes):
            out.append(d)
    pascal.close()
    poly.close()
    return out


def _polymarket_titles(limit: int = 500) -> list[tuple[str, str]]:
    """(outcome token_id, question) for active Polymarket markets, by volume."""
    import json

    import httpx

    out: list[tuple[str, str]] = []
    with httpx.Client(timeout=20.0, headers={"User-Agent": "xstruct/0.1"}) as c:
        for offset in range(0, limit, 100):
            r = c.get(
                "https://gamma-api.polymarket.com/markets",
                params={"active": "true", "closed": "false", "limit": 100,
                        "offset": offset, "order": "volumeNum", "ascending": "false"},
            )
            r.raise_for_status()
            batch = r.json()
            if not batch:
                break
            for m in batch:
                toks = m.get("clobTokenIds")
                if toks and m.get("question"):
                    out.append((json.loads(toks)[0], m["question"]))
    return out


def scan_kalshi_polymarket(max_pairs: int = 5, events: int = 60, fee: float = 0.0) -> list[Dislocation]:
    kal = KalshiVenue(events=events)
    kmarkets = kal.get_markets()
    pairs = match([(m.symbol, m.description) for m in kmarkets], _polymarket_titles())
    poly = PolymarketVenue(tokens={tok: tok for _, _, tok, _ in pairs[:max_pairs]})
    labels = {m.symbol: m.description for m in kmarkets}

    out: list[Dislocation] = []
    for _score, kt, tok, _shared in pairs[:max_pairs]:
        try:
            out.append(scan_event(labels[kt][:58], [(kal, kt), (poly, tok)], fee=fee))
        except Exception:
            continue
    kal.close()
    poly.close()
    return out


def render_live(d: Dislocation, t: Theme) -> str:
    lines = ["", "  " + t.bright(d.label, bold=True)]
    for q in d.quotes:
        mid = f"{q.mid:.4f}" if q.mid is not None else "n/a"
        bid = f"{q.bid:.4f}" if q.bid is not None else "n/a"
        ask = f"{q.ask:.4f}" if q.ask is not None else "n/a"
        lines.append(
            "      " + t.muted(q.venue.rjust(11)) + "   "
            + t.muted("bid ") + t.ink(bid) + "   "
            + t.muted("ask ") + t.ink(ask) + "   "
            + t.muted("mid ") + t.cyan(mid, bold=True)
        )
    if d.mid_spread is not None:
        val = f"{d.mid_spread:.4f}"
        verdict = "" if d.meaningful else t.faint("  inside the spread")
        lines.append(
            "      " + t.muted("dislocation".rjust(11)) + "   "
            + (t.amber(val, bold=True) if d.meaningful else t.muted(val)) + verdict
        )
    if d.arb_edge > 0:
        lines.append("      " + t.muted("arb".rjust(11)) + "   " + t.green(d.arb_desc, bold=True))
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="live cross-venue dislocation scan")
    ap.add_argument("--pair", choices=["pascal", "kalshi"], default="pascal",
                    help="pascal: exact key join. kalshi: IDF title match.")
    ap.add_argument("--events", type=int, default=4,
                    help="pascal: max events to scan. kalshi: events to walk for discovery.")
    ap.add_argument("--fee", type=float, default=0.0, help="round-trip fee to net off the arb check")
    ap.add_argument("--no-color", action="store_true")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    t = Theme(enabled=False if args.no_color else None)
    print(
        "\n  " + t.amber("xstruct", bold=True) + t.faint(f"  {t.g.arrow}  ")
        + t.bright("cross-venue") + t.faint("   ·   ") + t.muted(f"{args.pair} vs polymarket, same event")
    )
    if args.pair == "kalshi":
        found = scan_kalshi_polymarket(events=max(args.events, 20), fee=args.fee)
    else:
        found = scan_live(args.events, args.fee)
    if not found:
        print("\n  " + t.muted("no comparable two-sided books right now"))
        return
    for d in found:
        print(render_live(d, t))
    print()


if __name__ == "__main__":
    main()
