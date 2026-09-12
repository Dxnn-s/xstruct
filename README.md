# xstruct

**Venue-agnostic market-making engine + microstructure-analytics lab for prediction-market & derivatives CLOBs.**

One build, many doors. Because Hyperliquid, Pascal, Kalshi, XO Market, and Ondo Perps all expose central-limit order books for event/derivatives contracts, a venue-agnostic MM + microstructure tool is the *union of their APIs*. Same engine, swappable adapters. It doubles as a self-study vehicle and a proof-of-work wedge at ~8 target startups (incl. River Markets / Valence / Kairos, whose product this literally is).

> Full design + build plan: `projects/startup-hunt/wedge-artifact-spec.md` in the Brain vault.

## Status — Week 1 (the thin waist)
Shipped:
- `xstruct/venue/base.py` — the `Venue` interface + typed models (`Market`, `Book`, `Level`, `Trade`). **All venue differences (auth, endpoints, fee math) live behind this interface** — that's the whole trick.
- `xstruct/venue/paper.py` — a `PaperVenue` synthetic adapter so the whole thing runs offline (demos + CI).
- `xstruct/collect/store.py` — SQLite tick/book/trade store.
- `xstruct/cli.py` — a live board printer that polls a venue and logs to SQLite.

Zero dependencies — stdlib only. Runs today:
```bash
python -m xstruct.cli --iters 20 --sleep 0.5
pytest -q            # (pip install pytest)
```

## Known limits (stated plainly)
- **Transport is REST polling.** No WebSocket, no snapshot-plus-delta book maintenance yet. Fine for
  microstructure sampling and cross-venue comparison; not a low-latency path.
- **Read path only.** Signing, order placement, and the market-making engine are not in yet.
- Adapters today: Hyperliquid, Pascal, Polymarket, paper. No Kalshi yet.

## Roadmap (from the spec)
- **Week 2** — real signed adapters: Pascal (Ed25519 dual-key, verify byte-exact vs quickstart test vectors) + Hyperliquid (official SDK, testnet). First live read + first live order.
- **Week 3** — the MM engine: two-sided quoting, inventory skew, resolution-proximity/adverse-selection kill, hard risk gate + kill-switch.
- **Week 4** — microstructure report + cross-venue mispricing monitor → **ship v1** (the <60s demo).
- **Weeks 5-8** — widen doors: Kalshi, XO vault MM, Ondo Perps collateral-health, HyperEVM CoreWriter demo (Foundry).

## Safety spine
Testnet/paper first · byte-exact signing verified against vendor test vectors before any live order · hard position/loss caps + kill-switch · never commit keys · repo lives **outside** any cloud-synced dir.
