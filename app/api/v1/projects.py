from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ADMIN_ROLES, WRITE_ROLES, ensure_role, get_current_user, get_membership, require_project_access
from app.db import get_db_session
from app.models.feature_flags import EnvironmentKey
from app.models.identity import User
from app.models.organization import Membership
from app.models.project import Environment, Project
from app.schemas.project import (
    EnvironmentCreatedResponse, EnvironmentCreate, EnvironmentKeyCreatedResponse,
    EnvironmentKeyResponse, EnvironmentResponse, EnvironmentUpdate,
    ProjectCreate, ProjectResponse, ProjectUpdate,
)
from app.services.audit import record_audit
from app.services.credentials import hash_sdk_key, issue_sdk_key

router = APIRouter(tags=["projects"])

@router.get("/organizations/{organization_id}/projects", response_model=list[ProjectResponse])
async def list_projects(organization_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> list[Project]:
    membership = await get_membership(organization_id, user, db)
    if not membership:
        raise HTTPException(status_code=404, detail="Organization not found")
    return list(await db.scalars(select(Project).where(Project.organization_id == organization_id).order_by(Project.name)))

@router.post("/organizations/{organization_id}/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(organization_id: UUID, payload: ProjectCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> Project:
    membership = await get_membership(organization_id, user, db)
    if not membership:
        raise HTTPException(status_code=404, detail="Organization not found")
    ensure_role(membership, WRITE_ROLES)
    project = Project(organization_id=organization_id, name=payload.name, key=payload.key, description=payload.description)
    db.add(project)
    try:
        await db.flush()
        await record_audit(db=db, organization_id=organization_id, project_id=project.id, action="project.created", entity_type="project", entity_id=project.id, actor_user_id=user.id)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Project key already exists") from exc
    await db.refresh(project)
    return project

@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(access: tuple[Project, Membership] = Depends(require_project_access)) -> Project:
    return access[0]

@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(payload: ProjectUpdate, access: tuple[Project, Membership] = Depends(require_project_access), db: AsyncSession = Depends(get_db_session)) -> Project:
    project, membership = access
    ensure_role(membership, WRITE_ROLES)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await record_audit(db=db, organization_id=project.organization_id, project_id=project.id, action="project.updated", entity_type="project", entity_id=project.id, actor_user_id=membership.user_id, details=payload.model_dump(exclude_unset=True))
    await db.commit()
    await db.refresh(project)
    return project

@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(access: tuple[Project, Membership] = Depends(require_project_access), db: AsyncSession = Depends(get_db_session)) -> None:
    project, membership = access
    ensure_role(membership, ADMIN_ROLES)
    await db.delete(project)
    await record_audit(db=db, organization_id=project.organization_id, project_id=project.id, action="project.deleted", entity_type="project", entity_id=project.id, actor_user_id=membership.user_id)
    await db.commit()

@router.get("/projects/{project_id}/environments", response_model=list[EnvironmentResponse])
async def list_environments(access: tuple[Project, Membership] = Depends(require_project_access), db: AsyncSession = Depends(get_db_session)) -> list[Environment]:
    project, _ = access
    return list(await db.scalars(select(Environment).where(Environment.project_id == project.id).order_by(Environment.name)))

@router.post("/projects/{project_id}/environments", response_model=EnvironmentCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_environment(payload: EnvironmentCreate, access: tuple[Project, Membership] = Depends(require_project_access), db: AsyncSession = Depends(get_db_session)) -> EnvironmentCreatedResponse:
    project, membership = access
    ensure_role(membership, WRITE_ROLES)
    environment = Environment(project_id=project.id, name=payload.name, key=payload.key, is_protected=payload.is_protected)
    db.add(environment)
    try:
        await db.flush()
        raw_key = await issue_sdk_key(db=db, environment_id=environment.id, name="Initial SDK key", revoke_existing=False)
        await record_audit(db=db, organization_id=project.organization_id, project_id=project.id, action="environment.created", entity_type="environment", entity_id=environment.id, actor_user_id=membership.user_id)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Environment key already exists") from exc
    await db.refresh(environment)
    return EnvironmentCreatedResponse.model_validate(environment).model_copy(update={"sdk_key": raw_key})

@router.get("/environments/{environment_id}", response_model=EnvironmentResponse)
async def get_environment(environment_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> Environment:
    environment = await db.scalar(select(Environment).where(Environment.id == environment_id))
    if not environment:
        raise HTTPException(status_code=404, detail="Environment not found")
    project = await db.scalar(select(Project).where(Project.id == environment.project_id))
    membership = await get_membership(project.organization_id, user, db) if project else None
    if not membership:
        raise HTTPException(status_code=404, detail="Environment not found")
    return environment

@router.patch("/environments/{environment_id}", response_model=EnvironmentResponse)
async def update_environment(environment_id: UUID, payload: EnvironmentUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> Environment:
    environment = await db.scalar(select(Environment).where(Environment.id == environment_id))
    if not environment:
        raise HTTPException(status_code=404, detail="Environment not found")
    project = await db.scalar(select(Project).where(Project.id == environment.project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Environment not found")
    membership = await get_membership(project.organization_id, user, db)
    if not membership:
        raise HTTPException(status_code=404, detail="Environment not found")
    ensure_role(membership, WRITE_ROLES)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(environment, field, value)
    await record_audit(db=db, organization_id=project.organization_id, project_id=project.id, action="environment.updated", entity_type="environment", entity_id=environment.id, actor_user_id=user.id, details=payload.model_dump(exclude_unset=True))
    await db.commit()
    await db.refresh(environment)
    return environment

@router.delete("/environments/{environment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_environment(environment_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> None:
    environment = await db.scalar(select(Environment).where(Environment.id == environment_id))
    if not environment:
        raise HTTPException(status_code=404, detail="Environment not found")
    project = await db.scalar(select(Project).where(Project.id == environment.project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Environment not found")
    membership = await get_membership(project.organization_id, user, db)
    if not membership:
        raise HTTPException(status_code=404, detail="Environment not found")
    ensure_role(membership, ADMIN_ROLES)
    await db.delete(environment)
    await record_audit(db=db, organization_id=project.organization_id, project_id=project.id, action="environment.deleted", entity_type="environment", entity_id=environment.id, actor_user_id=user.id)
    await db.commit()

@router.get("/environments/{environment_id}/keys", response_model=list[EnvironmentKeyResponse])
async def list_environment_keys(environment_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> list[EnvironmentKey]:
    environment = await db.scalar(select(Environment).where(Environment.id == environment_id))
    if not environment:
        raise HTTPException(status_code=404, detail="Environment not found")
    project = await db.scalar(select(Project).where(Project.id == environment.project_id))
    membership = await get_membership(project.organization_id, user, db) if project else None
    if not membership:
        raise HTTPException(status_code=404, detail="Environment not found")
    return list(await db.scalars(select(EnvironmentKey).where(EnvironmentKey.environment_id == environment_id).order_by(EnvironmentKey.created_at.desc())))

@router.post("/environments/{environment_id}/keys/rotate", response_model=EnvironmentKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def rotate_environment_key(environment_id: UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)) -> EnvironmentKeyCreatedResponse:
    environment = await db.scalar(select(Environment).where(Environment.id == environment_id))
    if not environment:
        raise HTTPException(status_code=404, detail="Environment not found")
    project = await db.scalar(select(Project).where(Project.id == environment.project_id))
    membership = await get_membership(project.organization_id, user, db) if project else None
    if not membership:
        raise HTTPException(status_code=404, detail="Environment not found")
    ensure_role(membership, ADMIN_ROLES)
    raw_key = await issue_sdk_key(db=db, environment_id=environment_id, name="Rotated SDK key", revoke_existing=True)
    await db.commit()
    created = await db.scalar(select(EnvironmentKey).where(EnvironmentKey.key_hash == hash_sdk_key(raw_key)))
    assert created is not None
    return EnvironmentKeyCreatedResponse.model_validate(created).model_copy(update={"sdk_key": raw_key})
