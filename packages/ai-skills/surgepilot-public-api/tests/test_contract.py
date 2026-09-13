from __future__ import annotations

import importlib.util
import copy
import json
from pathlib import Path
import sys

import pytest
import yaml


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[2]
CANONICAL_OPENAPI = REPO_ROOT / "packages/contracts/openapi/public-api.openapi.json"
BUNDLED_OPENAPI = PACKAGE_ROOT / "references/public-api.openapi.json"
CALLER_PATH = PACKAGE_ROOT / "scripts/surgepilot_call.py"
SKILL_PATH = PACKAGE_ROOT / "SKILL.md"

EXPECTED_OPERATION_IDS = {
    "publicCopyEnvGroup",
    "publicCreateEnvGroup",
    "publicCreateRun",
    "publicCreateScenario",
    "publicCreateTestPlan",
    "publicDeleteEnvGroup",
    "publicDeleteDependencyFile",
    "publicDeleteScenario",
    "publicDeleteTestPlan",
    "publicGetRun",
    "publicGetRunReport",
    "publicGetScenario",
    "publicGetTestPlan",
    "publicListLoadNodes",
    "publicListDependencyFiles",
    "publicListRuns",
    "publicListScenarios",
    "publicListTestPlans",
    "publicPatchEnvGroup",
    "publicPatchScenario",
    "publicPatchTestPlan",
    "publicStopRun",
    "publicUploadDependencyFile",
}


