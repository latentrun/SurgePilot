import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_p2_01_paths_and_generated_client_are_fresh_and_scoped() -> None:
    document = json.loads((ROOT / "packages/contracts/openapi/api.openapi.json").read_text())
    paths = document["paths"]
    expected = {
        "/v1/scenarios/{scenarioId}/openapi-step-generation/specs": "listScenarioOpenApiSpecSources",
        "/v1/scenarios/{scenarioId}/openapi-step-generation/specs/{specId}/operations": "listScenarioOpenApiOperations",
        "/v1/scenarios/{scenarioId}/openapi-step-generation/drafts": "generateScenarioOpenApiStepDrafts",
    }
    for path, operation_id in expected.items():
        method = "post" if path.endswith("drafts") else "get"
        assert paths[path][method]["operationId"] == operation_id

    serialized = (ROOT / "packages/contracts/generated/web-client/index.ts").read_text()
    for operation_id in expected.values():
        assert operation_id in serialized
    assert document["components"]["schemas"]["OpenApiStepDraftGenerateRequest"]["properties"]["operationRefs"]["maxItems"] == 20


def test_p2_01_does_not_add_api_catalog_generation_operations() -> None:
    document = json.loads((ROOT / "packages/contracts/openapi/api.openapi.json").read_text())
    api_catalog_operations = {
        operation["operationId"]
        for path, methods in document["paths"].items()
        if path.startswith("/v1/api-catalog/")
        for operation in methods.values()
        if isinstance(operation, dict) and "operationId" in operation
    }
    assert not any("generate" in operation_id.lower() or "import" in operation_id.lower() for operation_id in api_catalog_operations)
