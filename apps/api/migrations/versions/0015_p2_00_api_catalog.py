"""P2-00 API Catalog spec assets."""

from alembic import op
import sqlalchemy as sa

revision = "0015_p2_00"
down_revision = "0014_p1_00_monitoring"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_catalog_specs",
        sa.Column("id", sa.String(length=26), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("source_format", sa.Text(), nullable=False),
        sa.Column("openapi_version", sa.Text(), nullable=False),
        sa.Column("document_title", sa.Text(), nullable=False),
        sa.Column("document_version", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("validation_message", sa.Text(), nullable=True),
        sa.Column("storage_bucket", sa.Text(), nullable=False),
        sa.Column("storage_object_key", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=26), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_by", sa.String(length=26), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(id) = 26", name="ck_api_catalog_specs_id_len"),
        sa.CheckConstraint(
            "length(workspace_id) = 26", name="ck_api_catalog_specs_workspace_id_len"
        ),
        sa.CheckConstraint("length(created_by) = 26", name="ck_api_catalog_specs_created_by_len"),
        sa.CheckConstraint(
            "deleted_by is null or length(deleted_by) = 26",
            name="ck_api_catalog_specs_deleted_by_len",
        ),
        sa.CheckConstraint(
            "source_format in ('openapi_json', 'openapi_yaml', 'swagger_json', 'swagger_yaml')",
            name="ck_api_catalog_specs_source_format",
        ),
        sa.CheckConstraint(
            "status in ('available', 'invalid', 'storage_unavailable', 'deleted')",
            name="ck_api_catalog_specs_status",
        ),
        sa.CheckConstraint("size_bytes >= 0", name="ck_api_catalog_specs_size_bytes_non_negative"),
        sa.CheckConstraint("length(sha256) = 64", name="ck_api_catalog_specs_sha256_len"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_api_catalog_specs_workspace_status_created",
        "api_catalog_specs",
        ["workspace_id", "status", sa.text("created_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_api_catalog_specs_workspace_status_name_lower",
        "api_catalog_specs",
        ["workspace_id", "status", sa.text("lower(name)")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_api_catalog_specs_workspace_status_name_lower", table_name="api_catalog_specs"
    )
    op.drop_index("ix_api_catalog_specs_workspace_status_created", table_name="api_catalog_specs")
    op.drop_table("api_catalog_specs")
