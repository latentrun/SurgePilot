from datetime import UTC, datetime, timedelta
import json

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.ids import new_ulid
from app.models.auth import DEFAULT_WORKSPACE_ID, AuditEvent, User, Workspace, WorkspaceMember
from app.models.load_nodes import LoadNode
from app.models.runs import Run, RunArtifact, RunSnapshot
from app.services.overview import get_overview

OTHER_WORKSPACE_ID = "01HZX3Y9M0E9W7Z6M5QK9S8P7W"


async def register(
    client: AsyncClient, email: str, display_name: str = "Overview User"
) -> tuple[str, str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "displayName": display_name, "password": "password123"},
    )
    assert response.status_code == 201
    body = response.json()
    return body["csrfToken"], body["defaultWorkspace"]["id"], body["user"]["id"]


def seed_node(
    db: Session,
    *,
    user_id: str,
    node_id: str | None = None,
    workspace_id: str | None = DEFAULT_WORKSPACE_ID,
    scope: str = "workspace",
    status: str = "idle",
    archived: bool = False,
) -> LoadNode:
    now = datetime.now(UTC)
    node = LoadNode(
        id=node_id or new_ulid(),
        scope=scope,
        workspace_id=workspace_id if scope == "workspace" else None,
        host=f"node-{(node_id or new_ulid())[-6:].lower()}.internal",
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        auth_type="password",
        maintainer=None,
        remark=None,
        status=status,
        last_status_reason=None,
        runner_version=None,
        bundle_version=None,
        last_checked_at=now,
        last_heartbeat_at=now,
        created_by=user_id,
        updated_by=None,
        archived_by=user_id if archived else None,
        archived_at=now if archived else None,
        created_at=now,
        updated_at=now,
    )
    db.add(node)
    db.flush()
    return node


def seed_run(
    db: Session,
    *,
    user_id: str,
    node: LoadNode,
    workspace_id: str = DEFAULT_WORKSPACE_ID,
    run_type: str = "standard",
    state: str = "finished",
    validity: str | None = "valid",
    sla_result: str = "passed",
    source_type: str = "test_plan",
    source_name: str = "Checkout Load Test",
    created_at: datetime | None = None,
) -> Run:
    created_at = created_at or datetime.now(UTC)
    run = Run(
        id=new_ulid(),
        workspace_id=workspace_id,
        run_type=run_type,
        state=state,
        source_type=source_type,
        source_id=new_ulid(),
        selected_node_id=node.id,
        triggered_by_user_id=user_id,
        accepted_at=created_at + timedelta(seconds=1),
        started_at=created_at + timedelta(seconds=2) if state != "initializing" else None,
        ended_at=created_at + timedelta(minutes=4)
        if state in {"finished", "failed", "aborted"}
        else None,
        last_heartbeat_at=created_at + timedelta(minutes=3),
        last_callback_event_id=None,
        stop_requested_at=None,
        stop_requested_by_user_id=None,
        failure_reason=None,
        failure_message=None,
        forced_convergence=False,
        runner_pid=None,
        remote_start_requested_at=None,
        remote_start_attempted_at=None,
        remote_start_completed_at=None,
        last_force_kill_at=None,
        validity=validity,
        sla_result=sla_result,
        sla_result_reason=None,
        validity_updated_by_user_id=None,
        validity_updated_at=None,
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(run)
    db.flush()
    snapshot_json = {
        "schemaVersion": 1,
        "sourceRevision": 1,
        "testPlan": {"name": source_name, "revision": 1, "tags": ["checkout"]},
    }
    if source_type == "debug_scenario":
        snapshot_json = {
            "schemaVersion": 1,
            "sourceRevision": 1,
            "scenario": {"name": source_name, "revision": 1, "tags": ["debug"]},
        }
    db.add(
        RunSnapshot(
            id=new_ulid(),
            workspace_id=workspace_id,
            run_id=run.id,
            snapshot_version=1,
            snapshot_hash="0" * 64,
            snapshot_json=snapshot_json,
            created_at=created_at,
        )
    )
    return run


def seed_artifact(db: Session, *, run: Run, artifact_type: str = "artifacts_zip") -> None:
    db.add(
        RunArtifact(
            id=new_ulid(),
            workspace_id=run.workspace_id,
            run_id=run.id,
            node_id=run.selected_node_id,
            event_id=new_ulid(),
            artifact_type=artifact_type,
            relative_path="artifacts/artifacts.zip"
            if artifact_type == "artifacts_zip"
            else "logs/run.log",
            display_filename="artifacts.zip" if artifact_type == "artifacts_zip" else "run.log",
            size_bytes=1024,
            sha256="a" * 64,
            content_type="application/zip" if artifact_type == "artifacts_zip" else "text/plain",
            storage_key=f"run-artifacts/{run.workspace_id}/{run.id}/hidden-key",
            status="available",
            terminal_late=False,
            created_at=datetime.now(UTC),
        )
    )


def seed_other_workspace(db: Session, *, user_id: str) -> Workspace:
    now = datetime.now(UTC)
    workspace = Workspace(
        id=OTHER_WORKSPACE_ID,
        name="Other Workspace",
        status="active",
        created_at=now,
        updated_at=now,
    )
    db.add(workspace)
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user_id, joined_at=now))
    db.flush()
    return workspace


