from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import (
    AuditEvent,
    DEFAULT_WORKSPACE_ID,
    ApiToken,
    User,
    Workspace,
    WorkspaceMember,
)
from app.models.load_nodes import LoadNode
from app.models.runs import Run, RunControlRequest
from app.schemas.load_nodes import LoadNodeCredentialInput
from app.services.load_nodes import create_load_node
from app.services.runs import create_protocol_smoke_run
from app.services.storage import LimitedHashingReader, PutResult, StorageClient, StoredObjectStream


class PublicApiFakeStorage(StorageClient):
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_stream(self, *, bucket, object_key, stream, size_limit, content_type=None):
        reader = LimitedHashingReader(stream, size_limit=size_limit)
        data = bytearray()
        while True:
            chunk = reader.read(1024)
            if not chunk:
                break
            data.extend(chunk)
        self.objects[(bucket, object_key)] = bytes(data)
        return PutResult(size_bytes=reader.size_bytes, sha256=reader.sha256_hex)

    def get_stream(self, *, bucket, object_key):
        data = self.objects[(bucket, object_key)]
        return StoredObjectStream(
            content_type="application/octet-stream",
            size_bytes=len(data),
            stream=BytesIO(data),
        )

    def delete_object_best_effort(self, *, bucket, object_key):
        self.objects.pop((bucket, object_key), None)
        return True

    def copy_object(self, *, bucket, source_key, destination_key):
        self.objects[(bucket, destination_key)] = self.objects[(bucket, source_key)]

    def health_check(self):
        return True


@pytest.fixture()
def public_api_fake_storage(monkeypatch: pytest.MonkeyPatch) -> PublicApiFakeStorage:
    from app.routes import public_api

    storage = PublicApiFakeStorage()
    monkeypatch.setattr(public_api, "get_storage_client", lambda: storage)
    return storage


def future_expiry() -> str:
    return (datetime.now(UTC) + timedelta(days=30)).isoformat().replace("+00:00", "Z")


async def register(
    client: AsyncClient,
    email: str = "public-api@example.com",
    display_name: str = "Public API User",
) -> tuple[str, str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "displayName": display_name, "password": "password123"},
    )
    assert response.status_code == 201
    body = response.json()
    return body["csrfToken"], body["defaultWorkspace"]["id"], body["user"]["id"]


async def create_pat(
    client: AsyncClient,
    csrf: str,
    workspace_ids: list[str],
    *,
    scopes: list[str],
    name: str = "Public automation",
) -> str:
    response = await client.post(
        "/api/v1/account/api-tokens",
        headers={"x-csrf-token": csrf},
        json={
            "name": name,
            "scopes": scopes,
            "workspaceAllowlist": workspace_ids,
            "expiresAt": future_expiry(),
        },
    )
    assert response.status_code == 201
    return response.json()["token"]["plaintext"]


