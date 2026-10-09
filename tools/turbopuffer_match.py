"""Compare xstruct's IDF title matcher against turbopuffer BM25 on one labeled set.

Kalshi and Polymarket share no market id, so the cross-venue monitor matches events
by title with an IDF-weighted word overlap (xstruct/monitor/match.py). This script
asks a narrower question: does a BM25 full-text index on turbopuffer find the same
counterparts, and at what precision and recall, on a hand-labeled set of Kalshi
titles? Both methods see the same Polymarket corpus and the same labels.

    python tools/turbopuffer_match.py                # offline: fixture titles, in-memory BM25 fake
    python tools/turbopuffer_match.py --live         # real turbopuffer, needs TURBOPUFFER_API_KEY
    python tools/turbopuffer_match.py --live --pull  # also re-pull titles from both venues

The labeled set is tests/fixtures/title_pairs.json. This measures match quality on a
few hundred titles. It says nothing about turbopuffer's latency or throughput.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from xstruct.monitor.match import match  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "title_pairs.json"
NAMESPACE = "xstruct-titles"
SCHEMA = {
    "title": {"type": "string", "full_text_search": True},
    "token_id": {"type": "string"},
    "venue": {"type": "string"},
}


# ---------------------------------------------------------------- titles

def load_fixture(path: Path = FIXTURE) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def pull_titles(events: int = 60, limit: int = 500) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Live (ticker, title) from Kalshi and (token_id, question) from Polymarket."""
    from xstruct.monitor.live import _polymarket_titles
    from xstruct.venue.kalshi import KalshiVenue

    kal = KalshiVenue(events=events)
    # KalshiVenue._market cuts the title to 96 chars for the board. Index the full title.
    raw = kal._get("/events", {"limit": events, "status": "open", "with_nested_markets": "true"})
    kal.close()
    kalshi = [
        (m.get("ticker", ""), m.get("title", ""))
        for e in raw.get("events", [])
        if "CROSSCATEGORY" not in (e.get("event_ticker") or "")
        for m in e.get("markets") or []
    ]
    return kalshi, _polymarket_titles(limit)


# ---------------------------------------------------------------- fake client

_WORD = re.compile(r"[a-z0-9]+")


def _tok(text: str) -> list[str]:
    return _WORD.findall(text.lower())


class FakeRow(dict):
    """Looks enough like a turbopuffer row: row.id and row["$dist"]."""

    @property
    def id(self):
        return self["id"]


class FakeResult:
    def __init__(self, rows: list[FakeRow]) -> None:
        self.rows = rows


class FakeNamespace:
    """In-memory stand-in for a turbopuffer namespace: write(upsert_rows) and a
    BM25 query (Lucene-style idf, k1 1.2, b 0.75, k3 8) with an Eq filter. The
    tokenizer is a lowercase [a-z0-9]+ split, close to word_v4 on these titles but
    not identical; the live numbers are the ones that count."""

    def __init__(self, k1: float = 1.2, b: float = 0.75, k3: float = 8.0) -> None:
        self.rows: dict[object, dict] = {}
        self.schema: dict | None = None
        self.k1, self.b, self.k3 = k1, b, k3

    def write(self, upsert_rows: list[dict], schema: dict | None = None, **_: object) -> None:
        if schema is not None:
            self.schema = schema
        for r in upsert_rows:
            self.rows[r["id"]] = dict(r)

    def query(self, rank_by: tuple, top_k: int = 10, filters: tuple | None = None,
              include_attributes: list[str] | None = None) -> FakeResult:
        attr, kind, text = rank_by
        if kind != "BM25":
            raise NotImplementedError(kind)
        docs = list(self.rows.values())
        if filters is not None:
            fa, op, fv = filters
            if op != "Eq":
                raise NotImplementedError(op)
            docs = [d for d in docs if d.get(fa) == fv]
        n = len(docs)
        if n == 0:
            return FakeResult([])
        toks = [_tok(d.get(attr, "")) for d in docs]
        avgdl = sum(len(t) for t in toks) / n
        df = Counter(w for t in toks for w in set(t))
        q = Counter(_tok(text))
        scored = []
        for d, t in zip(docs, toks):
            tf = Counter(t)
            s = 0.0
            for w, qtf in q.items():
                if w not in tf:
                    continue
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                num = tf[w] * (self.k1 + 1)
                den = tf[w] + self.k1 * (1 - self.b + self.b * len(t) / avgdl)
                qw = (self.k3 + 1) * qtf / (self.k3 + qtf)
                s += idf * num / den * qw
            if s > 0:
                scored.append((s, d))
        scored.sort(key=lambda x: -x[0])
        out = []
        for s, d in scored[:top_k]:
            row = FakeRow(id=d["id"])
            row["$dist"] = s
            for a in include_attributes or []:
                row[a] = d.get(a)
            out.append(row)
        return FakeResult(out)


