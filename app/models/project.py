from typing import TYPE_CHECKING
import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.feature_flags import EnvironmentKey, FlagEnvironmentState, FeatureFlag, Segment
    from app.models.organization import Organization

class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("organization_id", "key", name="uq_projects_organization_key"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship(back_populates="projects")
    environments: Mapped[list["Environment"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    feature_flags: Mapped[list["FeatureFlag"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    segments: Mapped[list["Segment"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )

class Environment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "environments"
    __table_args__ = (UniqueConstraint("project_id", "key", name="uq_environments_project_key"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    is_protected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    project: Mapped["Project"] = relationship(back_populates="environments")
    flag_states: Mapped[list["FlagEnvironmentState"]] = relationship(
        back_populates="environment", cascade="all, delete-orphan"
    )
    keys: Mapped[list["EnvironmentKey"]] = relationship(
        back_populates="environment", cascade="all, delete-orphan"
    )
