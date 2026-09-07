import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import DEFAULT_WORKSPACE_ID, AuditEvent, User
from app.models.load_nodes import LoadNode
from app.models.runs import NodeLease, Run, RunSnapshot
from app.schemas.load_nodes import LoadNodeCredentialInput
from app.services.load_nodes import create_load_node


async def register(client: AsyncClient, email: str) -> tuple[str, str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "displayName": "Plan User", "password": "password123"},
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


def scenario_payload(name: str = "Checkout flow", path: str = "/v1/users") -> dict:
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


def plan_payload(*, scenario_id: str, env_group_id: str | None, node_id: str | None) -> dict:
    return {
        "name": "Checkout Load Test",
        "description": "Checkout flow baseline",
        "tags": ["checkout", "baseline"],
        "envGroupId": env_group_id,
        "runMode": "sequential",
        "resource": {"poolType": "private" if node_id else None, "selectedNodeId": node_id},
        "scenarioItems": [
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7C",
                "scenarioId": scenario_id,
                "enabled": True,
                "order": 0,
                "loadSettings": {
                    "concurrencyPerNode": 10,
                    "rampUpSeconds": 60,
                    "holdForSeconds": 300,
                    "iterations": None,
                    "targetRps": None,
                    "steps": None,
                    "delaySeconds": 0,
                },
            }
        ],
        "slaRules": [
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7E",
                "enabled": True,
                "subject": "p95",
                "label": None,
                "condition": "gt",
                "threshold": {"value": 500, "unit": "ms"},
                "timeframeLogic": "for",
                "timeframeSeconds": 10,
                "action": "continue",
            }
        ],
    }


async def create_env_group(
    client: AsyncClient, csrf: str, workspace_id: str, *, variables: dict | None = None
) -> str:
    if variables is None:
        variables = {"base_url": "https://api.example.internal"}
    response = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={"name": "Staging", "variables": variables},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def create_scenario(
    client: AsyncClient, csrf: str, workspace_id: str, *, name: str = "Checkout flow"
) -> str:
    response = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(name=name),
    )
    assert response.status_code == 201
    return response.json()["id"]


def seed_idle_node(db_session: Session, *, user_id: str, host_prefix: str = "plan-node") -> LoadNode:
    user = db_session.get(User, user_id)
    assert user is not None
    node = create_load_node(
        db_session,
        actor=user,
        workspace_id=DEFAULT_WORKSPACE_ID,
        scope="workspace",
        host=f"{host_prefix}-{user_id.lower()}.internal",
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        credential=credential(),
        ssh_host_key=trusted_host_key(),
        maintainer=None,
        remark=None,
    )
    node.status = "idle"
    db_session.flush()
    return node


async def create_ready_plan(
    client: AsyncClient,
    db_session: Session,
    *,
    csrf: str,
    workspace_id: str,
    user_id: str,
    host_prefix: str,
    env_group_variables: dict | None = None,
) -> tuple[dict, LoadNode]:
    node = seed_idle_node(db_session, user_id=user_id, host_prefix=host_prefix)
    env_id = await create_env_group(
        client, csrf, workspace_id, variables=env_group_variables
    )
    scenario_id = await create_scenario(client, csrf, workspace_id)
    payload = plan_payload(scenario_id=scenario_id, env_group_id=env_id, node_id=node.id)
    created = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=payload,
    )
    assert created.status_code == 201
    return created.json(), node


