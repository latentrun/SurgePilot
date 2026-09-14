from datetime import UTC, datetime, timedelta

import pytest
import yaml
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.auth import DEFAULT_WORKSPACE_ID, User
from app.models.dependency_files import DependencyFile
from app.schemas.scenarios import ScenarioCreateRequest
from app.services.scenarios import (
    RUNTIME_JMETER_VERSION,
    build_debug_taurus_document_from_content,
    create_scenario,
    runtime_jmeter_path,
    validate_scenario_content,
)


def step(**overrides: object) -> dict:
    data = {
        "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
        "enabled": True,
        "name": "List users",
        "method": "GET",
        "path": "/api/${api_version}/users",
        "queryParams": [],
        "headers": [
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
                "name": "X-Step",
                "value": "local",
                "enabled": True,
            }
        ],
        "body": {"type": "none", "contentType": None, "rawText": None, "formFields": []},
        "uploadFiles": [],
        "extractors": [],
        "assertions": [],
        "scripts": [],
        "settings": {
            "thinkTimeMs": None,
            "timeoutMs": None,
            "followRedirects": None,
            "keepAlive": None,
        },
    }
    data.update(overrides)
    return data


def payload(**overrides: object) -> dict:
    data = {
        "name": "Checkout API",
        "description": "Debug checkout flow",
        "tags": ["checkout"],
        "baseUrlExpression": "${base_url}",
        "defaultSettings": {
            "thinkTimeMs": 0,
            "timeoutMs": 30000,
            "followRedirects": True,
            "keepAlive": True,
            "storeCache": True,
            "storeCookie": True,
            "retrieveResources": False,
        },
        "globalHeaders": [
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
                "name": "X-API-Version",
                "value": "${api_version}",
                "enabled": True,
            },
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7D",
                "name": "X-Disabled",
                "value": "${missing_disabled}",
                "enabled": False,
            },
        ],
        "variables": [
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7E",
                "name": "base_url",
                "value": "https://scenario.example.test",
                "enabled": True,
            },
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7F",
                "name": "api_version",
                "value": "v1",
                "enabled": True,
            },
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7G",
                "name": "disabled_value",
                "value": "ignored",
                "enabled": False,
            },
        ],
        "dataSources": [],
        "steps": [step()],
    }
    data.update(overrides)
    return data


def seed_user(db_session: Session) -> User:
    user = User(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7Z",
        email="scenario-global-config@example.com",
        display_name="Scenario Global Config User",
        password_hash="hash",
        role="admin",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(user)
    db_session.flush()
    return user


async def register(client: AsyncClient, email: str) -> tuple[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "displayName": "P1-09 User", "password": "password123"},
    )
    assert response.status_code == 201
    body = response.json()
    return body["csrfToken"], body["defaultWorkspace"]["id"]


def future_expiry() -> str:
    return (datetime.now(UTC) + timedelta(days=30)).isoformat().replace("+00:00", "Z")


def dependency_file(file_id: str = "01HZX3Y9M0E9W7Z6M5QK9S8P8A") -> DependencyFile:
    return DependencyFile(
        id=file_id,
        workspace_id=DEFAULT_WORKSPACE_ID,
        filename="users.csv",
        content_type="text/csv",
        size_bytes=16,
        sha256="a" * 64,
        storage_bucket="surgepilot",
        storage_object_key="dependency-files/not-returned/users.csv",
        status="available",
        created_by="01HZX3Y9M0E9W7Z6M5QK9S8P7Z",
        created_at=datetime.now(UTC),
    )


def test_global_headers_and_variables_generate_taurus_with_env_override(
    db_session: Session,
) -> None:
    scenario_content = payload()

    document = build_debug_taurus_document_from_content(
        scenario_content=scenario_content,
        env_variables={"api_version": "v2"},
        dependency_files=[],
        jmeter_path=runtime_jmeter_path("/opt/surgepilot/runner"),
        jmeter_version=RUNTIME_JMETER_VERSION,
    )

    scenario_doc = document["scenarios"]["surgepilot_scenario"]
    assert scenario_doc["default-address"] == "https://scenario.example.test"
    assert scenario_doc["headers"] == {"X-API-Version": "${api_version}"}
    assert scenario_doc["variables"] == {
        "base_url": "https://scenario.example.test",
        "api_version": "v2",
    }
    assert scenario_doc["requests"][0]["headers"] == {"X-Step": "local"}
    assert "X-Disabled" not in yaml.safe_dump(document)
    assert "disabled_value" not in scenario_doc["variables"]
    assert "jsr223" not in scenario_doc


