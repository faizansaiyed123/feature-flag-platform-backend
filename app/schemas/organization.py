from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.organization import MembershipRole
from app.schemas.common import ORMModel

class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()

class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value

class OrganizationResponse(ORMModel):
    id: UUID
    name: str
    slug: str

class MembershipResponse(ORMModel):
    id: UUID
    user_id: UUID
    role: MembershipRole

class MembershipDetailResponse(BaseModel):
    id: UUID
    user_id: UUID
    email: str
    display_name: str
    role: MembershipRole

class MembershipRoleUpdate(BaseModel):
    role: MembershipRole
