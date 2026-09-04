"""p0 00 auth workspace foundation

Revision ID: 0001_p0_00
Revises:
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_p0_00"
down_revision = None
branch_labels = None
depends_on = None

DEFAULT_WORKSPACE_ID = "01HZW000000000000000000000"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("role in ('admin', 'user')", name="ck_users_role"),
        sa.CheckConstraint("status in ('active')", name="ck_users_status"),
        sa.CheckConstraint("char_length(id) = 26", name="ck_users_id_len"),
        sa.CheckConstraint("char_length(email) <= 320", name="ck_users_email_len"),
        sa.CheckConstraint(
            "char_length(display_name) >= 1 and char_length(display_name) <= 120",
            name="ck_users_display_name_len",
        ),
    )
    op.create_unique_constraint("uq_users_email", "users", ["email"])

    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
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
        sa.CheckConstraint("status in ('active')", name="ck_workspaces_status"),
        sa.CheckConstraint("char_length(id) = 26", name="ck_workspaces_id_len"),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("session_token_hash", sa.Text(), nullable=False),
        sa.Column(
            "user_id",
            sa.String(length=26),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("csrf_token_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("char_length(id) = 26", name="ck_sessions_id_len"),
    )
    op.create_unique_constraint("uq_sessions_token_hash", "sessions", ["session_token_hash"])
    op.create_index("ix_sessions_user_active", "sessions", ["user_id", "revoked_at", "expires_at"])

    op.create_table(
        "workspace_members",
        sa.Column(
            "workspace_id",
            sa.String(length=26),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=26),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.PrimaryKeyConstraint("workspace_id", "user_id"),
    )
    op.create_index("ix_workspace_members_user_id", "workspace_members", ["user_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column(
            "workspace_id", sa.String(length=26), sa.ForeignKey("workspaces.id"), nullable=True
        ),
        sa.Column("actor_user_id", sa.String(length=26), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=True),
        sa.Column("target_id", sa.String(length=26), nullable=True),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "details_json",
            postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("char_length(id) = 26", name="ck_audit_events_id_len"),
    )
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])
    op.create_index("ix_audit_events_actor_user_id", "audit_events", ["actor_user_id"])
    op.create_index("ix_audit_events_workspace_id", "audit_events", ["workspace_id"])

    op.execute(
        sa.text(
            """
            INSERT INTO workspaces (id, name, status)
            VALUES (:id, 'Default Workspace', 'active')
            ON CONFLICT (id) DO NOTHING
            """
        ).bindparams(id=DEFAULT_WORKSPACE_ID)
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("workspace_members")
    op.drop_table("sessions")
    op.drop_table("workspaces")
    op.drop_table("users")
