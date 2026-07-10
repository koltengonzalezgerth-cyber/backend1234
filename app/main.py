from fastapi import FastAPI, Depends, HTTPException, Header
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, timedelta

from app.database import get_db, engine, Base
from app.models import Asset, Mention, SentimentSnapshot
from app.subscriptions import User, Subscription, TIERS, is_active
from app.schemas import AssetOut, AssetDetailOut, MoodOut, SnapshotOut, MentionOut
from app.scheduler import start_scheduler
from app.auth import verify_apple_identity_token, create_session_token, decode_session_token

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Pulse API", version="0.2.0")


class AppleAuthRequest(BaseModel):
    identity_token: str

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    start_scheduler()


def _mood_label(score: float) -> str:
    if score >= 70: return "Bullish"
    if score >= 55: return "Cautiously Bullish"
    if score >= 45: return "Neutral"
    if score >= 30: return "Cautiously Bearish"
    return "Bearish"


def _get_or_create_user_by_apple_sub(db: Session, apple_sub: str) -> User:
    user = db.query(User).filter(User.apple_sub == apple_sub).first()
    if not user:
        user = User(apple_sub=apple_sub)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _current_user(db: Session, authorization: str | None) -> User | None:
    """Resolves the calling user from a `Bearer <session_token>` header.
    Returns None (treated as free/unauthenticated) if absent or invalid —
    callers decide whether that's acceptable for the endpoint in question."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    try:
        user_id = decode_session_token(token)
    except HTTPException:
        return None
    return db.query(User).filter(User.id == user_id).first()


def _user_is_subscribed(user: User | None) -> bool:
    if not user:
        return False
    return any(is_active(s) for s in user.subscriptions)


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Entitlement + purchase endpoints
# ---------------------------------------------------------------------------
# IMPORTANT: /purchases/demo-subscribe below is for local testing only — it
# grants entitlement with no real payment verification. The real endpoints
# your production app calls are /purchases/apple/verify and
# /purchases/google/verify, which must verify the receipt/token against
# Apple's or Google's servers before writing a Subscription row. See the
# iap-roadmap doc for exactly what that involves.

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

@app.post("/auth/apple")
def auth_apple(body: AppleAuthRequest, db: Session = Depends(get_db)):
    """
    Call this once, right after the iOS app completes native Sign in with
    Apple, passing the identity token Apple gave the app on-device. We
    verify it cryptographically (see app/auth.py) before trusting it —
    this is the one place a client-supplied value is trusted, and only
    because it's independently verifiable against Apple's public keys.
    """
    apple_sub = verify_apple_identity_token(body.identity_token)
    user = _get_or_create_user_by_apple_sub(db, apple_sub)
    session_token = create_session_token(user.id)
    return {"session_token": session_token}


@app.get("/entitlement")
def get_entitlement(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    user = _current_user(db, authorization)
    return {"subscribed": _user_is_subscribed(user)}


@app.post("/purchases/demo-subscribe")
def demo_subscribe(
    tier: str,
    authorization: str | None = Header(default=None),
    x_demo_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """
    Local-only stand-in for a verified purchase — grants entitlement with
    ZERO real payment verification. Disabled unless DEMO_MODE=true and the
    caller supplies the matching X-Demo-Secret header. Requires a valid
    session (i.e. the caller must have completed Sign in with Apple first)
    so this can only ever grant entitlement to a real, verified user
    during your own testing — never enable DEMO_MODE on a deployment real
    users might connect to.
    """
    if not settings.DEMO_MODE or not settings.DEMO_MODE_SECRET:
        raise HTTPException(404, "Not found")
    if not x_demo_secret or x_demo_secret != settings.DEMO_MODE_SECRET:
        raise HTTPException(403, "Forbidden")
    user = _current_user(db, authorization)
    if not user:
        raise HTTPException(401, "Sign in required")
    if tier not in TIERS:
        raise HTTPException(400, "Unknown tier")
    sub = Subscription(
        user_id=user.id,
        tier=tier,
        platform="demo",
        store_transaction_id=f"demo-{user.id}-{datetime.utcnow().timestamp()}",
        expires_at=datetime.utcnow() + timedelta(days=TIERS[tier]["duration_days"]),
    )
    db.add(sub)
    db.commit()
    return {"subscribed": True, "tier": tier, "expires_at": sub.expires_at}


@app.post("/purchases/apple/verify")
def verify_apple_purchase(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    """
    TODO before production: accept the signed transaction (JWS) from
    StoreKit 2, verify it using Apple's App Store Server API / public
    keys, extract the product id + expiresDate, map product id -> tier,
    resolve the calling user via `_current_user(db, authorization)` (same
    pattern as demo_subscribe), then write a Subscription row exactly like
    demo_subscribe does.
    """
    raise HTTPException(501, "Not implemented — see iap-roadmap doc for what this needs")


@app.post("/purchases/google/verify")
def verify_google_purchase():
    """
    TODO before production: call the Google Play Developer API
    (purchases.subscriptionsv2.get) with a service-account credential to
    verify the purchase token, map product id -> tier, then write a
    Subscription row exactly like demo_subscribe does above.
    """
    raise HTTPException(501, "Not implemented — see iap-roadmap doc for what this needs")


# ---------------------------------------------------------------------------
# Asset data endpoints
# ---------------------------------------------------------------------------

@app.get("/assets", response_model=list[AssetOut])
def list_assets(asset_class: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Asset)
    if asset_class:
        q = q.filter(Asset.asset_class == asset_class)
    assets = q.all()

    out = []
    for a in assets:
        latest = (
            db.query(SentimentSnapshot)
            .filter(SentimentSnapshot.asset_id == a.id)
            .order_by(desc(SentimentSnapshot.created_at))
            .first()
        )
        history = (
            db.query(SentimentSnapshot)
            .filter(SentimentSnapshot.asset_id == a.id)
            .order_by(SentimentSnapshot.created_at)
            .limit(50)
            .all()
        )
        out.append(AssetOut(
            symbol=a.symbol, name=a.name, asset_class=a.asset_class,
            latest_score=latest.score if latest else None,
            history=[SnapshotOut.model_validate(h) for h in history],
            price=a.price, day_change_pct=a.day_change_pct, price_updated_at=a.price_updated_at,
        ))
    return out


@app.get("/assets/{symbol}", response_model=AssetDetailOut)
def get_asset(symbol: str, authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    asset = db.query(Asset).filter(Asset.symbol == symbol.upper()).first()
    if not asset:
        raise HTTPException(404, "Unknown symbol")

    user = _current_user(db, authorization)
    subscribed = _user_is_subscribed(user)

    latest = (
        db.query(SentimentSnapshot)
        .filter(SentimentSnapshot.asset_id == asset.id)
        .order_by(desc(SentimentSnapshot.created_at))
        .first()
    )
    history_limit = 50 if subscribed else 6  # free tier gets a short preview only
    history = (
        db.query(SentimentSnapshot)
        .filter(SentimentSnapshot.asset_id == asset.id)
        .order_by(SentimentSnapshot.created_at)
        .limit(history_limit)
        .all()
    )
    # Free tier gets no raw mentions at all — that's the premium feature.
    top_mentions = []
    if subscribed:
        top_mentions = (
            db.query(Mention)
            .filter(Mention.asset_id == asset.id)
            .order_by(desc(Mention.fetched_at))
            .limit(30)
            .all()
        )

    return AssetDetailOut(
        symbol=asset.symbol, name=asset.name, asset_class=asset.asset_class,
        latest_score=latest.score if latest else None,
        history=[SnapshotOut.model_validate(h) for h in history],
        top_mentions=[MentionOut.model_validate(m) for m in top_mentions],
        price=asset.price, day_change_pct=asset.day_change_pct, price_updated_at=asset.price_updated_at,
    )


@app.get("/mood", response_model=MoodOut)
def overall_mood(db: Session = Depends(get_db)):
    assets = db.query(Asset).all()
    scores = []
    for a in assets:
        latest = (
            db.query(SentimentSnapshot)
            .filter(SentimentSnapshot.asset_id == a.id)
            .order_by(desc(SentimentSnapshot.created_at))
            .first()
        )
        if latest:
            scores.append(latest.score)

    if not scores:
        return MoodOut(overall_score=50.0, label="Neutral", asset_count=0)

    avg = round(sum(scores) / len(scores), 1)
    return MoodOut(overall_score=avg, label=_mood_label(avg), asset_count=len(scores))
