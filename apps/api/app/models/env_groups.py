from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base


class EnvGroup(Base):
    __tablename__ = "env_groups"
    __table_args__ = (
        CheckConstraint("length(id) = 26", name="ck_env_groups_id_len"),
        CheckConstraint("length(workspace_id) = 26", name="ck_env_groups_workspace_id_len"),
        CheckConstraint("length(created_by) = 26", name="ck_env_groups_created_by_len"),
        CheckConstraint("length(updated_by) = 26", name="ck_env_groups_updated_by_len"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    variables: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=dict
    )
    created_by: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)


Index(
    "uq_env_groups_workspace_name_lower",
    EnvGroup.workspace_id,
    func.lower(EnvGroup.name),
    unique=True,
)
Index(
    "ix_env_groups_workspace_created",
    EnvGroup.workspace_id,
    EnvGroup.created_at.desc(),
    EnvGroup.id.desc(),
)
Index(
    "ix_env_groups_workspace_updated",
    EnvGroup.workspace_id,
    EnvGroup.updated_at.desc(),
    EnvGroup.id.desc(),
)
