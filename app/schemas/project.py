from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel

class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("name", "description")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value

class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("name", "description")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value

class ProjectResponse(ORMModel):
    id: UUID
    organization_id: UUID
    name: str
    key: str
    description: str | None

class EnvironmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    key: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    is_protected: bool = False

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()

class EnvironmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    is_protected: bool | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value

class EnvironmentResponse(ORMModel):
    id: UUID
    project_id: UUID
    name: str
    key: str
    is_protected: bool

class EnvironmentCreatedResponse(EnvironmentResponse):
    sdk_key: str

class EnvironmentKeyResponse(ORMModel):
    id: UUID
    name: str
    key_prefix: str
    revoked_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime

class EnvironmentKeyCreatedResponse(EnvironmentKeyResponse):
    sdk_key: str
