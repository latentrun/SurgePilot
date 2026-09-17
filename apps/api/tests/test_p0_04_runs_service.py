from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.ids import new_ulid
from app.models.auth import DEFAULT_WORKSPACE_ID, AuditEvent, User
from app.models.load_nodes import LoadNode
from app.models.runs import (
    NodeLease,
    Run,
    RunArtifact,
    RunControlRequest,
    RunnerCallbackEvent,
    RunNodeAllocation,
)
from app.schemas.load_nodes import LoadNodeCredentialInput
from app.services.load_nodes import create_load_node
from app.services.runs import (
    RUN_TRANSITIONS,
    CallbackResult,
    RunExecutionInput,
    RunnerCallbackInput,
    complete_run_control_request,
    create_run_execution,
    create_protocol_smoke_run,
    request_stop,
    apply_runner_callback as service_apply_runner_callback,
    sweep_accepted_timeouts,
    sweep_heartbeat_timeouts,
    sweep_stop_grace_timeouts,
)


def actor() -> User:
    now = datetime.now(UTC)
    return User(
        id="01HZX3Y9M0E9W7Z6M5QK9S8P7B",
        email="runner@example.com",
        display_name="Runner User",
        password_hash="hash",
        role="user",
        status="active",
        failed_login_count=0,
        created_at=now,
        updated_at=now,
    )


def credential() -> LoadNodeCredentialInput:
    return LoadNodeCredentialInput(authType="password", password="secret-password")


def trusted_host_key() -> dict[str, str]:
    return {
        "algorithm": "ssh-ed25519",
        "publicKey": "AAAAC3NzaC1lZDI1NTE5AAAAIF6W/+2uAKbK71edPOwIYEGmhaggGtRy5wu0lXPVysEC",
        "fingerprintSha256": "SHA256:SurgePilotTrustedHostKey",
    }


def idle_node(db_session: Session, user: User | None = None) -> LoadNode:
    user = user or actor()
    db_session.add(user)
    db_session.flush()
    node = create_load_node(
        db_session,
        actor=user,
        workspace_id=DEFAULT_WORKSPACE_ID,
        scope="workspace",
        host=f"run-node-{new_ulid().lower()}.internal",
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


def callback(
    run: Run,
    event_type: str,
    *,
    event_id: str,
    node_id: str | None = None,
    runner_pid: int | None = None,
    details: dict | None = None,
    runtime_version: str = "runtime-test-v1",
) -> RunnerCallbackInput:
    return RunnerCallbackInput(
        schema_version="1",
        event_id=event_id,
        run_id=run.id,
        node_id=node_id or run.selected_node_id,
        runtime_version=runtime_version,
        event_type=event_type,
        seq=1,
        event_time=datetime.now(UTC),
        message="Callback received.",
        runner_pid=runner_pid,
        details=details or {},
        raw_payload={
            "schemaVersion": "1",
            "eventId": event_id,
            "runId": run.id,
            "nodeId": node_id or run.selected_node_id,
            "runtimeVersion": runtime_version,
            "eventType": event_type,
            "seq": 1,
            "eventTime": "2030-06-01T10:00:00.000Z",
            "message": "Callback received.",
            **({"runnerPid": runner_pid} if runner_pid is not None else {}),
            "details": details or {},
        },
    )


def apply_runner_callback(
    db: Session,
    *,
    callback: RunnerCallbackInput,
    request_id: str,
    authenticated_node_id: str | None | object = ...,
) -> CallbackResult:
    if authenticated_node_id is ...:
        authenticated_node_id = callback.node_id
    return service_apply_runner_callback(
        db,
        callback=callback,
        request_id=request_id,
        authenticated_node_id=authenticated_node_id,
    )


def test_run_creation_creates_snapshot_lease_busy_node_and_start_request(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)

    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )

    assert run.state == "initializing"
    assert run.snapshot is not None
    assert run.snapshot.snapshot_json["sourceType"] == "protocol_smoke"
    lease = db_session.scalar(select(NodeLease).where(NodeLease.run_id == run.id))
    assert lease is not None
    assert lease.released_at is None
    assert node.status == "busy"
    assert node.current_run_id == run.id
    allocation = db_session.scalar(
        select(RunNodeAllocation).where(RunNodeAllocation.run_id == run.id)
    )
    assert allocation is not None
    assert allocation.expected_runtime_version == "runtime-test-v1"
    request = db_session.scalar(select(RunControlRequest).where(RunControlRequest.run_id == run.id))
    assert request is not None
    assert request.action == "start"


def test_runner_callback_uses_allocation_runtime_after_configuration_changes(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )

    accepted = callback(
        run,
        "accepted",
        event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7C",
        runner_pid=1234,
    )

    first = apply_runner_callback(db_session, callback=accepted, request_id="req-runtime-v1")
    monkeypatch.setenv("LOAD_NODE_RUNTIME_VERSION", "runtime-test-v2")
    heartbeat = apply_runner_callback(
        db_session,
        callback=callback(
            run,
            "heartbeat",
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7E",
        ),
        request_id="req-runtime-v1-heartbeat",
    )
    duplicate = apply_runner_callback(
        db_session, callback=accepted, request_id="req-runtime-v1-duplicate"
    )

    assert first.accepted is True
    assert heartbeat.accepted is True
    assert duplicate.duplicate is True


def test_runner_callback_rejects_runtime_that_differs_from_allocation(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )

    with pytest.raises(AppError) as exc:
        apply_runner_callback(
            db_session,
            callback=callback(
                run,
                "accepted",
                event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7D",
                runtime_version="runtime-test-v2",
            ),
            request_id="req-runtime-v2",
        )

    assert exc.value.code == "RUNNER_RUNTIME_MISMATCH"


def test_generic_run_execution_service_creates_already_validated_run(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)

    run = create_run_execution(
        db_session,
        RunExecutionInput(
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            selected_node_id=node.id,
            run_type="debug",
            source_type="protocol_smoke",
            source_id=None,
            snapshot_payload={"protocolSchemaVersion": 1, "sourceType": "protocol_smoke"},
        ),
    )

    assert run.state == "initializing"
    assert run.snapshot is not None
    assert run.snapshot.snapshot_json["sourceType"] == "protocol_smoke"
    assert node.status == "busy"
    assert node.current_run_id == run.id
    request = db_session.scalar(select(RunControlRequest).where(RunControlRequest.run_id == run.id))
    assert request is not None
    assert request.action == "start"


def test_protocol_smoke_creation_requires_guard(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "false")
    user = actor()
    node = idle_node(db_session, user)

    with pytest.raises(AppError) as exc:
        create_protocol_smoke_run(
            db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
        )

    assert exc.value.code == "RUN_CREATION_NOT_ALLOWED"


