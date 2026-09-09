"""p1 03 workspace admin

Revision ID: 0011_p1_03
Revises: 0010_p1_debug_http_trace
"""

from alembic import op
import json
import os

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0011_p1_03"
down_revision = "0010_p1_debug_http_trace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.drop_constraint("ck_users_status", type_="check")
        batch_op.create_check_constraint("ck_users_status", "status in ('active', 'disabled')")

    with op.batch_alter_table("workspaces") as batch_op:
        batch_op.add_column(sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.drop_constraint("ck_workspaces_status", type_="check")
        batch_op.create_check_constraint("ck_workspaces_status", "status in ('active', 'archived')")

    op.create_index(
        "uq_workspaces_active_name_ci",
        "workspaces",
        [sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )

    json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")
    op.create_table(
        "system_settings",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value_json", json_type, nullable=False),
        sa.Column(
            "updated_by_user_id", sa.String(length=26), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    allow_signup = os.environ.get("ALLOW_SIGNUP", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text(
                "insert into system_settings (key, value_json, updated_at) "
                "values (:key, CAST(:value AS jsonb), now())"
            ),
            {"key": "allowSignup", "value": json.dumps(bool(allow_signup))},
        )
    else:
        bind.execute(
            sa.text(
                "insert into system_settings (key, value_json, updated_at) "
                "values (:key, :value, now())"
            ),
            {"key": "allowSignup", "value": bool(allow_signup)},
        )


def downgrade() -> None:
    op.drop_table("system_settings")
    op.drop_index("uq_workspaces_active_name_ci", table_name="workspaces")
    with op.batch_alter_table("workspaces") as batch_op:
        batch_op.drop_constraint("ck_workspaces_status", type_="check")
        batch_op.create_check_constraint("ck_workspaces_status", "status in ('active')")
        batch_op.drop_column("archived_at")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("ck_users_status", type_="check")
        batch_op.create_check_constraint("ck_users_status", "status in ('active')")
        batch_op.drop_column("disabled_at")
