"""Persist activated Runtime versions for Load Nodes.

Revision ID: 0020_p0_runtime_version
Revises: 0019_p2_02_ssh_host_key
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0020_p0_runtime_version"
down_revision: str | None = "0019_p2_02_ssh_host_key"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("load_nodes", sa.Column("runtime_version", sa.Text(), nullable=True))
    op.add_column(
        "load_node_initialization_attempts",
        sa.Column("runtime_version", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("load_node_initialization_attempts", "runtime_version")
    op.drop_column("load_nodes", "runtime_version")
