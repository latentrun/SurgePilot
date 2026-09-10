from dataclasses import replace
from datetime import UTC, datetime, timedelta
from io import BytesIO
import hashlib
import hmac

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from surgepilot_runner import cli as fake_runner_cli

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.ids import new_ulid
from app.models.auth import DEFAULT_WORKSPACE_ID, User
from app.models.load_nodes import LoadNode
from app.models.runs import (
    NodeLease,
    Run,
    RunArtifact,
    RunControlRequest,
    RunNodeAllocation,
    RunSnapshot,
)
from app.schemas.runs import RunResourceRequest
from app.schemas.test_plans import TestPlanResourceConfig as ResourceConfig
from app.schemas.load_nodes import LoadNodeCredentialInput
from app.services.load_nodes import create_load_node
from app.services.run_control_executor import RemoteRunControlExecutor
from app.services.runs import (
    RunControlCommand,
    RunControlExecutionResult,
    RunControlExecutor,
    RunnerCallbackInput,
    apply_runner_callback,
    complete_run_control_request,
    enqueue_control_request,
    ingest_run_artifact,
    request_stop,
    recover_stale_run_control_requests,
    sweep_accepted_timeouts,
    sweep_heartbeat_timeouts,
    validate_runner_token,
)
from app.worker import run_once
from app.services.test_plans import (
    _apply_resource_request_override,
    _normalize_resource_request_override,
    build_test_plan_taurus_document_from_snapshot,
    clone_test_plan,
    create_test_plan,
    create_test_plan_run,
    detail_payload,
    patch_test_plan,
    summary_payload,
)
from app.services.run_reports import get_run_report, list_run_artifacts_report
from app.models.test_plans import (
    TestPlan as TestPlanModel,
    TestPlanScenarioItem as TestPlanScenarioItemModel,
    TestPlanSlaRule,
)
from app.models.scenarios import Scenario
from app.services.storage import PutResult

TestPlanModel.__test__ = False
TestPlanScenarioItemModel.__test__ = False
TestPlanSlaRule.__test__ = False


def trusted_host_key() -> dict[str, str]:
    return {
        "algorithm": "ssh-ed25519",
        "publicKey": "AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC",
        "fingerprintSha256": "SHA256:SurgePilotTrustedHostKey",
    }


class RecordingRunControlExecutor(RunControlExecutor):
    def __init__(self) -> None:
        self.commands: list[RunControlCommand] = []

    def execute(self, command: RunControlCommand) -> RunControlExecutionResult:
        self.commands.append(command)
        return RunControlExecutionResult(ok=True)


def test_run_resource_request_validates_mode_fields() -> None:
    node_id = new_ulid()

    assert RunResourceRequest(mode="manual", selectedNodeIds=[node_id]).selected_node_ids == [
        node_id
    ]
    assert RunResourceRequest(mode="auto", nodeCount=2).node_count == 2

    invalid_cases = [
        {"mode": "manual", "selectedNodeIds": ["not-a-ulid"]},
        {"mode": "manual", "selectedNodeIds": [node_id], "nodeCount": 2},
        {"mode": "manual", "selectedNodeIds": []},
        {"mode": "manual", "selectedNodeIds": [node_id, node_id]},
        {"mode": "auto", "selectedNodeIds": [node_id], "nodeCount": 2},
        {"mode": "auto"},
    ]
    for payload in invalid_cases:
        with pytest.raises(ValidationError):
            RunResourceRequest(**payload)


def test_test_plan_resource_config_validates_mode_fields() -> None:
    node_id = new_ulid()

    assert ResourceConfig(mode="manual", selectedNodeIds=[node_id]).selected_node_ids == [node_id]
    assert ResourceConfig(mode="auto", nodeCount=2).node_count == 2

    invalid_cases = [
        {"mode": "manual", "nodeCount": 2},
        {"mode": "auto", "nodeCount": 2, "selectedNodeId": node_id},
        {"mode": "auto", "nodeCount": 2, "selectedNodeIds": [node_id]},
        {"mode": "auto"},
    ]
    for payload in invalid_cases:
        with pytest.raises(ValidationError):
            ResourceConfig(**payload)


def test_test_plan_resource_request_override_normalization() -> None:
    node_id = new_ulid()
    snapshot = {"resourceRequest": {"mode": "manual", "selectedNodeIds": [node_id]}}

    resource = _apply_resource_request_override(
        snapshot,
        run_type="standard",
        resource_request={
            "mode": "auto",
            "poolType": "private",
            "nodeCount": 2,
            "concurrencyPerNode": 25,
        },
    )

    assert resource == {
        "mode": "auto",
        "selectedNodeIds": [],
        "selectedNodeId": None,
        "nodeCount": 2,
        "poolType": "private",
        "expectedConcurrencyPerNode": 25,
    }
    assert snapshot["resourceRequest"] == resource
    assert _normalize_resource_request_override(None) is None


def test_test_plan_resource_request_override_rejects_invalid_shapes() -> None:
    node_id = new_ulid()
    invalid_requests = [
        {"mode": "unsupported"},
        {"mode": "manual", "selectedNodeIds": []},
        {"mode": "manual", "selectedNodeIds": [node_id, node_id]},
        {"mode": "auto", "poolType": "unsupported", "nodeCount": 1},
        {"mode": "auto", "selectedNodeIds": [node_id], "nodeCount": 2},
        {"mode": "auto", "nodeCount": 0},
    ]

    for resource_request in invalid_requests:
        with pytest.raises(AppError) as exc_info:
            _normalize_resource_request_override(resource_request)
        assert exc_info.value.code == "RESOURCE_REQUEST_INVALID"

    with pytest.raises(AppError) as exc_info:
        _apply_resource_request_override(
            {"resourceRequest": {}},
            run_type="debug",
            resource_request={"mode": "manual", "selectedNodeIds": [node_id]},
        )
    assert exc_info.value.code == "RESOURCE_REQUEST_INVALID"


def actor() -> User:
    now = datetime.now(UTC)
    return User(
        id=new_ulid(),
        email=f"p1-{new_ulid().lower()}@example.com",
        display_name="P1 User",
        password_hash="hash",
        role="user",
        status="active",
        failed_login_count=0,
        created_at=now,
        updated_at=now,
    )


def credential() -> LoadNodeCredentialInput:
    return LoadNodeCredentialInput(authType="password", password="secret-password")


def idle_node(db_session: Session, user: User, *, status: str = "idle") -> LoadNode:
    node = create_load_node(
        db_session,
        actor=user,
        workspace_id=DEFAULT_WORKSPACE_ID,
        scope="workspace",
        host=f"p1-node-{new_ulid().lower()}.internal",
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        credential=credential(),
        ssh_host_key=trusted_host_key(),
        maintainer=None,
        remark=None,
    )
    node.status = status
    node.runtime_version = "runtime-test-v1"
    db_session.flush()
    return node


def public_idle_node(db_session: Session, user: User, *, status: str = "idle") -> LoadNode:
    user.role = "admin"
    node = create_load_node(
        db_session,
        actor=user,
        workspace_id=DEFAULT_WORKSPACE_ID,
        scope="public",
        host=f"p1-public-{new_ulid().lower()}.internal",
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        credential=credential(),
        ssh_host_key=trusted_host_key(),
        maintainer=None,
        remark=None,
    )
    node.status = status
    node.runtime_version = "runtime-test-v1"
    db_session.flush()
    return node


def scenario(db_session: Session, user: User) -> Scenario:
    now = datetime.now(UTC)
    row = Scenario(
        id=new_ulid(),
        workspace_id=DEFAULT_WORKSPACE_ID,
        scenario_type="visual",
        name="Checkout API",
        description=None,
        tags_json=[],
        base_url_expression="https://api.example.test",
        default_settings_json={
            "timeoutMs": 30000,
            "thinkTimeMs": 0,
            "followRedirects": True,
            "retrieveResources": False,
            "storeCache": True,
            "storeCookie": True,
            "keepAlive": True,
            "headers": [],
        },
        data_sources_json=[],
        steps_json=[
            {
                "id": new_ulid(),
                "type": "request",
                "enabled": True,
                "name": "Home",
                "method": "GET",
                "path": "/",
                "headers": [],
                "queryParams": [],
                "body": {"type": "none"},
                "assertions": [],
                "extractors": [],
            }
        ],
        visual_schema_version=1,
        revision=1,
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
        created_at=now,
        updated_at=now,
    )
    db_session.add(row)
    db_session.flush()
    return row


