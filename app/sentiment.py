"""
Sentiment scoring for ingested text.

Default: VADER (vaderSentiment) — fast, free, no GPU needed, good enough to
ship a v1. It under-performs on finance-specific phrasing ("beat estimates",
"missed guidance"), so we boost it with a small finance lexicon below.

Upgrade path: swap `score_text()` internals for a FinBERT call
(ProsusAI/finbert on Hugging Face) once you need higher accuracy — it's a
drop-in replacement, same function signature, just slower and needs a GPU
or hosted inference endpoint to run at scale affordably.
"""
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()

# Small domain boost so common finance phrasing isn't scored as neutral.
_FINANCE_LEXICON = {
    "beat estimates": 2.5,
    "beat expectations": 2.5,
    "missed estimates": -2.5,
    "missed guidance": -2.5,
    "cut guidance": -2.8,
    "raised guidance": 2.8,
    "downgrade": -2.2,
    "upgrade": 2.2,
    "bullish": 2.0,
    "bearish": -2.0,
    "recall": -2.0,
    "lawsuit": -1.8,
    "record high": 2.3,
    "all-time high": 2.3,
    "sell-off": -2.0,
    "rally": 1.8,
}
for phrase, score in _FINANCE_LEXICON.items():
    _analyzer.lexicon[phrase] = score


def score_text(text: str) -> float:
    """Returns a float from -1.0 (very negative) to 1.0 (very positive)."""
    if not text or not text.strip():
        return 0.0
    return _analyzer.polarity_scores(text)["compound"]


def score_mention(text: str, tagged_sentiment: str | None = None) -> float:
    """
    Like score_text, but honors an explicit user-applied label when one is
    available (currently only StockTwits provides this) — a person telling
    you directly "this is bullish" is a stronger signal than guessing from
    word choice, so it takes priority over text analysis when present.
    """
    if tagged_sentiment == "Bullish":
        return 0.9
    if tagged_sentiment == "Bearish":
        return -0.9
    return score_text(text)


def to_composite_score(mention_scores: list[float]) -> float:
    """
    Converts a list of raw -1..1 sentiment scores into the 0-100 composite
    score the app displays. Empty input returns a neutral 50.
    """
    if not mention_scores:
        return 50.0
    avg = sum(mention_scores) / len(mention_scores)
    return round((avg + 1) * 50, 1)  # map -1..1 -> 0..100