def test_active_lease_unique_index_prevents_double_allocation(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    first = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )

    with pytest.raises(AppError) as exc:
        create_protocol_smoke_run(
            db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
        )

    assert first.id != ""
    assert exc.value.code == "LOAD_NODE_BUSY"


def test_transition_table_covers_expected_states() -> None:
    assert RUN_TRANSITIONS["running"] == {"initializing"}
    assert RUN_TRANSITIONS["finished"] == {"running"}
    assert RUN_TRANSITIONS["aborted"] == {"initializing", "running", "stopping"}
    assert RUN_TRANSITIONS["failed"] == {"initializing", "running", "stopping"}


def test_callback_details_are_sanitized_and_outcomes_logged(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )

    with caplog.at_level("INFO", logger="app.services.runs"):
        first = apply_runner_callback(
            db_session,
            callback=callback(
                run,
                "running",
                event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7S",
                details={
                    "token": "super-secret-token",
                    "nested": {"Authorization": "Bearer secret-token"},
                    "safe": "kept",
                },
            ),
            request_id="req-secret",
        )
        duplicate = apply_runner_callback(
            db_session,
            callback=callback(
                run,
                "running",
                event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7S",
                details={
                    "token": "super-secret-token",
                    "nested": {"Authorization": "Bearer secret-token"},
                    "safe": "kept",
                },
            ),
            request_id="req-secret-duplicate",
        )

    assert first.state_changed is True
    assert duplicate.duplicate is True
    event = db_session.scalar(
        select(RunnerCallbackEvent).where(
            RunnerCallbackEvent.event_id == "01HZX3Y9M0E9W7Z6M5QK9S8P7S"
        )
    )
    assert event is not None
    assert event.payload_json["details"]["token"] == "[REDACTED]"
    assert event.payload_json["details"]["nested"]["Authorization"] == "[REDACTED]"
    assert event.payload_json["details"]["safe"] == "kept"
    assert "super-secret-token" not in str(event.payload_json)
    messages = [record.getMessage() for record in caplog.records]
    assert "Runner callback applied" in messages
    assert "Runner callback duplicate ignored" in messages


def test_callback_sanitizer_handles_nested_sequences_depth_and_sensitive_values() -> None:
    from app.services.runs import _sanitize_callback_value

    sanitized = _sanitize_callback_value(
        {
            "items": ["Bearer visible-token", ("safe", {"apiKey": "hidden"})],
            "deep": {"a": {"b": {"c": {"d": {"e": {"f": {"g": "too deep"}}}}}}},
        }
    )

    assert sanitized["items"] == ["[REDACTED]", ["safe", {"apiKey": "[REDACTED]"}]]
    assert sanitized["deep"]["a"]["b"]["c"]["d"]["e"]["f"]["g"] == "[TRUNCATED]"


