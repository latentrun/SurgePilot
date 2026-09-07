from datetime import UTC, datetime
import hashlib
import hmac

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import DEFAULT_WORKSPACE_ID, User, Workspace, WorkspaceMember
from app.models.load_nodes import LoadNode
from app.models.runs import NodeLease, Run, RunSnapshot
from app.schemas.load_nodes import LoadNodeCredentialInput
from app.services.load_nodes import create_load_node
from app.services.scenarios import bundle_file_path


def node_bound_token(secret: str, node_id: str) -> str:
    sig = hmac.new(secret.encode(), node_id.encode(), hashlib.sha256).hexdigest()
    return f"node:{node_id}:{sig}"


async def register(client: AsyncClient, email: str) -> tuple[str, str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "displayName": "Scenario User", "password": "password123"},
    )
    assert response.status_code == 201
    body = response.json()
    return body["csrfToken"], body["defaultWorkspace"]["id"], body["user"]["id"]


def trusted_host_key() -> dict[str, str]:
    return {
        "algorithm": "ssh-ed25519",
        "publicKey": "AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC",
        "fingerprintSha256": "SHA256:SurgePilotTrustedHostKey",
    }


def credential() -> LoadNodeCredentialInput:
    return LoadNodeCredentialInput(authType="password", password="secret-password")


def scenario_payload(name: str = "Checkout flow") -> dict:
    return {
        "name": name,
        "description": "Critical checkout APIs",
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
        "dataSources": [],
        "steps": [
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7D",
                "enabled": True,
                "name": "List users",
                "method": "GET",
                "path": "/v1/users",
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


def seed_idle_node(db_session: Session, *, user_id: str) -> LoadNode:
    user = db_session.get(User, user_id)
    assert user is not None
    node = create_load_node(
        db_session,
        actor=user,
        workspace_id=DEFAULT_WORKSPACE_ID,
        scope="workspace",
        host=f"scenario-node-{user_id.lower()}.internal",
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


async def runner_callback(
    client: AsyncClient,
    node: LoadNode,
    event_id: str,
    run_id: str,
    event_type: str,
    seq: int,
    details: dict[str, object],
):
    return await client.post(
        "/api/internal/v1/runner/callbacks",
        headers={"x-runner-token": node_bound_token("runner-secret", node.id)},
        json={
            "schemaVersion": "1",
            "eventId": event_id,
            "runId": run_id,
            "nodeId": node.id,
            "runtimeVersion": "runtime-test-v1",
            "eventType": event_type,
            "seq": seq,
            "eventTime": "2030-06-01T10:00:00.000Z",
            "details": details,
        },
    )


async def create_debug_env_group(
    client: AsyncClient, csrf: str, workspace_id: str, name: str
) -> str:
    env_response = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "name": name,
            "description": None,
            "variables": {"base_url": "https://api.example.internal"},
        },
    )
    assert env_response.status_code == 201
    return env_response.json()["id"]


async def create_debug_scenario(
    client: AsyncClient,
    csrf: str,
    workspace_id: str,
    name: str = "Checkout flow",
) -> tuple[str, int]:
    scenario_response = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(name),
    )
    assert scenario_response.status_code == 201
    scenario = scenario_response.json()
    return scenario["id"], scenario["revision"]


