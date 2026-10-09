"""Offline tests for tools/turbopuffer_match.py: the in-memory BM25 fake, the
precision/recall math, the threshold sweep, the fixture, and the side-by-side run."""
import importlib.util
import json
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "tools" / "turbopuffer_match.py"
_spec = importlib.util.spec_from_file_location("turbopuffer_match", _PATH)
tm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tm)

POLY = [
    ("P-KATZ", "Will Israel Katz be the next Prime Minister of Israel?"),
    ("P-ABDISA", "Will Shimelis Abdisa be the next Prime Minister of Ethiopia?"),
    ("P-NEGA", "Will Berhanu Nega be the next Prime Minister of Ethiopia?"),
    ("P-RAIN", "Will it rain in London on Friday?"),
    ("P-FED", "Will the Fed cut rates in December?"),
]


def indexed():
    ns = tm.FakeNamespace()
    tm.index_titles(ns, POLY)
    return ns


def test_fake_bm25_ranks_the_exact_title_first_and_scores_descend():
    ns = indexed()
    res = ns.query(rank_by=("title", "BM25", "Will Israel Katz be the next Prime Minister of Israel?"),
                   top_k=3, filters=("venue", "Eq", "polymarket"), include_attributes=["title", "token_id"])
    assert res.rows[0]["token_id"] == "P-KATZ"
    assert res.rows[0].id == 0
    scores = [r["$dist"] for r in res.rows]
    assert scores == sorted(scores, reverse=True) and scores[0] > scores[1]
    assert ns.schema["title"]["full_text_search"] is True


def test_fake_honours_filter_and_top_k():
    ns = indexed()
    assert ns.query(rank_by=("title", "BM25", "Prime Minister"), top_k=2).rows.__len__() == 2
    assert ns.query(rank_by=("title", "BM25", "Prime Minister"), top_k=10,
                    filters=("venue", "Eq", "kalshi")).rows == []
    # a query that shares no token with a doc does not return that doc
    ids = {r["token_id"] for r in ns.query(rank_by=("title", "BM25", "rain London"), top_k=10,
                                            include_attributes=["token_id"]).rows}
    assert ids == {"P-RAIN"}


def test_fake_upsert_replaces_the_row_with_the_same_id():
    ns = tm.FakeNamespace()
    ns.write(upsert_rows=[{"id": 1, "title": "old title", "venue": "polymarket"}])
    ns.write(upsert_rows=[{"id": 1, "title": "new title", "venue": "polymarket"}])
    assert len(ns.rows) == 1
    assert ns.query(rank_by=("title", "BM25", "old"), top_k=5).rows == []
    assert ns.query(rank_by=("title", "BM25", "new"), top_k=5).rows[0].id == 1


def test_precision_recall_counts_wrong_and_spurious_as_false_positives():
    labels = [
        {"kalshi": "A", "polymarket": "a"},
        {"kalshi": "B", "polymarket": "b"},
        {"kalshi": "C", "polymarket": None},
        {"kalshi": "D", "polymarket": "d"},
    ]
    pred = {"A": "a", "B": "x", "C": "c", "D": None}  # one right, one wrong, one spurious, one missed
    m = tm.precision_recall(pred, labels)
    assert (m["tp"], m["fp"], m["fn"]) == (1, 2, 2)
    assert m["precision"] == pytest.approx(1 / 3)
    assert m["recall"] == pytest.approx(1 / 3)


def test_threshold_sweep_separates_a_toy_set():
    labels = [{"kalshi": "A", "polymarket": "a"}, {"kalshi": "B", "polymarket": "b"},
              {"kalshi": "C", "polymarket": None}, {"kalshi": "D", "polymarket": None}]
    tops = {"A": [(9.0, "a", "")], "B": [(7.0, "b", "")], "C": [(4.0, "zzz", "")], "D": [(3.0, "zzz", "")]}
    t = tm.best_threshold(tops, labels)
    assert 4.0 < t <= 7.0
    m = tm.precision_recall(tm.bm25_predict(tops, labels, t), labels)
    assert m["precision"] == 1.0 and m["recall"] == 1.0


def test_fixture_is_well_formed_and_contains_the_israel_trap():
    fx = tm.load_fixture()
    scored = tm.scored_labels(fx)
    assert 40 <= len(scored) <= 60
    assert len(scored) < len(fx["labels"])  # uncertain pairs exist and are excluded
    assert all(l["uncertain"] for l in fx["labels"] if l not in scored)
    tickers = {r["ticker"] for r in fx["kalshi"]}
    tokens = {r["token_id"] for r in fx["polymarket"]}
    assert all(l["kalshi"] in tickers for l in scored)
    assert all(l["polymarket"] in tokens for l in scored if l["polymarket"] is not None)
    assert len({l["kalshi"] for l in fx["labels"]}) == len(fx["labels"])
    katz = next(l for l in scored if "Israel Katz" in l["kalshi_title"])
    assert katz["polymarket"] is None
    assert "—" not in json.dumps(fx, ensure_ascii=False)


def test_idf_matcher_on_the_fixture_keeps_katz_out_and_finds_bennett():
    fx = tm.load_fixture()
    kalshi = [(r["ticker"], r["title"]) for r in fx["kalshi"]]
    poly = [(r["token_id"], r["question"]) for r in fx["polymarket"]]
    top = tm.idf_top(kalshi, poly)
    assert "KXNEXTISRAELPM-45JAN01-IKAT" not in top
    bennett = next(l for l in fx["labels"] if l["kalshi"].endswith("-NBEN"))
    assert top[bennett["kalshi"]][1] == bennett["polymarket"]


def test_comparison_runs_offline_end_to_end_and_renders():
    fx = tm.load_fixture()
    result = tm.compare(fx, tm.FakeNamespace())
    assert result["dropped"] == 0
    for key in ("idf", "bm25", "bm25_raw"):
        assert 0.0 <= result[key]["precision"] <= 1.0 and 0.0 <= result[key]["recall"] <= 1.0
    assert result["bm25"]["precision"] >= result["bm25_raw"]["precision"]
    text = tm.render(result)
    assert "idf match()" in text and "bm25 top-1, tuned" in text
    assert "not a benchmark of the engine" in text
    assert "—" not in text


def test_live_path_refuses_without_a_key(monkeypatch):
    monkeypatch.delenv("TURBOPUFFER_API_KEY", raising=False)
    with pytest.raises(SystemExit) as e:
        tm.turbopuffer_namespace()
    assert "TURBOPUFFER_API_KEY" in str(e.value)
