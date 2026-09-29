from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feature_flags import AuditLog

async def record_audit(*, db: AsyncSession, organization_id: UUID, action: str, entity_type: str, actor_user_id: UUID | None, entity_id: UUID | str | None = None, project_id: UUID | None = None, details: dict[str, Any] | None = None) -> AuditLog:
    audit = AuditLog(
        organization_id=organization_id,
        project_id=project_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        details=details or {},
    )
    db.add(audit)
    await db.flush()
    return audit
