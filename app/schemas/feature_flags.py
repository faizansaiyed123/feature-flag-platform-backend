from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.feature_flags import FlagType
from app.schemas.common import ORMModel

class ConditionOperator(StrEnum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    EXISTS = "exists"

class Condition(BaseModel):
    attribute: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9_.-]+$")
    operator: ConditionOperator
    value: Any = None

    @model_validator(mode="after")
    def require_value_when_needed(self) -> "Condition":
        if self.operator == ConditionOperator.EXISTS:
            if not isinstance(self.value, bool):
                raise ValueError("exists conditions require a boolean value")
        elif self.value is None:
            raise ValueError(f"{self.operator.value} conditions require a value")
        return self

class FeatureFlagCreate(BaseModel):
    key: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    flag_type: FlagType = FlagType.BOOLEAN
    default_value: Any = False

    @field_validator("name", "description")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value

class FeatureFlagUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    is_archived: bool | None = None

    @field_validator("name", "description")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value

class EnvironmentStateUpdate(BaseModel):
    enabled: bool
    default_value: Any

class TargetingRuleCreate(BaseModel):
    priority: int | None = Field(default=None, ge=1, le=1_000_000)
    name: str = Field(min_length=2, max_length=160)
    conditions: list[Condition] = Field(default_factory=list, max_length=20)
    segment_keys: list[str] = Field(default_factory=list, max_length=20)
    rollout_percentage: int | None = Field(default=None, ge=1, le=100)
    serve_value: Any
    is_enabled: bool = True

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()

class TargetingRuleUpdate(BaseModel):
    priority: int | None = Field(default=None, ge=1, le=1_000_000)
    name: str | None = Field(default=None, min_length=2, max_length=160)
    conditions: list[Condition] | None = Field(default=None, max_length=20)
    segment_keys: list[str] | None = Field(default=None, max_length=20)
    rollout_percentage: int | None = Field(default=None, ge=1, le=100)
    serve_value: Any | None = None
    is_enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value

class SegmentCreate(BaseModel):
    key: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    conditions: list[Condition] = Field(default_factory=list, max_length=20)

    @field_validator("name", "description")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value

class SegmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    conditions: list[Condition] | None = Field(default=None, max_length=20)

    @field_validator("name", "description")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value

class SegmentResponse(ORMModel):
    id: UUID
    project_id: UUID
    key: str
    name: str
    description: str | None
    conditions: list[Condition]

class TargetingRuleResponse(ORMModel):
    id: UUID
    flag_environment_state_id: UUID
    priority: int
    name: str
    conditions: list[Condition]
    segment_keys: list[str]
    rollout_percentage: int | None
    serve_value: Any
    is_enabled: bool

class EnvironmentFlagStateResponse(ORMModel):
    id: UUID
    environment_id: UUID
    enabled: bool
    default_value: Any
    version: int
    targeting_rules: list[TargetingRuleResponse]

class FeatureFlagResponse(ORMModel):
    id: UUID
    project_id: UUID
    key: str
    name: str
    description: str | None
    flag_type: FlagType
    is_archived: bool
    environment_states: list[EnvironmentFlagStateResponse]

class EvaluationRequest(BaseModel):
    user_id: str | None = Field(default=None, max_length=200)
    attributes: dict[str, Any] = Field(default_factory=dict)

class EvaluationResult(BaseModel):
    flag_key: str
    value: Any
    reason: str
    matched_rule_id: UUID | None = None
    version: int

class BatchEvaluationRequest(EvaluationRequest):
    flag_keys: list[str] = Field(min_length=1, max_length=100)

class BatchEvaluationResponse(BaseModel):
    environment_key: str
    evaluations: list[EvaluationResult]

class SimulationRequest(BaseModel):
    environment_id: UUID
    flag_key: str = Field(min_length=2, max_length=120)
    users: list[EvaluationRequest] = Field(min_length=1, max_length=1000)

class SimulationRow(BaseModel):
    user_id: str | None
    value: Any
    reason: str
    matched_rule_id: UUID | None

class SimulationResponse(BaseModel):
    flag_key: str
    environment_key: str
    version: int
    results: list[SimulationRow]