@pytest.mark.anyio
async def test_test_plan_crud_revision_and_reference_guards(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "plan-crud@example.com")
    node = seed_idle_node(db_session, user_id=user_id)
    env_id = await create_env_group(client, csrf, workspace_id)
    scenario_id = await create_scenario(client, csrf, workspace_id)
    base = plan_payload(scenario_id=scenario_id, env_group_id=env_id, node_id=node.id)

    invalid_child_id = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            **base,
            "scenarioItems": [
                {**base["scenarioItems"][0], "id": "IIIIIIIIIIIIIIIIIIIIIIIIII"}
            ],
        },
    )
    assert invalid_child_id.status_code == 422
    assert invalid_child_id.json()["code"] == "VALIDATION_ERROR"
    assert invalid_child_id.json()["details"][0]["code"] == "INVALID_FIELD"

    duplicate_child_ids = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            **base,
            "scenarioItems": [base["scenarioItems"][0], base["scenarioItems"][0]],
            "slaRules": [base["slaRules"][0], base["slaRules"][0]],
        },
    )
    assert duplicate_child_ids.status_code == 422
    assert [item["code"] for item in duplicate_child_ids.json()["details"]] == [
        "duplicate_child_id",
        "duplicate_child_id",
    ]

    draft = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "name": "Draft plan",
            "description": None,
            "tags": [],
            "envGroupId": None,
            "runMode": "sequential",
            "resource": {"poolType": None, "selectedNodeId": None},
            "scenarioItems": [],
            "slaRules": [],
        },
    )
    assert draft.status_code == 201
    assert draft.json()["revision"] == 1
    assert draft.json()["runMode"] == "sequential"
    assert draft.json()["runGuard"]["expectedConcurrencyPerNode"] == 0
    assert draft.json()["runnable"] is False
    assert "no_enabled_scenarios" in draft.json()["notRunnableReasons"]

    stale = await client.patch(
        f"/api/v1/test-plans/{draft.json()['id']}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={**base, "expectedRevision": 99},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "TEST_PLAN_REVISION_CONFLICT"

    patched = await client.patch(
        f"/api/v1/test-plans/{draft.json()['id']}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={**base, "expectedRevision": 1},
    )
    assert patched.status_code == 200
    detail = patched.json()
    assert detail["revision"] == 2
    assert detail["scenarioItems"][0]["scenarioName"] == "Checkout flow"
    assert detail["slaRules"][0]["threshold"]["unit"] == "ms"
    assert detail["runGuard"]["expectedConcurrencyPerNode"] == 10
    assert detail["runnable"] is True

    listed = await client.get("/api/v1/test-plans", headers={"x-workspace-id": workspace_id})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["enabledScenarioItemCount"] == 1
    assert listed.json()["items"][0]["resource"]["selectedNodeId"] == node.id
    for params in (
        {"page": "0"},
        {"page": "not-a-number"},
        {"pageSize": "101"},
        {"search": "x" * 121},
        {"tag": "x" * 33},
        {"unexpected": "1"},
    ):
        invalid_query = await client.get(
            "/api/v1/test-plans",
            headers={"x-workspace-id": workspace_id},
            params=params,
        )
        assert invalid_query.status_code == 400
        assert invalid_query.json()["code"] == "INVALID_QUERY_PARAMETER"

    blocked_env_delete = await client.delete(
        f"/api/v1/env-groups/{env_id}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
    )
    assert blocked_env_delete.status_code == 409
    assert blocked_env_delete.json()["code"] == "ENV_GROUP_IN_USE"

    blocked_scenario_delete = await client.delete(
        f"/api/v1/scenarios/{scenario_id}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
    )
    assert blocked_scenario_delete.status_code == 409
    assert blocked_scenario_delete.json()["code"] == "RESOURCE_IN_USE"

    deleted = await client.delete(
        f"/api/v1/test-plans/{detail['id']}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
    )
    assert deleted.status_code == 204
    after_delete = await client.get("/api/v1/test-plans", headers={"x-workspace-id": workspace_id})
    assert after_delete.json()["total"] == 0


@pytest.mark.anyio
async def test_test_plan_run_now_creates_snapshot_and_busy_lease(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "plan-run@example.com")
    plan, node = await create_ready_plan(
        client, db_session, csrf=csrf, workspace_id=workspace_id, user_id=user_id,
        host_prefix="plan-run-node",
    )

    run_now = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "runType": "standard",
            "sourceType": "test_plan",
            "sourceId": plan["id"],
            "expectedSourceRevision": plan["revision"],
            "confirmHighConcurrency": False,
        },
    )
    assert run_now.status_code == 201
    run_body = run_now.json()
    assert run_body["runType"] == "standard"
    assert run_body["sourceType"] == "test_plan"
    assert run_body["sourceId"] == plan["id"]
    assert run_body["selectedNodeId"] == node.id
    assert run_body["validity"] == "valid"
    assert run_body["deduplicated"] is False

    node = db_session.get(LoadNode, node.id)
    assert node.status == "busy"
    assert node.current_run_id == run_body["id"]

    snapshot = db_session.scalar(
        select(RunSnapshot).where(RunSnapshot.run_id == run_body["id"])
    )
    assert snapshot is not None
    payload = snapshot.snapshot_json
    assert payload["schemaVersion"] == 1
    assert payload["runType"] == "standard"
    assert payload["sourceType"] == "test_plan"
    assert payload["sourceRevision"] == plan["revision"]
    assert payload["validityDefault"] == "valid"
    assert payload["slaEvaluationMode"] == "passfail"
    assert payload["testPlan"]["name"] == plan["name"]
    assert payload["envGroup"]["name"] == "Staging"
    assert payload["resourceRequest"] == {
        "mode": "manual",
        "poolType": "private",
        "selectedNodeId": node.id,
        "expectedConcurrencyPerNode": 10,
    }
    item = payload["scenarioItems"][0]
    assert item["scenarioId"] is not None
    assert item["loadSettings"]["concurrencyPerNode"] == 10
    assert "generatedYaml" in payload
    assert payload["generatedYaml"]["artifactRelativePath"] == "execution/generated.yml"

    lease = db_session.scalar(
        select(NodeLease).where(NodeLease.run_id == run_body["id"], NodeLease.released_at.is_(None))
    )
    assert lease is not None

    audit = db_session.scalar(
        select(AuditEvent).where(AuditEvent.event_type == "run.standard_requested")
    )
    assert audit is not None
    assert audit.details_json["testPlanId"] == plan["id"]

    # An active Run blocks Test Plan delete.
    blocked_delete = await client.delete(
        f"/api/v1/test-plans/{plan['id']}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
    )
    assert blocked_delete.status_code == 409
    assert blocked_delete.json()["code"] == "RESOURCE_IN_USE"


