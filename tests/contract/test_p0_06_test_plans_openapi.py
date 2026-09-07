import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OPENAPI = ROOT / "packages/contracts/openapi/api.openapi.json"
WEB_CLIENT = ROOT / "packages/contracts/generated/web-client/index.ts"


def load_openapi() -> dict:
    return json.loads(OPENAPI.read_text())


def operation(path: str, method: str) -> dict:
    return load_openapi()["paths"][path][method]


def test_test_plan_crud_endpoints_are_public_contracts() -> None:
    schema = load_openapi()

    assert "/v1/test-plans" in schema["paths"]
    assert operation("/v1/test-plans", "get")["operationId"] == "listTestPlans"
    assert operation("/v1/test-plans", "post")["operationId"] == "createTestPlan"
    assert operation("/v1/test-plans/{testPlanId}", "get")["operationId"] == "getTestPlan"
    assert operation("/v1/test-plans/{testPlanId}", "patch")["operationId"] == "patchTestPlan"
    assert operation("/v1/test-plans/{testPlanId}", "delete")["operationId"] == "deleteTestPlan"
    assert "TestPlanDetail" in schema["components"]["schemas"]


def test_run_create_contract_supports_test_plan_shape_and_errors() -> None:
    schema = load_openapi()
    run_create_schema = schema["components"]["schemas"]["RunCreateRequest"]
    serialized = str(run_create_schema)

    assert "test_plan" in serialized
    assert "confirmHighConcurrency" in serialized
    assert "expectedSourceRevision" in serialized
    error_codes = schema["info"].get("x-surgepilot-error-codes", [])
    assert "TEST_PLAN_REVISION_CONFLICT" in error_codes
    assert "TEST_PLAN_NOT_RUNNABLE" in error_codes
    assert "LOAD_SOFT_LIMIT_CONFIRMATION_REQUIRED" in error_codes


def test_generated_web_client_exposes_test_plans_without_internal_runner() -> None:
    web_client_text = WEB_CLIENT.read_text()

    assert '"/v1/test-plans"' in web_client_text
    assert '"/v1/test-plans/{testPlanId}"' in web_client_text
    assert '"/v1/runs"' in web_client_text
    assert "runner/callbacks" not in web_client_text
    assert "runner/artifacts" not in web_client_text
