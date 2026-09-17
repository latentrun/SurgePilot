from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ids import new_ulid
from app.models.auth import SessionRecord, SystemSetting, User, Workspace, WorkspaceMember


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


def add_workspace(db: Session, name: str, status: str = "active") -> Workspace:
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
async def test_session_context_uses_preferred_workspace_and_falls_back(
    client: AsyncClient, db_session: Session
) -> None:
    await register_admin(client)
    workspace_b = add_workspace(db_session, "Payments")
    workspace_c = add_workspace(db_session, "Archived", status="archived")
    db_session.commit()

    preferred = await client.get(f"/api/v1/auth/me?preferredWorkspaceId={workspace_b.id}")
    assert preferred.status_code == 200
    body = preferred.json()
    assert body["currentWorkspace"]["id"] == workspace_b.id
    assert body["defaultWorkspace"]["id"] == workspace_b.id
    assert {item["id"] for item in body["availableWorkspaces"]} >= {workspace_b.id}
    assert workspace_c.id not in {item["id"] for item in body["availableWorkspaces"]}
    assert body["permissions"]["canManageUsers"] is True

    fallback = await client.get(f"/api/v1/auth/me?preferredWorkspaceId={workspace_c.id}")
    assert fallback.status_code == 200
    assert fallback.json()["currentWorkspace"]["id"] != workspace_c.id

    overview = await client.get("/api/v1/overview", headers={"x-workspace-id": workspace_b.id})
    assert overview.status_code == 200
    assert overview.json()["workspace"]["id"] == workspace_b.id


