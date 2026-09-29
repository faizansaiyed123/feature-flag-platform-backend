import re
from uuid import UUID, uuid4

from fastapi import Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.identity import User
from app.models.organization import Membership, MembershipRole, Organization
from app.security.passwords import hash_password, verify_password
from app.security.tokens import create_access_token, create_refresh_token, decode_token

def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:70] or f"workspace-{uuid4().hex[:8]}"

def set_auth_cookies(response: Response, user_id: str) -> None:
    settings = get_settings()
    secure = settings.app_env == "production"
    samesite = settings.auth_cookie_samesite
    response.set_cookie("access_token", create_access_token(user_id), httponly=True, secure=secure, samesite=samesite, max_age=60 * settings.access_token_expire_minutes, path="/")
    response.set_cookie("refresh_token", create_refresh_token(user_id), httponly=True, secure=secure, samesite=samesite, max_age=60 * 60 * 24 * settings.refresh_token_expire_days, path="/api/v1/auth")

def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/v1/auth")

async def signup(*, db: AsyncSession, email: str, password: str, display_name: str, organization_name: str) -> User:
    normalized_email = email.strip().lower()
    existing = await db.scalar(select(User).where(User.email == normalized_email))
    if existing:
        raise ValueError("Email is already registered")
    user = User(email=normalized_email, password_hash=hash_password(password), display_name=display_name)
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
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ValueError("Account could not be created because the submitted data conflicts with an existing account") from exc
    await db.refresh(user)
    return user

async def login(*, db: AsyncSession, email: str, password: str) -> User | None:
    normalized_email = email.strip().lower()
    user = await db.scalar(select(User).where(User.email == normalized_email))
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        return None
    return user

async def refresh_user(*, db: AsyncSession, token: str) -> User | None:
    subject = decode_token(token, "refresh")
    if not subject:
        return None
    try:
        user_id = UUID(subject)
    except ValueError:
        return None
    return await db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
