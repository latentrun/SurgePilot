from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ids import new_ulid
from app.models.auth import DEFAULT_WORKSPACE_ID, User
from app.models.dependency_files import DependencyFile
from app.models.load_nodes import LoadNode
from app.models.runs import NodeLease, Run, RunSnapshot
from app.models.scenarios import RunCreationDedupKey, Scenario, ScenarioDependencyFileRef
from app.models.test_plans import (
    TestPlan as TestPlanModel,
    TestPlanScenarioItem as TestPlanScenarioItemModel,
    TestPlanSlaRule as TestPlanSlaRuleModel,
)
from app.schemas.load_nodes import LoadNodeCredentialInput
from app.services.load_nodes import create_load_node

TestPlanModel.__test__ = False
TestPlanScenarioItemModel.__test__ = False
TestPlanSlaRuleModel.__test__ = False


def trusted_host_key() -> dict[str, str]:
    return {
        "algorithm": "ssh-ed25519",
        "publicKey": "AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC",
        "fingerprintSha256": "SHA256:SurgePilotTrustedHostKey",
    }


async def register(client: AsyncClient, email: str) -> tuple[str, str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "displayName": "P1 Polish User", "password": "password123"},
    )
    assert response.status_code == 201
    body = response.json()
    return body["csrfToken"], body["defaultWorkspace"]["id"], body["user"]["id"]


