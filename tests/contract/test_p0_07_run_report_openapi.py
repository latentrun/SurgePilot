import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPENAPI = ROOT / "packages/contracts/openapi/api.openapi.json"
WEB_CLIENT = ROOT / "packages/contracts/generated/web-client/index.ts"


def load_openapi() -> dict:
    return json.loads(OPENAPI.read_text())


def operation(path: str, method: str) -> dict:
    return load_openapi()["paths"][path][method]


def test_run_report_public_endpoints_and_path_params_are_generated() -> None:
    schema = load_openapi()

    assert operation("/v1/runs", "get")["operationId"] == "listRuns"
    assert operation("/v1/runs/{runId}", "get")["operationId"] == "getRunReport"
    assert operation("/v1/runs/{runId}/artifacts", "get")["operationId"] == "listRunArtifacts"
    assert (
        operation("/v1/runs/{runId}/artifacts/{artifactId}/download", "get")["operationId"]
        == "downloadRunArtifact"
    )
    assert operation("/v1/runs/{runId}/validity", "patch")["operationId"] == "patchRunValidity"
    params = {
        parameter["name"]
        for parameter in operation("/v1/runs/{runId}/artifacts/{artifactId}/download", "get")[
            "parameters"
        ]
    }
    assert {"runId", "artifactId", "x-workspace-id"}.issubset(params)
    assert "run_id" not in params and "artifact_id" not in params
    assert "RunReportDetail" in schema["components"]["schemas"]


def test_run_report_public_schemas_include_p0_enums_only() -> None:
    schema_text = json.dumps(load_openapi())

    assert "SlaResult" in schema_text
    assert "RunValidity" in schema_text
    assert "RunArtifactType" in schema_text
    assert "artifacts_zip" in schema_text
    assert "failed_requests_csv" not in schema_text


def test_generated_web_client_exposes_run_report_without_internal_runner() -> None:
    web_client_text = WEB_CLIENT.read_text()

    assert '"/v1/runs"' in web_client_text
    assert '"/v1/runs/{runId}"' in web_client_text
    assert '"/v1/runs/{runId}/artifacts"' in web_client_text
    assert '"/v1/runs/{runId}/artifacts/{artifactId}/download"' in web_client_text
    assert '"/v1/runs/{runId}/validity"' in web_client_text
    assert "runner/callbacks" not in web_client_text
    assert "runner/artifacts" not in web_client_text
