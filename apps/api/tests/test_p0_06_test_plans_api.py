from copy import deepcopy
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ids import new_ulid
from app.core.config import get_settings
from app.models.auth import DEFAULT_WORKSPACE_ID, AuditEvent, User, Workspace, WorkspaceMember
from app.models.load_nodes import LoadNode
from app.models.runs import NodeLease, Run, RunSnapshot
from app.schemas.load_nodes import LoadNodeCredentialInput
import app.services.test_plans as test_plans_service
from app.services.load_nodes import create_load_node
from app.services.scenarios import request_label


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


def seed_idle_node(
    db_session: Session, *, user_id: str, host_prefix: str = "plan-node"
) -> LoadNode:
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
    node.runtime_version = get_settings().load_node_runtime_version
    db_session.flush()
    return node


@pytest.mark.anyio
async def test_test_plan_crud_revision_and_reference_guards(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "plan-crud@example.com")
    node = seed_idle_node(db_session, user_id=user_id)
    env = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "name": "Staging",
            "variables": {"base_url": {"type": "plain", "value": "https://api.example.internal"}},
        },
    )
    assert env.status_code == 201
    scenario = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(),
    )
    assert scenario.status_code == 201
    invalid_child_id = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            **plan_payload(
                scenario_id=scenario.json()["id"], env_group_id=env.json()["id"], node_id=node.id
            ),
            "scenarioItems": [
                {
                    **plan_payload(
                        scenario_id=scenario.json()["id"],
                        env_group_id=env.json()["id"],
                        node_id=node.id,
                    )["scenarioItems"][0],
                    "id": "IIIIIIIIIIIIIIIIIIIIIIIIII",
                }
            ],
        },
    )
    assert invalid_child_id.status_code == 422
    assert invalid_child_id.json()["code"] == "VALIDATION_ERROR"
    hard_limit = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            **plan_payload(
                scenario_id=scenario.json()["id"], env_group_id=env.json()["id"], node_id=node.id
            ),
            "scenarioItems": [
                {
                    **plan_payload(
                        scenario_id=scenario.json()["id"],
                        env_group_id=env.json()["id"],
                        node_id=node.id,
                    )["scenarioItems"][0],
                    "loadSettings": {
                        **plan_payload(
                            scenario_id=scenario.json()["id"],
                            env_group_id=env.json()["id"],
                            node_id=node.id,
                        )["scenarioItems"][0]["loadSettings"],
                        "concurrencyPerNode": 10001,
                    },
                }
            ],
        },
    )
    assert hard_limit.status_code == 422
    assert hard_limit.json()["code"] == "VALIDATION_ERROR"
    assert hard_limit.json()["details"][0]["code"] == "single_node_concurrency_hard_limit"

    duplicate_child_ids = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            **plan_payload(
                scenario_id=scenario.json()["id"], env_group_id=env.json()["id"], node_id=node.id
            ),
            "scenarioItems": [
                plan_payload(
                    scenario_id=scenario.json()["id"],
                    env_group_id=env.json()["id"],
                    node_id=node.id,
                )["scenarioItems"][0],
                plan_payload(
                    scenario_id=scenario.json()["id"],
                    env_group_id=env.json()["id"],
                    node_id=node.id,
                )["scenarioItems"][0],
            ],
            "slaRules": [
                plan_payload(
                    scenario_id=scenario.json()["id"],
                    env_group_id=env.json()["id"],
                    node_id=node.id,
                )["slaRules"][0],
                plan_payload(
                    scenario_id=scenario.json()["id"],
                    env_group_id=env.json()["id"],
                    node_id=node.id,
                )["slaRules"][0],
            ],
        },
    )
    assert duplicate_child_ids.status_code == 422
    assert duplicate_child_ids.json()["code"] == "VALIDATION_ERROR"
    assert duplicate_child_ids.json()["details"] == [
        {
            "field": "scenarioItems[1].id",
            "code": "duplicate_child_id",
            "message": "Scenario item ID must be unique within the Test Plan.",
        },
        {
            "field": "slaRules[1].id",
            "code": "duplicate_child_id",
            "message": "SLA Rule ID must be unique within the Test Plan.",
        },
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

    stale = await client.patch(
        f"/api/v1/test-plans/{draft.json()['id']}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            **plan_payload(
                scenario_id=scenario.json()["id"], env_group_id=env.json()["id"], node_id=node.id
            ),
            "expectedRevision": 99,
        },
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "TEST_PLAN_REVISION_CONFLICT"

    patched = await client.patch(
        f"/api/v1/test-plans/{draft.json()['id']}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            **plan_payload(
                scenario_id=scenario.json()["id"], env_group_id=env.json()["id"], node_id=node.id
            ),
            "expectedRevision": 1,
        },
    )
    assert patched.status_code == 200
    detail = patched.json()
    assert detail["revision"] == 2
    assert detail["scenarioItems"][0]["scenarioName"] == "Checkout flow"
    assert detail["slaRules"][0]["threshold"]["unit"] == "ms"
    assert detail["runGuard"]["expectedConcurrencyPerNode"] == 10
    assert detail["runnable"] is True

    duplicate_child_ids_patch = await client.patch(
        f"/api/v1/test-plans/{detail['id']}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            **plan_payload(
                scenario_id=scenario.json()["id"], env_group_id=env.json()["id"], node_id=node.id
            ),
            "scenarioItems": [
                plan_payload(
                    scenario_id=scenario.json()["id"],
                    env_group_id=env.json()["id"],
                    node_id=node.id,
                )["scenarioItems"][0],
                plan_payload(
                    scenario_id=scenario.json()["id"],
                    env_group_id=env.json()["id"],
                    node_id=node.id,
                )["scenarioItems"][0],
            ],
            "slaRules": [
                plan_payload(
                    scenario_id=scenario.json()["id"],
                    env_group_id=env.json()["id"],
                    node_id=node.id,
                )["slaRules"][0],
                plan_payload(
                    scenario_id=scenario.json()["id"],
                    env_group_id=env.json()["id"],
                    node_id=node.id,
                )["slaRules"][0],
            ],
            "expectedRevision": detail["revision"],
        },
    )
    assert duplicate_child_ids_patch.status_code == 422
    assert duplicate_child_ids_patch.json()["code"] == "VALIDATION_ERROR"
    assert [item["field"] for item in duplicate_child_ids_patch.json()["details"]] == [
        "scenarioItems[1].id",
        "slaRules[1].id",
    ]

    listed = await client.get("/api/v1/test-plans", headers={"x-workspace-id": workspace_id})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["enabledScenarioItemCount"] == 1
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
        f"/api/v1/env-groups/{env.json()['id']}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
    )
    assert blocked_env_delete.status_code == 409
    assert blocked_env_delete.json()["code"] == "ENV_GROUP_IN_USE"

    blocked_scenario_delete = await client.delete(
        f"/api/v1/scenarios/{scenario.json()['id']}",
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
async def test_sla_label_must_match_the_final_generated_sampler_label(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "plan-sla-label@example.com")
    node = seed_idle_node(db_session, user_id=user_id, host_prefix="plan-sla-label-node")
    scenario = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(),
    )
    assert scenario.status_code == 201
    payload = plan_payload(scenario_id=scenario.json()["id"], env_group_id=None, node_id=node.id)
    item = payload["scenarioItems"][0]
    step = scenario_payload()["steps"][0]
    payload["slaRules"][0]["label"] = request_label(
        step["method"], step["path"], step["id"], item_id=item["id"]
    )

    created = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=payload,
    )

    assert created.status_code == 201
    assert created.json()["slaRules"][0]["label"] == payload["slaRules"][0]["label"]

    payload["expectedRevision"] = created.json()["revision"]
    payload["slaRules"][0]["label"] = "GET /v1/users"
    rejected_patch = await client.patch(
        f"/api/v1/test-plans/{created.json()['id']}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=payload,
    )
    assert rejected_patch.status_code == 422
    assert rejected_patch.json()["details"][0]["code"] == "unknown_sampler_label"


