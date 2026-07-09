from pydantic import BaseModel
from datetime import datetime
from typing import List


class SnapshotOut(BaseModel):
    score: float
    news_count: int
    social_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class MentionOut(BaseModel):
    source: str
    text: str
    url: str | None
    sentiment_score: float | None
    fetched_at: datetime

    class Config:
        from_attributes = True


class AssetOut(BaseModel):
    symbol: str
    name: str
    asset_class: str
    latest_score: float | None = None
    history: List[SnapshotOut] = []
    price: float | None = None
    day_change_pct: float | None = None
    price_updated_at: datetime | None = None

    class Config:
        from_attributes = True


class AssetDetailOut(AssetOut):
    top_mentions: List[MentionOut] = []


class MoodOut(BaseModel):
    overall_score: float
    label: str
    asset_count: int
