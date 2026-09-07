"""P0-05 visual scenarios and debug run dedup."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_p0_05"
down_revision = "0005_p0_04"
branch_labels = None
depends_on = None


def json_type() -> sa.types.TypeEngine:
    return postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "scenarios",
        sa.Column("id", sa.String(length=26), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("scenario_type", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags_json", json_type(), nullable=False),
        sa.Column("base_url_expression", sa.Text(), nullable=False),
        sa.Column("default_settings_json", json_type(), nullable=False),
        sa.Column("data_sources_json", json_type(), nullable=False),
        sa.Column("steps_json", json_type(), nullable=False),
        sa.Column("visual_schema_version", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=26), nullable=False),
        sa.Column("updated_by_user_id", sa.String(length=26), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(id) = 26", name="ck_scenarios_id_len"),
        sa.CheckConstraint("length(workspace_id) = 26", name="ck_scenarios_workspace_id_len"),
        sa.CheckConstraint("scenario_type in ('visual')", name="ck_scenarios_type"),
        sa.CheckConstraint("visual_schema_version = 1", name="ck_scenarios_visual_schema_version"),
        sa.CheckConstraint("revision >= 1", name="ck_scenarios_revision"),
        sa.CheckConstraint("length(created_by_user_id) = 26", name="ck_scenarios_created_by_len"),
        sa.CheckConstraint("length(updated_by_user_id) = 26", name="ck_scenarios_updated_by_len"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_scenarios_workspace_deleted_updated",
        "scenarios",
        ["workspace_id", "deleted_at", sa.text("updated_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_scenarios_workspace_name_lower",
        "scenarios",
        ["workspace_id", sa.text("lower(name)")],
    )
    op.create_table(
        "scenario_dependency_file_refs",
        sa.Column("id", sa.String(length=26), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("scenario_id", sa.String(length=26), nullable=False),
        sa.Column("dependency_file_id", sa.String(length=26), nullable=False),
        sa.Column("ref_type", sa.Text(), nullable=False),
        sa.Column("step_id", sa.String(length=26), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(id) = 26", name="ck_scenario_dependency_file_refs_id_len"),
        sa.CheckConstraint(
            "length(workspace_id) = 26", name="ck_scenario_dependency_file_refs_workspace_id_len"
        ),
        sa.CheckConstraint(
            "length(scenario_id) = 26", name="ck_scenario_dependency_file_refs_scenario_id_len"
        ),
        sa.CheckConstraint(
            "length(dependency_file_id) = 26",
            name="ck_scenario_dependency_file_refs_dependency_file_id_len",
        ),
        sa.CheckConstraint(
            "ref_type in ('data_source', 'upload_file')",
            name="ck_scenario_dependency_file_refs_type",
        ),
        sa.CheckConstraint(
            "step_id is null or length(step_id) = 26",
            name="ck_scenario_dependency_file_refs_step_id_len",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scenario_id"], ["scenarios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["dependency_file_id"], ["dependency_files.id"], ondelete="RESTRICT"
        ),
    )
    op.create_index(
        "uq_scenario_dependency_file_refs_scenario_file_type_step",
        "scenario_dependency_file_refs",
        ["scenario_id", "dependency_file_id", "ref_type", "step_id"],
        unique=True,
    )
    op.create_index(
        "ix_scenario_dependency_file_refs_workspace_file",
        "scenario_dependency_file_refs",
        ["workspace_id", "dependency_file_id"],
    )
    op.create_index(
        "ix_scenario_dependency_file_refs_workspace_scenario",
        "scenario_dependency_file_refs",
        ["workspace_id", "scenario_id"],
    )
    op.create_table(
        "run_creation_dedup_keys",
        sa.Column("id", sa.String(length=26), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("dedup_key_hash", sa.Text(), nullable=False),
        sa.Column("run_id", sa.String(length=26), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(id) = 26", name="ck_run_creation_dedup_keys_id_len"),
        sa.CheckConstraint(
            "length(workspace_id) = 26", name="ck_run_creation_dedup_keys_workspace_id_len"
        ),
        sa.CheckConstraint("length(run_id) = 26", name="ck_run_creation_dedup_keys_run_id_len"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "uq_run_creation_dedup_keys_workspace_hash",
        "run_creation_dedup_keys",
        ["workspace_id", "dedup_key_hash"],
        unique=True,
    )
    op.create_index("ix_run_creation_dedup_keys_expires", "run_creation_dedup_keys", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_run_creation_dedup_keys_expires", table_name="run_creation_dedup_keys")
    op.drop_index("uq_run_creation_dedup_keys_workspace_hash", table_name="run_creation_dedup_keys")
    op.drop_table("run_creation_dedup_keys")
    op.drop_index(
        "ix_scenario_dependency_file_refs_workspace_scenario",
        table_name="scenario_dependency_file_refs",
    )
    op.drop_index(
        "ix_scenario_dependency_file_refs_workspace_file",
        table_name="scenario_dependency_file_refs",
    )
    op.drop_index(
        "uq_scenario_dependency_file_refs_scenario_file_type_step",
        table_name="scenario_dependency_file_refs",
    )
    op.drop_table("scenario_dependency_file_refs")
    op.drop_index("ix_scenarios_workspace_name_lower", table_name="scenarios")
    op.drop_index("ix_scenarios_workspace_deleted_updated", table_name="scenarios")
    op.drop_table("scenarios")