@pytest.mark.anyio
async def test_sla_label_rejects_unknown_sampler_and_normalizes_empty_value(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "plan-sla-invalid@example.com")
    node = seed_idle_node(db_session, user_id=user_id, host_prefix="plan-sla-invalid-node")
    scenario = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(),
    )
    assert scenario.status_code == 201
    payload = plan_payload(scenario_id=scenario.json()["id"], env_group_id=None, node_id=node.id)
    payload["slaRules"][0]["label"] = "GET /v1/users"

    rejected = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=payload,
    )

    assert rejected.status_code == 422
    assert rejected.json()["details"] == [
        {
            "field": "slaRules[0].label",
            "code": "unknown_sampler_label",
            "message": "SLA Rule label must match a generated sampler label.",
        }
    ]

    payload["slaRules"][0]["label"] = "   "
    created = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=payload,
    )
    assert created.status_code == 201
    assert created.json()["slaRules"][0]["label"] is None


@pytest.mark.anyio
async def test_test_plan_list_batches_preflight_inputs(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf, workspace_id, user_id = await register(client, "plan-list-batch@example.com")
    node = seed_idle_node(db_session, user_id=user_id)
    env = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "name": "Staging",
            "variables": {"base_url": {"type": "plain", "value": "https://api.example.internal"}},
        },
    )
    assert env.status_code == 201
    scenario = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(),
    )
    assert scenario.status_code == 201
    for index in range(3):
        payload = deepcopy(
            plan_payload(
                scenario_id=scenario.json()["id"],
                env_group_id=env.json()["id"],
                node_id=node.id,
            )
        )
        payload["name"] = f"Checkout Load Test {index}"
        payload["scenarioItems"][0]["id"] = new_ulid()
        payload["slaRules"][0]["id"] = new_ulid()
        created = await client.post(
            "/api/v1/test-plans",
            headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
            json=payload,
        )
        assert created.status_code == 201

    expected_rows, expected_total = test_plans_service.list_test_plans(
        db_session,
        workspace_id=workspace_id,
        page=1,
        page_size=3,
        search=None,
        tag=None,
        sort="name",
    )
    assert expected_total == 3
    expected_payloads = [
        test_plans_service.summary_payload(db_session, row) for row in expected_rows
    ]

    counters = {
        "effective_load_settings": 0,
        "get_settings": 0,
        "jmeter_memory_xmx": 0,
        "_env_for_plan": 0,
        "_node_for_plan": 0,
        "_enabled_dependency_files": 0,
    }

    def counted(name, original):
        def wrapper(*args, **kwargs):
            counters[name] += 1
            return original(*args, **kwargs)

        return wrapper

    monkeypatch.setattr(
        test_plans_service,
        "effective_load_settings",
        counted("effective_load_settings", test_plans_service.effective_load_settings),
    )
    monkeypatch.setattr(
        test_plans_service,
        "get_settings",
        counted("get_settings", test_plans_service.get_settings),
    )
    monkeypatch.setattr(
        test_plans_service,
        "jmeter_memory_xmx",
        counted("jmeter_memory_xmx", test_plans_service.jmeter_memory_xmx),
    )
    monkeypatch.setattr(
        test_plans_service,
        "_env_for_plan",
        counted("_env_for_plan", test_plans_service._env_for_plan),
    )
    monkeypatch.setattr(
        test_plans_service,
        "_node_for_plan",
        counted("_node_for_plan", test_plans_service._node_for_plan),
    )
    monkeypatch.setattr(
        test_plans_service,
        "_enabled_dependency_files",
        counted("_enabled_dependency_files", test_plans_service._enabled_dependency_files),
    )

    response = await client.get(
        "/api/v1/test-plans?pageSize=3&sort=name",
        headers={"x-workspace-id": workspace_id},
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["name"] for item in body["items"]] == [
        "Checkout Load Test 0",
        "Checkout Load Test 1",
        "Checkout Load Test 2",
    ]
    assert body["items"] == expected_payloads
    assert all(item["runnable"] is True for item in body["items"])
    assert all(item["notRunnableReasons"] == [] for item in body["items"])
    assert counters == {
        "effective_load_settings": 1,
        "get_settings": 1,
        "jmeter_memory_xmx": 1,
        "_env_for_plan": 0,
        "_node_for_plan": 0,
        "_enabled_dependency_files": 0,
    }