def scenario_payload(
    name: str = "Checkout flow",
    *,
    base_url_expression: str = "https://example.test",
    dependency_file_id: str | None = None,
) -> dict:
    data_sources = []
    if dependency_file_id:
        data_sources.append(
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7D",
                "dependencyFileId": dependency_file_id,
                "displayName": "users.csv",
                "delimiter": ",",
                "quoted": None,
                "loop": True,
                "variableNames": ["user_id"],
                "randomOrder": False,
                "enabled": True,
            }
        )
    return {
        "name": name,
        "description": "Critical checkout APIs",
        "tags": [" checkout ", "smoke", "checkout"],
        "baseUrlExpression": base_url_expression,
        "defaultSettings": {
            "thinkTimeMs": 0,
            "timeoutMs": 30000,
            "followRedirects": True,
            "keepAlive": True,
            "storeCache": True,
            "storeCookie": True,
            "retrieveResources": False,
        },
        "dataSources": data_sources,
        "steps": [
            {
                "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7A",
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
                        "id": "01HZX3Y9M0E9W7Z6M5QK9S8P7B",
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


def plan_payload(*, scenario_id: str, env_group_id: str | None, node_id: str) -> dict:
    return {
        "name": "Checkout Load Test",
        "description": "Checkout flow baseline",
        "tags": ["baseline", "checkout"],
        "envGroupId": env_group_id,
        "runMode": "sequential",
        "resource": {"poolType": "private", "selectedNodeId": node_id},
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
                "label": "",
                "condition": "gt",
                "threshold": {"value": 500, "unit": "ms"},
                "timeframeLogic": "for",
                "timeframeSeconds": 10,
                "action": "continue",
            }
        ],
    }


def seed_dependency_file(db_session: Session, *, user_id: str) -> DependencyFile:
    now = datetime.now(UTC)
    file = DependencyFile(
        id=new_ulid(),
        workspace_id=DEFAULT_WORKSPACE_ID,
        filename="users.csv",
        content_type="text/csv",
        size_bytes=42,
        sha256="0" * 64,
        storage_bucket="surgepilot",
        storage_object_key="dependency-files/test/users.csv",
        status="available",
        created_by=user_id,
        created_at=now,
        deleted_at=None,
        deleted_by=None,
    )
    db_session.add(file)
    db_session.flush()
    return file


def seed_idle_node(db_session: Session, *, user_id: str) -> LoadNode:
    user = db_session.get(User, user_id)
    assert user is not None
    node = create_load_node(
        db_session,
        actor=user,
        workspace_id=DEFAULT_WORKSPACE_ID,
        scope="workspace",
        host=f"p1-polish-node-{user_id.lower()}.internal",
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        credential=LoadNodeCredentialInput(authType="password", password="secret-password"),
        ssh_host_key=trusted_host_key(),
        maintainer=None,
        remark=None,
    )
    node.status = "busy"
    db_session.flush()
    return node


async def create_env_group(client: AsyncClient, *, csrf: str, workspace_id: str) -> str:
    response = await client.post(
        "/api/v1/env-groups",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            "name": "Staging",
            "description": None,
            "variables": {
                "base_url": {"type": "plain", "value": "https://secret-env.example.test"}
            },
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.anyio
async def test_scenario_clone_archive_and_removed_preview_are_workspace_safe(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "p1-scenario-polish@example.com")
    dependency_file = seed_dependency_file(db_session, user_id=user_id)

    created = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(dependency_file_id=dependency_file.id),
    )
    assert created.status_code == 201
    source = created.json()

    clone = await client.post(
        f"/api/v1/scenarios/{source['id']}/clone",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={},
    )
    assert clone.status_code == 201
    cloned = clone.json()
    assert cloned["id"] != source["id"]
    assert cloned["name"] == "Copy of Checkout flow"
    assert cloned["revision"] == 1
    assert cloned["tags"] == ["checkout", "smoke"]
    assert cloned["dataSources"] == source["dataSources"]
    assert db_session.scalar(select(Scenario).where(Scenario.id == source["id"])).revision == 1
    clone_refs = db_session.scalars(
        select(ScenarioDependencyFileRef).where(
            ScenarioDependencyFileRef.scenario_id == cloned["id"]
        )
    ).all()
    assert [ref.dependency_file_id for ref in clone_refs] == [dependency_file.id]

    removed_preview = await client.get(
        f"/api/v1/scenarios/{source['id']}/execution-preview",
        headers={"x-workspace-id": workspace_id},
        params={"profile": "debug"},
    )
    assert removed_preview.status_code == 404
    assert db_session.scalar(select(Run).where(Run.source_id == source["id"])) is None
    assert db_session.scalar(select(RunSnapshot)) is None
    assert db_session.scalar(select(RunCreationDedupKey)) is None
    assert db_session.scalar(select(NodeLease)) is None

    archived = await client.delete(
        f"/api/v1/scenarios/{source['id']}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
    )
    assert archived.status_code == 204
    assert db_session.get(Scenario, source["id"]).deleted_at is not None
    assert (
        await client.get(
            f"/api/v1/scenarios/{source['id']}", headers={"x-workspace-id": workspace_id}
        )
    ).status_code == 404
    assert (
        await client.post(
            f"/api/v1/scenarios/{source['id']}/clone",
            headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
            json={},
        )
    ).status_code == 404
    assert (
        await client.get(
            f"/api/v1/scenarios/{source['id']}/execution-preview",
            headers={"x-workspace-id": workspace_id},
            params={"profile": "debug"},
        )
    ).status_code == 404


@pytest.mark.anyio
async def test_scenario_clone_default_name_is_validated_without_side_effect(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, _user_id = await register(client, "p1-scenario-long-clone@example.com")
    long_name = "S" * 118
    created = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(name=long_name),
    )
    assert created.status_code == 201

    clone = await client.post(
        f"/api/v1/scenarios/{created.json()['id']}/clone",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={},
    )

    assert clone.status_code == 422
    assert clone.json()["code"] == "VALIDATION_ERROR"
    assert (
        db_session.scalar(select(Scenario.id).where(Scenario.name == f"Copy of {long_name}"))
        is None
    )


@pytest.mark.anyio
async def test_clone_explicit_blank_name_is_rejected_without_defaulting(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "p1-clone-blank-name@example.com")
    env_group_id = await create_env_group(client, csrf=csrf, workspace_id=workspace_id)
    node = seed_idle_node(db_session, user_id=user_id)
    scenario = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(base_url_expression="${base_url}"),
    )
    assert scenario.status_code == 201
    plan = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=plan_payload(
            scenario_id=scenario.json()["id"], env_group_id=env_group_id, node_id=node.id
        ),
    )
    assert plan.status_code == 201

    scenario_clone = await client.post(
        f"/api/v1/scenarios/{scenario.json()['id']}/clone",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={"name": "   "},
    )
    assert scenario_clone.status_code == 422
    assert scenario_clone.json()["code"] == "VALIDATION_ERROR"

    plan_clone = await client.post(
        f"/api/v1/test-plans/{plan.json()['id']}/clone",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={"name": "   "},
    )
    assert plan_clone.status_code == 422
    assert plan_clone.json()["code"] == "VALIDATION_ERROR"

    assert (
        db_session.scalar(select(Scenario.id).where(Scenario.name == "Copy of Checkout flow"))
        is None
    )
    assert (
        db_session.scalar(
            select(TestPlanModel.id).where(TestPlanModel.name == "Copy of Checkout Load Test")
        )
        is None
    )


