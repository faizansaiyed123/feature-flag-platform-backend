from datetime import datetime, timedelta, timezone
from typing import Any, Literal
import jwt
from app.config import get_settings

TokenType = Literal["access", "refresh"]

def create_token(*, subject: str, token_type: TokenType, lifetime: timedelta, jti: str | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {"sub": subject, "type": token_type, "iat": now, "exp": now + lifetime}
    if jti:
        payload["jti"] = jti
    return jwt.encode(payload, get_settings().auth_secret_key, algorithm="HS256")

def create_access_token(subject: str) -> str:
    settings = get_settings()
    return create_token(subject=subject, token_type="access", lifetime=timedelta(minutes=settings.access_token_expire_minutes))

def create_refresh_token(subject: str, jti: str) -> str:
    settings = get_settings()
    return create_token(subject=subject, token_type="refresh", lifetime=timedelta(days=settings.refresh_token_expire_days), jti=jti)

def decode_token_claims(token: str, expected_type: TokenType) -> dict[str, Any] | None:
    required = ["sub", "type", "iat", "exp"] + (["jti"] if expected_type == "refresh" else [])
    try:
        payload = jwt.decode(token, get_settings().auth_secret_key, algorithms=["HS256"], options={"require": required})
    except jwt.PyJWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload

def decode_token(token: str, expected_type: TokenType) -> str | None:
    payload = decode_token_claims(token, expected_type)
    if not payload:
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) and subject else None
