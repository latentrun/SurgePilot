from datetime import UTC, datetime, timedelta
import hashlib
import json
from io import BytesIO

import pytest
from sqlalchemy import func, select
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
    RunSnapshot,
)
from app.schemas.load_nodes import LoadNodeCredentialInput
from app.services.load_nodes import create_load_node
from app.services.runs import (
    RUN_TRANSITIONS,
    CallbackResult,
    RunExecutionInput,
    RunnerCallbackInput,
    apply_runner_callback as service_apply_runner_callback,
    create_protocol_smoke_run,
    create_run_execution,
    ingest_run_artifact,
    release_run_lease,
    request_stop,
    request_stop_by_id,
    validate_artifact_relative_path,
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
) -> RunnerCallbackInput:
    payload_node_id = node_id or run.selected_node_id
    return RunnerCallbackInput(
        schema_version="1",
        event_id=event_id,
        run_id=run.id,
        node_id=payload_node_id,
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
            "nodeId": payload_node_id,
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


def smoke_run(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> tuple[Run, LoadNode, User]:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    run = create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    return run, node, user


def running_run(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> tuple[Run, LoadNode, User]:
    run, node, user = smoke_run(db_session, monkeypatch)
    apply_runner_callback(
        db_session,
        callback=callback(run, "accepted", event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7C", runner_pid=1234),
        request_id="req-accepted",
    )
    apply_runner_callback(
        db_session,
        callback=callback(run, "running", event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7D"),
        request_id="req-running",
    )
    return run, node, user


def artifact_bytes(size: int = 16) -> tuple[bytes, str, int]:
    content = bytes((index % 251 for index in range(size)))
    return content, hashlib.sha256(content).hexdigest(), len(content)


class FakePut:
    def __init__(self, *, size_bytes: int, sha256: str) -> None:
        self.size_bytes = size_bytes
        self.sha256 = sha256


class FakeStorage:
    def __init__(
        self, *, declared_size: int | None = None, declared_sha256: str | None = None
    ) -> None:
        self.objects: dict[str, bytes] = {}
        self.declared_size = declared_size
        self.declared_sha256 = declared_sha256

    def put_stream(  # noqa: ANN001
        self, *, bucket, object_key, stream, size_limit, content_type=None
    ):
        data = stream.read()
        if len(data) > size_limit:
            raise AppError("PAYLOAD_TOO_LARGE", "Uploaded file is too large.", 413)
        self.objects[object_key] = data
        size_bytes = self.declared_size if self.declared_size is not None else len(data)
        sha256 = self.declared_sha256 or hashlib.sha256(data).hexdigest()
        return FakePut(size_bytes=size_bytes, sha256=sha256)

    def copy_object(self, *, bucket, source_key, destination_key):  # noqa: ANN001
        if source_key not in self.objects:
            raise AppError("STORAGE_UNAVAILABLE", "Storage is unavailable.", 503)
        self.objects[destination_key] = self.objects[source_key]

    def delete_object_best_effort(self, *, bucket, object_key):  # noqa: ANN001
        self.objects.pop(object_key, None)
        return True


def test_run_creation_creates_snapshot_lease_busy_node_and_start_request(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run, node, _ = smoke_run(db_session, monkeypatch)

    assert run.state == "initializing"
    assert run.remote_start_requested_at is not None
    snapshot = db_session.scalar(select(RunSnapshot).where(RunSnapshot.run_id == run.id))
    assert snapshot is not None
    assert snapshot.snapshot_json["sourceType"] == "protocol_smoke"
    assert snapshot.snapshot_json["runType"] == "debug"
    assert snapshot.snapshot_json["actorId"] == run.triggered_by_user_id
    assert snapshot.snapshot_json["protocolSchemaVersion"] == 1
    assert snapshot.snapshot_json["selectedNode"]["id"] == node.id
    assert "sourceId" not in snapshot.snapshot_json
    expected_hash = hashlib.sha256(
        json.dumps(
            snapshot.snapshot_json, sort_keys=True, separators=(",", ":"), default=str
        ).encode()
    ).hexdigest()
    assert snapshot.snapshot_hash == expected_hash

    lease = db_session.scalar(select(NodeLease).where(NodeLease.run_id == run.id))
    assert lease is not None
    assert lease.released_at is None
    assert node.status == "busy"
    assert node.current_run_id == run.id
    request = db_session.scalar(
        select(RunControlRequest).where(RunControlRequest.run_id == run.id)
    )
    assert request is not None
    assert request.action == "start"
    assert request.status == "pending"


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
    request = db_session.scalar(
        select(RunControlRequest).where(RunControlRequest.run_id == run.id)
    )
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
    run, node, user = smoke_run(db_session, monkeypatch)

    with pytest.raises(AppError) as exc:
        create_protocol_smoke_run(
            db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
        )

    assert run.id != ""
    assert exc.value.code == "LOAD_NODE_BUSY"


def test_run_creation_rejects_missing_cross_workspace_busy_and_cooldown_nodes(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SURGEPILOT_ENABLE_PROTOCOL_SMOKE_RUNS", "true")
    user = actor()
    node = idle_node(db_session, user)
    # Occupy the first node so later attempts against it see a Busy Load Node.
    create_protocol_smoke_run(
        db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
    )
    assert node.status == "busy"

    # A Load Node from another Workspace is not visible for selection.
    other = idle_node(db_session, user)
    other.workspace_id = "01HZX3Y9M0E9W7Z6M5QK9S8P7D"
    db_session.flush()
    with pytest.raises(AppError) as exc:
        create_protocol_smoke_run(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            selected_node_id=other.id,
        )
    assert exc.value.code == "RESOURCE_NOT_FOUND"

    # A node in force-kill cooldown is rejected even when idle.
    cooldown_node = idle_node(db_session, user)
    cooldown_node.status = "idle"
    cooldown_node.last_force_kill_at = datetime.now(UTC)
    db_session.flush()
    with pytest.raises(AppError) as exc:
        create_protocol_smoke_run(
            db_session,
            workspace_id=DEFAULT_WORKSPACE_ID,
            actor=user,
            selected_node_id=cooldown_node.id,
        )
    assert exc.value.code == "LOAD_NODE_ACTION_NOT_ALLOWED"

    # The Busy node is rejected.
    with pytest.raises(AppError) as exc:
        create_protocol_smoke_run(
            db_session, workspace_id=DEFAULT_WORKSPACE_ID, actor=user, selected_node_id=node.id
        )
    assert exc.value.code == "LOAD_NODE_BUSY"


def test_transition_table_covers_expected_states() -> None:
    assert RUN_TRANSITIONS["running"] == {"initializing"}
    assert RUN_TRANSITIONS["finished"] == {"running"}
    assert RUN_TRANSITIONS["aborted"] == {"initializing", "running", "stopping"}
    assert RUN_TRANSITIONS["failed"] == {"initializing", "running", "stopping"}


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


def test_callback_details_are_sanitized_and_duplicates_ignored(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    run, _, _ = smoke_run(db_session, monkeypatch)

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


def test_callbacks_apply_state_and_terminal_release(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run, node, _ = smoke_run(db_session, monkeypatch)

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
    assert run.started_at is not None

    heartbeat = apply_runner_callback(
        db_session,
        callback=callback(run, "heartbeat", event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7E"),
        request_id="req-3",
    )
    assert heartbeat.state_changed is False
    assert run.state == "running"
    assert run.last_heartbeat_at is not None
    assert node.last_heartbeat_at == run.last_heartbeat_at

    artifact_event = apply_runner_callback(
        db_session,
        callback=callback(
            run,
            "artifact",
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7A",
            details={"relativePath": "results/run.log", "artifactType": "run_log"},
        ),
        request_id="req-artifact",
    )
    assert artifact_event.state_changed is False
    assert run.state == "running"

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
    run, _, _ = smoke_run(db_session, monkeypatch)
    apply_runner_callback(
        db_session,
        callback=callback(run, "accepted", event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7C", runner_pid=1234),
        request_id="req-1",
    )
    apply_runner_callback(
        db_session,
        callback=callback(run, "running", event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7D"),
        request_id="req-2",
    )
    apply_runner_callback(
        db_session,
        callback=callback(
            run,
            "finished",
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7F",
            details={"processGroupExited": True},
        ),
        request_id="req-3",
    )
    assert run.state == "finished"

    late = apply_runner_callback(
        db_session,
        callback=callback(run, "heartbeat", event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7E"),
        request_id="req-late",
    )
    assert late.accepted is True
    assert late.duplicate is False
    assert late.state_changed is False
    assert late.current_state == "finished"
    assert late.ignored_reason == "terminal_state_protected"
    assert run.state == "finished"

    late_failed = apply_runner_callback(
        db_session,
        callback=callback(
            run,
            "failed",
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7G",
            details={"processGroupExited": True, "reason": "runner_exit_nonzero"},
        ),
        request_id="req-late-failed",
    )
    assert late_failed.ignored_reason == "terminal_state_protected"
    assert run.state == "finished"
    assert run.failure_reason is None


def test_duplicate_callback_same_hash_is_noop_and_different_hash_conflicts(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run, _, _ = smoke_run(db_session, monkeypatch)
    original = callback(
        run, "running", event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7D", details={"safe": "value"}
    )
    first = apply_runner_callback(db_session, callback=original, request_id="req-1")
    duplicate = apply_runner_callback(db_session, callback=original, request_id="req-2")
    assert first.state_changed is True
    assert duplicate.duplicate is True
    assert duplicate.state_changed is False

    conflicting = callback(
        run, "running", event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7D", details={"safe": "other"}
    )
    with pytest.raises(AppError) as exc:
        apply_runner_callback(db_session, callback=conflicting, request_id="req-3")
    assert exc.value.code == "RUNNER_CALLBACK_CONFLICT"


def test_illegal_finished_before_running_is_ignored(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run, _, _ = smoke_run(db_session, monkeypatch)
    result = apply_runner_callback(
        db_session,
        callback=callback(
            run,
            "finished",
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7F",
            details={"processGroupExited": True},
        ),
        request_id="req-illegal",
    )
    assert result.state_changed is False
    assert result.ignored_reason == "illegal_transition"
    assert run.state == "initializing"


def test_unsafe_terminal_callback_keeps_lease_and_enqueues_force_kill(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run, node, _ = running_run(db_session, monkeypatch)

    result = apply_runner_callback(
        db_session,
        callback=callback(
            run,
            "failed",
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7G",
            details={"processGroupExited": False, "reason": "runner_exit_nonzero"},
        ),
        request_id="req-failed",
    )

    assert result.state_changed is True
    assert run.state == "failed"
    assert run.failure_reason == "runner_exit_nonzero"
    assert run.failure_message is not None
    lease = db_session.scalar(select(NodeLease).where(NodeLease.run_id == run.id))
    assert lease is not None
    assert lease.released_at is None
    assert node.status == "busy"
    assert node.current_run_id == run.id
    force_kill = db_session.scalar(
        select(RunControlRequest).where(
            RunControlRequest.run_id == run.id, RunControlRequest.action == "force_kill"
        )
    )
    assert force_kill is not None
    assert force_kill.status == "pending"


def test_aborted_callback_converges_stop(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run, node, user = running_run(db_session, monkeypatch)
    result = request_stop(db_session, run=run, actor=user)
    assert result.status_code == 202
    assert run.state == "stopping"

    aborted = apply_runner_callback(
        db_session,
        callback=callback(
            run,
            "aborted",
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7H",
            details={"processGroupExited": True, "reason": "stop_requested"},
        ),
        request_id="req-aborted",
    )
    assert aborted.state_changed is True
    assert run.state == "aborted"
    assert run.failure_reason == "stop_requested"
    lease = db_session.scalar(select(NodeLease).where(NodeLease.run_id == run.id))
    assert lease is not None
    assert lease.released_at is not None
    assert lease.release_reason == "aborted"
    assert node.status == "idle"
    assert node.current_run_id is None


def test_runner_node_mismatch_is_forbidden(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run, _, user = smoke_run(db_session, monkeypatch)
    other_node = idle_node(db_session, user)

    with pytest.raises(AppError) as exc:
        apply_runner_callback(
            db_session,
            callback=callback(run, "running", event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7D"),
            request_id="req-other-node",
            authenticated_node_id=other_node.id,
        )
    assert exc.value.code == "RUNNER_FORBIDDEN"

    with pytest.raises(AppError) as exc:
        apply_runner_callback(
            db_session,
            callback=callback(
                run, "running", event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7E", node_id=other_node.id
            ),
            request_id="req-other-payload",
        )
    assert exc.value.code == "RUNNER_FORBIDDEN"


def test_stop_is_idempotent_and_terminal_stop_fails(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run, _, user = running_run(db_session, monkeypatch)

    first = request_stop(db_session, run=run, actor=user)
    assert first.status_code == 202
    assert first.duplicate is False
    assert run.state == "stopping"
    assert run.stop_requested_at is not None
    assert run.stop_requested_by_user_id == user.id
    audit = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "run.stop_requested")
    ).all()
    assert len(audit) == 1

    duplicate = request_stop(db_session, run=run, actor=user)
    assert duplicate.status_code == 200
    assert duplicate.duplicate is True
    stop_requests = db_session.scalars(
        select(RunControlRequest).where(
            RunControlRequest.run_id == run.id, RunControlRequest.action == "stop"
        )
    ).all()
    assert len(stop_requests) == 1
    audit_rows = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "run.stop_requested")
    ).all()
    assert len(audit_rows) == 1

    apply_runner_callback(
        db_session,
        callback=callback(
            run,
            "aborted",
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7H",
            details={"processGroupExited": True, "reason": "stop_requested"},
        ),
        request_id="req-aborted",
    )
    assert run.state == "aborted"
    with pytest.raises(AppError) as exc:
        request_stop(db_session, run=run, actor=user)
    assert exc.value.code == "RUN_TERMINAL_STATE"


def test_request_stop_by_id_is_workspace_scoped(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run, _, user = running_run(db_session, monkeypatch)

    # A Run outside the requested Workspace is not visible to the actor.
    with pytest.raises(AppError) as exc:
        request_stop_by_id(
            db_session,
            run_id=run.id,
            workspace_id="01HZX3Y9M0E9W7Z6M5QK9S8P7D",
            actor=user,
        )
    assert exc.value.code == "RESOURCE_NOT_FOUND"
    assert run.state == "running"

    result = request_stop_by_id(
        db_session,
        run_id=run.id,
        workspace_id=DEFAULT_WORKSPACE_ID,
        actor=user,
    )
    assert result.status_code == 202
    assert run.state == "stopping"


def test_release_lease_can_quarantine_and_is_safe_without_active_lease(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run, node, _ = smoke_run(db_session, monkeypatch)

    release_run_lease(db_session, run=run, reason="force_kill_failed", quarantine=True)
    assert node.status == "quarantined"
    assert node.current_run_id is None
    lease = db_session.scalar(select(NodeLease).where(NodeLease.run_id == run.id))
    assert lease is not None
    assert lease.released_at is not None
    assert lease.release_reason == "force_kill_failed"
    quarantine_audits = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "load_node.quarantined")
    ).all()
    assert len(quarantine_audits) == 1

    # Releasing again is safe even when no active lease remains.
    release_run_lease(db_session, run=run, reason="stale_recovery")


def test_artifact_path_validation_rejects_unsafe_paths() -> None:
    assert validate_artifact_relative_path("artifacts/run.log") == "artifacts/run.log"
    assert validate_artifact_relative_path("results/final_stats.csv") == "results/final_stats.csv"
    for path in [
        "",
        "/abs/run.log",
        "..\\escape",
        "a//b",
        "a/b/../c",
        "./a",
        "with:colon.log",
        "../outside",
    ]:
        with pytest.raises(AppError) as exc:
            validate_artifact_relative_path(path)
        assert exc.value.code == "INVALID_ARTIFACT_PATH"


def test_artifact_ingest_stores_metadata_and_is_idempotent(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run, node, _ = running_run(db_session, monkeypatch)
    storage = FakeStorage()
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: storage)
    content, digest, size = artifact_bytes(32)

    first = ingest_run_artifact(
        db_session,
        event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7J",
        run_id=run.id,
        node_id=node.id,
        artifact_type="run_log",
        relative_path="artifacts/run.log",
        declared_sha256=digest,
        declared_size_bytes=size,
        file=BytesIO(content),
        content_type="text/plain",
    )
    assert first.duplicate is False
    artifact = db_session.scalar(select(RunArtifact).where(RunArtifact.id == first.artifact_id))
    assert artifact is not None
    assert artifact.status == "available"
    assert artifact.display_filename == "run.log"
    assert artifact.size_bytes == size
    assert artifact.sha256 == digest
    assert artifact.workspace_id == DEFAULT_WORKSPACE_ID
    assert artifact.terminal_late is False
    assert artifact.storage_key.startswith("run-artifacts/")
    upload_audits = db_session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "artifact.uploaded")
    ).all()
    assert len(upload_audits) == 1
    assert upload_audits[0].details_json["relativePath"] == "artifacts/run.log"

    duplicate = ingest_run_artifact(
        db_session,
        event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7J",
        run_id=run.id,
        node_id=node.id,
        artifact_type="run_log",
        relative_path="artifacts/run.log",
        declared_sha256=digest,
        declared_size_bytes=size,
        file=BytesIO(content),
        content_type="text/plain",
    )
    assert duplicate.duplicate is True
    assert duplicate.artifact_id == first.artifact_id
    assert run.state == "running"


def test_artifact_ingest_size_and_hash_mismatch_cleanup(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run, node, _ = running_run(db_session, monkeypatch)
    storage = FakeStorage()
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: storage)
    content, digest, size = artifact_bytes(32)

    with pytest.raises(AppError) as exc:
        ingest_run_artifact(
            db_session,
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7K",
            run_id=run.id,
            node_id=node.id,
            artifact_type="run_log",
            relative_path="artifacts/size.log",
            declared_sha256=digest,
            declared_size_bytes=size + 5,
            file=BytesIO(content),
            content_type="text/plain",
        )
    assert exc.value.code == "ARTIFACT_SIZE_MISMATCH"

    with pytest.raises(AppError) as exc:
        ingest_run_artifact(
            db_session,
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7L",
            run_id=run.id,
            node_id=node.id,
            artifact_type="run_log",
            relative_path="artifacts/hash.log",
            declared_sha256="0" * 64,
            declared_size_bytes=size,
            file=BytesIO(content),
            content_type="text/plain",
        )
    assert exc.value.code == "ARTIFACT_HASH_MISMATCH"

    remaining = db_session.scalar(
        select(func.count(RunArtifact.id)).select_from(RunArtifact)
    )
    assert remaining == 0
    assert storage.objects == {}


def test_artifact_path_conflict_does_not_overwrite_winning_object(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run, node, _ = running_run(db_session, monkeypatch)
    storage = FakeStorage()
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: storage)
    first_content, first_digest, first_size = artifact_bytes(32)
    second_content, second_digest, second_size = artifact_bytes(40)

    first = ingest_run_artifact(
        db_session,
        event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7M",
        run_id=run.id,
        node_id=node.id,
        artifact_type="run_log",
        relative_path="artifacts/shared.log",
        declared_sha256=first_digest,
        declared_size_bytes=first_size,
        file=BytesIO(first_content),
        content_type="text/plain",
    )
    assert first.duplicate is False

    with pytest.raises(AppError) as exc:
        ingest_run_artifact(
            db_session,
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7N",
            run_id=run.id,
            node_id=node.id,
            artifact_type="run_log",
            relative_path="artifacts/shared.log",
            declared_sha256=second_digest,
            declared_size_bytes=second_size,
            file=BytesIO(second_content),
            content_type="text/plain",
        )
    assert exc.value.code == "ARTIFACT_PATH_CONFLICT"

    artifact = db_session.scalar(select(RunArtifact).where(RunArtifact.id == first.artifact_id))
    assert artifact is not None
    assert artifact.size_bytes == first_size
    assert artifact.sha256 == first_digest


def test_artifact_ingest_rejects_unknown_type_oversize_and_unknown_run(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run, node, _ = running_run(db_session, monkeypatch)
    content, digest, size = artifact_bytes(8)

    with pytest.raises(AppError) as exc:
        ingest_run_artifact(
            db_session,
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7P",
            run_id=run.id,
            node_id=node.id,
            artifact_type="debug_trace",
            relative_path="artifacts/x.log",
            declared_sha256=digest,
            declared_size_bytes=size,
            file=BytesIO(content),
            content_type="text/plain",
        )
    assert exc.value.code == "INVALID_ARTIFACT_TYPE"

    monkeypatch.setenv("SURGEPILOT_RUN_ARTIFACT_MAX_BYTES", "64")
    with pytest.raises(AppError) as exc:
        ingest_run_artifact(
            db_session,
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7Q",
            run_id=run.id,
            node_id=node.id,
            artifact_type="run_log",
            relative_path="artifacts/big.log",
            declared_sha256=digest,
            declared_size_bytes=128,
            file=BytesIO(content * 16),
            content_type="text/plain",
        )
    assert exc.value.code == "PAYLOAD_TOO_LARGE"

    with pytest.raises(AppError) as exc:
        ingest_run_artifact(
            db_session,
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7R",
            run_id="01HZX3Y9M0E9W7Z6M5QK9S8P7Z",
            node_id=node.id,
            artifact_type="run_log",
            relative_path="artifacts/unknown.log",
            declared_sha256=digest,
            declared_size_bytes=size,
            file=BytesIO(content),
            content_type="text/plain",
        )
    assert exc.value.code == "RESOURCE_NOT_FOUND"


def test_terminal_late_artifact_policy(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    run, node, _ = smoke_run(db_session, monkeypatch)
    apply_runner_callback(
        db_session,
        callback=callback(
            run,
            "finished",
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7F",
            details={"processGroupExited": True},
        ),
        request_id="req-finished",
    )
    assert run.state == "finished"
    storage = FakeStorage()
    monkeypatch.setattr("app.services.runs.get_storage_client", lambda: storage)
    content, digest, size = artifact_bytes(32)

    # A small terminal-late upload inside the window is accepted.
    result = ingest_run_artifact(
        db_session,
        event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7T",
        run_id=run.id,
        node_id=node.id,
        artifact_type="run_log",
        relative_path="artifacts/late.log",
        declared_sha256=digest,
        declared_size_bytes=size,
        file=BytesIO(content),
        content_type="text/plain",
    )
    artifact = db_session.scalar(select(RunArtifact).where(RunArtifact.id == result.artifact_id))
    assert artifact is not None
    assert artifact.terminal_late is True

    # A terminal-late upload that exceeds the late limit is rejected.
    run.ended_at = datetime.now(UTC) - timedelta(seconds=60)
    db_session.flush()
    with pytest.raises(AppError) as exc:
        ingest_run_artifact(
            db_session,
            event_id="01HZX3Y9M0E9W7Z6M5QK9S8P7U",
            run_id=run.id,
            node_id=node.id,
            artifact_type="run_log",
            relative_path="artifacts/late-big.log",
            declared_sha256=digest,
            declared_size_bytes=2048 * 1024,
            file=BytesIO(content),
            content_type="text/plain",
        )
    assert exc.value.code == "RUN_TERMINAL_STATE"