def test_callbacks_apply_state_and_terminal_release(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )

    accepted = apply_runner_callback(
        db_session,
        callback=callback(run, "accepted", event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7C", runner_pid=1234),
        request_id="req-1",
    )
    assert accepted == CallbackResult(True, False, False, "initializing", None)
    assert run.accepted_at is not None
    assert run.runner_pid == 1234

    running = apply_runner_callback(
        db_session,
        callback=callback(run, "running", event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7D"),
        request_id="req-2",
    )
    assert running.state_changed is True
    assert run.state == "running"
    heartbeat = apply_runner_callback(
        db_session,
        callback=callback(run, "heartbeat", event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7E"),
        request_id="req-3",
    )
    assert heartbeat.state_changed is False
    assert run.state == "running"
    assert run.last_heartbeat_at is not None

    finished = apply_runner_callback(
        db_session,
        callback=callback(
            run,
            "finished",
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7F",
            details={"processGroupExited": True},
        ),
        request_id="req-4",
    )
    assert finished.state_changed is True
    assert run.state == "finished"
    assert run.ended_at is not None
    lease = db_session.scalar(select(NodeLease).where(NodeLease.run_id == run.id))
    assert lease is not None
    assert lease.released_at is not None
    assert node.status == "idle"
    assert node.current_run_id is None


def test_terminal_state_cannot_be_overwritten_by_late_callback(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    apply_runner_callback(
        db_session,
        callback=callback(
            run,
            "running",
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7E",
        ),
        request_id="req-0",
    )
    apply_runner_callback(
        db_session,
        callback=callback(
            run,
            "finished",
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7F",
            details={"processGroupExited": True},
        ),
        request_id="req-1",
    )

    late = apply_runner_callback(
        db_session,
        callback=callback(
            run,
            "failed",
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7G",
            details={"processGroupExited": True, "reason": "runner_exit_nonzero"},
        ),
        request_id="req-2",
    )

    assert late.current_state == "finished"
    assert late.ignored_reason == "terminal_state_protected"
    assert run.state == "finished"


def test_duplicate_callback_same_hash_is_noop_and_different_hash_conflicts(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    first = callback(run, "accepted", event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7C", runner_pid=1234)
    apply_runner_callback(db_session, callback=first, request_id="req-1")

    duplicate = apply_runner_callback(db_session, callback=first, request_id="req-2")
    assert duplicate.duplicate is True
    event = db_session.scalar(
        select(RunnerCallbackEvent).where(RunnerCallbackEvent.run_id == run.id)
    )
    assert event is not None
    assert event.duplicate_count == 1

    changed = callback(run, "accepted", event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7C", runner_pid=9999)
    with pytest.raises(AppError) as exc:
        apply_runner_callback(db_session, callback=changed, request_id="req-3")
    assert exc.value.code == "RUNNER_CALLBACK_CONFLICT"


def test_stop_is_idempotent_and_terminal_stop_fails(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )

    first = request_stop(db_session, run=run, actor=user, request_id="req-stop")
    assert first.duplicate is False
    assert first.status_code == 202
    assert run.state == "stopping"
    assert len([request for request in run.control_requests if request.action == "stop"]) == 1

    duplicate = request_stop(db_session, run=run, actor=user, request_id="req-stop-2")
    assert duplicate.duplicate is True
    assert duplicate.status_code == 200
    assert len([request for request in run.control_requests if request.action == "stop"]) == 1

    run.state = "aborted"
    db_session.flush()
    with pytest.raises(AppError) as exc:
        request_stop(db_session, run=run, actor=user, request_id="req-stop-3")
    assert exc.value.code == "RUN_TERMINAL_STATE"


def test_request_stop_by_id_locks_latest_terminal_state(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.runs import request_stop_by_id

    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    run.state = "finished"
    db_session.flush()

    with pytest.raises(AppError) as exc:
        request_stop_by_id(db_session, run_id=run.id, workspace_id=DEFAULT_WORKSPACE_ID, actor=user)

    assert exc.value.code == "RUN_TERMINAL_STATE"
    assert run.state == "finished"


def test_runner_node_mismatch_is_forbidden(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )

    with pytest.raises(AppError) as exc:
        apply_runner_callback(
            db_session,
            callback=callback(
                run,
                "accepted",
                event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7C",
                node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7Z",
                runner_pid=1234,
            ),
            request_id="req-1",
        )
    assert exc.value.code == "RUNNER_FORBIDDEN"


def test_timeout_sweeps_keep_nodes_unavailable_until_force_kill_completion(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    old = datetime.now(UTC) - timedelta(seconds=500)
    run.remote_start_requested_at = old
    run.created_at = old
    db_session.flush()

    assert sweep_accepted_timeouts(db_session, now=datetime.now(UTC), timeout_seconds=120) == 1
    assert run.state == "failed"
    assert run.failure_reason == "runner_accept_timeout"
    assert node.status == "busy"
    assert node.current_run_id == run.id
    lease = db_session.scalar(select(NodeLease).where(NodeLease.run_id == run.id))
    assert lease is not None and lease.released_at is None
    force_kill = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == run.id,
            RunControlRequest.action == "force_kill",
            RunControlRequest.status == "pending",
        )
    )
    assert force_kill is not None

    complete_run_control_request(db_session, request=force_kill, success=True)
    assert node.status == "idle"
    assert node.current_run_id is None
    assert node.last_force_kill_at is not None
    assert run.last_force_kill_at is not None
    assert lease.released_at is not None
    assert lease.release_reason == "force_kill_success"

    node2 = idle_node(db_session, user)
    run2 = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node2.id
    )
    run2.state = "running"
    run2.started_at = old
    run2.last_heartbeat_at = None
    allocation2 = db_session.scalar(
        select(RunNodeAllocation).where(RunNodeAllocation.run_id == run2.id)
    )
    assert allocation2 is not None
    allocation2.state = "running"
    allocation2.started_at = old
    allocation2.last_heartbeat_at = None
    db_session.flush()
    assert sweep_heartbeat_timeouts(db_session, now=datetime.now(UTC), timeout_seconds=60) == 1
    assert run2.state == "failed"
    assert run2.failure_reason == "heartbeat_timeout"
    assert node2.status == "busy"
    assert node2.current_run_id == run2.id

    node3 = idle_node(db_session, user)
    run3 = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node3.id
    )
    run3.state = "stopping"
    run3.stop_requested_at = old
    db_session.flush()
    assert sweep_stop_grace_timeouts(db_session, now=datetime.now(UTC), timeout_seconds=60) == 1
    assert run3.state == "aborted"
    assert run3.forced_convergence is True
    assert run3.failure_reason == "stop_grace_timeout"
    assert node3.status == "busy"
    force_kill3 = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == run3.id,
            RunControlRequest.action == "force_kill",
            RunControlRequest.status == "pending",
        )
    )
    assert force_kill3 is not None

    complete_run_control_request(db_session, request=force_kill3, success=False)
    assert node3.status == "quarantined"
    assert node3.current_run_id is None
    lease3 = db_session.scalar(select(NodeLease).where(NodeLease.run_id == run3.id))
    assert lease3 is not None and lease3.released_at is not None
    assert lease3.release_reason == "force_kill_failed"
    quarantined_event = db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.event_type == "load_node.quarantined",
            AuditEvent.target_id == node3.id,
        )
    )
    assert quarantined_event is not None
    assert quarantined_event.details_json["recoveryHint"] == (
        "Manually confirm and clean residual processes and Monitoring secrets, then disable, "
        "enable, and reinitialize this Load Node."
    )


def test_uncertain_start_failure_keeps_lease_until_same_allocation_force_kill(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    allocation = db_session.scalar(
        select(RunNodeAllocation).where(RunNodeAllocation.run_id == run.id)
    )
    start_request = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == run.id,
            RunControlRequest.action == "start",
        )
    )
    lease = db_session.scalar(select(NodeLease).where(NodeLease.run_id == run.id))
    assert allocation is not None
    assert start_request is not None
    assert lease is not None

    complete_run_control_request(
        db_session,
        request=start_request,
        success=False,
        error_code="RUN_CONTROL_TIMEOUT",
        error_message="Run control command timed out.",
        timed_out=True,
        quarantine_node=False,
        cleanup_required=True,
    )

    force_kill = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == run.id,
            RunControlRequest.allocation_id == allocation.id,
            RunControlRequest.action == "force_kill",
            RunControlRequest.status == "pending",
        )
    )
    assert run.state == "failed"
    assert allocation.state == "failed"
    assert force_kill is not None
    assert node.status == "busy"
    assert node.current_run_id == run.id
    assert lease.released_at is None


def test_force_kill_host_key_failure_releases_to_uninitialized_without_quarantine(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    old = datetime.now(UTC) - timedelta(seconds=500)
    run.state = "stopping"
    run.stop_requested_at = old
    db_session.flush()
    assert sweep_stop_grace_timeouts(db_session, now=datetime.now(UTC), timeout_seconds=60) == 1
    request = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == run.id,
            RunControlRequest.action == "force_kill",
            RunControlRequest.status == "pending",
        )
    )
    assert request is not None

    complete_run_control_request(
        db_session,
        request=request,
        success=False,
        error_code="RUN_CONTROL_SSH_HOST_KEY_CHANGED",
        error_message="Run control SSH host key verification failed.",
        quarantine_node=False,
    )

    assert node.status == "uninitialized"
    assert node.current_run_id is None
    assert node.last_status_reason == "RUN_CONTROL_SSH_HOST_KEY_CHANGED"
    lease = db_session.scalar(select(NodeLease).where(NodeLease.run_id == run.id))
    assert lease is not None and lease.released_at is not None
    assert lease.release_reason == "force_kill_failed"
    quarantined = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "load_node.quarantined")
    ).all()
    assert quarantined == []


def test_accepted_but_not_running_times_out_and_waits_for_force_kill(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    old = datetime.now(UTC) - timedelta(seconds=500)
    run.remote_start_requested_at = old
    run.accepted_at = old
    run.started_at = None
    run.last_heartbeat_at = None
    allocation = db_session.scalar(
        select(RunNodeAllocation).where(RunNodeAllocation.run_id == run.id)
    )
    assert allocation is not None
    allocation.accepted_at = old
    allocation.started_at = None
    db_session.flush()

    assert sweep_heartbeat_timeouts(db_session, now=datetime.now(UTC), timeout_seconds=60) == 1

    assert run.state == "failed"
    assert run.failure_reason == "runner_start_timeout"
    assert node.status == "busy"
    assert node.current_run_id == run.id
    force_kill = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == run.id,
            RunControlRequest.action == "force_kill",
            RunControlRequest.status == "pending",
        )
    )
    assert force_kill is not None
    assert force_kill.reason == "runner_start_timeout"


