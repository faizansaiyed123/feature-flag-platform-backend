from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

class AuditLogResponse(BaseModel):
    id: UUID
    action: str
    entity_type: str
    entity_id: str | None
    details: dict
    actor_user_id: UUID | None
    created_at: datetime

class ProjectOverviewResponse(BaseModel):
    project_id: UUID
    environments: int
    flags: int
    enabled_flags: int
    segments: int
    targeting_rules: int
    recent_audit: list[AuditLogResponse]