def make_test_plan(db_session: Session, user: User, *, resource: dict) -> TestPlanModel:
    now = datetime.now(UTC)
    scn = scenario(db_session, user)
    plan = TestPlanModel(
        id=new_ulid(),
        workspace_id=DEFAULT_WORKSPACE_ID,
        name="P1 multi-node plan",
        description=None,
        tags_json=[],
        env_group_id=None,
        run_mode="parallel",
        pool_type=resource.get("poolType"),
        selected_node_id=resource.get("selectedNodeId"),
        resource_mode=resource.get("mode", "manual"),
        selected_node_ids_json=resource.get("selectedNodeIds") or [],
        node_count=resource.get("nodeCount"),
        revision=1,
        created_by=user.id,
        updated_by=user.id,
        created_at=now,
        updated_at=now,
    )
    db_session.add(plan)
    db_session.flush()
    item = TestPlanScenarioItemModel(
        id=new_ulid(),
        workspace_id=DEFAULT_WORKSPACE_ID,
        test_plan_id=plan.id,
        scenario_id=scn.id,
        enabled=True,
        position=0,
        concurrency_per_node=25,
        ramp_up_seconds=0,
        hold_for_seconds=60,
        iterations=None,
        target_rps=None,
        steps=None,
        delay_seconds=0,
        created_at=now,
        updated_at=now,
    )
    db_session.add(item)
    db_session.flush()
    return plan


def callback(run_id: str, node_id: str, event_type: str, *, event_id: str) -> RunnerCallbackInput:
    return RunnerCallbackInput(
        schema_version="1",
        event_id=event_id,
        run_id=run_id,
        node_id=node_id,
        runtime_version="runtime-test-v1",
        event_type=event_type,
        seq=1,
        event_time=datetime.now(UTC),
        message="Callback received.",
        runner_pid=123 if event_type == "accepted" else None,
        details={"processGroupExited": True, "slaResult": "passed"}
        if event_type == "finished"
        else {},
        raw_payload={
            "schemaVersion": "1",
            "eventId": event_id,
            "runId": run_id,
            "nodeId": node_id,
            "runtimeVersion": "runtime-test-v1",
            "eventType": event_type,
            "seq": 1,
            "eventTime": "2030-06-01T10:00:00.000Z",
            "message": "Callback received.",
            **({"runnerPid": 123} if event_type == "accepted" else {}),
            "details": {"processGroupExited": True, "slaResult": "passed"}
            if event_type == "finished"
            else {},
        },
    )


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_stream(self, *, bucket, object_key, stream, size_limit, content_type=None):  # noqa: ANN001
        _ = bucket, size_limit, content_type
        data = stream.read()
        self.objects[object_key] = data
        return PutResult(size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())

    def copy_object(self, *, bucket, source_key, destination_key) -> None:  # noqa: ANN001
        _ = bucket
        self.objects[destination_key] = self.objects[source_key]

    def delete_object_best_effort(self, *, bucket, object_key) -> None:  # noqa: ANN001
        _ = bucket
        self.objects.pop(object_key, None)


def signed_node_bound_token(base: str, node_id: str) -> str:
    sig = hmac.new(base.encode(), node_id.encode(), hashlib.sha256).hexdigest()
    return f"node:{node_id}:{sig}"


def old_node_bound_token(base: str, node_id: str) -> str:
    return f"{base}:node:{node_id}"


def command_for(node_id: str, *, source_type: str = "test_plan") -> RunControlCommand:
    return RunControlCommand(
        request_id=new_ulid(),
        action="start",
        run_id=new_ulid(),
        node_id=node_id,
        reason=None,
        source_type=source_type,
        host="load-node.internal",
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        trusted_host_key_algorithm="ssh-ed25519",
        trusted_host_key_public_key="AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC",
        trusted_host_key_fingerprint_sha256="SHA256:SurgePilotTrustedHostKey",
        argv=("python3", "/opt/surgepilot/runner/runner.py", "start"),
    )


def test_remote_env_uses_signed_node_credential_without_master_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUNNER_INTERNAL_TOKEN", "runner-secret")
    node_id = new_ulid()
    executor = RemoteRunControlExecutor(
        settings=replace(get_settings(), runner_internal_token="runner-secret")
    )

    env_text = executor._env_file(command_for(node_id))
    token_line = next(
        line for line in env_text.splitlines() if line.startswith("RUNNER_INTERNAL_TOKEN=")
    )
    signed_token = token_line.split("=", 1)[1].strip("'")

    assert signed_token.startswith(f"node:{node_id}:")
    assert "runner-secret" not in env_text
    assert validate_runner_token(signed_token, node_id=node_id) == node_id


def test_fake_runner_env_uses_node_bound_credential_and_rejects_sibling_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUNNER_INTERNAL_TOKEN", "runner-secret")
    node_a = new_ulid()
    node_b = new_ulid()
    executor = RemoteRunControlExecutor(
        settings=replace(get_settings(), runner_internal_token="runner-secret")
    )

    env_text = executor._env_file(command_for(node_a, source_type="protocol_smoke"))
    token_line = next(
        line for line in env_text.splitlines() if line.startswith("RUNNER_INTERNAL_TOKEN=")
    )
    signed_token = token_line.split("=", 1)[1].strip("'")

    assert signed_token.startswith(f"node:{node_a}:")
    assert "runner-secret" not in env_text
    assert validate_runner_token(signed_token, node_id=node_a) == node_a
    with pytest.raises(AppError) as mismatch:
        validate_runner_token(signed_token, node_id=node_b)
    assert mismatch.value.code == "RUNNER_FORBIDDEN"