def test_stale_running_force_kill_request_is_reset_for_retry(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.runs import enqueue_control_request, recover_stale_run_control_requests

    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    start_request = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == run.id, RunControlRequest.action == "start"
        )
    )
    assert start_request is not None
    start_request.status = "cancelled"
    run.state = "failed"
    allocation = db_session.scalar(
        select(RunNodeAllocation).where(RunNodeAllocation.run_id == run.id)
    )
    assert allocation is not None
    force_kill = enqueue_control_request(
        db_session,
        run=run,
        action="force_kill",
        reason="heartbeat_timeout",
        allocation=allocation,
    )
    old = datetime.now(UTC) - timedelta(seconds=500)
    force_kill.status = "running"
    force_kill.claimed_at = old
    force_kill.claimed_by = "dead-worker"
    db_session.flush()

    assert (
        recover_stale_run_control_requests(db_session, now=datetime.now(UTC), stale_seconds=120)
        == 1
    )

    assert force_kill.status == "pending"
    assert force_kill.claimed_at is None
    assert force_kill.claimed_by is None
    assert force_kill.last_error_code == "RUN_CONTROL_STALE_RETRY"
    assert node.status == "busy"


def test_stale_terminal_lease_enqueues_force_kill_before_release(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.runs import recover_stale_leases

    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    start_request = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == run.id, RunControlRequest.action == "start"
        )
    )
    assert start_request is not None
    start_request.status = "cancelled"
    run.state = "failed"
    db_session.flush()

    assert recover_stale_leases(db_session) == 1

    force_kill = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == run.id,
            RunControlRequest.action == "force_kill",
            RunControlRequest.status == "pending",
        )
    )
    lease = db_session.scalar(select(NodeLease).where(NodeLease.run_id == run.id))
    assert force_kill is not None
    assert force_kill.reason == "stale_recovery"
    assert lease is not None and lease.released_at is None
    assert node.status == "busy"


class FakePut:
    def __init__(self, size_bytes: int, sha256: str) -> None:
        self.size_bytes = size_bytes
        self.sha256 = sha256


class FakeStorage:
    def __init__(self, *, size: int | None = None, sha256: str | None = None) -> None:
        self.size = size
        self.sha256 = sha256
        self.deleted: list[tuple[str, str]] = []
        self.objects: dict[str, bytes] = {}

    def put_stream(self, *, bucket, object_key, stream, size_limit, content_type=None):
        data = stream.read()
        self.objects[object_key] = data
        return FakePut(
            self.size if self.size is not None else len(data),
            self.sha256 or __import__("hashlib").sha256(data).hexdigest(),
        )

    def copy_object(self, *, bucket, source_key, destination_key) -> None:
        self.objects[destination_key] = self.objects[source_key]

    def delete_object_best_effort(self, *, bucket, object_key) -> None:
        self.deleted.append((bucket, object_key))
        self.objects.pop(object_key, None)


class RaisingStorage(FakeStorage):
    def put_stream(self, *, bucket, object_key, stream, size_limit, content_type=None):
        _ = bucket, object_key, stream, size_limit, content_type
        raise AppError("PAYLOAD_TOO_LARGE", "Uploaded file is too large.", 413)


class TransactionCheckingStorage(FakeStorage):
    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session
        self.saw_open_transaction = False

    def put_stream(self, *, bucket, object_key, stream, size_limit, content_type=None):
        self.saw_open_transaction = self.session.in_transaction()
        return super().put_stream(
            bucket=bucket,
            object_key=object_key,
            stream=stream,
            size_limit=size_limit,
            content_type=content_type,
        )


def test_run_creation_rejects_missing_cross_workspace_busy_and_cooldown(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    with pytest.raises(AppError) as missing:
        create_protocol_smoke_run(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            selected_node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7Z",
        )
    assert missing.value.code == "RESOURCE_NOT_FOUND"

    node.workspace_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7D"
    db_session.flush()
    with pytest.raises(AppError) as cross:
        create_protocol_smoke_run(
            db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
        )
    assert cross.value.code == "RESOURCE_NOT_FOUND"

    node.workspace_id = DEFAULT_WORKSPACE_ID
    node.status = "offline"
    db_session.flush()
    with pytest.raises(AppError) as busy:
        create_protocol_smoke_run(
            db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
        )
    assert busy.value.code == "LOAD_NODE_BUSY"

    node.status = "idle"
    node.last_force_kill_at = datetime.now(UTC)
    db_session.flush()
    with pytest.raises(AppError) as cooldown:
        create_protocol_smoke_run(
            db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
        )
    assert cooldown.value.code == "LOAD_NODE_ACTION_NOT_ALLOWED"


def test_callback_illegal_finished_before_running_and_unsafe_terminal_enqueues_force_kill(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    illegal = apply_runner_callback(
        db_session,
        callback=callback(
            run,
            "finished",
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7H",
            details={"processGroupExited": True},
        ),
        request_id="req-illegal",
    )
    assert illegal.ignored_reason == "illegal_transition"
    assert run.state == "initializing"

    failed = apply_runner_callback(
        db_session,
        callback=callback(
            run,
            "failed",
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7J",
            details={"processGroupExited": False, "reason": "stale_process_detected"},
        ),
        request_id="req-failed",
    )
    assert failed.state_changed is True
    assert run.state == "failed"
    assert (
        db_session.scalar(
            select(RunControlRequest).where(
                RunControlRequest.run_id == run.id, RunControlRequest.action == "force_kill"
            )
        )
        is not None
    )
    assert node.status == "busy"


def test_stale_process_detected_quarantines_even_when_force_kill_succeeds(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )

    apply_runner_callback(
        db_session,
        callback=callback(
            run,
            "failed",
            event_id="01KT3JRVF275GXM8Q1N9EQM1B5",
            details={"processGroupExited": False, "reason": "stale_process_detected"},
        ),
        request_id="req-stale-process",
    )
    force_kill = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == run.id, RunControlRequest.action == "force_kill"
        )
    )
    assert force_kill is not None

    complete_run_control_request(db_session, request=force_kill, success=True)

    assert node.status == "quarantined"
    assert node.current_run_id is None
    assert node.last_status_reason == "stale_process_detected"
    lease = db_session.scalar(select(NodeLease).where(NodeLease.run_id == run.id))
    assert lease is not None
    assert lease.released_at is not None
    assert lease.release_reason == "stale_process_detected"


