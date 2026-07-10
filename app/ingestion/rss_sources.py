"""
Pulls headlines from free public RSS feeds and matches them to tracked
assets by name/symbol. No API key required.
"""
import socket
import feedparser
from app.config import settings

_FEED_TIMEOUT_SECONDS = 8


def fetch_rss_mentions() -> list[dict]:
    """
    Returns a list of {symbol, source, text, url} dicts. Matching is a
    simple substring check on title+summary — good enough for a v1, but
    worth replacing with a proper entity-linking model later to cut down
    on false positives (e.g. "Amazon" the river vs. the company).
    """
    all_symbols = {
        **{s: s for s in settings.STOCK_SYMBOLS},
        **{s: s for s in settings.CRYPTO_SYMBOLS},
    }
    # crude name map so "Apple", "Tesla" etc. also match — extend as needed
    name_map = {
        "AAPL": ["apple"], "TSLA": ["tesla"], "NVDA": ["nvidia"],
        "MSFT": ["microsoft"], "AMZN": ["amazon"],
        "BTC": ["bitcoin"], "ETH": ["ethereum"], "SOL": ["solana"],
        "XRP": ["xrp", "ripple"], "DOGE": ["dogecoin"],
    }

    results = []
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(_FEED_TIMEOUT_SECONDS)
    try:
        for feed_url in settings.RSS_FEEDS:
            try:
                parsed = feedparser.parse(feed_url)
            except Exception as e:
                print(f"[rss] failed to fetch {feed_url}: {e}")
                continue

            for entry in parsed.entries:
                haystack = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
                for symbol in all_symbols:
                    needles = [symbol.lower()] + name_map.get(symbol, [])
                    if any(n in haystack for n in needles):
                        results.append({
                            "symbol": symbol,
                            "source": "rss",
                            "text": entry.get("title", ""),
                            "url": entry.get("link"),
                        })
    finally:
        socket.setdefaulttimeout(old_timeout)
    return results
