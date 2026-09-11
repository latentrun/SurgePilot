from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ApiCatalogSpec(Base):
    __tablename__ = "api_catalog_specs"
    __table_args__ = (
        CheckConstraint("length(id) = 26", name="ck_api_catalog_specs_id_len"),
        CheckConstraint("length(workspace_id) = 26", name="ck_api_catalog_specs_workspace_id_len"),
        CheckConstraint("length(created_by) = 26", name="ck_api_catalog_specs_created_by_len"),
        CheckConstraint(
            "deleted_by is null or length(deleted_by) = 26",
            name="ck_api_catalog_specs_deleted_by_len",
        ),
        CheckConstraint(
            "source_format in ('openapi_json', 'openapi_yaml', 'swagger_json', 'swagger_yaml')",
            name="ck_api_catalog_specs_source_format",
        ),
        CheckConstraint(
            "status in ('available', 'invalid', 'storage_unavailable', 'deleted')",
            name="ck_api_catalog_specs_status",
        ),
        CheckConstraint("size_bytes >= 0", name="ck_api_catalog_specs_size_bytes_non_negative"),
        CheckConstraint("length(sha256) = 64", name="ck_api_catalog_specs_sha256_len"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(Text)
    source_format: Mapped[str] = mapped_column(Text, nullable=False)
    openapi_version: Mapped[str] = mapped_column(Text, nullable=False)
    document_title: Mapped[str] = mapped_column(Text, nullable=False)
    document_version: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="available")
    validation_message: Mapped[str | None] = mapped_column(Text)
    storage_bucket: Mapped[str] = mapped_column(Text, nullable=False)
    storage_object_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)
    deleted_by: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="RESTRICT")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)


Index(
    "ix_api_catalog_specs_workspace_status_created",
    ApiCatalogSpec.workspace_id,
    ApiCatalogSpec.status,
    ApiCatalogSpec.created_at.desc(),
    ApiCatalogSpec.id.desc(),
)
Index(
    "ix_api_catalog_specs_workspace_status_name_lower",
    ApiCatalogSpec.workspace_id,
    ApiCatalogSpec.status,
    func.lower(ApiCatalogSpec.name),
)
