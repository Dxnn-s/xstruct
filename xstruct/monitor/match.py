"""Match the same event across venues when there is no shared key.

Pascal republishes Polymarket's condition_id, so those two join exactly. Kalshi
publishes nothing that maps to Polymarket, so the only handle is the title.

Plain word overlap fails in a specific and confident way: "Will Israel Katz be
the next Prime Minister of Israel?" matched every "next Prime Minister of
Ethiopia" candidate, because the shared words were `next`, `prime`, `minister`.
Boilerplate, zero content. So shared words are weighted by inverse document
frequency across both venues' titles: a word that appears in most titles is
worth almost nothing, a name that appears in two is worth a lot.
"""
from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN = re.compile(r"[a-z0-9]+")


def tokens(title: str) -> set[str]:
    return {w for w in _TOKEN.findall(title.lower()) if len(w) > 2}


def match(
    left: list[tuple[str, str]],
    right: list[tuple[str, str]],
    min_score: float = 0.75,
    min_shared: int = 2,
) -> list[tuple[float, str, str, list[str]]]:
    """`left` and `right` are lists of (id, title). Returns matches as
    (score, left_id, right_id, shared_words), best first."""
    docs = [tokens(t) for _, t in left] + [tokens(t) for _, t in right]
    n = len(docs)
    df = Counter(w for d in docs for w in d)
    idf = {w: math.log(n / (1 + c)) for w, c in df.items()}

    def weigh(ts: set[str]) -> dict[str, float]:
        # a word in more than a third of all titles is boilerplate ("next", "prime",
        # "minister") and carries no weight. stated as a fraction, not an idf cutoff,
        # so it means the same thing in an 8-title test and a 1,600-title live run.
        return {w: idf[w] for w in ts if df[w] / n <= 1 / 3}

    lw = [(i, weigh(tokens(t))) for i, t in left]
    rw = [(j, weigh(tokens(t))) for j, t in right]
    out = []
    for li, lv in lw:
        if len(lv) < min_shared:
            continue
        for rj, rv in rw:
            if len(rv) < min_shared:
                continue
            shared = lv.keys() & rv.keys()
            if len(shared) < min_shared:
                continue
            score = sum(lv[w] for w in shared) / min(sum(lv.values()), sum(rv.values()))
            if score >= min_score:
                out.append((score, li, rj, sorted(shared)))
    return sorted(out, key=lambda x: -x[0])
