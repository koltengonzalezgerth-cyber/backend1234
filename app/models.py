from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(10), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    asset_class = Column(String(10), nullable=False)  # "stock" | "crypto"

    # Live price fields — updated every ingestion cycle from Finnhub
    # (stocks) or CoinGecko (crypto). Null until the first successful fetch.
    price = Column(Float, nullable=True)
    day_change_pct = Column(Float, nullable=True)
    price_updated_at = Column(DateTime, nullable=True)

    mentions = relationship("Mention", back_populates="asset")
    snapshots = relationship("SentimentSnapshot", back_populates="asset")


class Mention(Base):
    """A single raw item pulled from a source (news headline, Reddit post, etc.)."""
    __tablename__ = "mentions"

    id = Column(Integer, primary_key=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    source = Column(String(30), nullable=False)  # "rss" | "reddit" | "newsapi" | "stocktwits"
    text = Column(Text, nullable=False)
    url = Column(String(500), nullable=True)
    sentiment_score = Column(Float, nullable=True)  # -1.0 (negative) to 1.0 (positive)
    fetched_at = Column(DateTime, default=datetime.utcnow, index=True)

    asset = relationship("Asset", back_populates="mentions")


class SentimentSnapshot(Base):
    """Aggregated sentiment for one asset at one point in time (written every ingest cycle)."""
    __tablename__ = "sentiment_snapshots"

    id = Column(Integer, primary_key=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    score = Column(Float, nullable=False)       # 0-100 composite score served to the app
    news_count = Column(Integer, default=0)
    social_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    asset = relationship("Asset", back_populates="snapshots")
