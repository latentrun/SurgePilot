from enum import Enum
from typing import Literal

from pydantic import ConfigDict, Field

from app.schemas.common import ApiSchema


class RunState(str, Enum):
    initializing = "initializing"
    running = "running"
    stopping = "stopping"
    finished = "finished"
    failed = "failed"
    aborted = "aborted"


CallbackEventType = Literal[
    "accepted", "running", "heartbeat", "artifact", "finished", "failed", "aborted"
]

class RunType(str, Enum):
    debug = "debug"
    standard = "standard"


class RunSourceType(str, Enum):
    protocol_smoke = "protocol_smoke"
    debug_scenario = "debug_scenario"
    test_plan = "test_plan"


class RunValidity(str, Enum):
    valid = "valid"
    invalid = "invalid"


class SlaResult(str, Enum):
    passed = "passed"
    failed = "failed"
    not_evaluated = "not_evaluated"


class RunArtifactType(str, Enum):
    taurus_log = "taurus_log"
    jmeter_log = "jmeter_log"
    final_stats_csv = "final_stats_csv"
    run_log = "run_log"
    artifacts_zip = "artifacts_zip"


class ReportSummaryStatus(str, Enum):
    pending = "pending"
    parsed = "parsed"
    failed = "failed"
    missing = "missing"


RunCreateType = RunType
RunCreateSourceType = Literal["debug_scenario", "test_plan"]


class RunCreateRequest(ApiSchema):
    """Public ``POST /api/v1/runs`` payload for Scenario Debug Runs and
    Test Plan Runs.

    P0-05 activates public Run creation for ``runType=debug`` with
    ``sourceType=debug_scenario``. P0-06 extends public Run creation to
    ``runType=standard|debug`` with ``sourceType=test_plan``. Test Plan Runs
    use the saved Env Group and Load Node settings and reject overrides;
    ``confirmHighConcurrency`` acknowledges the soft single-node concurrency
    limit.
    """

    model_config = ConfigDict(
        alias_generator=ApiSchema.model_config["alias_generator"],
        populate_by_name=True,
        extra="forbid",
    )

    run_type: RunCreateType
    source_type: RunCreateSourceType
    source_id: str = Field(min_length=26, max_length=26)
    expected_source_revision: int = Field(ge=1)
    env_group_id: str | None = Field(default=None, min_length=26, max_length=26)
    selected_node_id: str | None = Field(default=None, min_length=26, max_length=26)
    confirm_high_concurrency: bool = False


class RunCreateResponse(ApiSchema):
    id: str
    state: RunState
    run_type: RunCreateType
    source_type: RunCreateSourceType
    source_id: str | None = None
    selected_node_id: str
    validity: str | None = None
    created_at: str
    deduplicated: bool


class RunStopResponse(ApiSchema):
    id: str
    state: RunState
    stop_requested_at: str | None = None
    duplicate: bool


class RunActor(ApiSchema):
    id: str
    email: str


class RunSelectedNode(ApiSchema):
    id: str
    name: str
    scope: str


class RunListItem(ApiSchema):
    id: str
    state: RunState
    run_type: RunType
    source_type: RunSourceType
    source_id: str | None = None
    source_name: str | None = None
    source_revision: int | None = None
    tags: list[str] = Field(default_factory=list)
    validity: RunValidity
    sla_result: SlaResult
    triggered_by: RunActor
    selected_node: RunSelectedNode
    created_at: str
    started_at: str | None = None
    ended_at: str | None = None
    duration_ms: int | None = None
    artifact_count: int
    has_artifacts_zip: bool


class RunListResponse(ApiSchema):
    items: list[RunListItem]
    next_cursor: str | None = None


class RunVerdict(ApiSchema):
    state: RunState
    run_type: RunType
    source_type: RunSourceType
    validity: RunValidity
    sla_result: SlaResult
    sla_result_reason: str | None = None
    duration_ms: int | None = None
    triggered_by: RunActor
    created_at: str
    accepted_at: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    last_heartbeat_at: str | None = None
    failure_reason: str | None = None
    failure_message: str | None = None
    forced_convergence: bool
    warnings: list[str] = Field(default_factory=list)


class RunKpiSummary(ApiSchema):
    status: ReportSummaryStatus
    source_artifact_id: str | None = None
    total_requests: int | None = None
    failed_requests: int | None = None
    error_rate: float | None = None
    average_response_time_ms: float | None = None
    p90_ms: float | None = None
    p95_ms: float | None = None
    p99_ms: float | None = None
    throughput_per_second: float | None = None
    missing_reasons: list[str] = Field(default_factory=list)


class FailureDiagnostics(ApiSchema):
    failure_reason: str | None = None
    failure_message: str | None = None
    has_failed_requests_preview: bool = False
    notes: list[str] = Field(default_factory=list)


class FinalStatsPreviewRow(ApiSchema):
    label: str | None = None
    total_requests: int | None = None
    success_requests: int | None = None
    failed_requests: int | None = None
    error_rate: float | None = None
    average_response_time_ms: float | None = None
    p90_ms: float | None = None
    p95_ms: float | None = None
    p99_ms: float | None = None
    response_code_counts: dict[str, int] = Field(default_factory=dict)


