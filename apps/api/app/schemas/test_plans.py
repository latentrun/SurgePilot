from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from app.core.ids import is_ulid
from app.schemas.common import ApiSchema

TestPlanRunMode = Literal["sequential", "parallel"]
TestPlanPoolType = Literal["public", "private"]
SlaCondition = Literal["gt", "gte", "lt", "lte", "eq"]
SlaThresholdUnit = Literal["ms", "s", "percent", "count", "b", "kb", "mb"]
SlaTimeframeLogic = Literal["for", "within"]
SlaAction = Literal["continue", "stop"]


def validate_ulid_value(value: str | None) -> str | None:
    if value is not None and not is_ulid(value):
        raise ValueError("Invalid ULID.")
    return value


class TestPlanResourceConfig(ApiSchema):
    pool_type: TestPlanPoolType | None = None
    selected_node_id: str | None = Field(default=None, min_length=26, max_length=26)

    @field_validator("selected_node_id")
    @classmethod
    def validate_selected_node_id(cls, value: str | None) -> str | None:
        return validate_ulid_value(value)


class TestPlanLoadSettings(ApiSchema):
    concurrency_per_node: int = Field(default=1, ge=1)
    ramp_up_seconds: int = Field(default=0, ge=0)
    hold_for_seconds: int | None = Field(default=60, gt=0)
    iterations: int | None = Field(default=None, gt=0)
    target_rps: float | None = Field(default=None, gt=0)
    steps: int | None = Field(default=None, gt=0)
    delay_seconds: int = Field(default=0, ge=0)


class TestPlanScenarioItemInput(ApiSchema):
    id: str | None = Field(default=None, min_length=26, max_length=26)
    scenario_id: str = Field(min_length=26, max_length=26)
    enabled: bool = True
    order: int = Field(default=0, ge=0)
    load_settings: TestPlanLoadSettings = Field(default_factory=TestPlanLoadSettings)

    @field_validator("id", "scenario_id")
    @classmethod
    def validate_ids(cls, value: str | None) -> str | None:
        return validate_ulid_value(value)


class TestPlanSlaThreshold(ApiSchema):
    value: float = Field(ge=0)
    unit: SlaThresholdUnit


class TestPlanSlaRuleInput(ApiSchema):
    id: str | None = Field(default=None, min_length=26, max_length=26)
    enabled: bool = True
    subject: str = Field(
        min_length=1,
        max_length=32,
        description=(
            "Supported SLA subjects: avg_rt, p90, p95, p99, fail, succ, hits, bytes, "
            "or response-code subjects such as rc500, rc4??, and rc*."
        ),
        json_schema_extra={
            "oneOf": [
                {"enum": ["avg_rt", "p90", "p95", "p99", "fail", "succ", "hits", "bytes"]},
                {"pattern": r"^rc(?:\d{3}|\d\?\?|\*)$"},
            ]
        },
    )
    label: str | None = Field(
        default=None,
        max_length=200,
        description="Exact generated sampler label; leave empty to evaluate the whole run.",
    )
    condition: SlaCondition
    threshold: TestPlanSlaThreshold
    timeframe_logic: SlaTimeframeLogic | None = None
    timeframe_seconds: int | None = Field(default=None, gt=0)
    action: SlaAction = "continue"

    @field_validator("subject")
    @classmethod
    def normalize_subject(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str | None) -> str | None:
        return validate_ulid_value(value)


class TestPlanEditableContent(ApiSchema):
    model_config = ConfigDict(
        alias_generator=ApiSchema.model_config["alias_generator"],
        populate_by_name=True,
        extra="forbid",
    )

    name: str = Field(min_length=1, max_length=120, pattern=r".*\S.*")
    description: str | None = Field(default=None, max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=10)
    env_group_id: str | None = Field(default=None, min_length=26, max_length=26)
    run_mode: TestPlanRunMode = "sequential"
    resource: TestPlanResourceConfig = Field(default_factory=TestPlanResourceConfig)
    scenario_items: list[TestPlanScenarioItemInput] = Field(default_factory=list, max_length=20)
    sla_rules: list[TestPlanSlaRuleInput] = Field(default_factory=list, max_length=10)

    @field_validator("env_group_id")
    @classmethod
    def validate_env_group_id(cls, value: str | None) -> str | None:
        return validate_ulid_value(value)


class TestPlanCreateRequest(TestPlanEditableContent):
    pass


class TestPlanPatchRequest(TestPlanEditableContent):
    expected_revision: int = Field(ge=1)


class TestPlanEnvGroupRef(ApiSchema):
    id: str
    name: str


class TestPlanResourceSummary(ApiSchema):
    pool_type: TestPlanPoolType | None = None
    selected_node_id: str | None = None
    selected_node_name: str | None = None
    selected_node_status: str | None = None


class TestPlanRunGuard(ApiSchema):
    expected_concurrency_per_node: int
    soft_concurrency_per_node_limit: int
    hard_concurrency_per_node_limit: int
    requires_high_concurrency_confirmation: bool


class TestPlanUpdatedBy(ApiSchema):
    id: str
    display_name: str


class TestPlanSummary(ApiSchema):
    id: str
    name: str
    description: str | None = None
    tags: list[str]
    run_mode: TestPlanRunMode
    env_group: TestPlanEnvGroupRef | None = None
    resource: TestPlanResourceSummary
    scenario_item_count: int
    enabled_scenario_item_count: int
    sla_rule_count: int
    expected_concurrency_per_node: int
    requires_high_concurrency_confirmation: bool
    runnable: bool
    not_runnable_reasons: list[str]
    revision: int
    updated_at: str
    updated_by: TestPlanUpdatedBy | None = None


class TestPlanScenarioItemDetail(TestPlanScenarioItemInput):
    id: str
    scenario_name: str | None = None
    scenario_revision: int | None = None
    enabled_step_count: int | None = None
    updated_at: str | None = None


class TestPlanSlaRuleDetail(TestPlanSlaRuleInput):
    id: str


class TestPlanDetail(ApiSchema):
    id: str
    name: str
    description: str | None = None
    tags: list[str]
    env_group_id: str | None = None
    run_mode: TestPlanRunMode
    resource: TestPlanResourceConfig
    scenario_items: list[TestPlanScenarioItemDetail]
    sla_rules: list[TestPlanSlaRuleDetail]
    run_guard: TestPlanRunGuard
    runnable: bool
    not_runnable_reasons: list[str]
    revision: int
    created_at: str
    updated_at: str


class TestPlanListResponse(ApiSchema):
    items: list[TestPlanSummary]
    page: int
    page_size: int
    total: int
