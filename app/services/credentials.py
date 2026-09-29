import hashlib
import secrets
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feature_flags import EnvironmentKey

def generate_sdk_key() -> str:
    return f"ffp_{secrets.token_urlsafe(32)}"

def hash_sdk_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

async def issue_sdk_key(*, db: AsyncSession, environment_id: UUID, name: str, revoke_existing: bool) -> str:
    if revoke_existing:
        existing = await db.scalars(select(EnvironmentKey).where(EnvironmentKey.environment_id == environment_id, EnvironmentKey.revoked_at.is_(None)))
        for key in existing:
            key.revoked_at = datetime.now(timezone.utc)
    raw_key = generate_sdk_key()
    db.add(EnvironmentKey(environment_id=environment_id, name=name, key_prefix=raw_key[:12], key_hash=hash_sdk_key(raw_key)))
    await db.flush()
    return raw_key
