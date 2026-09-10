from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base

TEST_PLAN_RUN_MODES = ("sequential", "parallel")
TEST_PLAN_POOL_TYPES = ("public", "private")
SLA_CONDITIONS = ("gt", "gte", "lt", "lte", "eq")
SLA_THRESHOLD_UNITS = ("ms", "s", "percent", "count", "b", "kb", "mb")
SLA_TIMEFRAME_LOGICS = ("for", "within")
SLA_ACTIONS = ("continue", "stop")


class TestPlan(Base):
    __tablename__ = "test_plans"
    __table_args__ = (
        CheckConstraint("length(id) = 26", name="ck_test_plans_id_len"),
        CheckConstraint("length(workspace_id) = 26", name="ck_test_plans_workspace_id_len"),
        CheckConstraint("run_mode in ('sequential', 'parallel')", name="ck_test_plans_run_mode"),
        CheckConstraint(
            "pool_type is null or pool_type in ('public', 'private')",
            name="ck_test_plans_pool_type",
        ),
        CheckConstraint("revision >= 1", name="ck_test_plans_revision"),
        CheckConstraint("length(created_by) = 26", name="ck_test_plans_created_by_len"),
        CheckConstraint("length(updated_by) = 26", name="ck_test_plans_updated_by_len"),
        CheckConstraint(
            "deleted_by is null or length(deleted_by) = 26",
            name="ck_test_plans_deleted_by_len",
        ),
        CheckConstraint(
            "env_group_id is null or length(env_group_id) = 26",
            name="ck_test_plans_env_group_id_len",
        ),
        CheckConstraint(
            "selected_node_id is null or length(selected_node_id) = 26",
            name="ck_test_plans_selected_node_id_len",
        ),
        CheckConstraint("resource_mode in ('manual', 'auto')", name="ck_test_plans_resource_mode"),
        CheckConstraint("node_count is null or node_count > 0", name="ck_test_plans_node_count"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    tags_json: Mapped[list[str]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=list
    )
    env_group_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("env_groups.id", ondelete="RESTRICT")
    )
    run_mode: Mapped[str] = mapped_column(Text, nullable=False)
    pool_type: Mapped[str | None] = mapped_column(Text)
    selected_node_id: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("load_nodes.id", ondelete="RESTRICT")
    )
    resource_mode: Mapped[str] = mapped_column(Text, nullable=False, default="manual")
    selected_node_ids_json: Mapped[list[str]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=list
    )
    node_count: Mapped[int | None] = mapped_column(nullable=True)
    revision: Mapped[int] = mapped_column(nullable=False, default=1)
    created_by: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    deleted_by: Mapped[str | None] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)

    scenario_items: Mapped[list["TestPlanScenarioItem"]] = relationship(
        back_populates="test_plan", cascade="all, delete-orphan"
    )
    sla_rules: Mapped[list["TestPlanSlaRule"]] = relationship(
        back_populates="test_plan", cascade="all, delete-orphan"
    )


Index(
    "ix_test_plans_workspace_deleted_updated",
    TestPlan.workspace_id,
    TestPlan.deleted_at,
    TestPlan.updated_at.desc(),
    TestPlan.id.desc(),
)
Index("ix_test_plans_workspace_name_lower", TestPlan.workspace_id, func.lower(TestPlan.name))
Index("ix_test_plans_workspace_env_group", TestPlan.workspace_id, TestPlan.env_group_id)
Index("ix_test_plans_workspace_selected_node", TestPlan.workspace_id, TestPlan.selected_node_id)