@pytest.mark.anyio
async def test_workspace_switch_rejects_archived_workspace(
    client: AsyncClient, db_session: Session
) -> None:
    await register_admin(client)
    archived = add_workspace(db_session, "Old", status="archived")
    db_session.commit()

    response = await client.post(
        "/api/v1/workspaces/switch",
        headers={"x-csrf-token": await csrf(client)},
        json={"workspaceId": archived.id},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "WORKSPACE_ARCHIVED"


@pytest.mark.anyio
async def test_admin_workspace_create_rename_archive_and_last_active_guard(
    client: AsyncClient,
) -> None:
    await register_admin(client)
    token = await csrf(client)

    created = await client.post(
        "/api/v1/admin/workspaces",
        headers={"x-csrf-token": token},
        json={"name": " Payments Team "},
    )
    assert created.status_code == 201
    workspace_id = created.json()["workspace"]["id"]
    assert created.json()["workspace"]["name"] == "Payments Team"

    duplicate = await client.post(
        "/api/v1/admin/workspaces",
        headers={"x-csrf-token": token},
        json={"name": "payments team"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "WORKSPACE_NAME_CONFLICT"

    renamed = await client.patch(
        f"/api/v1/admin/workspaces/{workspace_id}",
        headers={"x-csrf-token": token},
        json={"name": "Core Platform"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["workspace"]["name"] == "Core Platform"

    archived = await client.post(
        f"/api/v1/admin/workspaces/{workspace_id}/archive",
        headers={"x-csrf-token": token},
    )
    assert archived.status_code == 200
    assert archived.json()["workspace"]["status"] == "archived"

    active = await client.get("/api/v1/admin/workspaces?status=active")
    only_active_id = active.json()["workspaces"][0]["id"]
    blocked = await client.post(
        f"/api/v1/admin/workspaces/{only_active_id}/archive",
        headers={"x-csrf-token": token},
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "WORKSPACE_LAST_ACTIVE_REQUIRED"


@pytest.mark.anyio
async def test_user_management_disable_revokes_sessions_and_protects_last_admin(
    client: AsyncClient, db_session: Session
) -> None:
    await register_admin(client)
    token = await csrf(client)
    default_workspace = db_session.scalar(select(Workspace).where(Workspace.status == "active"))
    assert default_workspace is not None

    created = await client.post(
        "/api/v1/admin/users",
        headers={"x-csrf-token": token},
        json={
            "email": "User@Example.com",
            "displayName": "User",
            "role": "user",
            "status": "active",
            "password": "password123",
            "workspaceIds": [default_workspace.id],
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
    assert disabled.json()["user"]["status"] == "disabled"
    assert db_session.scalar(
        select(SessionRecord).where(SessionRecord.user_id == user_id)
    ).revoked_at

    old_session = await user_client.get("/api/v1/auth/me")
    assert old_session.status_code == 401
    await user_client.aclose()

    disabled_wrong_password = await client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "wrong-password123"},
    )
    assert disabled_wrong_password.status_code == 401
    assert disabled_wrong_password.json()["code"] == "INVALID_CREDENTIALS"

    disabled_correct_password = await client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert disabled_correct_password.status_code == 403
    assert disabled_correct_password.json()["code"] == "USER_DISABLED"

    admin = db_session.scalar(select(User).where(User.email == "admin@example.com"))
    assert admin is not None
    last_admin = await client.patch(
        f"/api/v1/admin/users/{admin.id}",
        headers={"x-csrf-token": token},
        json={"role": "user"},
    )
    assert last_admin.status_code == 409
    assert last_admin.json()["code"] == "USER_LAST_ACTIVE_ADMIN"


@pytest.mark.anyio
async def test_admin_downgrade_requires_active_workspace_membership(
    client: AsyncClient, db_session: Session
) -> None:
    await register_admin(client)
    token = await csrf(client)
    admin = db_session.scalar(select(User).where(User.email == "admin@example.com"))
    assert admin is not None
    workspace_b = add_workspace(db_session, "Still Active")
    db_session.commit()

    second_admin = await client.post(
        "/api/v1/admin/users",
        headers={"x-csrf-token": token},
        json={
            "email": "second-admin@example.com",
            "displayName": "Second Admin",
            "role": "admin",
            "status": "active",
            "password": "password123",
            "workspaceIds": [],
        },
    )
    assert second_admin.status_code == 201

    default_workspace = db_session.scalar(
        select(Workspace).where(Workspace.name == "Default Workspace")
    )
    assert default_workspace is not None
    archived = await client.post(
        f"/api/v1/admin/workspaces/{default_workspace.id}/archive",
        headers={"x-csrf-token": token},
    )
    assert archived.status_code == 200
    assert archived.json()["workspace"]["status"] == "archived"

    downgraded = await client.patch(
        f"/api/v1/admin/users/{admin.id}",
        headers={"x-csrf-token": token},
        json={"role": "user"},
    )
    assert downgraded.status_code == 409
    assert downgraded.json()["code"] == "USER_WORKSPACE_REQUIRED"
    assert workspace_b.status == "active"


@pytest.mark.anyio
async def test_non_admin_cannot_manage_workspaces_and_archived_header_is_rejected(
    client: AsyncClient, db_session: Session
) -> None:
    await register_admin(client)
    token = await csrf(client)
    default_workspace = db_session.scalar(select(Workspace).where(Workspace.status == "active"))
    assert default_workspace is not None
    created = await client.post(
        "/api/v1/admin/users",
        headers={"x-csrf-token": token},
        json={
            "email": "user2@example.com",
            "displayName": "User Two",
            "role": "user",
            "status": "active",
            "password": "password123",
            "workspaceIds": [default_workspace.id],
        },
    )
    assert created.status_code == 201

    user_client = AsyncClient(transport=client._transport, base_url="http://testserver")
    login = await user_client.post(
        "/api/v1/auth/login",
        json={"email": "user2@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    user_csrf = (await user_client.get("/api/v1/auth/csrf")).json()["csrfToken"]
    denied = await user_client.post(
        "/api/v1/admin/workspaces",
        headers={"x-csrf-token": user_csrf},
        json={"name": "Denied"},
    )
    assert denied.status_code == 403

    archived = add_workspace(db_session, "Archived For Header", status="archived")
    db_session.add(
        WorkspaceMember(
            workspace_id=archived.id,
            user_id=created.json()["user"]["id"],
            joined_at=datetime.now(UTC),
        )
    )
    db_session.commit()
    header_response = await user_client.get(
        "/api/v1/overview",
        headers={"x-workspace-id": archived.id},
    )
    assert header_response.status_code == 403
    assert header_response.json()["code"] == "WORKSPACE_ARCHIVED"
    await user_client.aclose()


@pytest.mark.anyio
async def test_user_membership_replace_and_password_reset_revoke_session(
    client: AsyncClient, db_session: Session
) -> None:
    await register_admin(client)
    token = await csrf(client)
    default_workspace = db_session.scalar(select(Workspace).where(Workspace.status == "active"))
    assert default_workspace is not None
    workspace_b = add_workspace(db_session, "Workspace B")
    db_session.commit()

    created = await client.post(
        "/api/v1/admin/users",
        headers={"x-csrf-token": token},
        json={
            "email": "member@example.com",
            "displayName": "Member",
            "role": "user",
            "status": "active",
            "password": "password123",
            "workspaceIds": [default_workspace.id],
        },
    )
    assert created.status_code == 201
    user_id = created.json()["user"]["id"]

    replaced = await client.put(
        f"/api/v1/admin/users/{user_id}/workspaces",
        headers={"x-csrf-token": token},
        json={"workspaceIds": [workspace_b.id]},
    )
    assert replaced.status_code == 200
    assert replaced.json()["user"]["workspaceIds"] == [workspace_b.id]

    blocked = await client.put(
        f"/api/v1/admin/users/{user_id}/workspaces",
        headers={"x-csrf-token": token},
        json={"workspaceIds": []},
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "USER_WORKSPACE_REQUIRED"

    user_client = AsyncClient(transport=client._transport, base_url="http://testserver")
    login = await user_client.post(
        "/api/v1/auth/login",
        json={"email": "member@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    reset = await client.post(
        f"/api/v1/admin/users/{user_id}/reset-password",
        headers={"x-csrf-token": token},
        json={"newPassword": "password456"},
    )
    assert reset.status_code == 200
    assert "password456" not in reset.text
    old_session = await user_client.get("/api/v1/auth/me")
    assert old_session.status_code == 401
    await user_client.aclose()

    relogin = await client.post(
        "/api/v1/auth/login",
        json={"email": "member@example.com", "password": "password456"},
    )
    assert relogin.status_code == 200


@pytest.mark.anyio
async def test_system_settings_are_whitelisted_and_public_setup_is_minimal(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALLOW_SIGNUP", "true")
    await register_admin(client)
    token = await csrf(client)

    payload = {
        "allowSignup": False,
        "loadSoftLimitWarningConcurrency": 1500,
        "jmeterMemoryXmx": "6G",
        "maxScenarioItemsPerTestPlan": 25,
        "maxSlaRulesPerTestPlan": 8,
        "maxRunDurationSeconds": 90000,
        "maxRampUpSeconds": 1200,
        "maxDelaySeconds": 300,
        "maxIterations": 2000000,
        "maxTargetRps": 250000,
        "dependencyFileMaxBytes": 209715200,
        "dependencyFileAllowedExtensions": ["csv", ".TXT", " .json "],
        "dependencyFilePreviewMaxBytes": 131072,
        "dependencyFilePreviewBinaryDenyExtensions": [".png", "JPG", " .zip "],
    }
    response = await client.patch(
        "/api/v1/admin/system-settings",
        headers={"x-csrf-token": token},
        json=payload,
    )
    assert response.status_code == 200
    settings = response.json()["settings"]
    assert settings == {
        "allowSignup": False,
        "loadSoftLimitWarningConcurrency": 1500,
        "jmeterMemoryXmx": "6G",
        "maxScenarioItemsPerTestPlan": 25,
        "maxSlaRulesPerTestPlan": 8,
        "maxRunDurationSeconds": 90000,
        "maxRampUpSeconds": 1200,
        "maxDelaySeconds": 300,
        "maxIterations": 2000000,
        "maxTargetRps": 250000,
        "dependencyFileMaxBytes": 209715200,
        "dependencyFileAllowedExtensions": [".csv", ".txt", ".json"],
        "dependencyFilePreviewMaxBytes": 131072,
        "dependencyFilePreviewBinaryDenyExtensions": [".png", ".jpg", ".zip"],
        "loadNodeApiBaseUrl": None,
    }
    assert "secret-value" not in response.text
    assert db_session.get(SystemSetting, "allowSignup") is not None
    assert db_session.get(SystemSetting, "dependencyFileAllowedExtensions").value_json == [
        ".csv",
        ".txt",
        ".json",
    ]

    current = await client.get("/api/v1/admin/system-settings")
    assert current.status_code == 200
    assert current.json()["settings"] == settings
    assert set(current.json()["sensitiveStatus"]) == {
        "runnerInternalTokenConfigured",
        "sshCredentialEncryptionKeyConfigured",
        "minioCredentialsConfigured",
    }
    assert "singleNodeConcurrencyHardLimit" not in current.text
    assert "monitoring" not in current.text.lower()
    assert "grafana" not in current.text.lower()
    assert "influx" not in current.text.lower()

    max_preview = await client.patch(
        "/api/v1/admin/system-settings",
        headers={"x-csrf-token": token},
        json={"dependencyFilePreviewMaxBytes": 5242880},
    )
    assert max_preview.status_code == 200
    upload_below_persisted_preview = await client.patch(
        "/api/v1/admin/system-settings",
        headers={"x-csrf-token": token},
        json={"dependencyFileMaxBytes": 1048576},
    )
    assert upload_below_persisted_preview.status_code == 422
    assert upload_below_persisted_preview.json()["code"] == "VALIDATION_ERROR"

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
    assert public_status.json()["allowSignup"] is False
    assert "activeAdminCount" not in public_status.text
    assert "runnerInternalTokenConfigured" not in public_status.text

    admin_status = await client.get("/api/v1/admin/setup-status")
    assert admin_status.status_code == 200
    assert admin_status.json()["activeAdminCount"] == 1
    assert isinstance(admin_status.json()["sensitiveStatus"]["runnerInternalTokenConfigured"], bool)


@pytest.mark.anyio
async def test_system_settings_validate_policy_values(client: AsyncClient) -> None:
    await register_admin(client)
    token = await csrf(client)

    cases = [
        ({"jmeterMemoryXmx": "256M"}, "VALIDATION_ERROR"),
        ({"jmeterMemoryXmx": "33G"}, "VALIDATION_ERROR"),
        ({"jmeterMemoryXmx": "4g"}, "VALIDATION_ERROR"),
        ({"loadSoftLimitWarningConcurrency": 10001}, "VALIDATION_ERROR"),
        ({"dependencyFileAllowedExtensions": [".csv", "bad extension"]}, "VALIDATION_ERROR"),
        (
            {"dependencyFileAllowedExtensions": [f".{index}" for index in range(101)]},
            "VALIDATION_ERROR",
        ),
        (
            {"dependencyFileMaxBytes": 1048576, "dependencyFilePreviewMaxBytes": 1048577},
            "VALIDATION_ERROR",
        ),
        ({"dependencyFilePreviewBinaryDenyExtensions": [".png", "../secret"]}, "VALIDATION_ERROR"),
        ({"singleNodeConcurrencyHardLimit": 999}, "SETTING_NOT_EDITABLE"),
        ({"unknownPolicy": 1}, "SETTING_NOT_EDITABLE"),
    ]
    for payload, expected_code in cases:
        response = await client.patch(
            "/api/v1/admin/system-settings",
            headers={"x-csrf-token": token},
            json=payload,
        )
        assert response.status_code in {400, 422}
        assert response.json()["code"] == expected_code

    sensitive = await client.patch(
        "/api/v1/admin/system-settings",
        headers={"x-csrf-token": token},
        json={"grafanaAdminPassword": "secret-value"},
    )
    assert sensitive.status_code == 400
    assert sensitive.json()["code"] == "SENSITIVE_SETTING_VALUE_FORBIDDEN"
    assert "secret-value" not in sensitive.text
