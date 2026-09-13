from datetime import UTC, datetime, timedelta
from pathlib import Path
import json

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.env_groups import EnvGroup
from app.models.runs import RunSnapshot
from app.schemas.load_nodes import LoadNodeCredentialInput
from app.services import execution_bundles
from app.services.load_nodes import create_load_node


async def register(client: AsyncClient, email: str) -> tuple[str, str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "displayName": "Secret User", "password": "password123"},
    )
    assert response.status_code == 201
    body = response.json()
    return body["csrfToken"], body["defaultWorkspace"]["id"], body["user"]["id"]


def future_expiry() -> str:
    return (datetime.now(UTC) + timedelta(days=30)).isoformat().replace("+00:00", "Z")


async def create_pat(
    client: AsyncClient, csrf: str, workspace_id: str, *, scopes: list[str]
) -> str:
    response = await client.post(
        "/api/v1/account/api-tokens",
        headers={"x-csrf-token": csrf},
        json={
            "name": "Secret automation",
            "scopes": scopes,
            "workspaceAllowlist": [workspace_id],
            "expiresAt": future_expiry(),
        },
    )
    assert response.status_code == 201
    return response.json()["token"]["plaintext"]


def auth_header(plaintext: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {plaintext}"}


def trusted_host_key() -> dict[str, str]:
    return {
        "algorithm": "ssh-ed25519",
        "publicKey": "AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC",
        "fingerprintSha256": "SHA256:SurgePilotTrustedHostKey",
    }


def credential() -> LoadNodeCredentialInput:
    return LoadNodeCredentialInput(authType="password", password="secret-password")


def seed_idle_node(db_session: Session, *, workspace_id: str, user_id: str):
    from app.models.auth import User

    user = db_session.get(User, user_id)
    assert user is not None
    node = create_load_node(
        db_session,
        actor=user,
        workspace_id=workspace_id,
        scope="workspace",
        host=f"p2-secret-node-{user_id.lower()}.internal",
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        credential=credential(),
        ssh_host_key=trusted_host_key(),
        maintainer=None,
        remark=None,
    )
    node.status = "idle"
    node.runtime_version = "runtime-test-v1"
    db_session.flush()
    return node


def scenario_payload() -> dict:
    return {
        "name": "Secret scenario",
        "description": None,
        "tags": [],
        "baseUrlExpression": "${BASE_URL}",
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
        "steps": [
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7D",
                "enabled": True,
                "name": "Call secret API",
                "method": "GET",
                "path": "/v1/secret",
                "queryParams": [],
                "headers": [
                    {
                        "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7F",
                        "name": "Authorization",
                        "value": "Bearer ${API_TOKEN}",
                        "enabled": True,
                    }
                ],
                "body": {"type": "none", "contentType": None, "rawText": None, "formFields": []},
                "uploadFiles": [],
                "extractors": [],
                "assertions": [
                    {
                        "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7K",
                        "type": "status_code",
                        "expectedStatus": 200,
                        "enabled": True,
                    }
                ],
                "scripts": [],
                "settings": {
                    "thinkTimeMs": None,
                    "timeoutMs": None,
                    "followRedirects": None,
                    "keepAlive": None,
                },
            }
        ],
    }


def test_env_group_secret_migration_preserves_existing_typed_entries() -> None:
    migration = (
        Path(__file__).resolve().parents[3]
        / "apps/api/migrations/versions/0017_p2_03_env_group_secret.py"
    ).read_text()

    assert "jsonb_each_text" not in migration
    assert "FROM jsonb_each(env_groups.variables)" in migration
    assert "WHEN jsonb_typeof(value) = 'string'" in migration
    assert "ELSE value" in migration


def test_execution_bundle_env_materialization_accepts_typed_secret_snapshot() -> None:
    assert execution_bundles._env_variables(
        {
            "envGroup": {
                "variables": {
                    "BASE_URL": {"type": "plain", "value": "https://api.example.test"},
                    "API_TOKEN": {"type": "secret", "value": "runtime-token"},
                }
            }
        }
    ) == {
        "BASE_URL": "https://api.example.test",
        "API_TOKEN": "runtime-token",
    }


