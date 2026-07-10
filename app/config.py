"""
Central configuration, loaded from environment variables (.env in dev).
Never hardcode secrets here — this file only reads them.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # --- Database ---
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./pulse.db")

    # --- Reddit API (create an app at https://www.reddit.com/prefs/apps) ---
    REDDIT_CLIENT_ID: str = os.getenv("REDDIT_CLIENT_ID", "")
    REDDIT_CLIENT_SECRET: str = os.getenv("REDDIT_CLIENT_SECRET", "")
    REDDIT_USER_AGENT: str = os.getenv("REDDIT_USER_AGENT", "pulse-app/0.1")

    # --- NewsAPI.org (free dev tier: https://newsapi.org) ---
    NEWSAPI_KEY: str = os.getenv("NEWSAPI_KEY", "")

    # --- Finnhub (free tier, 60 calls/min, no card: https://finnhub.io) ---
    # Used for live stock prices/day-change. Crypto prices come from
    # CoinGecko's free public endpoint below, which needs no key at all.
    FINNHUB_KEY: str = os.getenv("FINNHUB_KEY", "")
    COINGECKO_BASE_URL: str = "https://api.coingecko.com/api/v3"
    # Maps our symbols to CoinGecko's internal ids
    COINGECKO_IDS = {
        "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
        "XRP": "ripple", "DOGE": "dogecoin",
    }

    # --- StockTwits (no key needed for public read endpoints, but rate-limited) ---
    STOCKTWITS_BASE_URL: str = "https://api.stocktwits.com/api/2"

    # --- Demo/testing only: gates the insecure /purchases/demo-subscribe
    # endpoint, which grants entitlement with NO real payment verification.
    # Defaults to OFF. Only enable this on a throwaway test deployment,
    # never on anything a real user's device might point at. ---
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "false").lower() == "true"
    DEMO_MODE_SECRET: str = os.getenv("DEMO_MODE_SECRET", "")

    # --- Ingestion cadence ---
    # 15 minutes is the shortest interval that comfortably stays under
    # NewsAPI's free 100 req/day quota (96 requests/day at this cadence,
    # with 1 combined request per cycle). Going shorter risks exhausting
    # the quota partway through the day. See README for the full math.
    INGEST_INTERVAL_MINUTES: int = int(os.getenv("INGEST_INTERVAL_MINUTES", "15"))

    # --- Assets tracked (extend freely) ---
    STOCK_SYMBOLS = ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN"]
    CRYPTO_SYMBOLS = ["BTC", "ETH", "SOL", "XRP", "DOGE"]

    # Subreddits to pull chatter from per asset class
    STOCK_SUBREDDITS = ["stocks", "wallstreetbets", "investing"]
    CRYPTO_SUBREDDITS = ["cryptocurrency", "bitcoin", "ethtrader"]

    # RSS feeds (free, no key required)
    RSS_FEEDS = [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://www.cnbc.com/id/10001147/device/rss/rss.html",  # markets
        "https://cointelegraph.com/rss",
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
    ]


settings = Settings()
