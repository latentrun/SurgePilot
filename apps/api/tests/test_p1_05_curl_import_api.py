import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ids import new_ulid
from app.models.scenarios import Scenario


async def register(client: AsyncClient, email: str) -> tuple[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "displayName": "cURL User", "password": "password123"},
    )
    assert response.status_code == 201
    body = response.json()
    return body["csrfToken"], body["defaultWorkspace"]["id"]


def scenario_payload() -> dict:
    return {
        "name": "Existing Scenario",
        "description": None,
        "tags": [],
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
        "dataSources": [],
        "steps": [],
    }


def materialized_step(step: dict) -> dict:
    body = step["body"]
    return {
        "id": new_ulid(),
        **step,
        "queryParams": [{**item, "id": new_ulid()} for item in step.get("queryParams", [])],
        "headers": [{**item, "id": new_ulid()} for item in step.get("headers", [])],
        "body": {
            **body,
            "formFields": [{**item, "id": new_ulid()} for item in body.get("formFields", [])],
        },
        "uploadFiles": [],
        "extractors": [],
        "assertions": [
            {
                "id": new_ulid(),
                "type": "status_code",
                "expectedStatus": 200,
                "contains": None,
                "jsonpath": None,
                "expectedValue": None,
                "regexp": False,
                "not": False,
                "enabled": True,
            }
        ],
        "scripts": [],
    }


@pytest.mark.anyio
async def test_curl_import_parse_requires_auth_workspace_and_csrf(client: AsyncClient) -> None:
    unauthenticated = await client.post(
        "/api/v1/scenarios/curl-import/parse",
        json={"rawCurl": "curl https://example.test"},
    )
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["code"] == "UNAUTHENTICATED"

    csrf, workspace_id = await register(client, "curl-auth@example.com")
    missing_csrf = await client.post(
        "/api/v1/scenarios/curl-import/parse",
        headers={"x-workspace-id": workspace_id},
        json={"rawCurl": "curl https://example.test"},
    )
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["code"] == "CSRF_TOKEN_REQUIRED"

    invalid_workspace = await client.post(
        "/api/v1/scenarios/curl-import/parse",
        headers={"x-workspace-id": "not-a-ulid", "x-csrf-token": csrf},
        json={"rawCurl": "curl https://example.test"},
    )
    assert invalid_workspace.status_code == 400
    assert invalid_workspace.json()["code"] == "WORKSPACE_REQUIRED"


@pytest.mark.anyio
async def test_curl_import_parse_returns_preview_and_persists_nothing(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id = await register(client, "curl-preview@example.com")
    created = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(),
    )
    assert created.status_code == 201
    scenario = created.json()

    response = await client.post(
        "/api/v1/scenarios/curl-import/parse",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={"rawCurl": "curl -H 'Authorization: Bearer token' https://example.test/v1/orders"},
    )

    assert response.status_code == 200
    assert response.headers["x-workspace-id"] == workspace_id
    body = response.json()
    assert body["baseUrlSuggestion"] == "https://example.test"
    assert "id" not in body["step"]
    assert body["step"]["path"] == "/v1/orders"
    assert {warning["code"] for warning in body["warnings"]} >= {
        "BASE_URL_SUGGESTED",
        "SENSITIVE_HEADER_PRESENT",
    }

    db_session.expire_all()
    persisted = db_session.scalar(select(Scenario).where(Scenario.id == scenario["id"]))
    assert persisted is not None
    assert persisted.revision == 1
    assert db_session.query(Scenario).count() == 1


@pytest.mark.anyio
async def test_curl_import_long_cookie_preview_can_be_saved_through_scenario_patch(
    client: AsyncClient,
) -> None:
    csrf, workspace_id = await register(client, "curl-long-cookie@example.com")
    created = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(),
    )
    assert created.status_code == 201
    scenario = created.json()
    cookie = "session=" + ("x" * 5_200)

    parsed = await client.post(
        "/api/v1/scenarios/curl-import/parse",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={"rawCurl": f"curl -H 'Cookie: {cookie}' https://example.test/secure"},
    )
    assert parsed.status_code == 200
    parsed_body = parsed.json()
    assert parsed_body["step"]["headers"] == [{"name": "Cookie", "value": cookie, "enabled": True}]
    assert {warning["code"] for warning in parsed_body["warnings"]} >= {
        "BASE_URL_SUGGESTED",
        "SENSITIVE_HEADER_PRESENT",
    }

    payload = {
        **scenario_payload(),
        "expectedRevision": scenario["revision"],
        "baseUrlExpression": parsed_body["baseUrlSuggestion"],
        "steps": [materialized_step(parsed_body["step"])],
    }
    patched = await client.patch(
        f"/api/v1/scenarios/{scenario['id']}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=payload,
    )

    assert patched.status_code == 200
    assert patched.json()["steps"][0]["headers"][0]["value"] == cookie


@pytest.mark.anyio
async def test_curl_import_parse_safe_validation_error_does_not_echo_raw_curl(
    client: AsyncClient,
) -> None:
    csrf, workspace_id = await register(client, "curl-errors@example.com")
    response = await client.post(
        "/api/v1/scenarios/curl-import/parse",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={"rawCurl": "curl ftp://secret-token@example.test/file"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert "secret-token" not in str(body)
    assert "ftp://" not in str(body)


@pytest.mark.anyio
async def test_curl_import_parse_over_limit_cookie_returns_422_without_echoing_value(
    client: AsyncClient,
) -> None:
    csrf, workspace_id = await register(client, "curl-cookie-limit@example.com")
    cookie = "session=" + ("x" * 65_537)

    response = await client.post(
        "/api/v1/scenarios/curl-import/parse",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={"rawCurl": f"curl -H 'Cookie: {cookie}' https://example.test/secure"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert "x" * 100 not in str(body)