@pytest.mark.anyio
async def test_selected_node_without_pool_type_is_validated_before_node_lookup(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "plan-node-pool@example.com")
    node = seed_idle_node(db_session, user_id=user_id, host_prefix="plan-node-pool-node")

    for selected_node_id in (node.id, "01HZX3Y9M0E9W7Z6M5QK9S8P9Z"):
        response = await client.post(
            "/api/v1/test-plans",
            headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
            json={
                "name": "Draft plan",
                "description": None,
                "tags": [],
                "envGroupId": None,
                "runMode": "sequential",
                "resource": {"poolType": None, "selectedNodeId": selected_node_id},
                "scenarioItems": [],
                "slaRules": [],
            },
        )
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"
        assert response.json()["details"][0]["field"] == "resource.poolType"
        assert response.json()["details"][0]["code"] == "required_field"


@pytest.mark.anyio
async def test_env_group_in_use_reflects_test_plan_references_and_soft_deleted_fk(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "plan-env-use@example.com")
    node = seed_idle_node(db_session, user_id=user_id, host_prefix="plan-env-use-node")
    env = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "name": "Staging",
            "variables": {"base_url": {"type": "plain", "value": "https://api.example.internal"}},
        },
    )
    assert env.status_code == 201
    scenario = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(),
    )
    assert scenario.status_code == 201
    plan = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=plan_payload(
            scenario_id=scenario.json()["id"], env_group_id=env.json()["id"], node_id=node.id
        ),
    )
    assert plan.status_code == 201

    listed = await client.get("/api/v1/env-groups", headers={"x-workspace-id": workspace_id})
    assert listed.status_code == 200
    assert listed.json()["items"][0]["inUse"] is True
    detail = await client.get(
        f"/api/v1/env-groups/{env.json()['id']}", headers={"x-workspace-id": workspace_id}
    )
    assert detail.status_code == 200
    assert detail.json()["inUse"] is True

    delete_live_reference = await client.delete(
        f"/api/v1/env-groups/{env.json()['id']}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
    )
    assert delete_live_reference.status_code == 409
    assert delete_live_reference.json()["code"] == "ENV_GROUP_IN_USE"

    deleted_plan = await client.delete(
        f"/api/v1/test-plans/{plan.json()['id']}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
    )
    assert deleted_plan.status_code == 204
    delete_soft_deleted_reference = await client.delete(
        f"/api/v1/env-groups/{env.json()['id']}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
    )
    assert delete_soft_deleted_reference.status_code == 409
    assert delete_soft_deleted_reference.json()["code"] == "ENV_GROUP_IN_USE"


