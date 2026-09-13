from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError

import pytest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CALLER_PATH = PACKAGE_ROOT / "scripts/surgepilot_call.py"


def load_caller():
    assert CALLER_PATH.exists(), "Public API skill caller must exist."
    spec = importlib.util.spec_from_file_location("surgepilot_public_api_caller", CALLER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def caller():
    return load_caller()


def build(caller, operation_id: str, **overrides):
    values = {
        "operation_id": operation_id,
        "base_url": "https://surgepilot.example.com",
        "token": "surgepilot_pat_test_secret",
        "workspace_id": "01JWORKSPACE00000000000000",
        "path_params": {},
        "query_params": {},
        "body": None,
    }
    values.update(overrides)
    return caller.build_request(**values)


def test_build_request_rejects_unknown_operation(caller) -> None:
    with pytest.raises(caller.LocalInputError, match="not allowlisted"):
        build(caller, "listAccountApiTokens")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("base_url", ""),
        ("base_url", "https://user:password@surgepilot.example.com"),
        ("base_url", "https://surgepilot.example.com/api"),
        ("token", ""),
        ("workspace_id", ""),
    ],
)
def test_build_request_requires_safe_explicit_configuration(caller, field: str, value: str) -> None:
    with pytest.raises(caller.LocalInputError):
        build(caller, "publicListScenarios", **{field: value})


def test_build_request_rejects_non_http_origin(caller) -> None:
    with pytest.raises(caller.LocalInputError, match="absolute http"):
        build(caller, "publicListScenarios", base_url="ftp://surgepilot.example.com")


def test_build_request_uses_only_contract_url_and_fixed_headers(caller) -> None:
    request = build(
        caller,
        "publicGetScenario",
        path_params={"scenarioId": "scenario with spaces"},
    )

    assert request.url == (
        "https://surgepilot.example.com/api/public/v1/scenarios/scenario%20with%20spaces"
    )
    assert request.method == "GET"
    assert request.headers == {
        "Accept": "application/json",
        "Authorization": "Bearer surgepilot_pat_test_secret",
        "x-workspace-id": "01JWORKSPACE00000000000000",
    }
    assert request.body is None


def test_build_request_validates_path_and_query_parameter_names_and_types(caller) -> None:
    with pytest.raises(caller.LocalInputError, match="scenarioId"):
        build(caller, "publicGetScenario")
    with pytest.raises(caller.LocalInputError, match="unknown path parameter"):
        build(
            caller,
            "publicGetScenario",
            path_params={"scenarioId": "01JSCENARIO00000000000000", "workspaceId": "forbidden"},
        )
    with pytest.raises(caller.LocalInputError, match="page"):
        build(caller, "publicListScenarios", query_params={"page": "2"})
    with pytest.raises(caller.LocalInputError, match="unknown query parameter"):
        build(caller, "publicListScenarios", query_params={"workspaceId": "forbidden"})


def test_build_request_encodes_array_query_parameters(caller) -> None:
    request = build(
        caller,
        "publicListScenarios",
        query_params={"page": 2, "tag": ["smoke", "public api"]},
    )

    assert request.url == (
        "https://surgepilot.example.com/api/public/v1/scenarios?page=2&tag=smoke&tag=public+api"
    )


def test_build_request_validates_required_json_body(caller) -> None:
    with pytest.raises(caller.LocalInputError, match="request body is required"):
        build(caller, "publicCreateEnvGroup")
    with pytest.raises(caller.LocalInputError, match="name"):
        build(caller, "publicCreateEnvGroup", body={"variables": {}})


def test_build_request_rejects_body_for_read_operation(caller) -> None:
    with pytest.raises(caller.LocalInputError, match="does not accept"):
        build(caller, "publicListScenarios", body={})


def test_dependency_file_upload_requires_dedicated_file_input(caller, tmp_path: Path) -> None:
    upload = tmp_path / "setup.groovy"
    upload.write_text("println('ok')\n", encoding="utf-8")

    with pytest.raises(caller.LocalInputError, match="--file is required"):
        build(caller, "publicUploadDependencyFile")
    with pytest.raises(caller.LocalInputError, match="accepts --file"):
        build(caller, "publicUploadDependencyFile", body={"file": "forbidden"}, file_path=upload)
    with pytest.raises(caller.LocalInputError, match="supported only"):
        build(caller, "publicListScenarios", file_path=upload)