@pytest.mark.anyio
async def test_test_plan_clone_regenerates_child_rows_and_archive_hides_source(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "p1-plan-polish@example.com")
    env_group_id = await create_env_group(client, csrf=csrf, workspace_id=workspace_id)
    node = seed_idle_node(db_session, user_id=user_id)
    scenario = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(base_url_expression="${base_url}"),
    )
    assert scenario.status_code == 201
    plan = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=plan_payload(
            scenario_id=scenario.json()["id"], env_group_id=env_group_id, node_id=node.id
        ),
    )
    assert plan.status_code == 201
    source = plan.json()

    visible_reference_archive = await client.delete(
        f"/api/v1/scenarios/{scenario.json()['id']}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
    )
    assert visible_reference_archive.status_code == 409
    assert visible_reference_archive.json()["code"] == "RESOURCE_IN_USE"

    clone = await client.post(
        f"/api/v1/test-plans/{source['id']}/clone",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={"name": "Copied load test"},
    )
    assert clone.status_code == 201
    cloned = clone.json()
    assert cloned["id"] != source["id"]
    assert cloned["name"] == "Copied load test"
    assert cloned["revision"] == 1
    assert cloned["scenarioItems"][0]["scenarioId"] == scenario.json()["id"]
    assert cloned["scenarioItems"][0]["id"] != source["scenarioItems"][0]["id"]
    assert cloned["slaRules"][0]["id"] != source["slaRules"][0]["id"]
    assert (
        db_session.scalar(select(TestPlanModel).where(TestPlanModel.id == source["id"])).revision
        == 1
    )

    archived = await client.delete(
        f"/api/v1/test-plans/{source['id']}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
    )
    assert archived.status_code == 204
    assert db_session.get(TestPlanModel, source["id"]).deleted_at is not None
    assert (
        await client.get(
            f"/api/v1/test-plans/{source['id']}", headers={"x-workspace-id": workspace_id}
        )
    ).status_code == 404
    assert (
        await client.post(
            f"/api/v1/test-plans/{source['id']}/clone",
            headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
            json={},
        )
    ).status_code == 404

    archived_clone = await client.delete(
        f"/api/v1/test-plans/{cloned['id']}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
    )
    assert archived_clone.status_code == 204

    scenario_archive = await client.delete(
        f"/api/v1/scenarios/{scenario.json()['id']}",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
    )
    assert scenario_archive.status_code == 204


@pytest.mark.anyio
async def test_test_plan_clone_default_name_is_validated_without_side_effect(
    client: AsyncClient, db_session: Session
) -> None:
    csrf, workspace_id, user_id = await register(client, "p1-plan-long-clone@example.com")
    env_group_id = await create_env_group(client, csrf=csrf, workspace_id=workspace_id)
    node = seed_idle_node(db_session, user_id=user_id)
    scenario = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=scenario_payload(base_url_expression="${base_url}"),
    )
    assert scenario.status_code == 201
    long_name = "T" * 118
    plan = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={
            **plan_payload(
                scenario_id=scenario.json()["id"], env_group_id=env_group_id, node_id=node.id
            ),
            "name": long_name,
        },
    )
    assert plan.status_code == 201

    clone = await client.post(
        f"/api/v1/test-plans/{plan.json()['id']}/clone",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json={},
    )

    assert clone.status_code == 422
    assert clone.json()["code"] == "VALIDATION_ERROR"
    assert (
        db_session.scalar(
            select(TestPlanModel.id).where(TestPlanModel.name == f"Copy of {long_name}")
        )
        is None
    )


