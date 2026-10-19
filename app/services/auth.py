import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from fastapi import Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.models.identity import User
from app.models.organization import Membership, MembershipRole, Organization
from app.models.refresh_session import RefreshSession
from app.security.passwords import hash_password, verify_password
from app.security.tokens import create_access_token, create_refresh_token, decode_token_claims

@dataclass(frozen=True)
class AuthTokens:
    access_token: str
    refresh_token: str

def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:70] or f"workspace-{uuid4().hex[:8]}"

def set_auth_cookies(response: Response, tokens: AuthTokens) -> None:
    settings = get_settings()
    secure = settings.app_env.lower() == "production"
    samesite = settings.auth_cookie_samesite
    response.set_cookie("access_token", tokens.access_token, httponly=True, secure=secure, samesite=samesite, max_age=60 * settings.access_token_expire_minutes, path="/")
    response.set_cookie("refresh_token", tokens.refresh_token, httponly=True, secure=secure, samesite=samesite, max_age=60 * 60 * 24 * settings.refresh_token_expire_days, path="/api/v1/auth")

def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/v1/auth")

async def create_auth_session(db: AsyncSession, user_id: UUID) -> AuthTokens:
    settings = get_settings()
    token_jti = uuid4().hex
    session = RefreshSession(user_id=user_id, token_jti=token_jti, expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days))
    db.add(session)
    await db.flush()
    return AuthTokens(access_token=create_access_token(str(user_id)), refresh_token=create_refresh_token(str(user_id), token_jti))

async def rotate_auth_session(db: AsyncSession, refresh_token: str) -> tuple[User, AuthTokens] | None:
    claims = decode_token_claims(refresh_token, "refresh")
    if not claims:
        return None
    try:
        user_id = UUID(str(claims["sub"]))
    except (TypeError, ValueError):
        return None
    token_jti = claims.get("jti")
    if not isinstance(token_jti, str):
        return None
    now = datetime.now(timezone.utc)
    session = await db.scalar(select(RefreshSession).with_for_update().where(RefreshSession.user_id == user_id, RefreshSession.token_jti == token_jti, RefreshSession.revoked_at.is_(None), RefreshSession.expires_at > now))
    if not session:
        return None
    user = await db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    if not user:
        return None
    session.revoked_at = now
    session.last_used_at = now
    tokens = await create_auth_session(db, user_id)
    return user, tokens

async def revoke_refresh_session(db: AsyncSession, refresh_token: str) -> None:
    claims = decode_token_claims(refresh_token, "refresh")
    if not claims:
        return
    token_jti = claims.get("jti")
    if not isinstance(token_jti, str):
        return
    session = await db.scalar(select(RefreshSession).where(RefreshSession.token_jti == token_jti, RefreshSession.revoked_at.is_(None)))
    if session:
        session.revoked_at = datetime.now(timezone.utc)

async def signup(*, db: AsyncSession, email: str, password: str, display_name: str, organization_name: str) -> User:
    normalized_email = email.strip().lower()
    existing = await db.scalar(select(User).where(User.email == normalized_email))
    if existing:
        raise ValueError("Email is already registered")

    user = User(email=normalized_email, password_hash=hash_password(password), display_name=display_name)
    try:
        db.add(user)
        await db.flush()

        base_slug = slugify(organization_name)
        slug = base_slug
        for _ in range(5):
            if not await db.scalar(select(Organization.id).where(Organization.slug == slug)):
                break
            slug = f"{base_slug[:60]}-{uuid4().hex[:6]}"

        organization = Organization(name=organization_name, slug=slug)
        db.add(organization)
        await db.flush()
        db.add(Membership(organization_id=organization.id, user_id=user.id, role=MembershipRole.OWNER))
    except IntegrityError as exc:
        await db.rollback()
        raise ValueError(
            "Account could not be created because the submitted data conflicts with an existing account or workspace"
        ) from exc

    # The caller owns the transaction so account, organization, membership, and
    # authentication session are committed or rolled back together.
    return user

async def login(*, db: AsyncSession, email: str, password: str) -> User | None:
    normalized_email = email.strip().lower()
    user = await db.scalar(select(User).where(User.email == normalized_email))
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        return None
    return user
