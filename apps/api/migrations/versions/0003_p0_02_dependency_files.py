"""P0-02 dependency files metadata."""

from alembic import op
import sqlalchemy as sa

revision = "0003_p0_02"
down_revision = "0002_p0_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dependency_files",
        sa.Column("id", sa.String(length=26), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_bucket", sa.Text(), nullable=False),
        sa.Column("storage_object_key", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=26), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_by", sa.String(length=26), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(id) = 26", name="ck_dependency_files_id_len"),
        sa.CheckConstraint(
            "length(workspace_id) = 26", name="ck_dependency_files_workspace_id_len"
        ),
        sa.CheckConstraint("length(created_by) = 26", name="ck_dependency_files_created_by_len"),
        sa.CheckConstraint(
            "deleted_by is null or length(deleted_by) = 26",
            name="ck_dependency_files_deleted_by_len",
        ),
        sa.CheckConstraint("status in ('available', 'deleted')", name="ck_dependency_files_status"),
        sa.CheckConstraint("size_bytes >= 0", name="ck_dependency_files_size_bytes_non_negative"),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_dependency_files_sha256_hex"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "uq_dependency_files_workspace_filename_active_lower",
        "dependency_files",
        ["workspace_id", sa.text("lower(filename)")],
        unique=True,
        postgresql_where=sa.text("status = 'available'"),
    )
    op.create_index(
        "ix_dependency_files_workspace_status_created",
        "dependency_files",
        ["workspace_id", "status", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_dependency_files_workspace_status_filename_lower",
        "dependency_files",
        ["workspace_id", "status", sa.text("lower(filename)")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dependency_files_workspace_status_filename_lower", table_name="dependency_files"
    )
    op.drop_index("ix_dependency_files_workspace_status_created", table_name="dependency_files")
    op.drop_index(
        "uq_dependency_files_workspace_filename_active_lower", table_name="dependency_files"
    )
    op.drop_table("dependency_files")
