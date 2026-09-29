from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import ADMIN_ROLES, ensure_role, get_current_user, get_membership, require_org_membership
from app.db import get_db_session
from app.models.identity import User
from app.models.organization import Membership, MembershipRole, Organization
from app.schemas.organization import (
    MembershipDetailResponse, MembershipResponse, MembershipRoleUpdate,
    OrganizationCreate, OrganizationResponse, OrganizationUpdate,
)
from app.services.auth import slugify
from app.services.audit import record_audit

router = APIRouter(prefix="/organizations", tags=["organizations"])

@router.get("", response_model=list[OrganizationResponse])
async def list_organizations(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> list[Organization]:
    return list(await db.scalars(select(Organization).join(Membership, Membership.organization_id == Organization.id).where(Membership.user_id == user.id).order_by(Organization.name)))

@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(payload: OrganizationCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> Organization:
    base_slug = slugify(payload.name); slug = base_slug
    for _ in range(10):
        if not await db.scalar(select(Organization.id).where(Organization.slug == slug)):
            break
        slug = f"{base_slug[:60]}-{__import__('secrets').token_hex(4)}"
    organization = Organization(name=payload.name, slug=slug); db.add(organization); await db.flush()
    db.add(Membership(organization_id=organization.id, user_id=user.id, role=MembershipRole.OWNER))
    await record_audit(db=db, organization_id=organization.id, action="organization.created", entity_type="organization", entity_id=organization.id, actor_user_id=user.id)
    await db.commit(); await db.refresh(organization); return organization

@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization(organization_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> Organization:
    membership = await get_membership(organization_id, user, db)
    if not membership: raise HTTPException(status_code=404, detail="Organization not found")
    organization = await db.scalar(select(Organization).where(Organization.id == organization_id))
    if not organization: raise HTTPException(status_code=404, detail="Organization not found")
    return organization

@router.patch("/{organization_id}", response_model=OrganizationResponse)
async def update_organization(organization_id: UUID, payload: OrganizationUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> Organization:
    membership = await get_membership(organization_id, user, db)
    if not membership: raise HTTPException(status_code=404, detail="Organization not found")
    ensure_role(membership, ADMIN_ROLES)
    organization = await db.scalar(select(Organization).where(Organization.id == organization_id))
    if not organization: raise HTTPException(status_code=404, detail="Organization not found")
    for field, value in payload.model_dump(exclude_unset=True).items(): setattr(organization, field, value)
    await record_audit(db=db, organization_id=organization.id, action="organization.updated", entity_type="organization", entity_id=organization.id, actor_user_id=user.id, details=payload.model_dump(exclude_unset=True))
    await db.commit(); await db.refresh(organization); return organization

@router.get("/{organization_id}/members", response_model=list[MembershipDetailResponse])
async def list_members(organization_id: UUID, _: Membership = Depends(require_org_membership), db: AsyncSession = Depends(get_db_session)) -> list[MembershipDetailResponse]:
    memberships = list(await db.scalars(select(Membership).options(selectinload(Membership.user)).where(Membership.organization_id == organization_id).order_by(Membership.created_at)))
    return [MembershipDetailResponse(id=m.id, user_id=m.user_id, email=m.user.email, display_name=m.user.display_name, role=m.role) for m in memberships]

@router.patch("/{organization_id}/members/{user_id}", response_model=MembershipResponse)
async def update_member_role(organization_id: UUID, user_id: UUID, payload: MembershipRoleUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> Membership:
    actor = await get_membership(organization_id, user, db)
    if not actor: raise HTTPException(status_code=404, detail="Organization not found")
    ensure_role(actor, ADMIN_ROLES)
    target = await db.scalar(select(Membership).where(Membership.organization_id == organization_id, Membership.user_id == user_id))
    if not target: raise HTTPException(status_code=404, detail="Member not found")
    if target.role == MembershipRole.OWNER and payload.role != MembershipRole.OWNER:
        owner_count = await db.scalar(select(func.count()).select_from(Membership).where(Membership.organization_id == organization_id, Membership.role == MembershipRole.OWNER))
        if owner_count == 1: raise HTTPException(status_code=409, detail="Organization must retain an owner")
    target.role = payload.role
    await record_audit(db=db, organization_id=organization_id, action="membership.updated", entity_type="membership", entity_id=target.id, actor_user_id=user.id, details={"role": payload.role.value, "user_id": str(user_id)})
    await db.commit(); await db.refresh(target); return target

@router.delete("/{organization_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(organization_id: UUID, user_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> None:
    actor = await get_membership(organization_id, user, db)
    if not actor: raise HTTPException(status_code=404, detail="Organization not found")
    ensure_role(actor, ADMIN_ROLES)
    target = await db.scalar(select(Membership).where(Membership.organization_id == organization_id, Membership.user_id == user_id))
    if not target: raise HTTPException(status_code=404, detail="Member not found")
    if target.role == MembershipRole.OWNER:
        owner_count = await db.scalar(select(func.count()).select_from(Membership).where(Membership.organization_id == organization_id, Membership.role == MembershipRole.OWNER))
        if owner_count == 1: raise HTTPException(status_code=409, detail="Transfer ownership before removing the owner")
    await db.delete(target); await record_audit(db=db, organization_id=organization_id, action="membership.removed", entity_type="membership", entity_id=target.id, actor_user_id=user.id, details={"user_id": str(user_id)})
    try: await db.commit()
    except IntegrityError as exc:
        await db.rollback(); raise HTTPException(status_code=409, detail="Member could not be removed") from exc