class TestPlanScenarioItem(Base):
    __tablename__ = "test_plan_scenario_items"
    __table_args__ = (
        CheckConstraint("length(id) = 26", name="ck_test_plan_scenario_items_id_len"),
        CheckConstraint(
            "length(workspace_id) = 26", name="ck_test_plan_scenario_items_workspace_id_len"
        ),
        CheckConstraint(
            "length(test_plan_id) = 26", name="ck_test_plan_scenario_items_plan_id_len"
        ),
        CheckConstraint(
            "length(scenario_id) = 26", name="ck_test_plan_scenario_items_scenario_id_len"
        ),
        CheckConstraint("position >= 0", name="ck_test_plan_scenario_items_position"),
        CheckConstraint(
            "concurrency_per_node >= 1", name="ck_test_plan_scenario_items_concurrency"
        ),
        CheckConstraint("ramp_up_seconds >= 0", name="ck_test_plan_scenario_items_ramp"),
        CheckConstraint("delay_seconds >= 0", name="ck_test_plan_scenario_items_delay"),
        CheckConstraint(
            "hold_for_seconds is null or hold_for_seconds > 0",
            name="ck_test_plan_scenario_items_hold",
        ),
        CheckConstraint(
            "iterations is null or iterations > 0", name="ck_test_plan_scenario_items_iterations"
        ),
        CheckConstraint(
            "target_rps is null or target_rps > 0", name="ck_test_plan_scenario_items_rps"
        ),
        CheckConstraint("steps is null or steps > 0", name="ck_test_plan_scenario_items_steps"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    test_plan_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("test_plans.id", ondelete="CASCADE"), nullable=False
    )
    scenario_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("scenarios.id", ondelete="RESTRICT"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    position: Mapped[int] = mapped_column(nullable=False)
    concurrency_per_node: Mapped[int] = mapped_column(nullable=False)
    ramp_up_seconds: Mapped[int] = mapped_column(nullable=False, default=0)
    hold_for_seconds: Mapped[int | None] = mapped_column(nullable=True)
    iterations: Mapped[int | None] = mapped_column(nullable=True)
    target_rps: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    steps: Mapped[int | None] = mapped_column(nullable=True)
    delay_seconds: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)

    test_plan: Mapped[TestPlan] = relationship(back_populates="scenario_items")


Index(
    "uq_test_plan_scenario_items_plan_item",
    TestPlanScenarioItem.test_plan_id,
    TestPlanScenarioItem.id,
    unique=True,
)
Index(
    "uq_test_plan_scenario_items_plan_position",
    TestPlanScenarioItem.test_plan_id,
    TestPlanScenarioItem.position,
    unique=True,
)
Index(
    "ix_test_plan_scenario_items_workspace_scenario",
    TestPlanScenarioItem.workspace_id,
    TestPlanScenarioItem.scenario_id,
)
Index(
    "ix_test_plan_scenario_items_workspace_plan",
    TestPlanScenarioItem.workspace_id,
    TestPlanScenarioItem.test_plan_id,
)


class TestPlanSlaRule(Base):
    __tablename__ = "test_plan_sla_rules"
    __table_args__ = (
        CheckConstraint("length(id) = 26", name="ck_test_plan_sla_rules_id_len"),
        CheckConstraint(
            "length(workspace_id) = 26", name="ck_test_plan_sla_rules_workspace_id_len"
        ),
        CheckConstraint("length(test_plan_id) = 26", name="ck_test_plan_sla_rules_plan_id_len"),
        CheckConstraint("position >= 0", name="ck_test_plan_sla_rules_position"),
        CheckConstraint(
            "condition in ('gt', 'gte', 'lt', 'lte', 'eq')",
            name="ck_test_plan_sla_rules_condition",
        ),
        CheckConstraint(
            "threshold_unit in ('ms', 's', 'percent', 'count', 'b', 'kb', 'mb')",
            name="ck_test_plan_sla_rules_threshold_unit",
        ),
        CheckConstraint(
            "timeframe_logic is null or timeframe_logic in ('for', 'within')",
            name="ck_test_plan_sla_rules_timeframe_logic",
        ),
        CheckConstraint("action in ('continue', 'stop')", name="ck_test_plan_sla_rules_action"),
        CheckConstraint("threshold_value >= 0", name="ck_test_plan_sla_rules_threshold_value"),
        CheckConstraint(
            "timeframe_seconds is null or timeframe_seconds > 0",
            name="ck_test_plan_sla_rules_timeframe_seconds",
        ),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    test_plan_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("test_plans.id", ondelete="CASCADE"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    position: Mapped[int] = mapped_column(nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(Text)
    condition: Mapped[str] = mapped_column(Text, nullable=False)
    threshold_value: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    threshold_unit: Mapped[str] = mapped_column(Text, nullable=False)
    timeframe_logic: Mapped[str | None] = mapped_column(Text)
    timeframe_seconds: Mapped[int | None] = mapped_column(nullable=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False)

    test_plan: Mapped[TestPlan] = relationship(back_populates="sla_rules")


Index(
    "uq_test_plan_sla_rules_plan_rule",
    TestPlanSlaRule.test_plan_id,
    TestPlanSlaRule.id,
    unique=True,
)
Index(
    "uq_test_plan_sla_rules_plan_position",
    TestPlanSlaRule.test_plan_id,
    TestPlanSlaRule.position,
    unique=True,
)
Index(
    "ix_test_plan_sla_rules_workspace_plan",
    TestPlanSlaRule.workspace_id,
    TestPlanSlaRule.test_plan_id,
)