@pytest.mark.anyio
async def test_env_group_create_get_patch_and_duplicate_secret_masks_responses(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, _user_id = await register(client, "p2-secret-session@example.com")
    created = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "name": "Secret staging",
            "description": None,
            "variables": {
                "BASE_URL": {"type": "plain", "value": "https://api.example.test"},
                "API_TOKEN": {"type": "secret", "value": "initial-token"},
            },
        },
    )

    assert created.status_code == 201
    body = created.json()
    assert body["variables"]["BASE_URL"] == {
        "type": "plain",
        "value": "https://api.example.test",
    }
    assert body["variables"]["API_TOKEN"] == {
        "type": "secret",
        "hasValue": True,
        "displayValue": "********",
    }
    assert "initial-token" not in json.dumps(body)
    group_id = body["id"]
    stored = db_session.get(EnvGroup, group_id)
    assert stored is not None
    assert stored.variables["API_TOKEN"] == {"type": "secret", "value": "initial-token"}

    detail = await client.get(
        f"/api/v1/env-groups/{group_id}", headers={"x-workspace-id": workspace_id}
    )
    assert detail.status_code == 200
    assert detail.json()["variables"]["API_TOKEN"]["displayValue"] == "********"
    assert "initial-token" not in detail.text

    preserved = await client.patch(
        f"/api/v1/env-groups/{group_id}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={"variables": {"API_TOKEN": {"type": "secret"}}},
    )
    assert preserved.status_code == 200
    assert db_session.get(EnvGroup, group_id).variables["API_TOKEN"]["value"] == "initial-token"

    replaced = await client.patch(
        f"/api/v1/env-groups/{group_id}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={"variables": {"API_TOKEN": {"type": "secret", "value": "replacement-token"}}},
    )
    assert replaced.status_code == 200
    assert "replacement-token" not in replaced.text
    assert db_session.get(EnvGroup, group_id).variables["API_TOKEN"]["value"] == "replacement-token"

    duplicated = await client.post(
        f"/api/v1/env-groups/{group_id}/duplicate",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
    )
    assert duplicated.status_code == 201
    assert "replacement-token" not in duplicated.text
    duplicate_row = db_session.get(EnvGroup, duplicated.json()["id"])
    assert duplicate_row is not None
    assert duplicate_row.variables["API_TOKEN"]["value"] == "replacement-token"


@pytest.mark.anyio
async def test_env_group_rejects_old_string_map_and_does_not_echo_secret_values(
    client: AsyncClient,
) -> None:
    csrf, workspace_id, _user_id = await register(client, "p2-secret-validation@example.com")

    old_map = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={"name": "Old map", "variables": {"TOKEN": "legacy-token"}},
    )
    assert old_map.status_code == 422
    assert old_map.json()["code"] == "VALIDATION_ERROR"
    assert "legacy-token" not in old_map.text

    invalid_secret = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "name": "Invalid secret",
            "variables": {
                "TOKEN": {
                    "type": "secret",
                    "value": "secret-from-user",
                    "displayValue": "********",
                }
            },
        },
    )
    assert invalid_secret.status_code == 422
    assert "secret-from-user" not in invalid_secret.text
    assert "displayValue" in invalid_secret.text
    assert invalid_secret.json()["details"][0]["field"] == "variables.TOKEN.secret.displayValue"


@pytest.mark.anyio
async def test_public_env_group_secret_write_patch_and_copy_are_rejected(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, _user_id = await register(client, "p2-secret-public@example.com")
    public_token = await create_pat(client, csrf, workspace_id, scopes=["config:write"])

    public_secret_create = await client.post(
        "/api/public/v1/env-groups",
        headers=auth_header(public_token),
        json={"name": "No public secret", "variables": {"TOKEN": {"type": "secret", "value": "x"}}},
    )
    assert public_secret_create.status_code == 422
    assert public_secret_create.json()["code"] == "VALIDATION_ERROR"

    plain_create = await client.post(
        "/api/public/v1/env-groups",
        headers=auth_header(public_token),
        json={
            "name": "Public plain",
            "variables": {"BASE_URL": {"type": "plain", "value": "https://example.test"}},
        },
    )
    assert plain_create.status_code == 201
    assert plain_create.json()["variables"] == {
        "BASE_URL": {"type": "plain", "value": "https://example.test"}
    }

    public_secret_patch = await client.patch(
        f"/api/public/v1/env-groups/{plain_create.json()['id']}",
        headers=auth_header(public_token),
        json={"variables": {"TOKEN": {"type": "secret", "value": "x"}}},
    )
    assert public_secret_patch.status_code == 422
    assert public_secret_patch.json()["code"] == "VALIDATION_ERROR"

    session_secret = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "name": "Session secret",
            "variables": {"TOKEN": {"type": "secret", "value": "runtime-token"}},
        },
    )
    assert session_secret.status_code == 201
    before_count = db_session.scalar(
        select(func.count(EnvGroup.id)).where(EnvGroup.workspace_id == workspace_id)
    )

    public_patch_secret_target = await client.patch(
        f"/api/public/v1/env-groups/{session_secret.json()['id']}",
        headers=auth_header(public_token),
        json={"variables": {"BASE_URL": {"type": "plain", "value": "https://example.test"}}},
    )
    assert public_patch_secret_target.status_code == 422
    assert public_patch_secret_target.json()["code"] == "VALIDATION_ERROR"

    public_copy_secret = await client.post(
        f"/api/public/v1/env-groups/{session_secret.json()['id']}/copy",
        headers=auth_header(public_token),
    )
    assert public_copy_secret.status_code == 409
    assert public_copy_secret.json()["code"] == "ENV_GROUP_SECRET_PUBLIC_COPY_DENIED"
    after_count = db_session.scalar(
        select(func.count(EnvGroup.id)).where(EnvGroup.workspace_id == workspace_id)
    )
    assert after_count == before_count
    assert "runtime-token" not in public_copy_secret.text


