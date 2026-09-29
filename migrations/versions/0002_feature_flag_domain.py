"""Add feature flags, targeting, segments, SDK keys, and audit history.

Revision ID: 0002_feature_flag_domain
Revises: 0001_initial_domain
Create Date: 2026-09-29
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_feature_flag_domain"
down_revision: Union[str, None] = "0001_initial_domain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _common():
    return [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)]

def upgrade() -> None:
    common = _common()
    op.create_table("feature_flags", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("key", sa.String(120), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("description", sa.Text()), sa.Column("flag_type", sa.String(20), server_default="boolean", nullable=False), sa.Column("is_archived", sa.Boolean(), server_default=sa.text("false"), nullable=False), sa.Column("created_by", postgresql.UUID(as_uuid=True)), *common, sa.ForeignKeyConstraint(["project_id"],["projects.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["created_by"],["users.id"],ondelete="SET NULL"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("project_id","key"))
    op.create_index("ix_feature_flags_project_id","feature_flags",["project_id"])
    op.create_index("ix_feature_flags_created_by","feature_flags",["created_by"])
    op.create_table("flag_environment_states", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("flag_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("environment_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False), sa.Column("default_value", sa.JSON(), nullable=False), sa.Column("version", sa.Integer(), server_default="1", nullable=False), *common, sa.ForeignKeyConstraint(["flag_id"],["feature_flags.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["environment_id"],["environments.id"],ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("flag_id","environment_id"))
    op.create_index("ix_flag_environment_states_flag_id","flag_environment_states",["flag_id"]); op.create_index("ix_flag_environment_states_environment_id","flag_environment_states",["environment_id"])
    op.create_table("targeting_rules", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("flag_environment_state_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("priority", sa.Integer(), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("conditions", sa.JSON(), nullable=False), sa.Column("segment_keys", sa.JSON(), nullable=False), sa.Column("rollout_percentage", sa.Integer()), sa.Column("serve_value", sa.JSON(), nullable=False), sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False), *common, sa.ForeignKeyConstraint(["flag_environment_state_id"],["flag_environment_states.id"],ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("flag_environment_state_id","priority"))
    op.create_index("ix_targeting_rules_state_id","targeting_rules",["flag_environment_state_id"])
    op.create_table("segments", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("key", sa.String(120), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("description", sa.Text()), sa.Column("conditions", sa.JSON(), nullable=False), *common, sa.ForeignKeyConstraint(["project_id"],["projects.id"],ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("project_id","key"))
    op.create_index("ix_segments_project_id","segments",["project_id"])
    op.create_table("environment_keys", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("environment_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.Column("key_prefix", sa.String(20), nullable=False), sa.Column("key_hash", sa.String(64), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True)), sa.Column("last_used_at", sa.DateTime(timezone=True)), *common, sa.ForeignKeyConstraint(["environment_id"],["environments.id"],ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("key_hash"))
    op.create_index("ix_environment_keys_environment_id","environment_keys",["environment_id"])
    op.create_table("audit_logs", sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("project_id", postgresql.UUID(as_uuid=True)), sa.Column("actor_user_id", postgresql.UUID(as_uuid=True)), sa.Column("action", sa.String(80), nullable=False), sa.Column("entity_type", sa.String(80), nullable=False), sa.Column("entity_id", sa.String(80)), sa.Column("metadata", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.ForeignKeyConstraint(["organization_id"],["organizations.id"],ondelete="CASCADE"), sa.ForeignKeyConstraint(["project_id"],["projects.id"],ondelete="SET NULL"), sa.ForeignKeyConstraint(["actor_user_id"],["users.id"],ondelete="SET NULL"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_audit_logs_organization_id","audit_logs",["organization_id"]); op.create_index("ix_audit_logs_project_id","audit_logs",["project_id"]); op.create_index("ix_audit_logs_actor_user_id","audit_logs",["actor_user_id"]); op.create_index("ix_audit_logs_action","audit_logs",["action"]); op.create_index("ix_audit_logs_created_at","audit_logs",["created_at"])

def downgrade() -> None:
    for index, table in [("ix_audit_logs_created_at","audit_logs"),("ix_audit_logs_action","audit_logs"),("ix_audit_logs_actor_user_id","audit_logs"),("ix_audit_logs_project_id","audit_logs"),("ix_audit_logs_organization_id","audit_logs"),("ix_environment_keys_environment_id","environment_keys"),("ix_segments_project_id","segments"),("ix_targeting_rules_state_id","targeting_rules"),("ix_flag_environment_states_environment_id","flag_environment_states"),("ix_flag_environment_states_flag_id","flag_environment_states"),("ix_feature_flags_created_by","feature_flags"),("ix_feature_flags_project_id","feature_flags")]:
        op.drop_index(index, table_name=table)
    for table in ["audit_logs","environment_keys","segments","targeting_rules","flag_environment_states","feature_flags"]:
        op.drop_table(table)