def load_caller():
    assert CALLER_PATH.exists(), "Public API skill caller must exist."
    spec = importlib.util.spec_from_file_location("surgepilot_public_api_caller", CALLER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def operation_ids(document: dict) -> set[str]:
    return {
        operation["operationId"]
        for path_item in document["paths"].values()
        for operation in path_item.values()
        if isinstance(operation, dict) and "operationId" in operation
    }


def write_contract(tmp_path: Path, document: dict) -> Path:
    path = tmp_path / "public-api.openapi.json"
    path.write_text(json.dumps(document))
    return path


def test_bundled_public_openapi_matches_canonical_artifact() -> None:
    assert BUNDLED_OPENAPI.exists(), "Bundled public OpenAPI snapshot must exist."
    assert BUNDLED_OPENAPI.read_bytes() == CANONICAL_OPENAPI.read_bytes()


def test_skill_metadata_and_safety_workflow_are_ci_validated() -> None:
    text = SKILL_PATH.read_text()
    marker, frontmatter_text, body = text.split("---", maxsplit=2)
    frontmatter = yaml.safe_load(frontmatter_text)

    assert marker == ""
    assert frontmatter == {
        "name": "surgepilot-public-api",
        "description": (
            "Use when operating SurgePilot Scenarios, Test Plans, plain-only Env Groups, "
            "Dependency Files, Runs, Run reports, or Load Node summaries through the governed "
            "PAT Bearer public API."
        ),
    }
    for required_instruction in (
        "## Confirm writes",
        "one confirmation",
        "--file",
        "--expected-file-sha256",
        "filename, size, and SHA256",
        "## Fail closed",
        "Never follow HTTP redirects",
        "Never guess or probe another Workspace",
        "Never fall back to cookie/session/CSRF APIs",
        "Env Group operations are plain-only",
    ):
        assert required_instruction in body


def test_bundled_contract_contains_only_current_public_operations() -> None:
    document = json.loads(BUNDLED_OPENAPI.read_text())

    assert document["servers"] == [{"url": "/api"}]
    assert all(path.startswith("/public/v1/") for path in document["paths"])
    assert operation_ids(document) == EXPECTED_OPERATION_IDS
    assert document["components"]["securitySchemes"] == {
        "HTTPBearer": {"scheme": "bearer", "type": "http"}
    }


def test_bundled_contract_excludes_forbidden_routes_and_sensitive_schemas() -> None:
    document = json.loads(BUNDLED_OPENAPI.read_text())
    serialized = json.dumps(document, sort_keys=True)
    schemas = set(document["components"]["schemas"])

    assert not any(path.startswith("/v1/") for path in document["paths"])
    assert not any("account/api-tokens" in path for path in document["paths"])
    assert not any("/internal/" in path for path in document["paths"])
    assert {
        "AccountApiToken",
        "ApiTokenCreateRequest",
        "ApiTokenCreateResponse",
        "EnvGroupSecretVariableRead",
        "EnvGroupSecretVariableWrite",
        "LoadNodeConnectivitySummary",
    }.isdisjoint(schemas)
    for forbidden in (
        '"plaintext"',
        '"secretHash"',
        '"hasValue"',
        '"displayValue"',
        '"objectKey"',
        '"serverPath"',
        '"runnerToken"',
        "surgepilot_pat_",
        "/api/v1/account/api-tokens",
    ):
        assert forbidden not in serialized


def test_caller_allowlist_matches_bundled_contract_exactly() -> None:
    caller = load_caller()
    document = json.loads(BUNDLED_OPENAPI.read_text())

    assert caller.ALLOWED_OPERATION_IDS == frozenset(EXPECTED_OPERATION_IDS)
    assert caller.ALLOWED_OPERATION_IDS == frozenset(operation_ids(document))


def test_load_contract_rejects_unreadable_or_invalid_json(tmp_path: Path) -> None:
    caller = load_caller()
    missing = tmp_path / "missing.json"
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{")

    with pytest.raises(caller.ContractSafetyError, match="unable to load"):
        caller.load_contract(missing)
    with pytest.raises(caller.ContractSafetyError, match="unable to load"):
        caller.load_contract(invalid)


def test_load_contract_rejects_server_and_security_drift(tmp_path: Path) -> None:
    caller = load_caller()
    document = json.loads(BUNDLED_OPENAPI.read_text())

    invalid_server = copy.deepcopy(document)
    invalid_server["servers"] = [{"url": "/"}]
    with pytest.raises(caller.ContractSafetyError, match="fixed /api"):
        caller.load_contract(write_contract(tmp_path, invalid_server))

    invalid_security = copy.deepcopy(document)
    invalid_security["components"]["securitySchemes"]["HTTPBearer"]["scheme"] = "basic"
    with pytest.raises(caller.ContractSafetyError, match="HTTP Bearer"):
        caller.load_contract(write_contract(tmp_path, invalid_security))


def test_load_contract_rejects_non_public_and_invalid_path_items(tmp_path: Path) -> None:
    caller = load_caller()
    document = json.loads(BUNDLED_OPENAPI.read_text())
    first_path = next(iter(document["paths"]))

    non_public = copy.deepcopy(document)
    non_public["paths"]["/v1/forbidden"] = non_public["paths"].pop(first_path)
    with pytest.raises(caller.ContractSafetyError, match="non-public path"):
        caller.load_contract(write_contract(tmp_path, non_public))

    invalid_item = copy.deepcopy(document)
    invalid_item["paths"][first_path] = []
    with pytest.raises(caller.ContractSafetyError, match="invalid path item"):
        caller.load_contract(write_contract(tmp_path, invalid_item))


def test_load_contract_rejects_missing_duplicate_and_drifted_operation_ids(
    tmp_path: Path,
) -> None:
    caller = load_caller()
    document = json.loads(BUNDLED_OPENAPI.read_text())
    missing_id = copy.deepcopy(document)
    next(iter(next(iter(missing_id["paths"].values())).values())).pop("operationId")
    with pytest.raises(caller.ContractSafetyError, match="missing operationId"):
        caller.load_contract(write_contract(tmp_path, missing_id))

    duplicate_id = copy.deepcopy(document)
    duplicate_operations = [
        operation
        for path_item in duplicate_id["paths"].values()
        for operation in path_item.values()
    ]
    duplicate_operations[1]["operationId"] = duplicate_operations[0]["operationId"]
    with pytest.raises(caller.ContractSafetyError, match="duplicate operationId"):
        caller.load_contract(write_contract(tmp_path, duplicate_id))

    drifted = copy.deepcopy(document)
    drifted_operations = [
        operation for path_item in drifted["paths"].values() for operation in path_item.values()
    ]
    drifted_operations[0]["operationId"] = "publicUnexpectedOperation"
    with pytest.raises(caller.ContractSafetyError, match="allowlist drift"):
        caller.load_contract(write_contract(tmp_path, drifted))
