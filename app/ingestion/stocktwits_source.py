"""
Pulls recent community messages from StockTwits' public symbol stream
endpoint (https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json).

No API key or account needed for this endpoint — it's a public,
unauthenticated read. StockTwits' unique advantage over RSS/Reddit: many
messages carry an explicit user-applied "Bullish" or "Bearish" tag, which
is a much stronger signal than inferring sentiment from free text.

Rate limits on the anonymous public endpoint are informal/undocumented
but historically generous for this volume (10 symbols x 4 cycles/hour at
the default 15-minute interval = 40 requests/hour) — if you see 429s in
the logs, increase INGEST_INTERVAL_MINUTES or add a delay between symbols.
"""
import time
import requests
from app.config import settings

# StockTwits uses a ".X" suffix for crypto tickers; stocks use the plain symbol.
_CRYPTO_SUFFIX_MAP = {
    "BTC": "BTC.X", "ETH": "ETH.X", "SOL": "SOL.X", "XRP": "XRP.X", "DOGE": "DOGE.X",
}


def _stocktwits_symbol(sym: str) -> str:
    return _CRYPTO_SUFFIX_MAP.get(sym, sym)


def fetch_stocktwits_mentions() -> list[dict]:
    """
    Returns a list of {symbol, source, text, url, tagged_sentiment} dicts.
    `tagged_sentiment` is "Bullish", "Bearish", or None — see app/sentiment.py
    for how this overrides text-based scoring when present.
    """
    results = []
    symbols = settings.STOCK_SYMBOLS + settings.CRYPTO_SYMBOLS

    for sym in symbols:
        st_symbol = _stocktwits_symbol(sym)
        try:
            resp = requests.get(
                f"{settings.STOCKTWITS_BASE_URL}/streams/symbol/{st_symbol}.json",
                timeout=8,
            )
            if resp.status_code == 429:
                print("[stocktwits] rate limited — stopping early this cycle")
                break
            resp.raise_for_status()
            messages = resp.json().get("messages", [])
        except Exception as e:
            print(f"[stocktwits] failed for {st_symbol}: {e}")
            continue

        for m in messages:
            entities = m.get("entities") or {}
            sentiment_tag = (entities.get("sentiment") or {}).get("basic")  # "Bullish" | "Bearish" | None
            results.append({
                "symbol": sym,
                "source": "stocktwits",
                "text": m.get("body", ""),
                "url": f"https://stocktwits.com/message/{m['id']}" if m.get("id") else None,
                "tagged_sentiment": sentiment_tag,
            })

        time.sleep(0.2)  # small politeness delay between symbols

    return results