# ---------------------------------------------------------------- real client

def turbopuffer_namespace(name: str = NAMESPACE, region: str = "gcp-us-central1"):
    key = os.environ.get("TURBOPUFFER_API_KEY")
    if not key:
        sys.exit(
            "TURBOPUFFER_API_KEY is not set. There is no free tier: sign up for the Launch "
            "plan ($16 a month minimum), create a key in the dashboard, export it, then rerun "
            "with --live."
        )
    try:
        import turbopuffer
    except ImportError:
        sys.exit("pip install turbopuffer")
    return turbopuffer.Turbopuffer(api_key=key, region=region).namespace(name)


def _field(row, key: str):
    try:
        return row[key]
    except (KeyError, TypeError):
        pass
    v = getattr(row, key, None)
    if v is None and getattr(row, "model_extra", None):
        v = row.model_extra.get(key)
    return v


# ---------------------------------------------------------------- the two matchers

def index_titles(ns, polymarket: list[tuple[str, str]]) -> int:
    """Write Polymarket titles with a BM25 index on `title`. turbopuffer ids are u64,
    128-bit UUID, or strings up to 64 bytes. A Polymarket CLOB token id is a 77-digit
    decimal string, too long for all three, so the row id is the list index and the
    token id rides along as a string attribute."""
    rows = [
        {"id": i, "title": q, "token_id": tok, "venue": "polymarket"}
        for i, (tok, q) in enumerate(polymarket)
    ]
    for start in range(0, len(rows), 500):
        ns.write(upsert_rows=rows[start:start + 500], schema=SCHEMA)
    return len(rows)


def bm25_top(ns, kalshi: list[tuple[str, str]], top_k: int = 3) -> dict[str, list[tuple[float, str, str]]]:
    """Per Kalshi ticker: [(score, token_id, title), ...] best first."""
    out = {}
    for ticker, title in kalshi:
        res = ns.query(
            rank_by=("title", "BM25", title),
            top_k=top_k,
            filters=("venue", "Eq", "polymarket"),
            include_attributes=["title", "token_id"],
        )
        out[ticker] = [(float(_field(r, "$dist")), _field(r, "token_id"), _field(r, "title")) for r in res.rows]
    return out


def idf_top(kalshi: list[tuple[str, str]], polymarket: list[tuple[str, str]],
            min_score: float = 0.75) -> dict[str, tuple[float, str]]:
    """Per Kalshi ticker: (score, token_id) of the best match() hit at min_score."""
    out: dict[str, tuple[float, str]] = {}
    for score, kt, tok, _shared in match(kalshi, polymarket, min_score=min_score):
        out.setdefault(kt, (score, tok))  # match() is sorted best first
    return out


# ---------------------------------------------------------------- scoring

def scored_labels(fixture: dict) -> list[dict]:
    return [l for l in fixture["labels"] if not l.get("uncertain")]


def precision_recall(pred: dict[str, str | None], labels: list[dict]) -> dict:
    """pred maps ticker -> predicted token_id (or None). A prediction counts as
    correct only when it equals the labeled token_id. Predicting anything for a
    labeled-none title is a false positive."""
    tp = fp = fn = 0
    for l in labels:
        truth, guess = l["polymarket"], pred.get(l["kalshi"])
        if guess is None:
            fn += truth is not None
        elif guess == truth:
            tp += 1
        else:
            fp += 1
            fn += truth is not None
    positives = sum(1 for l in labels if l["polymarket"] is not None)
    made = tp + fp
    p = tp / made if made else 0.0
    r = tp / positives if positives else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "predictions": made, "positives": positives,
            "precision": p, "recall": r, "f1": f1}


def bm25_predict(tops: dict, labels: list[dict], threshold: float) -> dict[str, str | None]:
    pred = {}
    for l in labels:
        hits = tops.get(l["kalshi"]) or []
        pred[l["kalshi"]] = hits[0][1] if hits and hits[0][0] >= threshold else None
    return pred


def best_threshold(tops: dict, labels: list[dict]) -> float:
    """Sweep the observed top-1 scores and keep the threshold with the best F1,
    highest threshold on ties. Chosen on the labeled set, so it is optimistic."""
    cands = sorted({hits[0][0] for t, hits in tops.items() if hits}, reverse=True)
    best, best_t = (-1.0, -1.0), 0.0
    for t in cands:
        m = precision_recall(bm25_predict(tops, labels, t), labels)
        if (m["f1"], t) > best:
            best, best_t = (m["f1"], t), t
    return best_t


# ---------------------------------------------------------------- report

