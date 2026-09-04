from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from helixgate.config import JWT_ISSUER, JWT_SECRET


def issue_token(subject: str, audience: str, scopes: list[str], minutes: int = 30) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iss": JWT_ISSUER,
        "aud": audience,
        "scp": scopes,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_token(token: str, audience: str | None = None) -> dict:
    options = {"verify_aud": bool(audience)}
    kwargs: dict = {"algorithms": ["HS256"], "options": options}
    if audience:
        kwargs["audience"] = audience
    return jwt.decode(token, JWT_SECRET, **kwargs)


def authorize_route(token: str | None, route: dict) -> tuple[bool, str, dict]:
    auth = route.get("auth") or {}
    if auth.get("type") == "none":
        return True, "anonymous", {}
    if not token:
        return False, "anonymous", {}
    audiences = auth.get("audiences") or []
    try:
        claims = decode_token(token, audience=audiences[0] if audiences else None)
    except jwt.PyJWTError:
        return False, "anonymous", {}
    return True, str(claims.get("sub") or "unknown"), claims
