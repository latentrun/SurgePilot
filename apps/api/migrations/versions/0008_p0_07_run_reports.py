"""P0-07 run reports, artifacts, and validity."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_p0_07"
down_revision = "0007_p0_06"
branch_labels = None
depends_on = None


def json_type() -> sa.types.TypeEngine:
    return postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    op.add_column(
        "runs",
        sa.Column(
            "sla_result",
            sa.Text(),
            nullable=False,
            server_default="not_evaluated",
        ),
    )
    op.add_column("runs", sa.Column("sla_result_reason", sa.Text(), nullable=True))
    op.add_column(
        "runs",
        sa.Column("validity_updated_by_user_id", sa.String(length=26), nullable=True),
    )
    op.add_column(
        "runs", sa.Column("validity_updated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute("delete from run_artifacts where artifact_type = 'failed_requests_csv'")
    op.execute(
        "update runs set validity = case when run_type = 'debug' then 'invalid' else 'valid' end "
        "where validity is null"
    )
    artifact_type_check = (
        "artifact_type in ('taurus_log', 'jmeter_log', 'final_stats_csv', "
        "'run_log', 'artifacts_zip')"
    )
    if dialect == "sqlite":
        with op.batch_alter_table("run_artifacts", recreate="always") as batch_op:
            batch_op.drop_constraint("ck_run_artifacts_artifact_type", type_="check")
            batch_op.create_check_constraint(
                "ck_run_artifacts_artifact_type",
                artifact_type_check,
            )
    else:
        op.create_foreign_key(
            "fk_runs_validity_updated_by_user_id",
            "runs",
            "users",
            ["validity_updated_by_user_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        op.create_check_constraint(
            "ck_runs_sla_result",
            "runs",
            "sla_result in ('passed', 'failed', 'not_evaluated')",
        )
        op.create_check_constraint(
            "ck_runs_validity_updated_by_user_id_len",
            "runs",
            "validity_updated_by_user_id is null or length(validity_updated_by_user_id) = 26",
        )
        op.drop_constraint("ck_run_artifacts_artifact_type", "run_artifacts", type_="check")
        op.create_check_constraint(
            "ck_run_artifacts_artifact_type",
            "run_artifacts",
            artifact_type_check,
        )

    op.create_table(
        "run_report_summaries",
        sa.Column("id", sa.String(length=26), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("run_id", sa.String(length=26), nullable=False),
        sa.Column("source_artifact_id", sa.String(length=26), nullable=False),
        sa.Column("summary_type", sa.Text(), nullable=False),
        sa.Column("summary_json", json_type(), nullable=False),
        sa.Column("truncated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("parse_status", sa.Text(), nullable=False),
        sa.Column("parse_error_code", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(id) = 26", name="ck_run_report_summaries_id_len"),
        sa.CheckConstraint(
            "length(workspace_id) = 26", name="ck_run_report_summaries_workspace_id_len"
        ),
        sa.CheckConstraint("length(run_id) = 26", name="ck_run_report_summaries_run_id_len"),
        sa.CheckConstraint(
            "length(source_artifact_id) = 26",
            name="ck_run_report_summaries_source_artifact_id_len",
        ),
        sa.CheckConstraint("summary_type in ('final_stats')", name="ck_run_report_summaries_type"),
        sa.CheckConstraint(
            "parse_status in ('pending', 'parsed', 'failed')",
            name="ck_run_report_summaries_parse_status",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_artifact_id"], ["run_artifacts.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "uq_run_report_summaries_run_artifact_type",
        "run_report_summaries",
        ["run_id", "source_artifact_id", "summary_type"],
        unique=True,
    )
    op.create_index(
        "ix_run_report_summaries_workspace_run_type",
        "run_report_summaries",
        ["workspace_id", "run_id", "summary_type"],
    )
    op.create_index(
        "ix_run_report_summaries_status_created",
        "run_report_summaries",
        ["parse_status", "created_at"],
    )


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    op.drop_index("ix_run_report_summaries_status_created", table_name="run_report_summaries")
    op.drop_index("ix_run_report_summaries_workspace_run_type", table_name="run_report_summaries")
    op.drop_index("uq_run_report_summaries_run_artifact_type", table_name="run_report_summaries")
    op.drop_table("run_report_summaries")
    op.execute("delete from run_artifacts where artifact_type = 'artifacts_zip'")
    downgrade_artifact_type_check = (
        "artifact_type in ('taurus_log', 'jmeter_log', 'final_stats_csv', "
        "'failed_requests_csv', 'run_log')"
    )
    if dialect == "sqlite":
        with op.batch_alter_table("run_artifacts", recreate="always") as batch_op:
            batch_op.drop_constraint("ck_run_artifacts_artifact_type", type_="check")
            batch_op.create_check_constraint(
                "ck_run_artifacts_artifact_type",
                downgrade_artifact_type_check,
            )
    else:
        op.drop_constraint("ck_run_artifacts_artifact_type", "run_artifacts", type_="check")
        op.create_check_constraint(
            "ck_run_artifacts_artifact_type",
            "run_artifacts",
            downgrade_artifact_type_check,
        )
        op.drop_constraint("ck_runs_validity_updated_by_user_id_len", "runs", type_="check")
        op.drop_constraint("ck_runs_sla_result", "runs", type_="check")
        op.drop_constraint("fk_runs_validity_updated_by_user_id", "runs", type_="foreignkey")
    op.drop_column("runs", "validity_updated_at")
    op.drop_column("runs", "validity_updated_by_user_id")
    op.drop_column("runs", "sla_result_reason")
    op.drop_column("runs", "sla_result")