@pytest.mark.anyio
async def test_scenario_delete_ignores_archived_test_plan_reference(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "plan-scenario-use@example.com")
    node = seed_idle_node(db_session, user_id=user_id, host_prefix="plan-scenario-use-node")
    env = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "name": "Staging",
            "variables": {"base_url": {"type": "plain", "value": "https://api.example.internal"}},
        },
    )
    assert env.status_code == 201
    scenario = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(),
    )
    assert scenario.status_code == 201
    plan = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=plan_payload(
            scenario_id=scenario.json()["id"], env_group_id=env.json()["id"], node_id=node.id
        ),
    )
    assert plan.status_code == 201

    deleted_plan = await client.delete(
        f"/api/v1/test-plans/{plan.json()['id']}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
    )
    assert deleted_plan.status_code == 204

    delete_archived_reference = await client.delete(
        f"/api/v1/scenarios/{scenario.json()['id']}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
    )
    assert delete_archived_reference.status_code == 204


@pytest.mark.anyio
async def test_parallel_aggregate_hard_limit_marks_plan_not_runnable(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_SINGLE_NODE_CONCURRENCY_HARD_LIMIT", "15")
    csrf, workspace_id, user_id = await register(client, "plan-aggregate-hard@example.com")
    node = seed_idle_node(db_session, user_id=user_id, host_prefix="plan-aggregate-hard-node")
    env = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "name": "Staging",
            "variables": {"base_url": {"type": "plain", "value": "https://api.example.internal"}},
        },
    )
    assert env.status_code == 201
    scenario_one = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(name="Checkout flow", path="/v1/users"),
    )
    assert scenario_one.status_code == 201
    scenario_two = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(name="Search flow", path="/v1/search"),
    )
    assert scenario_two.status_code == 201
    first_item = plan_payload(
        scenario_id=scenario_one.json()["id"], env_group_id=env.json()["id"], node_id=node.id
    )["scenarioItems"][0]
    second_item = {
        **first_item,
        "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8C",
        "scenarioId": scenario_two.json()["id"],
        "order": 1,
    }
    created = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            **plan_payload(
                scenario_id=scenario_one.json()["id"],
                env_group_id=env.json()["id"],
                node_id=node.id,
            ),
            "runMode": "parallel",
            "scenarioItems": [first_item, second_item],
        },
    )
    assert created.status_code == 201

    detail = await client.get(
        f"/api/v1/test-plans/{created.json()['id']}", headers={"x-workspace-id": workspace_id}
    )
    assert detail.status_code == 200
    assert detail.json()["runGuard"]["expectedConcurrencyPerNode"] == 20
    assert detail.json()["runnable"] is False
    assert "single_node_concurrency_hard_limit" in detail.json()["notRunnableReasons"]
    listed = await client.get("/api/v1/test-plans", headers={"x-workspace-id": workspace_id})
    assert listed.status_code == 200
    assert listed.json()["items"][0]["runnable"] is False
    assert "single_node_concurrency_hard_limit" in listed.json()["items"][0]["notRunnableReasons"]

    run_now = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "runType": "standard",
            "sourceType": "test_plan",
            "sourceId": created.json()["id"],
            "expectedSourceRevision": created.json()["revision"],
            "confirmHighConcurrency": True,
        },
    )
    assert run_now.status_code == 422
    assert run_now.json()["code"] == "VALIDATION_ERROR"
    assert run_now.json()["details"][0]["code"] == "single_node_concurrency_hard_limit"
    assert db_session.query(NodeLease).filter_by(node_id=node.id, released_at=None).count() == 0


