from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPENAPI = ROOT / "packages/contracts/openapi/api.openapi.json"
RUNNER_CALLBACK = ROOT / "packages/contracts/runner/runner-callback.schema.json"


def load_openapi() -> dict:
    return json.loads(OPENAPI.read_text())


def test_run_report_contract_exposes_debug_http_trace() -> None:
    spec = load_openapi()
    schemas = spec["components"]["schemas"]

    assert "DebugHttpTrace" in schemas
    assert "DebugHttpTraceEntry" in schemas
    assert "DebugHttpTraceBody" in schemas
    report_props = schemas["RunReportDetail"]["properties"]
    assert "debugHttpTrace" in report_props
    assert "debugHttpTrace" in schemas["RunReportDetail"]["required"]
    trace_schema = schemas["DebugHttpTrace"]["properties"]
    assert trace_schema["status"]["enum"] == ["available", "unavailable"]
    assert "entries" in trace_schema


def test_public_run_artifact_type_contract_excludes_internal_debug_artifacts() -> None:
    spec = load_openapi()
    enum = spec["components"]["schemas"]["RunArtifactType"]["enum"]
    assert "debug_http_trace" not in enum
    assert "debug_http_body_blob" not in enum


def test_openapi_exposes_debug_http_body_blob_download_endpoint() -> None:
    spec = load_openapi()
    paths = spec["paths"]
    path = "/v1/runs/{runId}/debug-http-body-blobs/{artifactId}/download"
    assert path in paths
    assert paths[path]["get"]["operationId"] == "downloadDebugHttpBodyBlob"


def test_web_openapi_contract_excludes_internal_runner_endpoints() -> None:
    spec = load_openapi()
    paths = spec["paths"].keys()
    assert all("/internal/" not in path for path in paths)
    assert all("runner" not in path for path in paths)


def test_runner_callback_schema_accepts_debug_http_trace_artifact_event() -> None:
    schema = json.loads(RUNNER_CALLBACK.read_text())
    artifact_type = None
    for clause in schema["allOf"]:
        then = clause.get("then", {})
        details = then.get("properties", {}).get("details", {})
        properties = details.get("properties", {})
        if "artifactType" in properties:
            artifact_type = properties["artifactType"]
            break
    assert artifact_type is not None
    assert "debug_http_trace" in artifact_type["enum"]
