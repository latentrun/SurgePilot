from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.auth import User, Workspace, WorkspaceMember
from app.services.api_tokens import create_api_token


def future_expiry() -> str:
    return (datetime.now(UTC) + timedelta(days=30)).isoformat().replace("+00:00", "Z")


async def register(
    client: AsyncClient,
    email: str = "token-user@example.com",
    display_name: str = "Token User",
) -> tuple[str, str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "displayName": display_name, "password": "password123"},
    )
    assert response.status_code == 201
    body = response.json()
    return body["csrfToken"], body["defaultWorkspace"]["id"], body["user"]["id"]


def token_payload(workspace_id: str, *, scopes: list[str] | None = None) -> dict:
    return {
        "name": "CI automation",
        "scopes": scopes or ["read", "config:write", "run"],
        "workspaceAllowlist": [workspace_id],
        "expiresAt": future_expiry(),
    }


@pytest.mark.anyio
async def test_account_api_tokens_are_self_service_csrf_protected_and_plaintext_once(
    client: AsyncClient,
) -> None:
    csrf, workspace_id, _user_id = await register(client)

    empty = await client.get("/api/v1/account/api-tokens")
    assert empty.status_code == 200
    assert empty.json()["items"] == []

    missing_csrf = await client.post("/api/v1/account/api-tokens", json=token_payload(workspace_id))
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["code"] == "CSRF_TOKEN_REQUIRED"

    created = await client.post(
        "/api/v1/account/api-tokens",
        headers={"x-csrf-token": csrf},
        json=token_payload(workspace_id),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["token"]["plaintext"].startswith(f"surgepilot_pat_{body['token']['publicId']}_")
    assert body["token"]["name"] == "CI automation"
    assert body["token"]["scopes"] == ["read", "config:write", "run"]
    assert body["token"]["workspaceAllowlist"] == [workspace_id]
    assert "secretHash" not in created.text

    listed = await client.get("/api/v1/account/api-tokens")
    assert listed.status_code == 200
    listed_token = listed.json()["items"][0]
    assert listed_token["id"] == body["token"]["id"]
    assert listed_token["publicId"] == body["token"]["publicId"]
    assert "plaintext" not in listed.text
    assert "secretHash" not in listed.text

    deleted = await client.delete(
        f"/api/v1/account/api-tokens/{body['token']['id']}",
        headers={"x-csrf-token": csrf},
    )
    assert deleted.status_code == 204

    after_delete = await client.get("/api/v1/account/api-tokens")
    assert after_delete.status_code == 200
    assert after_delete.json()["items"][0]["revokedAt"] is not None


@pytest.mark.anyio
async def test_account_api_tokens_are_owner_only_and_phase_a_scoped(
    client: AsyncClient,
) -> None:
    csrf, workspace_id, _owner_id = await register(client, "owner@example.com", "Owner")
    all_scopes = await client.post(
        "/api/v1/account/api-tokens",
        headers={"x-csrf-token": csrf},
        json=token_payload(
            workspace_id,
            scopes=["read", "config:write", "run", "dependency:write"],
        ),
    )
    assert all_scopes.status_code == 201
    assert all_scopes.json()["token"]["scopes"] == [
        "read",
        "config:write",
        "run",
        "dependency:write",
    ]

    created = await client.post(
        "/api/v1/account/api-tokens",
        headers={"x-csrf-token": csrf},
        json=token_payload(workspace_id, scopes=["read"]),
    )
    assert created.status_code == 201
    token_id = created.json()["token"]["id"]

    invalid_scope = await client.post(
        "/api/v1/account/api-tokens",
        headers={"x-csrf-token": csrf},
        json=token_payload(workspace_id, scopes=["tokens:write"]),
    )
    assert invalid_scope.status_code == 422
    assert invalid_scope.json()["code"] == "VALIDATION_ERROR"

    other_client = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        other_csrf, _other_workspace_id, _other_id = await register(
            other_client, "other@example.com", "Other User"
        )
        stolen_delete = await other_client.delete(
            f"/api/v1/account/api-tokens/{token_id}",
            headers={"x-csrf-token": other_csrf},
        )
        assert stolen_delete.status_code == 404
        assert stolen_delete.json()["code"] == "RESOURCE_NOT_FOUND"
    finally:
        await other_client.aclose()


@pytest.mark.anyio
async def test_account_api_tokens_require_active_allowlisted_workspace_membership(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, _workspace_id, user_id = await register(
        client, "archived-token@example.com", "Archived Token"
    )
    archived_workspace = Workspace(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7R",
        name="Archived Token Workspace",
        status="archived",
        archived_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(archived_workspace)
    db_session.add(
        WorkspaceMember(
            workspace_id=archived_workspace.id,
            user_id=user_id,
            joined_at=datetime.now(UTC),
        )
    )
    db_session.flush()

    response = await client.post(
        "/api/v1/account/api-tokens",
        headers={"x-csrf-token": csrf},
        json=token_payload(archived_workspace.id, scopes=["read"]),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "WORKSPACE_ACCESS_DENIED"


@pytest.mark.anyio
async def test_api_token_service_rejects_empty_workspace_allowlist(
    client: AsyncClient, db_session: Session
) -> None:
    _csrf, _workspace_id, user_id = await register(
        client, "empty-allowlist-token@example.com", "Empty Allowlist"
    )
    user = db_session.get(User, user_id)
    assert user is not None

    with pytest.raises(AppError) as exc_info:
        create_api_token(
            db_session,
            actor=user,
            name="Empty allowlist",
            scopes=["read"],
            workspace_allowlist=[],
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
    assert exc_info.value.code == "VALIDATION_ERROR"
    assert exc_info.value.details[0]["field"] == "workspaceAllowlist"
