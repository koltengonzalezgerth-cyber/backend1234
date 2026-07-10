"""
Pulls recent headlines from NewsAPI.org's free developer tier
(https://newsapi.org — 100 requests/day, articles capped to ~1 month old,
dev tier not licensed for production commercial use at scale — read their
terms before shipping publicly and budget for a paid plan if you grow).
"""
"""
Pulls recent headlines from NewsAPI.org's free developer tier
(https://newsapi.org — 100 requests/day, articles capped to ~1 month old,
dev tier not licensed for production commercial use at scale — read their
terms before shipping publicly and budget for a paid plan if you grow).

IMPORTANT: this issues ONE combined request per ingestion cycle (not one
per symbol) specifically so the free 100 req/day quota can support a short
refresh interval. At the default 15-minute cycle that's 96 requests/day —
comfortably under the 100/day cap. If you lower INGEST_INTERVAL_MINUTES,
re-check this math: requests/day = (24*60 / interval_minutes).
"""
import requests
from app.config import settings

_BASE_URL = "https://newsapi.org/v2/everything"

# Maps headline text back to a symbol after the combined query returns.
_NAME_MAP = {
    "AAPL": ["apple"], "TSLA": ["tesla"], "NVDA": ["nvidia"],
    "MSFT": ["microsoft"], "AMZN": ["amazon"],
    "BTC": ["bitcoin"], "ETH": ["ethereum"], "SOL": ["solana"],
    "XRP": ["xrp", "ripple"], "DOGE": ["dogecoin"],
}


def fetch_newsapi_mentions() -> list[dict]:
    if not settings.NEWSAPI_KEY:
        print("[newsapi] no API key set, skipping")
        return []

    symbols = settings.STOCK_SYMBOLS + settings.CRYPTO_SYMBOLS
    # Build one OR-query covering every tracked asset, e.g. "AAPL OR TSLA OR bitcoin OR ..."
    terms = []
    for sym in symbols:
        terms.append(sym)
        terms.extend(_NAME_MAP.get(sym, []))
    query = " OR ".join(sorted(set(terms)))

    try:
        resp = requests.get(
            _BASE_URL,
            params={
                "q": query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 100,  # max allowed on the free tier in one call
            },
            headers={"X-Api-Key": settings.NEWSAPI_KEY},
            timeout=10,
        )
        resp.raise_for_status()
        articles = resp.json().get("articles", [])
    except Exception as e:
        print(f"[newsapi] combined query failed: {e}")
        return []

    results = []
    for article in articles:
        haystack = f"{article.get('title', '')} {article.get('description', '')}".lower()
        for sym in symbols:
            needles = [sym.lower()] + _NAME_MAP.get(sym, [])
            if any(n in haystack for n in needles):
                results.append({
                    "symbol": sym,
                    "source": "newsapi",
                    "text": article.get("title", ""),
                    "url": article.get("url"),
                })
    return results
