"""Establish identity, organization, project, and environment tables.

Revision ID: 0001_initial_domain
Revises:
Create Date: 2026-09-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_domain"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    role = postgresql.ENUM("owner", "admin", "member", "viewer", name="membership_role")
    role.create(op.get_bind(), checkfirst=True)
    ts = lambda: [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)]
    op.create_table("users", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("email", sa.String(320), nullable=False), sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("display_name", sa.String(120), nullable=False), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False), *ts(), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("email"))
    op.create_table("organizations", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("slug", sa.String(80), nullable=False), *ts(), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("slug"))
    op.create_table("memberships", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("role", role, nullable=False), *ts(), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("organization_id","user_id"))
    op.create_index("ix_memberships_organization_id","memberships",["organization_id"]); op.create_index("ix_memberships_user_id","memberships",["user_id"])
    op.create_table("projects", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("key", sa.String(80), nullable=False), sa.Column("description", sa.Text(), nullable=True), *ts(), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("organization_id","key"))
    op.create_index("ix_projects_organization_id","projects",["organization_id"])
    op.create_table("environments", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.Column("key", sa.String(80), nullable=False), sa.Column("is_protected", sa.Boolean(), server_default=sa.text("false"), nullable=False), *ts(), sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("project_id","key"))
    op.create_index("ix_environments_project_id","environments",["project_id"])

def downgrade() -> None:
    op.drop_index("ix_environments_project_id", table_name="environments"); op.drop_table("environments")
    op.drop_index("ix_projects_organization_id", table_name="projects"); op.drop_table("projects")
    op.drop_index("ix_memberships_user_id", table_name="memberships"); op.drop_index("ix_memberships_organization_id", table_name="memberships"); op.drop_table("memberships")
    op.drop_table("organizations"); op.drop_table("users")
    postgresql.ENUM("owner","admin","member","viewer",name="membership_role").drop(op.get_bind(), checkfirst=True)