def test_shared_fake_runner_multi_node_smoke_uses_callbacks_artifacts_and_redaction(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Exercise the shared fake Runner once per allocation, not a recording executor."""
    user = actor()
    db_session.add(user)
    db_session.flush()
    node_a = idle_node(db_session, user)
    node_b = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node_a.id,
            "selectedNodeIds": [node_a.id, node_b.id],
        },
    )

    def run_fake_allocation(run_id: str, node_id: str, *, scenario_name: str) -> list[dict]:
        events: list[dict] = []

        def fake_upload_artifact(**kwargs):  # noqa: ANN003
            path = kwargs["path"]
            return {
                "artifactId": new_ulid(),
                "sizeBytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }

        monkeypatch.setattr(fake_runner_cli, "post_callback", events.append)
        monkeypatch.setattr(fake_runner_cli, "upload_artifact", fake_upload_artifact)
        monkeypatch.setenv("RUNNER_HOME", str(tmp_path / node_id))
        monkeypatch.setenv("SURGEPILOT_NODE_ID", node_id)
        monkeypatch.setenv("RUNNER_FAKE_SCENARIO", scenario_name)
        fake_runner_cli.fake_scenario(run_id)
        return events

    def apply_events(
        node_id: str,
        events: list[dict],
        *,
        auth_node_id: str | None = None,
    ) -> None:
        for event in events:
            callback_input = RunnerCallbackInput(
                schema_version=event["schemaVersion"],
                event_id=event["eventId"],
                run_id=event["runId"],
                node_id=event["nodeId"],
                runtime_version=event["runtimeVersion"],
                event_type=event["eventType"],
                seq=event["seq"],
                event_time=datetime.fromisoformat(event["eventTime"].replace("Z", "+00:00")),
                message=event.get("message"),
                runner_pid=event.get("runnerPid"),
                details=event.get("details", {}),
                raw_payload=event,
            )
            apply_runner_callback(
                db_session,
                callback=callback_input,
                request_id=new_ulid(),
                authenticated_node_id=auth_node_id or node_id,
            )

    def new_run():
        return create_test_plan_run(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            source_id=plan.id,
            expected_source_revision=plan.revision,
            run_type="standard",
            confirm_high_concurrency=True,
        )

    success = new_run()
    events_a = run_fake_allocation(success.run.id, node_a.id, scenario_name="success")
    events_b = run_fake_allocation(success.run.id, node_b.id, scenario_name="success")
    assert any(event["eventType"] == "artifact" for event in events_a)
    assert any(event["eventType"] == "artifact" for event in events_b)

    with pytest.raises(AppError) as mismatch:
        apply_events(node_b.id, events_b[:1], auth_node_id=node_a.id)
    assert mismatch.value.code == "RUNNER_FORBIDDEN"
    apply_events(node_a.id, events_a)
    apply_events(node_b.id, events_b)
    assert success.run.state == "finished"
    report = get_run_report(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, run_id=success.run.id
    ).model_dump(by_alias=True)
    report_text = str(report)
    assert report["verdict"]["state"] == "finished"
    assert len(report["allocatedNodes"]) == 2
    for secret in (node_a.host, node_b.host, node_a.ssh_user, node_a.runner_home):
        assert secret not in report_text

    failed = new_run()
    apply_events(
        node_a.id,
        run_fake_allocation(failed.run.id, node_a.id, scenario_name="success"),
    )
    apply_events(
        node_b.id,
        run_fake_allocation(failed.run.id, node_b.id, scenario_name="failed"),
    )
    assert failed.run.state == "failed"


def test_old_node_bound_runner_token_format_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUNNER_INTERNAL_TOKEN", "runner-secret")
    node_id = new_ulid()

    with pytest.raises(AppError) as exc:
        validate_runner_token(old_node_bound_token("runner-secret", node_id), node_id=node_id)

    assert exc.value.code == "RUNNER_UNAUTHORIZED"


def test_concurrency_override_is_guarded_before_run_creation(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_SINGLE_NODE_CONCURRENCY_SOFT_LIMIT", "50")
    monkeypatch.setenv("SURGEPILOT_SINGLE_NODE_CONCURRENCY_HARD_LIMIT", "100")
    user = actor()
    db_session.add(user)
    db_session.flush()
    node = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node.id,
            "selectedNodeIds": [node.id],
        },
    )

    with pytest.raises(AppError) as hard:
        create_test_plan_run(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            source_id=plan.id,
            expected_source_revision=1,
            run_type="standard",
            confirm_high_concurrency=True,
            resource_request={
                "mode": "manual",
                "selectedNodeIds": [node.id],
                "concurrencyPerNode": 101,
            },
        )
    with pytest.raises(AppError) as soft:
        create_test_plan_run(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            source_id=plan.id,
            expected_source_revision=1,
            run_type="standard",
            confirm_high_concurrency=False,
            resource_request={
                "mode": "manual",
                "selectedNodeIds": [node.id],
                "concurrencyPerNode": 51,
            },
        )

    assert hard.value.code == "VALIDATION_ERROR"
    assert hard.value.details[0]["code"] == "single_node_concurrency_hard_limit"
    assert soft.value.code == "LOAD_SOFT_LIMIT_CONFIRMATION_REQUIRED"
    assert db_session.scalar(select(RunNodeAllocation)) is None

    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
        resource_request={
            "mode": "manual",
            "selectedNodeIds": [node.id],
            "concurrencyPerNode": 51,
        },
    )
    snapshot = result.run.snapshot.snapshot_json
    assert snapshot["resourceRequest"]["expectedConcurrencyPerNode"] == 51
    assert snapshot["scenarioItems"][0]["loadSettings"]["concurrencyPerNode"] == 51


def test_manual_standard_run_allocates_all_nodes_atomically(db_session: Session) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node_a = idle_node(db_session, user)
    node_b = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node_a.id,
            "selectedNodeIds": [node_a.id, node_b.id],
        },
    )

    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )

    allocations = db_session.scalars(
        select(RunNodeAllocation).where(RunNodeAllocation.run_id == result.run.id)
    ).all()
    leases = db_session.scalars(select(NodeLease).where(NodeLease.run_id == result.run.id)).all()
    starts = db_session.scalars(
        select(RunControlRequest).where(
            RunControlRequest.run_id == result.run.id,
            RunControlRequest.action == "start",
        )
    ).all()
    assert [allocation.node_id for allocation in allocations] == [node_a.id, node_b.id]
    assert [allocation.node_index for allocation in allocations] == [1, 2]
    assert {lease.node_id for lease in leases} == {node_a.id, node_b.id}
    assert {request.node_id for request in starts} == {node_a.id, node_b.id}
    assert result.run.snapshot.snapshot_json["resourceRequest"] == {
        "mode": "manual",
        "poolType": "private",
        "selectedNodeId": node_a.id,
        "selectedNodeIds": [node_a.id, node_b.id],
        "nodeCount": None,
        "expectedConcurrencyPerNode": 25,
    }


def test_manual_duplicate_nodes_are_rejected_without_partial_state(db_session: Session) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node.id,
            "selectedNodeIds": [node.id, node.id],
        },
    )

    with pytest.raises(AppError) as exc:
        create_test_plan_run(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            source_id=plan.id,
            expected_source_revision=1,
            run_type="standard",
            confirm_high_concurrency=True,
        )

    assert exc.value.code == "RESOURCE_REQUEST_INVALID"
    assert db_session.scalar(select(RunNodeAllocation)) is None
    assert db_session.scalar(select(NodeLease)) is None


def test_allocation_race_rolls_back_without_partial_run_state(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node.id,
            "selectedNodeIds": [node.id],
        },
    )
    competing_run = Run(
        id=new_ulid(),
        workspace_id=DEFAULT_WORKSPACE_ID,
        run_type="standard",
        state="running",
        source_type="test_plan",
        source_id=None,
        selected_node_id=node.id,
        triggered_by_user_id=user.id,
        forced_convergence=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    competing_lease = NodeLease(
        id=new_ulid(),
        workspace_id=DEFAULT_WORKSPACE_ID,
        node_id=node.id,
        run_id=competing_run.id,
        acquired_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add_all([competing_run, competing_lease])
    db_session.commit()
    monkeypatch.setattr("app.services.runs._active_lease", lambda *args, **kwargs: None)

    with pytest.raises(AppError) as exc:
        create_test_plan_run(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            source_id=plan.id,
            expected_source_revision=1,
            run_type="standard",
            confirm_high_concurrency=True,
        )
    db_session.rollback()

    assert exc.value.code == "LOAD_NODE_UNAVAILABLE"
    assert db_session.scalar(select(Run).where(Run.source_id == plan.id)) is None
    assert db_session.scalar(select(RunNodeAllocation)) is None
    assert db_session.scalar(select(RunControlRequest)) is None
    leases = db_session.scalars(select(NodeLease).where(NodeLease.node_id == node.id)).all()
    assert [lease.id for lease in leases] == [competing_lease.id]


def test_auto_standard_run_requires_capacity_and_does_not_partially_allocate(
    db_session: Session,
) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={"mode": "auto", "poolType": "private", "nodeCount": 2},
    )

    with pytest.raises(AppError) as exc:
        create_test_plan_run(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            source_id=plan.id,
            expected_source_revision=1,
            run_type="standard",
            confirm_high_concurrency=True,
        )

    assert exc.value.code == "LOAD_NODE_CAPACITY_UNAVAILABLE"
    assert db_session.scalar(select(RunNodeAllocation)) is None
    assert db_session.scalar(select(NodeLease)) is None


def test_auto_standard_run_filters_private_pool_candidates(db_session: Session) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    public_node = public_idle_node(db_session, user)
    private_node = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={"mode": "auto", "poolType": "private", "nodeCount": 1},
    )

    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )
    allocations = db_session.scalars(
        select(RunNodeAllocation).where(RunNodeAllocation.run_id == result.run.id)
    ).all()

    assert [allocation.node_id for allocation in allocations] == [private_node.id]
    assert public_node.status == "idle"
    assert private_node.status == "busy"
    assert result.run.snapshot.snapshot_json["resourceRequest"]["poolType"] == "private"


def test_auto_standard_run_filters_public_pool_candidates(db_session: Session) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    private_node = idle_node(db_session, user)
    public_node = public_idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={"mode": "auto", "poolType": "public", "nodeCount": 1},
    )

    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )
    allocations = db_session.scalars(
        select(RunNodeAllocation).where(RunNodeAllocation.run_id == result.run.id)
    ).all()

    assert [allocation.node_id for allocation in allocations] == [public_node.id]
    assert private_node.status == "idle"
    assert public_node.status == "busy"
    assert result.run.snapshot.snapshot_json["resourceRequest"]["poolType"] == "public"


def test_manual_standard_run_override_rejects_node_outside_plan_pool(
    db_session: Session,
) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    private_node = idle_node(db_session, user)
    public_node = public_idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": private_node.id,
            "selectedNodeIds": [private_node.id],
        },
    )

    with pytest.raises(AppError) as exc:
        create_test_plan_run(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            source_id=plan.id,
            expected_source_revision=1,
            run_type="standard",
            confirm_high_concurrency=True,
            resource_request={"mode": "manual", "selectedNodeIds": [public_node.id]},
        )

    assert exc.value.code == "RESOURCE_NOT_FOUND"
    assert db_session.scalar(select(RunNodeAllocation)) is None
    assert private_node.status == "idle"
    assert public_node.status == "idle"


def test_auto_test_plan_detail_and_summary_use_capacity_without_selected_node(
    db_session: Session,
) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    idle_node(db_session, user)
    idle_node(db_session, user)
    stale = idle_node(db_session, user)
    stale.runtime_version = "runtime-old"
    runnable_plan = make_test_plan(
        db_session,
        user,
        resource={"mode": "auto", "poolType": "private", "nodeCount": 2},
    )
    short_plan = make_test_plan(
        db_session,
        user,
        resource={"mode": "auto", "poolType": "private", "nodeCount": 3},
    )

    detail = detail_payload(db_session, runnable_plan)
    summary = summary_payload(db_session, runnable_plan)
    short_detail = detail_payload(db_session, short_plan)

    assert detail["runnable"] is True
    assert detail["notRunnableReasons"] == []
    assert summary["runnable"] is True
    assert "load_node_unavailable" not in summary["notRunnableReasons"]
    assert short_detail["runnable"] is False
    assert short_detail["notRunnableReasons"] == ["load_node_capacity_unavailable"]


def test_run_report_allocated_nodes_are_allocation_backed(db_session: Session) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node = idle_node(db_session, user)
    now = datetime.now(UTC)
    run = Run(
        id=new_ulid(),
        workspace_id=DEFAULT_WORKSPACE_ID,
        run_type="standard",
        state="finished",
        source_type="test_plan",
        source_id=new_ulid(),
        selected_node_id=node.id,
        triggered_by_user_id=user.id,
        forced_convergence=False,
        validity="valid",
        sla_result="not_evaluated",
        created_at=now,
        updated_at=now,
        ended_at=now,
    )
    snapshot = RunSnapshot(
        id=new_ulid(),
        workspace_id=DEFAULT_WORKSPACE_ID,
        run_id=run.id,
        snapshot_version=1,
        snapshot_hash="allocation-backed-report-test",
        snapshot_json={
            "schemaVersion": 1,
            "runType": "standard",
            "sourceType": "test_plan",
            "resourceRequest": {
                "mode": "manual",
                "poolType": "private",
                "selectedNodeId": node.id,
                "selectedNodeIds": [node.id],
            },
        },
        created_at=now,
    )
    db_session.add_all([run, snapshot])
    db_session.flush()

    report = get_run_report(db_session, workspace_id=DEFAULT_WORKSPACE_ID, run_id=run.id)

    assert report.snapshot.resource_request.selected_node_ids == [node.id]
    assert report.allocated_nodes == []


def test_standard_run_resource_request_override_rejects_conflicting_fields(
    db_session: Session,
) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node.id,
            "selectedNodeIds": [node.id],
        },
    )

    with pytest.raises(AppError) as manual_exc:
        create_test_plan_run(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            source_id=plan.id,
            expected_source_revision=1,
            run_type="standard",
            confirm_high_concurrency=True,
            resource_request={
                "mode": "manual",
                "selectedNodeIds": [node.id],
                "nodeCount": 1,
            },
        )
    with pytest.raises(AppError) as auto_exc:
        create_test_plan_run(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            source_id=plan.id,
            expected_source_revision=1,
            run_type="standard",
            confirm_high_concurrency=True,
            resource_request={
                "mode": "auto",
                "selectedNodeIds": [node.id],
                "nodeCount": 1,
            },
        )

    assert manual_exc.value.code == "RESOURCE_REQUEST_INVALID"
    assert auto_exc.value.code == "RESOURCE_REQUEST_INVALID"
    assert db_session.scalar(select(RunNodeAllocation)) is None


def test_concurrency_per_node_override_updates_snapshot_and_generated_yaml(
    db_session: Session,
) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node.id,
            "selectedNodeIds": [node.id],
        },
    )

    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
        resource_request={"mode": "manual", "selectedNodeIds": [node.id], "concurrencyPerNode": 50},
    )
    snapshot = result.run.snapshot.snapshot_json
    document = build_test_plan_taurus_document_from_snapshot(
        snapshot, jmeter_path="/opt/jmeter/bin/jmeter", jmeter_version="5.6.3"
    )

    assert snapshot["resourceRequest"]["expectedConcurrencyPerNode"] == 50
    assert snapshot["scenarioItems"][0]["loadSettings"]["concurrencyPerNode"] == 50
    assert document["execution"][0]["concurrency"] == 50


def test_debug_run_rejects_multi_node_resource_request_override(db_session: Session) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node_a = idle_node(db_session, user)
    node_b = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node_a.id,
            "selectedNodeIds": [node_a.id],
        },
    )

    with pytest.raises(AppError) as exc:
        create_test_plan_run(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            source_id=plan.id,
            expected_source_revision=1,
            run_type="debug",
            confirm_high_concurrency=True,
            resource_request={"mode": "manual", "selectedNodeIds": [node_a.id, node_b.id]},
        )

    assert exc.value.code == "RESOURCE_REQUEST_INVALID"
    assert db_session.scalar(select(RunNodeAllocation)) is None


def test_stop_broadcasts_once_per_non_terminal_allocation(db_session: Session) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node_a = idle_node(db_session, user)
    node_b = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node_a.id,
            "selectedNodeIds": [node_a.id, node_b.id],
        },
    )
    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )

    first = request_stop(db_session, run=result.run, actor=user)
    second = request_stop(db_session, run=result.run, actor=user)

    stops = db_session.scalars(
        select(RunControlRequest).where(
            RunControlRequest.run_id == result.run.id,
            RunControlRequest.action == "stop",
        )
    ).all()
    assert first.duplicate is False
    assert second.duplicate is True
    assert {request.node_id for request in stops} == {node_a.id, node_b.id}
    assert len(stops) == 2


def test_callbacks_wait_for_all_allocations_and_reject_unallocated_node(
    db_session: Session,
) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node_a = idle_node(db_session, user)
    node_b = idle_node(db_session, user)
    node_c = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node_a.id,
            "selectedNodeIds": [node_a.id, node_b.id],
        },
    )
    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )

    apply_runner_callback(
        db_session,
        callback=callback(result.run.id, node_a.id, "running", event_id=new_ulid()),
        request_id="req-1",
        authenticated_node_id=node_a.id,
    )
    apply_runner_callback(
        db_session,
        callback=callback(result.run.id, node_a.id, "finished", event_id=new_ulid()),
        request_id="req-2",
        authenticated_node_id=node_a.id,
    )
    assert result.run.state == "running"

    with pytest.raises(AppError) as exc:
        apply_runner_callback(
            db_session,
            callback=callback(result.run.id, node_c.id, "running", event_id=new_ulid()),
            request_id="req-3",
            authenticated_node_id=node_c.id,
        )
    assert exc.value.code == "RUNNER_FORBIDDEN"

    apply_runner_callback(
        db_session,
        callback=callback(result.run.id, node_b.id, "running", event_id=new_ulid()),
        request_id="req-4",
        authenticated_node_id=node_b.id,
    )
    apply_runner_callback(
        db_session,
        callback=callback(result.run.id, node_b.id, "finished", event_id=new_ulid()),
        request_id="req-5",
        authenticated_node_id=node_b.id,
    )
    assert result.run.state == "finished"
    assert result.run.sla_result == "not_evaluated"


def test_finished_callback_for_initializing_allocation_is_illegal_even_when_run_running(
    db_session: Session,
) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node_a = idle_node(db_session, user)
    node_b = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node_a.id,
            "selectedNodeIds": [node_a.id, node_b.id],
        },
    )
    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )
    apply_runner_callback(
        db_session,
        callback=callback(result.run.id, node_a.id, "running", event_id=new_ulid()),
        request_id="req-running-a-before-illegal-finish",
        authenticated_node_id=node_a.id,
    )
    allocation_b = db_session.scalar(
        select(RunNodeAllocation).where(
            RunNodeAllocation.run_id == result.run.id, RunNodeAllocation.node_id == node_b.id
        )
    )
    assert result.run.state == "running"
    assert allocation_b is not None and allocation_b.state == "initializing"

    finished_b = apply_runner_callback(
        db_session,
        callback=terminal_callback(
            result.run.id,
            node_b.id,
            "finished",
            event_id=new_ulid(),
            process_group_exited=True,
        ),
        request_id="req-finished-b-before-running",
        authenticated_node_id=node_b.id,
    )

    assert finished_b.ignored_reason == "illegal_transition"
    assert result.run.state == "running"
    assert allocation_b.state == "initializing"
    assert allocation_b.ended_at is None


def test_late_terminal_callback_does_not_override_terminal_run(
    db_session: Session,
) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node.id,
            "selectedNodeIds": [node.id],
        },
    )
    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )
    apply_runner_callback(
        db_session,
        callback=callback(result.run.id, node.id, "running", event_id=new_ulid()),
        request_id="req-running-before-late-terminal",
        authenticated_node_id=node.id,
    )
    apply_runner_callback(
        db_session,
        callback=terminal_callback(
            result.run.id,
            node.id,
            "finished",
            event_id=new_ulid(),
            process_group_exited=True,
            sla_result="passed",
        ),
        request_id="req-finished-before-late-terminal",
        authenticated_node_id=node.id,
    )
    allocation = db_session.scalar(
        select(RunNodeAllocation).where(RunNodeAllocation.run_id == result.run.id)
    )
    assert allocation is not None
    original_ended_at = result.run.ended_at
    original_allocation_reason = allocation.terminal_reason

    late = apply_runner_callback(
        db_session,
        callback=terminal_callback(
            result.run.id,
            node.id,
            "failed",
            event_id=new_ulid(),
            process_group_exited=True,
            sla_result="failed",
            reason="late_failure",
        ),
        request_id="req-late-terminal-after-finished",
        authenticated_node_id=node.id,
    )

    assert late.ignored_reason == "terminal_state_protected"
    assert result.run.state == "finished"
    assert result.run.ended_at is not None
    assert original_ended_at is not None
    assert result.run.ended_at.replace(tzinfo=UTC) == original_ended_at
    assert result.run.failure_reason is None
    assert result.run.sla_result == "not_evaluated"
    assert allocation.state == "finished"
    assert allocation.terminal_reason == original_allocation_reason


def test_multi_node_callbacks_require_node_bound_token_identity(db_session: Session) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node_a = idle_node(db_session, user)
    node_b = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node_a.id,
            "selectedNodeIds": [node_a.id, node_b.id],
        },
    )
    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )

    with pytest.raises(AppError) as shared_exc:
        apply_runner_callback(
            db_session,
            callback=callback(result.run.id, node_b.id, "running", event_id=new_ulid()),
            request_id="req-shared",
            authenticated_node_id=None,
        )
    with pytest.raises(AppError) as mismatch_exc:
        apply_runner_callback(
            db_session,
            callback=callback(result.run.id, node_b.id, "running", event_id=new_ulid()),
            request_id="req-mismatch",
            authenticated_node_id=node_a.id,
        )

    assert shared_exc.value.code == "RUNNER_FORBIDDEN"
    assert mismatch_exc.value.code == "RUNNER_FORBIDDEN"


def test_single_allocation_run_requires_node_bound_token_and_rejects_shared(
    db_session: Session,
) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node.id,
            "selectedNodeIds": [node.id],
        },
    )
    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )

    with pytest.raises(AppError) as new_run_exc:
        apply_runner_callback(
            db_session,
            callback=callback(result.run.id, node.id, "running", event_id=new_ulid()),
            request_id="req-shared-new-single",
            authenticated_node_id=None,
        )

    assert new_run_exc.value.code == "RUNNER_FORBIDDEN"


def test_artifact_upload_uses_allocation_membership_not_primary_node_only(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node_a = idle_node(db_session, user)
    node_b = idle_node(db_session, user)
    node_c = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node_a.id,
            "selectedNodeIds": [node_a.id, node_b.id],
        },
    )
    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )
    storage = MemoryStorage()
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: storage)
    data = b"node-b-log"
    digest = hashlib.sha256(data).hexdigest()

    accepted = ingest_run_artifact(
        db_session,
        event_id=new_ulid(),
        run_id=result.run.id,
        node_id=node_b.id,
        authenticated_node_id=node_b.id,
        artifact_type="run_log",
        relative_path="logs/node-b.log",
        declared_sha256=digest,
        declared_size_bytes=len(data),
        file=BytesIO(data),
        content_type="text/plain",
    )

    assert accepted.duplicate is False
    with pytest.raises(AppError) as unallocated_exc:
        ingest_run_artifact(
            db_session,
            event_id=new_ulid(),
            run_id=result.run.id,
            node_id=node_c.id,
            authenticated_node_id=node_c.id,
            artifact_type="run_log",
            relative_path="logs/node-c.log",
            declared_sha256=digest,
            declared_size_bytes=len(data),
            file=BytesIO(data),
            content_type="text/plain",
        )
    with pytest.raises(AppError) as mismatch_exc:
        ingest_run_artifact(
            db_session,
            event_id=new_ulid(),
            run_id=result.run.id,
            node_id=node_b.id,
            authenticated_node_id=node_a.id,
            artifact_type="run_log",
            relative_path="logs/node-b-mismatch.log",
            declared_sha256=digest,
            declared_size_bytes=len(data),
            file=BytesIO(data),
            content_type="text/plain",
        )

    assert unallocated_exc.value.code == "RUNNER_FORBIDDEN"
    assert mismatch_exc.value.code == "RUNNER_FORBIDDEN"


def test_same_relative_path_artifacts_are_scoped_per_allocation(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node_a = idle_node(db_session, user)
    node_b = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node_a.id,
            "selectedNodeIds": [node_a.id, node_b.id],
        },
    )
    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )
    storage = MemoryStorage()
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: storage)
    path = "artifacts/finalstats.csv"
    data_a = (
        b"label,throughput,succ,fail,avg_rt,perc_90.0,perc_95.0,perc_99.0\n,1,1,0,0.1,0.1,0.1,0.1\n"
    )
    data_b = (
        b"label,throughput,succ,fail,avg_rt,perc_90.0,perc_95.0,perc_99.0\n,2,1,1,0.2,0.2,0.2,0.2\n"
    )

    first = ingest_run_artifact(
        db_session,
        event_id=new_ulid(),
        run_id=result.run.id,
        node_id=node_a.id,
        authenticated_node_id=node_a.id,
        artifact_type="final_stats_csv",
        relative_path=path,
        declared_sha256=hashlib.sha256(data_a).hexdigest(),
        declared_size_bytes=len(data_a),
        file=BytesIO(data_a),
        content_type="text/csv",
    )
    second = ingest_run_artifact(
        db_session,
        event_id=new_ulid(),
        run_id=result.run.id,
        node_id=node_b.id,
        authenticated_node_id=node_b.id,
        artifact_type="final_stats_csv",
        relative_path=path,
        declared_sha256=hashlib.sha256(data_b).hexdigest(),
        declared_size_bytes=len(data_b),
        file=BytesIO(data_b),
        content_type="text/csv",
    )

    artifacts = db_session.scalars(
        select(RunArtifact)
        .where(RunArtifact.run_id == result.run.id, RunArtifact.relative_path == path)
        .order_by(RunArtifact.node_id.asc())
    ).all()
    assert first.duplicate is False
    assert second.duplicate is False
    assert len(artifacts) == 2
    assert {artifact.node_id for artifact in artifacts} == {node_a.id, node_b.id}
    assert artifacts[0].storage_key != artifacts[1].storage_key
    assert storage.objects[artifacts[0].storage_key] != storage.objects[artifacts[1].storage_key]

    duplicate = ingest_run_artifact(
        db_session,
        event_id=new_ulid(),
        run_id=result.run.id,
        node_id=node_a.id,
        authenticated_node_id=node_a.id,
        artifact_type="final_stats_csv",
        relative_path=path,
        declared_sha256=hashlib.sha256(data_a).hexdigest(),
        declared_size_bytes=len(data_a),
        file=BytesIO(data_a),
        content_type="text/csv",
    )
    assert duplicate.duplicate is True
    assert duplicate.artifact_id == first.artifact_id

    listed = list_run_artifacts_report(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, run_id=result.run.id
    )
    listed_json = listed.model_dump(by_alias=True)
    assert {
        (item["nodeId"], item["allocationId"], item["relativePath"], item["id"])
        for item in listed_json["items"]
    } == {
        (artifacts[1].node_id, artifacts[1].allocation_id, path, artifacts[1].id),
        (artifacts[0].node_id, artifacts[0].allocation_id, path, artifacts[0].id),
    }
    public_text = str(listed_json)
    assert "storageKey" not in public_text
    assert "run-artifacts/" not in public_text
    assert node_a.host not in public_text
    assert node_b.host not in public_text


def test_allocation_force_kill_releases_only_target_node(db_session: Session) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node_a = idle_node(db_session, user)
    node_b = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node_a.id,
            "selectedNodeIds": [node_a.id, node_b.id],
        },
    )
    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )
    allocation_b = db_session.scalar(
        select(RunNodeAllocation).where(
            RunNodeAllocation.run_id == result.run.id, RunNodeAllocation.node_id == node_b.id
        )
    )
    assert allocation_b is not None
    force_kill = enqueue_control_request(
        db_session,
        run=result.run,
        action="force_kill",
        reason="stop_grace_timeout",
        allocation=allocation_b,
    )
    force_kill.status = "running"

    complete_run_control_request(db_session, request=force_kill, success=True)

    lease_a = db_session.scalar(
        select(NodeLease).where(NodeLease.run_id == result.run.id, NodeLease.node_id == node_a.id)
    )
    lease_b = db_session.scalar(
        select(NodeLease).where(NodeLease.run_id == result.run.id, NodeLease.node_id == node_b.id)
    )
    assert lease_a is not None and lease_a.released_at is None
    assert lease_b is not None and lease_b.released_at is not None
    assert node_a.status == "busy"
    assert node_b.status == "idle"


def test_allocation_start_failure_quarantines_failed_node_and_schedules_cleanup(
    db_session: Session,
) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node_a = idle_node(db_session, user)
    node_b = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node_a.id,
            "selectedNodeIds": [node_a.id, node_b.id],
        },
    )
    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )
    start_b = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == result.run.id,
            RunControlRequest.node_id == node_b.id,
            RunControlRequest.action == "start",
        )
    )
    assert start_b is not None
    start_b.status = "running"

    complete_run_control_request(
        db_session,
        request=start_b,
        success=False,
        error_code="RUNNER_START_FAILED",
        error_message="Runner start command failed.",
        quarantine_node=True,
    )

    assert result.run.state == "initializing"
    assert result.run.failure_reason == "runner_start_failed"
    allocation_b = db_session.scalar(
        select(RunNodeAllocation).where(
            RunNodeAllocation.run_id == result.run.id, RunNodeAllocation.node_id == node_b.id
        )
    )
    force_kill_a = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == result.run.id,
            RunControlRequest.node_id == node_a.id,
            RunControlRequest.action == "force_kill",
            RunControlRequest.status == "pending",
        )
    )
    lease_a = db_session.scalar(
        select(NodeLease).where(NodeLease.run_id == result.run.id, NodeLease.node_id == node_a.id)
    )
    lease_b = db_session.scalar(
        select(NodeLease).where(NodeLease.run_id == result.run.id, NodeLease.node_id == node_b.id)
    )
    assert allocation_b is not None and allocation_b.state == "failed"
    assert force_kill_a is not None
    assert lease_a is not None and lease_a.released_at is None
    assert lease_b is not None and lease_b.released_at is not None
    assert node_a.status == "busy"
    assert node_b.status == "quarantined"


def terminal_callback(
    run_id: str,
    node_id: str,
    event_type: str,
    *,
    event_id: str,
    process_group_exited: bool = True,
    sla_result: str | None = None,
    reason: str | None = None,
) -> RunnerCallbackInput:
    details: dict[str, object] = {"processGroupExited": process_group_exited}
    if sla_result is not None:
        details["slaResult"] = sla_result
    if reason is not None:
        details["reason"] = reason
    return RunnerCallbackInput(
        schema_version="1",
        event_id=event_id,
        run_id=run_id,
        node_id=node_id,
        runtime_version="runtime-test-v1",
        event_type=event_type,
        seq=1,
        event_time=datetime.now(UTC),
        message="Callback received.",
        runner_pid=None,
        details=details,
        raw_payload={
            "schemaVersion": "1",
            "eventId": event_id,
            "runId": run_id,
            "nodeId": node_id,
            "runtimeVersion": "runtime-test-v1",
            "eventType": event_type,
            "seq": 1,
            "eventTime": "2030-06-01T10:00:00.000Z",
            "message": "Callback received.",
            "details": details,
        },
    )


def test_failed_allocation_enqueues_sibling_cleanup_without_terminal_run(
    db_session: Session,
) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node_a = idle_node(db_session, user)
    node_b = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node_a.id,
            "selectedNodeIds": [node_a.id, node_b.id],
        },
    )
    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )
    apply_runner_callback(
        db_session,
        callback=callback(result.run.id, node_a.id, "running", event_id=new_ulid()),
        request_id="req-running-a",
        authenticated_node_id=node_a.id,
    )
    apply_runner_callback(
        db_session,
        callback=callback(result.run.id, node_b.id, "running", event_id=new_ulid()),
        request_id="req-running-b",
        authenticated_node_id=node_b.id,
    )

    apply_runner_callback(
        db_session,
        callback=terminal_callback(
            result.run.id,
            node_a.id,
            "failed",
            event_id=new_ulid(),
            process_group_exited=True,
            sla_result="failed",
            reason="assertion_failed",
        ),
        request_id="req-failed-a",
        authenticated_node_id=node_a.id,
    )

    cleanup_b = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == result.run.id,
            RunControlRequest.node_id == node_b.id,
            RunControlRequest.action == "force_kill",
            RunControlRequest.status == "pending",
        )
    )
    assert result.run.state == "running"
    assert result.run.failure_reason == "assertion_failed"
    assert cleanup_b is not None


def test_standard_run_without_sla_rules_stays_not_evaluated_after_allocations_finish(
    db_session: Session,
) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node.id,
            "selectedNodeIds": [node.id],
        },
    )
    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )

    apply_runner_callback(
        db_session,
        callback=callback(result.run.id, node.id, "running", event_id=new_ulid()),
        request_id="req-running",
        authenticated_node_id=node.id,
    )
    apply_runner_callback(
        db_session,
        callback=terminal_callback(
            result.run.id,
            node.id,
            "finished",
            event_id=new_ulid(),
            process_group_exited=True,
            sla_result="passed",
        ),
        request_id="req-finished",
        authenticated_node_id=node.id,
    )

    assert result.run.state == "finished"
    assert result.run.sla_result == "not_evaluated"
    assert result.run.sla_result_reason is None


def test_required_sla_missing_allocation_verdict_is_not_evaluated(db_session: Session) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node.id,
            "selectedNodeIds": [node.id],
        },
    )
    now = datetime.now(UTC)
    db_session.add(
        TestPlanSlaRule(
            id=new_ulid(),
            workspace_id=DEFAULT_WORKSPACE_ID,
            test_plan_id=plan.id,
            enabled=True,
            position=0,
            subject="p95",
            label=None,
            condition="lte",
            threshold_value=500,
            threshold_unit="ms",
            timeframe_logic=None,
            timeframe_seconds=None,
            action="continue",
            created_at=now,
            updated_at=now,
        )
    )
    db_session.flush()
    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )

    apply_runner_callback(
        db_session,
        callback=callback(result.run.id, node.id, "running", event_id=new_ulid()),
        request_id="req-running-required-sla",
        authenticated_node_id=node.id,
    )
    apply_runner_callback(
        db_session,
        callback=terminal_callback(
            result.run.id,
            node.id,
            "finished",
            event_id=new_ulid(),
            process_group_exited=True,
        ),
        request_id="req-finished-required-sla",
        authenticated_node_id=node.id,
    )

    assert result.run.state == "finished"
    assert result.run.sla_result == "not_evaluated"
    assert result.run.sla_result_reason == "missing_sla_result"


def test_running_callback_ignores_duplicate_stopping_and_non_initializing_allocations(
    db_session: Session,
) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node.id,
            "selectedNodeIds": [node.id],
        },
    )
    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )
    first = apply_runner_callback(
        db_session,
        callback=callback(result.run.id, node.id, "running", event_id=new_ulid()),
        request_id="req-running-first",
        authenticated_node_id=node.id,
    )
    duplicate = apply_runner_callback(
        db_session,
        callback=callback(result.run.id, node.id, "running", event_id=new_ulid()),
        request_id="req-running-duplicate",
        authenticated_node_id=node.id,
    )
    assert first.state_changed is True
    assert duplicate.ignored_reason == "illegal_transition"

    request_stop(
        db_session,
        run=result.run,
        actor=user,
        request_id="stop-after-running",
    )
    stopped_running = apply_runner_callback(
        db_session,
        callback=callback(result.run.id, node.id, "running", event_id=new_ulid()),
        request_id="req-running-while-stopping",
        authenticated_node_id=node.id,
    )
    assert stopped_running.ignored_reason == "illegal_transition"

    node_c = idle_node(db_session, user)
    second = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
        resource_request={"mode": "manual", "selectedNodeIds": [node_c.id]},
    )
    second_allocation = db_session.scalar(
        select(RunNodeAllocation).where(RunNodeAllocation.run_id == second.run.id)
    )
    assert second_allocation is not None
    second_allocation.state = "stopping"
    non_initializing = apply_runner_callback(
        db_session,
        callback=callback(second.run.id, node_c.id, "running", event_id=new_ulid()),
        request_id="req-running-non-initializing",
        authenticated_node_id=node_c.id,
    )
    assert non_initializing.ignored_reason == "illegal_transition"


def test_start_failure_waits_for_sibling_cleanup_before_terminal_run(db_session: Session) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node_a = idle_node(db_session, user)
    node_b = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node_a.id,
            "selectedNodeIds": [node_a.id, node_b.id],
        },
    )
    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )
    start_a = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == result.run.id,
            RunControlRequest.node_id == node_a.id,
            RunControlRequest.action == "start",
        )
    )
    assert start_a is not None
    start_a.status = "running"

    complete_run_control_request(
        db_session,
        request=start_a,
        success=False,
        error_code="RUNNER_START_FAILED",
        error_message="Runner start command failed.",
        quarantine_node=True,
    )

    allocation_a = db_session.scalar(
        select(RunNodeAllocation).where(
            RunNodeAllocation.run_id == result.run.id,
            RunNodeAllocation.node_id == node_a.id,
        )
    )
    cleanup_b = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == result.run.id,
            RunControlRequest.node_id == node_b.id,
            RunControlRequest.action == "force_kill",
            RunControlRequest.status == "pending",
        )
    )
    assert allocation_a is not None and allocation_a.state == "failed"
    assert result.run.state == "initializing"
    assert result.run.failure_reason == "runner_start_failed"
    assert cleanup_b is not None


def test_force_kill_completion_terminalizes_allocation_and_then_run(db_session: Session) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node_a = idle_node(db_session, user)
    node_b = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node_a.id,
            "selectedNodeIds": [node_a.id, node_b.id],
        },
    )
    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )
    allocation_a, allocation_b = db_session.scalars(
        select(RunNodeAllocation)
        .where(RunNodeAllocation.run_id == result.run.id)
        .order_by(RunNodeAllocation.node_index.asc())
    ).all()
    allocation_a.state = "failed"
    allocation_a.ended_at = datetime.now(UTC)
    allocation_a.terminal_reason = "runner_start_failed"
    allocation_a.terminal_message = "Runner start failed."
    cleanup_b = enqueue_control_request(
        db_session,
        run=result.run,
        action="force_kill",
        reason="runner_start_failed",
        allocation=allocation_b,
    )
    cleanup_b.status = "running"

    complete_run_control_request(db_session, request=cleanup_b, success=True)

    assert allocation_b.state == "failed"
    assert allocation_b.ended_at is not None
    assert allocation_b.terminal_reason == "runner_start_failed"
    assert allocation_b.terminal_message == "Runner cleanup completed."
    assert allocation_b.cleanup_status == "released"
    assert allocation_b.quarantine_reason is None
    assert result.run.state == "failed"
    assert result.run.failure_reason == "runner_start_failed"


def test_accepted_timeout_converges_initializing_sibling_after_run_is_running(
    db_session: Session,
) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node_a = idle_node(db_session, user)
    node_b = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node_a.id,
            "selectedNodeIds": [node_a.id, node_b.id],
        },
    )
    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )
    now = datetime.now(UTC)
    result.run.state = "running"
    result.run.remote_start_requested_at = now - timedelta(minutes=2)
    allocation_a, allocation_b = db_session.scalars(
        select(RunNodeAllocation)
        .where(RunNodeAllocation.run_id == result.run.id)
        .order_by(RunNodeAllocation.node_index.asc())
    ).all()
    allocation_a.state = "running"
    allocation_a.accepted_at = now
    allocation_a.started_at = now
    allocation_a.last_heartbeat_at = now
    allocation_b.state = "initializing"
    allocation_b.accepted_at = None
    db_session.flush()

    converged = sweep_accepted_timeouts(db_session, now=now, timeout_seconds=60)

    cleanup_a = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == result.run.id,
            RunControlRequest.node_id == node_a.id,
            RunControlRequest.action == "force_kill",
            RunControlRequest.status == "pending",
        )
    )
    cleanup_b = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == result.run.id,
            RunControlRequest.node_id == node_b.id,
            RunControlRequest.action == "force_kill",
            RunControlRequest.status == "pending",
        )
    )
    assert converged == 1
    assert allocation_a.state == "running"
    assert allocation_b.state == "failed"
    assert allocation_b.terminal_reason == "runner_accept_timeout"
    assert result.run.state == "running"
    assert result.run.failure_reason == "runner_accept_timeout"
    assert cleanup_a is not None
    assert cleanup_b is not None


def test_worker_executes_pending_sibling_start_after_run_is_running(
    db_session: Session,
) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node_a = idle_node(db_session, user)
    node_b = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node_a.id,
            "selectedNodeIds": [node_a.id, node_b.id],
        },
    )
    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )
    request_a = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == result.run.id,
            RunControlRequest.node_id == node_a.id,
            RunControlRequest.action == "start",
        )
    )
    request_b = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == result.run.id,
            RunControlRequest.node_id == node_b.id,
            RunControlRequest.action == "start",
        )
    )
    assert request_a is not None and request_b is not None
    request_a.status = "succeeded"
    request_a.finished_at = datetime.now(UTC)
    apply_runner_callback(
        db_session,
        callback=callback(result.run.id, node_a.id, "running", event_id=new_ulid()),
        request_id="req-node-a-running-before-node-b-start",
        authenticated_node_id=node_a.id,
    )
    db_session.commit()
    factory = sessionmaker(
        bind=db_session.get_bind(), autoflush=False, expire_on_commit=False, future=True
    )
    executor = RecordingRunControlExecutor()

    assert run_once(factory, run_control_executor=executor) >= 1

    db_session.expire_all()
    request_b = db_session.get(RunControlRequest, request_b.id)
    assert request_b is not None
    assert request_b.status == "succeeded"
    assert request_b.last_error_code is None
    assert [command.node_id for command in executor.commands] == [node_b.id]
    assert db_session.get(Run, result.run.id).state == "running"


def test_stale_start_recovery_keeps_sibling_start_when_run_is_running(
    db_session: Session,
) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node_a = idle_node(db_session, user)
    node_b = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node_a.id,
            "selectedNodeIds": [node_a.id, node_b.id],
        },
    )
    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )
    now = datetime.now(UTC)
    request_b = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == result.run.id,
            RunControlRequest.node_id == node_b.id,
            RunControlRequest.action == "start",
        )
    )
    assert request_b is not None
    request_b.status = "running"
    request_b.claimed_at = now - timedelta(seconds=120)
    request_b.claimed_by = "worker-crashed"
    result.run.state = "running"
    db_session.flush()

    recovered = recover_stale_run_control_requests(db_session, now=now, stale_seconds=60)

    assert recovered == 1
    assert request_b.status == "pending"
    assert request_b.claimed_at is None
    assert request_b.claimed_by is None
    assert request_b.last_error_code == "RUN_CONTROL_STALE_RETRY"


def test_stale_start_recovery_cancels_obsolete_allocation_start(
    db_session: Session,
) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node_a = idle_node(db_session, user)
    node_b = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node_a.id,
            "selectedNodeIds": [node_a.id, node_b.id],
        },
    )
    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )
    now = datetime.now(UTC)
    request_b = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == result.run.id,
            RunControlRequest.node_id == node_b.id,
            RunControlRequest.action == "start",
        )
    )
    allocation_b = db_session.scalar(
        select(RunNodeAllocation).where(
            RunNodeAllocation.run_id == result.run.id,
            RunNodeAllocation.node_id == node_b.id,
        )
    )
    assert request_b is not None
    assert allocation_b is not None
    request_b.status = "running"
    request_b.claimed_at = now - timedelta(seconds=120)
    request_b.claimed_by = "worker-crashed-after-success"
    result.run.state = "running"
    allocation_b.state = "running"
    db_session.flush()

    recovered = recover_stale_run_control_requests(db_session, now=now, stale_seconds=60)

    assert recovered == 1
    assert request_b.status == "cancelled"
    assert request_b.finished_at == now
    assert request_b.claimed_by is None
    assert request_b.last_error_code == "RUN_CONTROL_OBSOLETE"


def test_heartbeat_timeout_converges_only_stale_allocation(db_session: Session) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node_a = idle_node(db_session, user)
    node_b = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node_a.id,
            "selectedNodeIds": [node_a.id, node_b.id],
        },
    )
    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )
    now = datetime.now(UTC)
    result.run.state = "running"
    result.run.started_at = now
    result.run.last_heartbeat_at = now
    allocation_a, allocation_b = db_session.scalars(
        select(RunNodeAllocation)
        .where(RunNodeAllocation.run_id == result.run.id)
        .order_by(RunNodeAllocation.node_index.asc())
    ).all()
    allocation_a.state = "running"
    allocation_a.started_at = now
    allocation_a.last_heartbeat_at = now
    allocation_b.state = "running"
    allocation_b.started_at = now
    allocation_b.last_heartbeat_at = now - timedelta(minutes=2)
    db_session.flush()

    converged = sweep_heartbeat_timeouts(db_session, now=now, timeout_seconds=60)

    cleanup_a = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == result.run.id,
            RunControlRequest.node_id == node_a.id,
            RunControlRequest.action == "force_kill",
            RunControlRequest.status == "pending",
        )
    )
    cleanup_b = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == result.run.id,
            RunControlRequest.node_id == node_b.id,
            RunControlRequest.action == "force_kill",
            RunControlRequest.status == "pending",
        )
    )
    assert converged == 1
    assert allocation_a.state == "running"
    assert allocation_b.state == "failed"
    assert allocation_b.terminal_reason == "heartbeat_timeout"
    assert result.run.state == "running"
    assert result.run.failure_reason == "heartbeat_timeout"
    assert cleanup_a is not None
    assert cleanup_b is not None


def test_single_node_busy_and_multi_node_unavailable_error_codes(db_session: Session) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    busy = idle_node(db_session, user, status="busy")
    idle = idle_node(db_session, user)
    single = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": busy.id,
            "selectedNodeIds": [busy.id],
        },
    )
    multi = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": busy.id,
            "selectedNodeIds": [busy.id, idle.id],
        },
    )
    db_session.commit()

    with pytest.raises(AppError) as single_exc:
        create_test_plan_run(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            source_id=single.id,
            expected_source_revision=1,
            run_type="standard",
            confirm_high_concurrency=True,
        )
    with pytest.raises(AppError) as multi_exc:
        create_test_plan_run(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            source_id=multi.id,
            expected_source_revision=1,
            run_type="standard",
            confirm_high_concurrency=True,
        )

    assert single_exc.value.code == "LOAD_NODE_BUSY"
    assert multi_exc.value.code == "LOAD_NODE_UNAVAILABLE"


def test_node_bound_runner_token_requires_ulid_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUNNER_INTERNAL_TOKEN", "runner-secret")
    from app.services.runs import validate_runner_token

    with pytest.raises(AppError) as invalid_exc:
        validate_runner_token("runner-secret:node:not-a-ulid", node_id=new_ulid())

    assert invalid_exc.value.code == "RUNNER_UNAUTHORIZED"


def test_test_plan_create_patch_and_clone_validate_all_selected_nodes(
    db_session: Session,
) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node_a = idle_node(db_session, user)
    archived = idle_node(db_session, user)
    archived.archived_at = datetime.now(UTC)
    scn = scenario(db_session, user)
    base_payload = {
        "name": "Resource validation plan",
        "description": None,
        "tags": [],
        "envGroupId": None,
        "runMode": "sequential",
        "resource": {
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node_a.id,
            "selectedNodeIds": [node_a.id],
            "nodeCount": None,
        },
        "scenarioItems": [
            {
                "id": new_ulid(),
                "scenarioId": scn.id,
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

    bad_payload = {
        **base_payload,
        "resource": {
            **base_payload["resource"],
            "selectedNodeId": node_a.id,
            "selectedNodeIds": [node_a.id, archived.id],
        },
    }
    with pytest.raises(AppError) as create_exc:
        create_test_plan(
            db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, payload=bad_payload
        )
    assert create_exc.value.code == "RESOURCE_NOT_FOUND"

    public_mismatch_payload = {
        **base_payload,
        "resource": {
            **base_payload["resource"],
            "poolType": "public",
            "selectedNodeIds": [node_a.id],
        },
    }
    with pytest.raises(AppError) as public_exc:
        create_test_plan(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            payload=public_mismatch_payload,
        )
    assert public_exc.value.code == "RESOURCE_NOT_FOUND"

    user.role = "admin"
    public_node = create_load_node(
        db_session,
        actor=user,
        workspace_id=DEFAULT_WORKSPACE_ID,
        scope="public",
        host=f"public-{new_ulid().lower()}.internal",
        ssh_port=22,
        ssh_user="surgepilot",
        runner_home="/opt/surgepilot/runner",
        credential=credential(),
        ssh_host_key=trusted_host_key(),
        maintainer=None,
        remark=None,
    )
    public_node.status = "idle"
    private_mismatch_payload = {
        **base_payload,
        "resource": {
            **base_payload["resource"],
            "selectedNodeId": public_node.id,
            "selectedNodeIds": [public_node.id],
        },
    }
    with pytest.raises(AppError) as private_exc:
        create_test_plan(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            payload=private_mismatch_payload,
        )
    assert private_exc.value.code == "RESOURCE_NOT_FOUND"

    plan = create_test_plan(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, payload=base_payload
    )
    with pytest.raises(AppError) as patch_exc:
        patch_test_plan(
            db_session,
            plan=plan,
            actor=user,
            expected_revision=plan.revision,
            payload={**bad_payload, "expectedRevision": plan.revision},
        )
    assert patch_exc.value.code == "RESOURCE_NOT_FOUND"

    plan.selected_node_ids_json = [node_a.id, archived.id]
    db_session.flush()
    with pytest.raises(AppError) as clone_exc:
        clone_test_plan(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            test_plan_id=plan.id,
            actor=user,
            name=None,
        )
    assert clone_exc.value.code == "RESOURCE_NOT_FOUND"


@pytest.mark.anyio
async def test_internal_runner_route_rejects_node_bound_token_mismatch(
    client: AsyncClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RUNNER_INTERNAL_TOKEN", "runner-secret")
    user = actor()
    db_session.add(user)
    db_session.flush()
    node_a = idle_node(db_session, user)
    node_b = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node_a.id,
            "selectedNodeIds": [node_a.id, node_b.id],
        },
    )
    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )
    payload = {
        "schemaVersion": "1",
        "eventId": new_ulid(),
        "runId": result.run.id,
        "nodeId": node_b.id,
        "runtimeVersion": "runtime-test-v1",
        "eventType": "running",
        "seq": 1,
        "eventTime": "2030-06-01T10:00:00.000Z",
        "details": {},
    }

    mismatch = await client.post(
        "/api/internal/v1/runner/callbacks",
        headers={"x-runner-token": signed_node_bound_token("runner-secret", node_a.id)},
        json=payload,
    )
    accepted = await client.post(
        "/api/internal/v1/runner/callbacks",
        headers={"x-runner-token": signed_node_bound_token("runner-secret", node_b.id)},
        json={**payload, "eventId": new_ulid()},
    )

    assert mismatch.status_code == 403
    assert mismatch.json()["code"] == "RUNNER_FORBIDDEN"
    assert accepted.status_code == 200
    assert accepted.json()["stateChanged"] is True


@pytest.mark.anyio
async def test_internal_runner_artifact_route_rejects_node_bound_token_mismatch(
    client: AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUNNER_INTERNAL_TOKEN", "runner-secret")
    user = actor()
    db_session.add(user)
    db_session.flush()
    node_a = idle_node(db_session, user)
    node_b = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node_a.id,
            "selectedNodeIds": [node_a.id, node_b.id],
        },
    )
    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )
    data = b"node-b-log"

    response = await client.post(
        "/api/internal/v1/runner/artifacts",
        headers={"x-runner-token": signed_node_bound_token("runner-secret", node_a.id)},
        data={
            "schemaVersion": "1",
            "eventId": new_ulid(),
            "runId": result.run.id,
            "nodeId": node_b.id,
            "runtimeVersion": "runtime-test-v1",
            "artifactType": "run_log",
            "relativePath": "logs/node-b.log",
            "sha256": hashlib.sha256(data).hexdigest(),
            "sizeBytes": str(len(data)),
        },
        files={"file": ("node-b.log", data, "text/plain")},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "RUNNER_FORBIDDEN"
    assert db_session.scalar(select(RunArtifact).where(RunArtifact.run_id == result.run.id)) is None


def test_run_report_exposes_redacted_allocation_rows(db_session: Session) -> None:
    user = actor()
    db_session.add(user)
    db_session.flush()
    node_a = idle_node(db_session, user)
    node_b = idle_node(db_session, user)
    plan = make_test_plan(
        db_session,
        user,
        resource={
            "mode": "manual",
            "poolType": "private",
            "selectedNodeId": node_a.id,
            "selectedNodeIds": [node_a.id, node_b.id],
        },
    )
    result = create_test_plan_run(
        db_session,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
        source_id=plan.id,
        expected_source_revision=1,
        run_type="standard",
        confirm_high_concurrency=True,
    )

    report = get_run_report(db_session, workspace_id=DEFAULT_WORKSPACE_ID, run_id=result.run.id)

    assert [node.node_index for node in report.allocated_nodes] == [1, 2]
    assert [node.total_nodes for node in report.allocated_nodes] == [2, 2]
    assert report.snapshot.resource_request is not None
    assert report.snapshot.resource_request.selected_node_ids == [node_a.id, node_b.id]
    public_json = report.model_dump(by_alias=True)
    public_text = str(public_json)
    assert "sshUser" not in public_text
    assert "runnerHome" not in public_text
    assert node_a.host not in public_text