@pytest.mark.anyio
async def test_overview_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/overview")

    assert response.status_code == 401


@pytest.mark.anyio
async def test_overview_filters_stats_recent_runs_and_nodes_by_scope(
    client: AsyncClient, db_session: Session
) -> None:
    _csrf, workspace_id, user_id = await register(client, "overview@example.com")
    user = db_session.get(User, user_id)
    assert user is not None
    now = datetime.now(UTC)
    node = seed_node(db_session, user_id=user_id, workspace_id=workspace_id, status="idle")
    seed_node(db_session, user_id=user_id, workspace_id=workspace_id, status="busy")
    seed_node(db_session, user_id=user_id, workspace_id=None, scope="public", status="offline")
    seed_node(db_session, user_id=user_id, workspace_id=workspace_id, status="idle", archived=True)
    other_workspace = seed_other_workspace(db_session, user_id=user_id)
    other_node = seed_node(
        db_session, user_id=user_id, workspace_id=other_workspace.id, status="quarantined"
    )

    passed = seed_run(
        db_session,
        user_id=user_id,
        node=node,
        workspace_id=workspace_id,
        state="finished",
        sla_result="passed",
        source_name="Valid finished run",
        created_at=now - timedelta(days=1),
    )
    seed_artifact(db_session, run=passed)
    seed_run(
        db_session,
        user_id=user_id,
        node=node,
        workspace_id=workspace_id,
        state="failed",
        sla_result="failed",
        source_name="Valid failed run",
        created_at=now - timedelta(days=2),
    )
    seed_run(
        db_session,
        user_id=user_id,
        node=node,
        workspace_id=workspace_id,
        state="aborted",
        sla_result="not_evaluated",
        source_name="Valid aborted run",
        created_at=now - timedelta(days=3),
    )
    seed_run(
        db_session,
        user_id=user_id,
        node=node,
        workspace_id=workspace_id,
        run_type="debug",
        source_type="debug_scenario",
        state="finished",
        validity="invalid",
        sla_result="passed",
        source_name="Debug calibration",
        created_at=now,
    )
    seed_run(
        db_session,
        user_id=user_id,
        node=node,
        workspace_id=workspace_id,
        validity="invalid",
        state="finished",
        sla_result="passed",
        source_name="Invalid standard run",
        created_at=now - timedelta(hours=1),
    )
    seed_run(
        db_session,
        user_id=user_id,
        node=node,
        workspace_id=workspace_id,
        state="running",
        validity="valid",
        sla_result="not_evaluated",
        source_name="Active run",
        created_at=now - timedelta(minutes=30),
    )
    seed_run(
        db_session,
        user_id=user_id,
        node=node,
        workspace_id=workspace_id,
        state="finished",
        validity="valid",
        sla_result="passed",
        source_name="Old run",
        created_at=now - timedelta(days=31),
    )
    seed_run(
        db_session,
        user_id=user_id,
        node=other_node,
        workspace_id=other_workspace.id,
        state="finished",
        validity="valid",
        sla_result="passed",
        source_name="Cross workspace run",
        created_at=now,
    )
    db_session.commit()

    before_audit_count = db_session.scalar(select(func.count(AuditEvent.id))) or 0
    response = await client.get("/api/v1/overview", headers={"x-workspace-id": workspace_id})

    assert response.status_code == 200
    assert response.headers["x-workspace-id"] == workspace_id
    body = response.json()
    assert body["workspace"] == {"id": workspace_id, "name": "Default Workspace"}
    assert body["statsScope"]["windowDays"] == 30
    assert body["statsScope"]["resultRunScope"] == "valid_standard_terminal_runs"
    assert body["runStats"]["resultRuns"]["total"] == 3
    assert body["runStats"]["resultRuns"]["byState"] == {
        "finished": 1,
        "failed": 1,
        "aborted": 1,
    }
    assert body["runStats"]["resultRuns"]["bySlaResult"] == {
        "passed": 1,
        "failed": 1,
        "notEvaluated": 1,
    }
    assert body["runStats"]["activeRuns"]["total"] == 1
    assert body["runStats"]["activeRuns"]["running"] == 1
    names = [item["sourceName"] for item in body["recentRuns"]]
    assert "Debug calibration" in names
    assert "Invalid standard run" in names
    assert "Cross workspace run" not in names
    assert body["recentRuns"][0]["runType"] == "debug"
    assert any(
        item["artifactCount"] == 1 and item["hasArtifactsZip"] for item in body["recentRuns"]
    )
    assert body["resourceSummary"]["totalVisibleNodes"] == 3
    assert body["resourceSummary"]["byStatus"]["idle"] == 1
    assert body["resourceSummary"]["byStatus"]["busy"] == 1
    assert body["resourceSummary"]["byStatus"]["offline"] == 1
    assert body["resourceSummary"]["byStatus"]["quarantined"] == 0
    encoded = json.dumps(body)
    assert "storageKey" not in encoded
    assert "ssh" not in encoded.lower()
    assert "hidden-key" not in encoded
    after_audit_count = db_session.scalar(select(func.count(AuditEvent.id))) or 0
    assert after_audit_count == before_audit_count


