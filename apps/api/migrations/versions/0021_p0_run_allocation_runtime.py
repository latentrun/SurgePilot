"""Persist the Runtime version expected by each Run allocation.

Revision ID: 0021_p0_run_allocation_runtime
Revises: 0020_p0_runtime_version
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0021_p0_run_allocation_runtime"
down_revision: str | None = "0020_p0_runtime_version"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    active_run_count = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT COUNT(*) FROM runs WHERE state IN ('initializing', 'running', 'stopping')"
            )
        )
        .scalar_one()
    )
    if active_run_count:
        raise RuntimeError(
            "Runtime identity migration cannot continue while active Runs exist. "
            "Finish or stop all Runs before upgrading."
        )
    op.add_column(
        "run_node_allocations",
        sa.Column("expected_runtime_version", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("run_node_allocations", "expected_runtime_version")
