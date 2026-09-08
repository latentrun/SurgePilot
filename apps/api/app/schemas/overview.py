from enum import Enum

from app.schemas.common import ApiSchema
from app.schemas.runs import RunSourceType, RunState, RunType, RunValidity, SlaResult


class OverviewResultRunScope(str, Enum):
    valid_standard_terminal_runs = "valid_standard_terminal_runs"


class OverviewWorkspace(ApiSchema):
    id: str
    name: str


class OverviewStatsScope(ApiSchema):
    window_days: int
    window_started_at: str
    result_run_scope: OverviewResultRunScope
    recent_run_limit: int


class OverviewTerminalStateCounts(ApiSchema):
    finished: int
    failed: int
    aborted: int


class OverviewSlaResultCounts(ApiSchema):
    passed: int
    failed: int
    not_evaluated: int


class OverviewResultRuns(ApiSchema):
    total: int
    by_state: OverviewTerminalStateCounts
    by_sla_result: OverviewSlaResultCounts


class OverviewActiveRuns(ApiSchema):
    total: int
    initializing: int
    running: int
    stopping: int


class OverviewRunStats(ApiSchema):
    result_runs: OverviewResultRuns
    active_runs: OverviewActiveRuns


class OverviewRecentRun(ApiSchema):
    id: str
    run_type: RunType
    source_type: RunSourceType
    source_name: str | None = None
    state: RunState
    validity: RunValidity | None = None
    sla_result: SlaResult | None = None
    created_at: str
    started_at: str | None = None
    ended_at: str | None = None
    duration_ms: int | None = None
    artifact_count: int
    has_artifacts_zip: bool


class OverviewLoadNodeStatusCounts(ApiSchema):
    uninitialized: int
    initializing: int
    idle: int
    busy: int
    offline: int
    quarantined: int
    disabled: int


class OverviewResourceSummary(ApiSchema):
    total_visible_nodes: int
    by_status: OverviewLoadNodeStatusCounts


class OverviewResponse(ApiSchema):
    generated_at: str
    workspace: OverviewWorkspace
    stats_scope: OverviewStatsScope
    run_stats: OverviewRunStats
    recent_runs: list[OverviewRecentRun]
    resource_summary: OverviewResourceSummary
