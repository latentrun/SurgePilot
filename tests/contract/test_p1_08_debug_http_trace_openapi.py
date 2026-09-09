import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_openapi() -> dict:
    return json.loads((ROOT / "packages/contracts/openapi/api.openapi.json").read_text())


def test_run_report_contract_exposes_nullable_debug_http_trace() -> None:
    schemas = load_openapi()["components"]["schemas"]
    assert {"DebugHttpTrace", "DebugHttpTraceEntry", "DebugHttpTraceBody"} <= schemas.keys()
    report = schemas["RunReportDetail"]
    assert "debugHttpTrace" in report["required"]
    trace_union = report["properties"]["debugHttpTrace"]["anyOf"]
    assert any(item.get("type") == "null" for item in trace_union)
    assert schemas["DebugHttpTrace"]["properties"]["status"]["enum"] == [
        "available",
        "unavailable",
    ]


def test_internal_debug_trace_artifacts_are_not_public_download_types() -> None:
    schemas = load_openapi()["components"]["schemas"]
    artifact_types = schemas["RunArtifactType"]["enum"]
    assert "debug_http_trace" not in artifact_types
    assert "debug_http_body_blob" not in artifact_types


def test_web_contract_does_not_expose_runner_routes() -> None:
    paths = load_openapi()["paths"]
    assert all("/internal/" not in path and "runner" not in path for path in paths)
