import ast
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_OPENAPI = ROOT / "packages/contracts/openapi/public-api.openapi.json"
BUNDLED_SKILL_OPENAPI = (
    ROOT / "packages/ai-skills/surgepilot-public-api/references/public-api.openapi.json"
)
WEB_OPENAPI = ROOT / "packages/contracts/openapi/api.openapi.json"
PUBLIC_OPERATION_COVERAGE = ROOT / "tests/contract/public_api_operation_coverage.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def assert_coverage_reference_exists(reference: str) -> None:
    file_part, separator, test_name = reference.partition("::")
    path = ROOT / file_part
    assert path.exists(), reference
    if separator and path.suffix == ".py":
        module = ast.parse(path.read_text())
        test_functions = {
            node.name
            for node in ast.walk(module)
            if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef)
        }
        assert test_name in test_functions, reference


def test_public_openapi_artifact_contains_only_public_api_paths() -> None:
    document = load(PUBLIC_OPENAPI)

    assert document["servers"] == [{"url": "/api"}]
    assert document["paths"]
    assert all(path.startswith("/public/v1/") for path in document["paths"])
    assert "/public/v1/scenarios" in document["paths"]
    assert "/public/v1/runs/{runId}/stop" in document["paths"]
    assert "get" not in document["paths"].get("/public/v1/env-groups", {})
    assert not any("account/api-tokens" in path for path in document["paths"])
    assert not any("connectivity-summary" in path for path in document["paths"])
    assert not any(path.startswith("/v1/") for path in document["paths"])


def test_public_api_skill_snapshot_matches_generated_public_artifact() -> None:
    assert BUNDLED_SKILL_OPENAPI.read_bytes() == PUBLIC_OPENAPI.read_bytes()


def test_public_openapi_excludes_token_management_and_secret_material() -> None:
    document = load(PUBLIC_OPENAPI)
    serialized = json.dumps(document, sort_keys=True)

    forbidden_fragments = [
        "AccountApiToken",
        "ApiTokenCreateRequest",
        "ApiTokenCreateResponse",
        "ApiTokenCreated",
        "ApiTokenMetadata",
        "ApiTokenListResponse",
        "plaintext",
        "secretHash",
        "surgepilot_pat_",
        "Authorization",
        "RunReportDetail",
        "DebugHttpTrace",
        "debugHttpTrace",
        "LoadNodeConnectivitySummary",
        "loadNodeApiBaseUrl",
        "publicListEnvGroups",
        "/v1/account/api-tokens",
        "/api/v1/account/api-tokens",
    ]
    for fragment in forbidden_fragments:
        assert fragment not in serialized


def test_public_openapi_excludes_internal_load_node_trust_workflow_error_codes() -> None:
    document = load(PUBLIC_OPENAPI)
    serialized = json.dumps(document, sort_keys=True)
    public_codes = set(document["info"].get("x-surgepilot-error-codes", []))
    internal_trust_codes = {
        "LOAD_NODE_SSH_HOST_KEY_SCAN_FAILED",
        "LOAD_NODE_SSH_HOST_KEY_MISMATCH",
        "LOAD_NODE_SSH_HOST_KEY_UNTRUSTED",
        "LOAD_NODE_SSH_HOST_KEY_CHANGED",
    }

    assert public_codes.isdisjoint(internal_trust_codes)
    for code in internal_trust_codes:
        assert code not in serialized


def test_web_openapi_contains_session_token_management_but_not_internal_runner_routes() -> None:
    document = load(WEB_OPENAPI)
    serialized = json.dumps(document, sort_keys=True)

    assert "/v1/account/api-tokens" in document["paths"]
    assert "/v1/account/api-tokens/{tokenId}" in document["paths"]
    assert "/v1/load-nodes/connectivity-summary" in document["paths"]
    assert "LoadNodeConnectivitySummary" in document["components"]["schemas"]
    assert "ApiTokenCreateRequest" in document["components"]["schemas"]
    assert "ApiTokenMetadata" in document["components"]["schemas"]
    assert "plaintext" in serialized
    assert "secretHash" not in serialized
    assert not any(path.startswith("/internal/") for path in document["paths"])
    assert not any(path.startswith("/public/v1/") for path in document["paths"])


