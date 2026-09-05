from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User, Workspace, WorkspaceMember
from app.services.env_groups import EnvGroupReferenceChecker, create_env_group


async def register_user(
    client: AsyncClient,
    email: str = "admin@example.com",
    password: str = "password123",
) -> tuple[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "displayName": "Admin User", "password": password},
    )
    assert response.status_code == 201
    return response.json()["csrfToken"], response.json()["defaultWorkspace"]["id"]


def seed_other_workspace(db_session: Session, user_id: str) -> str:
    now = datetime.now(UTC)
    workspace = Workspace(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7C",
        name="Other Workspace",
        status="active",
        created_at=now,
        updated_at=now,
    )
    db_session.add(workspace)
    db_session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user_id, joined_at=now))
    db_session.flush()
    return workspace.id


@pytest.mark.anyio
async def test_env_group_endpoints_require_session_and_csrf(client: AsyncClient) -> None:
    unauthenticated = await client.get("/api/v1/env-groups")
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["code"] == "UNAUTHENTICATED"

    csrf_token, _workspace_id = await register_user(client)
    created = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf_token},
        json={"name": "Staging"},
    )
    assert created.status_code == 201
    env_group_id = created.json()["id"]

    write_requests = [
        ("post", "/api/v1/env-groups", {"json": {"name": "Missing CSRF"}}),
        ("patch", f"/api/v1/env-groups/{env_group_id}", {"json": {"name": "Patch CSRF"}}),
        ("delete", f"/api/v1/env-groups/{env_group_id}", {}),
        ("post", f"/api/v1/env-groups/{env_group_id}/duplicate", {}),
    ]
    for method, path, kwargs in write_requests:
        missing_csrf = await getattr(client, method)(path, **kwargs)
        assert missing_csrf.status_code == 403
        assert missing_csrf.json()["code"] == "CSRF_TOKEN_REQUIRED"

        invalid_csrf = await getattr(client, method)(
            path, headers={"x-csrf-token": "bad-token"}, **kwargs
        )
        assert invalid_csrf.status_code == 403
        assert invalid_csrf.json()["code"] == "CSRF_TOKEN_INVALID"


@pytest.mark.anyio
async def test_create_list_get_patch_duplicate_and_delete_env_group(
    client: AsyncClient,
) -> None:
    csrf_token, workspace_id = await register_user(client)

    created = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": workspace_id},
        json={
            "name": "  Staging  ",
            "description": "  Staging variables  ",
            "variables": {
                "TOKEN": "fake-token",
                "BASE_URL": "https://example.test",
            },
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Staging"
    assert body["description"] == "Staging variables"
    assert body["variables"] == {
        "TOKEN": "fake-token",
        "BASE_URL": "https://example.test",
    }
    assert body["variableCount"] == 2
    assert body["inUse"] is False
    assert created.headers["x-workspace-id"] == workspace_id

    listed = await client.get("/api/v1/env-groups", headers={"x-workspace-id": workspace_id})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert "variables" not in listed.json()["items"][0]
    assert listed.json()["items"][0]["variableCount"] == 2

    detail = await client.get(f"/api/v1/env-groups/{body['id']}")
    assert detail.status_code == 200
    assert detail.json()["variables"]["BASE_URL"] == "https://example.test"

    patched = await client.patch(
        f"/api/v1/env-groups/{body['id']}",
        headers={"x-csrf-token": csrf_token, "content-type": "application/merge-patch+json"},
        json={
            "description": None,
            "variables": {"BASE_URL": "https://staging.example.test"},
        },
    )
    assert patched.status_code == 200
    assert patched.json()["description"] is None
    assert patched.json()["variables"] == {
        "BASE_URL": "https://staging.example.test"
    }

    preserved = await client.patch(
        f"/api/v1/env-groups/{body['id']}",
        headers={"x-csrf-token": csrf_token},
        json={"name": "Staging API"},
    )
    assert preserved.status_code == 200
    assert preserved.json()["variables"] == {
        "BASE_URL": "https://staging.example.test"
    }

    duplicate = await client.post(
        f"/api/v1/env-groups/{body['id']}/duplicate",
        headers={"x-csrf-token": csrf_token},
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["name"] == "Copy of Staging API"
    assert duplicate.json()["variables"] == {
        "BASE_URL": "https://staging.example.test"
    }

    deleted = await client.delete(
        f"/api/v1/env-groups/{duplicate.json()['id']}",
        headers={"x-csrf-token": csrf_token},
    )
    assert deleted.status_code == 204

    original = await client.get(f"/api/v1/env-groups/{body['id']}")
    assert original.status_code == 200


@pytest.mark.anyio
async def test_env_group_validation_conflict_query_and_patch_semantics(
    client: AsyncClient,
) -> None:
    csrf_token, workspace_id = await register_user(client)

    created = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf_token},
        json={
            "name": "Production",
            "variables": {"BASE_URL": "https://example.test"},
        },
    )
    assert created.status_code == 201

    duplicate_name = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": workspace_id},
        json={"name": "production"},
    )
    assert duplicate_name.status_code == 409
    assert duplicate_name.json()["code"] == "ENV_GROUP_NAME_CONFLICT"
    assert duplicate_name.headers["x-workspace-id"] == workspace_id

    invalid_variables = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": workspace_id},
        json={"name": "Invalid", "variables": {"bad-key": "value"}},
    )
    assert invalid_variables.status_code == 422
    assert invalid_variables.json()["details"][0]["field"] == "variables[bad-key]"
    assert invalid_variables.json()["details"][0]["message"] == "Variable key is invalid."
    assert invalid_variables.headers["x-workspace-id"] == workspace_id

    variables_null = await client.patch(
        f"/api/v1/env-groups/{created.json()['id']}",
        headers={"x-csrf-token": csrf_token},
        json={"variables": None},
    )
    assert variables_null.status_code == 422
    assert variables_null.json()["code"] == "VALIDATION_ERROR"

    cleared = await client.patch(
        f"/api/v1/env-groups/{created.json()['id']}",
        headers={"x-csrf-token": csrf_token},
        json={"variables": {}},
    )
    assert cleared.status_code == 200
    assert cleared.json()["variables"] == {}

    search = await client.get(
        "/api/v1/env-groups",
        headers={"x-workspace-id": workspace_id},
        params={"q": "pro", "sort": "name", "page": "1", "pageSize": "10"},
    )
    assert search.status_code == 200
    assert search.json()["items"][0]["name"] == "Production"

    for params in (
        {"page": "0"},
        {"page": "not-a-number"},
        {"pageSize": "101"},
        {"pageSize": "not-a-number"},
        {"q": "x" * 121},
    ):
        invalid_query_value = await client.get("/api/v1/env-groups", params=params)
        assert invalid_query_value.status_code == 400
        assert invalid_query_value.json()["code"] == "INVALID_QUERY_PARAMETER"

    invalid_sort = await client.get("/api/v1/env-groups", params={"sort": "-name"})
    assert invalid_sort.status_code == 400
    assert invalid_sort.json()["code"] == "INVALID_QUERY_PARAMETER"

    unknown_query = await client.get("/api/v1/env-groups", params={"unexpected": "1"})
    assert unknown_query.status_code == 400
    assert unknown_query.json()["code"] == "INVALID_QUERY_PARAMETER"