@pytest.mark.anyio
async def test_test_plan_run_now_dedup_returns_existing_run(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "plan-dedup@example.com")
    plan, _node = await create_ready_plan(
        client, db_session, csrf=csrf, workspace_id=workspace_id, user_id=user_id,
        host_prefix="plan-dedup-node",
    )
    body = {
        "runType": "standard",
        "sourceType": "test_plan",
        "sourceId": plan["id"],
        "expectedSourceRevision": plan["revision"],
        "confirmHighConcurrency": False,
    }
    first = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=body,
    )
    assert first.status_code == 201
    second = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=body,
    )
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["id"] == first.json()["id"]
    assert second_body["deduplicated"] is True

    runs = list(db_session.scalars(select(Run).where(Run.source_type == "test_plan")))
    assert len(runs) == 1
    leases = list(
        db_session.scalars(
            select(NodeLease).where(NodeLease.released_at.is_(None))
        )
    )
    assert len(leases) == 1


@pytest.mark.anyio
async def test_test_plan_debug_uses_fixed_low_risk_profile(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "plan-debug@example.com")
    plan, node = await create_ready_plan(
        client, db_session, csrf=csrf, workspace_id=workspace_id, user_id=user_id,
        host_prefix="plan-debug-node",
    )

    debug = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "runType": "debug",
            "sourceType": "test_plan",
            "sourceId": plan["id"],
            "expectedSourceRevision": plan["revision"],
        },
    )
    assert debug.status_code == 201
    debug_body = debug.json()
    assert debug_body["runType"] == "debug"
    assert debug_body["validity"] == "invalid"

    snapshot = db_session.scalar(
        select(RunSnapshot).where(RunSnapshot.run_id == debug_body["id"])
    )
    assert snapshot is not None
    payload = snapshot.snapshot_json
    assert payload["runType"] == "debug"
    assert payload["validityDefault"] == "invalid"
    assert payload["slaEvaluationMode"] == "not_evaluated"
    assert payload["slaRules"] == []
    assert payload["testPlan"]["runMode"] == "sequential"
    assert payload["resourceRequest"]["expectedConcurrencyPerNode"] == 1
    item = payload["scenarioItems"][0]
    assert item["loadSettings"] == {
        "concurrencyPerNode": 1,
        "rampUpSeconds": 0,
        "holdForSeconds": None,
        "iterations": 1,
        "targetRps": None,
        "steps": None,
        "delaySeconds": 0,
    }
    assert item["loadSettings"]["iterations"] == 1
    assert node.id == debug_body["selectedNodeId"]