class FinalStatsPreview(ApiSchema):
    status: ReportSummaryStatus
    truncated: bool
    rows: list[FinalStatsPreviewRow]
    warnings: list[str] = Field(default_factory=list)


class DebugHttpTraceBody(ApiSchema):
    content_type: str | None = None
    text: str | None = None
    inline_preview: str | None = None
    body_storage: Literal["inline", "truncated", "sidecar", "dropped"] = "inline"
    body_truncated: bool = False
    size_bytes: int | None = None
    sha256_prefix: str | None = None
    download_artifact_id: str | None = None
    download_relative_path: str | None = Field(default=None, exclude=True)
    drop_reason: str | None = None


class DebugHttpTraceEntry(ApiSchema):
    sequence: int
    label: str | None = None
    method: str
    url: str
    request_headers: dict[str, str] = Field(default_factory=dict)
    request_body: DebugHttpTraceBody
    response_status: int | None = None
    response_headers: dict[str, str] = Field(default_factory=dict)
    response_body: DebugHttpTraceBody
    duration_ms: int | None = None
    error: str | None = None


class DebugHttpTrace(ApiSchema):
    status: Literal["available", "unavailable"]
    source_artifact_id: str | None = None
    entry_count: int
    trace_truncated: bool
    warnings: list[str] = Field(default_factory=list)
    entries: list[DebugHttpTraceEntry] = Field(default_factory=list)


class RunSnapshotResourceRequest(ApiSchema):
    mode: str | None = None
    pool_type: str | None = None
    selected_node_id: str | None = None
    expected_concurrency_per_node: int | None = None


class RunReportNode(ApiSchema):
    id: str
    name: str
    scope: str
    pool_type: str
    state_at_report: str


class RunSnapshotLoadSettings(ApiSchema):
    concurrency_per_node: int | None = None
    ramp_up_seconds: int | None = None
    hold_for_seconds: int | None = None
    iterations: int | None = None
    target_rps: float | None = None
    steps: int | None = None
    delay_seconds: int | None = None


class RunSnapshotScenarioItem(ApiSchema):
    scenario_name: str
    load_settings: RunSnapshotLoadSettings


class RunSnapshotSlaRule(ApiSchema):
    metric: str | None = None
    condition: str | None = None
    threshold_text: str | None = None


class RunSnapshotSummary(ApiSchema):
    schema_version: int
    source_name: str | None = None
    source_revision: int | None = None
    env_group_name: str | None = None
    run_mode: str | None = None
    scenario_count: int
    scenario_names: list[str] = Field(default_factory=list)
    scenario_items: list[RunSnapshotScenarioItem] = Field(default_factory=list)
    sla_rule_count: int
    sla_rules: list[RunSnapshotSlaRule] = Field(default_factory=list)
    dependency_file_count: int
    dependency_file_names: list[str] = Field(default_factory=list)
    env_group_variable_keys: list[str] = Field(default_factory=list)
    resource_request: RunSnapshotResourceRequest | None = None


class RunArtifactsSummary(ApiSchema):
    count: int
    has_artifacts_zip: bool
    has_final_stats_csv: bool
    latest_available_at: str | None = None


class RunReportDetail(ApiSchema):
    id: str
    verdict: RunVerdict
    kpi_summary: RunKpiSummary
    failure_diagnostics: FailureDiagnostics
    final_stats_preview: FinalStatsPreview
    debug_http_trace: DebugHttpTrace | None
    snapshot: RunSnapshotSummary
    nodes: list[RunReportNode] = Field(default_factory=list)
    artifacts_summary: RunArtifactsSummary


class RunArtifactItem(ApiSchema):
    id: str
    node_id: str
    artifact_type: RunArtifactType
    relative_path: str
    display_filename: str
    size_bytes: int
    sha256: str
    content_type: str | None = None
    terminal_late: bool
    created_at: str
    available_at: str | None = None
    download_url: str


class RunArtifactListResponse(ApiSchema):
    items: list[RunArtifactItem]
    next_cursor: str | None = None


class RunValidityPatchRequest(ApiSchema):
    validity: RunValidity


class RunValidityPatchResponse(ApiSchema):
    id: str
    validity: RunValidity
    validity_updated_at: str
    validity_updated_by: RunActor


class RunnerCallbackRequest(ApiSchema):
    model_config = ConfigDict(
        alias_generator=ApiSchema.model_config["alias_generator"],
        populate_by_name=True,
        extra="forbid",
    )

    schema_version: Literal["1"]
    event_id: str = Field(min_length=26, max_length=26)
    run_id: str = Field(min_length=26, max_length=26)
    node_id: str = Field(min_length=26, max_length=26)
    runtime_version: str = Field(min_length=1, max_length=200)
    event_type: CallbackEventType
    seq: int = Field(ge=0)
    event_time: str
    message: str | None = Field(default=None, max_length=500)
    runner_pid: int | None = Field(default=None, ge=1)
    details: dict = Field(default_factory=dict)


class RunnerCallbackResponse(ApiSchema):
    accepted: bool
    duplicate: bool
    state_changed: bool
    current_state: RunState
    ignored_reason: str | None = None


class RunnerArtifactResponse(ApiSchema):
    artifact_id: str
    duplicate: bool
