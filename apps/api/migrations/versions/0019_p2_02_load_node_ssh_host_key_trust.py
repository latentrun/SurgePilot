"""Add node-level SSH host key trust fields.

Revision ID: 0019_p2_02_ssh_host_key
Revises: 0018_p1_09_scenario_global_configuration
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0019_p2_02_ssh_host_key"
down_revision: str | None = "0018_p1_09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("load_nodes", sa.Column("ssh_host_key_algorithm", sa.Text(), nullable=True))
    op.add_column("load_nodes", sa.Column("ssh_host_key_public_key", sa.Text(), nullable=True))
    op.add_column(
        "load_nodes", sa.Column("ssh_host_key_fingerprint_sha256", sa.Text(), nullable=True)
    )
    op.add_column(
        "load_nodes",
        sa.Column("ssh_host_key_trusted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "load_nodes", sa.Column("ssh_host_key_trusted_by", sa.String(length=26), nullable=True)
    )
    op.create_foreign_key(
        "fk_load_nodes_ssh_host_key_trusted_by",
        "load_nodes",
        "users",
        ["ssh_host_key_trusted_by"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        "update load_nodes set status = 'uninitialized', last_status_reason = "
        "'LOAD_NODE_SSH_HOST_KEY_UNTRUSTED' where archived_at is null and status <> 'disabled'"
    )


def downgrade() -> None:
    op.drop_constraint("fk_load_nodes_ssh_host_key_trusted_by", "load_nodes", type_="foreignkey")
    op.drop_column("load_nodes", "ssh_host_key_trusted_by")
    op.drop_column("load_nodes", "ssh_host_key_trusted_at")
    op.drop_column("load_nodes", "ssh_host_key_fingerprint_sha256")
    op.drop_column("load_nodes", "ssh_host_key_public_key")
    op.drop_column("load_nodes", "ssh_host_key_algorithm")