@pytest.mark.anyio
async def test_scenario_crud_is_workspace_scoped_and_revision_safe(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "scenario-crud@example.com")

    created = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(),
    )
    assert created.status_code == 201
    scenario = created.json()
    assert scenario["revision"] == 1
    assert scenario["scenarioType"] == "visual"

    listed = await client.get("/api/v1/scenarios", headers={"x-workspace-id": workspace_id})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["enabledStepCount"] == 1

    invalid_sort = await client.get(
        "/api/v1/scenarios?sort=createdAt", headers={"x-workspace-id": workspace_id}
    )
    assert invalid_sort.status_code == 400
    assert invalid_sort.json()["code"] == "INVALID_QUERY_PARAMETER"

    checkout_list = await client.get(
        "/api/v1/scenarios?tag=checkout", headers={"x-workspace-id": workspace_id}
    )
    assert checkout_list.status_code == 200
    assert checkout_list.json()["total"] == 1
    missing_tag_list = await client.get(
        "/api/v1/scenarios?tag=missing", headers={"x-workspace-id": workspace_id}
    )
    assert missing_tag_list.status_code == 200
    assert missing_tag_list.json()["total"] == 0

    stale = await client.patch(
        f"/api/v1/scenarios/{scenario['id']}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={**scenario_payload("Renamed"), "expectedRevision": 99},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "SCENARIO_REVISION_CONFLICT"

    patched = await client.patch(
        f"/api/v1/scenarios/{scenario['id']}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={**scenario_payload("Checkout smoke"), "expectedRevision": 1},
    )
    assert patched.status_code == 200
    assert patched.json()["revision"] == 2
    assert patched.json()["name"] == "Checkout smoke"

    other = Workspace(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7Z",
        name="Other Workspace",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(other)
    db_session.add(
        WorkspaceMember(workspace_id=other.id, user_id=user_id, joined_at=datetime.now(UTC))
    )
    db_session.flush()
    cross = await client.get(
        f"/api/v1/scenarios/{scenario['id']}", headers={"x-workspace-id": other.id}
    )
    assert cross.status_code == 404

    deleted = await client.delete(
        f"/api/v1/scenarios/{scenario['id']}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
    )
    assert deleted.status_code == 204
    after_delete = await client.get("/api/v1/scenarios", headers={"x-workspace-id": workspace_id})
    assert after_delete.json()["total"] == 0


@pytest.mark.anyio
async def test_debug_run_creates_snapshot_dedups_and_blocks_busy_node(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "scenario-debug@example.com")
    node = seed_idle_node(db_session, user_id=user_id)
    env_response = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "name": "Staging",
            "description": None,
            "variables": {"base_url": "https://api.example.internal"},
        },
    )
    assert env_response.status_code == 201
    scenario_response = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(),
    )
    assert scenario_response.status_code == 201
    scenario = scenario_response.json()
    payload = {
        "runType": "debug",
        "sourceType": "debug_scenario",
        "sourceId": scenario["id"],
        "expectedSourceRevision": scenario["revision"],
        "envGroupId": env_response.json()["id"],
        "selectedNodeId": node.id,
    }

    created = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=payload,
    )
    assert created.status_code == 201
    run_body = created.json()
    assert run_body["state"] == "initializing"
    assert run_body["deduplicated"] is False

    run = db_session.get(Run, run_body["id"])
    assert run is not None
    snapshot = db_session.scalar(select(RunSnapshot).where(RunSnapshot.run_id == run.id))
    assert snapshot is not None
    assert snapshot.snapshot_json["sourceType"] == "debug_scenario"
    assert snapshot.snapshot_json["scenario"]["id"] == scenario["id"]
    assert "storageObjectKey" not in str(snapshot.snapshot_json)
    assert db_session.scalar(select(NodeLease).where(NodeLease.run_id == run.id)) is not None

    duplicate = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=payload,
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["id"] == run.id
    assert duplicate.json()["deduplicated"] is True
    assert db_session.query(NodeLease).filter_by(node_id=node.id, released_at=None).count() == 1

    second_scenario_response = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload("Checkout alternate"),
    )
    assert second_scenario_response.status_code == 201
    second_scenario = second_scenario_response.json()

    non_dedup_busy = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            **payload,
            "sourceId": second_scenario["id"],
            "expectedSourceRevision": second_scenario["revision"],
        },
    )
    assert non_dedup_busy.status_code == 409
    assert non_dedup_busy.json()["code"] == "LOAD_NODE_BUSY"


@pytest.mark.anyio
async def test_debug_run_missing_variable_returns_field_validation(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "scenario-debug-missing-var@example.com")
    node = seed_idle_node(db_session, user_id=user_id)
    scenario_response = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(),
    )
    scenario = scenario_response.json()

    response = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "runType": "debug",
            "sourceType": "debug_scenario",
            "sourceId": scenario["id"],
            "expectedSourceRevision": scenario["revision"],
            "envGroupId": None,
            "selectedNodeId": node.id,
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert response.json()["details"][0]["code"] == "missing_variable"


def test_bundle_file_path_uses_safe_relative_path(db_session: Session) -> None:
    file = type("File", (), {"id": "01HZX3Y9M0E9W7Z6M5QK9S8P7C", "filename": "users.csv"})()
    assert bundle_file_path(file) == "files/01HZX3Y9M0E9W7Z6M5QK9S8P7C/users.csv"