def test_global_configuration_validation_rejects_invalid_duplicates_and_conflicts() -> None:
    invalid = payload(
        globalHeaders=[
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
                "name": "Bad Header",
                "value": "v1",
                "enabled": True,
            },
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7D",
                "name": "bad header",
                "value": "v2",
                "enabled": False,
            },
        ],
        variables=[
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7E",
                "name": "api-version",
                "value": "v1",
                "enabled": True,
            },
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7F",
                "name": "api-version",
                "value": "v2",
                "enabled": False,
            },
        ],
        dataSources=[
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7H",
                "dependencyFileId": "01HZX3Y9M0E9W7Z6M5QK9S8P7I",
                "displayName": "users.csv",
                "delimiter": ",",
                "quoted": None,
                "loop": True,
                "variableNames": ["not-valid"],
                "randomOrder": False,
                "enabled": False,
            }
        ],
        steps=[
            step(
                extractors=[
                    {
                        "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7J",
                        "type": "jsonpath",
                        "variableName": "api-version",
                        "expression": "$.id",
                        "defaultValue": "",
                        "matchNo": 1,
                        "subject": "body",
                        "enabled": True,
                    }
                ],
            )
        ],
    )

    with pytest.raises(AppError) as exc_info:
        validate_scenario_content(invalid)

    assert exc_info.value.code == "VALIDATION_ERROR"
    codes = {detail["code"] for detail in exc_info.value.details}
    assert {"invalid_header_name", "duplicate_header", "invalid_variable_name"}.issubset(codes)
    fields = {detail["field"] for detail in exc_info.value.details}
    assert "globalHeaders[0].name" in fields
    assert "variables[0].name" in fields
    assert "dataSources[0].variableNames[0]" in fields


def test_scenario_schema_rejects_nested_unsupported_fields() -> None:
    invalid = payload(
        defaultSettings={
            **payload()["defaultSettings"],
            "env": {"UNSUPPORTED": "true"},
        },
        globalHeaders=[
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
                "name": "X-API-Version",
                "value": "v1",
                "enabled": True,
                "secret": True,
            }
        ],
        steps=[
            {
                **step(),
                "jsr223": [],
                "settings": {**step()["settings"], "env": {"BAD": "true"}},
            }
        ],
    )

    with pytest.raises(ValidationError) as exc_info:
        ScenarioCreateRequest.model_validate(invalid)

    fields = {".".join(str(part) for part in error["loc"]) for error in exc_info.value.errors()}
    assert {
        "defaultSettings.env",
        "globalHeaders.0.secret",
        "steps.0.jsr223",
        "steps.0.settings.env",
    }.issubset(fields)


@pytest.mark.anyio
async def test_public_scenario_api_rejects_nested_unsupported_fields(
    client: AsyncClient,
) -> None:
    csrf, workspace_id = await register(client, "p1-09-public-strict@example.com")
    token_response = await client.post(
        "/api/v1/account/api-tokens",
        headers={"x-csrf-token": csrf},
        json={
            "name": "Public scenario writer",
            "scopes": ["config:write"],
            "workspaceAllowlist": [workspace_id],
            "expiresAt": future_expiry(),
        },
    )
    assert token_response.status_code == 201
    token = token_response.json()["token"]["plaintext"]
    invalid = payload(
        defaultSettings={
            **payload()["defaultSettings"],
            "env": {"UNSUPPORTED": "true"},
        },
        variables=[
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7E",
                "name": "base_url",
                "value": "https://scenario.example.test",
                "enabled": True,
                "secretHash": "not-allowed",
            }
        ],
        steps=[{**step(), "jsr223": []}],
    )

    response = await client.post(
        "/api/public/v1/scenarios",
        headers={"Authorization": f"Bearer {token}", "x-workspace-id": workspace_id},
        json=invalid,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.anyio
async def test_scenario_api_patch_persists_global_configuration_and_detail_reads_back(
    client: AsyncClient,
) -> None:
    csrf, workspace_id = await register(client, "p1-09-patch@example.com")
    created = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=payload(),
    )
    assert created.status_code == 201
    scenario = created.json()
    next_headers = [
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8B",
            "name": "X-Trace-Mode",
            "value": "${trace_mode}",
            "enabled": True,
        }
    ]
    next_variables = [
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8C",
            "name": "base_url",
            "value": "https://patched.example.test",
            "enabled": True,
        },
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8D",
            "name": "trace_mode",
            "value": "full",
            "enabled": True,
        },
    ]

    patched = await client.patch(
        f"/api/v1/scenarios/{scenario['id']}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            **payload(),
            "expectedRevision": scenario["revision"],
            "globalHeaders": next_headers,
            "variables": next_variables,
        },
    )

    assert patched.status_code == 200
    assert patched.json()["globalHeaders"] == next_headers
    assert patched.json()["variables"] == next_variables

    detail = await client.get(
        f"/api/v1/scenarios/{scenario['id']}",
        headers={"x-workspace-id": workspace_id},
    )
    assert detail.status_code == 200
    assert detail.json()["globalHeaders"] == next_headers
    assert detail.json()["variables"] == next_variables

    listed = await client.get("/api/v1/scenarios", headers={"x-workspace-id": workspace_id})
    assert listed.status_code == 200
    summary = listed.json()["items"][0]
    assert "globalHeaders" not in summary
    assert "variables" not in summary


