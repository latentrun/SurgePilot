import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def openapi() -> dict:
    return json.loads((ROOT / "packages/contracts/openapi/api.openapi.json").read_text())


def parameters_for(operation: dict) -> dict[str, dict]:
    return {parameter["name"]: parameter for parameter in operation.get("parameters", [])}


def test_env_group_openapi_paths_and_operation_ids() -> None:
    document = openapi()
    paths = document["paths"]

    assert paths["/v1/env-groups"]["get"]["operationId"] == "listEnvGroups"
    assert paths["/v1/env-groups"]["post"]["operationId"] == "createEnvGroup"
    assert paths["/v1/env-groups/{envGroupId}"]["get"]["operationId"] == "getEnvGroup"
    assert paths["/v1/env-groups/{envGroupId}"]["patch"]["operationId"] == "patchEnvGroup"
    assert paths["/v1/env-groups/{envGroupId}"]["delete"]["operationId"] == "deleteEnvGroup"
    assert (
        paths["/v1/env-groups/{envGroupId}/duplicate"]["post"]["operationId"] == "duplicateEnvGroup"
    )


def test_env_group_openapi_schemas_separate_summary_and_detail() -> None:
    schemas = openapi()["components"]["schemas"]

    assert "variables" not in schemas["EnvGroupSummary"]["properties"]
    assert "variables" in schemas["EnvGroupDetail"]["properties"]
    assert schemas["EnvGroupListResponse"]["properties"]["items"]["items"]["$ref"].endswith(
        "/EnvGroupSummary"
    )
    variable_write = schemas["EnvGroupCreateRequest"]["properties"]["variables"][
        "additionalProperties"
    ]
    assert variable_write == {"type": "string"}
    variable_read = schemas["EnvGroupDetail"]["properties"]["variables"]["additionalProperties"]
    assert variable_read == {"type": "string"}


def test_env_group_openapi_documents_workspace_and_csrf_headers() -> None:
    paths = openapi()["paths"]

    list_params = parameters_for(paths["/v1/env-groups"]["get"])
    create_params = parameters_for(paths["/v1/env-groups"]["post"])
    patch_params = parameters_for(paths["/v1/env-groups/{envGroupId}"]["patch"])
    delete_params = parameters_for(paths["/v1/env-groups/{envGroupId}"]["delete"])
    duplicate_params = parameters_for(paths["/v1/env-groups/{envGroupId}/duplicate"]["post"])

    assert "x-workspace-id" in list_params
    for params in (create_params, patch_params, delete_params, duplicate_params):
        assert "x-workspace-id" in params
        assert "x-csrf-token" in params
        assert params["x-csrf-token"]["required"] is True


def test_env_group_openapi_uses_shared_error_shape() -> None:
    document = openapi()
    paths = document["paths"]

    assert "422" not in paths["/v1/env-groups"]["get"]["responses"]
    conflict_response = paths["/v1/env-groups"]["post"]["responses"]["409"]["content"][
        "application/json"
    ]["schema"]
    validation_response = paths["/v1/env-groups/{envGroupId}"]["patch"]["responses"]["422"][
        "content"
    ]["application/json"]["schema"]

    assert conflict_response == {"$ref": "#/components/schemas/ErrorResponse"}
    assert validation_response == {"$ref": "#/components/schemas/ErrorResponse"}


def test_env_group_error_codes_are_registered() -> None:
    codes = set(openapi()["info"]["x-surgepilot-error-codes"])

    assert {
        "ENV_GROUP_NAME_CONFLICT",
        "ENV_GROUP_IN_USE",
    }.issubset(codes)