@pytest.mark.anyio
async def test_test_plan_guardrails_use_db_backed_system_settings(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "plan-db-policy@example.com")
    node = seed_idle_node(db_session, user_id=user_id, host_prefix="plan-db-policy-node")
    env = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "name": "Staging",
            "variables": {"base_url": {"type": "plain", "value": "https://api.example.internal"}},
        },
    )
    assert env.status_code == 201
    scenario_one = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(name="First flow", path="/v1/first"),
    )
    scenario_two = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(name="Second flow", path="/v1/second"),
    )
    assert scenario_one.status_code == 201
    assert scenario_two.status_code == 201

    settings = await client.patch(
        "/api/v1/admin/system-settings",
        headers={"x-csrf-token": csrf},
        json={
            "loadSoftLimitWarningConcurrency": 5,
            "maxScenarioItemsPerTestPlan": 1,
        },
    )
    assert settings.status_code == 200

    first_item = plan_payload(
        scenario_id=scenario_one.json()["id"], env_group_id=env.json()["id"], node_id=node.id
    )["scenarioItems"][0]
    second_item = {
        **first_item,
        "id": "01HZX3Y9M0E9W7Z6M5QK9S8P9C",
        "scenarioId": scenario_two.json()["id"],
        "order": 1,
    }
    too_many = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            **plan_payload(
                scenario_id=scenario_one.json()["id"],
                env_group_id=env.json()["id"],
                node_id=node.id,
            ),
            "scenarioItems": [first_item, second_item],
        },
    )
    assert too_many.status_code == 422
    assert too_many.json()["details"][0]["code"] == "too_many_scenarios"

    plan = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=plan_payload(
            scenario_id=scenario_one.json()["id"], env_group_id=env.json()["id"], node_id=node.id
        ),
    )
    assert plan.status_code == 201
    assert plan.json()["runGuard"]["softConcurrencyPerNodeLimit"] == 5
    assert plan.json()["runGuard"]["requiresHighConcurrencyConfirmation"] is True

    unconfirmed = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "runType": "standard",
            "sourceType": "test_plan",
            "sourceId": plan.json()["id"],
            "expectedSourceRevision": plan.json()["revision"],
            "confirmHighConcurrency": False,
        },
    )
    assert unconfirmed.status_code == 409
    assert unconfirmed.json()["code"] == "LOAD_SOFT_LIMIT_CONFIRMATION_REQUIRED"
    assert unconfirmed.json()["details"][0]["meta"]["softLimit"] == 5


@pytest.mark.anyio
async def test_scenario_items_are_persisted_by_explicit_order(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "plan-order@example.com")
    node = seed_idle_node(db_session, user_id=user_id, host_prefix="plan-order-node")
    env = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "name": "Staging",
            "variables": {"base_url": {"type": "plain", "value": "https://api.example.internal"}},
        },
    )
    assert env.status_code == 201
    scenario_one = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(name="First flow", path="/v1/first"),
    )
    assert scenario_one.status_code == 201
    scenario_two = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(name="Second flow", path="/v1/second"),
    )
    assert scenario_two.status_code == 201
    first_item = {
        **plan_payload(
            scenario_id=scenario_one.json()["id"], env_group_id=env.json()["id"], node_id=node.id
        )["scenarioItems"][0],
        "order": 1,
    }
    second_item = {
        **first_item,
        "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8C",
        "scenarioId": scenario_two.json()["id"],
        "order": 0,
    }

    created = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            **plan_payload(
                scenario_id=scenario_one.json()["id"],
                env_group_id=env.json()["id"],
                node_id=node.id,
            ),
            "scenarioItems": [first_item, second_item],
        },
    )
    assert created.status_code == 201

    assert [item["scenarioId"] for item in created.json()["scenarioItems"]] == [
        scenario_two.json()["id"],
        scenario_one.json()["id"],
    ]
    assert [item["order"] for item in created.json()["scenarioItems"]] == [0, 1]


