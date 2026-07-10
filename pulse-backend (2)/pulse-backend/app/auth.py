"""
Real identity verification, replacing the old "trust whatever external_id
the client sends" model (security-review.md item #3).

Flow:
  1. iOS app runs native Sign in with Apple -> gets a signed identity
     token (a JWT) directly from Apple, on-device.
  2. App sends that token to POST /auth/apple.
  3. This module verifies the token's signature against Apple's own
     public keys (fetched from Apple, cached), confirms it was issued for
     THIS app (aud check) and hasn't expired, then extracts Apple's
     stable per-user `sub` claim.
  4. We issue our own short-lived session token (a JWT we sign ourselves)
     tied to that verified `sub`. The app sends this session token on
     every subsequent request instead of a client-chosen identifier.

This means entitlement can never be spoofed by guessing/copying someone
else's ID string — the only way to get a valid session token is to
actually complete Sign in with Apple.
"""
import time
import jwt
import requests
from jwt import PyJWKClient
from fastapi import HTTPException

APPLE_ISSUER = "https://appleid.apple.com"
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"

# TODO: set this to your app's actual bundle ID (or Services ID if using
# Sign in with Apple for web) before shipping — e.g. "com.yourcompany.pulse"
EXPECTED_AUDIENCE = "com.yourcompany.pulse"

# Our own signing secret for session tokens — MUST be set to a long random
# value in production (e.g. `openssl rand -hex 32`), never left as this
# placeholder. Session tokens are only as secure as this secret.
import os
SESSION_SECRET = os.getenv("SESSION_SECRET", "")
SESSION_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days

_jwk_client = PyJWKClient(APPLE_JWKS_URL)


def verify_apple_identity_token(identity_token: str) -> str:
    """Returns Apple's stable `sub` claim if the token is valid, else raises."""
    try:
        signing_key = _jwk_client.get_signing_key_from_jwt(identity_token)
        claims = jwt.decode(
            identity_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=EXPECTED_AUDIENCE,
            issuer=APPLE_ISSUER,
        )
    except Exception as e:
        raise HTTPException(401, f"Invalid Apple identity token: {e}")

    sub = claims.get("sub")
    if not sub:
        raise HTTPException(401, "Apple identity token missing subject")
    return sub


def create_session_token(user_id: int) -> str:
    if not SESSION_SECRET:
        raise HTTPException(500, "Server misconfigured: SESSION_SECRET is not set")
    payload = {"user_id": user_id, "exp": int(time.time()) + SESSION_TTL_SECONDS}
    return jwt.encode(payload, SESSION_SECRET, algorithm="HS256")


def decode_session_token(token: str) -> int:
    if not SESSION_SECRET:
        raise HTTPException(500, "Server misconfigured: SESSION_SECRET is not set")
    try:
        claims = jwt.decode(token, SESSION_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid or expired session")
    return claims["user_id"]
