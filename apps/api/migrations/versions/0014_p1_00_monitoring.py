"""p1 00 monitoring

Revision ID: 0014_p1_00_monitoring
Revises: 0013_p1_01_resource_multi_node
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0014_p1_00_monitoring"
down_revision: str | None = "0013_p1_01_resource_multi_node"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "run_monitoring_configs",
        sa.Column("run_id", sa.String(length=26), nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("disabled_reason", sa.Text(), nullable=True),
        sa.Column("influxdb_node_write_url", sa.Text(), nullable=True),
        sa.Column("dashboard_uid", sa.Text(), nullable=False),
        sa.Column("grafana_base_path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("length(run_id) = 26", name="ck_run_monitoring_configs_run_id_len"),
        sa.CheckConstraint(
            "length(workspace_id) = 26", name="ck_run_monitoring_configs_workspace_id_len"
        ),
        sa.CheckConstraint(
            "status in ('enabled', 'config_error')",
            name="ck_run_monitoring_configs_status",
        ),
        sa.CheckConstraint(
            "disabled_reason is null or disabled_reason in ('not_configured')",
            name="ck_run_monitoring_configs_disabled_reason",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index(
        "ix_run_monitoring_configs_workspace_run",
        "run_monitoring_configs",
        ["workspace_id", "run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_run_monitoring_configs_workspace_run", table_name="run_monitoring_configs")
    op.drop_table("run_monitoring_configs")