@pytest.mark.anyio
async def test_over_configured_scenario_count_marks_plan_not_runnable(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "plan-scenario-count@example.com")
    node = seed_idle_node(db_session, user_id=user_id, host_prefix="plan-scenario-count-node")
    env = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "name": "Staging",
            "variables": {"base_url": {"type": "plain", "value": "https://api.example.internal"}},
        },
    )
    assert env.status_code == 201
    scenario_one = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(name="Checkout flow", path="/v1/users"),
    )
    assert scenario_one.status_code == 201
    scenario_two = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(name="Search flow", path="/v1/search"),
    )
    assert scenario_two.status_code == 201
    first_item = plan_payload(
        scenario_id=scenario_one.json()["id"], env_group_id=env.json()["id"], node_id=node.id
    )["scenarioItems"][0]
    second_item = {
        **first_item,
        "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8C",
        "scenarioId": scenario_two.json()["id"],
        "order": 1,
    }
    created = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            **plan_payload(
                scenario_id=scenario_one.json()["id"],
                env_group_id=env.json()["id"],
                node_id=node.id,
            ),
            "scenarioItems": [first_item, second_item],
        },
    )
    assert created.status_code == 201

    lowered_limit = await client.patch(
        "/api/v1/admin/system-settings",
        headers={"x-csrf-token": csrf},
        json={"maxScenarioItemsPerTestPlan": 1},
    )
    assert lowered_limit.status_code == 200

    detail = await client.get(
        f"/api/v1/test-plans/{created.json()['id']}", headers={"x-workspace-id": workspace_id}
    )
    assert detail.status_code == 200
    assert detail.json()["runnable"] is False
    assert "too_many_scenarios" in detail.json()["notRunnableReasons"]
    listed = await client.get("/api/v1/test-plans", headers={"x-workspace-id": workspace_id})
    assert listed.status_code == 200
    assert listed.json()["items"][0]["runnable"] is False
    assert "too_many_scenarios" in listed.json()["items"][0]["notRunnableReasons"]

    run_now = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "runType": "standard",
            "sourceType": "test_plan",
            "sourceId": created.json()["id"],
            "expectedSourceRevision": created.json()["revision"],
            "confirmHighConcurrency": True,
        },
    )
    assert run_now.status_code == 422
    assert run_now.json()["code"] == "VALIDATION_ERROR"
    assert run_now.json()["details"][0]["code"] == "too_many_scenarios"
    assert db_session.query(NodeLease).filter_by(node_id=node.id, released_at=None).count() == 0


@pytest.mark.anyio
async def test_over_configured_sla_count_marks_plan_not_runnable_before_run(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf, workspace_id, user_id = await register(client, "plan-sla-count@example.com")
    node = seed_idle_node(db_session, user_id=user_id, host_prefix="plan-sla-count-node")
    env = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "name": "Staging",
            "variables": {"base_url": {"type": "plain", "value": "https://api.example.internal"}},
        },
    )
    assert env.status_code == 201
    scenario = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(),
    )
    assert scenario.status_code == 201
    base = plan_payload(
        scenario_id=scenario.json()["id"], env_group_id=env.json()["id"], node_id=node.id
    )
    second_rule = {
        **base["slaRules"][0],
        "id": "01HZX3Y9M0E9W7Z6M5QK9S8P8E",
        "subject": "p99",
    }
    created = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={**base, "slaRules": [base["slaRules"][0], second_rule]},
    )
    assert created.status_code == 201

    monkeypatch.setenv("SURGEPILOT_MAX_SLA_RULES_PER_TEST_PLAN", "1")
    detail = await client.get(
        f"/api/v1/test-plans/{created.json()['id']}", headers={"x-workspace-id": workspace_id}
    )
    assert detail.status_code == 200
    assert detail.json()["runnable"] is False
    assert "too_many_sla_rules" in detail.json()["notRunnableReasons"]
    listed = await client.get("/api/v1/test-plans", headers={"x-workspace-id": workspace_id})
    assert listed.status_code == 200
    assert listed.json()["items"][0]["runnable"] is False
    assert "too_many_sla_rules" in listed.json()["items"][0]["notRunnableReasons"]

    run_now = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "runType": "standard",
            "sourceType": "test_plan",
            "sourceId": created.json()["id"],
            "expectedSourceRevision": created.json()["revision"],
            "confirmHighConcurrency": True,
        },
    )
    assert run_now.status_code == 422
    assert run_now.json()["code"] == "VALIDATION_ERROR"
    assert run_now.json()["details"][0]["code"] == "too_many_sla_rules"
    assert db_session.query(NodeLease).filter_by(node_id=node.id, released_at=None).count() == 0

    debug = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "runType": "debug",
            "sourceType": "test_plan",
            "sourceId": created.json()["id"],
            "expectedSourceRevision": created.json()["revision"],
        },
    )
    assert debug.status_code == 201
    debug_snapshot = db_session.scalar(
        select(RunSnapshot).where(RunSnapshot.run_id == debug.json()["id"])
    )
    assert debug_snapshot is not None
    assert debug_snapshot.snapshot_json["slaEvaluationMode"] == "not_evaluated"


