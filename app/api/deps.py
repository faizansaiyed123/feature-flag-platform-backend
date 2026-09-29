from collections.abc import Sequence
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.models.identity import User
from app.models.organization import Membership, MembershipRole
from app.models.project import Project
from app.security.tokens import decode_token

bearer_scheme = HTTPBearer(auto_error=False)

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    token = credentials.credentials if credentials else request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    subject = decode_token(token, "access")
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token")
    try:
        user_id = UUID(subject)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from exc
    user = await db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive or missing")
    return user

async def get_membership(organization_id: UUID, user: User, db: AsyncSession) -> Membership | None:
    return await db.scalar(select(Membership).where(Membership.organization_id == organization_id, Membership.user_id == user.id))

async def require_org_membership(
    organization_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Membership:
    membership = await get_membership(organization_id, user, db)
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return membership

def ensure_role(membership: Membership, allowed: Sequence[MembershipRole]) -> None:
    if membership.role not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient organization role")

async def require_project_access(
    project_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> tuple[Project, Membership]:
    project = await db.scalar(select(Project).where(Project.id == project_id))
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    membership = await get_membership(project.organization_id, user, db)
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project, membership

WRITE_ROLES = (MembershipRole.OWNER, MembershipRole.ADMIN, MembershipRole.MEMBER)
ADMIN_ROLES = (MembershipRole.OWNER, MembershipRole.ADMIN)
OWNER_ROLE = (MembershipRole.OWNER,)
