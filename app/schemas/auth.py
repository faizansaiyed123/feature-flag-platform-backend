from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import ORMModel

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=2, max_length=120)
    organization_name: str = Field(min_length=2, max_length=160)

    @field_validator("display_name", "organization_name", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

class UserResponse(ORMModel):
    id: UUID
    email: EmailStr
    display_name: str
    is_active: bool

class AuthResponse(BaseModel):
    user: UserResponse