def test_release_lease_can_quarantine_and_is_safe_without_active_lease(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.runs import release_run_lease

    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    release_run_lease(db_session, run=run, reason="force_kill_failed", quarantine=True)
    assert node.status == "quarantined"
    assert node.last_status_reason == "force_kill_failed"
    release_run_lease(db_session, run=run, reason="again", quarantine=False)
    assert node.status == "quarantined"


def test_stop_rejects_non_stoppable_non_terminal_state(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    run.state = "pending"
    with pytest.raises(AppError) as exc:
        request_stop(db_session, run=run, actor=user, request_id="req")
    assert exc.value.code == "RUN_STOP_NOT_ALLOWED"


def test_validate_runner_token_accepts_signed_node_token_and_rejects_shared_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.runs import sign_runner_node_token, validate_runner_token

    monkeypatch.setenv("RUNNER_INTERNAL_TOKEN", "runner-secret")
    node_id = new_ulid()
    assert validate_runner_token(sign_runner_node_token(node_id), node_id=node_id) == node_id
    with pytest.raises(AppError):
        validate_runner_token("runner-secret")
    with pytest.raises(AppError):
        validate_runner_token("wrong")


def test_artifact_ingest_does_not_stream_storage_inside_db_transaction(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from io import BytesIO
    from app.services.runs import ingest_run_artifact

    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    data = b"artifact"
    digest = __import__("hashlib").sha256(data).hexdigest()
    storage = TransactionCheckingStorage(db_session)
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: storage)

    ingest_run_artifact(
        db_session,
        event_id="01HZX3Y9M0E9W7Z6M5QK9S8P8A",
        run_id=run.id,
        node_id=node.id,
        authenticated_node_id=node.id,
        artifact_type="run_log",
        relative_path="logs/transaction.log",
        declared_sha256=digest,
        declared_size_bytes=len(data),
        file=BytesIO(data),
        content_type="text/plain",
    )

    assert storage.saw_open_transaction is False


def test_artifact_ingest_loser_cleanup_does_not_delete_winning_object(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from io import BytesIO
    import hashlib
    from app.services.runs import ingest_run_artifact

    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    allocation = db_session.scalar(
        select(RunNodeAllocation).where(RunNodeAllocation.run_id == run.id)
    )
    assert allocation is not None
    data = b"race artifact"
    digest = hashlib.sha256(data).hexdigest()
    winner_artifact_id = "01KT3JRVF275GXM8Q1N9EQM1B6"
    winner_event_id = "01KT3JRVF275GXM8Q1N9EQM1B7"
    loser_artifact_id = "01KT3JRVF275GXM8Q1N9EQM1B8"
    loser_event_id = "01KT3JRVF275GXM8Q1N9EQM1B9"
    winner_key = (
        f"run-artifacts/{run.workspace_id}/{run.id}/nodes/{node.id}/"
        f"allocations/{allocation.id}/logs/race.log"
    )
    monkeypatch.setattr("app.services.runs.new_ulid", lambda: loser_artifact_id)

    class InterleavingStorage(FakeStorage):
        def __init__(self) -> None:
            super().__init__()
            self.objects: dict[str, bytes] = {}
            self.uploaded_key: str | None = None

        def put_stream(self, *, bucket, object_key, stream, size_limit, content_type=None):
            _ = bucket, size_limit, content_type
            payload = stream.read()
            self.uploaded_key = object_key
            self.objects[object_key] = payload
            self.objects[winner_key] = payload
            db_session.add(
                RunArtifact(
                    id=winner_artifact_id,
                    workspace_id=run.workspace_id,
                    run_id=run.id,
                    node_id=node.id,
                    allocation_id=allocation.id,
                    event_id=winner_event_id,
                    artifact_type="run_log",
                    relative_path="logs/race.log",
                    display_filename="race.log",
                    size_bytes=len(payload),
                    sha256=hashlib.sha256(payload).hexdigest(),
                    content_type="text/plain",
                    storage_key=winner_key,
                    status="available",
                    terminal_late=False,
                    created_at=datetime.now(UTC),
                )
            )
            db_session.commit()
            return FakePut(len(payload), hashlib.sha256(payload).hexdigest())

        def delete_object_best_effort(self, *, bucket, object_key) -> None:
            super().delete_object_best_effort(bucket=bucket, object_key=object_key)
            self.objects.pop(object_key, None)

    storage = InterleavingStorage()
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: storage)

    duplicate = ingest_run_artifact(
        db_session,
        event_id=loser_event_id,
        run_id=run.id,
        node_id=node.id,
        authenticated_node_id=node.id,
        artifact_type="run_log",
        relative_path="logs/race.log",
        declared_sha256=digest,
        declared_size_bytes=len(data),
        file=BytesIO(data),
        content_type="text/plain",
    )

    assert duplicate.duplicate is True
    assert duplicate.artifact_id == winner_artifact_id
    assert storage.uploaded_key is not None
    assert f"/.tmp/{loser_artifact_id}/" in storage.uploaded_key
    assert storage.uploaded_key.endswith("/logs/race.log")
    assert storage.deleted == [("surgepilot", storage.uploaded_key)]
    assert winner_key in storage.objects


def test_artifact_ingest_path_conflict_does_not_overwrite_winning_object(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from io import BytesIO
    import hashlib
    from app.core.errors import AppError
    from app.services.runs import ingest_run_artifact

    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    allocation = db_session.scalar(
        select(RunNodeAllocation).where(RunNodeAllocation.run_id == run.id)
    )
    assert allocation is not None
    winner_data = b"winner artifact"
    loser_data = b"loser artifact"
    winner_digest = hashlib.sha256(winner_data).hexdigest()
    loser_digest = hashlib.sha256(loser_data).hexdigest()
    winner_artifact_id = "01KT3JRVF275GXM8Q1N9EQM1C6"
    winner_event_id = "01KT3JRVF275GXM8Q1N9EQM1C7"
    loser_artifact_id = "01KT3JRVF275GXM8Q1N9EQM1C8"
    loser_event_id = "01KT3JRVF275GXM8Q1N9EQM1C9"
    winner_key = (
        f"run-artifacts/{run.workspace_id}/{run.id}/nodes/{node.id}/"
        f"allocations/{allocation.id}/logs/race.log"
    )
    monkeypatch.setattr("app.services.runs.new_ulid", lambda: loser_artifact_id)

    class InterleavingConflictStorage(FakeStorage):
        def __init__(self) -> None:
            super().__init__()
            self.uploaded_key: str | None = None

        def put_stream(self, *, bucket, object_key, stream, size_limit, content_type=None):
            _ = bucket, size_limit, content_type
            payload = stream.read()
            self.uploaded_key = object_key
            self.objects[object_key] = payload
            self.objects[winner_key] = winner_data
            db_session.add(
                RunArtifact(
                    id=winner_artifact_id,
                    workspace_id=run.workspace_id,
                    run_id=run.id,
                    node_id=node.id,
                    allocation_id=allocation.id,
                    event_id=winner_event_id,
                    artifact_type="run_log",
                    relative_path="logs/race.log",
                    display_filename="race.log",
                    size_bytes=len(winner_data),
                    sha256=winner_digest,
                    content_type="text/plain",
                    storage_key=winner_key,
                    status="available",
                    terminal_late=False,
                    created_at=datetime.now(UTC),
                )
            )
            db_session.commit()
            return FakePut(len(payload), hashlib.sha256(payload).hexdigest())

    storage = InterleavingConflictStorage()
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: storage)

    with pytest.raises(AppError) as conflict:
        ingest_run_artifact(
            db_session,
            event_id=loser_event_id,
            run_id=run.id,
            node_id=node.id,
            authenticated_node_id=node.id,
            artifact_type="run_log",
            relative_path="logs/race.log",
            declared_sha256=loser_digest,
            declared_size_bytes=len(loser_data),
            file=BytesIO(loser_data),
            content_type="text/plain",
        )

    assert conflict.value.code == "ARTIFACT_PATH_CONFLICT"
    assert storage.uploaded_key is not None
    assert storage.uploaded_key not in storage.objects
    assert storage.objects[winner_key] == winner_data


def test_copy_artifact_object_fallback_and_unavailable_error() -> None:
    from app.core.errors import AppError
    from app.services.runs import _copy_artifact_object

    class ObjectDictStorage:
        def __init__(self) -> None:
            self.objects = {"tmp/source": b"payload"}

    storage = ObjectDictStorage()
    _copy_artifact_object(
        bucket="surgepilot",
        source_key="tmp/source",
        destination_key="final/dest",
        storage_client=storage,
    )
    assert storage.objects["final/dest"] == b"payload"

    with pytest.raises(AppError) as exc_info:
        _copy_artifact_object(
            bucket="surgepilot",
            source_key="tmp/missing",
            destination_key="final/missing",
            storage_client=object(),
        )
    assert exc_info.value.code == "STORAGE_UNAVAILABLE"


def test_artifact_ingest_cleans_final_object_when_metadata_write_fails(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from io import BytesIO
    import hashlib
    from app.core.errors import AppError
    from app.services.runs import ingest_run_artifact

    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    data = b"artifact"
    digest = hashlib.sha256(data).hexdigest()
    storage = FakeStorage()
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: storage)

    def fail_audit(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AppError("AUDIT_FAILED", "Audit failed.", 500)

    monkeypatch.setattr("app.services.runs.write_audit_event", fail_audit)

    with pytest.raises(AppError) as exc_info:
        ingest_run_artifact(
            db_session,
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P8B",
            run_id=run.id,
            node_id=node.id,
            authenticated_node_id=node.id,
            artifact_type="run_log",
            relative_path="logs/fail-after-copy.log",
            declared_sha256=digest,
            declared_size_bytes=len(data),
            file=BytesIO(data),
            content_type="text/plain",
        )

    assert exc_info.value.code == "AUDIT_FAILED"
    final_key = f"run-artifacts/{run.workspace_id}/{run.id}/logs/fail-after-copy.log"
    assert final_key not in storage.objects


def test_artifact_ingest_cleans_final_object_when_commit_fails(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from io import BytesIO
    import hashlib
    from app.core.errors import AppError
    from app.services.runs import ingest_run_artifact

    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    data = b"artifact"
    digest = hashlib.sha256(data).hexdigest()
    storage = FakeStorage()
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: storage)
    original_commit = db_session.commit
    commit_calls = 0

    def fail_second_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1
        if commit_calls == 1:
            original_commit()
            return
        raise AppError("COMMIT_FAILED", "Commit failed.", 500)

    monkeypatch.setattr(db_session, "commit", fail_second_commit)

    with pytest.raises(AppError) as exc_info:
        ingest_run_artifact(
            db_session,
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P8C",
            run_id=run.id,
            node_id=node.id,
            authenticated_node_id=node.id,
            artifact_type="run_log",
            relative_path="logs/fail-commit.log",
            declared_sha256=digest,
            declared_size_bytes=len(data),
            file=BytesIO(data),
            content_type="text/plain",
        )

    assert exc_info.value.code == "COMMIT_FAILED"
    final_key = f"run-artifacts/{run.workspace_id}/{run.id}/logs/fail-commit.log"
    assert final_key not in storage.objects


def test_artifact_ingest_error_and_idempotency_paths(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from io import BytesIO
    from app.services.runs import ingest_run_artifact

    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    data = b"artifact"
    digest = __import__("hashlib").sha256(data).hexdigest()
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: FakeStorage())

    with pytest.raises(AppError) as invalid_type:
        ingest_run_artifact(
            db_session,
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7K",
            run_id=run.id,
            node_id=node.id,
            authenticated_node_id=node.id,
            artifact_type="zip",
            relative_path="logs/a.log",
            declared_sha256=digest,
            declared_size_bytes=len(data),
            file=BytesIO(data),
            content_type="text/plain",
        )
    assert invalid_type.value.code == "INVALID_ARTIFACT_TYPE"

    with pytest.raises(AppError) as forbidden:
        ingest_run_artifact(
            db_session,
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7L",
            run_id=run.id,
            node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7Z",
            authenticated_node_id="01HZX3Y9M0E9W7Z6M5QK9S8P7Z",
            artifact_type="run_log",
            relative_path="logs/a.log",
            declared_sha256=digest,
            declared_size_bytes=len(data),
            file=BytesIO(data),
            content_type="text/plain",
        )
    assert forbidden.value.code == "RUNNER_FORBIDDEN"

    first = ingest_run_artifact(
        db_session,
        event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7M",
        run_id=run.id,
        node_id=node.id,
        authenticated_node_id=node.id,
        artifact_type="run_log",
        relative_path="logs/a.log",
        declared_sha256=digest,
        declared_size_bytes=len(data),
        file=BytesIO(data),
        content_type="text/plain",
    )
    duplicate = ingest_run_artifact(
        db_session,
        event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7M",
        run_id=run.id,
        node_id=node.id,
        authenticated_node_id=node.id,
        artifact_type="run_log",
        relative_path="logs/a.log",
        declared_sha256=digest,
        declared_size_bytes=len(data),
        file=BytesIO(data),
        content_type="text/plain",
    )
    assert duplicate.duplicate is True
    assert duplicate.artifact_id == first.artifact_id

    path_duplicate = ingest_run_artifact(
        db_session,
        event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N",
        run_id=run.id,
        node_id=node.id,
        authenticated_node_id=node.id,
        artifact_type="run_log",
        relative_path="logs/a.log",
        declared_sha256=digest,
        declared_size_bytes=len(data),
        file=BytesIO(data),
        content_type="text/plain",
    )
    assert path_duplicate.duplicate is True
    with pytest.raises(AppError) as conflict:
        ingest_run_artifact(
            db_session,
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7P",
            run_id=run.id,
            node_id=node.id,
            authenticated_node_id=node.id,
            artifact_type="taurus_log",
            relative_path="logs/a.log",
            declared_sha256=digest,
            declared_size_bytes=len(data),
            file=BytesIO(data),
            content_type="text/plain",
        )
    assert conflict.value.code == "ARTIFACT_PATH_CONFLICT"

    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: FakeStorage(size=999))
    with pytest.raises(AppError) as size:
        ingest_run_artifact(
            db_session,
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7Q",
            run_id=run.id,
            node_id=node.id,
            authenticated_node_id=node.id,
            artifact_type="run_log",
            relative_path="logs/b.log",
            declared_sha256=digest,
            declared_size_bytes=len(data),
            file=BytesIO(data),
            content_type="text/plain",
        )
    assert size.value.code == "ARTIFACT_SIZE_MISMATCH"

    monkeypatch.setattr(
        "app.services.runs.get_storage_client", lambda: FakeStorage(sha256="b" * 64)
    )
    with pytest.raises(AppError) as digest_error:
        ingest_run_artifact(
            db_session,
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7R",
            run_id=run.id,
            node_id=node.id,
            authenticated_node_id=node.id,
            artifact_type="run_log",
            relative_path="logs/c.log",
            declared_sha256=digest,
            declared_size_bytes=len(data),
            file=BytesIO(data),
            content_type="text/plain",
        )
    assert digest_error.value.code == "ARTIFACT_HASH_MISMATCH"


def test_terminal_late_artifact_policy_and_validation_cleanup(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from io import BytesIO
    from app.services.runs import ingest_run_artifact

    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    monkeypatch.setenv("SURGEPILOT_RUN_TERMINAL_LATE_ARTIFACT_MAX_BYTES", "16")
    monkeypatch.setenv("SURGEPILOT_RUN_TERMINAL_LATE_ARTIFACT_SECONDS", "300")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    run.state = "finished"
    run.ended_at = datetime.now(UTC)
    db_session.flush()
    data = b"small artifact"
    digest = __import__("hashlib").sha256(data).hexdigest()
    storage = FakeStorage()
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: storage)

    accepted = ingest_run_artifact(
        db_session,
        event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7W",
        run_id=run.id,
        node_id=node.id,
        authenticated_node_id=node.id,
        artifact_type="run_log",
        relative_path="logs/terminal.log",
        declared_sha256=digest,
        declared_size_bytes=len(data),
        file=BytesIO(data),
        content_type="text/plain",
    )
    artifact = db_session.get(RunArtifact, accepted.artifact_id)
    assert artifact is not None and artifact.terminal_late is True

    run.ended_at = datetime.now(UTC) - timedelta(seconds=301)
    db_session.flush()
    with pytest.raises(AppError) as outside_window:
        ingest_run_artifact(
            db_session,
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7X",
            run_id=run.id,
            node_id=node.id,
            authenticated_node_id=node.id,
            artifact_type="run_log",
            relative_path="logs/too-late.log",
            declared_sha256=digest,
            declared_size_bytes=len(data),
            file=BytesIO(data),
            content_type="text/plain",
        )
    assert outside_window.value.code == "RUN_TERMINAL_STATE"

    run.ended_at = datetime.now(UTC)
    db_session.flush()
    with pytest.raises(AppError) as too_large_declared:
        ingest_run_artifact(
            db_session,
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7Y",
            run_id=run.id,
            node_id=node.id,
            authenticated_node_id=node.id,
            artifact_type="run_log",
            relative_path="logs/too-large.log",
            declared_sha256=digest,
            declared_size_bytes=16,
            file=BytesIO(data),
            content_type="text/plain",
        )
    assert too_large_declared.value.code == "RUN_TERMINAL_STATE"

    actual_too_large_storage = FakeStorage(size=16)
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: actual_too_large_storage)
    with pytest.raises(AppError) as too_large_actual:
        ingest_run_artifact(
            db_session,
            event_id="01KT3JRVF275GXM8Q1N9EQM1B2",
            run_id=run.id,
            node_id=node.id,
            authenticated_node_id=node.id,
            artifact_type="run_log",
            relative_path="logs/actual-too-large.log",
            declared_sha256=digest,
            declared_size_bytes=len(data),
            file=BytesIO(data),
            content_type="text/plain",
        )
    assert too_large_actual.value.code == "RUN_TERMINAL_STATE"
    assert actual_too_large_storage.deleted

    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: RaisingStorage())
    with pytest.raises(AppError) as stream_too_large:
        ingest_run_artifact(
            db_session,
            event_id="01KT3JRVF275GXM8Q1N9EQM1B3",
            run_id=run.id,
            node_id=node.id,
            authenticated_node_id=node.id,
            artifact_type="run_log",
            relative_path="logs/stream-too-large.log",
            declared_sha256=digest,
            declared_size_bytes=len(data),
            file=BytesIO(data),
            content_type="text/plain",
        )
    assert stream_too_large.value.code == "RUN_TERMINAL_STATE"

    run.ended_at = None
    db_session.flush()
    with pytest.raises(AppError) as missing_ended_at:
        ingest_run_artifact(
            db_session,
            event_id="01KT3JRVF275GXM8Q1N9EQM1B4",
            run_id=run.id,
            node_id=node.id,
            authenticated_node_id=node.id,
            artifact_type="run_log",
            relative_path="logs/missing-ended-at.log",
            declared_sha256=digest,
            declared_size_bytes=len(data),
            file=BytesIO(data),
            content_type="text/plain",
        )
    assert missing_ended_at.value.code == "RUN_TERMINAL_STATE"

    run.ended_at = datetime.now(UTC)
    db_session.flush()
    mismatch_storage = FakeStorage(size=len(data), sha256="b" * 64)
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: mismatch_storage)
    with pytest.raises(AppError) as digest_error:
        ingest_run_artifact(
            db_session,
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7Z",
            run_id=run.id,
            node_id=node.id,
            authenticated_node_id=node.id,
            artifact_type="run_log",
            relative_path="logs/hash-mismatch.log",
            declared_sha256=digest,
            declared_size_bytes=len(data),
            file=BytesIO(data),
            content_type="text/plain",
        )
    assert digest_error.value.code == "ARTIFACT_HASH_MISMATCH"
    assert mismatch_storage.deleted