@pytest.mark.anyio
async def test_overview_uses_default_workspace_and_validates_recent_limit(
    client: AsyncClient, db_session: Session
) -> None:
    _csrf, workspace_id, user_id = await register(client, "overview-default@example.com")
    node = seed_node(db_session, user_id=user_id, workspace_id=workspace_id)
    for index in range(7):
        seed_run(
            db_session,
            user_id=user_id,
            node=node,
            workspace_id=workspace_id,
            source_name=f"Recent run {index}",
            created_at=datetime.now(UTC) - timedelta(minutes=index),
        )
    db_session.commit()

    default_response = await client.get("/api/v1/overview")
    assert default_response.status_code == 200
    assert default_response.headers["x-workspace-id"] == workspace_id
    assert default_response.json()["statsScope"]["recentRunLimit"] == 5
    assert len(default_response.json()["recentRuns"]) == 5

    limited_response = await client.get("/api/v1/overview?recentLimit=10")
    assert limited_response.status_code == 200
    assert len(limited_response.json()["recentRuns"]) == 7

    invalid_response = await client.get("/api/v1/overview?recentLimit=11")
    assert invalid_response.status_code == 422
    assert invalid_response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.anyio
async def test_admin_setup_status_requires_admin(client: AsyncClient, db_session: Session) -> None:
    _csrf, _workspace_id, admin_id = await register(client, "admin-setup@example.com")
    admin_response = await client.get("/api/v1/admin/setup-status")
    assert admin_response.status_code == 200
    body = admin_response.json()
    assert body["hasDefaultWorkspace"] is True
    assert body["needsBootstrap"] is False
    assert "storageAvailable" not in body

    user = db_session.get(User, admin_id)
    assert user is not None
    user.role = "user"
    db_session.commit()

    user_response = await client.get("/api/v1/admin/setup-status")
    assert user_response.status_code == 403


def test_overview_service_does_not_use_artifact_storage_or_parsers(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime.now(UTC)
    user = User(
        id=new_ulid(),
        email="service-overview@example.com",
        display_name="Overview Service",
        password_hash="hash",
        role="admin",
        status="active",
        failed_login_count=0,
        locked_until=None,
        last_login_at=None,
        created_at=now,
        updated_at=now,
    )
    db_session.add(user)
    db_session.add(
        WorkspaceMember(workspace_id=DEFAULT_WORKSPACE_ID, user_id=user.id, joined_at=now)
    )
    node = seed_node(db_session, user_id=user.id, workspace_id=DEFAULT_WORKSPACE_ID)
    run = seed_run(db_session, user_id=user.id, node=node, workspace_id=DEFAULT_WORKSPACE_ID)
    seed_artifact(db_session, run=run)
    db_session.commit()
    workspace = db_session.get(Workspace, DEFAULT_WORKSPACE_ID)
    assert workspace is not None

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Overview must not parse artifact content.")

    monkeypatch.setattr("app.services.run_reports.get_storage_client", forbidden)
    monkeypatch.setattr("app.services.run_reports.parse_final_stats_csv", forbidden)

    response = get_overview(db_session, workspace=workspace)

    assert response.recent_runs[0].artifact_count == 1