def test_public_openapi_env_group_plain_only_contract() -> None:
    document = load(PUBLIC_OPENAPI)
    schemas = document["components"]["schemas"]

    assert "PublicEnvGroupDetail" in schemas
    assert "PublicEnvGroupCreateRequest" in schemas
    assert "PublicEnvGroupPatchRequest" in schemas
    create_variables = schemas["PublicEnvGroupCreateRequest"]["properties"]["variables"]
    assert create_variables["additionalProperties"] == {"type": "string"}
    patch_variables = schemas["PublicEnvGroupPatchRequest"]["properties"]["variables"]
    assert patch_variables["anyOf"][0]["additionalProperties"] == {"type": "string"}
    response_variables = schemas["PublicEnvGroupDetail"]["properties"]["variables"]
    assert response_variables["additionalProperties"] == {"type": "string"}


def test_public_openapi_dependency_sla_and_resource_contracts_are_explicit() -> None:
    document = load(PUBLIC_OPENAPI)
    paths = document["paths"]
    schemas = document["components"]["schemas"]

    assert paths["/public/v1/dependency-files"]["get"]["operationId"] == (
        "publicListDependencyFiles"
    )
    assert paths["/public/v1/dependency-files"]["post"]["operationId"] == (
        "publicUploadDependencyFile"
    )
    assert paths["/public/v1/dependency-files/{dependencyFileId}"]["delete"]["operationId"] == (
        "publicDeleteDependencyFile"
    )

    subject_schema = schemas["TestPlanSlaRuleInput"]["properties"]["subject"]
    assert subject_schema["oneOf"] == [
        {"enum": ["avg_rt", "p90", "p95", "p99", "fail", "succ", "hits", "bytes"]},
        {"pattern": r"^rc(?:\d{3}|\d\?\?|\*)$"},
    ]
    subject_validator = Draft202012Validator(subject_schema)
    for valid in ("avg_rt", "p95", "rc500", "rc4??", "rc*"):
        assert not list(subject_validator.iter_errors(valid)), valid
    for invalid in ("avg-rt", "rc50", "rc4xx", "rc5000"):
        assert list(subject_validator.iter_errors(invalid)), invalid

    run_resource_validator = Draft202012Validator(schemas["PublicRunResourceRequest"])
    assert not list(
        run_resource_validator.iter_errors({"mode": "manual", "selectedNodeIds": ["node"]})
    )
    assert not list(run_resource_validator.iter_errors({"mode": "auto", "nodeCount": 2}))
    assert list(
        run_resource_validator.iter_errors(
            {"mode": "manual", "selectedNodeIds": ["node"], "nodeCount": 2}
        )
    )
    assert list(
        run_resource_validator.iter_errors(
            {"mode": "auto", "nodeCount": 2, "selectedNodeIds": ["node"]}
        )
    )

    plan_resource_validator = Draft202012Validator(schemas["PublicTestPlanResourceConfig"])
    assert not list(plan_resource_validator.iter_errors({"mode": "manual"}))
    assert not list(plan_resource_validator.iter_errors({"mode": "auto", "nodeCount": 2}))
    assert list(plan_resource_validator.iter_errors({"mode": "manual", "nodeCount": 2}))
    assert list(
        plan_resource_validator.iter_errors(
            {"mode": "auto", "nodeCount": 2, "selectedNodeIds": ["node"]}
        )
    )


def test_public_openapi_operation_coverage_manifest_is_complete() -> None:
    document = load(PUBLIC_OPENAPI)
    operations = {
        operation["operationId"]
        for path_item in document["paths"].values()
        for operation in path_item.values()
    }

    manifest = load(PUBLIC_OPERATION_COVERAGE)
    covered = set(manifest["operations"])

    assert operations - covered == set()
    assert covered - operations == set()
    for operation_id, entry in manifest["operations"].items():
        assert entry["successPathTests"], operation_id
        assert entry["responseAssertions"], operation_id
        for reference in [*entry["successPathTests"], *entry["responseAssertions"]]:
            assert_coverage_reference_exists(reference)
