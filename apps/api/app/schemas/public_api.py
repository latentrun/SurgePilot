from typing import Literal

from pydantic import ConfigDict, Field

from app.schemas.common import ApiSchema
from app.schemas.runs import (
    FailureDiagnostics,
    FinalStatsPreview,
    RunAllocatedNode,
    RunArtifactsSummary,
    RunKpiSummary,
    RunCreateRequest,
    RunResourceRequest,
    RunSnapshotSummary,
    RunVerdict,
)
from app.schemas.test_plans import (
    TestPlanCreateRequest,
    TestPlanPatchRequest,
    TestPlanResourceConfig,
)


PUBLIC_RUN_RESOURCE_SCHEMA = {
    "oneOf": [
        {
            "required": ["mode", "selectedNodeIds"],
            "properties": {
                "mode": {"const": "manual"},
                "selectedNodeIds": {"minItems": 1},
                "nodeCount": {"type": "null"},
            },
        },
        {
            "required": ["mode", "nodeCount"],
            "properties": {
                "mode": {"const": "auto"},
                "selectedNodeIds": {"maxItems": 0},
            },
        },
    ]
}

PUBLIC_TEST_PLAN_RESOURCE_SCHEMA = {
    "oneOf": [
        {
            "properties": {
                "mode": {"const": "manual"},
                "nodeCount": {"type": "null"},
            }
        },
        {
            "required": ["mode", "nodeCount"],
            "properties": {
                "mode": {"const": "auto"},
                "selectedNodeId": {"type": "null"},
                "selectedNodeIds": {"maxItems": 0},
            },
        },
    ]
}


class PublicRunResourceRequest(RunResourceRequest):
    model_config = ConfigDict(json_schema_extra=PUBLIC_RUN_RESOURCE_SCHEMA)


class PublicRunCreateRequest(RunCreateRequest):
    resource_request: PublicRunResourceRequest | None = None


class PublicTestPlanResourceConfig(TestPlanResourceConfig):
    model_config = ConfigDict(json_schema_extra=PUBLIC_TEST_PLAN_RESOURCE_SCHEMA)


class PublicTestPlanCreateRequest(TestPlanCreateRequest):
    resource: PublicTestPlanResourceConfig = Field(default_factory=PublicTestPlanResourceConfig)


class PublicTestPlanPatchRequest(TestPlanPatchRequest):
    resource: PublicTestPlanResourceConfig = Field(default_factory=PublicTestPlanResourceConfig)


class PublicLoadNodeSummary(ApiSchema):
    id: str
    scope: Literal["public", "workspace"]
    workspace_id: str | None = None
    host: str
    status: str
    runner_version: str | None = None
    bundle_version: str | None = None
    runtime_version: str | None = None
    last_checked_at: str | None = None
    last_heartbeat_at: str | None = None
    created_at: str
    updated_at: str


class PublicLoadNodeListResponse(ApiSchema):
    items: list[PublicLoadNodeSummary]
    limit: int
    offset: int
    total: int


class PublicRunReport(ApiSchema):
    id: str
    verdict: RunVerdict
    kpi_summary: RunKpiSummary
    failure_diagnostics: FailureDiagnostics
    final_stats_preview: FinalStatsPreview
    snapshot: RunSnapshotSummary
    allocated_nodes: list[RunAllocatedNode]
    artifacts_summary: RunArtifactsSummary
