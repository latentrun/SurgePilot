import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_p0_00_auth_operation_ids_and_contract_shape() -> None:
    document = json.loads((ROOT / "packages/contracts/openapi/api.openapi.json").read_text())

    assert document["servers"] == [{"url": "/api"}]
    paths = document["paths"]
    assert set(paths) >= {
        "/v1/setup/status",
        "/v1/auth/register",
        "/v1/auth/login",
        "/v1/auth/logout",
        "/v1/auth/me",
        "/v1/auth/csrf",
    }
    assert paths["/v1/setup/status"]["get"]["operationId"] == "getSetupStatus"
    setup_schema = document["components"]["schemas"]["SetupStatusResponse"]
    assert "storageAvailable" in setup_schema["properties"]
    assert setup_schema["properties"]["storageAvailable"]["type"] == "boolean"
    runtime_status = setup_schema["properties"]["loadNodeRuntimeStatus"]
    assert runtime_status["anyOf"][0]["enum"] == [
        "ready",
        "not_configured",
        "artifact_missing",
    ]
    assert "loadNodeRuntimeVersionConfigured" not in setup_schema["properties"]
    assert "loadNodeRuntimeArtifactAvailable" not in setup_schema["properties"]
    assert paths["/v1/auth/register"]["post"]["operationId"] == "register"
    assert paths["/v1/auth/login"]["post"]["operationId"] == "login"
    assert paths["/v1/auth/logout"]["post"]["operationId"] == "logout"
    assert paths["/v1/auth/me"]["get"]["operationId"] == "getCurrentUser"
    assert paths["/v1/auth/csrf"]["get"]["operationId"] == "getCsrfToken"

    logout_parameters = paths["/v1/auth/logout"]["post"]["parameters"]
    assert any(parameter["name"] == "x-csrf-token" for parameter in logout_parameters)
    serialized = json.dumps(document)
    assert "passwordHash" not in serialized
    assert "sessionToken" not in serialized
    assert "runnerToken" not in serialized


def test_p0_00_auth_openapi_does_not_expose_fastapi_validation_error_schema() -> None:
    document = json.loads((ROOT / "packages/contracts/openapi/api.openapi.json").read_text())
    serialized = json.dumps(document)

    assert "HTTPValidationError" not in serialized
    assert "ValidationError" not in serialized

    error_ref = "#/components/schemas/ErrorResponse"
    for path in (
        "/v1/auth/register",
        "/v1/auth/login",
        "/v1/auth/logout",
        "/v1/auth/me",
        "/v1/auth/csrf",
    ):
        operation = next(iter(document["paths"][path].values()))
        response = operation["responses"].get("422")
        if response is not None:
            assert response["content"]["application/json"]["schema"]["$ref"] == error_ref