def test_dependency_file_upload_confirmation_exposes_metadata_not_content(
    caller, tmp_path: Path
) -> None:
    upload = tmp_path / "setup.groovy"
    content = b"println('do-not-print-this-content')\n"
    upload.write_bytes(content)

    request = build(caller, "publicUploadDependencyFile", file_path=upload)
    summary = caller.summarize_confirmation(request)
    serialized = json.dumps(summary, sort_keys=True)

    assert request.body is None
    assert summary["targetResource"] == "setup.groovy"
    assert summary["keyParameters"]["file"] == {
        "filename": "setup.groovy",
        "sizeBytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    assert "do-not-print-this-content" not in serialized


def test_dependency_file_upload_rejects_invalid_local_files(caller, tmp_path: Path) -> None:
    missing = tmp_path / "missing.groovy"
    with pytest.raises(caller.LocalInputError, match="existing regular file"):
        caller._prepare_file_upload(missing)

    invalid_name = tmp_path / 'bad"name.groovy'
    invalid_name.write_text("println('bad')\n", encoding="utf-8")
    with pytest.raises(caller.LocalInputError, match="filename contains unsupported"):
        caller._prepare_file_upload(invalid_name)


def test_dependency_file_upload_contract_fails_closed_on_schema_drift(
    caller, tmp_path: Path
) -> None:
    upload = tmp_path / "setup.groovy"
    upload.write_text("println('ok')\n", encoding="utf-8")
    base_contract = caller.load_contract()

    no_multipart = copy.deepcopy(base_contract)
    no_multipart["paths"]["/public/v1/dependency-files"]["post"]["requestBody"]["content"] = {}
    with pytest.raises(caller.ContractSafetyError, match="multipart/form-data"):
        build(caller, "publicUploadDependencyFile", file_path=upload, contract=no_multipart)

    unsupported_ref = copy.deepcopy(base_contract)
    unsupported_ref["paths"]["/public/v1/dependency-files"]["post"]["requestBody"]["content"][
        "multipart/form-data"
    ]["schema"] = {"$ref": "https://example.invalid/schema"}
    with pytest.raises(caller.ContractSafetyError, match="unsupported schema reference"):
        build(caller, "publicUploadDependencyFile", file_path=upload, contract=unsupported_ref)

    missing_ref = copy.deepcopy(base_contract)
    missing_ref["paths"]["/public/v1/dependency-files"]["post"]["requestBody"]["content"][
        "multipart/form-data"
    ]["schema"] = {"$ref": "#/components/schemas/MissingUploadSchema"}
    with pytest.raises(caller.ContractSafetyError, match="missing schema"):
        build(caller, "publicUploadDependencyFile", file_path=upload, contract=missing_ref)

    missing_file = copy.deepcopy(base_contract)
    upload_schema = missing_file["paths"]["/public/v1/dependency-files"]["post"]["requestBody"][
        "content"
    ]["multipart/form-data"]["schema"]
    upload_schema["properties"] = {}
    with pytest.raises(caller.ContractSafetyError, match="one binary file field"):
        build(caller, "publicUploadDependencyFile", file_path=upload, contract=missing_file)

    invalid_binary = copy.deepcopy(base_contract)
    upload_schema = invalid_binary["paths"]["/public/v1/dependency-files"]["post"]["requestBody"][
        "content"
    ]["multipart/form-data"]["schema"]
    upload_schema["properties"]["file"] = {"type": "string"}
    with pytest.raises(caller.ContractSafetyError, match="one binary file field"):
        build(caller, "publicUploadDependencyFile", file_path=upload, contract=invalid_binary)


def test_dependency_file_upload_detects_read_failure_and_in_process_change(
    caller, tmp_path: Path
) -> None:
    upload = tmp_path / "setup.groovy"
    upload.write_bytes(b"original")
    prepared = caller._prepare_file_upload(upload)
    upload.unlink()
    with pytest.raises(caller.LocalInputError, match="unable to read --file"):
        caller._multipart_file_body(prepared)

    upload.write_bytes(b"original")
    prepared = caller._prepare_file_upload(upload)
    upload.write_bytes(b"changed!")
    with pytest.raises(caller.LocalInputError, match="changed after confirmation preview"):
        caller._multipart_file_body(prepared)


def test_build_request_rejects_secret_bearing_env_group_payload(caller) -> None:
    body = {
        "name": "Production",
        "variables": {"PASSWORD": {"type": "secret", "value": "do-not-send"}},
    }

    with pytest.raises(caller.ContractSafetyError, match="secret-bearing"):
        build(caller, "publicCreateEnvGroup", body=body)


def test_build_request_rejects_forbidden_payload_field(caller) -> None:
    with pytest.raises(caller.ContractSafetyError, match="runnerToken"):
        build(
            caller,
            "publicCreateEnvGroup",
            body={"name": "Production", "runnerToken": "must-not-send"},
        )
    with pytest.raises(caller.ContractSafetyError, match="credential-like"):
        build(
            caller,
            "publicCreateEnvGroup",
            body={"name": "Production", "description": "surgepilot_pat_test_secret"},
        )
    with pytest.raises(caller.ContractSafetyError, match="credential-like"):
        build(
            caller,
            "publicCreateEnvGroup",
            body={
                "name": "Production",
                "variables": {"surgepilot_pat_test_secret": {"type": "plain", "value": "hidden"}},
            },
        )


def test_build_request_rejects_operation_and_schema_drift(caller) -> None:
    contract = caller.load_contract()

    missing_operation = copy.deepcopy(contract)
    missing_operation["paths"].pop("/public/v1/scenarios")
    with pytest.raises(caller.ContractSafetyError, match="missing from bundled contract"):
        build(caller, "publicListScenarios", contract=missing_operation)

    missing_schema = copy.deepcopy(contract)
    create_operation = missing_schema["paths"]["/public/v1/env-groups"]["post"]
    create_operation["requestBody"]["content"]["application/json"]["schema"] = None
    with pytest.raises(caller.ContractSafetyError, match="application/json"):
        build(
            caller,
            "publicCreateEnvGroup",
            body={"name": "Production"},
            contract=missing_schema,
        )


def test_build_request_rejects_unexpected_public_header_contract(caller) -> None:
    contract = copy.deepcopy(caller.load_contract())
    operation = contract["paths"]["/public/v1/scenarios"]["get"]
    operation["parameters"].append(
        {"in": "header", "name": "x-internal-token", "schema": {"type": "string"}}
    )

    with pytest.raises(caller.ContractSafetyError, match="unexpected public header"):
        build(caller, "publicListScenarios", contract=contract)


def test_write_confirmation_summary_redacts_credentials_and_nested_values(caller) -> None:
    request = build(
        caller,
        "publicCreateEnvGroup",
        body={
            "name": "Production",
            "description": "Primary environment",
            "variables": {"PASSWORD": {"type": "plain", "value": "sensitive-value"}},
        },
    )

    summary = caller.summarize_confirmation(request)
    serialized = json.dumps(summary, sort_keys=True)

    assert summary["confirmationRequired"] is True
    assert summary["workspaceId"] == "01JWORKSPACE00000000000000"
    assert summary["operationId"] == "publicCreateEnvGroup"
    assert summary["method"] == "POST"
    assert summary["targetResource"] == "Production"
    assert summary["keyParameters"]["variables"] == {"keys": ["PASSWORD"]}
    assert "surgepilot_pat_test_secret" not in serialized
    assert "sensitive-value" not in serialized


def test_confirmation_summary_covers_path_query_and_nested_collections(caller) -> None:
    path_request = build(
        caller,
        "publicStopRun",
        path_params={"runId": "01JRUN0000000000000000000"},
    )
    query_request = build(
        caller,
        "publicListScenarios",
        query_params={"tag": ["api", "smoke"]},
    )
    scenario_request = build(
        caller,
        "publicCreateScenario",
        body={
            "name": "Checkout",
            "globalHeaders": [{"id": "H" * 26, "name": "Authorization", "value": "hidden"}],
            "tags": ["api"],
        },
    )
    run_request = build(
        caller,
        "publicCreateRun",
        body={
            "runType": "standard",
            "sourceType": "test_plan",
            "sourceId": "S" * 26,
            "expectedSourceRevision": 1,
            "resourceRequest": {"mode": "auto", "nodeCount": 2},
        },
    )

    assert caller.summarize_confirmation(path_request)["targetResource"] == (
        "01JRUN0000000000000000000"
    )
    assert caller.summarize_confirmation(query_request)["keyParameters"]["tag"] == {"count": 2}
    scenario_summary = caller.summarize_confirmation(scenario_request)
    assert scenario_summary["keyParameters"]["globalHeaders"] == {"count": 1}
    assert scenario_summary["keyParameters"]["tags"] == {"count": 1}
    assert "hidden" not in json.dumps(scenario_summary)
    assert caller.summarize_confirmation(run_request)["keyParameters"]["resourceRequest"] == {
        "keys": ["mode", "nodeCount"]
    }


def test_run_cli_prepares_write_without_network_until_confirmed(caller, capsys) -> None:
    calls = 0

    def fail_if_called(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("network must not be called before confirmation")

    exit_code = caller.run_cli(
        [
            "publicCreateEnvGroup",
            "--body-json",
            '{"name":"Production","variables":{}}',
        ],
        environ={
            "SURGEPILOT_PUBLIC_API_BASE": "https://surgepilot.example.com",
            "SURGEPILOT_PAT": "surgepilot_pat_test_secret",
            "SURGEPILOT_WORKSPACE_ID": "01JWORKSPACE00000000000000",
        },
        opener=fail_if_called,
    )

    output = capsys.readouterr().out
    assert exit_code == 2
    assert calls == 0
    assert '"confirmationRequired": true' in output
    assert "surgepilot_pat_test_secret" not in output


def test_run_cli_rejects_caller_supplied_url_or_headers(caller) -> None:
    parser = caller.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["publicListScenarios", "--url", "https://evil.example.com"])
    with pytest.raises(SystemExit):
        parser.parse_args(["publicListScenarios", "--header-json", "{}"])


class Response:
    def __init__(self, payload: object, status: int = 200) -> None:
        self.payload = json.dumps(payload).encode()
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self.payload


def cli_environment() -> dict[str, str]:
    return {
        "SURGEPILOT_PUBLIC_API_BASE": "https://surgepilot.example.com",
        "SURGEPILOT_PAT": "surgepilot_pat_test_secret",
        "SURGEPILOT_WORKSPACE_ID": "01JWORKSPACE00000000000000",
    }


def test_run_cli_executes_reads_and_confirmed_writes(caller, capsys) -> None:
    requests = []

    def opener(request, timeout):
        requests.append((request, timeout))
        if request.method == "GET":
            return Response({"items": [], "page": 1, "pageSize": 20, "total": 0})
        return Response(
            {
                "id": "01JENVGROUP000000000000000",
                "name": "Production",
                "variableCount": 0,
                "inUse": False,
                "createdBy": "01JUSER0000000000000000000",
                "updatedBy": "01JUSER0000000000000000000",
                "createdAt": "2030-07-13T00:00:00Z",
                "updatedAt": "2030-07-13T00:00:00Z",
                "variables": {},
            },
            status=201,
        )

    read_exit = caller.run_cli(["publicListScenarios"], environ=cli_environment(), opener=opener)
    write_exit = caller.run_cli(
        [
            "publicCreateEnvGroup",
            "--body-json",
            '{"name":"Production","variables":{}}',
            "--confirm",
        ],
        environ=cli_environment(),
        opener=opener,
    )

    output = capsys.readouterr().out
    assert read_exit == 0
    assert write_exit == 0
    assert len(requests) == 2
    assert requests[1][0].method == "POST"
    assert "surgepilot_pat_test_secret" not in output


def test_run_cli_uploads_dependency_file_only_after_confirmation(
    caller, capsys, tmp_path: Path
) -> None:
    upload = tmp_path / "setup.groovy"
    content = b"println('upload')\n"
    upload.write_bytes(content)
    requests = []

    def opener(request, timeout):
        requests.append((request, timeout))
        return Response(
            {
                "id": "01JDEPENDENCY00000000000000",
                "filename": "setup.groovy",
                "contentType": "text/x-groovy",
                "sizeBytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "inUse": False,
                "createdBy": "01JUSER0000000000000000000",
                "createdAt": "2030-07-13T00:00:00Z",
            },
            status=201,
        )

    preview_exit = caller.run_cli(
        ["publicUploadDependencyFile", "--file", str(upload)],
        environ=cli_environment(),
        opener=lambda *_args, **_kwargs: pytest.fail("network called before confirmation"),
    )
    upload_exit = caller.run_cli(
        [
            "publicUploadDependencyFile",
            "--file",
            str(upload),
            "--confirm",
            "--expected-file-sha256",
            hashlib.sha256(content).hexdigest(),
        ],
        environ=cli_environment(),
        opener=opener,
    )

    output = capsys.readouterr().out
    assert preview_exit == 2
    assert upload_exit == 0
    assert len(requests) == 1
    request = requests[0][0]
    assert request.method == "POST"
    assert request.headers["Content-type"].startswith("multipart/form-data; boundary=")
    assert b'Content-Disposition: form-data; name="file"; filename="setup.groovy"' in request.data
    assert content in request.data
    preview_part = output.split('"status": 201', 1)[0]
    assert "println('upload')" not in preview_part


def test_run_cli_rejects_changed_dependency_file_after_confirmation(
    caller, capsys, tmp_path: Path
) -> None:
    upload = tmp_path / "setup.groovy"
    original = b"println('original')\n"
    upload.write_bytes(b"println('changed')\n")

    exit_code = caller.run_cli(
        [
            "publicUploadDependencyFile",
            "--file",
            str(upload),
            "--confirm",
            "--expected-file-sha256",
            hashlib.sha256(original).hexdigest(),
        ],
        environ=cli_environment(),
        opener=lambda *_args, **_kwargs: pytest.fail("changed file must not be uploaded"),
    )

    error = capsys.readouterr().err
    assert exit_code == 2
    assert "changed after confirmation preview" in error


def test_run_cli_rejects_file_hash_option_for_non_upload_operation(caller, capsys) -> None:
    exit_code = caller.run_cli(
        [
            "publicListScenarios",
            "--expected-file-sha256",
            "a" * 64,
        ],
        environ=cli_environment(),
        opener=lambda *_args, **_kwargs: pytest.fail("invalid local input must not call network"),
    )

    error = capsys.readouterr().err
    assert exit_code == 2
    assert "supported only for publicUploadDependencyFile" in error


def test_run_cli_requires_confirmed_sha_for_dependency_upload(
    caller, capsys, tmp_path: Path
) -> None:
    upload = tmp_path / "setup.groovy"
    upload.write_bytes(b"println('upload')\n")

    exit_code = caller.run_cli(
        ["publicUploadDependencyFile", "--file", str(upload), "--confirm"],
        environ=cli_environment(),
        opener=lambda *_args, **_kwargs: pytest.fail("missing confirmed SHA must not call network"),
    )

    error = capsys.readouterr().err
    assert exit_code == 2
    assert "required with --confirm for file upload" in error


@pytest.mark.parametrize(
    ("argv", "expected_error"),
    [
        (["publicListScenarios", "--query-json", "[]"], "LOCAL_INPUT_ERROR"),
        (["publicListScenarios", "--query-json", "{"], "LOCAL_INPUT_ERROR"),
    ],
)
def test_run_cli_reports_local_json_errors(caller, capsys, argv, expected_error) -> None:
    exit_code = caller.run_cli(argv, environ=cli_environment())

    error = capsys.readouterr().err
    assert exit_code == 2
    assert expected_error in error


def test_run_cli_reports_public_network_and_contract_errors(caller, capsys) -> None:
    error_body = json.dumps(
        {
            "code": "UNAUTHENTICATED",
            "message": "Authentication required.",
            "requestId": "req_public_error",
            "details": None,
        }
    ).encode()

    def public_error(request, timeout):
        raise HTTPError(request.full_url, 401, "failed", {}, io.BytesIO(error_body))

    def network_error(_request, timeout):
        raise URLError("offline")

    def contract_error(_request, timeout):
        return Response({"runnerToken": "forbidden"})

    public_exit = caller.run_cli(
        ["publicListScenarios"], environ=cli_environment(), opener=public_error
    )
    network_exit = caller.run_cli(
        ["publicListScenarios"], environ=cli_environment(), opener=network_error
    )
    contract_exit = caller.run_cli(
        ["publicListScenarios"], environ=cli_environment(), opener=contract_error
    )

    error = capsys.readouterr().err
    assert public_exit == 3
    assert network_exit == 3
    assert contract_exit == 4
    assert "UNAUTHENTICATED" in error
    assert "NETWORK_ERROR" in error
    assert "CONTRACT_SAFETY_ERROR" in error


def test_main_exits_with_run_cli_result(caller, monkeypatch) -> None:
    monkeypatch.setattr(caller, "run_cli", lambda: 7)

    with pytest.raises(SystemExit) as error:
        caller.main()

    assert error.value.code == 7
