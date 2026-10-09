# xstruct

![tests](https://github.com/Dxnn-s/xstruct/actions/workflows/tests.yml/badge.svg)

**A venue-agnostic market-making and microstructure toolkit for prediction markets and derivatives order books.**

Every venue publishes its book in a different shape. xstruct puts them behind one interface, so the same
analysis and the same strategy code run against any of them without caring whose API is underneath.

![live board](assets/board-demo.gif)

The depth ladder, polling Hyperliquid. Bid and ask bars share one scale, so a lopsided
book looks lopsided.

![cross-venue dislocation](assets/cross-venue-dislocation.png)

Two venues listing the same event, and the gap between them. Pascal republishes the Polymarket
`condition_id`, so the books line up on a known key instead of fuzzy-matching market names.

```bash
pip install -r requirements.txt
python -m xstruct.monitor.live               # Pascal vs Polymarket, exact key join
python -m xstruct.monitor.live --pair kalshi # Kalshi vs Polymarket, IDF title match
python -m xstruct.cli --venue pascal    # live depth-ladder board
```

## What it does today

**Five venues behind one `Venue` interface** — Hyperliquid (perps), Pascal, Polymarket, Kalshi, and a synthetic
paper adapter so everything runs offline for demos and CI. Adding a venue is one file, not a refactor.

**A live cross-venue monitor.** Pascal publishes the Polymarket `condition_id` and outcome `token_id` for
each of its markets, so the two books join on a known key instead of fuzzy-matching market names. A real
run on the ACA House 2026 market:

```
  Not extended, Democrats
           pascal   bid 0.8440   ask 0.8700   mid 0.8570
       polymarket   bid 0.8500   ask 0.8700   mid 0.8600
      dislocation   0.0030
```

It reports the mid dislocation across venues and flags any locked cross-venue edge (a best bid above
another venue's best ask, net of fees).

**A terminal depth ladder**, with size bars, tick-aware price precision, and an ASCII fallback for
consoles that cannot encode block glyphs.

**A SQLite tick store** recording books and trades for later microstructure work, and a chart renderer
that turns a recorded pair into a shareable dislocation figure.

## One thing worth knowing if you build venue adapters

Polymarket returns asks **descending**, so the first element on the wire is the *worst* ask, not the best.
Trusting wire order gives you a best ask of 0.99 instead of the real one, and silently poisons every
spread, mid and arbitrage check downstream. xstruct sorts both sides itself rather than trusting order.
Pascal returns bids descending and asks ascending. Hyperliquid nests both under `levels: [bids, asks]`.

## Known limits, stated plainly

- **Transport is REST polling.** No WebSocket, no snapshot-plus-delta book maintenance. Fine for
  microstructure sampling and cross-venue comparison, not a low-latency path.
- **Read path only.** No signing, no order placement, no market-making engine yet.
- Adapters today are Hyperliquid, Pascal, Polymarket, Kalshi and paper.

## Layout

```
xstruct/
  venue/      one adapter per venue, all behind the Venue interface
  collect/    SQLite tick store
  monitor/    cross-venue mispricing scan
  render/     terminal board
  report/     charts
```

## Tests

```bash
pytest -q     # 48 tests, all offline (network calls are injectable)
```

## Comparing the IDF matcher against turbopuffer BM25

The Kalshi pair above matches titles with a hand-rolled IDF-weighted overlap. `tools/turbopuffer_match.py`
asks whether a BM25 full-text index on [turbopuffer](https://turbopuffer.com) finds the same counterparts.
It writes the Polymarket titles into a namespace with `full_text_search` on `title`, runs one BM25 query per
Kalshi title, keeps the top hit above a threshold, and scores precision and recall at top-1 against
`tests/fixtures/title_pairs.json`: 57 hand-labeled Kalshi titles (30 with a Polymarket counterpart, 27 without,
3 more marked uncertain and excluded) built from live listings on 2026-10-09. The Israel Katz trap from
`match.py`'s docstring is in there, labeled as having no counterpart. Both matchers see the same corpus and the
same labels.

```bash
python tools/turbopuffer_match.py                 # offline: fixture titles, in-memory BM25 fake, no key needed
pip install turbopuffer                           # or: pip install -e ".[turbopuffer]"
export TURBOPUFFER_API_KEY=...                    # Launch plan, $16 a month minimum, no free tier
python tools/turbopuffer_match.py --live          # real turbopuffer, same fixture corpus and labels
python tools/turbopuffer_match.py --live --pull   # re-pull titles; labels missing from the new corpus are dropped
```

The offline fake implements write and a Lucene-style BM25 with turbopuffer's defaults (k1 1.2, b 0.75, k3 8)
so the tests and the table run without a key. Its tokenizer is a plain lowercase split, not `word_v4`, so
offline numbers are a rehearsal. Fill this table from a `--live` run:

| method | threshold | predicted | correct | precision | recall |
|---|---|---|---|---|---|
| `match()` IDF overlap | 0.75 | TBD | TBD | TBD | TBD |
| turbopuffer BM25 top-1, threshold tuned on the set | TBD | TBD | TBD | TBD | TBD |
| turbopuffer BM25 top-1, no threshold | 0 | TBD | TBD | TBD | TBD |

This measures match quality on a few hundred titles. It is not a benchmark of turbopuffer's latency or
throughput. The BM25 threshold is chosen on the same labeled set, so that row is BM25's best case.

Two things worth knowing before you run it. turbopuffer ids are u64, UUID, or strings up to 64 bytes, and a
Polymarket CLOB token id is a 77-digit decimal string, so the script keys rows by list index and carries the
token id as an attribute. And a Kalshi title can repeat its one informative word (`Will Israel Katz be the next
Prime Minister of Israel?`), which BM25's query-term weighting (`k3`) rewards, so the wrong-country failure that
motivated `match.py` is a real test of the threshold, not a freebie.

## Roadmap

Signed write paths (Pascal Ed25519, Hyperliquid SDK), then the market-making engine with inventory skew
and a resolution-proximity kill, then more adapters.

## License

MIT
