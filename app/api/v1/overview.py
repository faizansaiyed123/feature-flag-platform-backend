from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_project_access
from app.db import get_db_session
from app.models.feature_flags import AuditLog, FeatureFlag, FlagEnvironmentState, Segment, TargetingRule
from app.models.organization import Membership
from app.models.project import Environment, Project
from app.schemas.overview import AuditLogResponse, ProjectOverviewResponse

router = APIRouter(tags=["overview"])

@router.get("/projects/{project_id}/overview", response_model=ProjectOverviewResponse)
async def project_overview(access: tuple[Project, Membership] = Depends(require_project_access), db: AsyncSession = Depends(get_db_session)) -> ProjectOverviewResponse:
    project, _ = access
    environments = await db.scalar(select(func.count()).select_from(Environment).where(Environment.project_id == project.id)) or 0
    flags = await db.scalar(select(func.count()).select_from(FeatureFlag).where(FeatureFlag.project_id == project.id, FeatureFlag.is_archived.is_(False))) or 0
    enabled_flags = await db.scalar(select(func.count(func.distinct(FlagEnvironmentState.flag_id))).join(FeatureFlag, FeatureFlag.id == FlagEnvironmentState.flag_id).where(FeatureFlag.project_id == project.id, FeatureFlag.is_archived.is_(False), FlagEnvironmentState.enabled.is_(True))) or 0
    segments = await db.scalar(select(func.count()).select_from(Segment).where(Segment.project_id == project.id)) or 0
    targeting_rules = await db.scalar(select(func.count()).select_from(TargetingRule).join(FlagEnvironmentState, TargetingRule.flag_environment_state_id == FlagEnvironmentState.id).join(FeatureFlag, FlagEnvironmentState.flag_id == FeatureFlag.id).where(FeatureFlag.project_id == project.id)) or 0
    audits = list(await db.scalars(select(AuditLog).where(AuditLog.project_id == project.id).order_by(AuditLog.created_at.desc()).limit(12)))
    return ProjectOverviewResponse(
        project_id=project.id,
        environments=environments,
        flags=flags,
        enabled_flags=enabled_flags,
        segments=segments,
        targeting_rules=targeting_rules,
        recent_audit=[AuditLogResponse.model_validate(audit) for audit in audits],
    )

@router.get("/projects/{project_id}/audit-logs", response_model=list[AuditLogResponse])
async def project_audit_logs(
    project_id: UUID,
    limit: int = 50,
    access: tuple[Project, Membership] = Depends(require_project_access),
    db: AsyncSession = Depends(get_db_session),
) -> list[AuditLog]:
    project, _ = access
    limit = max(1, min(limit, 200))
    return list(await db.scalars(select(AuditLog).where(AuditLog.project_id == project.id).order_by(AuditLog.created_at.desc()).limit(limit)))
