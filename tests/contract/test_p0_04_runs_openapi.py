import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPENAPI = ROOT / "packages/contracts/openapi/api.openapi.json"
WEB_CLIENT = ROOT / "packages/contracts/generated/web-client/index.ts"


def load_openapi() -> dict:
    return json.loads(OPENAPI.read_text())


def test_stop_run_public_contract_is_generated() -> None:
    openapi = load_openapi()
    operation = openapi["paths"]["/v1/runs/{runId}/stop"]["post"]

    assert operation["operationId"] == "stopRun"
    parameter_names = {p["name"] for p in operation["parameters"]}
    assert "runId" in parameter_names
    assert "run_id" not in parameter_names
    assert "x-csrf-token" in parameter_names
    assert "x-workspace-id" in parameter_names
    assert "202" in operation["responses"]
    assert "200" in operation["responses"]


def test_internal_runner_endpoints_are_not_in_public_openapi_or_web_client() -> None:
    openapi_text = OPENAPI.read_text()
    web_client_text = WEB_CLIENT.read_text()

    assert "/api/internal/v1/runner" not in openapi_text
    assert "runner/callbacks" not in openapi_text
    assert "runner/artifacts" not in openapi_text
    assert "runner/callbacks" not in web_client_text
    assert "runner/artifacts" not in web_client_text


def test_p0_04_error_codes_are_registered() -> None:
    codes = set(load_openapi()["info"]["x-surgepilot-error-codes"])

    assert {
        "RUN_TERMINAL_STATE",
        "RUN_STOP_NOT_ALLOWED",
        "RUNNER_UNAUTHORIZED",
        "RUNNER_FORBIDDEN",
        "RUNNER_CALLBACK_INVALID",
        "RUNNER_CALLBACK_CONFLICT",
        "INVALID_ARTIFACT_PATH",
        "INVALID_ARTIFACT_TYPE",
        "ARTIFACT_SIZE_MISMATCH",
        "ARTIFACT_HASH_MISMATCH",
        "ARTIFACT_PATH_CONFLICT",
        "ARTIFACT_NOT_READY",
    }.issubset(codes)