def test_start_control_failure_can_release_without_quarantining_node(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    request = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == run.id, RunControlRequest.action == "start"
        )
    )
    assert request is not None
    request.status = "running"
    db_session.flush()

    complete_run_control_request(
        db_session,
        request=request,
        success=False,
        error_code="RUN_BUNDLE_BUILD_FAILED",
        error_message="Run execution bundle could not be prepared.",
        quarantine_node=False,
    )

    assert run.state == "failed"
    assert node.status == "idle"
    assert node.current_run_id is None
    quarantined_event = db_session.scalar(
        select(AuditEvent).where(AuditEvent.event_type == "load_node.quarantined")
    )
    assert quarantined_event is None


def test_start_host_key_failure_releases_to_uninitialized_without_quarantine(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    request = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == run.id, RunControlRequest.action == "start"
        )
    )
    assert request is not None
    request.status = "running"
    db_session.flush()

    complete_run_control_request(
        db_session,
        request=request,
        success=False,
        error_code="RUN_CONTROL_SSH_HOST_KEY_UNTRUSTED",
        error_message="Run control SSH host key verification failed.",
        quarantine_node=False,
    )

    assert run.state == "failed"
    assert node.status == "uninitialized"
    assert node.current_run_id is None
    assert node.last_status_reason == "RUN_CONTROL_SSH_HOST_KEY_UNTRUSTED"
    lease = db_session.scalar(select(NodeLease).where(NodeLease.run_id == run.id))
    assert lease is not None and lease.released_at is not None
    assert lease.release_reason == "runner_start_failed"
    quarantined_event = db_session.scalar(
        select(AuditEvent).where(AuditEvent.event_type == "load_node.quarantined")
    )
    assert quarantined_event is None


