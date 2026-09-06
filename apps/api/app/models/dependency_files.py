from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DependencyFile(Base):
    __tablename__ = "dependency_files"
    __table_args__ = (
        CheckConstraint("length(id) = 26", name="ck_dependency_files_id_len"),
        CheckConstraint("length(workspace_id) = 26", name="ck_dependency_files_workspace_id_len"),
        CheckConstraint("length(created_by) = 26", name="ck_dependency_files_created_by_len"),
        CheckConstraint(
            "deleted_by is null or length(deleted_by) = 26",
            name="ck_dependency_files_deleted_by_len",
        ),
        CheckConstraint("status in ('available', 'deleted')", name="ck_dependency_files_status"),
        CheckConstraint("size_bytes >= 0", name="ck_dependency_files_size_bytes_non_negative"),
        CheckConstraint(
            "length(sha256) = 64",
            name="ck_dependency_files_sha256_len",
        ),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_bucket: Mapped[str] = mapped_column(Text, nullable=False)
    storage_object_key: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="available")
    created_by: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    deleted_by: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="RESTRICT")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)


Index(
    "uq_dependency_files_workspace_filename_active_lower",
    DependencyFile.workspace_id,
    func.lower(DependencyFile.filename),
    unique=True,
    sqlite_where=DependencyFile.status == "available",
    postgresql_where=DependencyFile.status == "available",
)
Index(
    "ix_dependency_files_workspace_status_created",
    DependencyFile.workspace_id,
    DependencyFile.status,
    DependencyFile.created_at.desc(),
    DependencyFile.id.desc(),
)
Index(
    "ix_dependency_files_workspace_status_filename_lower",
    DependencyFile.workspace_id,
    DependencyFile.status,
    func.lower(DependencyFile.filename),
)