@pytest.mark.anyio
async def test_test_plan_preview_is_read_only_safe_and_reports_static_warnings(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_SINGLE_NODE_CONCURRENCY_SOFT_LIMIT", "5")
    csrf, workspace_id, user_id = await register(client, "p1-plan-preview@example.com")
    env_group_id = await create_env_group(client, csrf=csrf, workspace_id=workspace_id)
    node = seed_idle_node(db_session, user_id=user_id)
    preview_scenario_payload = scenario_payload(base_url_expression="${base_url}")
    scenario = await client.post(
        "/api/v1/scenarios",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=preview_scenario_payload,
    )
    assert scenario.status_code == 201
    plan = await client.post(
        "/api/v1/test-plans",
        headers={"x-csrf-token": csrf, "x-workspace-id": workspace_id},
        json=plan_payload(
            scenario_id=scenario.json()["id"], env_group_id=env_group_id, node_id=node.id
        ),
    )
    assert plan.status_code == 201
    plan_id = plan.json()["id"]

    missing_run_type = await client.get(
        f"/api/v1/test-plans/{plan_id}/execution-preview",
        headers={"x-workspace-id": workspace_id},
    )
    assert missing_run_type.status_code == 400
    assert missing_run_type.json()["code"] == "INVALID_EXECUTION_PREVIEW_MODE"
    assert missing_run_type.json()["details"][0]["field"] == "runType"

    standard_preview = await client.get(
        f"/api/v1/test-plans/{plan_id}/execution-preview",
        headers={"x-workspace-id": workspace_id},
        params={"runType": "standard"},
    )
    assert standard_preview.status_code == 200, standard_preview.text
    body = standard_preview.json()
    assert body["sourceType"] == "test_plan"
    assert body["mode"] == "standard"
    assert "soft_limit_exceeded" in {warning["code"] for warning in body["warnings"]}
    assert "passfail" in body["content"]
    assert "https://secret-env.example.test" not in body["content"]
    assert "/opt/surgepilot" not in body["content"]
    assert "env_value_redacted" in {warning["code"] for warning in body["warnings"]}

    debug_preview = await client.get(
        f"/api/v1/test-plans/{plan_id}/execution-preview",
        headers={"x-workspace-id": workspace_id},
        params={"runType": "debug"},
    )
    assert debug_preview.status_code == 200
    assert debug_preview.json()["mode"] == "debug"
    assert "passfail" not in debug_preview.json()["content"]

    invalid = await client.get(
        f"/api/v1/test-plans/{plan_id}/execution-preview",
        headers={"x-workspace-id": workspace_id},
        params={"runType": "load"},
    )
    assert invalid.status_code == 400
    assert invalid.json()["code"] == "INVALID_EXECUTION_PREVIEW_MODE"
    assert invalid.json()["details"][0]["field"] == "runType"

    assert db_session.scalar(select(Run).where(Run.source_id == plan_id)) is None
    assert db_session.scalar(select(RunSnapshot)) is None
    assert db_session.scalar(select(RunCreationDedupKey)) is None
    assert db_session.scalar(select(NodeLease)) is None
    assert (
        db_session.scalar(
            select(TestPlanScenarioItemModel).where(
                TestPlanScenarioItemModel.test_plan_id == plan_id
            )
        )
        is not None
    )
    assert (
        db_session.scalar(
            select(TestPlanSlaRuleModel).where(TestPlanSlaRuleModel.test_plan_id == plan_id)
        )
        is not None
    )