def test_build_run_control_command_missing_trusted_host_key_fails_request(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.runs import build_run_control_command, claim_next_run_control_request

    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    node.ssh_host_key_algorithm = None
    node.ssh_host_key_public_key = None
    node.ssh_host_key_fingerprint_sha256 = None
    db_session.flush()

    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    request = claim_next_run_control_request(db_session)
    assert request is not None

    assert build_run_control_command(db_session, request=request) is None

    assert request.status == "failed"
    assert request.last_error_code == "RUN_CONTROL_SSH_HOST_KEY_UNTRUSTED"
    assert run.state == "failed"
    assert node.status == "uninitialized"
    assert node.current_run_id is None
    assert node.last_status_reason == "RUN_CONTROL_SSH_HOST_KEY_UNTRUSTED"
    quarantined_event = db_session.scalar(
        select(AuditEvent).where(AuditEvent.event_type == "load_node.quarantined")
    )
    assert quarantined_event is None


def test_run_control_and_recovery_helpers_cover_failure_paths(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.runs import (
        RunControlExecutor,
        build_run_control_command,
        claim_next_run_control_request,
        complete_run_control_request,
        enqueue_control_request,
        recover_stale_leases,
    )

    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    request = claim_next_run_control_request(db_session)
    assert request is not None
    with pytest.raises(NotImplementedError):
        RunControlExecutor().execute(build_run_control_command(db_session, request=request))

    request.status = "failed"
    db_session.flush()
    assert build_run_control_command(db_session, request=request) is None
    request.status = "running"
    request.run_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7Z"
    db_session.flush()
    assert build_run_control_command(db_session, request=request) is None
    request.run_id = run.id
    request.node_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7Z"
    db_session.flush()
    assert build_run_control_command(db_session, request=request) is None
    request.node_id = node.id
    db_session.flush()

    allocation = db_session.scalar(
        select(RunNodeAllocation).where(RunNodeAllocation.run_id == run.id)
    )
    assert allocation is not None
    stop_request = enqueue_control_request(
        db_session, run=run, action="stop", allocation=allocation
    )
    stop_request.status = "running"
    run.state = "running"
    db_session.flush()
    assert build_run_control_command(db_session, request=stop_request) is None
    stop_request.status = "failed"
    run.state = "initializing"
    db_session.flush()

    complete_run_control_request(db_session, request=request, success=False)
    assert request.status == "failed"
    assert run.state == "failed"
    assert node.status == "quarantined"

    node2 = idle_node(db_session, user)
    run2 = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node2.id
    )
    run2.state = "failed"
    db_session.flush()
    assert recover_stale_leases(db_session) == 1
    lease2 = db_session.scalar(select(NodeLease).where(NodeLease.run_id == run2.id))
    force_kill2 = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == run2.id, RunControlRequest.action == "force_kill"
        )
    )
    assert lease2 is not None and lease2.released_at is None
    assert force_kill2 is not None and force_kill2.status == "pending"


