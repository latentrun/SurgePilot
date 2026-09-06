import json
from pathlib import Path

OPENAPI = json.loads(Path("packages/contracts/openapi/api.openapi.json").read_text())


def test_load_node_paths_operation_ids_and_enums() -> None:
    paths = OPENAPI["paths"]
    expected = {
        "/v1/load-nodes": {"get": "listLoadNodes", "post": "createLoadNode"},
        "/v1/load-nodes/{loadNodeId}": {
            "get": "getLoadNode",
            "patch": "patchLoadNode",
            "delete": "deleteLoadNode",
        },
        "/v1/load-nodes/{loadNodeId}/credentials": {"post": "updateLoadNodeCredentials"},
        "/v1/load-nodes/{loadNodeId}/initialize": {"post": "initializeLoadNode"},
        "/v1/load-nodes/{loadNodeId}/init-attempts": {"get": "listLoadNodeInitAttempts"},
        "/v1/load-nodes/{loadNodeId}/init-attempts/{attemptId}": {"get": "getLoadNodeInitAttempt"},
        "/v1/load-nodes/{loadNodeId}/disable": {"post": "disableLoadNode"},
        "/v1/load-nodes/{loadNodeId}/enable": {"post": "enableLoadNode"},
    }
    for path, operations in expected.items():
        assert path in paths
        for method, operation_id in operations.items():
            assert paths[path][method]["operationId"] == operation_id

    schemas = OPENAPI["components"]["schemas"]
    assert set(schemas["LoadNodeSummary"]["properties"]["status"]["enum"]) == {
        "uninitialized",
        "initializing",
        "idle",
        "busy",
        "offline",
        "quarantined",
        "disabled",
    }
    assert schemas["LoadNodeSummary"]["properties"]["scope"]["enum"] == ["public", "workspace"]
    assert schemas["LoadNodeSummary"]["properties"]["authType"]["enum"] == [
        "password",
        "private_key",
        "generated_key",
    ]


def test_load_node_public_schemas_do_not_expose_secret_or_ciphertext_fields() -> None:
    schemas = OPENAPI["components"]["schemas"]
    forbidden = {
        "password",
        "privateKey",
        "privateKeyPassphrase",
        "passwordCiphertext",
        "privateKeyCiphertext",
        "privateKeyPassphraseCiphertext",
        "encryptionKeyVersion",
    }
    for schema_name in ["LoadNodeSummary", "LoadNodeDetail", "LoadNodeInitAttemptDetail"]:
        properties = set(schemas[schema_name]["properties"])
        assert forbidden.isdisjoint(properties)


def test_load_node_write_operations_document_csrf_and_workspace_headers() -> None:
    for path, operations in OPENAPI["paths"].items():
        if not path.startswith("/v1/load-nodes"):
            continue
        for method, operation in operations.items():
            if method not in {"post", "patch", "delete"}:
                continue
            parameters = {(p["in"], p["name"]): p for p in operation.get("parameters", [])}
            assert parameters[("header", "x-csrf-token")]["required"] is True
            assert ("header", "x-workspace-id") in parameters


def test_load_node_error_codes_registered_in_openapi() -> None:
    text = json.dumps(OPENAPI)
    for code in [
        "LOAD_NODE_PUBLIC_ADMIN_REQUIRED",
        "LOAD_NODE_CONFLICT",
        "LOAD_NODE_BUSY",
        "LOAD_NODE_ACTION_NOT_ALLOWED",
        "LOAD_NODE_CREDENTIAL_REQUIRED",
        "LOAD_NODE_CREDENTIAL_INVALID",
        "LOAD_NODE_HOST_INVALID",
        "LOAD_NODE_RUNNER_HOME_INVALID",
        "LOAD_NODE_JMETER_MISSING",
        "CREDENTIAL_DECRYPT_FAILED",
    ]:
        assert code in text
