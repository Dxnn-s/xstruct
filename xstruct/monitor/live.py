"""Live cross-venue scan: Pascal vs Polymarket on the SAME event.

This is the payoff of the whole venue-agnostic design. Pascal publishes the
Polymarket outcome token_id for each of its markets, so the two order books can
be lined up on a real shared event with no guessing about which market is which.

    python -m xstruct.monitor.live
    python -m xstruct.monitor.live --events 5 --fee 0.02
"""
from __future__ import annotations

import argparse
import sys

from ..render.theme import Theme
from ..venue.pascal import PascalVenue
from ..venue.polymarket import PolymarketVenue
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
        flag = d.mid_spread >= 0.02
        val = f"{d.mid_spread:.4f}"
        lines.append(
            "      " + t.muted("dislocation".rjust(11)) + "   "
            + (t.amber(val, bold=True) if flag else t.muted(val))
        )
    if d.arb_edge > 0:
        lines.append("      " + t.muted("arb".rjust(11)) + "   " + t.green(d.arb_desc, bold=True))
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="live Pascal vs Polymarket dislocation scan")
    ap.add_argument("--events", type=int, default=4)
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
        + t.bright("cross-venue") + t.faint("   ·   ") + t.muted("pascal vs polymarket, same event")
    )
    found = scan_live(args.events, args.fee)
    if not found:
        print("\n  " + t.muted("no comparable two-sided books right now"))
        return
    for d in found:
        print(render_live(d, t))
    print()


if __name__ == "__main__":
    main()