def auth_header(plaintext: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {plaintext}"}


@pytest.mark.anyio
async def test_public_api_requires_pat_bearer_and_checks_scope_without_csrf(
    client: AsyncClient,
) -> None:
    csrf, workspace_id, _user_id = await register(client)

    cookie_only = await client.get("/api/public/v1/scenarios")
    assert cookie_only.status_code == 401
    assert cookie_only.json()["code"] == "UNAUTHENTICATED"

    config_token = await create_pat(client, csrf, [workspace_id], scopes=["config:write"])
    denied_read = await client.get("/api/public/v1/scenarios", headers=auth_header(config_token))
    assert denied_read.status_code == 403
    assert denied_read.json()["code"] == "PUBLIC_TOKEN_SCOPE_DENIED"

    created_env_group = await client.post(
        "/api/public/v1/env-groups",
        headers=auth_header(config_token),
        json={
            "name": "Public Env",
            "description": None,
            "variables": {"BASE_URL": {"type": "plain", "value": "https://example.test"}},
        },
    )
    assert created_env_group.status_code == 201
    assert created_env_group.json()["name"] == "Public Env"
    assert created_env_group.headers["x-workspace-id"] == workspace_id

    env_group_list = await client.get(
        "/api/public/v1/env-groups", headers=auth_header(config_token)
    )
    assert env_group_list.status_code == 405


@pytest.mark.anyio
async def test_public_api_resolves_only_explicit_or_single_allowlisted_workspace(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "multi-workspace@example.com", "Multi")
    other_workspace = Workspace(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7Y",
        name="Automation Workspace",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    denied_workspace = Workspace(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7X",
        name="Denied Workspace",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add_all([other_workspace, denied_workspace])
    db_session.add(
        WorkspaceMember(
            workspace_id=other_workspace.id, user_id=user_id, joined_at=datetime.now(UTC)
        )
    )
    db_session.flush()

    read_token = await create_pat(
        client,
        csrf,
        [workspace_id, other_workspace.id],
        scopes=["read"],
        name="Multi workspace reader",
    )

    missing_header = await client.get("/api/public/v1/scenarios", headers=auth_header(read_token))
    assert missing_header.status_code == 400
    assert missing_header.json()["code"] == "WORKSPACE_REQUIRED"

    explicit_allowed = await client.get(
        "/api/public/v1/scenarios",
        headers={**auth_header(read_token), "x-workspace-id": other_workspace.id},
    )
    assert explicit_allowed.status_code == 200
    assert explicit_allowed.headers["x-workspace-id"] == other_workspace.id

    explicit_denied = await client.get(
        "/api/public/v1/scenarios",
        headers={**auth_header(read_token), "x-workspace-id": denied_workspace.id},
    )
    assert explicit_denied.status_code == 403
    assert explicit_denied.json()["code"] == "WORKSPACE_ACCESS_DENIED"


@pytest.mark.anyio
async def test_public_api_invalidates_disabled_users_and_revoked_tokens(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "revoked-public@example.com", "Revoked")
    read_token = await create_pat(client, csrf, [workspace_id], scopes=["read"])

    disabled_user = db_session.get(User, user_id)
    assert disabled_user is not None
    disabled_user.status = "disabled"
    disabled_user.disabled_at = datetime.now(UTC)
    db_session.flush()

    disabled = await client.get("/api/public/v1/scenarios", headers=auth_header(read_token))
    assert disabled.status_code == 401
    assert disabled.json()["code"] == "UNAUTHENTICATED"

    disabled_user.status = "active"
    disabled_user.disabled_at = None
    db_session.flush()
    csrf_response = await client.get("/api/v1/auth/csrf")
    assert csrf_response.status_code == 200
    revoke = await client.delete(
        "/api/v1/account/api-tokens/"
        + (await client.get("/api/v1/account/api-tokens")).json()["items"][0]["id"],
        headers={"x-csrf-token": csrf_response.json()["csrfToken"]},
    )
    assert revoke.status_code == 204

    revoked = await client.get("/api/public/v1/scenarios", headers=auth_header(read_token))
    assert revoked.status_code == 401
    assert revoked.json()["code"] == "UNAUTHENTICATED"


@pytest.mark.anyio
async def test_public_api_invalidates_expired_tokens_and_lost_workspace_membership(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "expired-public@example.com", "Expired")
    expired_token = await create_pat(
        client, csrf, [workspace_id], scopes=["read"], name="Expiring reader"
    )
    token_record = db_session.scalar(
        select(ApiToken).where(
            ApiToken.actor_user_id == user_id, ApiToken.name == "Expiring reader"
        )
    )
    assert token_record is not None
    token_record.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.flush()

    expired = await client.get("/api/public/v1/scenarios", headers=auth_header(expired_token))
    assert expired.status_code == 401
    assert expired.json()["code"] == "UNAUTHENTICATED"

    membership_token = await create_pat(
        client, csrf, [workspace_id], scopes=["read"], name="Membership reader"
    )
    membership = db_session.get(WorkspaceMember, {"workspace_id": workspace_id, "user_id": user_id})
    assert membership is not None
    db_session.delete(membership)
    db_session.flush()

    lost_membership = await client.get(
        "/api/public/v1/scenarios", headers=auth_header(membership_token)
    )
    assert lost_membership.status_code == 403
    assert lost_membership.json()["code"] == "WORKSPACE_ACCESS_DENIED"


def trusted_host_key() -> dict[str, str]:
    return {
        "algorithm": "ssh-ed25519",
        "publicKey": "AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC",
        "fingerprintSha256": "SHA256:SurgePilotTrustedHostKey",
    }


def credential() -> LoadNodeCredentialInput:
    return LoadNodeCredentialInput(authType="password", password="secret-password")


def seed_idle_node_and_run(
    db_session: Session, *, user_id: str, monkeypatch: pytest.MonkeyPatch
) -> tuple[LoadNode, Run]:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = db_session.get(User, user_id)
    assert user is not None
    node = create_load_node(
        db_session,
        actor=user,
        workspace_id=DEFAULT_WORKSPACE_ID,
        scope="workspace",
        host=f"public-run-node-{user_id.lower()}.internal",
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
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    db_session.flush()
    return node, run


@pytest.mark.anyio
async def test_public_run_stop_uses_existing_idempotent_run_service_without_csrf(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf, workspace_id, user_id = await register(client, "public-run@example.com", "Runner")
    _node, run = seed_idle_node_and_run(db_session, user_id=user_id, monkeypatch=monkeypatch)
    run_token = await create_pat(client, csrf, [workspace_id], scopes=["run"])

    listed = await client.get("/api/public/v1/runs", headers=auth_header(run_token))
    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == run.id

    stopped = await client.post(
        f"/api/public/v1/runs/{run.id}/stop",
        headers=auth_header(run_token),
    )
    assert stopped.status_code == 202
    assert stopped.json()["state"] == "stopping"
    assert stopped.json()["duplicate"] is False
    assert (
        db_session.scalar(
            select(RunControlRequest).where(
                RunControlRequest.run_id == run.id, RunControlRequest.action == "stop"
            )
        )
        is not None
    )

    duplicate = await client.post(
        f"/api/public/v1/runs/{run.id}/stop",
        headers=auth_header(run_token),
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True


@pytest.mark.anyio
async def test_public_load_nodes_summary_omits_credential_material(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "public-load-nodes@example.com", "Nodes")
    user = db_session.get(User, user_id)
    assert user is not None
    node = create_load_node(
        db_session,
        actor=user,
        workspace_id=workspace_id,
        scope="workspace",
        host="public-node.internal",
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        credential=credential(),
        ssh_host_key=trusted_host_key(),
        maintainer="SRE",
        remark="Public API visible",
    )
    node.status = "idle"
    node.runtime_version = "runtime-test-v1"
    db_session.flush()
    read_token = await create_pat(client, csrf, [workspace_id], scopes=["read"])

    response = await client.get("/api/public/v1/load-nodes", headers=auth_header(read_token))
    assert response.status_code == 200
    text = response.text
    assert "credential" not in text.lower()
    assert "password" not in text.lower()
    assert "privateKey" not in text
    assert response.json()["items"][0]["id"] == node.id


def scenario_payload(name: str = "Public checkout", path: str = "/v1/public") -> dict:
    return {
        "name": name,
        "description": "Public API scenario",
        "tags": ["public"],
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
        "steps": [
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7D",
                "enabled": True,
                "name": "Public request",
                "method": "GET",
                "path": path,
                "queryParams": [],
                "headers": [],
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


def plan_payload(
    *,
    scenario_id: str,
    env_group_id: str,
    node_id: str,
    item_id: str = "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
) -> dict:
    return {
        "name": "Public Test Plan",
        "description": "Public API plan",
        "tags": ["public"],
        "envGroupId": env_group_id,
        "runMode": "sequential",
        "resource": {"mode": "manual", "poolType": "private", "selectedNodeId": node_id},
        "scenarioItems": [
            {
                "id": item_id,
                "scenarioId": scenario_id,
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
    }


@pytest.mark.anyio
async def test_public_dependency_files_support_upload_list_reference_protection_and_delete(
    client: AsyncClient,
    db_session: Session,
    public_api_fake_storage: PublicApiFakeStorage,
) -> None:
    csrf, workspace_id, _user_id = await register(
        client, "public-dependency@example.com", "Dependency Public"
    )
    token = await create_pat(
        client,
        csrf,
        [workspace_id],
        scopes=["read", "config:write", "dependency:write"],
        name="Dependency automation",
    )
    read_only_token = await create_pat(
        client,
        csrf,
        [workspace_id],
        scopes=["read"],
        name="Dependency reader",
    )

    denied_upload = await client.post(
        "/api/public/v1/dependency-files",
        headers=auth_header(read_only_token),
        files={"file": ("setup.groovy", b"println('denied')\n", "text/x-groovy")},
    )
    assert denied_upload.status_code == 403
    assert denied_upload.json()["code"] == "PUBLIC_TOKEN_SCOPE_DENIED"

    content = b"println('public dependency')\n"
    uploaded = await client.post(
        "/api/public/v1/dependency-files",
        headers=auth_header(token),
        files={"file": ("setup.groovy", content, "text/x-groovy")},
    )
    assert uploaded.status_code == 201
    file_body = uploaded.json()
    dependency_file_id = file_body["id"]
    assert file_body["filename"] == "setup.groovy"
    assert file_body["sizeBytes"] == len(content)
    assert file_body["inUse"] is False
    assert uploaded.headers["x-workspace-id"] == workspace_id
    assert any(value == content for value in public_api_fake_storage.objects.values())

    listed = await client.get("/api/public/v1/dependency-files", headers=auth_header(token))
    assert listed.status_code == 200
    listed_item = listed.json()["items"][0]
    assert listed_item["id"] == dependency_file_id
    assert listed_item["filename"] == "setup.groovy"
    assert listed_item["sha256"] == file_body["sha256"]
    assert listed_item["inUse"] is False

    payload = scenario_payload("Dependency scenario", "/v1/dependency")
    payload["steps"][0]["scripts"] = [
        {
            "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8T",
            "execute": "before",
            "language": "groovy",
            "dependencyFileId": dependency_file_id,
            "enabled": True,
        }
    ]
    created_scenario = await client.post(
        "/api/public/v1/scenarios",
        headers=auth_header(token),
        json=payload,
    )
    assert created_scenario.status_code == 201
    scenario_id = created_scenario.json()["id"]

    listed_in_use = await client.get("/api/public/v1/dependency-files", headers=auth_header(token))
    assert listed_in_use.status_code == 200
    assert listed_in_use.json()["items"][0]["inUse"] is True

    invalid_delete = await client.delete(
        "/api/public/v1/dependency-files/not-a-ulid", headers=auth_header(token)
    )
    assert invalid_delete.status_code == 422
    assert invalid_delete.json()["code"] == "VALIDATION_ERROR"

    in_use_delete = await client.delete(
        f"/api/public/v1/dependency-files/{dependency_file_id}", headers=auth_header(token)
    )
    assert in_use_delete.status_code == 409
    assert in_use_delete.json()["code"] == "FILE_IN_USE"

    deleted_scenario = await client.delete(
        f"/api/public/v1/scenarios/{scenario_id}", headers=auth_header(token)
    )
    assert deleted_scenario.status_code == 204

    deleted_file = await client.delete(
        f"/api/public/v1/dependency-files/{dependency_file_id}", headers=auth_header(token)
    )
    assert deleted_file.status_code == 204
    assert deleted_file.headers["x-workspace-id"] == workspace_id

    after_delete = await client.get("/api/public/v1/dependency-files", headers=auth_header(token))
    assert after_delete.status_code == 200
    assert after_delete.json()["items"] == []

    event_types = set(
        db_session.scalars(
            select(AuditEvent.event_type).where(AuditEvent.workspace_id == workspace_id)
        ).all()
    )
    assert {"dependency_file.uploaded", "dependency_file.deleted"}.issubset(event_types)


@pytest.mark.anyio
async def test_public_config_crud_and_run_create_use_existing_services(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "public-crud@example.com", "CRUD")
    user = db_session.get(User, user_id)
    assert user is not None
    node = create_load_node(
        db_session,
        actor=user,
        workspace_id=workspace_id,
        scope="workspace",
        host="public-crud-node.internal",
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
    config_token = await create_pat(client, csrf, [workspace_id], scopes=["config:write"])
    read_token = await create_pat(client, csrf, [workspace_id], scopes=["read"])
    run_token = await create_pat(client, csrf, [workspace_id], scopes=["run"])

    env_created = await client.post(
        "/api/public/v1/env-groups",
        headers=auth_header(config_token),
        json={
            "name": "Public CRUD Env",
            "variables": {"base_url": {"type": "plain", "value": "https://example.test"}},
        },
    )
    assert env_created.status_code == 201
    env_id = env_created.json()["id"]

    env_patched = await client.patch(
        f"/api/public/v1/env-groups/{env_id}",
        headers=auth_header(config_token),
        json={"description": "Patched through public API"},
    )
    assert env_patched.status_code == 200
    assert env_patched.json()["description"] == "Patched through public API"

    env_copied = await client.post(
        f"/api/public/v1/env-groups/{env_id}/copy", headers=auth_header(config_token)
    )
    assert env_copied.status_code == 201
    env_copy_id = env_copied.json()["id"]

    scenario_created = await client.post(
        "/api/public/v1/scenarios", headers=auth_header(config_token), json=scenario_payload()
    )
    assert scenario_created.status_code == 201
    scenario_id = scenario_created.json()["id"]

    scenario_listed = await client.get("/api/public/v1/scenarios", headers=auth_header(read_token))
    assert scenario_listed.status_code == 200
    assert scenario_listed.json()["items"][0]["id"] == scenario_id

    scenario_read = await client.get(
        f"/api/public/v1/scenarios/{scenario_id}", headers=auth_header(read_token)
    )
    assert scenario_read.status_code == 200
    assert scenario_read.json()["name"] == "Public checkout"

    scenario_patched = await client.patch(
        f"/api/public/v1/scenarios/{scenario_id}",
        headers=auth_header(config_token),
        json={**scenario_payload("Public checkout patched"), "expectedRevision": 1},
    )
    assert scenario_patched.status_code == 200
    assert scenario_patched.json()["revision"] == 2

    plan_created = await client.post(
        "/api/public/v1/test-plans",
        headers=auth_header(config_token),
        json=plan_payload(scenario_id=scenario_id, env_group_id=env_id, node_id=node.id),
    )
    assert plan_created.status_code == 201
    plan_id = plan_created.json()["id"]

    plan_listed = await client.get("/api/public/v1/test-plans", headers=auth_header(read_token))
    assert plan_listed.status_code == 200
    assert plan_listed.json()["items"][0]["id"] == plan_id

    plan_read = await client.get(
        f"/api/public/v1/test-plans/{plan_id}", headers=auth_header(read_token)
    )
    assert plan_read.status_code == 200
    assert plan_read.json()["name"] == "Public Test Plan"

    plan_patched = await client.patch(
        f"/api/public/v1/test-plans/{plan_id}",
        headers=auth_header(config_token),
        json={
            **plan_payload(scenario_id=scenario_id, env_group_id=env_id, node_id=node.id),
            "name": "Public Test Plan patched",
            "expectedRevision": 1,
        },
    )
    assert plan_patched.status_code == 200
    assert plan_patched.json()["revision"] == 2

    disposable_scenario = await client.post(
        "/api/public/v1/scenarios",
        headers=auth_header(config_token),
        json=scenario_payload("Disposable public scenario", "/v1/disposable"),
    )
    assert disposable_scenario.status_code == 201
    disposable_scenario_id = disposable_scenario.json()["id"]
    disposable_plan = await client.post(
        "/api/public/v1/test-plans",
        headers=auth_header(config_token),
        json=plan_payload(
            scenario_id=disposable_scenario_id,
            env_group_id=env_id,
            node_id=node.id,
            item_id="01HZX3Y9M0E9W7Z6M5QK9S8P7F",
        ),
    )
    assert disposable_plan.status_code == 201
    disposable_plan_deleted = await client.delete(
        f"/api/public/v1/test-plans/{disposable_plan.json()['id']}",
        headers=auth_header(config_token),
    )
    assert disposable_plan_deleted.status_code == 204
    disposable_scenario_deleted = await client.delete(
        f"/api/public/v1/scenarios/{disposable_scenario_id}", headers=auth_header(config_token)
    )
    assert disposable_scenario_deleted.status_code == 204
    env_copy_deleted = await client.delete(
        f"/api/public/v1/env-groups/{env_copy_id}", headers=auth_header(config_token)
    )
    assert env_copy_deleted.status_code == 204

    run_created = await client.post(
        "/api/public/v1/runs",
        headers=auth_header(run_token),
        json={
            "runType": "standard",
            "sourceType": "test_plan",
            "sourceId": plan_id,
            "expectedSourceRevision": 2,
        },
    )
    assert run_created.status_code == 201
    run_id = run_created.json()["id"]

    run_read = await client.get(f"/api/public/v1/runs/{run_id}", headers=auth_header(run_token))
    assert run_read.status_code == 200
    assert run_read.json()["id"] == run_id
    assert "debugHttpTrace" not in run_read.text

    report_read = await client.get(
        f"/api/public/v1/runs/{run_id}/report", headers=auth_header(run_token)
    )
    assert report_read.status_code == 200
    assert report_read.json()["id"] == run_id
    assert "debugHttpTrace" not in report_read.text

    env_delete_conflict = await client.delete(
        f"/api/public/v1/env-groups/{env_id}", headers=auth_header(config_token)
    )
    assert env_delete_conflict.status_code == 409

    plan_deleted = await client.delete(
        f"/api/public/v1/test-plans/{plan_id}", headers=auth_header(config_token)
    )
    assert plan_deleted.status_code == 409