@pytest.mark.anyio
async def test_test_plan_run_now_revision_override_and_runnable_guards(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "plan-guards@example.com")
    plan, node = await create_ready_plan(
        client, db_session, csrf=csrf, workspace_id=workspace_id, user_id=user_id,
        host_prefix="plan-guards-node",
    )

    stale = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "runType": "standard",
            "sourceType": "test_plan",
            "sourceId": plan["id"],
            "expectedSourceRevision": 99,
        },
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "TEST_PLAN_REVISION_CONFLICT"

    override = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "runType": "standard",
            "sourceType": "test_plan",
            "sourceId": plan["id"],
            "expectedSourceRevision": plan["revision"],
            "envGroupId": "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
        },
    )
    assert override.status_code == 422
    assert override.json()["details"][0]["code"] == "unsupported_run_override"

    draft = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "name": "Incomplete plan",
            "description": None,
            "tags": [],
            "envGroupId": None,
            "runMode": "sequential",
            "resource": {"poolType": "private", "selectedNodeId": node.id},
            "scenarioItems": [],
            "slaRules": [],
        },
    )
    assert draft.status_code == 201
    not_runnable = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "runType": "standard",
            "sourceType": "test_plan",
            "sourceId": draft.json()["id"],
            "expectedSourceRevision": 1,
        },
    )
    assert not_runnable.status_code == 409
    assert not_runnable.json()["code"] == "TEST_PLAN_NOT_RUNNABLE"


@pytest.mark.anyio
async def test_test_plan_soft_limit_requires_high_concurrency_confirmation(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_SINGLE_NODE_CONCURRENCY_SOFT_LIMIT", "5")
    csrf, workspace_id, user_id = await register(client, "plan-soft-limit@example.com")
    plan, _node = await create_ready_plan(
        client, db_session, csrf=csrf, workspace_id=workspace_id, user_id=user_id,
        host_prefix="plan-soft-limit-node",
    )
    body = {
        "runType": "standard",
        "sourceType": "test_plan",
        "sourceId": plan["id"],
        "expectedSourceRevision": plan["revision"],
        "confirmHighConcurrency": False,
    }
    unconfirmed = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=body,
    )
    assert unconfirmed.status_code == 409
    assert unconfirmed.json()["code"] == "LOAD_SOFT_LIMIT_CONFIRMATION_REQUIRED"
    assert unconfirmed.json()["details"][0]["meta"] == {
        "expectedConcurrencyPerNode": 10,
        "softLimit": 5,
    }

    confirmed = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={**body, "confirmHighConcurrency": True},
    )
    assert confirmed.status_code == 201


@pytest.mark.anyio
async def test_test_plan_run_now_busy_node_without_dedup_returns_busy(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "plan-busy@example.com")
    plan, node = await create_ready_plan(
        client, db_session, csrf=csrf, workspace_id=workspace_id, user_id=user_id,
        host_prefix="plan-busy-node",
    )
    node = db_session.get(LoadNode, node.id)
    node.status = "busy"
    node.last_status_reason = "occupied by another run"
    db_session.flush()

    busy = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "runType": "standard",
            "sourceType": "test_plan",
            "sourceId": plan["id"],
            "expectedSourceRevision": plan["revision"],
            "confirmHighConcurrency": True,
        },
    )
    assert busy.status_code == 409
    assert busy.json()["code"] == "LOAD_NODE_BUSY"
    assert db_session.scalar(select(Run).where(Run.source_type == "test_plan")) is None


@pytest.mark.anyio
async def test_test_plan_run_now_rejects_missing_env_variable(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "plan-variable@example.com")
    plan, _node = await create_ready_plan(
        client,
        db_session,
        csrf=csrf,
        workspace_id=workspace_id,
        user_id=user_id,
        host_prefix="plan-variable-node",
        env_group_variables={"other": "https://else.internal"},
    )
    run_now = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "runType": "debug",
            "sourceType": "test_plan",
            "sourceId": plan["id"],
            "expectedSourceRevision": plan["revision"],
        },
    )
    assert run_now.status_code == 422
    assert run_now.json()["code"] == "VALIDATION_ERROR"
    assert run_now.json()["details"][0]["code"] == "missing_variable"
