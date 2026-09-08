import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPENAPI = ROOT / "packages/contracts/openapi/api.openapi.json"
WEB_CLIENT = ROOT / "packages/contracts/generated/web-client/index.ts"


def load_openapi() -> dict:
    return json.loads(OPENAPI.read_text())


def operation(path: str, method: str) -> dict:
    return load_openapi()["paths"][path][method]


def test_overview_endpoint_and_schemas_are_generated() -> None:
    schema = load_openapi()
    overview = operation("/v1/overview", "get")

    assert overview["operationId"] == "getOverview"
    assert overview["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/OverviewResponse"
    )
    params = {parameter["name"]: parameter for parameter in overview["parameters"]}
    assert params["x-workspace-id"]["in"] == "header"
    assert params["recentLimit"]["schema"]["maximum"] == 10
    assert params["recentLimit"]["schema"]["minimum"] == 1
    assert "OverviewResponse" in schema["components"]["schemas"]


def test_overview_result_scope_is_closed_literal_and_camel_case() -> None:
    schemas = load_openapi()["components"]["schemas"]

    assert schemas["OverviewResultRunScope"]["enum"] == ["valid_standard_terminal_runs"]
    overview_props = schemas["OverviewResponse"]["properties"]
    assert {"generatedAt", "statsScope", "runStats", "recentRuns", "resourceSummary"}.issubset(
        overview_props
    )
    assert "generated_at" not in overview_props
    scope_props = schemas["OverviewStatsScope"]["properties"]
    assert "resultRunScope" in scope_props
    assert "result_run_scope" not in scope_props


def test_generated_web_client_exposes_overview_without_internal_runner() -> None:
    web_client_text = WEB_CLIENT.read_text()

    assert '"/v1/overview"' in web_client_text
    assert "OverviewResponse" in web_client_text
    assert "OverviewResultRunScope" in web_client_text
    assert "runner/callbacks" not in web_client_text
    assert "runner/artifacts" not in web_client_text
