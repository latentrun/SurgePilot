import os
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_openapi_uses_api_server_and_v1_paths() -> None:
    openapi_path = ROOT / "packages/contracts/openapi/api.openapi.json"

    document = json.loads(openapi_path.read_text())

    assert document["servers"] == [{"url": "/api"}]
    assert "/healthz" not in document["paths"]
    if not document["paths"]:
        assert os.environ.get("SURGEPILOT_ALLOW_EMPTY_OPENAPI_PATHS") == "1", (
            "OpenAPI paths is empty. Set SURGEPILOT_ALLOW_EMPTY_OPENAPI_PATHS=1 only for "
            "intentional placeholder exports."
        )
        return

    assert all(path.startswith("/v1/") for path in document["paths"])


def test_generated_web_client_exists() -> None:
    client_path = ROOT / "packages/contracts/generated/web-client/index.ts"

    assert client_path.exists()
    client_text = client_path.read_text()
    assert "export type paths" in client_text or "export interface paths" in client_text


def test_openapi_exports_runtime_bootstrap_error_codes() -> None:
    openapi_path = ROOT / "packages/contracts/openapi/api.openapi.json"
    document = json.loads(openapi_path.read_text())

    codes = set(document["info"].get("x-surgepilot-error-codes", []))

    assert {
        "LOAD_NODE_TAR_MISSING",
        "LOAD_NODE_RUNTIME_ARTIFACT_MISSING",
        "LOAD_NODE_RUNTIME_ARCH_UNSUPPORTED",
        "LOAD_NODE_RUNTIME_UPLOAD_FAILED",
        "LOAD_NODE_RUNTIME_CHECKSUM_FAILED",
        "LOAD_NODE_RUNTIME_EXTRACT_FAILED",
        "LOAD_NODE_RUNTIME_METADATA_INVALID",
        "LOAD_NODE_RUNTIME_BZT_FAILED",
        "LOAD_NODE_RUNTIME_JMETER_FAILED",
        "LOAD_NODE_RUNTIME_PLUGIN_MISSING",
        "LOAD_NODE_RUNTIME_ACTIVATION_FAILED",
    }.issubset(codes)
