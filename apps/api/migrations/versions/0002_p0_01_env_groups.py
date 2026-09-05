"""p0 01 env groups

Revision ID: 0002_p0_01
Revises: 0001_p0_00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_p0_01"
down_revision = "0001_p0_00"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "env_groups",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(length=26),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "variables",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_by",
            sa.String(length=26),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "updated_by",
            sa.String(length=26),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("char_length(id) = 26", name="ck_env_groups_id_len"),
        sa.CheckConstraint("char_length(workspace_id) = 26", name="ck_env_groups_workspace_id_len"),
        sa.CheckConstraint("char_length(created_by) = 26", name="ck_env_groups_created_by_len"),
        sa.CheckConstraint("char_length(updated_by) = 26", name="ck_env_groups_updated_by_len"),
        sa.CheckConstraint(
            "jsonb_typeof(variables) = 'object'", name="ck_env_groups_variables_object"
        ),
    )
    op.create_index(
        "uq_env_groups_workspace_name_lower",
        "env_groups",
        ["workspace_id", sa.text("lower(name)")],
        unique=True,
    )
    op.create_index(
        "ix_env_groups_workspace_created",
        "env_groups",
        ["workspace_id", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_env_groups_workspace_updated",
        "env_groups",
        ["workspace_id", sa.text("updated_at DESC"), sa.text("id DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_env_groups_workspace_updated", table_name="env_groups")
    op.drop_index("ix_env_groups_workspace_created", table_name="env_groups")
    op.drop_index("uq_env_groups_workspace_name_lower", table_name="env_groups")
    op.drop_table("env_groups")