def test_debug_variable_validation_rejects_extractor_conflict_with_env_group_variable() -> None:
    conflicting_step = step(
        extractors=[
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8F",
                "type": "jsonpath",
                "variableName": "session_id",
                "expression": "$.session",
                "defaultValue": "",
                "matchNo": 1,
                "subject": "body",
                "enabled": True,
            }
        ]
    )

    with pytest.raises(AppError) as exc_info:
        build_debug_taurus_document_from_content(
            scenario_content=payload(steps=[conflicting_step]),
            env_variables={"session_id": "env-session"},
            dependency_files=[],
            jmeter_path=runtime_jmeter_path("/opt/surgepilot/runner"),
            jmeter_version=RUNTIME_JMETER_VERSION,
        )

    assert exc_info.value.code == "VALIDATION_ERROR"
    assert {detail["code"] for detail in exc_info.value.details} == {"variable_conflict"}


def test_header_based_csv_allows_unresolved_global_header_reference() -> None:
    file_id = "01HZX3Y9M0E9W7Z6M5QK9S8P8G"

    document = build_debug_taurus_document_from_content(
        scenario_content=payload(
            globalHeaders=[
                {
                    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8H",
                    "name": "X-CSV-Header",
                    "value": "${csv_header_value}",
                    "enabled": True,
                }
            ],
            dataSources=[
                {
                    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8I",
                    "dependencyFileId": file_id,
                    "displayName": "users.csv",
                    "delimiter": ",",
                    "quoted": None,
                    "loop": True,
                    "variableNames": [],
                    "randomOrder": False,
                    "enabled": True,
                }
            ],
        ),
        env_variables={},
        dependency_files=[dependency_file(file_id)],
        jmeter_path=runtime_jmeter_path("/opt/surgepilot/runner"),
        jmeter_version=RUNTIME_JMETER_VERSION,
    )

    scenario_doc = document["scenarios"]["surgepilot_scenario"]
    assert scenario_doc["headers"] == {"X-CSV-Header": "${csv_header_value}"}
    assert scenario_doc["data-sources"][0]["path"].endswith("/users.csv")


def test_missing_variables_honor_scenario_variables_disabled_rows_and_header_csv() -> None:
    build_debug_taurus_document_from_content(
        scenario_content=payload(),
        env_variables={},
        dependency_files=[],
        jmeter_path=runtime_jmeter_path("/opt/surgepilot/runner"),
        jmeter_version=RUNTIME_JMETER_VERSION,
    )

    with pytest.raises(AppError) as exc_info:
        build_debug_taurus_document_from_content(
            scenario_content=payload(steps=[step(path="/v1/${disabled_value}")]),
            env_variables={},
            dependency_files=[],
            jmeter_path=runtime_jmeter_path("/opt/surgepilot/runner"),
            jmeter_version=RUNTIME_JMETER_VERSION,
        )
    assert exc_info.value.code == "VALIDATION_ERROR"
    assert {detail["code"] for detail in exc_info.value.details} == {"missing_variable"}


def test_create_detail_and_clone_materialize_global_configuration(db_session: Session) -> None:
    user = seed_user(db_session)

    scenario = create_scenario(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, payload=payload()
    )

    assert scenario.global_headers_json == payload()["globalHeaders"]
    assert scenario.variables_json == payload()["variables"]


@pytest.mark.anyio
async def test_scenario_api_persists_and_clones_global_configuration(
    client: AsyncClient,
) -> None:
    csrf, workspace_id = await register(client, "p1-09-scenario-api@example.com")
    created = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=payload(),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["globalHeaders"] == payload()["globalHeaders"]
    assert body["variables"] == payload()["variables"]

    listed = await client.get("/api/v1/scenarios", headers={"x-workspace-id": workspace_id})
    assert listed.status_code == 200
    summary = listed.json()["items"][0]
    assert "globalHeaders" not in summary
    assert "variables" not in summary

    clone = await client.post(
        f"/api/v1/scenarios/{body['id']}/clone",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={"name": "Copied scenario"},
    )
    assert clone.status_code == 201
    assert clone.json()["globalHeaders"] == body["globalHeaders"]
    assert clone.json()["variables"] == body["variables"]