@pytest.mark.anyio
async def test_workspace_dependency_errors_include_resolved_contract_codes(
    client: AsyncClient, db_session: Session
) -> None:
    await register_user(client)
    user_client = AsyncClient(transport=client._transport, base_url="http://testserver")
    await register_user(user_client, email="plain@example.com")

    malformed = await user_client.get(
        "/api/v1/env-groups", headers={"x-workspace-id": "not-a-ulid"}
    )
    assert malformed.status_code == 400
    assert malformed.json()["code"] == "WORKSPACE_REQUIRED"

    now = datetime.now(UTC)
    inaccessible = Workspace(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7R",
        name="Inaccessible Workspace",
        status="active",
        created_at=now,
        updated_at=now,
    )
    db_session.add(inaccessible)
    db_session.flush()

    denied = await user_client.get(
        "/api/v1/env-groups", headers={"x-workspace-id": inaccessible.id}
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "WORKSPACE_ACCESS_DENIED"
    await user_client.aclose()


@pytest.mark.anyio
async def test_env_groups_are_workspace_isolated(client: AsyncClient, db_session: Session) -> None:
    csrf_token, workspace_id = await register_user(client)
    user = db_session.scalar(select(User).where(User.email == "admin@example.com"))
    assert user is not None
    other_workspace_id = seed_other_workspace(db_session, user.id)
    other_group = create_env_group(
        db_session,
        workspace_id=other_workspace_id,
        actor_user_id=user.id,
        name="Shared Name",
        description=None,
        variables={},
    )
    db_session.commit()

    same_name_default = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf_token, "x-workspace-id": workspace_id},
        json={"name": "shared name"},
    )
    assert same_name_default.status_code == 201

    hidden = await client.get(
        f"/api/v1/env-groups/{other_group.id}", headers={"x-workspace-id": workspace_id}
    )
    assert hidden.status_code == 404
    assert hidden.json()["code"] == "RESOURCE_NOT_FOUND"

    other_list = await client.get(
        "/api/v1/env-groups", headers={"x-workspace-id": other_workspace_id}
    )
    assert other_list.status_code == 200
    assert other_list.json()["items"][0]["name"] == "Shared Name"


@pytest.mark.anyio
async def test_delete_returns_in_use_when_reference_checker_reports_reference(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    csrf_token, _workspace_id = await register_user(client)
    created = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf_token},
        json={"name": "Referenced"},
    )
    assert created.status_code == 201

    monkeypatch.setattr(EnvGroupReferenceChecker, "is_in_use", lambda self, env_group_id: True)
    deleted = await client.delete(
        f"/api/v1/env-groups/{created.json()['id']}",
        headers={"x-csrf-token": csrf_token},
    )

    assert deleted.status_code == 409
    assert deleted.json()["code"] == "ENV_GROUP_IN_USE"