@pytest.mark.anyio
async def test_test_plan_run_now_debug_snapshot_dedup_and_guards(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_SINGLE_NODE_CONCURRENCY_SOFT_LIMIT", "5")
    monkeypatch.setenv("SURGEPILOT_SINGLE_NODE_CONCURRENCY_HARD_LIMIT", "100")
    csrf, workspace_id, user_id = await register(client, "plan-run@example.com")
    node = seed_idle_node(db_session, user_id=user_id, host_prefix="plan-run-node")
    env = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "name": "Staging",
            "variables": {"base_url": {"type": "plain", "value": "https://api.example.internal"}},
        },
    )
    scenario = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(),
    )
    plan = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=plan_payload(
            scenario_id=scenario.json()["id"], env_group_id=env.json()["id"], node_id=node.id
        ),
    )
    assert plan.status_code == 201
    override = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "runType": "standard",
            "sourceType": "test_plan",
            "sourceId": plan.json()["id"],
            "expectedSourceRevision": plan.json()["revision"],
            "selectedNodeId": node.id,
            "confirmHighConcurrency": True,
        },
    )
    assert override.status_code == 422
    assert override.json()["code"] == "VALIDATION_ERROR"

    unconfirmed = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "runType": "standard",
            "sourceType": "test_plan",
            "sourceId": plan.json()["id"],
            "expectedSourceRevision": plan.json()["revision"],
            "confirmHighConcurrency": False,
        },
    )
    assert unconfirmed.status_code == 409
    assert unconfirmed.json()["code"] == "LOAD_SOFT_LIMIT_CONFIRMATION_REQUIRED"
    assert unconfirmed.json()["details"][0]["meta"]["expectedConcurrencyPerNode"] == 10

    created = await client.post(
        "/api/v1/runs",
        headers={
            "x-csrf-token": csrf,
            "x-workspace-id": workspace_id,
            "user-agent": "SurgePilotTest/1.0",
        },
        json={
            "runType": "standard",
            "sourceType": "test_plan",
            "sourceId": plan.json()["id"],
            "expectedSourceRevision": plan.json()["revision"],
            "confirmHighConcurrency": True,
        },
    )
    assert created.status_code == 201
    run_body = created.json()
    assert run_body["runType"] == "standard"
    assert run_body["sourceType"] == "test_plan"
    assert run_body["validity"] == "valid"

    run = db_session.get(Run, run_body["id"])
    assert run is not None
    snapshot = db_session.scalar(select(RunSnapshot).where(RunSnapshot.run_id == run.id))
    assert snapshot is not None
    payload = snapshot.snapshot_json
    assert payload["testPlan"]["id"] == plan.json()["id"]
    assert payload["scenarioItems"][0]["scenarioRevision"] == scenario.json()["revision"]
    assert payload["envGroup"]["variables"] == {"base_url": "https://api.example.internal"}
    assert payload["resourceRequest"]["selectedNodeId"] == node.id
    assert payload["slaEvaluationMode"] == "passfail"
    assert payload["generatedYaml"]["artifactRelativePath"] == "execution/generated.yml"
    serialized = str(payload)
    assert "storageObjectKey" not in serialized
    assert "runner-token" not in serialized.lower()
    assert db_session.scalar(select(NodeLease).where(NodeLease.run_id == run.id)) is not None
    standard_audit = db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.event_type == "run.standard_requested",
            AuditEvent.target_id == run.id,
        )
    )
    assert standard_audit is not None
    assert standard_audit.request_id == created.headers["x-request-id"]
    assert standard_audit.ip_address is not None
    assert standard_audit.user_agent == "SurgePilotTest/1.0"

    duplicate = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "runType": "standard",
            "sourceType": "test_plan",
            "sourceId": plan.json()["id"],
            "expectedSourceRevision": plan.json()["revision"],
            "confirmHighConcurrency": True,
        },
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["id"] == run.id
    assert duplicate.json()["deduplicated"] is True
    assert db_session.query(NodeLease).filter_by(node_id=node.id, released_at=None).count() == 1

    stale = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "runType": "debug",
            "sourceType": "test_plan",
            "sourceId": plan.json()["id"],
            "expectedSourceRevision": 99,
        },
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "TEST_PLAN_REVISION_CONFLICT"

    # Release the first run so a Debug Run can reuse the same node through the real lease flow.
    lease = db_session.scalar(select(NodeLease).where(NodeLease.run_id == run.id))
    assert lease is not None
    lease.released_at = datetime.now(UTC)
    node.status = "idle"
    node.current_run_id = None
    db_session.flush()

    debug = await client.post(
        "/api/v1/runs",
        headers={
            "x-csrf-token": csrf,
            "x-workspace-id": workspace_id,
            "user-agent": "SurgePilotTest/1.0",
        },
        json={
            "runType": "debug",
            "sourceType": "test_plan",
            "sourceId": plan.json()["id"],
            "expectedSourceRevision": plan.json()["revision"],
        },
    )
    assert debug.status_code == 201
    debug_run = db_session.get(Run, debug.json()["id"])
    assert debug_run is not None
    debug_snapshot = db_session.scalar(
        select(RunSnapshot).where(RunSnapshot.run_id == debug_run.id)
    )
    assert debug_snapshot is not None
    assert debug_snapshot.snapshot_json["runType"] == "debug"
    assert debug_snapshot.snapshot_json["validityDefault"] == "invalid"
    assert debug_snapshot.snapshot_json["slaEvaluationMode"] == "not_evaluated"
    assert debug_snapshot.snapshot_json["scenarioItems"][0]["loadSettings"] == {
        "concurrencyPerNode": 1,
        "rampUpSeconds": 0,
        "holdForSeconds": None,
        "iterations": 1,
        "targetRps": None,
        "steps": None,
        "delaySeconds": 0,
    }
    debug_audit = db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.event_type == "run.debug_requested",
            AuditEvent.target_id == debug_run.id,
        )
    )
    assert debug_audit is not None
    assert debug_audit.request_id == debug.headers["x-request-id"]
    assert debug_audit.ip_address is not None
    assert debug_audit.user_agent == "SurgePilotTest/1.0"


