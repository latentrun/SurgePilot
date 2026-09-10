import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OPENAPI = ROOT / "packages/contracts/openapi/api.openapi.json"
WEB_CLIENT = ROOT / "packages/contracts/generated/web-client/index.ts"


def load_openapi() -> dict:
    return json.loads(OPENAPI.read_text())


def operation(path: str, method: str) -> dict:
    return load_openapi()["paths"][path][method]


def parameter_names(operation_schema: dict) -> set[str]:
    return {parameter["name"] for parameter in operation_schema.get("parameters", [])}


def parameter(operation_schema: dict, name: str) -> dict:
    for item in operation_schema.get("parameters", []):
        if item["name"] == name:
            return item
    raise AssertionError(f"Missing parameter {name}")


def literal_values(parameter_schema: dict) -> set[str]:
    schema = parameter_schema["schema"]
    if "const" in schema:
        return {schema["const"]}
    if "enum" in schema:
        return set(schema["enum"])
    if "anyOf" in schema:
        values: set[str] = set()
        for item in schema["anyOf"]:
            if "const" in item:
                values.add(item["const"])
            values.update(item.get("enum", []))
        return values
    return set()


def test_p1_04_scenario_clone_archive_contracts_exclude_execution_preview() -> None:
    schema = load_openapi()

    clone = operation("/v1/scenarios/{scenarioId}/clone", "post")
    archive = operation("/v1/scenarios/{scenarioId}", "delete")

    assert clone["operationId"] == "cloneScenario"
    assert "201" in clone["responses"]
    assert "CloneRequest" in str(clone.get("requestBody", {}))
    assert {"scenarioId", "x-csrf-token", "x-workspace-id"}.issubset(parameter_names(clone))

    assert "/v1/scenarios/{scenarioId}/execution-preview" not in schema["paths"]

    archive_copy = f"{archive.get('summary', '')} {archive.get('description', '')}"
    assert "Archive" in archive_copy
    assert "permanent" not in archive_copy.lower()

    components = schema["components"]["schemas"]
    assert "CloneRequest" in components
    assert "ExecutionPreviewResponse" in components
    assert "ExecutionPreviewWarning" in components
    assert components["ExecutionPreviewResponse"]["properties"]["sourceType"] == {
        "const": "test_plan",
        "title": "Sourcetype",
        "type": "string",
    }
    assert "INVALID_EXECUTION_PREVIEW_MODE" in schema["info"]["x-surgepilot-error-codes"]


def test_p1_04_test_plan_clone_archive_and_preview_contracts_are_generated() -> None:
    clone = operation("/v1/test-plans/{testPlanId}/clone", "post")
    preview = operation("/v1/test-plans/{testPlanId}/execution-preview", "get")
    archive = operation("/v1/test-plans/{testPlanId}", "delete")

    assert clone["operationId"] == "cloneTestPlan"
    assert "201" in clone["responses"]
    assert "CloneRequest" in str(clone.get("requestBody", {}))
    assert {"testPlanId", "x-csrf-token", "x-workspace-id"}.issubset(parameter_names(clone))

    assert preview["operationId"] == "getTestPlanExecutionPreview"
    assert {"testPlanId", "runType", "x-workspace-id"}.issubset(parameter_names(preview))
    run_type = parameter(preview, "runType")
    assert run_type["required"] is False
    assert literal_values(run_type) == {"debug", "standard"}
    assert "ExecutionPreviewResponse" in str(preview["responses"]["200"])
    assert "ErrorResponse" in str(preview["responses"]["400"])

    archive_copy = f"{archive.get('summary', '')} {archive.get('description', '')}"
    assert "Archive" in archive_copy
    assert "permanent" not in archive_copy.lower()


def test_p1_04_generated_web_client_exposes_test_plan_preview_only() -> None:
    web_client_text = WEB_CLIENT.read_text()

    assert '"/v1/scenarios/{scenarioId}/clone"' in web_client_text
    assert '"/v1/scenarios/{scenarioId}/execution-preview"' not in web_client_text
    assert '"/v1/test-plans/{testPlanId}/clone"' in web_client_text
    assert '"/v1/test-plans/{testPlanId}/execution-preview"' in web_client_text
    assert "CloneRequest" in web_client_text
    assert "ExecutionPreviewResponse" in web_client_text
    assert "INVALID_EXECUTION_PREVIEW_MODE" in load_openapi()["info"]["x-surgepilot-error-codes"]
    assert "runner/callbacks" not in web_client_text
    assert "runner/artifacts" not in web_client_text