def compare(fixture: dict, ns, kalshi: list[tuple[str, str]] | None = None,
            polymarket: list[tuple[str, str]] | None = None, min_score: float = 0.75) -> dict:
    """Run both matchers on one corpus and score them on the fixture labels.
    Labels whose ticker or token id is missing from the corpus are dropped."""
    kalshi = kalshi or [(r["ticker"], r["title"]) for r in fixture["kalshi"]]
    polymarket = polymarket or [(r["token_id"], r["question"]) for r in fixture["polymarket"]]
    kt, pt = dict(kalshi), {tok for tok, _ in polymarket}
    labels = [l for l in scored_labels(fixture)
              if l["kalshi"] in kt and (l["polymarket"] is None or l["polymarket"] in pt)]
    dropped = len(scored_labels(fixture)) - len(labels)

    index_titles(ns, polymarket)
    queries = [(l["kalshi"], kt[l["kalshi"]]) for l in labels]
    tops = bm25_top(ns, queries)
    t = best_threshold(tops, labels)
    bm25_pred = bm25_predict(tops, labels, t)
    raw_pred = bm25_predict(tops, labels, 0.0)

    idf = idf_top(kalshi, polymarket, min_score=min_score)
    idf_pred = {l["kalshi"]: (idf[l["kalshi"]][1] if l["kalshi"] in idf else None) for l in labels}

    return {
        "n_kalshi": len(kalshi), "n_polymarket": len(polymarket), "labels": labels, "dropped": dropped,
        "idf": {"pred": idf_pred, "scores": idf, "threshold": min_score, **precision_recall(idf_pred, labels)},
        "bm25": {"pred": bm25_pred, "tops": tops, "threshold": t, **precision_recall(bm25_pred, labels)},
        "bm25_raw": {"pred": raw_pred, "threshold": 0.0, **precision_recall(raw_pred, labels)},
    }


def _mark(guess, truth) -> str:
    if guess is None:
        return "none" if truth is None else "MISS"
    return "ok" if guess == truth else "WRONG"


def render(result: dict) -> str:
    lines = []
    labels = result["labels"]
    idf, bm = result["idf"], result["bm25"]
    lines.append(f"{'kalshi':<30} {'truth':<8} {'idf':<6} {'score':>6}   {'bm25':<6} {'score':>6}  {'bm25 top-1 title'}")
    for l in labels:
        k = l["kalshi"]
        truth = l["polymarket"]
        ig, bg = idf["pred"].get(k), bm["pred"].get(k)
        isc = idf["scores"][k][0] if k in idf["scores"] else 0.0
        hits = bm["tops"].get(k) or []
        bsc, btitle = (hits[0][0], hits[0][2]) if hits else (0.0, "")
        lines.append(f"{k[:30]:<30} {('none' if truth is None else truth[:8]):<8} "
                     f"{_mark(ig, truth):<6} {isc:6.2f}   {_mark(bg, truth):<6} {bsc:6.2f}  {btitle[:60]}")
    lines.append("")
    lines.append(f"corpus: {result['n_kalshi']} kalshi titles, {result['n_polymarket']} polymarket titles; "
                 f"{len(labels)} labeled ({idf['positives']} with a counterpart, "
                 f"{len(labels) - idf['positives']} without); {result['dropped']} labels dropped as not in corpus")
    lines.append("")
    lines.append(f"{'method':<22} {'threshold':>9} {'predicted':>9} {'correct':>7} {'precision':>9} {'recall':>7} {'f1':>6}")
    for name, m in (("idf match()", idf), ("bm25 top-1, tuned", bm), ("bm25 top-1, no cut", result["bm25_raw"])):
        lines.append(f"{name:<22} {m['threshold']:9.2f} {m['predictions']:9d} {m['tp']:7d} "
                     f"{m['precision']:9.3f} {m['recall']:7.3f} {m['f1']:6.3f}")
    lines.append("")
    lines.append("match quality on a few hundred titles. not a benchmark of the engine. the bm25 threshold "
                 "was picked on this same labeled set, so it is the best case for bm25.")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="IDF matcher vs turbopuffer BM25 on a labeled title set")
    ap.add_argument("--live", action="store_true", help="use turbopuffer (reads TURBOPUFFER_API_KEY)")
    ap.add_argument("--pull", action="store_true", help="re-pull titles from Kalshi and Polymarket")
    ap.add_argument("--events", type=int, default=60, help="Kalshi events to walk when pulling")
    ap.add_argument("--fixture", type=Path, default=FIXTURE)
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    fixture = load_fixture(args.fixture)
    kalshi = polymarket = None
    if args.pull:
        kalshi, polymarket = pull_titles(events=args.events)
        print(f"pulled {len(kalshi)} kalshi titles and {len(polymarket)} polymarket titles")
    ns = turbopuffer_namespace() if args.live else FakeNamespace()
    if args.live and hasattr(ns, "delete_all"):
        try:
            ns.delete_all()  # start from an empty namespace so stale rows cannot rank
        except Exception:
            pass
    print(("live turbopuffer" if args.live else "offline fake (in-memory BM25)") + "\n")
    print(render(compare(fixture, ns, kalshi, polymarket)))


if __name__ == "__main__":
    main()
