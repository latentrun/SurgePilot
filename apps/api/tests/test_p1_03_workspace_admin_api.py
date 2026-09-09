from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ids import new_ulid
from app.models.auth import SessionRecord, SystemSetting, User, Workspace


async def register_admin(client: AsyncClient) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "admin@example.com", "displayName": "Admin", "password": "password123"},
    )
    assert response.status_code == 201
    return response.json()


async def csrf(client: AsyncClient) -> str:
    response = await client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return response.json()["csrfToken"]


def add_workspace(db: Session, name: str, *, status: str = "active") -> Workspace:
    now = datetime.now(UTC)
    workspace = Workspace(
        id=new_ulid(),
        name=name,
        status=status,
        archived_at=now if status == "archived" else None,
        created_at=now,
        updated_at=now,
    )
    db.add(workspace)
    db.flush()
    return workspace


@pytest.mark.anyio
async def test_session_context_preference_fallback_and_workspace_lifecycle(
    client: AsyncClient, db_session: Session
) -> None:
    await register_admin(client)
    workspace_b = add_workspace(db_session, "Payments")
    archived = add_workspace(db_session, "Archived", status="archived")
    db_session.commit()

    preferred = await client.get(f"/api/v1/auth/me?preferredWorkspaceId={workspace_b.id}")
    assert preferred.status_code == 200
    assert preferred.json()["currentWorkspace"]["id"] == workspace_b.id
    assert archived.id not in {row["id"] for row in preferred.json()["availableWorkspaces"]}
    assert preferred.json()["permissions"]["canManageUsers"] is True

    fallback = await client.get(f"/api/v1/auth/me?preferredWorkspaceId={archived.id}")
    assert fallback.status_code == 200
    assert fallback.json()["currentWorkspace"]["id"] != archived.id

    token = await csrf(client)
    created = await client.post(
        "/api/v1/admin/workspaces",
        headers={"x-csrf-token": token},
        json={"name": "  Core Platform  "},
    )
    assert created.status_code == 201
    created_id = created.json()["workspace"]["id"]
    assert created.json()["workspace"]["name"] == "Core Platform"

    duplicate = await client.post(
        "/api/v1/admin/workspaces",
        headers={"x-csrf-token": token},
        json={"name": "core platform"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "WORKSPACE_NAME_CONFLICT"

    archived_response = await client.post(
        f"/api/v1/admin/workspaces/{created_id}/archive",
        headers={"x-csrf-token": token},
    )
    assert archived_response.status_code == 200
    assert archived_response.json()["workspace"]["status"] == "archived"


@pytest.mark.anyio
async def test_workspace_and_user_guards_cover_archived_access_disabled_sessions_and_last_admin(
    client: AsyncClient, db_session: Session
) -> None:
    await register_admin(client)
    token = await csrf(client)
    default = db_session.scalar(select(Workspace).where(Workspace.status == "active"))
    assert default is not None

    created = await client.post(
        "/api/v1/admin/users",
        headers={"x-csrf-token": token},
        json={
            "email": "user@example.com",
            "displayName": "User",
            "role": "user",
            "status": "active",
            "password": "password123",
            "workspaceIds": [default.id],
        },
    )
    assert created.status_code == 201
    user_id = created.json()["user"]["id"]
    assert "password123" not in created.text

    user_client = AsyncClient(transport=client._transport, base_url="http://testserver")
    login = await user_client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert login.status_code == 200

    disabled = await client.patch(
        f"/api/v1/admin/users/{user_id}",
        headers={"x-csrf-token": token},
        json={"status": "disabled"},
    )
    assert disabled.status_code == 200
    assert db_session.scalar(select(SessionRecord).where(SessionRecord.user_id == user_id)).revoked_at
    assert (await user_client.get("/api/v1/auth/me")).status_code == 401
    await user_client.aclose()

    admin = db_session.scalar(select(User).where(User.email == "admin@example.com"))
    assert admin is not None
    last_admin = await client.patch(
        f"/api/v1/admin/users/{admin.id}",
        headers={"x-csrf-token": token},
        json={"status": "disabled"},
    )
    assert last_admin.status_code == 409
    assert last_admin.json()["code"] == "USER_LAST_ACTIVE_ADMIN"


@pytest.mark.anyio
async def test_system_settings_are_whitelisted_and_never_echo_sensitive_values(
    client: AsyncClient, db_session: Session
) -> None:
    await register_admin(client)
    token = await csrf(client)

    response = await client.patch(
        "/api/v1/admin/system-settings",
        headers={"x-csrf-token": token},
        json={
            "allowSignup": False,
            "jmeterMemoryXmx": "6G",
            "dependencyFileAllowedExtensions": ["csv", ".TXT"],
        },
    )
    assert response.status_code == 200
    assert response.json()["settings"]["allowSignup"] is False
    assert response.json()["settings"]["dependencyFileAllowedExtensions"] == [".csv", ".txt"]
    assert db_session.get(SystemSetting, "allowSignup") is not None
    assert "singleNodeConcurrencyHardLimit" not in response.text

    sensitive = await client.patch(
        "/api/v1/admin/system-settings",
        headers={"x-csrf-token": token},
        json={"runnerInternalToken": "secret-value"},
    )
    assert sensitive.status_code == 400
    assert sensitive.json()["code"] == "SENSITIVE_SETTING_VALUE_FORBIDDEN"
    assert "secret-value" not in sensitive.text

    public_status = await client.get("/api/v1/setup/status")
    assert public_status.status_code == 200
    assert "runnerInternalTokenConfigured" not in public_status.text
    admin_status = await client.get("/api/v1/admin/setup-status")
    assert admin_status.status_code == 200
    assert isinstance(admin_status.json()["sensitiveStatus"]["runnerInternalTokenConfigured"], bool)
