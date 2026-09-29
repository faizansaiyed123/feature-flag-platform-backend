from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import jwt

from app.config import get_settings

TokenType = Literal["access", "refresh"]

def create_token(*, subject: str, token_type: TokenType, lifetime: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + lifetime,
    }
    return jwt.encode(payload, get_settings().auth_secret_key, algorithm="HS256")

def create_access_token(subject: str) -> str:
    settings = get_settings()
    return create_token(subject=subject, token_type="access", lifetime=timedelta(minutes=settings.access_token_expire_minutes))

def create_refresh_token(subject: str) -> str:
    settings = get_settings()
    return create_token(subject=subject, token_type="refresh", lifetime=timedelta(days=settings.refresh_token_expire_days))

def decode_token(token: str, expected_type: TokenType) -> str | None:
    try:
        payload = jwt.decode(
            token,
            get_settings().auth_secret_key,
            algorithms=["HS256"],
            options={"require": ["sub", "type", "iat", "exp"]},
        )
    except jwt.PyJWTError:
        return None

    if payload.get("type") != expected_type:
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) and subject else None