@pytest.mark.anyio
async def test_test_plan_debug_ignores_saved_standard_concurrency_hard_limit(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_SINGLE_NODE_CONCURRENCY_HARD_LIMIT", "100")
    csrf, workspace_id, user_id = await register(client, "plan-debug-hard-limit@example.com")
    node = seed_idle_node(db_session, user_id=user_id, host_prefix="plan-debug-hard-limit-node")
    env = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "name": "Staging",
            "variables": {"base_url": {"type": "plain", "value": "https://api.example.internal"}},
        },
    )
    assert env.status_code == 201
    scenario = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(),
    )
    assert scenario.status_code == 201
    plan = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=plan_payload(
            scenario_id=scenario.json()["id"], env_group_id=env.json()["id"], node_id=node.id
        ),
    )
    assert plan.status_code == 201

    monkeypatch.setenv("SURGEPILOT_SINGLE_NODE_CONCURRENCY_HARD_LIMIT", "5")
    detail_after_limit_change = await client.get(
        f"/api/v1/test-plans/{plan.json()['id']}", headers={"x-workspace-id": workspace_id}
    )
    assert detail_after_limit_change.status_code == 200
    assert detail_after_limit_change.json()["runnable"] is False
    assert (
        "single_node_concurrency_hard_limit"
        in detail_after_limit_change.json()["notRunnableReasons"]
    )

    debug = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "runType": "debug",
            "sourceType": "test_plan",
            "sourceId": plan.json()["id"],
            "expectedSourceRevision": plan.json()["revision"],
        },
    )

    assert debug.status_code == 201
    snapshot = db_session.scalar(
        select(RunSnapshot).where(RunSnapshot.run_id == debug.json()["id"])
    )
    assert snapshot is not None
    assert snapshot.snapshot_json["runType"] == "debug"
    assert snapshot.snapshot_json["testPlan"]["runMode"] == "sequential"
    assert snapshot.snapshot_json["scenarioItems"][0]["loadSettings"]["concurrencyPerNode"] == 1
    assert snapshot.snapshot_json["scenarioItems"][0]["loadSettings"]["iterations"] == 1


@pytest.mark.anyio
async def test_test_plan_workspace_isolation_and_missing_variable_validation(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "plan-isolation@example.com")
    node = seed_idle_node(db_session, user_id=user_id, host_prefix="plan-isolation-node")
    scenario = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(),
    )
    plan = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=plan_payload(scenario_id=scenario.json()["id"], env_group_id=None, node_id=node.id),
    )
    assert plan.status_code == 201
    assert plan.json()["runnable"] is False
    assert "missing_variables" in plan.json()["notRunnableReasons"]
    listed = await client.get("/api/v1/test-plans", headers={"x-workspace-id": workspace_id})
    assert listed.status_code == 200
    assert listed.json()["items"][0]["runnable"] is False

    missing_var = await client.post(
        "/api/v1/runs",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "runType": "standard",
            "sourceType": "test_plan",
            "sourceId": plan.json()["id"],
            "expectedSourceRevision": plan.json()["revision"],
            "confirmHighConcurrency": True,
        },
    )
    assert missing_var.status_code == 422
    assert missing_var.json()["code"] == "VALIDATION_ERROR"
    assert missing_var.json()["details"][0]["code"] == "missing_variable"

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

    cross_workspace = await client.get(
        f"/api/v1/test-plans/{plan.json()['id']}", headers={"x-workspace-id": other.id}
    )
    assert cross_workspace.status_code == 404