@pytest.mark.anyio
async def test_public_env_group_patch_without_variables_does_not_expose_secret_metadata(
    client: AsyncClient,
) -> None:
    csrf, workspace_id, _user_id = await register(client, "p2-secret-public-metadata@example.com")
    public_token = await create_pat(client, csrf, workspace_id, scopes=["config:write"])
    session_secret = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "name": "Session mixed secret",
            "variables": {
                "BASE_URL": {"type": "plain", "value": "https://api.example.test"},
                "API_TOKEN": {"type": "secret", "value": "runtime-token"},
            },
        },
    )
    assert session_secret.status_code == 201

    public_patch = await client.patch(
        f"/api/public/v1/env-groups/{session_secret.json()['id']}",
        headers=auth_header(public_token),
        json={"description": "Public metadata edit"},
    )

    assert public_patch.status_code == 200
    body = public_patch.json()
    assert body["variableCount"] == 1
    assert body["variables"] == {"BASE_URL": {"type": "plain", "value": "https://api.example.test"}}
    assert "API_TOKEN" not in public_patch.text
    assert "runtime-token" not in public_patch.text
    assert "hasValue" not in public_patch.text
    assert "displayValue" not in public_patch.text


@pytest.mark.anyio
async def test_secret_env_group_runtime_snapshot_preview_and_report_do_not_expose_plaintext(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "p2-secret-runtime@example.com")
    node = seed_idle_node(db_session, workspace_id=workspace_id, user_id=user_id)
    env_response = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "name": "Runtime secret",
            "variables": {
                "BASE_URL": {"type": "plain", "value": "https://api.example.test"},
                "API_TOKEN": {"type": "secret", "value": "runtime-token"},
            },
        },
    )
    assert env_response.status_code == 201
    scenario_response = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(),
    )
    assert scenario_response.status_code == 201

    plan_response = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "name": "Secret preview plan",
            "description": None,
            "tags": [],
            "envGroupId": env_response.json()["id"],
            "runMode": "sequential",
            "resource": {"poolType": "private", "selectedNodeId": node.id},
            "scenarioItems": [
                {
                    "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8A",
                    "scenarioId": scenario_response.json()["id"],
                    "enabled": True,
                    "order": 0,
                    "loadSettings": {
                        "concurrencyPerNode": 1,
                        "rampUpSeconds": 0,
                        "holdForSeconds": 60,
                        "iterations": None,
                        "targetRps": None,
                        "steps": None,
                        "delaySeconds": 0,
                    },
                }
            ],
            "slaRules": [],
        },
    )
    assert plan_response.status_code == 201

    preview = await client.get(
        f"/api/v1/test-plans/{plan_response.json()['id']}/execution-preview",
        headers={"x-workspace-id": workspace_id},
        params={"runType": "debug"},
    )
    assert preview.status_code == 200
    assert "runtime-token" not in preview.text
    assert "<redacted-env-value>" in preview.json()["content"]

    run_create = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "runType": "debug",
            "sourceType": "debug_scenario",
            "sourceId": scenario_response.json()["id"],
            "expectedSourceRevision": scenario_response.json()["revision"],
            "envGroupId": env_response.json()["id"],
            "selectedNodeId": node.id,
        },
    )
    assert run_create.status_code == 201
    snapshot = db_session.scalar(
        select(RunSnapshot).where(RunSnapshot.run_id == run_create.json()["id"])
    )
    assert snapshot is not None
    assert snapshot.snapshot_json["envGroup"]["variables"]["API_TOKEN"] == "runtime-token"

    report = await client.get(
        f"/api/v1/runs/{run_create.json()['id']}",
        headers={"x-workspace-id": workspace_id},
    )
    assert report.status_code == 200
    assert "runtime-token" not in report.text
    assert report.json()["snapshot"]["envGroupVariableKeys"] == ["API_TOKEN", "BASE_URL"]

    public_token = await create_pat(client, csrf, workspace_id, scopes=["read", "run"])
    public_report = await client.get(
        f"/api/public/v1/runs/{run_create.json()['id']}/report",
        headers=auth_header(public_token),
    )
    assert public_report.status_code == 200
    assert "runtime-token" not in public_report.text
    assert public_report.json()["snapshot"]["envGroupVariableKeys"] == ["API_TOKEN", "BASE_URL"]