def test_additional_state_machine_branches_for_review_coverage(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from io import BytesIO
    from app.services.runs import (
        _force_converge,
        ingest_run_artifact,
        validate_artifact_relative_path,
    )

    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    run.state = "running"
    db_session.flush()

    ignored_running = apply_runner_callback(
        db_session,
        callback=callback(run, "running", event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7S"),
        request_id="req-running-again",
    )
    assert ignored_running.ignored_reason == "illegal_transition"

    artifact_callback = apply_runner_callback(
        db_session,
        callback=callback(
            run,
            "artifact",
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7T",
            details={
                "artifactId": "01HZX3Y9M0E9W7Z6M5QK9S8P7U",
                "artifactType": "run_log",
                "relativePath": "logs/a.log",
                "sizeBytes": 1,
                "sha256": "a" * 64,
            },
        ),
        request_id="req-artifact",
    )
    assert artifact_callback.state_changed is False

    assert (
        _force_converge(
            db_session,
            run=run,
            target_state="aborted",
            reason="stop_grace_timeout",
            forced=True,
            now=datetime.now(UTC),
        )
        is False
    )
    assert (
        _force_converge(
            db_session,
            run=run,
            target_state="failed",
            reason="heartbeat_timeout",
            forced=False,
            now=datetime.now(UTC),
        )
        is True
    )
    assert (
        _force_converge(
            db_session,
            run=run,
            target_state="failed",
            reason="heartbeat_timeout",
            forced=False,
            now=datetime.now(UTC),
        )
        is False
    )

    with pytest.raises(AppError):
        validate_artifact_relative_path("")
    with pytest.raises(AppError) as negative:
        ingest_run_artifact(
            db_session,
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7V",
            run_id=run.id,
            node_id=node.id,
            authenticated_node_id=node.id,
            artifact_type="run_log",
            relative_path="logs/negative.log",
            declared_sha256="a" * 64,
            declared_size_bytes=-1,
            file=BytesIO(b"x"),
            content_type="text/plain",
        )
    assert negative.value.code == "ARTIFACT_SIZE_MISMATCH"
