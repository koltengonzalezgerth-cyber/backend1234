"""
Fetches live price + day-change for every tracked asset.

- Stocks: Finnhub's free /quote endpoint (60 calls/min, no card required —
  get a key at https://finnhub.io). One call per symbol.
- Crypto: CoinGecko's free public /simple/price endpoint — no key needed
  at all, and one call covers every tracked coin at once.

Both are separate from the sentiment ingestion sources (RSS/NewsAPI/
StockTwits/Reddit) — this module is purely about price, not sentiment.
"""
import requests
from app.config import settings


def fetch_stock_prices() -> dict:
    """Returns {symbol: {"price": float, "change_pct": float}}."""
    if not settings.FINNHUB_KEY:
        print("[prices] no Finnhub key set, skipping stock prices")
        return {}

    results = {}
    for symbol in settings.STOCK_SYMBOLS:
        try:
            resp = requests.get(
                "https://finnhub.io/api/v1/quote",
                params={"symbol": symbol, "token": settings.FINNHUB_KEY},
                timeout=8,
            )
            resp.raise_for_status()
            data = resp.json()
            # Finnhub returns all-zero fields for an invalid/unknown symbol
            # rather than an error — skip those rather than storing junk.
            if not data.get("c"):
                continue
            results[symbol] = {"price": data["c"], "change_pct": data.get("dp", 0.0)}
        except Exception as e:
            print(f"[prices] Finnhub failed for {symbol}: {e}")
            continue
    return results


def fetch_crypto_prices() -> dict:
    """Returns {symbol: {"price": float, "change_pct": float}}."""
    ids = list(settings.COINGECKO_IDS.values())
    try:
        resp = requests.get(
            f"{settings.COINGECKO_BASE_URL}/simple/price",
            params={"ids": ",".join(ids), "vs_currencies": "usd", "include_24hr_change": "true"},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[prices] CoinGecko failed: {e}")
        return {}

    results = {}
    for symbol, coingecko_id in settings.COINGECKO_IDS.items():
        entry = data.get(coingecko_id)
        if not entry:
            continue
        results[symbol] = {"price": entry.get("usd", 0.0), "change_pct": entry.get("usd_24h_change", 0.0)}
    return results


def fetch_all_prices() -> dict:
    prices = {}
    prices.update(fetch_stock_prices())
    prices.update(fetch_crypto_prices())
    return prices
