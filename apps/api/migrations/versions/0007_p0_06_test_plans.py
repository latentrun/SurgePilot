"""P0-06 test plans and run now."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_p0_06"
down_revision = "0006_p0_05"
branch_labels = None
depends_on = None


def json_type() -> sa.types.TypeEngine:
    return postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "test_plans",
        sa.Column("id", sa.String(length=26), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags_json", json_type(), nullable=False),
        sa.Column("env_group_id", sa.String(length=26), nullable=True),
        sa.Column("run_mode", sa.Text(), nullable=False),
        sa.Column("pool_type", sa.Text(), nullable=True),
        sa.Column("selected_node_id", sa.String(length=26), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=26), nullable=False),
        sa.Column("updated_by", sa.String(length=26), nullable=False),
        sa.Column("deleted_by", sa.String(length=26), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("length(id) = 26", name="ck_test_plans_id_len"),
        sa.CheckConstraint("length(workspace_id) = 26", name="ck_test_plans_workspace_id_len"),
        sa.CheckConstraint("run_mode in ('sequential', 'parallel')", name="ck_test_plans_run_mode"),
        sa.CheckConstraint(
            "pool_type is null or pool_type in ('public', 'private')",
            name="ck_test_plans_pool_type",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_test_plans_revision"),
        sa.CheckConstraint("length(created_by) = 26", name="ck_test_plans_created_by_len"),
        sa.CheckConstraint("length(updated_by) = 26", name="ck_test_plans_updated_by_len"),
        sa.CheckConstraint(
            "deleted_by is null or length(deleted_by) = 26", name="ck_test_plans_deleted_by_len"
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["env_group_id"], ["env_groups.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["selected_node_id"], ["load_nodes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["deleted_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_test_plans_workspace_deleted_updated",
        "test_plans",
        ["workspace_id", "deleted_at", sa.text("updated_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_test_plans_workspace_name_lower",
        "test_plans",
        ["workspace_id", sa.text("lower(name)")],
    )
    op.create_index(
        "ix_test_plans_workspace_env_group", "test_plans", ["workspace_id", "env_group_id"]
    )
    op.create_index(
        "ix_test_plans_workspace_selected_node",
        "test_plans",
        ["workspace_id", "selected_node_id"],
    )

    op.create_table(
        "test_plan_scenario_items",
        sa.Column("id", sa.String(length=26), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("test_plan_id", sa.String(length=26), nullable=False),
        sa.Column("scenario_id", sa.String(length=26), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("concurrency_per_node", sa.Integer(), nullable=False),
        sa.Column("ramp_up_seconds", sa.Integer(), nullable=False),
        sa.Column("hold_for_seconds", sa.Integer(), nullable=True),
        sa.Column("iterations", sa.Integer(), nullable=True),
        sa.Column("target_rps", sa.Numeric(12, 3), nullable=True),
        sa.Column("steps", sa.Integer(), nullable=True),
        sa.Column("delay_seconds", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(id) = 26", name="ck_test_plan_scenario_items_id_len"),
        sa.CheckConstraint(
            "length(workspace_id) = 26", name="ck_test_plan_scenario_items_workspace_id_len"
        ),
        sa.CheckConstraint(
            "length(test_plan_id) = 26", name="ck_test_plan_scenario_items_plan_id_len"
        ),
        sa.CheckConstraint(
            "length(scenario_id) = 26", name="ck_test_plan_scenario_items_scenario_id_len"
        ),
        sa.CheckConstraint("position >= 0", name="ck_test_plan_scenario_items_position"),
        sa.CheckConstraint(
            "concurrency_per_node >= 1", name="ck_test_plan_scenario_items_concurrency"
        ),
        sa.CheckConstraint("ramp_up_seconds >= 0", name="ck_test_plan_scenario_items_ramp"),
        sa.CheckConstraint("delay_seconds >= 0", name="ck_test_plan_scenario_items_delay"),
        sa.CheckConstraint(
            "hold_for_seconds is null or hold_for_seconds > 0",
            name="ck_test_plan_scenario_items_hold",
        ),
        sa.CheckConstraint(
            "iterations is null or iterations > 0", name="ck_test_plan_scenario_items_iterations"
        ),
        sa.CheckConstraint(
            "target_rps is null or target_rps > 0", name="ck_test_plan_scenario_items_rps"
        ),
        sa.CheckConstraint("steps is null or steps > 0", name="ck_test_plan_scenario_items_steps"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["test_plan_id"], ["test_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scenario_id"], ["scenarios.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "uq_test_plan_scenario_items_plan_item",
        "test_plan_scenario_items",
        ["test_plan_id", "id"],
        unique=True,
    )
    op.create_index(
        "uq_test_plan_scenario_items_plan_position",
        "test_plan_scenario_items",
        ["test_plan_id", "position"],
        unique=True,
    )
    op.create_index(
        "ix_test_plan_scenario_items_workspace_scenario",
        "test_plan_scenario_items",
        ["workspace_id", "scenario_id"],
    )
    op.create_index(
        "ix_test_plan_scenario_items_workspace_plan",
        "test_plan_scenario_items",
        ["workspace_id", "test_plan_id"],
    )

    op.create_table(
        "test_plan_sla_rules",
        sa.Column("id", sa.String(length=26), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.String(length=26), nullable=False),
        sa.Column("test_plan_id", sa.String(length=26), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("condition", sa.Text(), nullable=False),
        sa.Column("threshold_value", sa.Numeric(12, 3), nullable=False),
        sa.Column("threshold_unit", sa.Text(), nullable=False),
        sa.Column("timeframe_logic", sa.Text(), nullable=True),
        sa.Column("timeframe_seconds", sa.Integer(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(id) = 26", name="ck_test_plan_sla_rules_id_len"),
        sa.CheckConstraint(
            "length(workspace_id) = 26", name="ck_test_plan_sla_rules_workspace_id_len"
        ),
        sa.CheckConstraint("length(test_plan_id) = 26", name="ck_test_plan_sla_rules_plan_id_len"),
        sa.CheckConstraint("position >= 0", name="ck_test_plan_sla_rules_position"),
        sa.CheckConstraint(
            "condition in ('gt', 'gte', 'lt', 'lte', 'eq')", name="ck_test_plan_sla_rules_condition"
        ),
        sa.CheckConstraint(
            "threshold_unit in ('ms', 's', 'percent', 'count', 'b', 'kb', 'mb')",
            name="ck_test_plan_sla_rules_threshold_unit",
        ),
        sa.CheckConstraint(
            "timeframe_logic is null or timeframe_logic in ('for', 'within')",
            name="ck_test_plan_sla_rules_timeframe_logic",
        ),
        sa.CheckConstraint("action in ('continue', 'stop')", name="ck_test_plan_sla_rules_action"),
        sa.CheckConstraint("threshold_value >= 0", name="ck_test_plan_sla_rules_threshold_value"),
        sa.CheckConstraint(
            "timeframe_seconds is null or timeframe_seconds > 0",
            name="ck_test_plan_sla_rules_timeframe_seconds",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["test_plan_id"], ["test_plans.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "uq_test_plan_sla_rules_plan_rule",
        "test_plan_sla_rules",
        ["test_plan_id", "id"],
        unique=True,
    )
    op.create_index(
        "uq_test_plan_sla_rules_plan_position",
        "test_plan_sla_rules",
        ["test_plan_id", "position"],
        unique=True,
    )
    op.create_index(
        "ix_test_plan_sla_rules_workspace_plan",
        "test_plan_sla_rules",
        ["workspace_id", "test_plan_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_test_plan_sla_rules_workspace_plan", table_name="test_plan_sla_rules")
    op.drop_index("uq_test_plan_sla_rules_plan_position", table_name="test_plan_sla_rules")
    op.drop_index("uq_test_plan_sla_rules_plan_rule", table_name="test_plan_sla_rules")
    op.drop_table("test_plan_sla_rules")
    op.drop_index(
        "ix_test_plan_scenario_items_workspace_plan", table_name="test_plan_scenario_items"
    )
    op.drop_index(
        "ix_test_plan_scenario_items_workspace_scenario", table_name="test_plan_scenario_items"
    )
    op.drop_index(
        "uq_test_plan_scenario_items_plan_position", table_name="test_plan_scenario_items"
    )
    op.drop_index("uq_test_plan_scenario_items_plan_item", table_name="test_plan_scenario_items")
    op.drop_table("test_plan_scenario_items")
    op.drop_index("ix_test_plans_workspace_selected_node", table_name="test_plans")
    op.drop_index("ix_test_plans_workspace_env_group", table_name="test_plans")
    op.drop_index("ix_test_plans_workspace_name_lower", table_name="test_plans")
    op.drop_index("ix_test_plans_workspace_deleted_updated", table_name="test_plans")
    op.drop_table("test_plans")
