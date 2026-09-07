from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base


class Scenario(Base):
    __tablename__ = "scenarios"
    __table_args__ = (
        CheckConstraint("length(id) = 26", name="ck_scenarios_id_len"),
        CheckConstraint("length(workspace_id) = 26", name="ck_scenarios_workspace_id_len"),
        CheckConstraint("scenario_type in ('visual')", name="ck_scenarios_type"),
        CheckConstraint("visual_schema_version = 1", name="ck_scenarios_visual_schema_version"),
        CheckConstraint("revision >= 1", name="ck_scenarios_revision"),
        CheckConstraint("length(created_by_user_id) = 26", name="ck_scenarios_created_by_len"),
        CheckConstraint("length(updated_by_user_id) = 26", name="ck_scenarios_updated_by_len"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    scenario_type: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    tags_json: Mapped[list[str]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=list
    )
    base_url_expression: Mapped[str] = mapped_column(Text, nullable=False)
    default_settings_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False
    )
    data_sources_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=list
    )
    steps_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=list
    )
    visual_schema_version: Mapped[int] = mapped_column(nullable=False, default=1)
    revision: Mapped[int] = mapped_column(nullable=False, default=1)
    created_by_user_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by_user_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)


Index(
    "ix_scenarios_workspace_deleted_updated",
    Scenario.workspace_id,
    Scenario.deleted_at,
    Scenario.updated_at.desc(),
    Scenario.id.desc(),
)
Index("ix_scenarios_workspace_name_lower", Scenario.workspace_id, func.lower(Scenario.name))


class ScenarioDependencyFileRef(Base):
    __tablename__ = "scenario_dependency_file_refs"
    __table_args__ = (
        CheckConstraint("length(id) = 26", name="ck_scenario_dependency_file_refs_id_len"),
        CheckConstraint(
            "length(workspace_id) = 26", name="ck_scenario_dependency_file_refs_workspace_id_len"
        ),
        CheckConstraint(
            "length(scenario_id) = 26", name="ck_scenario_dependency_file_refs_scenario_id_len"
        ),
        CheckConstraint(
            "length(dependency_file_id) = 26",
            name="ck_scenario_dependency_file_refs_dependency_file_id_len",
        ),
        CheckConstraint(
            "ref_type in ('data_source', 'upload_file')",
            name="ck_scenario_dependency_file_refs_type",
        ),
        CheckConstraint(
            "step_id is null or length(step_id) = 26",
            name="ck_scenario_dependency_file_refs_step_id_len",
        ),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    scenario_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False
    )
    dependency_file_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("dependency_files.id", ondelete="RESTRICT"), nullable=False
    )
    ref_type: Mapped[str] = mapped_column(Text, nullable=False)
    step_id: Mapped[str | None] = mapped_column(String(26))
    created_at: Mapped[datetime] = mapped_column(nullable=False)


Index(
    "uq_scenario_dependency_file_refs_scenario_file_type_step",
    ScenarioDependencyFileRef.scenario_id,
    ScenarioDependencyFileRef.dependency_file_id,
    ScenarioDependencyFileRef.ref_type,
    ScenarioDependencyFileRef.step_id,
    unique=True,
)
Index(
    "ix_scenario_dependency_file_refs_workspace_file",
    ScenarioDependencyFileRef.workspace_id,
    ScenarioDependencyFileRef.dependency_file_id,
)
Index(
    "ix_scenario_dependency_file_refs_workspace_scenario",
    ScenarioDependencyFileRef.workspace_id,
    ScenarioDependencyFileRef.scenario_id,
)


class RunCreationDedupKey(Base):
    __tablename__ = "run_creation_dedup_keys"
    __table_args__ = (
        CheckConstraint("length(id) = 26", name="ck_run_creation_dedup_keys_id_len"),
        CheckConstraint(
            "length(workspace_id) = 26", name="ck_run_creation_dedup_keys_workspace_id_len"
        ),
        CheckConstraint("length(run_id) = 26", name="ck_run_creation_dedup_keys_run_id_len"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    dedup_key_hash: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)


Index(
    "uq_run_creation_dedup_keys_workspace_hash",
    RunCreationDedupKey.workspace_id,
    RunCreationDedupKey.dedup_key_hash,
    unique=True,
)
Index("ix_run_creation_dedup_keys_expires", RunCreationDedupKey.expires_at)
