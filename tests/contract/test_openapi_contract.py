import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPORTER = runpy.run_path(str(ROOT / "scripts" / "export_openapi.py"))["_export_document"]


def test_openapi_artifact_uses_api_server_and_v1_business_paths() -> None:
    document = json.loads(
        (ROOT / "packages/contracts/openapi/api.openapi.json").read_text()
    )

    assert document["servers"] == [{"url": "/api"}]
    assert "/healthz" not in document["paths"]
    assert all(path.startswith("/v1/") for path in document["paths"])


def test_export_normalizes_runtime_routes_without_a_double_api_prefix() -> None:
    source = {
        "openapi": "3.1.0",
        "info": {"title": "SurgePilot API", "version": "0.1.0"},
        "paths": {
            "/api/v1/runs": {"get": {"operationId": "listRuns"}},
            "/api/healthz": {"get": {"operationId": "healthz"}},
            "/api/internal/v1/runner/callbacks": {
                "post": {"operationId": "runnerCallback"}
            },
        },
    }

    exported = EXPORTER(source)

    assert exported["servers"] == [{"url": "/api"}]
    assert set(exported["paths"]) == {"/v1/runs"}


def test_generated_web_client_is_present() -> None:
    client_path = ROOT / "packages/contracts/generated/web-client/index.ts"

    assert client_path.exists()
    assert "export type paths" in client_path.read_text() or "export interface paths" in client_path.read_text()
