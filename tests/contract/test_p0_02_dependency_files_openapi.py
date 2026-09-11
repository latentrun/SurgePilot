import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def openapi() -> dict:
    return json.loads((ROOT / "packages/contracts/openapi/api.openapi.json").read_text())


def parameters_for(operation: dict) -> dict[str, dict]:
    return {parameter["name"]: parameter for parameter in operation.get("parameters", [])}


def test_dependency_file_openapi_paths_and_operation_ids() -> None:
    paths = openapi()["paths"]

    assert paths["/v1/dependency-files"]["get"]["operationId"] == "listDependencyFiles"
    assert paths["/v1/dependency-files"]["post"]["operationId"] == "uploadDependencyFile"
    assert (
        paths["/v1/dependency-files/{dependencyFileId}"]["get"]["operationId"]
        == "getDependencyFile"
    )
    assert (
        paths["/v1/dependency-files/{dependencyFileId}/download"]["get"]["operationId"]
        == "downloadDependencyFile"
    )
    assert (
        paths["/v1/dependency-files/{dependencyFileId}/preview"]["get"]["operationId"]
        == "previewDependencyFile"
    )
    assert (
        paths["/v1/dependency-files/{dependencyFileId}"]["delete"]["operationId"]
        == "deleteDependencyFile"
    )


def test_dependency_file_openapi_schemas_exclude_storage_internals() -> None:
    schemas = openapi()["components"]["schemas"]
    for schema_name in (
        "DependencyFileSummary",
        "DependencyFileDetail",
        "DependencyFilePreviewResponse",
    ):
        properties = schemas[schema_name]["properties"]
        assert "storageBucket" not in properties
        assert "storageObjectKey" not in properties
        assert "status" not in properties
        assert "deletedAt" not in properties
    assert schemas["DependencyFileListResponse"]["properties"]["items"]["items"]["$ref"].endswith(
        "/DependencyFileSummary"
    )
    preview = schemas["DependencyFilePreviewResponse"]["properties"]
    assert preview["previewKind"]["$ref"].endswith("/DependencyFilePreviewKind")
    assert preview["reason"]["anyOf"][0]["$ref"].endswith("/DependencyFilePreviewUnavailableReason")
    assert set(schemas["DependencyFilePreviewKind"]["enum"]) == {"text", "unsupported"}
    assert set(schemas["DependencyFilePreviewUnavailableReason"]["enum"]) == {
        "binary_content",
        "decode_failed",
        "storage_unavailable",
    }


def test_dependency_file_openapi_documents_upload_download_and_headers() -> None:
    paths = openapi()["paths"]
    list_params = parameters_for(paths["/v1/dependency-files"]["get"])
    upload = paths["/v1/dependency-files"]["post"]
    upload_params = parameters_for(upload)
    delete_params = parameters_for(paths["/v1/dependency-files/{dependencyFileId}"]["delete"])

    assert "x-workspace-id" in list_params
    assert upload["requestBody"]["content"]["multipart/form-data"]["schema"]["properties"][
        "file"
    ] == {
        "type": "string",
        "format": "binary",
    }
    for params in (upload_params, delete_params):
        assert "x-workspace-id" in params
        assert "x-csrf-token" in params
        assert params["x-csrf-token"]["required"] is True

    download_200 = paths["/v1/dependency-files/{dependencyFileId}/download"]["get"]["responses"][
        "200"
    ]
    assert set(download_200["content"]) == {"application/octet-stream"}
    assert download_200["content"]["application/octet-stream"]["schema"] == {
        "type": "string",
        "format": "binary",
    }
    preview_params = parameters_for(paths["/v1/dependency-files/{dependencyFileId}/preview"]["get"])
    assert "x-workspace-id" in preview_params
    assert "x-csrf-token" not in preview_params
    preview_200 = paths["/v1/dependency-files/{dependencyFileId}/preview"]["get"]["responses"][
        "200"
    ]
    assert preview_200["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/DependencyFilePreviewResponse"
    }


def test_dependency_file_openapi_uses_shared_error_shape_and_codes_are_documented() -> None:
    paths = openapi()["paths"]
    assert "422" not in paths["/v1/dependency-files"]["get"]["responses"]
    assert paths["/v1/dependency-files"]["post"]["responses"]["409"]["content"]["application/json"][
        "schema"
    ] == {"$ref": "#/components/schemas/ErrorResponse"}
    assert paths["/v1/dependency-files/{dependencyFileId}/download"]["get"]["responses"]["503"][
        "content"
    ]["application/json"]["schema"] == {"$ref": "#/components/schemas/ErrorResponse"}
    assert paths["/v1/dependency-files/{dependencyFileId}/preview"]["get"]["responses"]["503"][
        "content"
    ]["application/json"]["schema"] == {"$ref": "#/components/schemas/ErrorResponse"}
    document_text = json.dumps(openapi())
    for expected_code in (
        "INVALID_FILENAME",
        "DEPENDENCY_FILE_NAME_CONFLICT",
        "PAYLOAD_TOO_LARGE",
        "STORAGE_UNAVAILABLE",
        "FILE_IN_USE",
    ):
        assert expected_code in document_text
    assert "storage_object_key" not in document_text
    assert "storageObjectKey" not in document_text
