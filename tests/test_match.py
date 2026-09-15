"""The matcher exists because of one specific failure, so that failure is the test."""
from xstruct.monitor.match import match, tokens

KALSHI = [("K-KATZ", "Will Israel Katz be the next Prime Minister of Israel?")]
POLY = [
    ("P-ABDISA", "Will Shimelis Abdisa be the next Prime Minister of Ethiopia?"),
    ("P-TIMO", "Will Gedion Timothewos be the next Prime Minister of Ethiopia?"),
    ("P-MEKO", "Will Demeke Mekonnen be the next Prime Minister of Ethiopia?"),
    ("P-NEGA", "Will Berhanu Nega be the next Prime Minister of Ethiopia?"),
    ("P-MOLLA", "Will Belete Molla be the next Prime Minister of Ethiopia?"),
    ("P-KATZ", "Will Israel Katz be the next Prime Minister of Israel?"),
    # unrelated filler so the corpus resembles a real venue listing, where "next
    # prime minister" is common and a candidate's name is rare
    ("P-RAIN", "Will it rain in London on Friday?"),
    ("P-FED", "Will the Fed cut rates in December?"),
    ("P-BTC", "Will Bitcoin close above 100k this month?"),
    ("P-NFL", "Will the Chiefs win the Super Bowl?"),
    ("P-OSCAR", "Will Dune win Best Picture?"),
    ("P-SHUT", "Will the government shut down in October?"),
]


def test_naive_overlap_would_have_matched_the_wrong_country():
    # documents the bug: every Ethiopia title shares 3 words with the Israel one
    k = tokens(KALSHI[0][1])
    eth = tokens(POLY[0][1])
    assert {"next", "prime", "minister"} <= (k & eth)


def test_idf_matches_the_right_market_and_only_that_one():
    hits = match(KALSHI, POLY)
    assert hits, "expected the true pair to match"
    score, left, right, shared = hits[0]
    assert (left, right) == ("K-KATZ", "P-KATZ")
    assert "katz" in shared and "israel" in shared
    # boilerplate carried no weight
    assert not {"next", "prime", "minister"} & set(shared)
    # and no Ethiopia candidate survived
    assert len(hits) == 1
