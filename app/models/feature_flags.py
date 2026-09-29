from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
import uuid

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.identity import User
    from app.models.project import Environment, Project

class FlagType(StrEnum):
    BOOLEAN = "boolean"
    STRING = "string"
    NUMBER = "number"
    JSON = "json"

class FeatureFlag(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "feature_flags"
    __table_args__ = (UniqueConstraint("project_id", "key", name="uq_feature_flags_project_key"),)

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    flag_type: Mapped[FlagType] = mapped_column(SAEnum(FlagType, name="flag_type", native_enum=False), nullable=False, default=FlagType.BOOLEAN, server_default=FlagType.BOOLEAN.value)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    project: Mapped["Project"] = relationship(back_populates="feature_flags")
    creator: Mapped["User | None"] = relationship(foreign_keys=[created_by])
    environment_states: Mapped[list["FlagEnvironmentState"]] = relationship(back_populates="flag", cascade="all, delete-orphan")

class FlagEnvironmentState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "flag_environment_states"
    __table_args__ = (UniqueConstraint("flag_id", "environment_id", name="uq_flag_environment_state"),)

    flag_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("feature_flags.id", ondelete="CASCADE"), nullable=False, index=True)
    environment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("environments.id", ondelete="CASCADE"), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    default_value: Mapped[Any] = mapped_column(JSON, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    flag: Mapped["FeatureFlag"] = relationship(back_populates="environment_states")
    environment: Mapped["Environment"] = relationship(back_populates="flag_states")
    targeting_rules: Mapped[list["TargetingRule"]] = relationship(back_populates="state", cascade="all, delete-orphan", order_by="TargetingRule.priority")

class TargetingRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "targeting_rules"
    __table_args__ = (UniqueConstraint("flag_environment_state_id", "priority", name="uq_targeting_rule_priority"),)

    flag_environment_state_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("flag_environment_states.id", ondelete="CASCADE"), nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    conditions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    segment_keys: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    rollout_percentage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    serve_value: Mapped[Any] = mapped_column(JSON, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    state: Mapped["FlagEnvironmentState"] = relationship(back_populates="targeting_rules")

class Segment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "segments"
    __table_args__ = (UniqueConstraint("project_id", "key", name="uq_segments_project_key"),)

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    conditions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)

    project: Mapped["Project"] = relationship(back_populates="segments")

class EnvironmentKey(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "environment_keys"

    environment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("environments.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    environment: Mapped["Environment"] = relationship(back_populates="keys")

class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"

    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="CURRENT_TIMESTAMP", index=True)
