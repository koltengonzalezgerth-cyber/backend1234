"""
Run one full ingestion cycle:
  1. Pull raw mentions from RSS, Reddit, NewsAPI
  2. Score each mention's sentiment
  3. Store raw mentions
  4. Compute + store one aggregated SentimentSnapshot per asset

Run directly for testing: `python -m app.ingestion.run_ingest`
In production this is called on a schedule (see app/scheduler.py).
"""
from datetime import datetime
from app.database import SessionLocal, engine, Base
from app.models import Asset, Mention, SentimentSnapshot
from app.config import settings
from app.sentiment import score_mention, to_composite_score
from app.ingestion.rss_sources import fetch_rss_mentions
from app.ingestion.reddit_source import fetch_reddit_mentions
from app.ingestion.newsapi_source import fetch_newsapi_mentions
from app.ingestion.stocktwits_source import fetch_stocktwits_mentions
from app.ingestion.price_source import fetch_all_prices

ASSET_NAMES = {
    "AAPL": "Apple", "TSLA": "Tesla", "NVDA": "NVIDIA", "MSFT": "Microsoft", "AMZN": "Amazon",
    "BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana", "XRP": "XRP", "DOGE": "Dogecoin",
}


def _ensure_assets(db):
    """Make sure every tracked symbol has an Asset row; return {symbol: Asset}."""
    existing = {a.symbol: a for a in db.query(Asset).all()}
    for symbol in settings.STOCK_SYMBOLS:
        if symbol not in existing:
            a = Asset(symbol=symbol, name=ASSET_NAMES.get(symbol, symbol), asset_class="stock")
            db.add(a)
            existing[symbol] = a
    for symbol in settings.CRYPTO_SYMBOLS:
        if symbol not in existing:
            a = Asset(symbol=symbol, name=ASSET_NAMES.get(symbol, symbol), asset_class="crypto")
            db.add(a)
            existing[symbol] = a
    db.commit()
    return existing


def run_ingest_cycle():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        assets = _ensure_assets(db)

        print("[ingest] fetching from all sources...")
        raw = []
        raw += fetch_rss_mentions()
        raw += fetch_reddit_mentions()
        raw += fetch_newsapi_mentions()
        raw += fetch_stocktwits_mentions()
        print(f"[ingest] pulled {len(raw)} raw mentions")

        by_symbol: dict[str, list[dict]] = {}
        for item in raw:
            by_symbol.setdefault(item["symbol"], []).append(item)

        for symbol, asset in assets.items():
            items = by_symbol.get(symbol, [])
            scores = []
            news_count = 0
            social_count = 0

            for item in items:
                s = score_mention(item["text"], item.get("tagged_sentiment"))
                scores.append(s)
                if item["source"] in ("rss", "newsapi"):
                    news_count += 1
                else:
                    social_count += 1

                db.add(Mention(
                    asset_id=asset.id,
                    source=item["source"],
                    text=item["text"][:1000],
                    url=item.get("url"),
                    sentiment_score=s,
                    fetched_at=datetime.utcnow(),
                ))

            composite = to_composite_score(scores)
            db.add(SentimentSnapshot(
                asset_id=asset.id,
                score=composite,
                news_count=news_count,
                social_count=social_count,
                created_at=datetime.utcnow(),
            ))
            print(f"[ingest] {symbol}: {len(items)} mentions -> score {composite}")

        print("[ingest] fetching live prices...")
        prices = fetch_all_prices()
        for symbol, asset in assets.items():
            p = prices.get(symbol)
            if not p:
                continue
            asset.price = p["price"]
            asset.day_change_pct = p["change_pct"]
            asset.price_updated_at = datetime.utcnow()
        print(f"[ingest] updated prices for {len(prices)} assets")

        db.commit()
        print("[ingest] cycle complete")
    finally:
        db.close()


if __name__ == "__main__":
    run_ingest_cycle()
