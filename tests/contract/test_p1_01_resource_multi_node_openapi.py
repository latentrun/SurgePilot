from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPENAPI = ROOT / "packages/contracts/openapi/api.openapi.json"
WEB_CLIENT = ROOT / "packages/contracts/generated/web-client/index.ts"


def load_openapi() -> dict:
    return json.loads(OPENAPI.read_text())


def test_run_create_contract_accepts_normalized_resource_request() -> None:
    spec = load_openapi()
    schemas = spec["components"]["schemas"]

    create_props = schemas["RunCreateRequest"]["properties"]
    assert "resourceRequest" in create_props
    resource_props = schemas["RunResourceRequest"]["properties"]
    assert resource_props["mode"]["enum"] == ["manual", "auto"]
    assert "selectedNodeIds" in resource_props
    assert "nodeCount" in resource_props
    assert "concurrencyPerNode" in resource_props


def test_run_report_contract_exposes_redacted_allocation_projection() -> None:
    spec = load_openapi()
    schemas = spec["components"]["schemas"]

    assert "RunAllocatedNode" in schemas
    report_props = schemas["RunReportDetail"]["properties"]
    assert "allocatedNodes" in report_props
    assert "nodes" not in report_props

    node_props = schemas["RunAllocatedNode"]["properties"]
    assert "nodeIndex" in node_props
    assert "totalNodes" in node_props
    assert "sshUser" not in node_props
    assert "runnerHome" not in node_props
    assert "host" not in node_props

    snapshot_resource_props = schemas["RunSnapshotResourceRequest"]["properties"]
    assert "selectedNodeIds" in snapshot_resource_props
    assert "nodeCount" in snapshot_resource_props

    artifact_props = schemas["RunArtifactItem"]["properties"]
    assert "nodeId" in artifact_props
    assert "allocationId" in artifact_props
    assert "storageKey" not in artifact_props
    assert "host" not in artifact_props
    assert "runnerHome" not in artifact_props
    assert "sshUser" not in artifact_props


def test_p1_01_error_codes_and_internal_runner_exclusion_are_generated() -> None:
    spec = load_openapi()
    codes = set(spec["info"]["x-surgepilot-error-codes"])

    assert {
        "RESOURCE_REQUEST_INVALID",
        "LOAD_NODE_UNAVAILABLE",
        "LOAD_NODE_CAPACITY_UNAVAILABLE",
        "RUNNER_FORBIDDEN",
    }.issubset(codes)
    assert all("/internal/" not in path for path in spec["paths"])
    web_client_text = WEB_CLIENT.read_text()
    assert "runner/callbacks" not in web_client_text
    assert "runner/artifacts" not in web_client_text