@pytest.mark.anyio
async def test_debug_run_fake_runner_smoke_happy_path_reaches_finished(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf, workspace_id, user_id = await register(
        client, "scenario-fake-finished@example.com"
    )
    node = seed_idle_node(db_session, user_id=user_id)
    monkeypatch.setenv("RUNNER_INTERNAL_TOKEN", "runner-secret")
    env_group_id = await create_debug_env_group(
        client, csrf, workspace_id, "Staging"
    )
    scenario_id, scenario_revision = await create_debug_scenario(
        client, csrf, workspace_id
    )

    created = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "runType": "debug",
            "sourceType": "debug_scenario",
            "sourceId": scenario_id,
            "expectedSourceRevision": scenario_revision,
            "envGroupId": env_group_id,
            "selectedNodeId": node.id,
        },
    )
    assert created.status_code == 201
    run_id = created.json()["id"]
    assert created.json()["state"] == "initializing"

    running = await runner_callback(
        client, node, "01HZX3Y9M0E9W7Z6M5QK9S8P9A", run_id, "running", 1, {}
    )
    assert running.status_code == 200
    assert running.json()["stateChanged"] is True
    assert running.json()["currentState"] == "running"

    finished = await runner_callback(
        client,
        node,
        "01HZX3Y9M0E9W7Z6M5QK9S8P9B",
        run_id,
        "finished",
        2,
        {"processGroupExited": True},
    )
    assert finished.status_code == 200
    assert finished.json()["stateChanged"] is True
    assert finished.json()["currentState"] == "finished"

    run = db_session.get(Run, run_id)
    assert run is not None
    assert run.state == "finished"
    lease = db_session.scalar(select(NodeLease).where(NodeLease.run_id == run.id))
    assert lease is not None
    assert lease.released_at is not None
    assert db_session.get(LoadNode, node.id).status == "idle"


@pytest.mark.anyio
async def test_debug_run_fake_runner_smoke_failed_and_stop_paths(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf, workspace_id, user_id = await register(
        client, "scenario-fake-failed-stop@example.com"
    )
    node = seed_idle_node(db_session, user_id=user_id)
    monkeypatch.setenv("RUNNER_INTERNAL_TOKEN", "runner-secret")
    env_group_id = await create_debug_env_group(
        client, csrf, workspace_id, "Staging"
    )
    scenario_id, scenario_revision = await create_debug_scenario(
        client, csrf, workspace_id
    )

    def debug_run_payload() -> dict:
        return {
            "runType": "debug",
            "sourceType": "debug_scenario",
            "sourceId": scenario_id,
            "expectedSourceRevision": scenario_revision,
            "envGroupId": env_group_id,
            "selectedNodeId": node.id,
        }

    first = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=debug_run_payload(),
    )
    assert first.status_code == 201
    first_run_id = first.json()["id"]
    failed = await runner_callback(
        client,
        node,
        "01HZX3Y9M0E9W7Z6M5QK9S8P9C",
        first_run_id,
        "failed",
        1,
        {"processGroupExited": True, "reason": "runner_exit_nonzero"},
    )
    assert failed.status_code == 200
    assert failed.json()["currentState"] == "failed"
    run = db_session.get(Run, first_run_id)
    assert run is not None
    assert run.state == "failed"
    assert run.failure_reason == "runner_exit_nonzero"
    first_lease = db_session.scalar(
        select(NodeLease).where(NodeLease.run_id == first_run_id)
    )
    assert first_lease is not None
    assert first_lease.released_at is not None

    second_scenario_id, second_revision = await create_debug_scenario(
        client, csrf, workspace_id, name="Checkout stop"
    )
    second = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            **debug_run_payload(),
            "sourceId": second_scenario_id,
            "expectedSourceRevision": second_revision,
        },
    )
    assert second.status_code == 201
    second_run_id = second.json()["id"]
    running = await runner_callback(
        client, node, "01HZX3Y9M0E9W7Z6M5QK9S8P9D", second_run_id, "running", 1, {}
    )
    assert running.json()["currentState"] == "running"

    stopped = await client.post(
        f"/api/v1/runs/{second_run_id}/stop",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
    )
    assert stopped.status_code == 202
    assert stopped.json()["state"] == "stopping"

    aborted = await runner_callback(
        client,
        node,
        "01HZX3Y9M0E9W7Z6M5QK9S8P9E",
        second_run_id,
        "aborted",
        2,
        {"processGroupExited": True, "reason": "stopped_by_user"},
    )
    assert aborted.status_code == 200
    assert aborted.json()["currentState"] == "aborted"
    second_run = db_session.get(Run, second_run_id)
    assert second_run is not None
    assert second_run.state == "aborted"
    second_lease = db_session.scalar(
        select(NodeLease).where(NodeLease.run_id == second_run_id)
    )
    assert second_lease is not None
    assert second_lease.released_at is not None
    assert db_session.get(LoadNode, node.id).status == "idle"
