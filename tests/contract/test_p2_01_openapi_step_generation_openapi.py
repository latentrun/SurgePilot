import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPENAPI = ROOT / "packages/contracts/openapi/api.openapi.json"
WEB_CLIENT = ROOT / "packages/contracts/generated/web-client/index.ts"


def load_openapi() -> dict:
    return json.loads(OPENAPI.read_text())


def test_p2_01_openapi_step_generation_contract_is_generated() -> None:
    openapi = load_openapi()
    paths = openapi["paths"]
    assert (
        paths["/v1/scenarios/{scenarioId}/openapi-step-generation/specs"]["get"]["operationId"]
        == "listScenarioOpenApiSpecSources"
    )
    assert (
        paths["/v1/scenarios/{scenarioId}/openapi-step-generation/specs/{specId}/operations"][
            "get"
        ]["operationId"]
        == "listScenarioOpenApiOperations"
    )
    assert (
        paths["/v1/scenarios/{scenarioId}/openapi-step-generation/drafts"]["post"]["operationId"]
        == "generateScenarioOpenApiStepDrafts"
    )
    post = paths["/v1/scenarios/{scenarioId}/openapi-step-generation/drafts"]["post"]
    parameter_names = {parameter["name"] for parameter in post["parameters"]}
    assert "x-csrf-token" in parameter_names
    assert "x-workspace-id" in parameter_names
    schemas = openapi["components"]["schemas"]
    assert "OpenApiStepDraftPreviewResponse" in schemas
    assert "operationRefs" in schemas["OpenApiStepDraftGenerateRequest"]["properties"]
    assert "operation_refs" not in json.dumps(schemas["OpenApiStepDraftGenerateRequest"])
    assert "OPENAPI_OPERATION_NOT_FOUND" in openapi["info"]["x-surgepilot-error-codes"]


def test_generated_web_client_exposes_p2_01_operations() -> None:
    text = WEB_CLIENT.read_text()
    assert "listScenarioOpenApiSpecSources" in text
    assert "listScenarioOpenApiOperations" in text
    assert "generateScenarioOpenApiStepDrafts" in text
