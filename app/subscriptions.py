"""
Subscription/entitlement data model.

Real purchase validation happens with Apple/Google, not here — this module
just stores the *result* of that validation (which tier a user is entitled
to, until when) and every request checks it. Never trust a client-supplied
"I'm subscribed" flag; state ownership lives on the backend/App Store/Play
Store, and is only ever written here after verifying a receipt/notification
signature (see PLAN.md in the ingestion doc + the iap-roadmap doc for how).
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

TIERS = {
    "monthly": {"label": "Monthly", "price_usd": 10.00, "duration_days": 30},
    "quarterly": {"label": "3 Months", "price_usd": 15.00, "duration_days": 90},
    "annual": {"label": "Annual", "price_usd": 45.00, "duration_days": 365},
}


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    # Apple's stable per-user identifier, set ONLY after verifying a real
    # Sign in with Apple identity token server-side (see app/auth.py) —
    # never trust a client-supplied value for this column.
    apple_sub = Column(String(200), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    subscriptions = relationship("Subscription", back_populates="user")


class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tier = Column(String(20), nullable=False)  # "monthly" | "quarterly" | "annual"
    platform = Column(String(10), nullable=False)  # "ios" | "android"
    store_transaction_id = Column(String(200), unique=True, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    auto_renewing = Column(String(5), default="true")
    revoked = Column(String(5), default="false")  # set true on refund/chargeback webhook

    user = relationship("User", back_populates="subscriptions")


def is_active(subscription: "Subscription") -> bool:
    return subscription.revoked != "true" and subscription.expires_at > datetime.utcnow()
