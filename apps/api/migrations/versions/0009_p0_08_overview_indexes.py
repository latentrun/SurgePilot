"""P0-08 overview query indexes."""

from alembic import op
import sqlalchemy as sa

revision = "0009_p0_08"
down_revision = "0008_p0_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_runs_workspace_type_validity_state_created",
        "runs",
        ["workspace_id", "run_type", "validity", "state", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_runs_workspace_type_validity_state_created", table_name="runs")
