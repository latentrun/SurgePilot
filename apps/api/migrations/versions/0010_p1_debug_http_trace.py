"""P1 debug HTTP trace artifact type."""

from alembic import op

revision = "0010_p1_debug_http_trace"
down_revision = "0009_p0_08"
branch_labels = None
depends_on = None

P1_CHECK = (
    "artifact_type in ('taurus_log', 'jmeter_log', 'final_stats_csv', "
    "'run_log', 'artifacts_zip', 'debug_http_trace', 'debug_http_body_blob')"
)
P0_CHECK = (
    "artifact_type in ('taurus_log', 'jmeter_log', 'final_stats_csv', 'run_log', 'artifacts_zip')"
)


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    if dialect == "sqlite":
        with op.batch_alter_table("run_artifacts", recreate="always") as batch_op:
            batch_op.drop_constraint("ck_run_artifacts_artifact_type", type_="check")
            batch_op.create_check_constraint("ck_run_artifacts_artifact_type", P1_CHECK)
    else:
        op.drop_constraint("ck_run_artifacts_artifact_type", "run_artifacts", type_="check")
        op.create_check_constraint("ck_run_artifacts_artifact_type", "run_artifacts", P1_CHECK)


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    op.execute(
        "delete from run_artifacts where artifact_type in ('debug_http_trace', 'debug_http_body_blob')"
    )
    if dialect == "sqlite":
        with op.batch_alter_table("run_artifacts", recreate="always") as batch_op:
            batch_op.drop_constraint("ck_run_artifacts_artifact_type", type_="check")
            batch_op.create_check_constraint("ck_run_artifacts_artifact_type", P0_CHECK)
    else:
        op.drop_constraint("ck_run_artifacts_artifact_type", "run_artifacts", type_="check")
        op.create_check_constraint("ck_run_artifacts_artifact_type", "run_artifacts", P0_CHECK)
